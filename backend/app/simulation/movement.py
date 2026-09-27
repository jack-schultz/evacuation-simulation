"""Occupant movement: continuous steer toward route waypoints with aperture targeting."""

from __future__ import annotations

from dataclasses import dataclass, field
import heapq
from typing import Protocol

from app.domain.building import Door, OccupantStatus
from app.simulation.collision import (
    dist,
    door_other_space,
)
from app.simulation.graph import EdgeKind, GraphNode, NavigationGraph, NodeKind
from app.simulation.routing import edge_between


@dataclass
class SimulatedOccupant:
    id: str
    group_id: str
    speed_mps: float
    route: list[str]
    current_space_id: str = ""
    route_index: int = 0
    progress_on_edge: float = 0.0  # metres travelled toward current waypoint (approx)
    x: float = 0.0
    y: float = 0.0
    status: OccupantStatus = OccupantStatus.ACTIVE
    deceased: bool = False
    distance_m: float = 0.0
    travel_time_s: float = 0.0
    wait_time_s: float = 0.0
    evacuated_at: float | None = None
    aperture_slot: int = 0
    floor_id: str = "floor-0"
    climb_progress: float | None = None
    climb_from_space_id: str | None = None
    climb_to_space_id: str | None = None
    # Full-intensity-equivalent seconds spent in flood water (dose).
    flood_exposure_s: float = 0.0
    # When True, body is following a hazard skirt — do not snap onto the direct chord.
    hazard_detour: bool = False
    # Preferred exit id from the spawning group (for mid-run replan fallback).
    preferred_exit_id: str | None = None
    # Debug / playback: remaining steer polyline (local skirt + openings).
    path_preview: list[tuple[float, float]] = field(default_factory=list)

    @property
    def current_node_id(self) -> str:
        return self.route[self.route_index]

    @property
    def next_node_id(self) -> str | None:
        if self.route_index + 1 < len(self.route):
            return self.route[self.route_index + 1]
        return None

    @property
    def finished_route(self) -> bool:
        return self.route_index >= len(self.route) - 1


def interpolate_position(a: GraphNode, b: GraphNode, progress_m: float, edge_length: float) -> tuple[float, float]:
    if edge_length <= 1e-9:
        return b.x, b.y
    t = min(max(progress_m / edge_length, 0.0), 1.0)
    return a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t


def is_walk_anchor(node: GraphNode, graph: NavigationGraph) -> bool:
    """True if node is a walk polyline vertex (not a room-centroid bookkeeping node)."""
    if node.kind == NodeKind.SPACE:
        return node.id in graph.stair_space_node_ids
    return True


def project_onto_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> tuple[float, float]:
    """Clamp (px, py) onto the segment A→B."""
    dx = bx - ax
    dy = by - ay
    len2 = dx * dx + dy * dy
    if len2 < 1e-18:
        return ax, ay
    t = ((px - ax) * dx + (py - ay) * dy) / len2
    t = max(0.0, min(1.0, t))
    return ax + t * dx, ay + t * dy


def project_onto_route_segment(
    occupant: SimulatedOccupant, graph: NavigationGraph
) -> None:
    """Snap occupant onto current→next walk segment when the current node is a walk anchor."""
    nxt = occupant.next_node_id
    if nxt is None:
        return
    cur = graph.nodes.get(occupant.current_node_id)
    waypoint = graph.nodes.get(nxt)
    if cur is None or waypoint is None:
        return
    if not is_walk_anchor(cur, graph):
        return
    # Stair↔stair transfer positions are driven by climb centreline, not this chord.
    if (
        cur.kind == NodeKind.SPACE
        and waypoint.kind == NodeKind.SPACE
        and cur.id in graph.stair_space_node_ids
        and waypoint.id in graph.stair_space_node_ids
    ):
        return
    occupant.x, occupant.y = project_onto_segment(
        occupant.x, occupant.y, cur.x, cur.y, waypoint.x, waypoint.y
    )


