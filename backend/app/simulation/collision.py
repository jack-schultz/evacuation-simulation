"""Spatial collision helpers: body radius, door apertures, space edges, overlap resolution.

Compatibility barrel — implementation lives in apertures, walls, containment, and collision_aabb.
"""

from __future__ import annotations

from app.simulation.apertures import (
    PositionedOccupant,
    aperture_axis,
    aperture_slot_point,
    aperture_slots,
    clamp_outside_throat,
    dist,
    in_throat,
    resolve_overlaps,
    throat_radius,
)
from app.simulation.collision_aabb import (
    Aabb,
    clamp_point_to_aabb,
    inset_aabb,
    push_out_of_aabb,
)
from app.simulation.containment import (
    ContainedOccupant,
    resolve_space_containment,
    resolve_wall_collisions,
)
from app.simulation.walls import (
    WallSegment,
    build_collision_solids,
    space_boundary_rects,
    space_boundary_segments,
)

__all__ = [
    "Aabb",
    "ContainedOccupant",
    "PositionedOccupant",
    "WallSegment",
    "aperture_axis",
    "aperture_slot_point",
    "aperture_slots",
    "build_collision_solids",
    "clamp_outside_throat",
    "clamp_point_to_aabb",
    "dist",
    "in_throat",
    "inset_aabb",
    "push_out_of_aabb",
    "resolve_overlaps",
    "resolve_space_containment",
    "resolve_wall_collisions",
    "space_boundary_rects",
    "space_boundary_segments",
    "throat_radius",
]
