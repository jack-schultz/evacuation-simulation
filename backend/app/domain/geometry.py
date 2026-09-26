"""2D polygon helpers for space geometry (top-left origin, metres)."""

from __future__ import annotations

from typing import Sequence

Point = tuple[float, float]


def _ring(vertices: Sequence[Point]) -> list[Point]:
    """Return vertices with the closing duplicate stripped if present."""
    pts = [(float(x), float(y)) for x, y in vertices]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def signed_area(vertices: Sequence[Point]) -> float:
    """Shoelace signed area (positive for counter-clockwise in math coords)."""
    pts = _ring(vertices)
    if len(pts) < 3:
        return 0.0
    total = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def area(vertices: Sequence[Point]) -> float:
    return abs(signed_area(vertices))


def centroid(vertices: Sequence[Point]) -> Point:
    """Polygon centroid via shoelace; falls back to vertex average for degenerate rings."""
    pts = _ring(vertices)
    if not pts:
        return 0.0, 0.0
    if len(pts) == 1:
        return pts[0]
    if len(pts) == 2:
        return (pts[0][0] + pts[1][0]) / 2.0, (pts[0][1] + pts[1][1]) / 2.0

    a = signed_area(pts)
    if abs(a) < 1e-12:
        sx = sum(p[0] for p in pts) / len(pts)
        sy = sum(p[1] for p in pts) / len(pts)
        return sx, sy

    cx = 0.0
    cy = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    factor = 1.0 / (6.0 * a)
    return cx * factor, cy * factor


def bbox(vertices: Sequence[Point]) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, width, height)."""
    pts = _ring(vertices)
    if not pts:
        return 0.0, 0.0, 0.0, 0.0
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return min_x, min_y, max_x - min_x, max_y - min_y


def edges(vertices: Sequence[Point]) -> list[tuple[Point, Point]]:
    pts = _ring(vertices)
    if len(pts) < 2:
        return []
    n = len(pts)
    return [(pts[i], pts[(i + 1) % n]) for i in range(n)]


def point_in_polygon(x: float, y: float, vertices: Sequence[Point]) -> bool:
    """Ray-casting inclusion test (boundary counts as inside)."""
    pts = _ring(vertices)
    if len(pts) < 3:
        return False

    # Boundary check via distance to edges
    for (ax, ay), (bx, by) in edges(pts):
        if _point_to_segment_dist(x, y, ax, ay, bx, by) <= 1e-9:
            return True

    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-30) + xi
        ):
            inside = not inside
        j = i
    return inside


def distance_to_boundary(x: float, y: float, vertices: Sequence[Point]) -> float:
    """Minimum distance from point to any polygon edge."""
    best = float("inf")
    for (ax, ay), (bx, by) in edges(vertices):
        d = _point_to_segment_dist(x, y, ax, ay, bx, by)
        if d < best:
            best = d
    return best if best != float("inf") else 0.0


def closest_boundary_point(x: float, y: float, vertices: Sequence[Point]) -> Point:
    """Project (x, y) onto the nearest point on the polygon boundary."""
    best = x, y
    best_d = float("inf")
    for (ax, ay), (bx, by) in edges(vertices):
        px, py = _closest_point_on_segment(x, y, ax, ay, bx, by)
        d = (px - x) ** 2 + (py - y) ** 2
        if d < best_d:
            best_d = d
            best = px, py
    return best


def clamp_into_polygon(
    x: float, y: float, vertices: Sequence[Point], inset_m: float = 0.0
) -> Point:
    """Keep point inside the polygon, optionally inset from edges by inset_m."""
    cx, cy = centroid(vertices)

    def _safe_inside(px: float, py: float) -> bool:
        if not point_in_polygon(px, py, vertices):
            return False
        if inset_m <= 0:
            return True
        return distance_to_boundary(px, py, vertices) >= inset_m - 1e-9

    if _safe_inside(x, y):
        return x, y

    # Binary search from current point (or boundary projection) toward centroid
    start_x, start_y = x, y
    if not point_in_polygon(x, y, vertices):
        start_x, start_y = closest_boundary_point(x, y, vertices)

    if _safe_inside(cx, cy):
        lo, hi = 0.0, 1.0
        best = cx, cy
        for _ in range(24):
            mid = (lo + hi) / 2.0
            px = start_x + (cx - start_x) * mid
            py = start_y + (cy - start_y) * mid
            if _safe_inside(px, py):
                best = px, py
                hi = mid
            else:
                lo = mid
        return best

    return cx, cy


def _point_to_segment_dist(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    qx, qy = _closest_point_on_segment(px, py, ax, ay, bx, by)
    return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5


def _closest_point_on_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> Point:
    abx, aby = bx - ax, by - ay
    ab_len2 = abx * abx + aby * aby
    if ab_len2 < 1e-18:
        return ax, ay
    t = ((px - ax) * abx + (py - ay) * aby) / ab_len2
    t = max(0.0, min(1.0, t))
    return ax + t * abx, ay + t * aby


def rect_vertices(x: float, y: float, width: float, height: float) -> list[Point]:
    return [
        (x, y),
        (x + width, y),
        (x + width, y + height),
        (x, y + height),
    ]