def enforce_walk_segment(
    occupant: SimulatedOccupant,
    graph: NavigationGraph,
    *,
    admitted: bool,
    radius_m: float,
) -> None:
    """Keep the body on the walk chord; hold non-admitted agents outside the throat on-line."""
    from app.simulation.collision import in_throat, throat_radius

    if occupant.hazard_detour:
        return
    project_onto_route_segment(occupant, graph)
    if admitted:
        return
    nxt = occupant.next_node_id
    if nxt is None:
        return
    cur = graph.nodes.get(occupant.current_node_id)
    waypoint = graph.nodes.get(nxt)
    if cur is None or waypoint is None:
        return
    if not is_walk_anchor(cur, graph):
        return
    if waypoint.kind not in (NodeKind.DOOR, NodeKind.EXIT):
        return
    if not in_throat(occupant.x, occupant.y, waypoint.x, waypoint.y, radius_m):
        return
    tr = throat_radius(radius_m)
    dx = cur.x - waypoint.x
    dy = cur.y - waypoint.y
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-9:
        return
    occupant.x = waypoint.x + dx / length * tr
    occupant.y = waypoint.y + dy / length * tr


def _next_waypoint_on_space_side(
    graph: NavigationGraph,
    waypoint: GraphNode,
    space_id: str,
    other_space_id: str,
) -> bool:
    """True if waypoint is closer to space_id's node than to other_space_id's."""
    cur_nid = graph.space_node_ids.get(space_id)
    oth_nid = graph.space_node_ids.get(other_space_id)
    if cur_nid is None or oth_nid is None:
        return True
    cur_n = graph.nodes[cur_nid]
    oth_n = graph.nodes[oth_nid]
    d_cur = dist(waypoint.x, waypoint.y, cur_n.x, cur_n.y)
    d_oth = dist(waypoint.x, waypoint.y, oth_n.x, oth_n.y)
    return d_cur <= d_oth + 1e-9


class MovementModel(Protocol):
    """Protocol for spatial (or legacy) movement implementations."""

    def propose_target(
        self,
        occupant: SimulatedOccupant,
        graph: NavigationGraph,
        radius_m: float,
        admitted: bool,
        doors: dict[str, Door] | None = None,
        *,
        hazard_ctx=None,
    ) -> tuple[float, float]:
        """Return the (x, y) steering target for this timestep."""
        ...

    def step_toward(
        self,
        occupant: SimulatedOccupant,
        target_x: float,
        target_y: float,
        max_distance: float,
    ) -> float:
        """Move occupant toward target up to max_distance. Returns metres moved."""
        ...

    def try_advance_route(
        self,
        occupant: SimulatedOccupant,
        graph: NavigationGraph,
        radius_m: float,
        t: float,
        *,
        admitted: bool = True,
        doors: dict[str, Door] | None = None,
    ) -> None:
        """Advance route index / evacuate when close enough to the next waypoint."""
        ...


