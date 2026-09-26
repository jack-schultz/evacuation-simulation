"""Stair centreline geometry and climb path helpers."""

from __future__ import annotations

from app.domain.building import Floor, Space


def floor_elevation(floors: dict[str, Floor], floor_id: str) -> float:
    floor = floors.get(floor_id)
    return floor.elevation_m if floor is not None else 0.0


def stair_rise_m(floors: dict[str, Floor], a: Space, b: Space) -> float:
    rise = abs(floor_elevation(floors, a.floor_id) - floor_elevation(floors, b.floor_id))
    return rise if rise > 1e-6 else 3.0


def stair_long_axis(space: Space) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return two endpoints of the stair polygon's long axis through the centroid."""
    min_x, min_y, w, h = space.bbox
    cx, cy = space.centroid
    if w >= h:
        return (min_x + 0.15 * w, cy), (min_x + 0.85 * w, cy)
    return (cx, min_y + 0.15 * h), (cx, min_y + 0.85 * h)


def preferred_down_direction(
    space: Space,
    partner: Space,
    floors: dict[str, Floor],
) -> tuple[float, float]:
    """Unit XY direction along the stair long axis toward the lower floor (preferred evacuation)."""
    a, b = stair_long_axis(space)
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-9:
        return 1.0, 0.0
    ux, uy = dx / length, dy / length
    # Arrow points "down" the shaft: if this floor is higher, arrow toward +axis;
    # if lower, arrow toward partner (up the shaft visually on this plan).
    elev = floor_elevation(floors, space.floor_id)
    partner_elev = floor_elevation(floors, partner.floor_id)
    if elev >= partner_elev:
        return ux, uy
    return -ux, -uy


def climb_position(
    from_space: Space,
    to_space: Space,
    floors: dict[str, Floor],
    progress: float,
) -> tuple[float, float, str]:
    """Position and floor_id along a 0..1 climb from from_space to to_space.

    First half walks the origin stair centreline toward the portal end;
    second half walks the destination stair from portal toward exit end.
    """
    p = max(0.0, min(1.0, progress))
    from_a, from_b = stair_long_axis(from_space)
    to_a, to_b = stair_long_axis(to_space)
    # Orient so travel goes from_a -> from_b on origin when descending, etc.
    elev_from = floor_elevation(floors, from_space.floor_id)
    elev_to = floor_elevation(floors, to_space.floor_id)
    descending = elev_from >= elev_to
    if descending:
        o0, o1 = from_a, from_b
        d0, d1 = to_b, to_a  # arrive at far end, walk toward near/exit end
    else:
        o0, o1 = from_b, from_a
        d0, d1 = to_a, to_b

    if p <= 0.5:
        t = p * 2.0
        x = o0[0] + (o1[0] - o0[0]) * t
        y = o0[1] + (o1[1] - o0[1]) * t
        return x, y, from_space.floor_id

    t = (p - 0.5) * 2.0
    x = d0[0] + (d1[0] - d0[0]) * t
    y = d0[1] + (d1[1] - d0[1]) * t
    return x, y, to_space.floor_id


def climb_path_length_m(from_space: Space, to_space: Space, floors: dict[str, Floor]) -> float:
    """Approximate metre length of the directed stair walk (both halves + rise)."""
    a0, a1 = stair_long_axis(from_space)
    b0, b1 = stair_long_axis(to_space)
    run = ((a1[0] - a0[0]) ** 2 + (a1[1] - a0[1]) ** 2) ** 0.5
    run += ((b1[0] - b0[0]) ** 2 + (b1[1] - b0[1]) ** 2) ** 0.5
    return run + stair_rise_m(floors, from_space, to_space)
