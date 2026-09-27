"""Occupant spawning for the evacuation simulation."""

from __future__ import annotations

import heapq
import math

from app.domain.building import BuildingLayout, OccupantStatus, SimulationParameters
from app.domain.geometry import (
    clamp_into_polygon,
    distance_to_boundary,
    point_in_polygon,
)
from app.simulation.collision import (
    WallSegment,
    aperture_slots,
    resolve_overlaps,
    resolve_space_containment,
    resolve_wall_collisions,
)
from app.simulation.graph import NodeKind, NavigationGraphBuilder
from app.simulation.hazard_routing import HazardRoutingContext, edge_traversal_cost
from app.simulation.obstacles import free_position
from app.simulation.movement import SimulatedOccupant
from app.simulation.routing import DijkstraRouteSelector, edge_between, shortest_path_to_node

def spawn_occupants(
    route_selector,
    layout: BuildingLayout,
    graph,
    radius_m: float,
    boundary_solids: list[WallSegment] | None = None,
    spaces: dict | None = None,
    doors: dict | None = None,
    timestep_s: float = 0.25,
    defaults: dict | None = None,
    params: SimulationParameters | None = None,
) -> list[SimulatedOccupant]:
    occupants: list[SimulatedOccupant] = []
    spaces = spaces if spaces is not None else {s.id: s for s in layout.spaces}
    doors = doors if doors is not None else {d.id: d for d in layout.doors}
    spacing = max(2.0 * radius_m + 0.05, 0.45)
    margin = radius_m + 0.1
    solids = boundary_solids or []
    # Track projected availability at every door and exit aperture across groups.
    opening_slots: dict[str, list[float]] = {}
    spawn_defaults = defaults or {
        "occupant_radius_m": radius_m, "door_flow_per_s": 1.2,
        "exit_flow_per_s": 1.5, "stairs_flow_per_s": 0.8,
    }
    hazard_ctx = HazardRoutingContext.at(layout, 0.0, params, body_radius_m=radius_m)
    has_hazards = bool(
        hazard_ctx.fire_plumes or hazard_ctx.flood_plumes or hazard_ctx.smoke_plumes
    )

    for group in layout.occupant_groups:
        start_node = graph.space_node_ids[group.space_id]
        obstacles = [o for o in layout.obstacles if o.floor_id == group.floor_id]
        if obstacles:
            routes = [[start_node]]
        elif type(route_selector) is DijkstraRouteSelector:
            exit_ids = ([group.destination_exit_id] if group.destination_exit_id
                        else [e.id for e in layout.exits])
            routes = _candidate_routes(
                route_selector, graph, layout, group.space_id,
                start_node, exit_ids, hazard_ctx=hazard_ctx if has_hazards else None,
                speed_mps=group.walking_speed_mps,
            )
            if not routes:
                try:
                    routes = [route_selector.select_route(
                        graph, start_node,
                        preferred_exit_id=group.destination_exit_id,
                        layout=layout if has_hazards else None,
                        hazard_ctx=hazard_ctx if has_hazards else None,
                        speed_mps=group.walking_speed_mps,
                    )]
                except ValueError:
                    routes = [[start_node]]
        else:
            try:
                routes = [route_selector.select_route(
                    graph, start_node, preferred_exit_id=group.destination_exit_id
                )]
            except ValueError:
                routes = [[start_node]]
        space = spaces[group.space_id]
        min_x, min_y, width, height = space.bbox
        # Compact roughly-square cluster around the spawn point, not a
        # room-wide line that stretches across the full usable width.
        cols = max(1, math.ceil(math.sqrt(group.count)))
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
            if obstacles:
                position = free_position((ox, oy), space, obstacles, radius_m,
                    [o for o in occupants if o.floor_id == group.floor_id])
                if position is None:
                    raise ValueError(f"Space '{space.name}' has no free area for occupants")
                ox, oy = position
                individual_start = f"spawn:{group.id}:{i}"
                NavigationGraphBuilder().add_spawn_node(
                    graph, layout, space, position, individual_start,
                    spawn_defaults,
                )
                if type(route_selector) is DijkstraRouteSelector:
                    routes = _candidate_routes(
                        route_selector, graph, layout, group.space_id,
                        individual_start,
                        [group.destination_exit_id] if group.destination_exit_id
                        else [e.id for e in layout.exits],
                        hazard_ctx=hazard_ctx if has_hazards else None,
                        speed_mps=group.walking_speed_mps,
                    )
                else:
                    try:
                        routes = [route_selector.select_route(graph, individual_start,
                            preferred_exit_id=group.destination_exit_id)]
                    except ValueError:
                        routes = []
                routes = routes or [[individual_start]]
            route = min(
                routes,
                key=lambda candidate: _projected_route_time(
                    candidate, ox, oy, group.walking_speed_mps,
                    graph, layout, radius_m, timestep_s, opening_slots,
                    hazard_ctx=hazard_ctx if has_hazards else None,
                ),
            )
            if len(route) > 1:
                _projected_route_time(
                    route, ox, oy, group.walking_speed_mps,
                    graph, layout, radius_m, timestep_s, opening_slots,
                    reserve=True,
                    hazard_ctx=hazard_ctx if has_hazards else None,
                )
            occupants.append(
                SimulatedOccupant(
                    id=f"{group.id}:{i}",
                    group_id=group.id,
                    speed_mps=group.walking_speed_mps,
                    route=list(route),
                    current_space_id=group.space_id,
                    floor_id=group.floor_id,
                    status=OccupantStatus.TRAPPED if len(route) == 1 else OccupantStatus.ACTIVE,
                    x=ox,
                    y=oy,
                    aperture_slot=i,
                    preferred_exit_id=group.destination_exit_id,
                )
            )
    resolve_overlaps(occupants, radius_m, iterations=6)
    resolve_wall_collisions(occupants, solids, radius_m)
    resolve_space_containment(occupants, spaces, radius_m)
    for o in occupants:
        obstacles = [item for item in layout.obstacles if item.floor_id == o.floor_id]
        if obstacles:
            position = free_position((o.x, o.y), spaces[o.current_space_id], obstacles, radius_m)
            if position is not None:
                o.x, o.y = position
    return occupants