@dataclass
class SpatialMovementModel:
    """Continuous steering along walk-route segments with door aperture admission."""

    approach_distance_m: float = 2.0

    def _through_door_target(
        self,
        occupant: SimulatedOccupant,
        graph: NavigationGraph,
        door_node: GraphNode,
        waypoint: GraphNode,
        radius_m: float,
        doors: dict[str, Door],
    ) -> tuple[float, float] | None:
        """Aim through the door center toward the next walk waypoint while origin-side."""
        door = doors.get(door_node.ref_id)
        if door is None or not occupant.current_space_id:
            return None
        other = door_other_space(door, occupant.current_space_id)
        if other is None:
            return None
        # Already on the destination side of membership — use normal waypoint aiming.
        if _next_waypoint_on_space_side(
            graph, waypoint, occupant.current_space_id, other
        ):
            return None

        dx = waypoint.x - door_node.x
        dy = waypoint.y - door_node.y
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1e-9:
            return door_node.x, door_node.y
        offset = max(radius_m * 1.5, 0.4)
        return door_node.x + dx / length * offset, door_node.y + dy / length * offset

    def _rejoin_target(
        self,
        occupant: SimulatedOccupant,
        graph: NavigationGraph,
        target: GraphNode,
        radius_m: float,
    ) -> tuple[float, float] | None:
        """Rejoin a fixed route leg from a position displaced by crowd movement."""
        from app.simulation.obstacles import visible, wall_clearance_cost

        space = graph.spaces.get(occupant.current_space_id)
        if space is None:
            return None
        obstacles = [o for o in graph.obstacles if o.floor_id == occupant.floor_id]
        start = (occupant.x, occupant.y)
        goal = (target.x, target.y)
        if visible(start, goal, space, obstacles, radius_m):
            return None

        candidates = {
            n.id: n for n in graph.nodes.values()
            if n.id == target.id or (
                n.ref_id == space.id
                and (n.kind == NodeKind.WAYPOINT or n.id == graph.space_node_ids.get(space.id))
                and not n.id.startswith("spawn:")
            )
        }
        if target.id not in candidates:
            return None

        heap: list[tuple[float, str, str]] = []
        for node in candidates.values():
            point = (node.x, node.y)
            if dist(*start, *point) < 0.05 or not visible(
                start, point, space, obstacles, radius_m
            ):
                continue
            cost = dist(*start, *point) + wall_clearance_cost(
                start, point, space, radius_m
            )
            heapq.heappush(heap, (cost, node.id, node.id))
        best: dict[str, float] = {}
        while heap:
            cost, node_id, first_id = heapq.heappop(heap)
            if cost >= best.get(node_id, float("inf")):
                continue
            best[node_id] = cost
            if node_id == target.id:
                first = candidates[first_id]
                return first.x, first.y
            for edge_id in graph.adjacency.get(node_id, []):
                edge = graph.edges[edge_id]
                if edge.to_id not in candidates or edge.speed_factor <= 0:
                    continue
                next_cost = cost + (
                    edge.distance_m + edge.route_penalty_m
                ) / edge.speed_factor
                if next_cost < best.get(edge.to_id, float("inf")):
                    heapq.heappush(heap, (next_cost, edge.to_id, first_id))
        return None

    def propose_target(
        self,
        occupant: SimulatedOccupant,
        graph: NavigationGraph,
        radius_m: float,
        admitted: bool,
        doors: dict[str, Door] | None = None,
        *,
        hazard_ctx=None,
    ) -> tuple[float, float]:
        occupant.hazard_detour = False
        nxt = occupant.next_node_id
        if nxt is None:
            node = graph.nodes[occupant.current_node_id]
            return node.x, node.y

        waypoint = graph.nodes[nxt]
        cur = graph.nodes[occupant.current_node_id]

        if cur.kind == NodeKind.DOOR and doors is not None:
            through = self._through_door_target(
                occupant, graph, cur, waypoint, radius_m, doors
            )
            if through is not None:
                return through
            # Already on the destination side of this door — leave toward the
            # next route waypoint (do not re-apply aperture approach geometry).
            return waypoint.x, waypoint.y

        # Hazard skirting inside the current room toward the next macro node.
        if (
            hazard_ctx is not None
            and (
                hazard_ctx.fire_plumes
                or hazard_ctx.flood_plumes
                or hazard_ctx.smoke_plumes
            )
            and occupant.current_space_id
            and waypoint.kind in (
                NodeKind.WAYPOINT, NodeKind.DOOR, NodeKind.EXIT, NodeKind.SPACE,
            )
        ):
            space = graph.spaces.get(occupant.current_space_id)
            if space is not None:
                from app.simulation.hazard_local_path import local_path_to_node

                local = local_path_to_node(
                    (occupant.x, occupant.y),
                    waypoint,
                    space,
                    occupant.floor_id,
                    graph,
                    hazard_ctx,
                    radius_m,
                )
                if local.reachable and local.hops:
                    # Preview: skirt hops then remaining macro openings on this floor.
                    preview = list(local.hops)
                    for nid in occupant.route[occupant.route_index + 2 :]:
                        n = graph.nodes.get(nid)
                        if n is None:
                            continue
                        if n.kind.value == "space" and nid not in graph.stair_space_node_ids:
                            continue
                        preview.append((n.x, n.y))
                    occupant.path_preview = preview
                # #region agent log
                if occupant.id.endswith(":0") and int(getattr(occupant, "_dbg_skirt_n", 0)) < 8:
                    occupant._dbg_skirt_n = int(getattr(occupant, "_dbg_skirt_n", 0)) + 1  # type: ignore[attr-defined]
                    try:
                        import json, time
                        with open("/Users/jackschultz/PycharmProjects/evacuation-simulation/.cursor/debug-a376ca.log", "a") as _f:
                            _f.write(json.dumps({
                                "sessionId": "a376ca",
                                "hypothesisId": "A,B,C,F",
                                "location": "movement.py:propose_target",
                                "message": "local skirt decision",
                                "data": {
                                    "occ": occupant.id,
                                    "xy": [round(occupant.x, 2), round(occupant.y, 2)],
                                    "goal": [round(waypoint.x, 2), round(waypoint.y, 2)],
                                    "goal_kind": waypoint.kind.value,
                                    "floor": occupant.floor_id,
                                    "space": occupant.current_space_id,
                                    "n_fire": len(hazard_ctx.fire_plumes),
                                    "fire0": (
                                        {
                                            "floor": hazard_ctx.fire_plumes[0].floor_id,
                                            "xy": [hazard_ctx.fire_plumes[0].x, hazard_ctx.fire_plumes[0].y],
                                            "r": hazard_ctx.fire_plumes[0].radius_m,
                                        }
                                        if hazard_ctx.fire_plumes else None
                                    ),
                                    "reachable": local.reachable,
                                    "direct": local.direct,
                                    "hop": (
                                        [round(local.first_hop[0], 2), round(local.first_hop[1], 2)]
                                        if local.first_hop else None
                                    ),
                                    "n_hops": len(local.hops),
                                    "clearance": hazard_ctx.hard_fire_radius_extra,
                                },
                                "timestamp": int(time.time() * 1000),
                            }) + "\n")
                    except Exception:
                        pass
                # #endregion
                if local.reachable and local.first_hop is not None and not local.direct:
                    occupant.hazard_detour = True
                    return local.first_hop
                # Skirt graph failed but the direct chord crosses fire — do not
                # walk into the plume; step toward the nearest clear skirt point.
                if (
                    not local.reachable
                    and hazard_ctx.fire_plumes
                    and space is not None
                ):
                    from app.simulation.hazard_local_path import _fire_skirt_points
                    from app.simulation.hazard_routing import fire_disk_blocks_segment

                    if fire_disk_blocks_segment(
                        hazard_ctx,
                        occupant.floor_id,
                        occupant.x,
                        occupant.y,
                        waypoint.x,
                        waypoint.y,
                    ):
                        skirts = _fire_skirt_points(
                            hazard_ctx,
                            occupant.floor_id,
                            space,
                            radius_m,
                            from_point=(occupant.x, occupant.y),
                            to_point=(waypoint.x, waypoint.y),
                        )
                        best = None
                        best_d = float("inf")
                        for sx, sy in skirts:
                            if fire_disk_blocks_segment(
                                hazard_ctx, occupant.floor_id,
                                occupant.x, occupant.y, sx, sy,
                            ):
                                continue
                            d = dist(occupant.x, occupant.y, sx, sy)
                            if d < best_d:
                                best_d = d
                                best = (sx, sy)
                        if best is not None:
                            # #region agent log
                            try:
                                import json, time
                                with open("/Users/jackschultz/PycharmProjects/evacuation-simulation/.cursor/debug-a376ca.log", "a") as _f:
                                    _f.write(json.dumps({
                                        "sessionId": "a376ca",
                                        "hypothesisId": "E-fix",
                                        "location": "movement.py:propose_target",
                                        "message": "fallback skirt hop",
                                        "data": {
                                            "occ": occupant.id,
                                            "hop": [round(best[0], 2), round(best[1], 2)],
                                        },
                                        "timestamp": int(time.time() * 1000),
                                    }) + "\n")
                            except Exception:
                                pass
                            # #endregion
                            occupant.hazard_detour = True
                            return best

        if graph.obstacles and waypoint.kind in (
            NodeKind.WAYPOINT, NodeKind.DOOR, NodeKind.EXIT,
        ):
            detour = self._rejoin_target(occupant, graph, waypoint, radius_m)
            if detour is not None:
                occupant.hazard_detour = True
                return detour

        edge = edge_between(graph, occupant.current_node_id, nxt)
        if edge is None:
            return waypoint.x, waypoint.y

        # Stair teleport portal: stay at / walk to current stair center
        if (
            cur.kind == NodeKind.SPACE
            and waypoint.kind == NodeKind.SPACE
            and cur.id in graph.stair_space_node_ids
            and waypoint.id in graph.stair_space_node_ids
        ):
            return cur.x, cur.y

        if edge.kind not in (EdgeKind.DOOR, EdgeKind.EXIT, EdgeKind.STAIRS):
            return waypoint.x, waypoint.y

        # Next waypoint is an opening — approach / hold on centerline (admission gates throat).
        d_to_door = dist(occupant.x, occupant.y, waypoint.x, waypoint.y)
        if d_to_door > self.approach_distance_m:
            return waypoint.x, waypoint.y

        if admitted:
            return waypoint.x, waypoint.y

        # Not admitted: hold at the throat boundary on the approach centerline.
        from app.simulation.collision import throat_radius

        tr = throat_radius(radius_m)
        adx = cur.x - waypoint.x
        ady = cur.y - waypoint.y
        al = (adx * adx + ady * ady) ** 0.5
        if al < 1e-9:
            dx = occupant.x - waypoint.x
            dy = occupant.y - waypoint.y
            d = (dx * dx + dy * dy) ** 0.5
            if d < 1e-9:
                return waypoint.x + tr, waypoint.y
            return waypoint.x + dx / d * tr, waypoint.y + dy / d * tr
        return waypoint.x + adx / al * tr, waypoint.y + ady / al * tr

    def step_toward(
        self,
        occupant: SimulatedOccupant,
        target_x: float,
        target_y: float,
        max_distance: float,
    ) -> float:
        if max_distance <= 0:
            return 0.0
        dx = target_x - occupant.x
        dy = target_y - occupant.y
        d = (dx * dx + dy * dy) ** 0.5
        if d < 1e-9:
            return 0.0
        step = min(max_distance, d)
        occupant.x += dx / d * step
        occupant.y += dy / d * step
        occupant.progress_on_edge += step
        return step

    def try_advance_route(
        self,
        occupant: SimulatedOccupant,
        graph: NavigationGraph,
        radius_m: float,
        t: float,
        *,
        admitted: bool = True,
        doors: dict[str, Door] | None = None,
    ) -> None:
        if occupant.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED):
            return

        nxt = occupant.next_node_id
        if nxt is None:
            node = graph.nodes[occupant.current_node_id]
            if node.kind == NodeKind.EXIT:
                occupant.status = OccupantStatus.EVACUATED
                if occupant.evacuated_at is None:
                    occupant.evacuated_at = t
            return

        waypoint = graph.nodes[nxt]
        edge = edge_between(graph, occupant.current_node_id, nxt)

        # Cannot claim an opening waypoint without an aperture slot
        if (
            not admitted
            and edge is not None
            and edge.kind in (EdgeKind.DOOR, EdgeKind.EXIT, EdgeKind.STAIRS)
            and waypoint.kind in (NodeKind.DOOR, NodeKind.EXIT)
        ):
            return

        from_node = graph.nodes[occupant.current_node_id]
        # Leaving a door requires physical membership on the destination side.
        if from_node.kind == NodeKind.DOOR and doors is not None:
            door = doors.get(from_node.ref_id)
            if door is not None and occupant.current_space_id:
                other = door_other_space(door, occupant.current_space_id)
                if other is not None and not _next_waypoint_on_space_side(
                    graph, waypoint, occupant.current_space_id, other
                ):
                    return

        reach = max(radius_m * 1.2, 0.35)
        stair_transfer = (
            from_node.kind == NodeKind.SPACE
            and waypoint.kind == NodeKind.SPACE
            and from_node.id in graph.stair_space_node_ids
            and waypoint.id in graph.stair_space_node_ids
            and edge is not None
        )

        if not admitted and stair_transfer:
            return

        if stair_transfer:
            reached = dist(occupant.x, occupant.y, from_node.x, from_node.y) <= reach
        else:
            d_wp = dist(occupant.x, occupant.y, waypoint.x, waypoint.y)
            reached = d_wp <= reach

        if reached and ":obstacle:" in waypoint.id and occupant.route_index + 2 < len(occupant.route):
            from app.simulation.obstacles import clear_segment
            following = graph.nodes[occupant.route[occupant.route_index + 2]]
            obstacles = [o for o in graph.obstacles if o.floor_id == occupant.floor_id]
            if not clear_segment((occupant.x, occupant.y), (following.x, following.y), obstacles, radius_m):
                reached = False

        if not reached:
            return

        if stair_transfer:
            # Begin directed climb along the stair centreline (completed in step.py).
            occupant.status = OccupantStatus.CLIMBING
            occupant.climb_progress = 0.0
            occupant.climb_from_space_id = from_node.ref_id
            occupant.climb_to_space_id = waypoint.ref_id
            return

        occupant.route_index += 1
        occupant.progress_on_edge = 0.0

        if waypoint.kind == NodeKind.EXIT or occupant.next_node_id is None:
            occupant.status = OccupantStatus.EVACUATED
            if occupant.evacuated_at is None:
                occupant.evacuated_at = t
            occupant.x, occupant.y = waypoint.x, waypoint.y
