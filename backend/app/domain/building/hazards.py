"""Hazard and raster obstacle domain types."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

DEFAULT_FLOOR_ID = "floor-0"


class RadialEmergency(BaseModel):
    """Expanding illustrative hazard area; speeds use metres per simulation second."""

    enabled: bool = True
    x: float = Field(ge=0, allow_inf_nan=False)
    y: float = Field(ge=0, allow_inf_nan=False)
    radius_m: float = Field(default=3.0, gt=0, allow_inf_nan=False)
    spread_speed_mps: float = Field(default=0.1, ge=0, allow_inf_nan=False)
    intensity: float = Field(default=50.0, ge=0, le=100, allow_inf_nan=False)
    floor_id: str = Field(
        default=DEFAULT_FLOOR_ID,
        description="Origin floor for this hazard circle.",
    )


class FloodEmergency(RadialEmergency):
    """Illustrative flood scenario.

    Water slows people (soft) and accumulates immersion exposure. After enough
    time in the water (scaled by intensity) occupants become trapped. Contact
    alone is not lethal. Spread is room-scoped through same-floor doors.
    """

    id: str = Field(default="flood", description="Stable id for editor selection.")


class FireEmergency(RadialEmergency):
    """Illustrative fire scenario.

    Contact with the fire circle is lethal (occupant becomes trapped), including
    on stairs. Smoke is part of the fire disaster: when emit_smoke is true the
    engine synthesizes a soft plume that expands faster than the fire and only
    slows people. Both spread through linked stairs in either direction.
    """

    id: str = Field(default="fire", description="Stable id for editor selection.")
    emit_smoke: bool = Field(
        default=True,
        description="When true, smoke is produced from the fire (soft slowdown + stair spread).",
    )
    smoke_visibility_m: float = Field(
        default=8.0,
        gt=0,
        allow_inf_nan=False,
        description="Sight range (m) in smoke at intensity 100.",
    )
    smoke_stair_spread_delay_s: float = Field(
        default=8.0,
        ge=0,
        allow_inf_nan=False,
        description="Seconds for smoke to transfer one storey through a linked stair.",
    )
    smoke_stair_intensity_factor: float = Field(
        default=0.85,
        gt=0,
        le=1.0,
        allow_inf_nan=False,
        description="Intensity multiplier for smoke/fire plumes after a stair transfer.",
    )


class SmokeEmergency(RadialEmergency):
    """Internal soft smoke plume used by the engine (always derived from fire)."""

    visibility_m: float = Field(
        default=8.0,
        gt=0,
        allow_inf_nan=False,
        description="Sight range (m) at intensity 100; longer when intensity is lower.",
    )
    stair_spread_delay_s: float = Field(
        default=8.0,
        ge=0,
        allow_inf_nan=False,
        description="Seconds for smoke to transfer one storey through a linked stair.",
    )
    stair_spread_intensity_factor: float = Field(
        default=0.85,
        gt=0,
        le=1.0,
        allow_inf_nan=False,
        description="Intensity multiplier for plumes after a stair transfer.",
    )


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
