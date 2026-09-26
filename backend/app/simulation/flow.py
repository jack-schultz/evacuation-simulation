"""Flow / congestion models for constrained building elements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.simulation.collision import aperture_slots
from app.simulation.graph import EdgeKind, GraphEdge


@dataclass
class ElementQueueState:
    element_id: str
    element_type: str
    queue_length: int = 0
    throughput_this_step: float = 0.0
    max_throughput_this_step: float = 0.0
    total_wait_s: float = 0.0
    peak_queue: int = 0
    waiting_occupant_ids: list[str] = field(default_factory=list)


class FlowModel(Protocol):
    def calculate_capacity(self, edge: GraphEdge, timestep_s: float, occupants_on_element: int) -> float:
        """Return max concurrent occupants for the element (aperture or density)."""
        ...

    def calculate_delay(
        self,
        edge: GraphEdge,
        demand: int,
        capacity: float,
        timestep_s: float,
    ) -> float:
        """Return additional wait time (seconds) implied by excess demand."""
        ...


class CapacityFlowModel:
    """Aperture / density congestion model for bookkeeping and gating.

    - Doors, stairs, exits: concurrent bodies ≈ width / (2 * radius)
    - Corridors: remaining density capacity relative to area
    - Rooms (SPACE): unconstrained
    """

    def __init__(self, occupant_radius_m: float = 0.25) -> None:
        self.occupant_radius_m = occupant_radius_m

    def calculate_capacity(self, edge: GraphEdge, timestep_s: float, occupants_on_element: int) -> float:
        if edge.kind in (EdgeKind.DOOR, EdgeKind.EXIT, EdgeKind.STAIRS):
            return float(aperture_slots(edge.width_m, self.occupant_radius_m))

        if edge.kind == EdgeKind.CORRIDOR:
            density = edge.capacity_density_per_m2 or 2.0
            area = edge.area_m2 or 1.0
            max_occ = density * area
            remaining = max(max_occ - occupants_on_element, 0.0)
            return max(remaining, 0.0)

        return float("inf")

    def calculate_delay(
        self,
        edge: GraphEdge,
        demand: int,
        capacity: float,
        timestep_s: float,
    ) -> float:
        if capacity <= 0:
            return timestep_s * demand
        if demand <= capacity:
            return 0.0
        excess = demand - capacity
        return excess * timestep_s


class UnlimitedFlowModel:
    """Baseline model with no congestion (useful for comparison tests)."""

    def calculate_capacity(self, edge: GraphEdge, timestep_s: float, occupants_on_element: int) -> float:
        return float("inf")

    def calculate_delay(
        self,
        edge: GraphEdge,
        demand: int,
        capacity: float,
        timestep_s: float,
    ) -> float:
        return 0.0
