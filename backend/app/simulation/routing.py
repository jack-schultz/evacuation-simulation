"""Route selection strategies."""

from __future__ import annotations

import heapq
from typing import Protocol

from app.domain.building import BuildingLayout
from app.simulation.graph import NavigationGraph, NodeKind
from app.simulation.hazard_routing import (
    HazardRoutingContext,
    edge_traversal_cost,
    forbidden_fire_node_ids,
)


class RouteSelector(Protocol):
    def select_route(
        self,
        graph: NavigationGraph,
        start_node_id: str,
        preferred_exit_id: str | None = None,
    ) -> list[str]:
        """Return ordered node IDs from start to an exit (inclusive)."""
        ...


class DijkstraRouteSelector:
    """Shortest-path route selection by travel time, with optional hazard costs."""

    def select_route(
        self,
        graph: NavigationGraph,
        start_node_id: str,
        preferred_exit_id: str | None = None,
        *,
        forbidden_node_ids: frozenset[str] = frozenset(),
        layout: BuildingLayout | None = None,
        hazard_ctx: HazardRoutingContext | None = None,
        speed_mps: float = 1.0,
        allow_preferred_fallback: bool = True,
    ) -> list[str]:
        if start_node_id not in graph.nodes:
            raise ValueError(f"Unknown start node '{start_node_id}'")

        targets = set(graph.exit_node_ids)
        if preferred_exit_id:
            preferred_node = f"exit:{preferred_exit_id}"
            if preferred_node in targets:
                targets = {preferred_node}

        if not targets:
            raise ValueError("Building has no exits")

        blocked = set(forbidden_node_ids)
        if hazard_ctx is not None and layout is not None:
            blocked |= set(forbidden_fire_node_ids(graph, layout, hazard_ctx))

        try:
            return self._dijkstra(
                graph,
                start_node_id,
                targets,
                frozenset(blocked),
                layout,
                hazard_ctx,
                speed_mps,
            )
        except ValueError:
            if (
                preferred_exit_id
                and allow_preferred_fallback
                and len(graph.exit_node_ids) > 1
            ):
                # Preferred exit unreachable (e.g. on fire) — try any exit.
                return self._dijkstra(
                    graph,
                    start_node_id,
                    set(graph.exit_node_ids),
                    frozenset(blocked),
                    layout,
                    hazard_ctx,
                    speed_mps,
                )
            raise

    def _dijkstra(
        self,
        graph: NavigationGraph,
        start_node_id: str,
        targets: set[str],
        forbidden_node_ids: frozenset[str],
        layout: BuildingLayout | None,
        hazard_ctx: HazardRoutingContext | None,
        speed_mps: float,
    ) -> list[str]:
        dist: dict[str, float] = {start_node_id: 0.0}
        prev: dict[str, str | None] = {start_node_id: None}
        heap: list[tuple[float, str]] = [(0.0, start_node_id)]

        while heap:
            cost, node_id = heapq.heappop(heap)
            if cost > dist.get(node_id, float("inf")):
                continue
            if node_id in targets:
                return self._strip_intermediate_spaces(
                    graph, self._reconstruct(prev, node_id)
                )

            for edge_id in graph.adjacency.get(node_id, []):
                edge = graph.edges[edge_id]
                if edge.distance_m <= 0 and edge.from_id == edge.to_id:
                    continue
                nxt = edge.to_id
                if nxt in forbidden_node_ids:
                    continue
                if hazard_ctx is not None and layout is not None:
                    step = edge_traversal_cost(
                        graph, layout, edge, hazard_ctx, speed_mps=speed_mps
                    )
                    if step is None:
                        continue
                    new_cost = cost + step
                else:
                    if edge.speed_factor <= 0:
                        continue
                    new_cost = (
                        cost
                        + (edge.distance_m + edge.route_penalty_m) / edge.speed_factor
                    )
                if new_cost < dist.get(nxt, float("inf")):
                    dist[nxt] = new_cost
                    prev[nxt] = node_id
                    heapq.heappush(heap, (new_cost, nxt))

        raise ValueError(
            f"No path from '{start_node_id}' to any exit"
        )

    @staticmethod
    def _reconstruct(prev: dict[str, str | None], end: str) -> list[str]:
        path: list[str] = []
        cur: str | None = end
        while cur is not None:
            path.append(cur)
            cur = prev.get(cur)
        path.reverse()
        return path

    @staticmethod
    def _strip_intermediate_spaces(graph: NavigationGraph, path: list[str]) -> list[str]:
        """Drop centroids only when a walkable visibility shortcut exists."""
        if len(path) <= 1:
            return path
        result = [path[0]]
        for index, node_id in enumerate(path[1:], 1):
            node = graph.nodes.get(node_id)
            if (
                node is not None
                and node.kind == NodeKind.SPACE
                and node_id not in graph.stair_space_node_ids
                and index + 1 < len(path)
                and (shortcut := edge_between(graph, result[-1], path[index + 1])) is not None
                and shortcut.speed_factor > 0
            ):
                continue
            result.append(node_id)
        return result


def edge_between(graph: NavigationGraph, a: str, b: str):
    for edge_id in graph.adjacency.get(a, []):
        edge = graph.edges[edge_id]
        if edge.to_id == b and not (edge.from_id == edge.to_id):
            return edge
    return None


def shortest_path_to_node(
    graph: NavigationGraph,
    start_node_id: str,
    target_node_id: str,
    allowed_node_ids: set[str],
    *,
    layout: BuildingLayout | None = None,
    hazard_ctx: HazardRoutingContext | None = None,
    speed_mps: float = 1.0,
) -> list[str] | None:
    """Find a path to an opening without leaving the starting space first."""
    distance = {start_node_id: 0.0}
    previous: dict[str, str | None] = {start_node_id: None}
    heap = [(0.0, start_node_id)]
    while heap:
        cost, node_id = heapq.heappop(heap)
        if cost > distance.get(node_id, float("inf")):
            continue
        if node_id == target_node_id:
            return DijkstraRouteSelector._reconstruct(previous, node_id)
        for edge_id in graph.adjacency.get(node_id, []):
            edge = graph.edges[edge_id]
            if edge.to_id not in allowed_node_ids:
                continue
            if hazard_ctx is not None and layout is not None:
                step = edge_traversal_cost(
                    graph, layout, edge, hazard_ctx, speed_mps=speed_mps
                )
                if step is None:
                    continue
                next_cost = cost + step
            else:
                if edge.speed_factor <= 0:
                    continue
                next_cost = (
                    cost + (edge.distance_m + edge.route_penalty_m) / edge.speed_factor
                )
            if next_cost < distance.get(edge.to_id, float("inf")):
                distance[edge.to_id] = next_cost
                previous[edge.to_id] = node_id
                heapq.heappush(heap, (next_cost, edge.to_id))
    return None


def replan_route_from_occupant(
    selector: DijkstraRouteSelector,
    graph: NavigationGraph,
    layout: BuildingLayout,
    hazard_ctx: HazardRoutingContext,
    start_node_id: str,
    preferred_exit_id: str | None,
    speed_mps: float,
) -> list[str] | None:
    """Compute a new macro route avoiding fire-blocked openings at ``hazard_ctx.t``."""
    try:
        return selector.select_route(
            graph,
            start_node_id,
            preferred_exit_id=preferred_exit_id,
            layout=layout,
            hazard_ctx=hazard_ctx,
            speed_mps=speed_mps,
            allow_preferred_fallback=True,
        )
    except ValueError:
        return None
