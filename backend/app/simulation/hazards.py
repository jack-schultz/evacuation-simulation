"""Time-dependent radial hazards shared by flood, fire, and smoke scenarios."""

from __future__ import annotations

import heapq
import math

from app.domain.building import (
    DEFAULT_FLOOR_ID,
    BuildingLayout,
    FireEmergency,
    RadialEmergency,
    SmokeEmergency,
    SmokeFloorState,
    SmokeRoomState,
    SpaceType,
)
from app.domain.geometry import closest_boundary_point, point_in_polygon
from app.simulation.graph import NavigationGraph, NodeKind
from app.simulation.routing import DijkstraRouteSelector
from app.simulation.stair_geometry import floor_elevation

# Smoke expands faster on the floor than the parent fire.
SMOKE_SPREAD_MULTIPLIER = 2.5
SMOKE_RADIUS_MULTIPLIER = 1.4
# Fire takes longer to transfer through a stair than smoke.
FIRE_STAIR_DELAY_MULTIPLIER = 2.5


def _floor_id(entity) -> str:
    return getattr(entity, "floor_id", None) or DEFAULT_FLOOR_ID


def _t_travel(t_start: float, r0: float, dist: float, speed: float) -> float | None:
    """Time when an expanding plume reaches distance ``dist`` from its centre."""
    if dist <= r0 + 1e-9:
        return t_start
    if speed <= 1e-9:
        return None
    return t_start + (dist - r0) / speed


def hazard_radius_at(hazard: RadialEmergency | None, t: float) -> float | None:
    if hazard is None or not hazard.enabled or hazard.intensity == 0:
        return None
    return hazard.radius_m + hazard.spread_speed_mps * max(t, 0.0)


def max_hazard_radius_at(
    hazards: list[RadialEmergency] | None,
    t: float,
) -> float | None:
    """Largest active origin radius, or None when no hazard is active."""
    if not hazards:
        return None
    radii = [hazard_radius_at(h, t) for h in hazards]
    active = [r for r in radii if r is not None]
    return max(active) if active else None


def segment_speed_factor(hazard, radius, x, y, target_x, target_y, *, is_exit=False):
    """Reject entry/crossing; allow slowed outward escape from the affected area.

    Movement calls this with the person's current position, so a hazard behind
    them cannot block or slow their remaining clear path.
    """
    if radius is None:
        return 1.0
    radius_sq = radius * radius
    ax, ay = x - hazard.x, y - hazard.y
    dx, dy = target_x - x, target_y - y
    length_sq = dx * dx + dy * dy
    start_sq = ax * ax + ay * ay
    end_sq = (target_x - hazard.x) ** 2 + (target_y - hazard.y) ** 2
    progress = ax * dx + ay * dy
    fraction = max(0.0, min(1.0, -progress / length_sq)) if length_sq else 0.0
    closest_sq = (ax + fraction * dx) ** 2 + (ay + fraction * dy) ** 2
    if closest_sq > radius_sq:
        return 1.0
    if is_exit and end_sq <= radius_sq:
        return 0.0
    if start_sq <= radius_sq and progress >= 0 and end_sq > start_sq:
        return max(0.1, 1.0 - hazard.intensity / 100)
    return 0.0


def smoke_speed_factor(hazard: SmokeEmergency | None, radius: float | None, x: float, y: float) -> float:
    """Soft slowdown inside smoke; never hard-blocks."""
    if hazard is None or radius is None:
        return 1.0
    dx, dy = x - hazard.x, y - hazard.y
    if dx * dx + dy * dy > radius * radius:
        return 1.0
    return max(0.25, 1.0 - hazard.intensity / 100.0)


def smoke_visibility_m(hazard: SmokeEmergency) -> float:
    return hazard.visibility_m * (1.2 - hazard.intensity / 100.0)


def hazards_speed_factor(hazards, t, x, y, target_x, target_y, *, is_exit=False):
    """Use the strongest restriction; one hazard cannot cancel another."""
    return min(
        (
            segment_speed_factor(
                hazard,
                hazard_radius_at(hazard, t),
                x,
                y,
                target_x,
                target_y,
                is_exit=is_exit,
            )
            for hazard in hazards
            if hazard is not None and not isinstance(hazard, SmokeEmergency)
        ),
        default=1.0,
    )


