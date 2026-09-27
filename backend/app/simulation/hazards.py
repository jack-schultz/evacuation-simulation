"""Time-dependent radial hazards shared by flood, fire, and smoke scenarios."""

from __future__ import annotations

from app.domain.building import (
    BuildingLayout,
    FireEmergency,
    RadialEmergency,
    SmokeEmergency,
    SmokeFloorState,
    SpaceType,
)
from app.simulation.graph import NavigationGraph, NodeKind
from app.simulation.routing import DijkstraRouteSelector
from app.simulation.stair_geometry import floor_elevation

# Smoke expands faster on the floor than the parent fire.
SMOKE_SPREAD_MULTIPLIER = 2.5
SMOKE_RADIUS_MULTIPLIER = 1.4
# Fire takes longer to transfer through a stair than smoke.
FIRE_STAIR_DELAY_MULTIPLIER = 2.5


def hazard_radius_at(hazard: RadialEmergency | None, t: float) -> float | None:
    if hazard is None or not hazard.enabled or hazard.intensity == 0:
        return None
    return hazard.radius_m + hazard.spread_speed_mps * max(t, 0.0)


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


def _synthetic_fire_smoke(layout: BuildingLayout) -> SmokeEmergency | None:
    fire = layout.fire
    if fire is None or not fire.enabled or not fire.emit_smoke or fire.intensity <= 0:
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


def resolve_origin_smoke(layout: BuildingLayout) -> SmokeEmergency | None:
    """Smoke is produced by fire (emit_smoke); not a separate disaster."""
    return _synthetic_fire_smoke(layout)


def resolve_origin_fire(layout: BuildingLayout) -> FireEmergency | None:
    fire = layout.fire
    if fire is None or not fire.enabled or fire.intensity <= 0:
        return None
    return fire


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


def _active_stair_plumes(
    origin: RadialEmergency,
    layout: BuildingLayout,
    t: float,
    *,
    stair_delay_s: float,
    intensity_factor: float,
) -> list[SmokeFloorState]:
    """Expand on the origin floor and spread through linked stairs (up and down)."""
    origin_radius = hazard_radius_at(origin, t)
    if origin_radius is None:
        return []

    floors = {f.id: f for f in layout.floors}
    spaces = {s.id: s for s in layout.spaces}
    stairs = [
        s for s in layout.spaces if s.type == SpaceType.STAIRS and s.linked_stair_id
    ]
    partners_by_floor = _stair_partners_by_floor(stairs, spaces, floors)

    # Meta: floor_id -> (x, y, intensity, t_start, start_radius)
    start_r = origin.radius_m
    plume_meta: dict[str, tuple[float, float, float, float, float]] = {
        origin.floor_id: (origin.x, origin.y, origin.intensity, 0.0, start_r)
    }
    queue: list[str] = [origin.floor_id]
    ignited = {origin.floor_id}

    while queue:
        floor_id = queue.pop(0)
        cx, cy, intensity, t_start, plume_r0 = plume_meta[floor_id]
        age = max(t - t_start, 0.0)
        radius_here = plume_r0 + origin.spread_speed_mps * age
        for stair, partner, _going_up in partners_by_floor.get(floor_id, []):
            if partner.floor_id in ignited:
                continue
            sx, sy = stair.centroid
            dist = ((sx - cx) ** 2 + (sy - cy) ** 2) ** 0.5
            if origin.spread_speed_mps > 1e-9:
                t_hit = t_start + max(0.0, (dist - plume_r0) / origin.spread_speed_mps)
            elif dist <= plume_r0 + 1e-9:
                t_hit = t_start
            else:
                continue
            if radius_here + 1e-6 < dist and t < t_hit:
                continue
            t_ignite = t_hit + stair_delay_s
            if t + 1e-9 < t_ignite:
                continue
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

    plumes: list[SmokeFloorState] = []
    for floor_id, (cx, cy, intensity, t_start, plume_r0) in plume_meta.items():
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


def hazard_stair_spread_pending(layout: BuildingLayout, t: float, horizon: float) -> bool:
    """True when waiting until horizon would ignite more fire/smoke floors."""
    fire_now = {p.floor_id for p in active_fire_plumes(layout, t)}
    fire_later = {p.floor_id for p in active_fire_plumes(layout, horizon)}
    smoke_now = {p.floor_id for p in active_smoke_plumes(layout, t)}
    smoke_later = {p.floor_id for p in active_smoke_plumes(layout, horizon)}
    return bool(fire_later - fire_now or smoke_later - smoke_now)


def active_smoke_plumes(layout: BuildingLayout, t: float) -> list[SmokeFloorState]:
    """Origin smoke plus plumes that spread through linked stairs (up, then down from top)."""
    origin = resolve_origin_smoke(layout)
    if origin is None:
        return []
    return _active_stair_plumes(
        origin,
        layout,
        t,
        stair_delay_s=origin.stair_spread_delay_s,
        intensity_factor=origin.stair_spread_intensity_factor,
    )


def active_fire_plumes(layout: BuildingLayout, t: float) -> list[SmokeFloorState]:
    """Fire expands on-floor and follows the same stair path as smoke, but more slowly."""
    origin = resolve_origin_fire(layout)
    if origin is None:
        return []
    return _active_stair_plumes(
        origin,
        layout,
        t,
        stair_delay_s=origin.smoke_stair_spread_delay_s * FIRE_STAIR_DELAY_MULTIPLIER,
        intensity_factor=origin.smoke_stair_intensity_factor,
    )


def smoke_factor_at(
    plumes: list[SmokeFloorState],
    floor_id: str,
    x: float,
    y: float,
) -> float:
    factor = 1.0
    for plume in plumes:
        if plume.floor_id != floor_id:
            continue
        dx, dy = x - plume.x, y - plume.y
        if dx * dx + dy * dy <= plume.radius_m * plume.radius_m:
            factor = min(factor, max(0.25, 1.0 - plume.intensity / 100.0))
    return factor


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
    """Hard fire/flood-style restriction from floor-scoped plumes (already expanded)."""
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
        factor = min(
            factor,
            segment_speed_factor(
                hazard,
                plume.radius_m,
                x,
                y,
                target_x,
                target_y,
                is_exit=is_exit,
            ),
        )
    return factor


def smoke_emergencies_from_plumes(plumes: list[SmokeFloorState]) -> list[SmokeEmergency]:
    """Adapt plume snapshots into RadialEmergency-like objects for apply_hazards."""
    return [
        SmokeEmergency(
            enabled=True,
            x=p.x,
            y=p.y,
            radius_m=p.radius_m,
            spread_speed_mps=0.0,
            intensity=p.intensity,
            floor_id=p.floor_id,
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
