"""Spatial collision helpers: body radius, door apertures, overlap resolution."""

from __future__ import annotations

from typing import Protocol

from app.domain.building import OccupantStatus


class PositionedOccupant(Protocol):
    id: str
    x: float
    y: float
    status: OccupantStatus


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
