"""Pure domain types for building geometry and occupants.

Coordinates use a top-left origin in metres (or grid cells scaled by meters_per_cell).

Compatibility barrel — prefer importing from app.domain.building.
"""

from __future__ import annotations

from app.domain.building.hazards import (
    FireEmergency,
    FloodEmergency,
    PixelObstacleMap,
    RadialEmergency,
)
from app.domain.building.layout import (
    BuildingLayout,
    Door,
    Exit,
    OccupantGroup,
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
)

__all__ = [
    "BuildingLayout",
    "CongestionHotspot",
    "Door",
    "Exit",
    "FireEmergency",
    "FloodEmergency",
    "OccupantFrameState",
    "OccupantGroup",
    "OccupantResult",
    "OccupantStatus",
    "PixelObstacleMap",
    "RadialEmergency",
    "SimulationFrame",
    "SimulationParameters",
    "SimulationResults",
    "Space",
    "SpaceType",
]
