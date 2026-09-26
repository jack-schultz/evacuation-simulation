"""Layout geometry entities: spaces, doors, exits, occupant groups."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.geometry import area as polygon_area
from app.domain.geometry import bbox as polygon_bbox
from app.domain.geometry import centroid as polygon_centroid
from app.domain.geometry import rect_vertices
from app.domain.building.hazards import FireEmergency, FloodEmergency, PixelObstacleMap

class SpaceType(str, Enum):
    ROOM = "room"
    CORRIDOR = "corridor"
    STAIRS = "stairs"


class Space(BaseModel):
    id: str
    name: str
    type: SpaceType
    vertices: list[tuple[float, float]] = Field(
        min_length=3,
        description="Closed polygon ring in metres (closing duplicate omitted).",
    )
    capacity_density_per_m2: float | None = Field(
        default=None,
        description="Max occupants per m²; None uses simulation defaults for corridors/stairs.",
    )
    linked_stair_id: str | None = Field(
        default=None,
        description="Paired stairs space id for teleport pathing; only used when type is stairs.",
    )

    @model_validator(mode="before")
    @classmethod
    def legacy_aabb_to_vertices(cls, data: object) -> object:
        """Accept legacy x/y/width/height spaces and expand to four corners."""
        if not isinstance(data, dict):
            return data
        if data.get("vertices"):
            return data
        if all(k in data for k in ("x", "y", "width", "height")):
            converted = dict(data)
            converted["vertices"] = rect_vertices(
                float(data["x"]),
                float(data["y"]),
                float(data["width"]),
                float(data["height"]),
            )
            for key in ("x", "y", "width", "height"):
                converted.pop(key, None)
            return converted
        return data

    @field_validator("vertices")
    @classmethod
    def validate_vertices(
        cls, v: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        pts = [(float(x), float(y)) for x, y in v]
        if len(pts) >= 2 and pts[0] == pts[-1]:
            pts = pts[:-1]
        if len(pts) < 3:
            raise ValueError("Space must have at least 3 vertices")
        cleaned: list[tuple[float, float]] = []
        for p in pts:
            if cleaned and cleaned[-1] == p:
                continue
            cleaned.append(p)
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1]:
            cleaned = cleaned[:-1]
        if len(cleaned) < 3:
            raise ValueError("Space must have at least 3 distinct vertices")
        if polygon_area(cleaned) < 1e-6:
            raise ValueError("Space polygon must have positive area")
        return cleaned

    @property
    def centroid(self) -> tuple[float, float]:
        return polygon_centroid(self.vertices)

    @property
    def area_m2(self) -> float:
        return polygon_area(self.vertices)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """(min_x, min_y, width, height)."""
        return polygon_bbox(self.vertices)


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

class BuildingLayout(BaseModel):
    """Serializable building configuration (API + persistence payload)."""

    name: str = "Untitled Building"
    width: float = Field(default=40.0, gt=0)
    height: float = Field(default=40.0, gt=0)
    meters_per_cell: float = Field(default=1.0, gt=0)
    spaces: list[Space] = Field(default_factory=list)
    doors: list[Door] = Field(default_factory=list)
    exits: list[Exit] = Field(default_factory=list)
    occupant_groups: list[OccupantGroup] = Field(default_factory=list)
    flood: FloodEmergency | None = None
    fire: FireEmergency | None = None
    obstacle_map: PixelObstacleMap | None = None

    @model_validator(mode="after")
    def validate_references(self) -> BuildingLayout:
        if self.flood and (self.flood.x > self.width or self.flood.y > self.height):
            raise ValueError("Flood centre must be inside the building bounds")
        if self.fire and (self.fire.x > self.width or self.fire.y > self.height):
            raise ValueError("Fire centre must be inside the building bounds")
        space_ids = {s.id for s in self.spaces}
        spaces_by_id = {s.id: s for s in self.spaces}
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

        for space in self.spaces:
            if space.linked_stair_id is None:
                continue
            if space.type != SpaceType.STAIRS:
                raise ValueError(
                    f"Space '{space.id}' has linked_stair_id but is not stairs"
                )
            if space.linked_stair_id == space.id:
                raise ValueError(f"Stairs '{space.id}' cannot link to itself")
            other = spaces_by_id.get(space.linked_stair_id)
            if other is None:
                raise ValueError(
                    f"Stairs '{space.id}' links to unknown space '{space.linked_stair_id}'"
                )
            if other.type != SpaceType.STAIRS:
                raise ValueError(
                    f"Stairs '{space.id}' links to non-stairs space '{space.linked_stair_id}'"
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
