"""Linked stairs: graph portals, routes, and teleport movement."""

import unittest

from app.domain.building import BuildingLayout, SimulationParameters
from app.simulation.engine import SimulationEngine
from app.simulation.graph import EdgeKind, NavigationGraphBuilder
from app.simulation.movement import SimulatedOccupant, SpatialMovementModel
from app.simulation.routing import DijkstraRouteSelector


def linked_floors_layout(*, link: bool = True, count: int = 1) -> BuildingLayout:
    """Two 'floors': room—door—stairs each, stairs optionally linked."""
    stairs_a = {
        "id": "stairs_a",
        "name": "Stairs A",
        "type": "stairs",
        "vertices": [[8, 2], [12, 2], [12, 6], [8, 6]],
    }
    stairs_b = {
        "id": "stairs_b",
        "name": "Stairs B",
        "type": "stairs",
        "vertices": [[20, 2], [24, 2], [24, 6], [20, 6]],
    }
    if link:
        stairs_a["linked_stair_id"] = "stairs_b"
        stairs_b["linked_stair_id"] = "stairs_a"

    return BuildingLayout.model_validate(
        {
            "width": 40,
            "height": 20,
            "spaces": [
                {
                    "id": "room_a",
                    "name": "Room A",
                    "type": "room",
                    "vertices": [[0, 0], [8, 0], [8, 8], [0, 8]],
                },
                stairs_a,
                stairs_b,
                {
                    "id": "room_b",
                    "name": "Room B",
                    "type": "room",
                    "vertices": [[24, 0], [32, 0], [32, 8], [24, 8]],
                },
            ],
            "doors": [
                {
                    "id": "door_a",
                    "x": 8,
                    "y": 4,
                    "width": 1.2,
                    "connects": ["room_a", "stairs_a"],
                },
                {
                    "id": "door_b",
                    "x": 24,
                    "y": 4,
                    "width": 1.2,
                    "connects": ["stairs_b", "room_b"],
                },
            ],
            "exits": [
                {
                    "id": "out",
                    "x": 32,
                    "y": 4,
                    "width": 1.2,
                    "connected_space_id": "room_b",
                }
            ],
            "occupant_groups": [
                {
                    "id": "g",
                    "name": "Crowd",
                    "count": count,
                    "space_id": "room_a",
                    "spawn_x": 2.0,
                    "spawn_y": 4.0,
                    "walking_speed_mps": 1.4,
                }
            ],
        }
    )


class StairLinkValidationTests(unittest.TestCase):
    def test_rejects_link_to_non_stairs(self):
        with self.assertRaises(ValueError):
            BuildingLayout.model_validate(
                {
                    "width": 20,
                    "height": 20,
                    "spaces": [
                        {
                            "id": "stairs_a",
                            "name": "S",
                            "type": "stairs",
                            "vertices": [[0, 0], [4, 0], [4, 4], [0, 4]],
                            "linked_stair_id": "room",
                        },
                        {
                            "id": "room",
                            "name": "R",
                            "type": "room",
                            "vertices": [[5, 0], [10, 0], [10, 4], [5, 4]],
                        },
                    ],
                }
            )

    def test_rejects_self_link(self):
        with self.assertRaises(ValueError):
            BuildingLayout.model_validate(
                {
                    "width": 20,
                    "height": 20,
                    "spaces": [
                        {
                            "id": "stairs_a",
                            "name": "S",
                            "type": "stairs",
                            "vertices": [[0, 0], [4, 0], [4, 4], [0, 4]],
                            "linked_stair_id": "stairs_a",
                        },
                    ],
                }
            )


