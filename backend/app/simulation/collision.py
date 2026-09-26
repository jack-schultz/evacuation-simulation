"""Spatial collision helpers: body radius, door apertures, walls, overlap resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.building import Door, Exit, OccupantStatus, Space, Wall


class PositionedOccupant(Protocol):
    id: str
    x: float
    y: float
    status: OccupantStatus


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


def aperture_slots(width_m: float, radius_m: float) -> int:
    """How many bodies fit abreast through an opening of the given clear width."""
    if radius_m <= 0:
        return 1
    return max(1, int(width_m / (2.0 * radius_m)))


def throat_radius(radius_m: float) -> float:
    """Distance from a door/exit node that counts as being in the opening throat."""
    return max(radius_m * 2.5, 0.6)


def dist(ax: float, ay: float, bx: float, by: float) -> float:
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def in_throat(x: float, y: float, node_x: float, node_y: float, radius_m: float) -> bool:
    return dist(x, y, node_x, node_y) <= throat_radius(radius_m)


def aperture_axis(from_x: float, from_y: float, to_x: float, to_y: float) -> tuple[float, float]:
    """Unit vector perpendicular to the approach direction (door opening axis)."""
    dx = to_x - from_x
    dy = to_y - from_y
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-9:
        return 1.0, 0.0
    return -dy / length, dx / length


def aperture_slot_point(
    door_x: float,
    door_y: float,
    axis_x: float,
    axis_y: float,
    width_m: float,
    slot_index: int,
    slot_count: int,
) -> tuple[float, float]:
    """World position of slot_index along the aperture segment centered on the door."""
    if slot_count <= 1:
        return door_x, door_y
    t = (slot_index + 0.5) / slot_count - 0.5
    offset = t * width_m
    return door_x + axis_x * offset, door_y + axis_y * offset


def clamp_outside_throat(
    x: float,
    y: float,
    node_x: float,
    node_y: float,
    radius_m: float,
) -> tuple[float, float]:
    """Push a point onto the throat circle if it lies inside."""
    tr = throat_radius(radius_m)
    dx = x - node_x
    dy = y - node_y
    d = (dx * dx + dy * dy) ** 0.5
    if d >= tr:
        return x, y
    if d < 1e-9:
        return node_x + tr, node_y
    scale = tr / d
    return node_x + dx * scale, node_y + dy * scale


def resolve_overlaps(
    occupants: list[PositionedOccupant],
    radius_m: float,
    iterations: int = 4,
) -> None:
    """Separating-axis push for pairs closer than 2 * radius (in-place)."""
    min_dist = 2.0 * radius_m
    if min_dist <= 0:
        return

    active = [
        o
        for o in occupants
        if o.status not in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED)
    ]

    for _ in range(iterations):
        for i in range(len(active)):
            a = active[i]
            for j in range(i + 1, len(active)):
                b = active[j]
                dx = b.x - a.x
                dy = b.y - a.y
                d = (dx * dx + dy * dy) ** 0.5
                if d < 1e-9:
                    # Coincident: unit push along a stable axis from ids
                    nx, ny = (1.0, 0.0) if a.id <= b.id else (-1.0, 0.0)
                    push = min_dist / 2.0
                    a.x -= nx * push
                    a.y -= ny * push
                    b.x += nx * push
                    b.y += ny * push
                    continue
                if d >= min_dist:
                    continue
                push = (min_dist - d) / 2.0
                nx = dx / d
                ny = dy / d
                a.x -= nx * push
                a.y -= ny * push
                b.x += nx * push
                b.y += ny * push


def _opening_gap(
    wall: Aabb,
    ox: float,
    oy: float,
    width_m: float,
    *,
    horizontal: bool,
) -> Aabb | None:
    """Clear rectangle punched through a wall at an opening, or None if far away."""
    half = width_m / 2.0
    if horizontal:
        gap = Aabb(ox - half, wall.y, width_m, wall.height)
    else:
        gap = Aabb(wall.x, oy - half, wall.width, width_m)
    # Opening must land on or near this wall segment
    pad = max(0.15, min(wall.width, wall.height) + 0.05)
    near = Aabb(wall.x - pad, wall.y - pad, wall.width + 2 * pad, wall.height + 2 * pad)
    if not (wall.intersects(gap) and near.contains_point(ox, oy)):
        return None
    return gap


def _subtract_gap(rect: Aabb, gap: Aabb) -> list[Aabb]:
    """Return axis-aligned pieces of rect after removing gap intersection."""
    ix = max(rect.x, gap.x)
    iy = max(rect.y, gap.y)
    ir = min(rect.right, gap.right)
    ib = min(rect.bottom, gap.bottom)
    if ix >= ir or iy >= ib:
        return [rect]

    pieces: list[Aabb] = []
    if rect.x < ix:
        pieces.append(Aabb(rect.x, rect.y, ix - rect.x, rect.height))
    if ir < rect.right:
        pieces.append(Aabb(ir, rect.y, rect.right - ir, rect.height))
    if rect.y < iy:
        pieces.append(Aabb(ix, rect.y, ir - ix, iy - rect.y))
    if ib < rect.bottom:
        pieces.append(Aabb(ix, ib, ir - ix, rect.bottom - ib))
    return [p for p in pieces if p.width > 1e-9 and p.height > 1e-9]


def _punch_openings(
    segments: list[tuple[Aabb, bool]],
    openings: list[tuple[float, float, float]],
) -> list[Aabb]:
    """Punch door/exit gaps from (rect, is_horizontal) segments; return solid AABBs."""
    solids: list[Aabb] = []
    for rect, horizontal in segments:
        pieces = [rect]
        for ox, oy, ow in openings:
            next_pieces: list[Aabb] = []
            for seg in pieces:
                gap = _opening_gap(seg, ox, oy, ow, horizontal=horizontal)
                if gap is None:
                    next_pieces.append(seg)
                else:
                    next_pieces.extend(_subtract_gap(seg, gap))
            pieces = next_pieces
        solids.extend(pieces)
    return solids


def solid_wall_rects(
    walls: list[Wall],
    doors: list[Door],
    exits: list[Exit],
) -> list[Aabb]:
    """Explicit wall AABBs with door/exit clear widths punched out."""
    openings = [(d.x, d.y, d.width) for d in doors] + [(e.x, e.y, e.width) for e in exits]
    segments = [
        (Aabb(w.x, w.y, w.width, w.height), w.width >= w.height) for w in walls
    ]
    return _punch_openings(segments, openings)


# Thin shell along each space edge; only door/exit widths are passable.
_SPACE_EDGE_THICKNESS_M = 0.1


def space_boundary_rects(
    spaces: list[Space],
    doors: list[Door],
    exits: list[Exit],
    thickness_m: float = _SPACE_EDGE_THICKNESS_M,
) -> list[Aabb]:
    """Space perimeter segments as solids, with door/exit widths punched through."""
    half = thickness_m / 2.0
    segments: list[tuple[Aabb, bool]] = []
    for s in spaces:
        segments.append((Aabb(s.x, s.y - half, s.width, thickness_m), True))
        segments.append((Aabb(s.x, s.y + s.height - half, s.width, thickness_m), True))
        segments.append((Aabb(s.x - half, s.y, thickness_m, s.height), False))
        segments.append((Aabb(s.x + s.width - half, s.y, thickness_m, s.height), False))
    openings = [(d.x, d.y, d.width) for d in doors] + [(e.x, e.y, e.width) for e in exits]
    return _punch_openings(segments, openings)


def build_collision_solids(
    walls: list[Wall],
    spaces: list[Space],
    doors: list[Door],
    exits: list[Exit],
) -> list[Aabb]:
    """Space boundaries plus optional explicit walls; openings stay passable."""
    return space_boundary_rects(spaces, doors, exits) + solid_wall_rects(
        walls, doors, exits
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


def resolve_wall_collisions(
    occupants: list[PositionedOccupant],
    solids: list[Aabb],
    radius_m: float,
) -> None:
    """Push active occupants so their body circle does not overlap solid wall AABBs."""
    if not solids or radius_m < 0:
        return
    r = radius_m
    active = [
        o
        for o in occupants
        if o.status not in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED)
    ]
    for o in active:
        for solid in solids:
            inflated = Aabb(
                solid.x - r,
                solid.y - r,
                solid.width + 2.0 * r,
                solid.height + 2.0 * r,
            )
            o.x, o.y = push_out_of_aabb(o.x, o.y, inflated)
