"""Simulation output / playback domain types."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class OccupantStatus(str, Enum):
    ACTIVE = "active"
    WAITING = "waiting"
    EVACUATED = "evacuated"
    TRAPPED = "trapped"
    CLIMBING = "climbing"


class OccupantFrameState(BaseModel):
    id: str
    x: float
    y: float
    status: OccupantStatus
    deceased: bool = False
    group_id: str
    floor_id: str = "floor-0"
    route_index: int = Field(
        default=0,
        description="Index into the occupant's fixed route of the current waypoint.",
    )
    climb_progress: float | None = Field(
        default=None,
        description="0..1 along a stair transfer when status is climbing.",
    )


class SmokeFloorState(BaseModel):
    """Floor-scoped fire plume (and legacy smoke frames)."""

    floor_id: str
    radius_m: float
    x: float
    y: float
    intensity: float = 50.0


class FloodRoomState(BaseModel):
    """Flood plume scoped to one space (origin or doorway restart)."""

    space_id: str
    radius_m: float
    x: float
    y: float
    intensity: float = 50.0


class SmokeRoomState(BaseModel):
    """Smoke plume scoped to one space (origin, doorway, or fire-seeded)."""

    space_id: str
    radius_m: float
    x: float
    y: float
    intensity: float = 50.0


class SimulationFrame(BaseModel):
    flood_radius_m: float | None = None
    flood_rooms: list[FloodRoomState] = Field(default_factory=list)
    fire_radius_m: float | None = None
    fire_floors: list[SmokeFloorState] = Field(default_factory=list)
    smoke_floors: list[SmokeFloorState] = Field(
        default_factory=list,
        description="Legacy floor-scoped smoke; prefer smoke_rooms.",
    )
    smoke_rooms: list[SmokeRoomState] = Field(default_factory=list)
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
    deceased: bool = False
    distance_m: float
    travel_time_s: float
    wait_time_s: float
    total_time_s: float
    route_node_ids: list[str]
    route_points: list[tuple[float, float]] = []
    route_floors: list[str] = Field(
        default_factory=list,
        description="Floor id for each route_points entry (same length).",
    )
    route_point_indexes: list[int] = Field(
        default_factory=list,
        description="Index into route_node_ids for each route_points entry.",
    )


class SimulationResults(BaseModel):
    total_occupants: int
    evacuated_count: int
    remaining_count: int
    death_count: int = 0
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
