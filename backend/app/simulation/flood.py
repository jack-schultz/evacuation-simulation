"""Room-scoped flood spread through doors and gravity-aware stairs."""

from __future__ import annotations

import heapq
import math

from app.domain.building import (
    BuildingLayout,
    DEFAULT_FLOOR_ID,
    FloodEmergency,
    FloodRoomState,
    OccupantStatus,
    SpaceType,
)
from app.domain.geometry import point_in_polygon
from app.simulation.graph import NavigationGraph, NodeKind
from app.simulation.hazards import (
    HazardRouteSelector as FloodRouteSelector,
    apply_hazards,
    hazard_radius_at as flood_radius_at,
    segment_speed_factor,
)
from app.simulation.stair_geometry import floor_elevation

# Full-intensity-equivalent seconds in water before casualty (trapped).
# At intensity 50 this is ~20s; at intensity 100 it is 10s.
FLOOD_LETHAL_EXPOSURE_S = 10.0


def _floor_id(entity) -> str:
    return getattr(entity, "floor_id", None) or DEFAULT_FLOOR_ID


def _space_fill_radius_m(space, cx: float, cy: float) -> float:
    """Radius needed for a circle at (cx, cy) to cover the space vertices."""
    if not space.vertices:
        return 0.0
    return max(math.hypot(vx - cx, vy - cy) for vx, vy in space.vertices)


def _t_travel(t_start: float, r0: float, dist: float, speed: float) -> float | None:
    """Time when an expanding plume reaches distance ``dist`` from its centre."""
    if dist <= r0 + 1e-9:
        return t_start
    if speed <= 1e-9:
        return None
    return t_start + (dist - r0) / speed


def _door_is_past_stair(
    plume_x: float,
    plume_y: float,
    stair_x: float,
    stair_y: float,
    door_x: float,
    door_y: float,
) -> bool:
    """True when the door lies on the opposite side of the stair from the plume centre."""
    incoming_x = plume_x - stair_x
    incoming_y = plume_y - stair_y
    out_x = door_x - stair_x
    out_y = door_y - stair_y
    return incoming_x * out_x + incoming_y * out_y < -1e-9


def _stair_hosts(layout: BuildingLayout) -> list[tuple[str, str, float, float]]:
    """(host_space_id, stair_id, sx, sy) when a stair centre sits in a same-floor room."""
    spaces = list(layout.spaces)
    hosts: list[tuple[str, str, float, float]] = []
    for stair in spaces:
        if stair.type != SpaceType.STAIRS or len(stair.vertices) < 3:
            continue
        sx, sy = stair.centroid
        candidates = []
        for other in spaces:
            if other.id == stair.id or other.type == SpaceType.STAIRS:
                continue
            if _floor_id(other) != _floor_id(stair):
                continue
            if len(other.vertices) >= 3 and point_in_polygon(sx, sy, other.vertices):
                candidates.append(other)
        if not candidates:
            continue
        host = min(candidates, key=lambda s: s.area_m2)
        hosts.append((host.id, stair.id, sx, sy))
    return hosts


def _build_flood_adjacency(layout: BuildingLayout) -> tuple[dict, dict, list]:
    """doors_by_space, vertical_links by stair id, host openings."""
    spaces = {s.id: s for s in layout.spaces}
    floors = {f.id: f for f in layout.floors}
    doors_by_space: dict[str, list] = {sid: [] for sid in spaces}
    for door in layout.doors:
        a, b = door.connects
        if a in spaces and b in spaces:
            doors_by_space[a].append(door)
            doors_by_space[b].append(door)

    # stair_id -> list of (partner_stair, going_up)
    vertical: dict[str, list] = {}
    stairs = [s for s in layout.spaces if s.type == SpaceType.STAIRS and s.linked_stair_id]
    seen: set[tuple[str, str]] = set()
    for stair in stairs:
        partner = spaces.get(stair.linked_stair_id)
        if partner is None or partner.type != SpaceType.STAIRS:
            continue
        elev = floor_elevation(floors, stair.floor_id)
        partner_elev = floor_elevation(floors, partner.floor_id)
        if abs(partner_elev - elev) <= 1e-9:
            continue
        for a, b in ((stair, partner), (partner, stair)):
            key = (a.id, b.id)
            if key in seen:
                continue
            seen.add(key)
            going_up = floor_elevation(floors, b.floor_id) > floor_elevation(
                floors, a.floor_id
            )
            vertical.setdefault(a.id, []).append((b, going_up))

    return doors_by_space, vertical, _stair_hosts(layout)