def _candidate_routes(
    selector, graph, layout, start_space_id, start_node, exit_ids,
    *, hazard_ctx=None, speed_mps=1.0,
):
    """Include shortest routes through each reachable door of the start room."""
    routes: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    def add(route):
        if route and tuple(route) not in seen and _route_is_walkable(
            route, graph, layout=layout, hazard_ctx=hazard_ctx, speed_mps=speed_mps
        ):
            routes.append(route)
            seen.add(tuple(route))

    for exit_id in exit_ids:
        try:
            add(selector.select_route(
                graph, start_node, preferred_exit_id=exit_id,
                layout=layout if hazard_ctx is not None else None,
                hazard_ctx=hazard_ctx,
                speed_mps=speed_mps,
                allow_preferred_fallback=False,
            ))
        except ValueError:
            pass

    room_nodes = {nid for nid, node in graph.nodes.items()
                  if nid == start_node or
                  (node.kind == NodeKind.WAYPOINT and node.ref_id == start_space_id)}
    for door in layout.doors:
        if start_space_id not in door.connects:
            continue
        door_node = f"door:{door.id}"
        other_space = door.connects[1] if door.connects[0] == start_space_id else door.connects[0]
        other_node = graph.space_node_ids[other_space]
        prefix = shortest_path_to_node(
            graph, start_node, door_node,
            room_nodes | {door_node},
            layout=layout if hazard_ctx is not None else None,
            hazard_ctx=hazard_ctx,
            speed_mps=speed_mps,
        )
        if prefix is None or edge_between(graph, door_node, other_node) is None:
            continue
        for exit_id in exit_ids:
            try:
                suffix = selector.select_route(
                    graph, other_node, preferred_exit_id=exit_id,
                    forbidden_node_ids=frozenset({door_node}),
                    layout=layout if hazard_ctx is not None else None,
                    hazard_ctx=hazard_ctx,
                    speed_mps=speed_mps,
                    allow_preferred_fallback=False,
                )
            except ValueError:
                continue
            # Retain the adjoining space node unless visibility provides a
            # direct opening/waypoint edge through that same adjoining space.
            tail = suffix[1:]
            direct_edge = edge_between(graph, door_node, tail[0]) if tail else None
            direct_through_other = (
                direct_edge is not None
                and direct_edge.speed_factor > 0
                and direct_edge.id.endswith(f":{other_space}")
            )
            add(prefix + (tail if direct_through_other else suffix))
    return routes


