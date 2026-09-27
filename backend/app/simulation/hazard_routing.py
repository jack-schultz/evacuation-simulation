"""Hazard-aware edge costing for macro (door/stair/exit) routing."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.building import BuildingLayout, SimulationParameters
from app.simulation.flood import active_flood_plumes, flood_soft_speed_factor
from app.simulation.graph import GraphEdge, GraphNode, NavigationGraph, NodeKind
from app.simulation.hazards import (
    active_fire_plumes,
    active_smoke_plumes,
    fire_touches,
    smoke_factor_at,
)


@dataclass(frozen=True)
class HazardRoutingContext:
    """Plumes + clearance knobs for one routing query at time ``t``."""

    layout: BuildingLayout
    t: float
    fire_plumes: list
    smoke_plumes: list
    flood_plumes: list
    clearance_m: float = 2.5
    soft_clearance_m: float = 1.0
    body_radius_m: float = 0.25

    @classmethod
    def at(
        cls,
        layout: BuildingLayout,
        t: float,
        params: SimulationParameters | None = None,
        *,
        body_radius_m: float | None = None,
    ) -> HazardRoutingContext:
        clearance = 2.5
        soft = 1.0
        radius = body_radius_m if body_radius_m is not None else 0.25
        if params is not None:
            clearance = params.hazard_clearance_m
            soft = params.hazard_soft_clearance_m
            radius = params.occupant_radius_m
        return cls(
            layout=layout,
            t=max(t, 0.0),
            fire_plumes=active_fire_plumes(layout, t),
            smoke_plumes=active_smoke_plumes(layout, t),
            flood_plumes=active_flood_plumes(layout, t),
            clearance_m=clearance,
            soft_clearance_m=soft,
            body_radius_m=radius,
        )

    @property
    def hard_fire_radius_extra(self) -> float:
        return self.clearance_m + self.body_radius_m


def point_in_disk(x: float, y: float, cx: float, cy: float, radius: float) -> bool:
    if radius < 0:
        return False
    dx, dy = x - cx, y - cy
    return dx * dx + dy * dy <= radius * radius + 1e-9


def segment_hits_disk(
    ax: float, ay: float, bx: float, by: float, cx: float, cy: float, radius: float
) -> bool:
    """True when segment A→B comes within ``radius`` of (cx, cy)."""
    if radius < 0:
        return False
    if point_in_disk(ax, ay, cx, cy, radius) or point_in_disk(bx, by, cx, cy, radius):
        return True
    dx, dy = bx - ax, by - ay
    len2 = dx * dx + dy * dy
    if len2 < 1e-18:
        return False
    t = ((cx - ax) * dx + (cy - ay) * dy) / len2
    t = max(0.0, min(1.0, t))
    px, py = ax + t * dx, ay + t * dy
    return point_in_disk(px, py, cx, cy, radius)


def opening_in_fire(
    ctx: HazardRoutingContext, floor_id: str, x: float, y: float
) -> bool:
    """Exit/door is unusable when the lethal fire plume covers it (no skirt buffer)."""
    return fire_touches(ctx.fire_plumes, floor_id, x, y, ctx.body_radius_m)


def fire_disk_blocks_point(ctx: HazardRoutingContext, floor_id: str, x: float, y: float) -> bool:
    """Hard skirt disk — used for in-room local pathing clearance."""
    extra = ctx.hard_fire_radius_extra
    for plume in ctx.fire_plumes:
        if plume.floor_id != floor_id:
            continue
        if point_in_disk(x, y, plume.x, plume.y, plume.radius_m + extra):
            return True
    return False


def fire_disk_blocks_segment(
    ctx: HazardRoutingContext,
    floor_id: str,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> bool:
    """True when segment A→B comes within hard skirt clearance of fire."""
    extra = ctx.hard_fire_radius_extra
    for plume in ctx.fire_plumes:
        if plume.floor_id != floor_id:
            continue
        if segment_hits_disk(ax, ay, bx, by, plume.x, plume.y, plume.radius_m + extra):
            return True
    return False


def lethal_segment_hits_fire(
    ctx: HazardRoutingContext,
    floor_id: str,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> bool:
    """Macro corridor blocked when the chord intersects the lethal plume."""
    for plume in ctx.fire_plumes:
        if plume.floor_id != floor_id:
            continue
        if segment_hits_disk(
            ax, ay, bx, by, plume.x, plume.y, plume.radius_m + ctx.body_radius_m
        ):
            return True
    return False


def opening_floor_id(graph: NavigationGraph, layout: BuildingLayout, node: GraphNode) -> str:
    if node.kind == NodeKind.EXIT:
        exit_obj = next((e for e in layout.exits if e.id == node.ref_id), None)
        if exit_obj is not None:
            space = next((s for s in layout.spaces if s.id == exit_obj.connected_space_id), None)
            if space is not None:
                return space.floor_id
            return exit_obj.floor_id
    if node.kind == NodeKind.DOOR:
        door = next((d for d in layout.doors if d.id == node.ref_id), None)
        if door is not None and door.connects:
            space = next((s for s in layout.spaces if s.id == door.connects[0]), None)
            if space is not None:
                return space.floor_id
            return door.floor_id
    if node.kind == NodeKind.SPACE:
        return graph.space_floor_ids.get(node.ref_id, "floor-0")
    if node.kind == NodeKind.WAYPOINT:
        return graph.space_floor_ids.get(node.ref_id, "floor-0")
    return "floor-0"


def node_blocked_by_fire(
    graph: NavigationGraph,
    layout: BuildingLayout,
    ctx: HazardRoutingContext,
    node_id: str,
) -> bool:
    """True when a door/exit/stair portal is covered by the lethal fire plume."""
    node = graph.nodes.get(node_id)
    if node is None:
        return True
    if node.kind == NodeKind.SPACE and node_id not in graph.stair_space_node_ids:
        return False
    if node.kind == NodeKind.WAYPOINT:
        return False
    floor_id = opening_floor_id(graph, layout, node)
    return opening_in_fire(ctx, floor_id, node.x, node.y)


def soft_hazard_speed_along_segment(
    ctx: HazardRoutingContext,
    space_id: str | None,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    """Minimum soft speed factor sampled along a chord (flood + smoke)."""
    if not ctx.flood_plumes and not ctx.smoke_plumes:
        return 1.0
    factor = 1.0
    samples = (0.0, 0.25, 0.5, 0.75, 1.0)
    for s in samples:
        x = ax + (bx - ax) * s
        y = ay + (by - ay) * s
        factor = min(
            factor,
            flood_soft_speed_factor(ctx.flood_plumes, space_id, x, y),
            smoke_factor_at(ctx.smoke_plumes, space_id, x, y),
        )
    # Soft clearance: penalize chords that skim near wet/smoky cores.
    soft_r = ctx.soft_clearance_m
    if soft_r > 0 and space_id:
        for plume in ctx.flood_plumes:
            if plume.space_id != space_id:
                continue
            if segment_hits_disk(ax, ay, bx, by, plume.x, plume.y, plume.radius_m + soft_r):
                factor = min(factor, max(0.15, 1.0 - plume.intensity / 100.0) * 0.85)
        for plume in ctx.smoke_plumes:
            if plume.space_id != space_id:
                continue
            if segment_hits_disk(ax, ay, bx, by, plume.x, plume.y, plume.radius_m + soft_r):
                factor = min(factor, max(0.25, 1.0 - plume.intensity / 100.0) * 0.9)
    return max(factor, 0.05)


def edge_space_id(graph: NavigationGraph, edge: GraphEdge) -> str | None:
    """Best-effort space id for soft room-scoped hazard queries on an edge."""
    for nid in (edge.from_id, edge.to_id):
        node = graph.nodes.get(nid)
        if node is None:
            continue
        if node.kind == NodeKind.SPACE and nid not in graph.stair_space_node_ids:
            return node.ref_id
        if node.kind == NodeKind.WAYPOINT:
            return node.ref_id
    parts = edge.id.split(":")
    if len(parts) >= 3:
        maybe = parts[-1]
        if maybe in graph.spaces or maybe in graph.space_node_ids:
            return maybe
    return None


def edge_traversal_cost(
    graph: NavigationGraph,
    layout: BuildingLayout,
    edge: GraphEdge,
    ctx: HazardRoutingContext,
    *,
    speed_mps: float = 1.0,
) -> float | None:
    """Predicted traversal time for an edge, or None if fire-blocked."""
    if edge.distance_m <= 0 and edge.from_id == edge.to_id:
        return None
    if edge.speed_factor <= 0:
        return None
    frm = graph.nodes[edge.from_id]
    to = graph.nodes[edge.to_id]
    floor_from = opening_floor_id(graph, layout, frm)
    floor_to = opening_floor_id(graph, layout, to)

    def _is_portal(node: GraphNode, node_id: str) -> bool:
        if node.kind in (NodeKind.DOOR, NodeKind.EXIT):
            return True
        return node.kind == NodeKind.SPACE and node_id in graph.stair_space_node_ids

    if _is_portal(frm, edge.from_id) and opening_in_fire(ctx, floor_from, frm.x, frm.y):
        return None
    if _is_portal(to, edge.to_id) and opening_in_fire(ctx, floor_to, to.x, to.y):
        return None

    # Opening↔opening (and stair) chords: lethal plume intersection blocks.
    both_portals = _is_portal(frm, edge.from_id) and _is_portal(to, edge.to_id)
    both_waypoints = (
        frm.kind == NodeKind.WAYPOINT and to.kind == NodeKind.WAYPOINT
    )
    if (both_portals or both_waypoints or frm.kind == NodeKind.WAYPOINT or to.kind == NodeKind.WAYPOINT) and floor_from == floor_to:
        if lethal_segment_hits_fire(ctx, floor_from, frm.x, frm.y, to.x, to.y):
            return None

    space_id = edge_space_id(graph, edge)
    soft = soft_hazard_speed_along_segment(
        ctx, space_id, frm.x, frm.y, to.x, to.y
    )
    effective_speed = max(speed_mps * edge.speed_factor * soft, 1e-6)
    distance = edge.distance_m + edge.route_penalty_m
    return distance / effective_speed


def forbidden_fire_node_ids(
    graph: NavigationGraph,
    layout: BuildingLayout,
    ctx: HazardRoutingContext,
) -> frozenset[str]:
    blocked: set[str] = set()
    for node_id, node in graph.nodes.items():
        if node.kind not in (NodeKind.DOOR, NodeKind.EXIT) and not (
            node.kind == NodeKind.SPACE and node_id in graph.stair_space_node_ids
        ):
            continue
        if node_blocked_by_fire(graph, layout, ctx, node_id):
            blocked.add(node_id)
    return frozenset(blocked)


def macro_leg_fire_blocked(
    graph: NavigationGraph,
    layout: BuildingLayout,
    ctx: HazardRoutingContext,
    from_id: str,
    to_id: str,
) -> bool:
    """True when the current macro hop is unusable due to fire."""
    if node_blocked_by_fire(graph, layout, ctx, to_id):
        return True
    if node_blocked_by_fire(graph, layout, ctx, from_id):
        return True
    from app.simulation.routing import edge_between

    edge = edge_between(graph, from_id, to_id)
    if edge is None:
        # No direct edge — still blocked if segment on shared floor hits fire.
        frm, to = graph.nodes[from_id], graph.nodes[to_id]
        floor = opening_floor_id(graph, layout, to)
        return fire_disk_blocks_segment(ctx, floor, frm.x, frm.y, to.x, to.y)
    return edge_traversal_cost(graph, layout, edge, ctx) is None


def remaining_route_fire_blocked(
    graph: NavigationGraph,
    layout: BuildingLayout,
    ctx: HazardRoutingContext,
    route: list[str],
    route_index: int,
) -> bool:
    """True when any upcoming macro hop on the route is fire-blocked at ``ctx.t``."""
    if route_index >= len(route) - 1:
        return False
    for a, b in zip(route[route_index:], route[route_index + 1 :]):
        if macro_leg_fire_blocked(graph, layout, ctx, a, b):
            return True
    return False


def lethal_fire_contact(
    ctx: HazardRoutingContext, floor_id: str, x: float, y: float
) -> bool:
    """Contact with the raw fire plume (no clearance) — matches casualty rules."""
    return fire_touches(ctx.fire_plumes, floor_id, x, y, ctx.body_radius_m)