def _flood_spread_meta(
    flood: FloodEmergency,
    layout: BuildingLayout,
    *,
    lower_filled: dict[str, float] | None,
    floor_filled: dict[str, float] | None,
) -> dict[str, tuple[float, float, float, float, float]]:
    """space_id -> (t_start, x, y, r0, intensity).

    ``lower_filled`` gates door expansion past descending stairs.
    ``floor_filled`` gates upward stair transfer. Pass None/empty to disable a gate.
    """
    if not flood.enabled or flood.intensity == 0:
        return {}

    spaces = {s.id: s for s in layout.spaces}
    origin_floor = flood.floor_id or DEFAULT_FLOOR_ID
    origin_space = next(
        (
            s
            for s in spaces.values()
            if _floor_id(s) == origin_floor
            and len(s.vertices) >= 3
            and point_in_polygon(flood.x, flood.y, s.vertices)
        ),
        None,
    )
    if origin_space is None:
        return {}

    doors_by_space, vertical, host_openings = _build_flood_adjacency(layout)
    speed = flood.spread_speed_mps
    lower_filled = lower_filled or {}
    floor_filled = floor_filled or {}

    # Openings between host rooms and overlay stairs (centroid portals).
    host_links: dict[str, list[tuple[str, float, float]]] = {sid: [] for sid in spaces}
    for host_id, stair_id, sx, sy in host_openings:
        host_links[host_id].append((stair_id, sx, sy))
        host_links[stair_id].append((host_id, sx, sy))

    # Descending stairs on each floor for "past stair" checks.
    descending_on_floor: dict[str, list] = {}
    for stair_id, partners in vertical.items():
        stair = spaces[stair_id]
        for partner, going_up in partners:
            if going_up:
                continue
            descending_on_floor.setdefault(_floor_id(stair), []).append(
                (stair, partner)
            )

    best: dict[str, tuple[float, float, float, float, float]] = {
        origin_space.id: (0.0, flood.x, flood.y, flood.radius_m, flood.intensity)
    }
    heap: list[tuple[float, str]] = [(0.0, origin_space.id)]

    def offer(space_id: str, t_start: float, x: float, y: float, r0: float, intensity: float) -> None:
        if space_id not in spaces:
            return
        prior = best.get(space_id)
        if prior is not None and prior[0] <= t_start + 1e-12:
            return
        best[space_id] = (t_start, x, y, r0, intensity)
        heapq.heappush(heap, (t_start, space_id))

    while heap:
        t_start, space_id = heapq.heappop(heap)
        meta = best.get(space_id)
        if meta is None or t_start > meta[0] + 1e-12:
            continue
        _, cx, cy, r0, intensity = meta
        space = spaces[space_id]
        floor_id = _floor_id(space)

        # Same-floor doors.
        for door in doors_by_space.get(space_id, []):
            a, b = door.connects
            neighbor = b if a == space_id else a if b == space_id else None
            if neighbor is None or neighbor not in spaces:
                continue
            dist = math.hypot(door.x - cx, door.y - cy)
            t_hit = _t_travel(t_start, r0, dist, speed)
            if t_hit is None:
                continue
            # Gravity: once water reaches a descending stair on this floor, do not
            # expand past that stair until the lower floor is filled.
            for stair, partner in descending_on_floor.get(floor_id, []):
                sx, sy = stair.centroid
                t_stair = _t_travel(t_start, r0, math.hypot(sx - cx, sy - cy), speed)
                if t_stair is None or t_stair > t_hit + 1e-9:
                    # Stair not yet reached by this plume when the door is hit —
                    # only apply if the stair space itself is already wet earlier.
                    stair_meta = best.get(stair.id)
                    if stair_meta is None or stair_meta[0] > t_hit + 1e-9:
                        continue
                    t_stair = stair_meta[0]
                if not _door_is_past_stair(cx, cy, sx, sy, door.x, door.y):
                    continue
                t_lower = lower_filled.get(_floor_id(partner), 0.0)
                t_hit = max(t_hit, t_lower)
            offer(neighbor, t_hit, door.x, door.y, 0.0, intensity)

        # Host room <-> overlay stair openings.
        for neighbor_id, ox, oy in host_links.get(space_id, []):
            dist = math.hypot(ox - cx, oy - cy)
            t_hit = _t_travel(t_start, r0, dist, speed)
            if t_hit is None:
                continue
            offer(neighbor_id, t_hit, ox, oy, 0.0, intensity)

        # Vertical stair transfers.
        if space.type == SpaceType.STAIRS:
            sx, sy = space.centroid
            t_reach = _t_travel(t_start, r0, math.hypot(sx - cx, sy - cy), speed)
            if t_reach is None:
                continue
            for partner, going_up in vertical.get(space_id, []):
                px, py = partner.centroid
                if going_up:
                    # Up only after this floor is filled.
                    t_filled = floor_filled.get(floor_id)
                    if t_filled is None:
                        continue
                    t_transfer = max(t_reach, t_filled)
                else:
                    # Down immediately when the stair is reached.
                    t_transfer = t_reach
                offer(partner.id, t_transfer, px, py, 0.0, intensity)

    return best