class StairLinkGraphTests(unittest.TestCase):
    def setUp(self):
        self.defaults = SimulationParameters().model_dump()

    def test_linked_stairs_get_bidirectional_edge(self):
        layout = linked_floors_layout(link=True)
        graph = NavigationGraphBuilder().build(layout, self.defaults)
        a = graph.space_node_ids["stairs_a"]
        b = graph.space_node_ids["stairs_b"]
        self.assertIn(a, graph.stair_space_node_ids)
        self.assertIn(b, graph.stair_space_node_ids)

        forward = [
            graph.edges[eid]
            for eid in graph.adjacency[a]
            if graph.edges[eid].to_id == b and graph.edges[eid].from_id != b
        ]
        reverse = [
            graph.edges[eid]
            for eid in graph.adjacency[b]
            if graph.edges[eid].to_id == a and graph.edges[eid].from_id != a
        ]
        self.assertEqual(len(forward), 1)
        self.assertEqual(len(reverse), 1)
        self.assertEqual(forward[0].kind, EdgeKind.STAIRS)
        self.assertTrue(forward[0].id.startswith("edge:stair_link:"))

    def test_unpaired_stairs_have_no_stair_link(self):
        layout = linked_floors_layout(link=False)
        graph = NavigationGraphBuilder().build(layout, self.defaults)
        a = graph.space_node_ids["stairs_a"]
        b = graph.space_node_ids["stairs_b"]
        link_edges = [
            graph.edges[eid]
            for eid in graph.adjacency[a]
            if graph.edges[eid].to_id == b
            and graph.edges[eid].id.startswith("edge:stair_link:")
        ]
        self.assertEqual(link_edges, [])


class StairLinkRouteTests(unittest.TestCase):
    def setUp(self):
        self.defaults = SimulationParameters().model_dump()

    def test_route_includes_both_stair_space_nodes(self):
        layout = linked_floors_layout(link=True)
        graph = NavigationGraphBuilder().build(layout, self.defaults)
        route = DijkstraRouteSelector().select_route(
            graph, graph.space_node_ids["room_a"]
        )
        self.assertIn("space:stairs_a", route)
        self.assertIn("space:stairs_b", route)
        self.assertLess(route.index("space:stairs_a"), route.index("space:stairs_b"))
        self.assertEqual(route[-1], "exit:out")

    def test_unlinked_stairs_have_no_path(self):
        layout = linked_floors_layout(link=False)
        graph = NavigationGraphBuilder().build(layout, self.defaults)
        with self.assertRaises(ValueError):
            DijkstraRouteSelector().select_route(
                graph, graph.space_node_ids["room_a"]
            )


class StairLinkTeleportTests(unittest.TestCase):
    def setUp(self):
        self.defaults = SimulationParameters().model_dump()
        self.movement = SpatialMovementModel()

    def test_try_advance_teleports_to_linked_stair(self):
        layout = linked_floors_layout(link=True)
        graph = NavigationGraphBuilder().build(layout, self.defaults)
        a = graph.nodes[graph.space_node_ids["stairs_a"]]
        b = graph.nodes[graph.space_node_ids["stairs_b"]]

        occ = SimulatedOccupant(
            id="g:0",
            group_id="g",
            speed_mps=1.4,
            route=["space:stairs_a", "space:stairs_b", "door:door_b"],
            current_space_id="stairs_a",
            route_index=0,
            x=a.x,
            y=a.y,
        )
        self.movement.try_advance_route(occ, graph, 0.25, t=1.0)
        self.assertEqual(occ.current_space_id, "stairs_b")
        self.assertAlmostEqual(occ.x, b.x, places=5)
        self.assertAlmostEqual(occ.y, b.y, places=5)
        self.assertEqual(occ.route_index, 1)
        self.assertEqual(occ.current_node_id, "space:stairs_b")

    def test_propose_target_aims_at_current_stair_center(self):
        layout = linked_floors_layout(link=True)
        graph = NavigationGraphBuilder().build(layout, self.defaults)
        a = graph.nodes[graph.space_node_ids["stairs_a"]]
        occ = SimulatedOccupant(
            id="g:0",
            group_id="g",
            speed_mps=1.4,
            route=["space:stairs_a", "space:stairs_b"],
            current_space_id="stairs_a",
            route_index=0,
            x=a.x + 0.5,
            y=a.y,
        )
        tx, ty = self.movement.propose_target(occ, graph, 0.25, admitted=True)
        self.assertAlmostEqual(tx, a.x, places=5)
        self.assertAlmostEqual(ty, a.y, places=5)

    def test_full_evacuation_via_linked_stairs(self):
        layout = linked_floors_layout(link=True, count=1)
        params = SimulationParameters(max_time_s=120, timestep_s=0.25)
        result = SimulationEngine().run(layout, params)
        self.assertGreater(result.results.evacuated_count, 0)
        self.assertEqual(result.results.remaining_count, 0)
        occ = next(o for o in result.results.occupants if o.id == "g:0")
        self.assertTrue(occ.evacuated)
        self.assertIn("space:stairs_a", occ.route_node_ids)
        self.assertIn("space:stairs_b", occ.route_node_ids)


if __name__ == "__main__":
    unittest.main()
