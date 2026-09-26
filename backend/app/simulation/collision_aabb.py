"""Axis-aligned bounding box helpers used by collision resolution."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.building import Space
from app.simulation.apertures import dist

@dataclass(frozen=True)
class Aabb:
    """Axis-aligned rectangle: top-left origin, positive width/height."""

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def contains_point(self, px: float, py: float) -> bool:
        return self.x <= px <= self.right and self.y <= py <= self.bottom

    def intersects(self, other: Aabb) -> bool:
        return not (
            self.right < other.x
            or other.right < self.x
            or self.bottom < other.y
            or other.bottom < self.y
        )

def push_out_of_aabb(x: float, y: float, box: Aabb) -> tuple[float, float]:
    """If (x, y) is inside box, push to the nearest outside face."""
    if not box.contains_point(x, y):
        return x, y
    dl = x - box.x
    dr = box.right - x
    dt = y - box.y
    db = box.bottom - y
    m = min(dl, dr, dt, db)
    if m == dl:
        return box.x, y
    if m == dr:
        return box.right, y
    if m == dt:
        return x, box.y
    return x, box.bottom


def inset_aabb(space: Space, radius_m: float) -> Aabb:
    """Walkable AABB inset of the space bounding box (exact for axis-aligned rects)."""
    from app.domain.geometry import bbox

    r = max(radius_m, 0.0)
    min_x, min_y, width, height = bbox(space.vertices)
    if width <= 2.0 * r or height <= 2.0 * r:
        cx, cy = space.centroid
        return Aabb(cx, cy, 0.0, 0.0)
    return Aabb(
        min_x + r,
        min_y + r,
        width - 2.0 * r,
        height - 2.0 * r,
    )


def clamp_point_to_aabb(x: float, y: float, box: Aabb) -> tuple[float, float]:
    """Project (x, y) onto the closed AABB."""
    return (
        min(max(x, box.x), box.right),
        min(max(y, box.y), box.bottom),
    )


def _clamp_to_nearest_aabb(
    x: float, y: float, boxes: list[Aabb]
) -> tuple[float, float]:
    """Keep point if inside any box; otherwise snap to the closest box."""
    if any(b.contains_point(x, y) for b in boxes):
        return x, y
    best_x, best_y = x, y
    best_d = float("inf")
    for box in boxes:
        cx, cy = clamp_point_to_aabb(x, y, box)
        d = dist(x, y, cx, cy)
        if d < best_d:
            best_d = d
            best_x, best_y = cx, cy
    return best_x, best_y