def _floor_fill_times(
    flood: FloodEmergency,
    layout: BuildingLayout,
    best: dict[str, tuple[float, float, float, float, float]],
) -> dict[str, float]:
    """Earliest time each floor is fully covered by its wet spaces' plumes."""
    speed = flood.spread_speed_mps
    spaces = {s.id: s for s in layout.spaces}
    by_floor: dict[str, list[str]] = {}
    for space_id in best:
        by_floor.setdefault(_floor_id(spaces[space_id]), []).append(space_id)

    fills: dict[str, float] = {}
    for floor_id, space_ids in by_floor.items():
        t_fill = 0.0
        for space_id in space_ids:
            t0, cx, cy, r0, _intensity = best[space_id]
            need = _space_fill_radius_m(spaces[space_id], cx, cy)
            done = _t_travel(t0, r0, need, speed)
            if done is None:
                done = math.inf
            t_fill = max(t_fill, done)
        fills[floor_id] = t_fill
    return fills


def _active_flood_plumes_for(
    flood: FloodEmergency,
    layout: BuildingLayout,
    t: float,
) -> list[FloodRoomState]:
    """Expand one flood origin room-by-room with gravity-aware stairs."""
    if not flood.enabled or flood.intensity == 0:
        return []

    # Pass 1: doors + downward stairs (no past-stair delay, no upward transfer).
    best = _flood_spread_meta(flood, layout, lower_filled=None, floor_filled=None)
    fills = _floor_fill_times(flood, layout, best)

    # Pass 2: delay expansion past descending stairs until lower floors fill;
    # allow upward transfer after each floor fills.
    best = _flood_spread_meta(flood, layout, lower_filled=fills, floor_filled=fills)
    fills = _floor_fill_times(flood, layout, best)

    # Pass 3: converge gates with updated fill times.
    best = _flood_spread_meta(flood, layout, lower_filled=fills, floor_filled=fills)

    speed = flood.spread_speed_mps
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
                radius_m=r0 + speed * age,
                intensity=intensity,
            )
        )
    return plumes


def active_flood_plumes(layout: BuildingLayout, t: float) -> list[FloodRoomState]:
    """Merge plumes from every flood origin on the layout."""
    plumes: list[FloodRoomState] = []
    for flood in layout.floods:
        plumes.extend(_active_flood_plumes_for(flood, layout, t))
    return plumes


def flood_stair_spread_pending(layout: BuildingLayout, t: float, horizon: float) -> bool:
    """True when waiting until horizon would wet more spaces via flood spread."""
    now = {p.space_id for p in active_flood_plumes(layout, t)}
    later = {p.space_id for p in active_flood_plumes(layout, horizon)}
    return bool(later - now)


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
            occ.deceased = True
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
    "flood_stair_spread_pending",
    "segment_speed_factor",
]
