"""Local waypoint routing around a growing circular flood area."""

from __future__ import annotations

import heapq
import math

from app.domain.building import FloodRoomState, Space
from app.domain.geometry import point_in_polygon, segment_in_polygon


def flood_detour_target(
    start: tuple[float, float],
    goal: tuple[float, float],
    space: Space | None,
    flood_plumes: list[FloodRoomState] | None,
    occupant_radius_m: float,
) -> tuple[float, float] | None | bool:
    """Prefer a dry waypoint around water; None keeps the direct (possibly wet) path.

    People may walk through flood (slowed + exposure elsewhere). Detours only
    help when the goal is dry and a clear ring path exists around the water.
    """
    if space is None or len(space.vertices) < 3:
        return None
    plumes = flood_plumes or []
    plume = next((p for p in plumes if p.space_id == space.id), None)
    if plume is None:
        return None

    cx, cy = plume.x, plume.y
    radius = plume.radius_m
    blocked_radius = radius + max(occupant_radius_m, 0.0) + 0.1
    sx, sy = start
    gx, gy = goal
    start_distance = math.hypot(sx - cx, sy - cy)
    goal_distance = math.hypot(gx - cx, gy - cy)

    def clear_of_flood(a: tuple[float, float], b: tuple[float, float]) -> bool:
        dx, dy = b[0] - a[0], b[1] - a[1]
        length_sq = dx * dx + dy * dy
        if length_sq <= 1e-18:
            return math.hypot(a[0] - cx, a[1] - cy) >= blocked_radius
        fraction = max(0.0, min(1.0, ((cx - a[0]) * dx + (cy - a[1]) * dy) / length_sq))
        nearest_x, nearest_y = a[0] + fraction * dx, a[1] + fraction * dy
        return (nearest_x - cx) ** 2 + (nearest_y - cy) ** 2 >= blocked_radius**2 - 1e-9

    # Goal is in/through water: walk straight (soft flood allows transit).
    if goal_distance <= blocked_radius:
        return None

    if clear_of_flood(start, goal):
        return None

    # Dry goal but path crosses water — try a ring detour; otherwise walk through.
    sample_count = 32
    ring_radius = blocked_radius / math.cos(math.pi / sample_count) + 0.02
    points: list[tuple[float, float]] = [start, goal]
    for i in range(sample_count):
        angle = 2.0 * math.pi * i / sample_count
        point = (cx + math.cos(angle) * ring_radius, cy + math.sin(angle) * ring_radius)
        if point_in_polygon(*point, space.vertices):
            points.append(point)

    # If already in water, seed a step out onto the ring toward the goal first.
    if start_distance < blocked_radius:
        goal_angle = math.atan2(gy - cy, gx - cx)
        best = None
        best_delta = math.inf
        for i in range(72):
            angle = 2.0 * math.pi * i / 72
            point = (
                cx + math.cos(angle) * (blocked_radius + 0.2),
                cy + math.sin(angle) * (blocked_radius + 0.2),
            )
            if not (
                point_in_polygon(*point, space.vertices)
                and segment_in_polygon(start, point, space.vertices)
            ):
                continue
            delta = abs(math.atan2(math.sin(angle - goal_angle), math.cos(angle - goal_angle)))
            if delta < best_delta:
                best_delta = delta
                best = point
        if best is not None:
            return best
        return None

    adjacency: list[list[tuple[int, float]]] = [[] for _ in points]
    for i, a in enumerate(points):
        for j in range(i + 1, len(points)):
            b = points[j]
            if not clear_of_flood(a, b) or not segment_in_polygon(a, b, space.vertices):
                continue
            distance = math.hypot(b[0] - a[0], b[1] - a[1])
            adjacency[i].append((j, distance))
            adjacency[j].append((i, distance))

    distances = [math.inf] * len(points)
    previous = [-1] * len(points)
    distances[0] = 0.0
    queue = [(0.0, 0)]
    while queue:
        cost, node = heapq.heappop(queue)
        if cost > distances[node]:
            continue
        if node == 1:
            break
        for neighbor, edge_cost in adjacency[node]:
            next_cost = cost + edge_cost
            if next_cost < distances[neighbor]:
                distances[neighbor] = next_cost
                previous[neighbor] = node
                heapq.heappush(queue, (next_cost, neighbor))

    if not math.isfinite(distances[1]):
        return None

    path = [1]
    while path[-1] != 0:
        parent = previous[path[-1]]
        if parent < 0:
            return None
        path.append(parent)
    path.reverse()
    return points[path[1]] if len(path) > 1 else None
