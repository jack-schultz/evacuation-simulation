"""Time-dependent radial hazards shared by flood, fire, and smoke scenarios."""

from __future__ import annotations

from app.domain.building import (
    BuildingLayout,
    RadialEmergency,
    SmokeEmergency,
    SmokeFloorState,
    SpaceType,
)
from app.simulation.graph import NavigationGraph, NodeKind
from app.simulation.routing import DijkstraRouteSelector
from app.simulation.stair_geometry import floor_elevation


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
        radius_m=fire.radius_m * 1.4,
        spread_speed_mps=fire.spread_speed_mps,
        intensity=max(1.0, fire.intensity * 0.8),
        floor_id=fire.floor_id,
        visibility_m=fire.smoke_visibility_m,
        stair_spread_delay_s=fire.smoke_stair_spread_delay_s,
        stair_spread_intensity_factor=fire.smoke_stair_intensity_factor,
    )


def resolve_origin_smoke(layout: BuildingLayout) -> SmokeEmergency | None:
    """Smoke is produced by fire (emit_smoke); not a separate disaster."""
    return _synthetic_fire_smoke(layout)


def active_smoke_plumes(layout: BuildingLayout, t: float) -> list[SmokeFloorState]:
    """Origin smoke plus chimney plumes that have risen through linked stairs."""
    origin = resolve_origin_smoke(layout)
    if origin is None:
        return []
    origin_radius = hazard_radius_at(origin, t)
    if origin_radius is None:
        return []

    floors = {f.id: f for f in layout.floors}
    spaces = {s.id: s for s in layout.spaces}
    stairs = [
        s for s in layout.spaces if s.type == SpaceType.STAIRS and s.linked_stair_id
    ]

    plumes: list[SmokeFloorState] = [
        SmokeFloorState(
            floor_id=origin.floor_id,
            radius_m=origin_radius,
            x=origin.x,
            y=origin.y,
            intensity=origin.intensity,
        )
    ]

    # Queue of (floor_id, centre, intensity, time when this plume started)
    queue: list[tuple[str, float, float, float, float]] = [
        (origin.floor_id, origin.x, origin.y, origin.intensity, 0.0)
    ]
    ignited = {origin.floor_id}

    while queue:
        floor_id, cx, cy, intensity, t_start = queue.pop(0)
        age = max(t - t_start, 0.0)
        radius_here = origin.radius_m + origin.spread_speed_mps * age
        for stair in stairs:
            if stair.floor_id != floor_id or not stair.linked_stair_id:
                continue
            partner = spaces.get(stair.linked_stair_id)
            if partner is None or partner.type != SpaceType.STAIRS:
                continue
            elev = floor_elevation(floors, stair.floor_id)
            partner_elev = floor_elevation(floors, partner.floor_id)
            if partner_elev <= elev + 1e-9:
                continue
            if partner.floor_id in ignited:
                continue
            sx, sy = stair.centroid
            dist = ((sx - cx) ** 2 + (sy - cy) ** 2) ** 0.5
            if origin.spread_speed_mps > 1e-9:
                t_hit = t_start + max(0.0, (dist - origin.radius_m) / origin.spread_speed_mps)
            elif dist <= origin.radius_m + 1e-9:
                t_hit = t_start
            else:
                continue
            if radius_here + 1e-6 < dist and t < t_hit:
                continue
            t_ignite = t_hit + origin.stair_spread_delay_s
            if t + 1e-9 < t_ignite:
                continue
            upper_intensity = intensity * origin.stair_spread_intensity_factor
            px, py = partner.centroid
            upper_radius = max(
                0.5,
                origin.radius_m * 0.5
                + origin.spread_speed_mps * max(t - t_ignite, 0.0),
            )
            ignited.add(partner.floor_id)
            plumes.append(
                SmokeFloorState(
                    floor_id=partner.floor_id,
                    radius_m=upper_radius,
                    x=px,
                    y=py,
                    intensity=upper_intensity,
                )
            )
            queue.append((partner.floor_id, px, py, upper_intensity, t_ignite))

    return plumes


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
