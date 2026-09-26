"""Occupant spawning for the evacuation simulation."""

from __future__ import annotations

import heapq
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
from app.simulation.routing import DijkstraRouteSelector, edge_between

def spawn_occupants(
    route_selector,
    layout: BuildingLayout,
    graph,
    radius_m: float,
    boundary_solids: list[WallSegment] | None = None,
    spaces: dict | None = None,
    doors: dict | None = None,
    timestep_s: float = 0.25,
) -> list[SimulatedOccupant]:
    occupants: list[SimulatedOccupant] = []
    spaces = spaces if spaces is not None else {s.id: s for s in layout.spaces}
    doors = doors if doors is not None else {d.id: d for d in layout.doors}
    spacing = max(2.0 * radius_m + 0.05, 0.45)
    margin = radius_m + 0.1
    solids = boundary_solids or []
    # Each exit aperture has independent service slots. Their next available
    # times estimate the queue that a newly spawned person would join.
    exit_slots: dict[str, list[float]] = {}

    for group in layout.occupant_groups:
        start_node = graph.space_node_ids[group.space_id]
        selector = (
            HazardRouteSelector()
            if any(hazard_radius_at(h, 0) is not None for h in (layout.flood, layout.fire))
            and isinstance(route_selector, DijkstraRouteSelector)
            else route_selector
        )
        routes: list[list[str]] = []
        if type(route_selector) is DijkstraRouteSelector:
            # A preferred exit is binding while it remains reachable. When a
            # hazard blocks it, try the other viable exits as before.
            exit_ids = ([group.destination_exit_id] if group.destination_exit_id
                        else [e.id for e in layout.exits])
            for exit_id in exit_ids:
                try:
                    routes.append(route_selector.select_route(
                        graph, start_node, preferred_exit_id=exit_id
                    ))
                except ValueError:
                    pass
            if not routes and group.destination_exit_id and selector is not route_selector:
                for exit_ in layout.exits:
                    try:
                        routes.append(route_selector.select_route(
                            graph, start_node, preferred_exit_id=exit_.id
                        ))
                    except ValueError:
                        pass
            # Keep the existing no-path behavior: ordinary routing raises,
            # while hazard routing marks stranded occupants as trapped.
            if not routes:
                routes = [selector.select_route(
                    graph, start_node, preferred_exit_id=group.destination_exit_id
                )]
        else:
            # Respect injected routing strategies without assuming they expose
            # paths to individual exits.
            routes = [selector.select_route(
                graph, start_node, preferred_exit_id=group.destination_exit_id
            )]
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
            route = min(
                routes,
                key=lambda candidate: _projected_exit_time(
                    candidate, ox, oy, group.walking_speed_mps,
                    graph, layout, radius_m, timestep_s, exit_slots,
                ),
            )
            if len(route) > 1:
                _reserve_exit_slot(
                    route, ox, oy, group.walking_speed_mps,
                    graph, layout, radius_m, timestep_s, exit_slots,
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


def _route_travel_time(route, x, y, speed_mps, graph):
    """Estimate travel from the actual spawn point along a fixed graph route."""
    total = 0.0
    for i, (from_id, to_id) in enumerate(zip(route, route[1:])):
        edge = edge_between(graph, from_id, to_id)
        if edge is None or edge.speed_factor <= 0:
            return float("inf")
        node = graph.nodes[to_id]
        distance = math.hypot(node.x - x, node.y - y) if i == 0 else edge.distance_m
        total += distance / (speed_mps * edge.speed_factor)
    return total


def _exit_service(route, speed_mps, graph, layout, radius_m, timestep_s, exit_slots):
    exit_id = graph.nodes[route[-1]].ref_id
    queue = exit_slots.get(exit_id)
    if queue is None:
        exit_ = next(e for e in layout.exits if e.id == exit_id)
        slots = max(1, int(exit_.width / (2 * radius_m)))
        queue = [0.0] * slots
        heapq.heapify(queue)
        exit_slots[exit_id] = queue
    # One person needs roughly a body diameter to clear an aperture. The
    # timestep is a lower bound because the engine admits by discrete steps.
    service_s = max(timestep_s, 2 * radius_m / speed_mps)
    return queue, service_s


def _projected_exit_time(route, x, y, speed_mps, graph, layout, radius_m, timestep_s, exit_slots):
    if len(route) <= 1:
        return float("inf")
    arrival = _route_travel_time(route, x, y, speed_mps, graph)
    queue, service_s = _exit_service(
        route, speed_mps, graph, layout, radius_m, timestep_s, exit_slots
    )
    return max(arrival, queue[0]) + service_s


def _reserve_exit_slot(route, x, y, speed_mps, graph, layout, radius_m, timestep_s, exit_slots):
    arrival = _route_travel_time(route, x, y, speed_mps, graph)
    queue, service_s = _exit_service(
        route, speed_mps, graph, layout, radius_m, timestep_s, exit_slots
    )
    heapq.heapreplace(queue, max(arrival, queue[0]) + service_s)
