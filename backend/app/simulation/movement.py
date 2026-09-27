"""Occupant movement: continuous steer toward route waypoints with aperture targeting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.building import Door, OccupantStatus
from app.simulation.collision import (
    aperture_axis,
    aperture_slot_point,
    aperture_slots,
    dist,
    door_other_space,
)
from app.simulation.graph import EdgeKind, GraphNode, NavigationGraph, NodeKind
from app.simulation.routing import edge_between


@dataclass
class SimulatedOccupant:
    id: str
    group_id: str
    speed_mps: float
    route: list[str]
    current_space_id: str = ""
    route_index: int = 0
    progress_on_edge: float = 0.0  # metres travelled toward current waypoint (approx)
    x: float = 0.0
    y: float = 0.0
    status: OccupantStatus = OccupantStatus.ACTIVE
    distance_m: float = 0.0
    travel_time_s: float = 0.0
    wait_time_s: float = 0.0
    evacuated_at: float | None = None
    aperture_slot: int = 0
    floor_id: str = "floor-0"
    climb_progress: float | None = None
    climb_from_space_id: str | None = None
    climb_to_space_id: str | None = None
    # Full-intensity-equivalent seconds spent in flood water (dose).
    flood_exposure_s: float = 0.0

    @property
    def current_node_id(self) -> str:
        return self.route[self.route_index]

    @property
    def next_node_id(self) -> str | None:
        if self.route_index + 1 < len(self.route):
            return self.route[self.route_index + 1]
        return None

    @property
    def finished_route(self) -> bool:
        return self.route_index >= len(self.route) - 1


def interpolate_position(a: GraphNode, b: GraphNode, progress_m: float, edge_length: float) -> tuple[float, float]:
    if edge_length <= 1e-9:
        return b.x, b.y
    t = min(max(progress_m / edge_length, 0.0), 1.0)
    return a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t


def _next_waypoint_on_space_side(
    graph: NavigationGraph,
    waypoint: GraphNode,
    space_id: str,
    other_space_id: str,
) -> bool:
    """True if waypoint is closer to space_id's node than to other_space_id's."""
    cur_nid = graph.space_node_ids.get(space_id)
    oth_nid = graph.space_node_ids.get(other_space_id)
    if cur_nid is None or oth_nid is None:
        return True
    cur_n = graph.nodes[cur_nid]
    oth_n = graph.nodes[oth_nid]
    d_cur = dist(waypoint.x, waypoint.y, cur_n.x, cur_n.y)
    d_oth = dist(waypoint.x, waypoint.y, oth_n.x, oth_n.y)
    return d_cur <= d_oth + 1e-9


class MovementModel(Protocol):
    """Protocol for spatial (or legacy) movement implementations."""

    def propose_target(
        self,
        occupant: SimulatedOccupant,
        graph: NavigationGraph,
        radius_m: float,
        admitted: bool,
        doors: dict[str, Door] | None = None,
    ) -> tuple[float, float]:
        """Return the (x, y) steering target for this timestep."""
        ...

    def step_toward(
        self,
        occupant: SimulatedOccupant,
        target_x: float,
        target_y: float,
        max_distance: float,
    ) -> float:
        """Move occupant toward target up to max_distance. Returns metres moved."""
        ...

    def try_advance_route(
        self,
        occupant: SimulatedOccupant,
        graph: NavigationGraph,
        radius_m: float,
        t: float,
        *,
        admitted: bool = True,
        doors: dict[str, Door] | None = None,
    ) -> None:
        """Advance route index / evacuate when close enough to the next waypoint."""
        ...


@dataclass
class SpatialMovementModel:
    """Continuous 2D steering toward graph waypoints with door aperture slots."""

    approach_distance_m: float = 2.0

    def _through_door_target(
        self,
        occupant: SimulatedOccupant,
        graph: NavigationGraph,
        door_node: GraphNode,
        waypoint: GraphNode,
        radius_m: float,
        doors: dict[str, Door],
    ) -> tuple[float, float] | None:
        """Aim through the aperture into the destination while still origin-side."""
        door = doors.get(door_node.ref_id)
        if door is None or not occupant.current_space_id:
            return None
        other = door_other_space(door, occupant.current_space_id)
        if other is None:
            return None
        # Already on the destination side of membership — use normal waypoint aiming.
        if _next_waypoint_on_space_side(
            graph, waypoint, occupant.current_space_id, other
        ):
            return None

        origin_nid = graph.space_node_ids.get(occupant.current_space_id)
        dest_nid = graph.space_node_ids.get(other)
        if origin_nid is None or dest_nid is None:
            return None
        origin_n = graph.nodes[origin_nid]
        dest_n = graph.nodes[dest_nid]

        axis_x, axis_y = aperture_axis(origin_n.x, origin_n.y, door_node.x, door_node.y)
        slots = aperture_slots(door.width, radius_m)
        slot = occupant.aperture_slot % slots
        slot_x, slot_y = aperture_slot_point(
            door_node.x, door_node.y, axis_x, axis_y, door.width, slot, slots
        )
        dx = dest_n.x - door_node.x
        dy = dest_n.y - door_node.y
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1e-9:
            return slot_x, slot_y
        offset = max(radius_m * 1.5, 0.4)
        return slot_x + dx / length * offset, slot_y + dy / length * offset

    def propose_target(
        self,
        occupant: SimulatedOccupant,
        graph: NavigationGraph,
        radius_m: float,
        admitted: bool,
        doors: dict[str, Door] | None = None,
    ) -> tuple[float, float]:
        nxt = occupant.next_node_id
        if nxt is None:
            node = graph.nodes[occupant.current_node_id]
            return node.x, node.y

        waypoint = graph.nodes[nxt]
        cur = graph.nodes[occupant.current_node_id]

        if cur.kind == NodeKind.DOOR and doors is not None:
            through = self._through_door_target(
                occupant, graph, cur, waypoint, radius_m, doors
            )
            if through is not None:
                return through
            # Already on the destination side of this door — leave toward the
            # next route waypoint (do not re-apply aperture approach geometry).
            return waypoint.x, waypoint.y

        edge = edge_between(graph, occupant.current_node_id, nxt)
        if edge is None:
            return waypoint.x, waypoint.y

        # Stair teleport portal: stay at / walk to current stair center
        if (
            cur.kind == NodeKind.SPACE
            and waypoint.kind == NodeKind.SPACE
            and cur.id in graph.stair_space_node_ids
            and waypoint.id in graph.stair_space_node_ids
        ):
            return cur.x, cur.y

        if edge.kind not in (EdgeKind.DOOR, EdgeKind.EXIT, EdgeKind.STAIRS):
            return waypoint.x, waypoint.y

        # Next waypoint is an opening — approach / aperture / hold outside throat
        axis_x, axis_y = aperture_axis(cur.x, cur.y, waypoint.x, waypoint.y)
        slots = aperture_slots(edge.width_m, radius_m)
        slot = occupant.aperture_slot % slots
        slot_x, slot_y = aperture_slot_point(
            waypoint.x, waypoint.y, axis_x, axis_y, edge.width_m, slot, slots
        )

        d_to_door = dist(occupant.x, occupant.y, waypoint.x, waypoint.y)
        if d_to_door > self.approach_distance_m:
            # Far: head toward door center so the crowd converges
            return waypoint.x, waypoint.y

        if admitted:
            # Near and admitted: aim at assigned aperture slot, then through
            return slot_x, slot_y

        # Not admitted: hold at the throat boundary in front of the door
        from app.simulation.collision import throat_radius

        tr = throat_radius(radius_m)
        dx = occupant.x - waypoint.x
        dy = occupant.y - waypoint.y
        d = (dx * dx + dy * dy) ** 0.5
        if d < 1e-9:
            # Prefer standing on the approach side of the door
            adx = cur.x - waypoint.x
            ady = cur.y - waypoint.y
            al = (adx * adx + ady * ady) ** 0.5
            if al < 1e-9:
                return waypoint.x + tr, waypoint.y
            return waypoint.x + adx / al * tr, waypoint.y + ady / al * tr
        # Hold just outside throat, biased toward own slot laterally
        hold_x = waypoint.x + dx / d * tr
        hold_y = waypoint.y + dy / d * tr
        # Blend toward slot laterally for packing in front of the door
        hold_x = 0.7 * hold_x + 0.3 * slot_x
        hold_y = 0.7 * hold_y + 0.3 * slot_y
        return hold_x, hold_y

    def step_toward(
        self,
        occupant: SimulatedOccupant,
        target_x: float,
        target_y: float,
        max_distance: float,
    ) -> float:
        if max_distance <= 0:
            return 0.0
        dx = target_x - occupant.x
        dy = target_y - occupant.y
        d = (dx * dx + dy * dy) ** 0.5
        if d < 1e-9:
            return 0.0
        step = min(max_distance, d)
        occupant.x += dx / d * step
        occupant.y += dy / d * step
        occupant.progress_on_edge += step
        return step

    def try_advance_route(
        self,
        occupant: SimulatedOccupant,
        graph: NavigationGraph,
        radius_m: float,
        t: float,
        *,
        admitted: bool = True,
        doors: dict[str, Door] | None = None,
    ) -> None:
        if occupant.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED):
            return

        nxt = occupant.next_node_id
        if nxt is None:
            node = graph.nodes[occupant.current_node_id]
            if node.kind == NodeKind.EXIT:
                occupant.status = OccupantStatus.EVACUATED
                if occupant.evacuated_at is None:
                    occupant.evacuated_at = t
            return

        waypoint = graph.nodes[nxt]
        edge = edge_between(graph, occupant.current_node_id, nxt)

        # Cannot claim an opening waypoint without an aperture slot
        if (
            not admitted
            and edge is not None
            and edge.kind in (EdgeKind.DOOR, EdgeKind.EXIT, EdgeKind.STAIRS)
            and waypoint.kind in (NodeKind.DOOR, NodeKind.EXIT)
        ):
            return

        from_node = graph.nodes[occupant.current_node_id]
        # Leaving a door requires physical membership on the destination side.
        if from_node.kind == NodeKind.DOOR and doors is not None:
            door = doors.get(from_node.ref_id)
            if door is not None and occupant.current_space_id:
                other = door_other_space(door, occupant.current_space_id)
                if other is not None and not _next_waypoint_on_space_side(
                    graph, waypoint, occupant.current_space_id, other
                ):
                    return

        reach = max(radius_m * 1.2, 0.35)
        stair_transfer = (
            from_node.kind == NodeKind.SPACE
            and waypoint.kind == NodeKind.SPACE
            and from_node.id in graph.stair_space_node_ids
            and waypoint.id in graph.stair_space_node_ids
            and edge is not None
        )

        if not admitted and stair_transfer:
            return

        if stair_transfer:
            reached = dist(occupant.x, occupant.y, from_node.x, from_node.y) <= reach
        else:
            d_wp = dist(occupant.x, occupant.y, waypoint.x, waypoint.y)
            reached = d_wp <= reach
            if (
                not reached
                and edge is not None
                and edge.kind in (EdgeKind.DOOR, EdgeKind.EXIT, EdgeKind.STAIRS)
                and waypoint.kind in (NodeKind.DOOR, NodeKind.EXIT)
            ):
                cur = graph.nodes[occupant.current_node_id]
                axis_x, axis_y = aperture_axis(cur.x, cur.y, waypoint.x, waypoint.y)
                slots = aperture_slots(edge.width_m, radius_m)
                slot = occupant.aperture_slot % slots
                sx, sy = aperture_slot_point(
                    waypoint.x, waypoint.y, axis_x, axis_y, edge.width_m, slot, slots
                )
                reached = dist(occupant.x, occupant.y, sx, sy) <= reach

        if not reached:
            return

        if stair_transfer:
            # Begin directed climb along the stair centreline (completed in step.py).
            occupant.status = OccupantStatus.CLIMBING
            occupant.climb_progress = 0.0
            occupant.climb_from_space_id = from_node.ref_id
            occupant.climb_to_space_id = waypoint.ref_id
            return

        occupant.route_index += 1
        occupant.progress_on_edge = 0.0

        if waypoint.kind == NodeKind.EXIT or occupant.next_node_id is None:
            occupant.status = OccupantStatus.EVACUATED
            if occupant.evacuated_at is None:
                occupant.evacuated_at = t
            occupant.x, occupant.y = waypoint.x, waypoint.y
