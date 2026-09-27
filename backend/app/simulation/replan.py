"""Mid-run macro route updates when fire blocks the current path."""

from __future__ import annotations

from app.domain.building import BuildingLayout, OccupantStatus, SimulationParameters
from app.simulation.graph import NavigationGraph, NodeKind
from app.simulation.hazard_local_path import local_path_to_node
from app.simulation.hazard_routing import (
    HazardRoutingContext,
    remaining_route_fire_blocked,
)
from app.simulation.movement import SimulatedOccupant
from app.simulation.routing import DijkstraRouteSelector, replan_route_from_occupant


def _start_node_for_replan(occ: SimulatedOccupant, graph: NavigationGraph) -> str:
    """Anchor replan at the current space (or stair) node."""
    if occ.current_space_id:
        nid = graph.space_node_ids.get(occ.current_space_id)
        if nid is not None:
            return nid
    if occ.current_node_id in graph.nodes:
        return occ.current_node_id
    return occ.route[min(occ.route_index, len(occ.route) - 1)]


def _local_leg_impassable(
    occ: SimulatedOccupant,
    graph: NavigationGraph,
    ctx: HazardRoutingContext,
    radius_m: float,
) -> bool:
    nxt = occ.next_node_id
    if nxt is None:
        return False
    waypoint = graph.nodes.get(nxt)
    space = graph.spaces.get(occ.current_space_id) if occ.current_space_id else None
    if waypoint is None or space is None:
        return False
    # Stair↔stair climb legs are not local room skirts.
    cur = graph.nodes.get(occ.current_node_id)
    if (
        cur is not None
        and cur.kind == NodeKind.SPACE
        and waypoint.kind == NodeKind.SPACE
        and cur.id in graph.stair_space_node_ids
        and waypoint.id in graph.stair_space_node_ids
    ):
        return remaining_route_fire_blocked(
            graph, ctx.layout, ctx, occ.route, occ.route_index
        )
    local = local_path_to_node(
        (occ.x, occ.y),
        waypoint,
        space,
        occ.floor_id,
        graph,
        ctx,
        radius_m,
    )
    return not local.reachable


def maybe_replan_occupant(
    occ: SimulatedOccupant,
    graph: NavigationGraph,
    layout: BuildingLayout,
    ctx: HazardRoutingContext,
    selector: DijkstraRouteSelector,
    radius_m: float,
) -> bool:
    """Replace ``occ.route`` when fire blocks the current plan. Returns True if changed."""
    if occ.status in (
        OccupantStatus.EVACUATED,
        OccupantStatus.TRAPPED,
        OccupantStatus.CLIMBING,
    ):
        return False
    if len(occ.route) <= 1:
        return False

    needs = remaining_route_fire_blocked(
        graph, layout, ctx, occ.route, occ.route_index
    ) or _local_leg_impassable(occ, graph, ctx, radius_m)
    if not needs:
        return False

    start = _start_node_for_replan(occ, graph)
    new_route = replan_route_from_occupant(
        selector,
        graph,
        layout,
        ctx,
        start,
        preferred_exit_id=occ.preferred_exit_id,
        speed_mps=occ.speed_mps,
    )
    if not new_route or len(new_route) <= 1:
        occ.status = OccupantStatus.TRAPPED
        occ.route = [occ.current_node_id]
        occ.route_index = 0
        return True

    # Prefer keeping continuity: if current node is on the new route, resume there.
    if occ.current_node_id in new_route:
        idx = new_route.index(occ.current_node_id)
        occ.route = new_route
        occ.route_index = idx
    else:
        occ.route = new_route
        occ.route_index = 0
    occ.progress_on_edge = 0.0
    occ.hazard_detour = False
    return True


def replan_blocked_occupants(
    occupants: list[SimulatedOccupant],
    graph: NavigationGraph,
    layout: BuildingLayout,
    params: SimulationParameters,
    t: float,
    route_selector,
) -> None:
    """Exit-switch when expanding fire seals the current macro route."""
    ctx = HazardRoutingContext.at(layout, t, params)
    if not ctx.fire_plumes:
        return
    if type(route_selector) is not DijkstraRouteSelector:
        return

    for occ in occupants:
        maybe_replan_occupant(
            occ, graph, layout, ctx, route_selector, params.occupant_radius_m
        )
