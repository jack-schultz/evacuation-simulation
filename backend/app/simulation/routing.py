"""Route selection strategies."""

from __future__ import annotations

import heapq
from typing import Protocol

from app.simulation.graph import NavigationGraph, NodeKind


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
    """Shortest-path route selection by distance adjusted for edge speed factors."""

    def select_route(
        self,
        graph: NavigationGraph,
        start_node_id: str,
        preferred_exit_id: str | None = None,
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
                if edge.speed_factor <= 0:
                    continue
                new_cost = cost + edge.distance_m / edge.speed_factor
                if new_cost < dist.get(nxt, float("inf")):
                    dist[nxt] = new_cost
                    prev[nxt] = node_id
                    heapq.heappush(heap, (new_cost, nxt))

        raise ValueError(
            f"No path from '{start_node_id}' to any exit"
            + (f" (preferred={preferred_exit_id})" if preferred_exit_id else "")
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
        """Keep the start space node; drop any later space centroids from the route."""
        if len(path) <= 1:
            return path
        result = [path[0]]
        for node_id in path[1:]:
            node = graph.nodes.get(node_id)
            if node is not None and node.kind == NodeKind.SPACE:
                continue
            result.append(node_id)
        return result


def edge_between(graph: NavigationGraph, a: str, b: str):
    for edge_id in graph.adjacency.get(a, []):
        edge = graph.edges[edge_id]
        if edge.to_id == b and not (edge.from_id == edge.to_id):
            return edge
    return None