def apply_hazards(graph: NavigationGraph, hazards, t: float = 0.0) -> None:
    hard = [h for h in hazards if h is not None and not isinstance(h, SmokeEmergency)]
    smokes = [h for h in hazards if isinstance(h, SmokeEmergency)]
    for edge in graph.edges.values():
        a, b = graph.nodes[edge.from_id], graph.nodes[edge.to_id]
        hard_factor = hazards_speed_factor(
            hard, t, a.x, a.y, b.x, b.y, is_exit=b.kind == NodeKind.EXIT
        )
        smoke_factor = 1.0
        for smoke in smokes:
            radius = hazard_radius_at(smoke, t)
            mid_x, mid_y = (a.x + b.x) * 0.5, (a.y + b.y) * 0.5
            smoke_factor = min(smoke_factor, smoke_speed_factor(smoke, radius, mid_x, mid_y))
            if radius is not None and edge.distance_m > smoke_visibility_m(smoke):
                smoke_factor = min(smoke_factor, 0.15)
        edge.speed_factor = edge.base_speed_factor * hard_factor * smoke_factor


class HazardRouteSelector(DijkstraRouteSelector):
    """Fall back from an inaccessible preferred exit; preserve stranded occupants."""

    def select_route(self, graph, start_node_id, preferred_exit_id=None):
        try:
            return super().select_route(graph, start_node_id, preferred_exit_id)
        except ValueError:
            if preferred_exit_id:
                try:
                    return super().select_route(graph, start_node_id)
                except ValueError:
                    pass
            return [start_node_id]


def _synthetic_fire_smoke(fire: FireEmergency) -> SmokeEmergency | None:
    if not fire.enabled or not fire.emit_smoke or fire.intensity <= 0:
        return None
    return SmokeEmergency(
        enabled=True,
        x=fire.x,
        y=fire.y,
        radius_m=fire.radius_m * SMOKE_RADIUS_MULTIPLIER,
        spread_speed_mps=fire.spread_speed_mps * SMOKE_SPREAD_MULTIPLIER,
        intensity=max(1.0, fire.intensity * 0.8),
        floor_id=fire.floor_id,
        visibility_m=fire.smoke_visibility_m,
        stair_spread_delay_s=fire.smoke_stair_spread_delay_s,
        stair_spread_intensity_factor=fire.smoke_stair_intensity_factor,
    )


def resolve_origin_smokes(layout: BuildingLayout) -> list[SmokeEmergency]:
    """Smoke plumes produced by each fire with emit_smoke enabled."""
    return [
        smoke
        for fire in layout.fires
        if (smoke := _synthetic_fire_smoke(fire)) is not None
    ]


def resolve_origin_smoke(layout: BuildingLayout) -> SmokeEmergency | None:
    """First active smoke origin (compat); prefer resolve_origin_smokes."""
    smokes = resolve_origin_smokes(layout)
    return smokes[0] if smokes else None


def resolve_origin_fires(layout: BuildingLayout) -> list[FireEmergency]:
    return [
        fire
        for fire in layout.fires
        if fire.enabled and fire.intensity > 0
    ]


def resolve_origin_fire(layout: BuildingLayout) -> FireEmergency | None:
    """First active fire origin (compat); prefer resolve_origin_fires."""
    fires = resolve_origin_fires(layout)
    return fires[0] if fires else None


