"""Visibility / interior waypoint pathing for non-convex spaces."""

import unittest

from app.domain.building import BuildingLayout, SimulationParameters
from app.simulation.engine import SimulationEngine
from app.simulation.graph import NavigationGraphBuilder, NodeKind
from app.simulation.routing import DijkstraRouteSelector


def u_shaped_layout() -> BuildingLayout:
    """U with exits on both arms — left→right path must use reflex waypoints."""
    u_verts = [
        [2.0, 0.0],
        [14.0, 0.0],
        [14.0, 12.0],
        [10.0, 12.0],
        [10.0, 4.0],
        [6.0, 4.0],
        [6.0, 12.0],
        [2.0, 12.0],
    ]
    return BuildingLayout.model_validate(
        {
            "width": 18,
            "height": 16,
            "spaces": [
                {
                    "id": "u_room",
                    "name": "U Room",
                    "type": "room",
                    "vertices": u_verts,
                },
            ],
            "exits": [
                {
                    "id": "left",
                    "x": 4.0,
                    "y": 12.0,
                    "width": 1.0,
                    "connected_space_id": "u_room",
                },
                {
                    "id": "right",
                    "x": 12.0,
                    "y": 12.0,
                    "width": 1.2,
                    "connected_space_id": "u_room",
                },
            ],
            "occupant_groups": [
                {
                    "id": "g",
                    "name": "Crowd",
                    "count": 1,
                    "space_id": "u_room",
                    "walking_speed_mps": 1.4,
                    "destination_exit_id": "right",
                }
            ],
        }
    )


class VisibilityPathTests(unittest.TestCase):
    _defaults = {
        "door_flow_per_s": 1.2,
        "stairs_flow_per_s": 1.0,
        "exit_flow_per_s": 1.5,
        "corridor_density_per_m2": 2.0,
    }

    def test_u_room_route_uses_waypoint_not_chord_across_bay(self):
        layout = u_shaped_layout()
        graph = NavigationGraphBuilder().build(
            layout, {**self._defaults, "occupant_radius_m": 0.25}
        )
        # Path from left exit to right exit crosses the bay if taken as a chord
        route = DijkstraRouteSelector().select_route(
            graph, "exit:left", preferred_exit_id="right"
        )
        self.assertEqual(route[0], "exit:left")
        self.assertEqual(route[-1], "exit:right")
        between = route[1:-1]
        self.assertTrue(
            any(n.startswith("waypoint:") for n in between),
            f"left→right should include waypoints, got {route}",
        )

    def test_u_room_evacuates_without_stalling(self):
        layout = u_shaped_layout()
        output = SimulationEngine().run(
            layout,
            SimulationParameters(
                max_time_s=120,
                occupant_radius_m=0.25,
                frame_interval_s=0.5,
            ),
        )
        self.assertEqual(output.results.evacuated_count, 1)
        self.assertEqual(output.results.remaining_count, 0)
        self.assertTrue(
            any(
                n.startswith("waypoint:")
                for n in output.results.occupants[0].route_node_ids
            ),
            f"expected waypoint on route {output.results.occupants[0].route_node_ids}",
        )

    def test_visibility_creates_waypoint_nodes_for_reflex_corners(self):
        layout = u_shaped_layout()
        defaults = {**self._defaults, "occupant_radius_m": 0.25}
        graph = NavigationGraphBuilder().build(layout, defaults)
        wps = [n for n in graph.nodes.values() if n.kind == NodeKind.WAYPOINT]
        self.assertGreaterEqual(len(wps), 2)
        reflex_corners = [(10.0, 4.0), (6.0, 4.0)]
        for wp in wps:
            clearance = min(
                ((wp.x - cx) ** 2 + (wp.y - cy) ** 2) ** 0.5
                for cx, cy in reflex_corners
            )
            self.assertGreaterEqual(
                clearance,
                0.35,
                f"waypoint ({wp.x}, {wp.y}) too close to wall corner ({clearance:.3f} m)",
            )


if __name__ == "__main__":
    unittest.main()
