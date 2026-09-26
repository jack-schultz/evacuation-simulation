"""Discrete-time evacuation simulation engine."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math

from app.domain.building import (
    BuildingLayout,
    OccupantFrameState,
    OccupantStatus,
    SimulationFrame,
    SimulationParameters,
    SimulationResults,
)
from app.simulation.collision import (
    Aabb,
    aperture_slots,
    build_collision_solids,
    clamp_outside_throat,
    dist,
    in_throat,
    resolve_overlaps,
    resolve_space_containment,
    resolve_wall_collisions,
)
from app.simulation.flood import FloodRouteSelector, apply_flood
from app.simulation.flow import CapacityFlowModel, ElementQueueState, FlowModel
from app.simulation.graph import EdgeKind, NavigationGraphBuilder, NodeKind
from app.simulation.movement import SimulatedOccupant, SpatialMovementModel
from app.simulation.pixel_obstacles import position_is_walkable
from app.simulation.results import build_results
from app.simulation.routing import DijkstraRouteSelector, RouteSelector, edge_between


@dataclass
class SimulationOutput:
    results: SimulationResults
    frames: list[SimulationFrame]


class SimulationEngine:
    """Runs a discrete-time evacuation over a building navigation graph.

    Occupants steer continuously toward fixed Dijkstra waypoints, collide via
    body radius and space boundaries, and pass doors/exits through width-limited
    apertures.
    """

    def __init__(
        self,
        route_selector: RouteSelector | None = None,
        flow_model: FlowModel | None = None,
        movement_model: SpatialMovementModel | None = None,
    ) -> None:
        self.route_selector = route_selector or DijkstraRouteSelector()
        self.flow_model = flow_model  # may be set per-run with radius
        self._flow_model_override = flow_model
        self.movement_model = movement_model or SpatialMovementModel()
        self.graph_builder = NavigationGraphBuilder()

    def run(self, layout: BuildingLayout, params: SimulationParameters) -> SimulationOutput:
        if not layout.exits:
            raise ValueError("Building must have at least one exit")
        if not layout.occupant_groups:
            raise ValueError("Building must have at least one occupant group")

        if self._flow_model_override is not None:
            self.flow_model = self._flow_model_override
        else:
            self.flow_model = CapacityFlowModel(occupant_radius_m=params.occupant_radius_m)

        defaults = {
            "door_flow_per_s": params.door_flow_per_s,
            "stairs_flow_per_s": params.stairs_flow_per_s,
            "exit_flow_per_s": params.exit_flow_per_s,
            "corridor_density_per_m2": params.corridor_density_per_m2,
        }
        graph = self.graph_builder.build(layout, defaults)
        apply_flood(graph, layout.flood)

        boundary_solids = build_collision_solids(
            layout.spaces, layout.doors, layout.exits
        )
        spaces = {s.id: s for s in layout.spaces}
        doors = {d.id: d for d in layout.doors}
        occupants = self._spawn_occupants(
            layout, graph, params.occupant_radius_m, boundary_solids, spaces, doors
        )
        queues: dict[str, ElementQueueState] = {}
        frames: list[SimulationFrame] = []
        t = 0.0
        next_frame_t = 0.0

        frames.append(self._capture_frame(t, occupants))
        next_frame_t = params.frame_interval_s

        while t < params.max_time_s:
            if all(o.status == OccupantStatus.EVACUATED for o in occupants):
                break

            t += params.timestep_s
            self._step(
                occupants, graph, queues, params, t, boundary_solids, spaces, doors,
                layout.obstacle_map, layout.width, layout.height,
            )

            if t + 1e-9 >= next_frame_t:
                frames.append(self._capture_frame(t, occupants))
                next_frame_t += params.frame_interval_s

        if not frames or frames[-1].t < t:
            frames.append(self._capture_frame(t, occupants))

        results = build_results(occupants, queues, t)
        return SimulationOutput(results=results, frames=frames)

    def _spawn_occupants(
        self,
        layout: BuildingLayout,
        graph,
        radius_m: float,
        boundary_solids: list[Aabb] | None = None,
        spaces: dict | None = None,
        doors: dict | None = None,
    ) -> list[SimulatedOccupant]:
        occupants: list[SimulatedOccupant] = []
        spaces = spaces if spaces is not None else {s.id: s for s in layout.spaces}
        doors = doors if doors is not None else {d.id: d for d in layout.doors}
        spacing = max(2.0 * radius_m + 0.05, 0.45)
        margin = radius_m + 0.1
        solids = boundary_solids or []

        for group in layout.occupant_groups:
            start_node = graph.space_node_ids[group.space_id]
            selector = (
                FloodRouteSelector()
                if layout.flood
                and layout.flood.enabled
                and layout.flood.intensity > 0
                and isinstance(self.route_selector, DijkstraRouteSelector)
                else self.route_selector
            )
            route = selector.select_route(
                graph, start_node, preferred_exit_id=group.destination_exit_id
            )
            space = spaces[group.space_id]
            node = graph.nodes[start_node]
            spawn_x = group.spawn_x if group.spawn_x is not None else node.x
            spawn_y = group.spawn_y if group.spawn_y is not None else node.y
            interior_left = space.x + margin
            interior_right = space.x + space.width - margin
            interior_top = space.y + margin
            interior_bottom = space.y + space.height - margin
            max_cols = max(1, int(max(space.width - 2 * margin, 0) / spacing) + 1)
            cols = min(max_cols, max(1, math.ceil(math.sqrt(group.count))))
            rows = math.ceil(group.count / cols)
            half_width = (cols - 1) * spacing / 2
            half_height = (rows - 1) * spacing / 2
            center_x = min(max(spawn_x, interior_left + half_width), interior_right - half_width)
            center_y = min(max(spawn_y, interior_top + half_height), interior_bottom - half_height)
            # If the formation is larger than the room's usable area, center it
            # in the room and let overlap resolution handle the tight spacing.
            if interior_left + half_width > interior_right - half_width:
                center_x = (interior_left + interior_right) / 2
            if interior_top + half_height > interior_bottom - half_height:
                center_y = (interior_top + interior_bottom) / 2
            for i in range(group.count):
                if group.count == 1:
                    ox, oy = spawn_x, spawn_y
                else:
                    col = i % cols
                    row = i // cols
                    row_size = min(cols, group.count - row * cols)
                    ox = center_x + (col - (row_size - 1) / 2) * spacing
                    oy = center_y + (row - (rows - 1) / 2) * spacing
                occupants.append(
                    SimulatedOccupant(
                        id=f"{group.id}:{i}",
                        group_id=group.id,
                        speed_mps=group.walking_speed_mps,
                        route=list(route),
                        current_space_id=group.space_id,
                        status=OccupantStatus.TRAPPED if len(route) == 1 else OccupantStatus.ACTIVE,
                        x=ox,
                        y=oy,
                        aperture_slot=i,
                    )
                )
        resolve_overlaps(occupants, radius_m, iterations=6)
        resolve_wall_collisions(occupants, solids, radius_m)
        resolve_space_containment(occupants, spaces, doors, graph, radius_m)
        for occupant in occupants:
            if not position_is_walkable(
                layout.obstacle_map, occupant.x, occupant.y, radius_m, layout.width, layout.height
            ):
                replacement = self._nearby_walkable_point(
                    layout, occupant.x, occupant.y, radius_m, spaces[occupant.current_space_id]
                )
                if replacement is None:
                    occupant.status = OccupantStatus.TRAPPED
                else:
                    occupant.x, occupant.y = replacement
        return occupants

    @staticmethod
    def _nearby_walkable_point(layout: BuildingLayout, x: float, y: float, radius: float, space):
        raster = layout.obstacle_map
        if raster is None:
            return None
        step = min(layout.width / raster.width, layout.height / raster.height)
        for ring in range(1, max(raster.width, raster.height)):
            distance = ring * step
            if distance > 3.0:
                break
            sample_count = max(8, int(8 * ring))
            for i in range(sample_count):
                angle = 2 * 3.141592653589793 * i / sample_count
                px, py = x + distance * math.cos(angle), y + distance * math.sin(angle)
                if space.x <= px <= space.x + space.width and space.y <= py <= space.y + space.height and position_is_walkable(
                    raster, px, py, radius, layout.width, layout.height
                ):
                    return px, py
        return None

    def _step(
        self,
        occupants: list[SimulatedOccupant],
        graph,
        queues: dict[str, ElementQueueState],
        params: SimulationParameters,
        t: float,
        boundary_solids: list[Aabb] | None = None,
        spaces: dict | None = None,
        doors: dict | None = None,
        obstacle_map=None,
        world_width: float = 0.0,
        world_height: float = 0.0,
    ) -> None:
        radius = params.occupant_radius_m
        solids = boundary_solids or []
        spaces = spaces or {}
        doors = doors or {}
        flood_active = any(e.speed_factor != 1.0 for e in graph.edges.values())

        contenders: dict[str, list[SimulatedOccupant]] = defaultdict(list)
        element_edge: dict = {}
        occ_edge: dict[str, object] = {}

        for occ in occupants:
            if occ.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED):
                continue
            nxt = occ.next_node_id
            if nxt is None:
                self.movement_model.try_advance_route(occ, graph, radius, t)
                continue
            edge = edge_between(graph, occ.current_node_id, nxt)
            if edge is None or edge.speed_factor <= 0:
                occ.status = OccupantStatus.TRAPPED
                continue
            contenders[edge.element_id].append(occ)
            element_edge[edge.element_id] = edge
            occ_edge[occ.id] = edge

        occupants_on: dict[str, int] = defaultdict(int)
        for occ in occupants:
            if occ.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED):
                continue
            node = graph.nodes[occ.current_node_id]
            if node.kind.value == "space":
                occupants_on[node.ref_id] += 1

        admitted: set[str] = set()

        for element_id, group in contenders.items():
            edge = element_edge[element_id]
            on_elem = occupants_on.get(element_id, 0)
            capacity = self.flow_model.calculate_capacity(edge, params.timestep_s, on_elem)

            q = queues.get(element_id)
            if q is None:
                kind = edge.kind.value
                if kind == "space":
                    kind = "corridor"
                q = ElementQueueState(element_id=element_id, element_type=kind)
                queues[element_id] = q

            q.max_throughput_this_step = capacity if capacity != float("inf") else float(len(group))
            q.queue_length = len(group)
            q.peak_queue = max(q.peak_queue, len(group))
            q.throughput_this_step = 0.0

            if edge.kind in (EdgeKind.DOOR, EdgeKind.EXIT, EdgeKind.STAIRS):
                # Gate only when approaching an opening node, not when leaving into a space
                sample_next = graph.nodes[group[0].next_node_id]  # type: ignore[index]
                approaching_opening = sample_next.kind in (NodeKind.DOOR, NodeKind.EXIT)

                if not approaching_opening:
                    for o in group:
                        admitted.add(o.id)
                    continue

                waypoint = sample_next
                for o in group:
                    if o.next_node_id:
                        waypoint = graph.nodes[o.next_node_id]
                        break

                slots = (
                    int(capacity)
                    if capacity != float("inf")
                    else aperture_slots(edge.width_m, radius)
                )
                in_th = [
                    o
                    for o in group
                    if in_throat(o.x, o.y, waypoint.x, waypoint.y, radius)
                ]
                approaching = [o for o in group if o not in in_th]
                approaching.sort(
                    key=lambda o: (dist(o.x, o.y, waypoint.x, waypoint.y), o.id)
                )

                ordered = sorted(in_th, key=lambda o: o.id) + approaching
                for o in ordered[:slots]:
                    admitted.add(o.id)
                for o in ordered[slots:]:
                    q.total_wait_s += params.timestep_s
                    q.waiting_occupant_ids.append(o.id)
            else:
                # Open space / corridor: all may try to move; density is soft
                if capacity == float("inf") or capacity > 0:
                    for o in group:
                        admitted.add(o.id)
                else:
                    for o in group:
                        q.total_wait_s += params.timestep_s

        moved_by: dict[str, float] = {}
        safe_positions: dict[str, tuple[float, float]] = {}

        def move_without_crossing_black_pixels(occupant, target_x: float, target_y: float, distance: float) -> float:
            old_x, old_y = occupant.x, occupant.y
            old_progress = occupant.progress_on_edge
            moved = self.movement_model.step_toward(occupant, target_x, target_y, distance)
            if obstacle_map is None or moved <= 1e-9:
                return moved
            new_x, new_y = occupant.x, occupant.y
            cell = min(world_width / obstacle_map.width, world_height / obstacle_map.height)
            steps = max(1, math.ceil(moved / max(cell * 0.4, 1e-4)))
            last_x, last_y = old_x, old_y
            for i in range(1, steps + 1):
                fraction = i / steps
                sample_x = old_x + (new_x - old_x) * fraction
                sample_y = old_y + (new_y - old_y) * fraction
                if not position_is_walkable(
                    obstacle_map, sample_x, sample_y, radius, world_width, world_height
                ):
                    break
                last_x, last_y = sample_x, sample_y
            actual = dist(old_x, old_y, last_x, last_y)
            occupant.x, occupant.y = last_x, last_y
            occupant.progress_on_edge = old_progress + actual
            return actual

        for occ in occupants:
            if occ.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED):
                continue
            if occ.next_node_id is None:
                continue

            edge = occ_edge.get(occ.id)
            is_admitted = occ.id in admitted
            # Non-aperture edges always admitted above; doors need admission to enter throat
            target_x, target_y = self.movement_model.propose_target(
                occ, graph, radius, admitted=is_admitted
            )

            desired = occ.speed_mps * params.timestep_s
            if flood_active and edge is not None:
                desired *= edge.speed_factor  # type: ignore[union-attr]

            if edge is not None and edge.kind in (EdgeKind.DOOR, EdgeKind.EXIT, EdgeKind.STAIRS):  # type: ignore[union-attr]
                next_node = graph.nodes[occ.next_node_id]
                approaching_opening = next_node.kind in (NodeKind.DOOR, NodeKind.EXIT)
                if approaching_opening and not is_admitted:
                    # Can shuffle toward hold point but cannot enter throat
                    waypoint = next_node
                    old_x, old_y = occ.x, occ.y
                    moved = move_without_crossing_black_pixels(occ, target_x, target_y, desired)
                    occ.x, occ.y = clamp_outside_throat(
                        occ.x, occ.y, waypoint.x, waypoint.y, radius
                    )
                    moved = dist(old_x, old_y, occ.x, occ.y)
                    moved_by[occ.id] = moved
                    continue

            moved = move_without_crossing_black_pixels(occ, target_x, target_y, desired)
            moved_by[occ.id] = moved
            if (
                is_admitted
                and edge is not None
                and edge.kind in (EdgeKind.DOOR, EdgeKind.EXIT, EdgeKind.STAIRS)  # type: ignore[union-attr]
            ):
                next_node = graph.nodes[occ.next_node_id]
                if next_node.kind in (NodeKind.DOOR, NodeKind.EXIT):
                    q = queues.get(edge.element_id)  # type: ignore[union-attr]
                    if q is not None and moved > 1e-6:
                        q.throughput_this_step += 1.0 / max(
                            aperture_slots(edge.width_m, radius), 1  # type: ignore[union-attr]
                        )

        resolve_wall_collisions(occupants, solids, radius)
        resolve_overlaps(occupants, radius)
        if obstacle_map is not None:
            safe_positions = {
                o.id: (o.x, o.y) for o in occupants
                if position_is_walkable(obstacle_map, o.x, o.y, radius, world_width, world_height)
            }

        # Re-clamp non-admitted after overlap resolution so pushes don't sneak them in
        for occ in occupants:
            if occ.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED):
                continue
            if occ.id in admitted:
                continue
            edge = occ_edge.get(occ.id)
            if edge is None or edge.kind not in (EdgeKind.DOOR, EdgeKind.EXIT, EdgeKind.STAIRS):  # type: ignore[union-attr]
                continue
            if occ.next_node_id is None:
                continue
            waypoint = graph.nodes[occ.next_node_id]
            if waypoint.kind not in (NodeKind.DOOR, NodeKind.EXIT):
                continue
            occ.x, occ.y = clamp_outside_throat(occ.x, occ.y, waypoint.x, waypoint.y, radius)

        resolve_wall_collisions(occupants, solids, radius)
        resolve_space_containment(
            occupants, spaces, doors, graph, radius, admitted=admitted
        )
        if obstacle_map is not None:
            for occupant in occupants:
                if occupant.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED):
                    continue
                if not position_is_walkable(
                    obstacle_map, occupant.x, occupant.y, radius, world_width, world_height
                ):
                    occupant.x, occupant.y = safe_positions.get(
                        occupant.id, (occupant.x, occupant.y)
                    )

        for occ in occupants:
            if occ.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED):
                continue
            moved = moved_by.get(occ.id, 0.0)
            edge = occ_edge.get(occ.id)
            approaching_opening = False
            if (
                edge is not None
                and edge.kind in (EdgeKind.DOOR, EdgeKind.EXIT, EdgeKind.STAIRS)  # type: ignore[union-attr]
                and occ.next_node_id is not None
            ):
                approaching_opening = graph.nodes[occ.next_node_id].kind in (
                    NodeKind.DOOR,
                    NodeKind.EXIT,
                )

            blocked = approaching_opening and occ.id not in admitted
            if blocked:
                occ.status = OccupantStatus.WAITING
                occ.wait_time_s += params.timestep_s
            elif moved > 1e-4:
                occ.distance_m += moved
                occ.travel_time_s += params.timestep_s
                if occ.status != OccupantStatus.EVACUATED:
                    occ.status = OccupantStatus.ACTIVE
            else:
                if occ.status != OccupantStatus.EVACUATED:
                    occ.status = OccupantStatus.WAITING
                    occ.wait_time_s += params.timestep_s

            can_advance = not blocked
            if can_advance:
                self.movement_model.try_advance_route(
                    occ, graph, radius, t, admitted=occ.id in admitted or not approaching_opening
                )
            if occ.status == OccupantStatus.EVACUATED and occ.evacuated_at is None:
                occ.evacuated_at = t

            # Count travel distance for blocked agents who still shuffled
            if blocked and moved > 1e-4:
                occ.distance_m += moved
                occ.travel_time_s += params.timestep_s

    @staticmethod
    def _capture_frame(t: float, occupants: list[SimulatedOccupant]) -> SimulationFrame:
        return SimulationFrame(
            t=round(t, 3),
            occupants=[
                OccupantFrameState(
                    id=o.id,
                    x=round(o.x, 3),
                    y=round(o.y, 3),
                    status=o.status,
                    group_id=o.group_id,
                )
                for o in occupants
            ],
        )