def _stair_partners_by_floor(
    stairs: list,
    spaces: dict,
    floors: dict,
) -> dict[str, list[tuple[object, object, bool]]]:
    """floor_id -> list of (stair_on_this_floor, partner_stair, going_up).

    Linked stairs are treated as bidirectional for hazard spread, so a
    one-way editor link (ground→level1 only, or a climb chain level1→2→3)
    still allows smoke/fire to move back down the shaft.
    """
    by_floor: dict[str, list[tuple[object, object, bool]]] = {}
    seen: set[tuple[str, str]] = set()

    def add_edge(stair, partner) -> None:
        elev = floor_elevation(floors, stair.floor_id)
        partner_elev = floor_elevation(floors, partner.floor_id)
        if abs(partner_elev - elev) <= 1e-9:
            return
        key = (stair.floor_id, partner.floor_id)
        if key in seen:
            return
        seen.add(key)
        going_up = partner_elev > elev
        by_floor.setdefault(stair.floor_id, []).append((stair, partner, going_up))

    for stair in stairs:
        if not stair.linked_stair_id:
            continue
        partner = spaces.get(stair.linked_stair_id)
        if partner is None or partner.type != SpaceType.STAIRS:
            continue
        add_edge(stair, partner)
        add_edge(partner, stair)
    return by_floor


def _stair_plume_metas(
    origin: RadialEmergency,
    layout: BuildingLayout,
    *,
    stair_delay_s: float,
    intensity_factor: float,
) -> dict[str, tuple[float, float, float, float, float]]:
    """floor_id -> (x, y, intensity, t_start, start_radius) for eventual stair plumes."""
    if not origin.enabled or origin.intensity <= 0:
        return {}

    floors = {f.id: f for f in layout.floors}
    spaces = {s.id: s for s in layout.spaces}
    stairs = [
        s for s in layout.spaces if s.type == SpaceType.STAIRS and s.linked_stair_id
    ]
    partners_by_floor = _stair_partners_by_floor(stairs, spaces, floors)

    start_r = origin.radius_m
    plume_meta: dict[str, tuple[float, float, float, float, float]] = {
        origin.floor_id: (origin.x, origin.y, origin.intensity, 0.0, start_r)
    }
    queue: list[str] = [origin.floor_id]
    ignited = {origin.floor_id}

    while queue:
        floor_id = queue.pop(0)
        cx, cy, intensity, t_start, plume_r0 = plume_meta[floor_id]
        for stair, partner, _going_up in partners_by_floor.get(floor_id, []):
            if partner.floor_id in ignited:
                continue
            sx, sy = stair.centroid
            dist = ((sx - cx) ** 2 + (sy - cy) ** 2) ** 0.5
            t_hit = _t_travel(t_start, plume_r0, dist, origin.spread_speed_mps)
            if t_hit is None:
                continue
            t_ignite = t_hit + stair_delay_s
            next_intensity = intensity * intensity_factor
            px, py = partner.centroid
            next_r0 = max(0.5, origin.radius_m * 0.5)
            ignited.add(partner.floor_id)
            plume_meta[partner.floor_id] = (
                px,
                py,
                next_intensity,
                t_ignite,
                next_r0,
            )
            queue.append(partner.floor_id)

    return plume_meta


def _active_stair_plumes(
    origin: RadialEmergency,
    layout: BuildingLayout,
    t: float,
    *,
    stair_delay_s: float,
    intensity_factor: float,
) -> list[SmokeFloorState]:
    """Expand on the origin floor and spread through linked stairs (up and down)."""
    if hazard_radius_at(origin, t) is None:
        return []
    plumes: list[SmokeFloorState] = []
    for floor_id, (cx, cy, intensity, t_start, plume_r0) in _stair_plume_metas(
        origin,
        layout,
        stair_delay_s=stair_delay_s,
        intensity_factor=intensity_factor,
    ).items():
        if t + 1e-9 < t_start:
            continue
        age = max(t - t_start, 0.0)
        plumes.append(
            SmokeFloorState(
                floor_id=floor_id,
                radius_m=plume_r0 + origin.spread_speed_mps * age,
                x=cx,
                y=cy,
                intensity=intensity,
            )
        )
    return plumes


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


def _smoke_adjacency(layout: BuildingLayout) -> tuple[dict, dict, list]:
    """doors_by_space, vertical_links by stair id, host openings."""
    spaces = {s.id: s for s in layout.spaces}
    floors = {f.id: f for f in layout.floors}
    doors_by_space: dict[str, list] = {sid: [] for sid in spaces}
    for door in layout.doors:
        a, b = door.connects
        if a in spaces and b in spaces:
            doors_by_space[a].append(door)
            doors_by_space[b].append(door)

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
            vertical.setdefault(a.id, []).append(b)

    return doors_by_space, vertical, _stair_hosts(layout)


