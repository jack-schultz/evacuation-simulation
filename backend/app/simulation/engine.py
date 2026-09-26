"""Discrete-time evacuation simulation engine."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.domain.building import (
    BuildingLayout,
    OccupantFrameState,
    OccupantStatus,
    SimulationFrame,
    SimulationParameters,
    SimulationResults,
)
from app.simulation.collision import (
    aperture_slots,
    clamp_outside_throat,
    dist,
    in_throat,
    resolve_overlaps,
)
from app.simulation.flood import FloodRouteSelector, apply_flood
from app.simulation.flow import CapacityFlowModel, ElementQueueState, FlowModel
from app.simulation.graph import EdgeKind, NavigationGraphBuilder, NodeKind
from app.simulation.movement import SimulatedOccupant, SpatialMovementModel
from app.simulation.results import build_results
from app.simulation.routing import DijkstraRouteSelector, RouteSelector, edge_between


@dataclass
class SimulationOutput:
    results: SimulationResults
    frames: list[SimulationFrame]


class SimulationEngine:
    """Runs a discrete-time evacuation over a building navigation graph.

    Occupants steer continuously toward fixed Dijkstra waypoints, collide via
    body radius, and pass doors/exits through width-limited apertures.
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

        occupants = self._spawn_occupants(layout, graph, params.occupant_radius_m)
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
            self._step(occupants, graph, queues, params, t)

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
    ) -> list[SimulatedOccupant]:
        occupants: list[SimulatedOccupant] = []
        spaces = {s.id: s for s in layout.spaces}
        spacing = max(2.0 * radius_m + 0.05, 0.45)
        margin = radius_m + 0.1

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
            usable_w = max(space.width - 2 * margin, spacing)
            cols = max(1, int(usable_w / spacing) + 1)
            node = graph.nodes[start_node]
            for i in range(group.count):
                if group.count == 1:
                    ox, oy = node.x, node.y
                else:
                    ox = space.x + margin + (i % cols) * spacing
                    oy = space.y + margin + (i // cols) * spacing
                    ox = min(ox, space.x + space.width - margin)
                    oy = min(oy, space.y + space.height - margin)
                occupants.append(
                    SimulatedOccupant(
                        id=f"{group.id}:{i}",
                        group_id=group.id,
                        speed_mps=group.walking_speed_mps,
                        route=list(route),
                        status=OccupantStatus.TRAPPED if len(route) == 1 else OccupantStatus.ACTIVE,
                        x=ox,
                        y=oy,
                        aperture_slot=i,
                    )
                )
        resolve_overlaps(occupants, radius_m, iterations=6)
        return occupants

    def _step(
        self,
        occupants: list[SimulatedOccupant],
        graph,
        queues: dict[str, ElementQueueState],
        params: SimulationParameters,
        t: float,
    ) -> None:
        radius = params.occupant_radius_m
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
                    moved = self.movement_model.step_toward(occ, target_x, target_y, desired)
                    occ.x, occ.y = clamp_outside_throat(
                        occ.x, occ.y, waypoint.x, waypoint.y, radius
                    )
                    moved = dist(old_x, old_y, occ.x, occ.y)
                    moved_by[occ.id] = moved
                    continue

            moved = self.movement_model.step_toward(occ, target_x, target_y, desired)
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

        resolve_overlaps(occupants, radius)

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
