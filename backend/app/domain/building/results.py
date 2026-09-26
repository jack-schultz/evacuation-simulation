"""Simulation output / playback domain types."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel

class OccupantStatus(str, Enum):
    ACTIVE = "active"
    WAITING = "waiting"
    EVACUATED = "evacuated"
    TRAPPED = "trapped"


class OccupantFrameState(BaseModel):
    id: str
    x: float
    y: float
    status: OccupantStatus
    group_id: str


class SimulationFrame(BaseModel):
    flood_radius_m: float | None = None
    fire_radius_m: float | None = None
    t: float
    occupants: list[OccupantFrameState]


class CongestionHotspot(BaseModel):
    element_id: str
    element_type: Literal["door", "corridor", "stairs", "exit"]
    total_wait_s: float
    peak_queue: int


class OccupantResult(BaseModel):
    id: str
    group_id: str
    evacuated: bool
    distance_m: float
    travel_time_s: float
    wait_time_s: float
    total_time_s: float
    route_node_ids: list[str]
    route_points: list[tuple[float, float]] = []


class SimulationResults(BaseModel):
    total_occupants: int
    evacuated_count: int
    remaining_count: int
    total_evacuation_time_s: float | None
    average_evacuation_time_s: float | None
    max_evacuation_time_s: float | None
    average_distance_m: float | None
    average_wait_time_s: float | None
    congestion_hotspots: list[CongestionHotspot]
    occupants: list[OccupantResult]
    assumptions_note: str = (
        "Estimation only — not a safety certification or regulatory compliance calculation."
    )