def _fire_smoke_room_seeds(
    fire: FireEmergency,
    layout: BuildingLayout,
) -> list[tuple[str, float, float, float, float, float]]:
    """Seeds (space_id, t_start, x, y, r0, intensity) when fire first touches each room.

    Fire keeps radial floor spread; any room the fire circle reaches without
    prior smoke becomes a new smoke origin.
    """
    smoke = _synthetic_fire_smoke(fire)
    if smoke is None:
        return []
    metas = _stair_plume_metas(
        fire,
        layout,
        stair_delay_s=fire.smoke_stair_spread_delay_s * FIRE_STAIR_DELAY_MULTIPLIER,
        intensity_factor=fire.smoke_stair_intensity_factor,
    )
    spaces = list(layout.spaces)
    seeds: list[tuple[str, float, float, float, float, float]] = []
    for floor_id, (cx, cy, intensity, t_start, r0) in metas.items():
        smoke_intensity = max(1.0, intensity * 0.8)
        for space in spaces:
            if _floor_id(space) != floor_id or len(space.vertices) < 3:
                continue
            if point_in_polygon(cx, cy, space.vertices):
                seeds.append(
                    (
                        space.id,
                        t_start,
                        cx,
                        cy,
                        fire.radius_m * SMOKE_RADIUS_MULTIPLIER,
                        smoke_intensity,
                    )
                )
                continue
            bx, by = closest_boundary_point(cx, cy, space.vertices)
            dist = math.hypot(bx - cx, by - cy)
            t_hit = _t_travel(t_start, r0, dist, fire.spread_speed_mps)
            if t_hit is None:
                continue
            seeds.append((space.id, t_hit, bx, by, 0.0, smoke_intensity))
    return seeds


def _smoke_spread_meta(
    layout: BuildingLayout,
    seeds: list[tuple[str, float, float, float, float, float]],
    *,
    speed: float,
    stair_delay_s: float,
    intensity_factor: float,
    stair_r0: float,
) -> dict[str, tuple[float, float, float, float, float]]:
    """space_id -> (t_start, x, y, r0, intensity). Door + host openings + delayed stairs."""
    if not seeds:
        return {}
    spaces = {s.id: s for s in layout.spaces}
    doors_by_space, vertical, host_openings = _smoke_adjacency(layout)
    host_links: dict[str, list[tuple[str, float, float]]] = {sid: [] for sid in spaces}
    for host_id, stair_id, sx, sy in host_openings:
        host_links[host_id].append((stair_id, sx, sy))
        host_links[stair_id].append((host_id, sx, sy))

    best: dict[str, tuple[float, float, float, float, float]] = {}
    heap: list[tuple[float, str]] = []

    def offer(
        space_id: str, t_start: float, x: float, y: float, r0: float, intensity: float
    ) -> None:
        if space_id not in spaces:
            return
        prior = best.get(space_id)
        if prior is not None and prior[0] <= t_start + 1e-12:
            return
        best[space_id] = (t_start, x, y, r0, intensity)
        heapq.heappush(heap, (t_start, space_id))

    for space_id, t_start, x, y, r0, intensity in seeds:
        offer(space_id, t_start, x, y, r0, intensity)

    while heap:
        t_start, space_id = heapq.heappop(heap)
        meta = best.get(space_id)
        if meta is None or t_start > meta[0] + 1e-12:
            continue
        _, cx, cy, r0, intensity = meta
        space = spaces[space_id]

        for door in doors_by_space.get(space_id, []):
            a, b = door.connects
            neighbor = b if a == space_id else a if b == space_id else None
            if neighbor is None or neighbor not in spaces:
                continue
            dist = math.hypot(door.x - cx, door.y - cy)
            t_hit = _t_travel(t_start, r0, dist, speed)
            if t_hit is None:
                continue
            offer(neighbor, t_hit, door.x, door.y, 0.0, intensity)

        for neighbor_id, ox, oy in host_links.get(space_id, []):
            dist = math.hypot(ox - cx, oy - cy)
            t_hit = _t_travel(t_start, r0, dist, speed)
            if t_hit is None:
                continue
            offer(neighbor_id, t_hit, ox, oy, 0.0, intensity)

        if space.type == SpaceType.STAIRS:
            sx, sy = space.centroid
            t_reach = _t_travel(t_start, r0, math.hypot(sx - cx, sy - cy), speed)
            if t_reach is None:
                continue
            t_transfer = t_reach + stair_delay_s
            next_intensity = intensity * intensity_factor
            for partner in vertical.get(space_id, []):
                px, py = partner.centroid
                offer(partner.id, t_transfer, px, py, stair_r0, next_intensity)

    return best


