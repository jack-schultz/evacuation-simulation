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

    def _safe_inside(px: float, py: float) -> bool:
        if not point_in_polygon(px, py, vertices):
            return False
        if inset_m <= 0:
            return True
        return distance_to_boundary(px, py, vertices) >= inset_m - 1e-9

    if _safe_inside(x, y):
        return x, y

    bx, by = closest_boundary_point(x, y, vertices)
    ix, iy = interior_point(vertices)

    if point_in_polygon(x, y, vertices):
        # Inside but too close to an edge: push away from that edge along the
        # inward normal (avoids long chords across concave bays).
        dx, dy = x - bx, y - by
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1e-9:
            dx, dy = ix - bx, iy - by
            length = (dx * dx + dy * dy) ** 0.5
            if length < 1e-9:
                return x, y
        needed = max(inset_m, 0.05)
        px = bx + dx / length * needed
        py = by + dy / length * needed
        if point_in_polygon(px, py, vertices):
            return px, py
        return x, y

    # Outside: continue from the boundary further inward
    dx, dy = bx - x, by - y
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-9:
        dx, dy = ix - bx, iy - by
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1e-9:
            return bx, by
    ux, uy = dx / length, dy / length
    needed = max(inset_m, 0.05)
    px, py = bx + ux * needed, by + uy * needed
    if point_in_polygon(px, py, vertices):
        return px, py
    return ix, iy


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


def interior_point(vertices: Sequence[Point]) -> Point:
    """A point guaranteed strictly inside the polygon (centroid when valid)."""
    pts = _ring(vertices)
    if not pts:
        return 0.0, 0.0
    cx, cy = centroid(pts)
    if point_in_polygon(cx, cy, pts) and distance_to_boundary(cx, cy, pts) > 1e-6:
        return cx, cy
    # Fan-triangulate from first vertex; prefer a triangle centroid deep inside
    n = len(pts)
    best: Point | None = None
    best_clearance = -1.0
    for i in range(1, n - 1):
        ax, ay = pts[0]
        bx, by = pts[i]
        cx2, cy2 = pts[i + 1]
        tx = (ax + bx + cx2) / 3.0
        ty = (ay + by + cy2) / 3.0
        if not point_in_polygon(tx, ty, pts):
            continue
        clearance = distance_to_boundary(tx, ty, pts)
        if clearance > best_clearance:
            best_clearance = clearance
            best = (tx, ty)
    if best is not None and best_clearance > 1e-6:
        return best
    # Grid sample inside bbox as last resort
    min_x, min_y, width, height = bbox(pts)
    if width > 0 and height > 0:
        for gy in range(1, 8):
            for gx in range(1, 8):
                sx = min_x + width * gx / 8.0
                sy = min_y + height * gy / 8.0
                if point_in_polygon(sx, sy, pts) and distance_to_boundary(sx, sy, pts) > 1e-6:
                    return sx, sy
    return cx, cy


def reflex_vertices(vertices: Sequence[Point]) -> list[Point]:
    """Concave corners of the polygon (interior angle > π)."""
    pts = _ring(vertices)
    n = len(pts)
    if n < 3:
        return []
    # Positive signed area => CCW in math coords; reflex turns are clockwise (cross < 0)
    # Negative signed area => CW; reflex turns are counter-clockwise (cross > 0)
    ccw = signed_area(pts) > 0
    result: list[Point] = []
    for i in range(n):
        ax, ay = pts[(i - 1) % n]
        bx, by = pts[i]
        cx, cy = pts[(i + 1) % n]
        cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        is_reflex = cross < -1e-12 if ccw else cross > 1e-12
        if is_reflex:
            result.append(pts[i])
    return result


def _segments_properly_intersect(
    a1: Point, a2: Point, b1: Point, b2: Point
) -> bool:
    """True if open segments a1–a2 and b1–b2 properly cross (not mere endpoint touch)."""

    def orient(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    o1 = orient(a1, a2, b1)
    o2 = orient(a1, a2, b2)
    o3 = orient(b1, b2, a1)
    o4 = orient(b1, b2, a2)
    if abs(o1) < 1e-12 and abs(o2) < 1e-12 and abs(o3) < 1e-12 and abs(o4) < 1e-12:
        # Colinear — treat as non-crossing for visibility (edge-adjacent OK)
        return False
    return (o1 * o2 < 0) and (o3 * o4 < 0)


def segment_in_polygon(a: Point, b: Point, vertices: Sequence[Point]) -> bool:
    """True if the open segment between a and b lies inside the polygon.

    Rejects chords that leave and re-enter (e.g. across a U bay) by requiring
    no proper edge crossings and that the midpoint is inside.
    """
    pts = _ring(vertices)
    if len(pts) < 3:
        return False
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    if (ax - bx) ** 2 + (ay - by) ** 2 < 1e-18:
        return point_in_polygon(ax, ay, pts)

    mid = ((ax + bx) / 2.0, (ay + by) / 2.0)
    if not point_in_polygon(mid[0], mid[1], pts):
        return False

    # Also sample two more points to catch thin exterior lobes
    for t in (0.25, 0.75):
        sx = ax + (bx - ax) * t
        sy = ay + (by - ay) * t
        if not point_in_polygon(sx, sy, pts):
            return False

    a_pt = (ax, ay)
    b_pt = (bx, by)
    for e0, e1 in edges(pts):
        if _segments_properly_intersect(a_pt, b_pt, e0, e1):
            return False
    return True
