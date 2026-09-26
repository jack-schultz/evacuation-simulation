"""Time-dependent radial flood scenario (not a hydraulic solver)."""
from app.domain.building import FloodEmergency
from app.simulation.graph import NavigationGraph, NodeKind
from app.simulation.routing import DijkstraRouteSelector


def flood_radius_at(flood: FloodEmergency | None, t: float) -> float | None:
    if flood is None or not flood.enabled or flood.intensity == 0:
        return None
    return flood.radius_m + flood.spread_speed_mps * max(t, 0.0)


def segment_speed_factor(flood, radius, x, y, target_x, target_y, *, is_exit=False):
    """Reject entry/crossing; allow slowed outward escape from the wet area.

    Movement calls this with the person's current position, so water behind
    them cannot block or slow their remaining dry path.
    """
    if radius is None:
        return 1.0
    radius_sq = radius * radius
    ax, ay = x - flood.x, y - flood.y
    dx, dy = target_x - x, target_y - y
    length_sq = dx * dx + dy * dy
    start_sq = ax * ax + ay * ay
    end_sq = (target_x - flood.x) ** 2 + (target_y - flood.y) ** 2
    progress = ax * dx + ay * dy
    fraction = max(0.0, min(1.0, -progress / length_sq)) if length_sq else 0.0
    closest_sq = (ax + fraction * dx) ** 2 + (ay + fraction * dy) ** 2
    if closest_sq > radius_sq:
        return 1.0
    if is_exit and end_sq <= radius_sq:
        return 0.0
    if start_sq <= radius_sq and progress >= 0 and end_sq > start_sq:
        return max(0.1, 1.0 - flood.intensity / 100)
    return 0.0


def apply_flood(graph: NavigationGraph, flood: FloodEmergency | None, t: float = 0.0) -> None:
    radius = flood_radius_at(flood, t)
    for edge in graph.edges.values():
        a, b = graph.nodes[edge.from_id], graph.nodes[edge.to_id]
        edge.speed_factor = segment_speed_factor(
            flood, radius, a.x, a.y, b.x, b.y, is_exit=b.kind == NodeKind.EXIT
        )


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