def hazard_stair_spread_pending(layout: BuildingLayout, t: float, horizon: float) -> bool:
    """True when waiting until horizon would ignite more fire/smoke/flood."""
    from app.simulation.flood import flood_stair_spread_pending

    fire_now = {p.floor_id for p in active_fire_plumes(layout, t)}
    fire_later = {p.floor_id for p in active_fire_plumes(layout, horizon)}
    smoke_now = {p.space_id for p in active_smoke_plumes(layout, t)}
    smoke_later = {p.space_id for p in active_smoke_plumes(layout, horizon)}
    return bool(
        fire_later - fire_now
        or smoke_later - smoke_now
        or flood_stair_spread_pending(layout, t, horizon)
    )


def active_smoke_plumes(layout: BuildingLayout, t: float) -> list[SmokeRoomState]:
    """Room-scoped smoke: through doors like flood, plus fire-seeded rooms."""
    plumes: list[SmokeRoomState] = []
    # Merge overlapping room plumes from every fire (earliest / strongest per space).
    best_by_space: dict[str, SmokeRoomState] = {}
    for fire in resolve_origin_fires(layout):
        smoke = _synthetic_fire_smoke(fire)
        if smoke is None:
            continue
        seeds = _fire_smoke_room_seeds(fire, layout)
        meta = _smoke_spread_meta(
            layout,
            seeds,
            speed=smoke.spread_speed_mps,
            stair_delay_s=smoke.stair_spread_delay_s,
            intensity_factor=smoke.stair_spread_intensity_factor,
            stair_r0=max(0.5, smoke.radius_m * 0.5),
        )
        for space_id, (t_start, cx, cy, r0, intensity) in meta.items():
            if t + 1e-9 < t_start:
                continue
            age = max(t - t_start, 0.0)
            plume = SmokeRoomState(
                space_id=space_id,
                x=cx,
                y=cy,
                radius_m=r0 + smoke.spread_speed_mps * age,
                intensity=intensity,
            )
            prior = best_by_space.get(space_id)
            if prior is None or plume.radius_m > prior.radius_m + 1e-12:
                best_by_space[space_id] = plume
            elif abs(plume.radius_m - prior.radius_m) <= 1e-12:
                best_by_space[space_id] = SmokeRoomState(
                    space_id=space_id,
                    x=prior.x,
                    y=prior.y,
                    radius_m=prior.radius_m,
                    intensity=max(prior.intensity, plume.intensity),
                )
    plumes.extend(best_by_space.values())
    return plumes


def active_fire_plumes(layout: BuildingLayout, t: float) -> list[SmokeFloorState]:
    """Fire expands on-floor and follows the same stair path as smoke, but more slowly."""
    plumes: list[SmokeFloorState] = []
    for origin in resolve_origin_fires(layout):
        plumes.extend(
            _active_stair_plumes(
                origin,
                layout,
                t,
                stair_delay_s=origin.smoke_stair_spread_delay_s * FIRE_STAIR_DELAY_MULTIPLIER,
                intensity_factor=origin.smoke_stair_intensity_factor,
            )
        )
    return plumes


def smoke_factor_at(
    plumes: list[SmokeRoomState],
    space_id: str | None,
    x: float,
    y: float,
) -> float:
    """Soft slowdown inside a room-scoped smoke plume; never hard-blocks."""
    if not plumes or not space_id:
        return 1.0
    factor = 1.0
    for plume in plumes:
        if plume.space_id != space_id:
            continue
        dx, dy = x - plume.x, y - plume.y
        if dx * dx + dy * dy <= plume.radius_m * plume.radius_m + 1e-9:
            factor = min(factor, max(0.25, 1.0 - plume.intensity / 100.0))
    return factor


