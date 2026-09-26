"""Occupant spawning for the evacuation simulation."""

from __future__ import annotations

import math

from app.domain.building import BuildingLayout, OccupantStatus
from app.domain.geometry import (
    clamp_into_polygon,
    distance_to_boundary,
    point_in_polygon,
)
from app.simulation.collision import (
    WallSegment,
    resolve_overlaps,
    resolve_space_containment,
    resolve_wall_collisions,
)
from app.simulation.hazards import HazardRouteSelector, hazard_radius_at
from app.simulation.movement import SimulatedOccupant
from app.simulation.routing import DijkstraRouteSelector

def spawn_occupants(
    route_selector,
    layout: BuildingLayout,
    graph,
    radius_m: float,
    boundary_solids: list[WallSegment] | None = None,
    spaces: dict | None = None,
    doors: dict | None = None,
) -> list[SimulatedOccupant]:
    occupants: list[SimulatedOccupant] = []
    spaces = spaces if spaces is not None else {s.id: s for s in layout.spaces}
    doors = doors if doors is not None else {d.id: d for d in layout.doors}
    spacing = max(2.0 * radius_m + 0.05, 0.45)
    margin = radius_m + 0.1
    solids = boundary_solids or []

    for group in layout.occupant_groups:
        start_node = graph.space_node_ids[group.space_id]
        selector = (
            HazardRouteSelector()
            if any(hazard_radius_at(h, 0) is not None for h in (layout.flood, layout.fire))
            and isinstance(route_selector, DijkstraRouteSelector)
            else route_selector
        )
        route = selector.select_route(
            graph, start_node, preferred_exit_id=group.destination_exit_id
        )
        space = spaces[group.space_id]
        min_x, min_y, width, height = space.bbox
        usable_w = max(width - 2 * margin, spacing)
        cols = max(1, int(usable_w / spacing) + 1)
        rows = math.ceil(group.count / cols)
        node = graph.nodes[start_node]
        spawn_x = group.spawn_x if group.spawn_x is not None else node.x
        spawn_y = group.spawn_y if group.spawn_y is not None else node.y

        for i in range(group.count):
            if group.count == 1:
                ox, oy = spawn_x, spawn_y
            else:
                row = i // cols
                row_count = min(cols, group.count - row * cols)
                ox = spawn_x + (i % cols - (row_count - 1) / 2) * spacing
                oy = spawn_y + (row - (rows - 1) / 2) * spacing
                ox = min(max(ox, min_x + margin), min_x + width - margin)
                oy = min(max(oy, min_y + margin), min_y + height - margin)
                if not (
                    point_in_polygon(ox, oy, space.vertices)
                    and distance_to_boundary(ox, oy, space.vertices) >= margin - 1e-6
                ):
                    ox, oy = clamp_into_polygon(
                        ox, oy, space.vertices, inset_m=margin
                    )
            occupants.append(
                SimulatedOccupant(
                    id=f"{group.id}:{i}",
                    group_id=group.id,
                    speed_mps=group.walking_speed_mps,
                    route=list(route),
                    current_space_id=group.space_id,
                    status=OccupantStatus.TRAPPED if len(route) == 1 else OccupantStatus.ACTIVE,
                    x=ox,
                    y=oy,
                    aperture_slot=i,
                )
            )
    resolve_overlaps(occupants, radius_m, iterations=6)
    resolve_wall_collisions(occupants, solids, radius_m)
    resolve_space_containment(occupants, spaces, doors, graph, radius_m)
    return occupants
