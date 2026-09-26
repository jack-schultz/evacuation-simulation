"""Occupant movement along graph edges."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.building import OccupantStatus
from app.simulation.graph import GraphNode, NavigationGraph
from app.simulation.routing import edge_between


@dataclass
class SimulatedOccupant:
    id: str
    group_id: str
    speed_mps: float
    route: list[str]
    route_index: int = 0
    progress_on_edge: float = 0.0  # metres travelled on current edge
    x: float = 0.0
    y: float = 0.0
    status: OccupantStatus = OccupantStatus.ACTIVE
    distance_m: float = 0.0
    travel_time_s: float = 0.0
    wait_time_s: float = 0.0
    evacuated_at: float | None = None

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
        return self.route_index >= len(self.route) - 1 and self.progress_on_edge <= 1e-9


def interpolate_position(a: GraphNode, b: GraphNode, progress_m: float, edge_length: float) -> tuple[float, float]:
    if edge_length <= 1e-9:
        return b.x, b.y
    t = min(max(progress_m / edge_length, 0.0), 1.0)
    return a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t


@dataclass
class MovementModel:
    """Advances occupants along their assigned routes subject to allowed distances."""

    def desired_move_distance(self, occupant: SimulatedOccupant, timestep_s: float) -> float:
        return occupant.speed_mps * timestep_s

    def apply_move(
        self,
        occupant: SimulatedOccupant,
        graph: NavigationGraph,
        allowed_distance: float,
        timestep_s: float,
        waited: bool,
    ) -> None:
        if occupant.status == OccupantStatus.EVACUATED:
            return

        if waited or allowed_distance <= 0:
            occupant.status = OccupantStatus.WAITING
            occupant.wait_time_s += timestep_s
            return

        remaining = allowed_distance
        moved = 0.0

        while remaining > 1e-9 and occupant.next_node_id is not None:
            edge = edge_between(graph, occupant.current_node_id, occupant.next_node_id)
            if edge is None:
                occupant.status = OccupantStatus.TRAPPED
                return

            edge_len = edge.distance_m
            left_on_edge = edge_len - occupant.progress_on_edge
            step = min(remaining, left_on_edge)
            occupant.progress_on_edge += step
            remaining -= step
            moved += step

            a = graph.nodes[occupant.current_node_id]
            b = graph.nodes[occupant.next_node_id]
            occupant.x, occupant.y = interpolate_position(a, b, occupant.progress_on_edge, edge_len)

            if occupant.progress_on_edge >= edge_len - 1e-9:
                occupant.route_index += 1
                occupant.progress_on_edge = 0.0
                node = graph.nodes[occupant.current_node_id]
                occupant.x, occupant.y = node.x, node.y
                if occupant.next_node_id is None:
                    # Reached exit node
                    occupant.status = OccupantStatus.EVACUATED
                    break

        if moved > 0:
            occupant.distance_m += moved
            occupant.travel_time_s += timestep_s
            if occupant.status != OccupantStatus.EVACUATED:
                occupant.status = OccupantStatus.ACTIVE
        elif occupant.status != OccupantStatus.EVACUATED:
            occupant.status = OccupantStatus.WAITING
            occupant.wait_time_s += timestep_s