def fire_touches(
    plumes: list[SmokeFloorState],
    floor_id: str,
    x: float,
    y: float,
    body_radius_m: float = 0.0,
) -> bool:
    """True when the person's body intersects a fire plume on their floor."""
    for plume in plumes:
        if plume.floor_id != floor_id:
            continue
        r = plume.radius_m + max(body_radius_m, 0.0)
        dx, dy = x - plume.x, y - plume.y
        if dx * dx + dy * dy <= r * r:
            return True
    return False


def hard_plume_factor(
    plumes: list[SmokeFloorState],
    floor_id: str,
    x: float,
    y: float,
    target_x: float,
    target_y: float,
    *,
    is_exit: bool = False,
) -> float:
    """Hard fire restriction: no entry/crossing; contact is lethal (handled separately)."""
    factor = 1.0
    for plume in plumes:
        if plume.floor_id != floor_id:
            continue
        hazard = RadialEmergency(
            enabled=True,
            x=plume.x,
            y=plume.y,
            radius_m=plume.radius_m,
            spread_speed_mps=0.0,
            intensity=plume.intensity,
            floor_id=plume.floor_id,
        )
        # Fire is lethal on contact: never allow the "escape outward" slowdown.
        radius = plume.radius_m
        radius_sq = radius * radius
        ax, ay = x - hazard.x, y - hazard.y
        start_sq = ax * ax + ay * ay
        if start_sq <= radius_sq:
            return 0.0
        factor = min(
            factor,
            segment_speed_factor(
                hazard,
                radius,
                x,
                y,
                target_x,
                target_y,
                is_exit=is_exit,
            ),
        )
    return factor


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


def apply_smoke_plumes(
    graph: NavigationGraph,
    plumes: list[SmokeRoomState],
    layout: BuildingLayout,
    *,
    visibility_m: float = 8.0,
) -> None:
    """Multiply graph edge speed factors by soft smoke slowdown (never zero)."""
    if not plumes:
        return
    doors = {d.id: d for d in layout.doors}
    exits = {e.id: e for e in layout.exits}
    for edge in graph.edges.values():
        a, b = graph.nodes[edge.from_id], graph.nodes[edge.to_id]
        edge_spaces = _node_space_ids(a, doors, exits) & _node_space_ids(b, doors, exits)
        if not edge_spaces:
            continue
        mid_x, mid_y = (a.x + b.x) * 0.5, (a.y + b.y) * 0.5
        factor = 1.0
        for sid in edge_spaces:
            factor = min(factor, smoke_factor_at(plumes, sid, mid_x, mid_y))
            factor = min(factor, smoke_factor_at(plumes, sid, a.x, a.y))
            factor = min(factor, smoke_factor_at(plumes, sid, b.x, b.y))
        if factor < 1.0 - 1e-12 and edge.distance_m > visibility_m:
            factor = min(factor, 0.15)
        edge.speed_factor *= factor


def smoke_emergencies_from_plumes(plumes: list[SmokeRoomState]) -> list[SmokeEmergency]:
    """Adapt room plume snapshots into RadialEmergency-like objects for apply_hazards."""
    return [
        SmokeEmergency(
            enabled=True,
            x=p.x,
            y=p.y,
            radius_m=p.radius_m,
            spread_speed_mps=0.0,
            intensity=p.intensity,
            floor_id=DEFAULT_FLOOR_ID,
        )
        for p in plumes
    ]


def fire_emergencies_from_plumes(plumes: list[SmokeFloorState]) -> list[FireEmergency]:
    return [
        FireEmergency(
            enabled=True,
            x=p.x,
            y=p.y,
            radius_m=p.radius_m,
            spread_speed_mps=0.0,
            intensity=p.intensity,
            floor_id=p.floor_id,
            emit_smoke=False,
        )
        for p in plumes
    ]
