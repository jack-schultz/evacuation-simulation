"""Hazard and raster obstacle domain types."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

class RadialEmergency(BaseModel):
    """Expanding illustrative hazard area; speeds use metres per simulation second."""

    enabled: bool = True
    x: float = Field(ge=0, allow_inf_nan=False)
    y: float = Field(ge=0, allow_inf_nan=False)
    radius_m: float = Field(default=3.0, gt=0, allow_inf_nan=False)
    spread_speed_mps: float = Field(default=0.1, ge=0, allow_inf_nan=False)
    intensity: float = Field(default=50.0, ge=0, le=100, allow_inf_nan=False)


class FloodEmergency(RadialEmergency):
    """Illustrative flood scenario."""


class FireEmergency(RadialEmergency):
    """Illustrative fire scenario; intensity is a relative slowdown, not heat."""


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
