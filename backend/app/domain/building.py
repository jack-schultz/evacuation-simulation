"""Pure domain types for building geometry and occupants.

Coordinates use a top-left origin in metres (or grid cells scaled by meters_per_cell).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class SpaceType(str, Enum):
    ROOM = "room"
    CORRIDOR = "corridor"
    STAIRS = "stairs"


class Space(BaseModel):
    id: str
    name: str
    type: SpaceType
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    capacity_density_per_m2: float | None = Field(
        default=None,
        description="Max occupants per m²; None uses simulation defaults for corridors/stairs.",
    )


class Wall(BaseModel):
    id: str
    name: str = "Wall"
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class Door(BaseModel):
    id: str
    name: str = "Door"
    x: float
    y: float
    width: float = Field(gt=0, description="Clear opening width in metres")
    connects: tuple[str, str] = Field(description="IDs of two connected spaces")
    flow_rate_per_s: float | None = Field(
        default=None,
        gt=0,
        description="Max occupants per second through this door; None uses default",
    )

    @field_validator("connects")
    @classmethod
    def distinct_spaces(cls, v: tuple[str, str]) -> tuple[str, str]:
        if v[0] == v[1]:
            raise ValueError("Door must connect two different spaces")
        return v


class Exit(BaseModel):
    id: str
    name: str = "Exit"
    x: float
    y: float
    width: float = Field(gt=0)
    connected_space_id: str
    flow_rate_per_s: float | None = Field(default=None, gt=0)


class OccupantGroup(BaseModel):
    id: str
    name: str
    count: int = Field(gt=0, le=5000)
    space_id: str
    spawn_x: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    spawn_y: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    walking_speed_mps: float = Field(default=1.2, gt=0, le=5.0)
    destination_exit_id: str | None = None
    # Reserved for future behavioural parameters
    behaviour: dict[str, float | str | bool] = Field(default_factory=dict)


class FloodEmergency(BaseModel):
    """Static, illustrative flood area; intensity is a relative scenario control."""

    enabled: bool = True
    x: float = Field(ge=0, allow_inf_nan=False)
    y: float = Field(ge=0, allow_inf_nan=False)
    radius_m: float = Field(default=3.0, gt=0, allow_inf_nan=False)
    intensity: float = Field(default=50.0, ge=0, le=100, allow_inf_nan=False)


class PixelObstacleMap(BaseModel):
    """Downsampled binary plan: 1 is solid black, 0 is walkable white."""

    width: int = Field(gt=0, le=512)
    height: int = Field(gt=0, le=512)
    rows: list[str]

    @model_validator(mode="after")
    def validate_raster(self) -> PixelObstacleMap:
        if len(self.rows) != self.height or any(
            len(row) != self.width or set(row) - {"0", "1"} for row in self.rows
        ):
            raise ValueError("Obstacle map rows must match dimensions and contain only 0 or 1")
        return self


class BuildingLayout(BaseModel):
    """Serializable building configuration (API + persistence payload)."""

    name: str = "Untitled Building"
    width: float = Field(default=40.0, gt=0)
    height: float = Field(default=40.0, gt=0)
    meters_per_cell: float = Field(default=1.0, gt=0)
    spaces: list[Space] = Field(default_factory=list)
    walls: list[Wall] = Field(default_factory=list)
    doors: list[Door] = Field(default_factory=list)
    exits: list[Exit] = Field(default_factory=list)
    occupant_groups: list[OccupantGroup] = Field(default_factory=list)
    flood: FloodEmergency | None = None
    obstacle_map: PixelObstacleMap | None = None

    @model_validator(mode="after")
    def validate_references(self) -> BuildingLayout:
        if self.flood and (self.flood.x > self.width or self.flood.y > self.height):
            raise ValueError("Flood centre must be inside the building bounds")
        space_ids = {s.id for s in self.spaces}
        exit_ids = {e.id for e in self.exits}

        for door in self.doors:
            for sid in door.connects:
                if sid not in space_ids:
                    raise ValueError(f"Door '{door.id}' references unknown space '{sid}'")

        for exit_ in self.exits:
            if exit_.connected_space_id not in space_ids:
                raise ValueError(
                    f"Exit '{exit_.id}' references unknown space '{exit_.connected_space_id}'"
                )

        for group in self.occupant_groups:
            if group.space_id not in space_ids:
                raise ValueError(
                    f"Occupant group '{group.id}' references unknown space '{group.space_id}'"
                )
            if group.destination_exit_id is not None and group.destination_exit_id not in exit_ids:
                raise ValueError(
                    f"Occupant group '{group.id}' references unknown exit '{group.destination_exit_id}'"
                )
            if (group.spawn_x is None) != (group.spawn_y is None):
                raise ValueError(f"Occupant group '{group.id}' must define both spawn coordinates")
            if group.spawn_x is not None and group.spawn_y is not None and (
                group.spawn_x > self.width or group.spawn_y > self.height
            ):
                raise ValueError(f"Occupant group '{group.id}' spawn point must be inside the building")

        return self


class SimulationParameters(BaseModel):
    timestep_s: float = Field(default=0.25, gt=0, le=2.0)
    max_time_s: float = Field(default=600.0, gt=0)
    door_flow_per_s: float = Field(
        default=1.2,
        gt=0,
        description="Legacy; door throughput is aperture-based (width / body diameter).",
    )
    stairs_flow_per_s: float = Field(
        default=0.8,
        gt=0,
        description="Legacy; stairs throughput is aperture-based when width is set.",
    )
    exit_flow_per_s: float = Field(
        default=1.5,
        gt=0,
        description="Legacy; exit throughput is aperture-based (width / body diameter).",
    )
    corridor_density_per_m2: float = Field(default=2.0, gt=0)
    occupant_radius_m: float = Field(
        default=0.25,
        gt=0,
        le=1.0,
        description="Body radius for collision and door aperture capacity",
    )
    frame_interval_s: float = Field(
        default=0.5,
        gt=0,
        description="Seconds between stored animation frames (reduces payload size)",
    )


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
