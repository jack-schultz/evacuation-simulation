"""Simulation run parameters."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
    stair_descent_speed_factor: float = Field(
        default=1.1,
        gt=0,
        le=2.0,
        description="Multiplier on flat walking speed when descending stairs.",
    )
    stair_ascent_speed_factor: float = Field(
        default=0.7,
        gt=0,
        le=2.0,
        description="Multiplier on flat walking speed when ascending stairs.",
    )
