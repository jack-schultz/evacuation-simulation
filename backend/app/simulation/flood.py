"""Static flood effects on graph routes (illustrative, not hydrodynamics)."""
from app.domain.building import FloodEmergency
from app.simulation.graph import NavigationGraph, NodeKind
from app.simulation.routing import DijkstraRouteSelector


def apply_flood(graph: NavigationGraph, flood: FloodEmergency | None) -> None:
    if flood is None or not flood.enabled or flood.intensity == 0:
        return
    radius_sq = flood.radius_m ** 2
    for edge in graph.edges.values():
        a, b = graph.nodes[edge.from_id], graph.nodes[edge.to_id]
        dx, dy = b.x - a.x, b.y - a.y
        length_sq = dx * dx + dy * dy
        ax, ay = a.x - flood.x, a.y - flood.y
        start_distance_sq = ax * ax + ay * ay
        end_distance_sq = (b.x - flood.x) ** 2 + (b.y - flood.y) ** 2
        radial_progress = ax * dx + ay * dy
        fraction = max(0.0, min(1.0, -radial_progress / length_sq)) if length_sq else 0.0
        closest_distance_sq = (ax + fraction * dx) ** 2 + (ay + fraction * dy) ** 2
        if closest_distance_sq > radius_sq:
            continue

        # A time penalty alone still permits routes into danger. Block entry at
        # every positive intensity, including segments crossing the flood with
        # both endpoints outside it. Flooded exits can never be destinations.
        flooded_exit = b.kind == NodeKind.EXIT and end_distance_sq <= radius_sq
        escaping = (
            start_distance_sq <= radius_sq
            and radial_progress >= 0
            and end_distance_sq > start_distance_sq
            and not flooded_exit
        )
        # Direction matters: allow occupants already inside to move steadily
        # outward, but never permit the reverse journey back into the flood.
        edge.speed_factor = max(0.1, 1.0 - flood.intensity / 100) if escaping else 0.0



class FloodRouteSelector(DijkstraRouteSelector):
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
