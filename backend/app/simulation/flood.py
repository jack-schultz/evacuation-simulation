"""Room-scoped flood spread through same-floor doors."""

from __future__ import annotations

import heapq
import math

from app.domain.building import (
    BuildingLayout,
    DEFAULT_FLOOR_ID,
    FloodRoomState,
    OccupantStatus,
)
from app.domain.geometry import point_in_polygon
from app.simulation.graph import NavigationGraph, NodeKind
from app.simulation.hazards import (
    HazardRouteSelector as FloodRouteSelector,
    apply_hazards,
    hazard_radius_at as flood_radius_at,
    segment_speed_factor,
)

# Full-intensity-equivalent seconds in water before casualty (trapped).
# At intensity 50 this is ~20s; at intensity 100 it is 10s.
FLOOD_LETHAL_EXPOSURE_S = 10.0


def active_flood_plumes(layout: BuildingLayout, t: float) -> list[FloodRoomState]:
    """Expand in the origin room; restart at each doorway into the next room."""
    flood = layout.flood
    if flood is None or not flood.enabled or flood.intensity == 0:
        return []

    floor_id = flood.floor_id or DEFAULT_FLOOR_ID
    spaces = {
        s.id: s
        for s in layout.spaces
        if (s.floor_id or DEFAULT_FLOOR_ID) == floor_id
    }
    origin_space = next(
        (
            s
            for s in spaces.values()
            if len(s.vertices) >= 3 and point_in_polygon(flood.x, flood.y, s.vertices)
        ),
        None,
    )
    if origin_space is None:
        return []

    doors_by_space: dict[str, list] = {sid: [] for sid in spaces}
    for door in layout.doors:
        if (door.floor_id or DEFAULT_FLOOR_ID) != floor_id:
            continue
        a, b = door.connects
        if a in spaces and b in spaces:
            doors_by_space[a].append(door)
            doors_by_space[b].append(door)

    # space_id -> (t_start, x, y, r0, intensity)
    best: dict[str, tuple[float, float, float, float, float]] = {
        origin_space.id: (0.0, flood.x, flood.y, flood.radius_m, flood.intensity)
    }
    heap: list[tuple[float, str]] = [(0.0, origin_space.id)]

    while heap:
        t_start, space_id = heapq.heappop(heap)
        meta = best.get(space_id)
        if meta is None or t_start > meta[0] + 1e-12:
            continue
        _, cx, cy, r0, intensity = meta
        for door in doors_by_space.get(space_id, []):
            a, b = door.connects
            neighbor = b if a == space_id else a if b == space_id else None
            if neighbor is None or neighbor not in spaces:
                continue
            dist = math.hypot(door.x - cx, door.y - cy)
            if flood.spread_speed_mps > 1e-9:
                t_hit = t_start + max(0.0, (dist - r0) / flood.spread_speed_mps)
            elif dist <= r0 + 1e-9:
                t_hit = t_start
            else:
                continue
            prior = best.get(neighbor)
            if prior is not None and prior[0] <= t_hit + 1e-12:
                continue
            best[neighbor] = (t_hit, door.x, door.y, 0.0, intensity)
            heapq.heappush(heap, (t_hit, neighbor))

    plumes: list[FloodRoomState] = []
    for space_id, (t_start, cx, cy, r0, intensity) in best.items():
        if t + 1e-9 < t_start:
            continue
        age = max(t - t_start, 0.0)
        plumes.append(
            FloodRoomState(
                space_id=space_id,
                x=cx,
                y=cy,
                radius_m=r0 + flood.spread_speed_mps * age,
                intensity=intensity,
            )
        )
    return plumes


def _node_space_ids(node, doors: dict, exits: dict) -> set[str]:
    if node.kind in (NodeKind.SPACE, NodeKind.WAYPOINT):
        return {node.ref_id}
    if node.kind == NodeKind.DOOR:
        door = doors.get(node.ref_id)
        return set(door.connects) if door is not None else set()
    if node.kind == NodeKind.EXIT:
        exit_ = exits.get(node.ref_id)
        return {exit_.connected_space_id} if exit_ is not None else set()
    return set()


