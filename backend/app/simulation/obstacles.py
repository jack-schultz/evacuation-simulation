"""Shared rectangle clearance for routing, spawning and swept movement."""

import math
from collections.abc import Iterable, Sequence
from itertools import chain

from app.domain.building import Obstacle, Space
from app.domain.geometry import distance_to_boundary, edges, point_in_polygon, segment_in_polygon
from app.simulation.apertures import PositionedOccupant
from app.simulation.walls import _point_to_segment_dist

Point = tuple[float, float]


def segment_hits_rectangle(
    a: Point, b: Point, obstacle: Obstacle, clearance: float = 0.0,
) -> bool:
    """Slab intersection against an inflated rectangle (including endpoints)."""
    low, high = 0.0, 1.0
    for start, end, minimum, maximum in (
        (a[0], b[0], obstacle.x - clearance, obstacle.x + obstacle.width + clearance),
        (a[1], b[1], obstacle.y - clearance, obstacle.y + obstacle.height + clearance),
    ):
        delta = end - start
        if abs(delta) < 1e-12:
            if start < minimum or start > maximum:
                return False
            continue
        t0, t1 = sorted(((minimum - start) / delta, (maximum - start) / delta))
        low, high = max(low, t0), min(high, t1)
        if low > high:
            return False
    return True


def clear_segment(
    a: Point, b: Point, obstacles: Sequence[Obstacle], radius: float,
) -> bool:
    return not any(segment_hits_rectangle(a, b, o, radius) for o in obstacles)


def visible(
    a: Point, b: Point, space: Space, obstacles: Sequence[Obstacle], radius: float,
) -> bool:
    if not segment_in_polygon(a, b, space.vertices):
        return False
    if not clear_segment(a, b, obstacles, radius):
        return False
    # Obstacle detours must leave body clearance against the room walls too.
    # Endpoints on openings are handled by the existing aperture logic.
    if obstacles and all(distance_to_boundary(*p, space.vertices) > radius for p in (a, b)):
        for c, d in edges(space.vertices):
            if min(_point_to_segment_dist(*c, *a, *b),
                   _point_to_segment_dist(*d, *a, *b),
                   _point_to_segment_dist(*a, *c, *d),
                   _point_to_segment_dist(*b, *c, *d)) < radius + 0.05:
                return False
    return True


def wall_clearance_cost(
    a: Point, b: Point, space: Space, radius: float,
) -> float:
    """Soft routing penalty for walking close to room walls.

    Paths through narrow passages remain available when they are necessary.
    """
    length = math.dist(a, b)
    if length < 1e-9:
        return 0.0
    desired_free_m = 0.9
    samples = (0.2, 0.4, 0.6, 0.8)
    crowding = sum(
        max(0.0, (desired_free_m - max(
            0.0,
            distance_to_boundary(
                a[0] + (b[0] - a[0]) * t,
                a[1] + (b[1] - a[1]) * t,
                space.vertices,
            ) - radius,
        )) / desired_free_m)
        for t in samples
    ) / len(samples)
    return length * 2.5 * crowding


def corner_points(
    obstacles: Sequence[Obstacle], radius: float, space: Space | None = None,
) -> Iterable[Point]:
    """Allow a relaxed turn in open rooms, tightening clearance in narrow gaps."""
    for o in obstacles:
        for sx in (-1, 1):
            for sy in (-1, 1):
                for margin in (radius + max(radius * 1.2, 0.35) + 0.1, radius + 0.08):
                    x = o.x - margin if sx < 0 else o.x + o.width + margin
                    y = o.y - margin if sy < 0 else o.y + o.height + margin
                    if space is not None and (
                        not point_in_polygon(x, y, space.vertices)
                        or distance_to_boundary(x, y, space.vertices) < radius + 0.05
                        or not clear_segment((x, y), (x, y), obstacles, radius)
                    ):
                        continue
                    yield x, y
                    break


def free_position(
    position: Point, space: Space, obstacles: Sequence[Obstacle], radius: float,
    occupied: Sequence[PositionedOccupant] = (),
) -> Point | None:
    """Find nearest free spawn/space anchor; fail explicitly if no body fits."""
    def valid(p):
        return (point_in_polygon(*p, space.vertices)
                and distance_to_boundary(*p, space.vertices) >= radius + 0.05
                and clear_segment(p, p, obstacles, radius + 0.01)
                and all((p[0]-o.x)**2 + (p[1]-o.y)**2 >= (2*radius + 0.01)**2 for o in occupied))
    if valid(position):
        return position
    x, y, width, height = space.bbox
    step = max(radius, 0.1)
    # Grid fallback handles obstacles covering the default centroid and overlaps.
    grid = (
        (x + radius + 0.06 + ix * step, y + radius + 0.06 + iy * step)
        for ix in range(max(0, math.ceil((width - 2 * radius) / step)))
        for iy in range(max(0, math.ceil((height - 2 * radius) / step)))
    )
    candidates = (p for p in chain(corner_points(obstacles, radius), grid) if valid(p))
    return min(candidates, key=lambda p: (p[0]-position[0])**2 + (p[1]-position[1])**2,
               default=None)
