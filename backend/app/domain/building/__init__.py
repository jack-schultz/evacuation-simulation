"""Pure domain types for building geometry and occupants.

Coordinates use a top-left origin in metres (or grid cells scaled by meters_per_cell).

Compatibility barrel — prefer importing from app.domain.building.
"""

from __future__ import annotations

from app.domain.building.hazards import (
    DEFAULT_FLOOR_ID,
    FireEmergency,
    FloodEmergency,
    PixelObstacleMap,
    RadialEmergency,
    SmokeEmergency,
)
from app.domain.building.layout import (
    BuildingLayout,
    Door,
    Exit,
    Floor,
    OccupantGroup,
    Obstacle,
    Space,
    SpaceType,
)
from app.domain.building.parameters import SimulationParameters
from app.domain.building.results import (
    CongestionHotspot,
    OccupantFrameState,
    OccupantResult,
    OccupantStatus,
    SimulationFrame,
    SimulationResults,
    SmokeFloorState,
)

__all__ = [
    "BuildingLayout",
    "CongestionHotspot",
    "DEFAULT_FLOOR_ID",
    "Door",
    "Exit",
    "FireEmergency",
    "FloodEmergency",
    "Floor",
    "OccupantFrameState",
    "OccupantGroup",
    "Obstacle",
    "OccupantResult",
    "OccupantStatus",
    "PixelObstacleMap",
    "RadialEmergency",
    "SimulationFrame",
    "SimulationParameters",
    "SimulationResults",
    "SmokeEmergency",
    "SmokeFloorState",
    "Space",
    "SpaceType",
]