def _route_is_walkable(route, graph, *, layout=None, hazard_ctx=None, speed_mps=1.0):
    for a, b in zip(route, route[1:]):
        edge = edge_between(graph, a, b)
        if edge is None:
            return False
        if hazard_ctx is not None and layout is not None:
            if edge_traversal_cost(graph, layout, edge, hazard_ctx, speed_mps=speed_mps) is None:
                return False
        elif edge.speed_factor <= 0:
            return False
    return True


def _opening_service(node, speed_mps, layout, radius_m, timestep_s, opening_slots):
    key = node.id
    queue = opening_slots.get(key)
    if queue is None:
        elements = layout.doors if node.kind == NodeKind.DOOR else layout.exits
        opening = next(e for e in elements if e.id == node.ref_id)
        queue = [0.0] * aperture_slots(opening.width, radius_m)
        heapq.heapify(queue)
        opening_slots[key] = queue
    service_s = max(timestep_s, 2 * radius_m / speed_mps)
    return queue, service_s


def _projected_route_time(route, x, y, speed_mps, graph, layout, radius_m,
                          timestep_s, opening_slots, *, reserve=False, hazard_ctx=None):
    if len(route) <= 1:
        return float("inf"), float("inf")
    time_s = 0.0
    total_wait_s = 0.0
    clearance_time_s = 0.0

    for i, (from_id, to_id) in enumerate(zip(route, route[1:])):
        edge = edge_between(graph, from_id, to_id)
        if edge is None:
            return float("inf"), float("inf")
        if hazard_ctx is not None:
            step = edge_traversal_cost(
                graph, layout, edge, hazard_ctx, speed_mps=speed_mps
            )
            if step is None:
                return float("inf"), float("inf")
            # step already includes soft hazard slowdown + distance/penalty.
            # Split out clearance for tie-breaking consistency.
            travel_s = step
            if i == 0:
                node = graph.nodes[to_id]
                distance = math.hypot(node.x - x, node.y - y)
                soft_ratio = step / max(
                    (edge.distance_m + edge.route_penalty_m)
                    / max(speed_mps * edge.speed_factor, 1e-6),
                    1e-9,
                )
                travel_s = (distance / max(speed_mps * edge.speed_factor, 1e-6)) * soft_ratio
            time_s += travel_s
        else:
            if edge.speed_factor <= 0:
                return float("inf"), float("inf")
            node = graph.nodes[to_id]
            distance = math.hypot(node.x - x, node.y - y) if i == 0 else edge.distance_m
            travel_s = distance / (speed_mps * edge.speed_factor)
            time_s += travel_s
            clearance_time_s += edge.route_penalty_m / (speed_mps * edge.speed_factor)
            node = graph.nodes[to_id]
        node = graph.nodes[to_id]
        if node.kind in (NodeKind.DOOR, NodeKind.EXIT):
            queue, service_s = _opening_service(
                node, speed_mps, layout, radius_m, timestep_s, opening_slots
            )
            wait_s = max(0.0, queue[0] - time_s)
            total_wait_s += wait_s
            time_s = max(time_s, queue[0]) + service_s
            if reserve:
                heapq.heapreplace(queue, time_s)
    # A shared downstream bottleneck can make different first doors have the
    # same finish time. Prefer the route with less total waiting in that tie.
    route_score = time_s + clearance_time_s
    return time_s if reserve else route_score, total_wait_s
