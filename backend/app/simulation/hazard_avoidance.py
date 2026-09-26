"""Local waypoint routing around a growing circular flood area."""

from __future__ import annotations

import heapq
import math

from app.domain.building import FloodEmergency, Space
from app.domain.geometry import point_in_polygon, segment_in_polygon
from app.simulation.hazards import hazard_radius_at


def flood_detour_target(
    start: tuple[float, float],
    goal: tuple[float, float],
    space: Space | None,
    flood: FloodEmergency | None,
    t: float,
    occupant_radius_m: float,
) -> tuple[float, float] | None | bool:
    """Return the next safe waypoint, None for a clear segment, False if blocked.

    The flood is expanded by the occupant's body radius and a small clearance.
    A sampled visibility graph around that circle supplies stable local detours.
    """
    radius = hazard_radius_at(flood, t)
    if radius is None:
        return None
    if space is None or len(space.vertices) < 3:
        return False

    cx, cy = flood.x, flood.y
    blocked_radius = radius + max(occupant_radius_m, 0.0) + 0.1
    sx, sy = start
    gx, gy = goal
    start_distance = math.hypot(sx - cx, sy - cy)
    goal_distance = math.hypot(gx - cx, gy - cy)

    # If the expanding water reaches an occupant, guide them outward first.
    # The existing hazard speed model permits movement away from the centre.
    if start_distance < blocked_radius:
        candidates = []
        for i in range(72):
            angle = 2.0 * math.pi * i / 72
            point = (
                cx + math.cos(angle) * (blocked_radius + 0.2),
                cy + math.sin(angle) * (blocked_radius + 0.2),
            )
            if point_in_polygon(*point, space.vertices) and segment_in_polygon(
                start, point, space.vertices
            ):
                # Favor the exit direction while guaranteeing outward movement.
                goal_angle = math.atan2(gy - cy, gx - cx)
                delta = math.atan2(math.sin(angle - goal_angle), math.cos(angle - goal_angle))
                candidates.append((abs(delta), point))
        if not candidates:
            return False
        return min(candidates, key=lambda item: item[0])[1]

    if goal_distance <= blocked_radius:
        return False

    def clear_of_flood(a: tuple[float, float], b: tuple[float, float]) -> bool:
        dx, dy = b[0] - a[0], b[1] - a[1]
        length_sq = dx * dx + dy * dy
        if length_sq <= 1e-18:
            return math.hypot(a[0] - cx, a[1] - cy) >= blocked_radius
        fraction = max(0.0, min(1.0, ((cx - a[0]) * dx + (cy - a[1]) * dy) / length_sq))
        nearest_x, nearest_y = a[0] + fraction * dx, a[1] + fraction * dy
        return (nearest_x - cx) ** 2 + (nearest_y - cy) ** 2 >= blocked_radius**2 - 1e-9

    if clear_of_flood(start, goal):
        return None

    # Chords between adjacent samples stay outside the inflated flood boundary.
    sample_count = 32
    ring_radius = blocked_radius / math.cos(math.pi / sample_count) + 0.02
    points: list[tuple[float, float]] = [start, goal]
    for i in range(sample_count):
        angle = 2.0 * math.pi * i / sample_count
        point = (cx + math.cos(angle) * ring_radius, cy + math.sin(angle) * ring_radius)
        if point_in_polygon(*point, space.vertices):
            points.append(point)

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
        return False

    path = [1]
    while path[-1] != 0:
        parent = previous[path[-1]]
        if parent < 0:
            return False
        path.append(parent)
    path.reverse()
    return points[path[1]] if len(path) > 1 else None
