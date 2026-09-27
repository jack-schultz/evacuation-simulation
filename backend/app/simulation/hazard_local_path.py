"""In-room local paths that skirt expanding fire / flood / smoke."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

from app.domain.building import Obstacle, Space
from app.domain.geometry import distance_to_boundary, point_in_polygon
from app.simulation.graph import NodeKind
from app.simulation.hazard_routing import (
    HazardRoutingContext,
    fire_disk_blocks_point,
    fire_disk_blocks_segment,
    lethal_segment_hits_fire,
    point_in_disk,
    soft_hazard_speed_along_segment,
)
from app.simulation.hazards import fire_touches
from app.simulation.obstacles import clear_segment, visible, wall_clearance_cost

Point = tuple[float, float]

# Sample density around hard fire disks for skirt waypoints.
_FIRE_SAMPLE_COUNT = 24


@dataclass(frozen=True)
class LocalPathResult:
    """First steering hop toward the goal, or impassable."""

    first_hop: Point | None
    reachable: bool
    direct: bool
    hops: tuple[Point, ...] = ()


def _tangent_points(px: float, py: float, cx: float, cy: float, radius: float) -> list[Point]:
    """External tangency points on a circle from an outside point."""
    dx, dy = px - cx, py - cy
    dist = math.hypot(dx, dy)
    if dist <= radius + 1e-9:
        return []
    offset = math.acos(min(1.0, radius / dist))
    base = math.atan2(dy, dx)
    return [
        (cx + radius * math.cos(base + offset), cy + radius * math.sin(base + offset)),
        (cx + radius * math.cos(base - offset), cy + radius * math.sin(base - offset)),
    ]


def _fire_skirt_points(
    ctx: HazardRoutingContext,
    floor_id: str,
    space: Space,
    body_radius: float,
    *,
    from_point: Point | None = None,
    to_point: Point | None = None,
) -> list[Point]:
    points: list[Point] = []
    hard = ctx.hard_fire_radius_extra
    n = _FIRE_SAMPLE_COUNT
    for plume in ctx.fire_plumes:
        if plume.floor_id != floor_id:
            continue
        blocked = plume.radius_m + hard
        if blocked <= 0:
            continue
        # Ring far enough out that chords between adjacent samples stay outside
        # the hard disk (otherwise Dijkstra has no path around the fire).
        ring = blocked / math.cos(math.pi / n) + 0.35
        for i in range(n):
            ang = 2.0 * math.pi * i / n
            x = plume.x + math.cos(ang) * ring
            y = plume.y + math.sin(ang) * ring
            if not point_in_polygon(x, y, space.vertices):
                continue
            if distance_to_boundary(x, y, space.vertices) < body_radius + 0.05:
                continue
            if fire_disk_blocks_point(ctx, floor_id, x, y):
                continue
            points.append((x, y))
        for origin in (from_point, to_point):
            if origin is None:
                continue
            for tx, ty in _tangent_points(origin[0], origin[1], plume.x, plume.y, ring):
                if not point_in_polygon(tx, ty, space.vertices):
                    continue
                if distance_to_boundary(tx, ty, space.vertices) < body_radius + 0.05:
                    continue
                if fire_disk_blocks_point(ctx, floor_id, tx, ty):
                    continue
                points.append((tx, ty))
    return points


def _soft_avoid_points(
    ctx: HazardRoutingContext,
    space: Space,
    body_radius: float,
) -> list[Point]:
    """Sample rings around flood/smoke so soft avoidance has waypoints."""
    points: list[Point] = []
    soft = ctx.soft_clearance_m + body_radius
    for plume in list(ctx.flood_plumes) + list(ctx.smoke_plumes):
        if getattr(plume, "space_id", None) != space.id:
            continue
        ring = plume.radius_m + soft + 0.1
        if ring <= 0:
            continue
        for i in range(8):
            ang = 2.0 * math.pi * i / 8
            x = plume.x + math.cos(ang) * ring
            y = plume.y + math.sin(ang) * ring
            if not point_in_polygon(x, y, space.vertices):
                continue
            if distance_to_boundary(x, y, space.vertices) < body_radius + 0.05:
                continue
            points.append((x, y))
    return points


def _chord_ok(
    a: Point,
    b: Point,
    space: Space,
    obstacles: list[Obstacle],
    body_radius: float,
    ctx: HazardRoutingContext,
    floor_id: str,
    *,
    allow_clearance_near_goal: bool = False,
) -> bool:
    if not visible(a, b, space, obstacles, body_radius):
        return False
    # Final approach to an exit may enter the soft clearance ring, but never
    # the lethal plume itself.
    if allow_clearance_near_goal:
        if lethal_segment_hits_fire(ctx, floor_id, a[0], a[1], b[0], b[1]):
            return False
        return True
    if fire_disk_blocks_segment(ctx, floor_id, a[0], a[1], b[0], b[1]):
        return False
    return True


def _edge_cost(
    a: Point,
    b: Point,
    space: Space,
    body_radius: float,
    ctx: HazardRoutingContext,
) -> float:
    length = math.dist(a, b)
    soft = soft_hazard_speed_along_segment(ctx, space.id, a[0], a[1], b[0], b[1])
    cost = length / max(soft, 0.05)
    cost += wall_clearance_cost(a, b, space, body_radius)
    soft_r = ctx.soft_clearance_m
    for plume in ctx.flood_plumes:
        if plume.space_id != space.id:
            continue
        mid = ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)
        if point_in_disk(mid[0], mid[1], plume.x, plume.y, plume.radius_m + soft_r):
            cost += length * 2.0
    for plume in ctx.smoke_plumes:
        if plume.space_id != space.id:
            continue
        mid = ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)
        if point_in_disk(mid[0], mid[1], plume.x, plume.y, plume.radius_m + soft_r):
            cost += length * 1.5
    return cost


def plan_local_path(
    start: Point,
    goal: Point,
    space: Space,
    floor_id: str,
    obstacles: list[Obstacle],
    ctx: HazardRoutingContext,
    body_radius: float,
    extra_waypoints: list[Point] | None = None,
) -> LocalPathResult:
    """Shortest clear in-room path from start to goal, skirting hazards.

    Returns the first hop after ``start``. When the direct chord is clear and
    cheapest, ``direct`` is True. ``reachable`` is False when fire seals the goal.
    """
    if fire_touches(
        ctx.fire_plumes, floor_id, goal[0], goal[1], body_radius
    ):
        # #region agent log
        try:
            import json, time
            with open("/Users/jackschultz/PycharmProjects/evacuation-simulation/.cursor/debug-a376ca.log", "a") as _f:
                _f.write(json.dumps({
                    "sessionId": "a376ca",
                    "hypothesisId": "B",
                    "location": "hazard_local_path.py:plan_local_path",
                    "message": "goal inside lethal fire",
                    "data": {
                        "start": [round(start[0], 2), round(start[1], 2)],
                        "goal": [round(goal[0], 2), round(goal[1], 2)],
                        "floor_id": floor_id,
                        "clearance": ctx.hard_fire_radius_extra,
                        "n_fire": len(ctx.fire_plumes),
                    },
                    "timestamp": int(time.time() * 1000),
                }) + "\n")
        except Exception:
            pass
        # #endregion
        return LocalPathResult(first_hop=None, reachable=False, direct=False, hops=())

    # Direct is only clear when the full chord respects hard fire clearance.
    # Final approaches may enter the clearance ring (see edge building below).
    direct_clear = _chord_ok(
        start, goal, space, obstacles, body_radius, ctx, floor_id,
        allow_clearance_near_goal=False,
    )

    waypoints: list[Point] = [goal]
    if extra_waypoints:
        waypoints.extend(extra_waypoints)
    waypoints.extend(_fire_skirt_points(
        ctx, floor_id, space, body_radius, from_point=start, to_point=goal,
    ))
    waypoints.extend(_soft_avoid_points(ctx, space, body_radius))

    uniq: list[Point] = []
    seen: set[tuple[float, float]] = set()
    for p in waypoints:
        key = (round(p[0], 3), round(p[1], 3))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    waypoints = uniq

    nodes: list[Point] = [start] + waypoints
    goal_index = None
    for i, p in enumerate(nodes):
        if math.dist(p, goal) < 1e-6:
            goal_index = i
            break
    if goal_index is None:
        nodes.append(goal)
        goal_index = len(nodes) - 1

    n = len(nodes)
    adj: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            a, b = nodes[i], nodes[j]
            toward_goal = i == goal_index or j == goal_index
            other = a if j == goal_index else b
            # Only short final hops to the goal may enter the clearance ring.
            # Long start→goal chords must stay outside hard clearance.
            final_approach = (
                toward_goal
                and math.dist(other, goal) <= max(ctx.clearance_m + 1.5, 3.0)
            )
            if not _chord_ok(
                a, b, space, obstacles, body_radius, ctx, floor_id,
                allow_clearance_near_goal=final_approach,
            ):
                continue
            cost = _edge_cost(a, b, space, body_radius, ctx)
            adj[i].append((j, cost))
            adj[j].append((i, cost))

    dist = [float("inf")] * n
    prev = [-1] * n
    dist[0] = 0.0
    heap = [(0.0, 0)]
    while heap:
        cost, i = heapq.heappop(heap)
        if cost > dist[i]:
            continue
        if i == goal_index:
            break
        for j, w in adj[i]:
            nxt = cost + w
            if nxt < dist[j]:
                dist[j] = nxt
                prev[j] = i
                heapq.heappush(heap, (nxt, j))

    if dist[goal_index] == float("inf"):
        # #region agent log
        try:
            import json, time
            n_edges = sum(len(a) for a in adj)
            with open("/Users/jackschultz/PycharmProjects/evacuation-simulation/.cursor/debug-a376ca.log", "a") as _f:
                _f.write(json.dumps({
                    "sessionId": "a376ca",
                    "hypothesisId": "E",
                    "location": "hazard_local_path.py:plan_local_path",
                    "message": "skirt graph unreachable",
                    "data": {
                        "n_nodes": n,
                        "n_edges": n_edges,
                        "direct_clear": direct_clear,
                        "n_skirt_fire": len(_fire_skirt_points(
                            ctx, floor_id, space, body_radius,
                            from_point=start, to_point=goal,
                        )),
                        "hard_extra": ctx.hard_fire_radius_extra,
                    },
                    "timestamp": int(time.time() * 1000),
                }) + "\n")
        except Exception:
            pass
        # #endregion
        return LocalPathResult(first_hop=None, reachable=False, direct=False, hops=())

    cur = goal_index
    path = [cur]
    while prev[cur] != -1:
        cur = prev[cur]
        path.append(cur)
    path.reverse()
    if len(path) < 2:
        return LocalPathResult(first_hop=goal, reachable=True, direct=True, hops=(goal,))

    hop_points = tuple(nodes[i] for i in path[1:])
    first = hop_points[0]
    is_direct = direct_clear and len(path) == 2 and math.dist(first, goal) < 1e-6
    # #region agent log
    if not is_direct:
        try:
            import json, time
            with open("/Users/jackschultz/PycharmProjects/evacuation-simulation/.cursor/debug-a376ca.log", "a") as _f:
                _f.write(json.dumps({
                    "sessionId": "a376ca",
                    "hypothesisId": "E-fix",
                    "location": "hazard_local_path.py:plan_local_path",
                    "message": "skirt path found",
                    "data": {
                        "path_len": len(path),
                        "first_hop": [round(first[0], 2), round(first[1], 2)],
                        "direct_clear": direct_clear,
                        "hops": [[round(p[0], 2), round(p[1], 2)] for p in hop_points[:6]],
                    },
                    "timestamp": int(time.time() * 1000),
                }) + "\n")
        except Exception:
            pass
    # #endregion
    return LocalPathResult(
        first_hop=first, reachable=True, direct=is_direct, hops=hop_points,
    )


def room_graph_waypoints(
    graph,
    space_id: str,
    goal_id: str | None = None,
) -> list[Point]:
    """Existing reflex / obstacle waypoints in a space for local planning."""
    points: list[Point] = []
    for node in graph.nodes.values():
        if node.ref_id != space_id:
            continue
        if goal_id is not None and node.id == goal_id:
            continue
        if node.kind == NodeKind.WAYPOINT and not node.id.startswith("spawn:"):
            points.append((node.x, node.y))
    return points


def local_path_to_node(
    occupant_xy: Point,
    goal_node,
    space: Space,
    floor_id: str,
    graph,
    ctx: HazardRoutingContext,
    body_radius: float,
) -> LocalPathResult:
    obstacles = [o for o in graph.obstacles if o.floor_id == floor_id]
    extras = room_graph_waypoints(graph, space.id, goal_id=goal_node.id)
    return plan_local_path(
        occupant_xy,
        (goal_node.x, goal_node.y),
        space,
        floor_id,
        obstacles,
        ctx,
        body_radius,
        extra_waypoints=extras,
    )


def segment_needs_hazard_detour(
    a: Point,
    b: Point,
    space: Space,
    floor_id: str,
    obstacles: list[Obstacle],
    ctx: HazardRoutingContext,
    body_radius: float,
) -> bool:
    """True when the walk chord is fire-blocked or soft-hazardous enough to skirt."""
    if fire_disk_blocks_segment(ctx, floor_id, a[0], a[1], b[0], b[1]):
        return True
    if not clear_segment(a, b, obstacles, body_radius):
        return True
    soft = soft_hazard_speed_along_segment(ctx, space.id, a[0], a[1], b[0], b[1])
    return soft < 0.95
