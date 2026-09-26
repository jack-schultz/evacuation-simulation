"""Flow / congestion models for constrained building elements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

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
        """Return max occupants that may traverse the element in this timestep."""
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
    """Simple capacity / flow-rate congestion model.

    - Doors, stairs, exits: limited by flow_rate_per_s * timestep
    - Corridors: limited by remaining density capacity relative to area
    - Rooms (SPACE): treated as unconstrained for flow (capacity check soft)
    """

    def calculate_capacity(self, edge: GraphEdge, timestep_s: float, occupants_on_element: int) -> float:
        if edge.kind in (EdgeKind.DOOR, EdgeKind.EXIT, EdgeKind.STAIRS):
            rate = edge.flow_rate_per_s or 0.0
            if edge.kind == EdgeKind.STAIRS and edge.flow_rate_per_s is None:
                rate = 0.8
            return max(rate * timestep_s, 0.0)

        if edge.kind == EdgeKind.CORRIDOR:
            density = edge.capacity_density_per_m2 or 2.0
            area = edge.area_m2 or 1.0
            max_occ = density * area
            remaining = max(max_occ - occupants_on_element, 0.0)
            # Allow a fraction of remaining capacity per step to model gradual flow
            return max(remaining, 0.0)

        # Unconstrained room interiors
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
        # Each excess occupant waits approximately one timestep this step
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
