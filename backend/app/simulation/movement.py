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


class MovementModel(Protocol):
    """Protocol for spatial (or legacy) movement implementations."""

    def propose_target(
        self,
        occupant: SimulatedOccupant,
        graph: NavigationGraph,
        radius_m: float,
        admitted: bool,
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

    def propose_target(
        self,
        occupant: SimulatedOccupant,
        graph: NavigationGraph,
        radius_m: float,
        admitted: bool,
    ) -> tuple[float, float]:
        nxt = occupant.next_node_id
        if nxt is None:
            node = graph.nodes[occupant.current_node_id]
            return node.x, node.y

        waypoint = graph.nodes[nxt]
        edge = edge_between(graph, occupant.current_node_id, nxt)
        if edge is None:
            return waypoint.x, waypoint.y

        if edge.kind not in (EdgeKind.DOOR, EdgeKind.EXIT, EdgeKind.STAIRS):
            return waypoint.x, waypoint.y

        # Next waypoint is an opening — approach / aperture / hold outside throat
        cur = graph.nodes[occupant.current_node_id]
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

        reach = max(radius_m * 1.2, 0.35)
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

        from_node = graph.nodes[occupant.current_node_id]
        occupant.route_index += 1
        occupant.progress_on_edge = 0.0
        # Membership flips when leaving a door into the next space, not on arrival
        if from_node.kind == NodeKind.DOOR and doors is not None:
            door = doors.get(from_node.ref_id)
            if door is not None:
                a, b = door.connects
                if occupant.current_space_id == a:
                    occupant.current_space_id = b
                elif occupant.current_space_id == b:
                    occupant.current_space_id = a
                else:
                    occupant.current_space_id = a

        if waypoint.kind == NodeKind.EXIT or occupant.next_node_id is None:
            occupant.status = OccupantStatus.EVACUATED
            if occupant.evacuated_at is None:
                occupant.evacuated_at = t
            occupant.x, occupant.y = waypoint.x, waypoint.y