def flood_intensity_at(
    plumes: list[FloodRoomState],
    space_id: str | None,
    x: float,
    y: float,
) -> float:
    """Highest flood intensity covering (x, y) in space_id, or 0 if dry."""
    if not plumes or not space_id:
        return 0.0
    best = 0.0
    for plume in plumes:
        if plume.space_id != space_id:
            continue
        if plume.radius_m < 0:
            continue
        if (x - plume.x) ** 2 + (y - plume.y) ** 2 <= plume.radius_m**2 + 1e-9:
            best = max(best, plume.intensity)
    return best


def flood_soft_speed_factor(
    plumes: list[FloodRoomState],
    space_id: str | None,
    x: float,
    y: float,
) -> float:
    """Slow while standing in water; never hard-blocks (unlike fire)."""
    intensity = flood_intensity_at(plumes, space_id, x, y)
    if intensity <= 0:
        return 1.0
    return max(0.1, 1.0 - intensity / 100.0)


def flood_plumes_speed_factor(
    plumes: list[FloodRoomState],
    space_ids: set[str] | None,
    x: float,
    y: float,
    target_x: float | None = None,
    target_y: float | None = None,
    *,
    is_exit: bool = False,
) -> float:
    """Soft slowdown for flood along a segment (strongest wet point wins).

    ``is_exit`` is accepted for call-site compatibility; flood never hard-blocks.
    """
    del is_exit  # flood is soft-only
    if not plumes:
        return 1.0
    spaces = space_ids if space_ids is not None else {p.space_id for p in plumes}
    points = [(x, y)]
    if target_x is not None and target_y is not None:
        points.append((target_x, target_y))
        points.append(((x + target_x) * 0.5, (y + target_y) * 0.5))
    factor = 1.0
    for sid in spaces:
        for px, py in points:
            factor = min(factor, flood_soft_speed_factor(plumes, sid, px, py))
    return factor


def apply_flood_exposure(
    occupants,
    plumes: list[FloodRoomState],
    dt: float,
) -> None:
    """Accumulate immersion dose; trap after FLOOD_LETHAL_EXPOSURE_S at full intensity."""
    if not plumes or dt <= 0:
        return
    for occ in occupants:
        if occ.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED):
            continue
        intensity = flood_intensity_at(plumes, occ.current_space_id, occ.x, occ.y)
        if intensity <= 0:
            continue
        occ.flood_exposure_s += (intensity / 100.0) * dt
        if occ.flood_exposure_s + 1e-12 >= FLOOD_LETHAL_EXPOSURE_S:
            occ.status = OccupantStatus.TRAPPED
            occ.climb_progress = None
            occ.climb_from_space_id = None
            occ.climb_to_space_id = None


def apply_flood_plumes(
    graph: NavigationGraph,
    plumes: list[FloodRoomState],
    layout: BuildingLayout,
) -> None:
    """Multiply graph edge speed factors by soft flood slowdown (never zero from flood)."""
    if not plumes:
        return
    doors = {d.id: d for d in layout.doors}
    exits = {e.id: e for e in layout.exits}
    for edge in graph.edges.values():
        a, b = graph.nodes[edge.from_id], graph.nodes[edge.to_id]
        edge_spaces = _node_space_ids(a, doors, exits) & _node_space_ids(b, doors, exits)
        if not edge_spaces:
            continue
        factor = flood_plumes_speed_factor(
            plumes,
            edge_spaces,
            a.x,
            a.y,
            b.x,
            b.y,
        )
        edge.speed_factor *= factor


def apply_flood(graph, flood_or_layout, t=0.0, layout: BuildingLayout | None = None):
    """Apply flood to the nav graph.

    Preferred: ``apply_flood(graph, layout, t)``.
    Legacy: ``apply_flood(graph, flood, layout=layout)``.
    """
    if isinstance(flood_or_layout, BuildingLayout):
        building = flood_or_layout
        plumes = active_flood_plumes(building, t)
        apply_flood_plumes(graph, plumes, building)
        return
    if layout is not None:
        plumes = active_flood_plumes(layout, t)
        apply_flood_plumes(graph, plumes, layout)
        return
    # Fallback: unscoped single circle (tests without a layout).
    apply_hazards(graph, (flood_or_layout,), t)


__all__ = [
    "FLOOD_LETHAL_EXPOSURE_S",
    "FloodRouteSelector",
    "active_flood_plumes",
    "apply_flood",
    "apply_flood_exposure",
    "apply_flood_plumes",
    "flood_intensity_at",
    "flood_plumes_speed_factor",
    "flood_radius_at",
    "flood_soft_speed_factor",
    "segment_speed_factor",
]
