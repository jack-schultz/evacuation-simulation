"""Linked stairs: graph portals, routes, and directed climb movement."""

import unittest

from app.domain.building import BuildingLayout, SimulationParameters
from app.simulation.engine import SimulationEngine
from app.simulation.graph import EdgeKind, NavigationGraphBuilder
from app.simulation.movement import SimulatedOccupant, SpatialMovementModel
from app.simulation.routing import DijkstraRouteSelector


def linked_floors_layout(*, link: bool = True, count: int = 1) -> BuildingLayout:
    """Two floors: room—door—stairs each, stairs optionally linked."""
    stairs_a = {
        "id": "stairs_a",
        "name": "Stairs A",
        "type": "stairs",
        "floor_id": "floor-1",
        "vertices": [[8, 2], [12, 2], [12, 6], [8, 6]],
    }
    stairs_b = {
        "id": "stairs_b",
        "name": "Stairs B",
        "type": "stairs",
        "floor_id": "floor-0",
        "vertices": [[8, 2], [12, 2], [12, 6], [8, 6]],
    }
    if link:
        stairs_a["linked_stair_id"] = "stairs_b"
        stairs_b["linked_stair_id"] = "stairs_a"

    return BuildingLayout.model_validate(
        {
            "width": 40,
            "height": 20,
            "floors": [
                {"id": "floor-0", "name": "Ground", "elevation_m": 0, "order": 0},
                {"id": "floor-1", "name": "Level 1", "elevation_m": 3.2, "order": 1},
            ],
            "spaces": [
                {
                    "id": "room_a",
                    "name": "Room A",
                    "type": "room",
                    "floor_id": "floor-1",
                    "vertices": [[0, 0], [8, 0], [8, 8], [0, 8]],
                },
                stairs_a,
                stairs_b,
                {
                    "id": "room_b",
                    "name": "Room B",
                    "type": "room",
                    "floor_id": "floor-0",
                    "vertices": [[0, 0], [8, 0], [8, 8], [0, 8]],
                },
            ],
            "doors": [
                {
                    "id": "door_a",
                    "x": 8,
                    "y": 4,
                    "width": 1.2,
                    "floor_id": "floor-1",
                    "connects": ["room_a", "stairs_a"],
                },
                {
                    "id": "door_b",
                    "x": 8,
                    "y": 4,
                    "width": 1.2,
                    "floor_id": "floor-0",
                    "connects": ["stairs_b", "room_b"],
                },
            ],
            "exits": [
                {
                    "id": "out",
                    "x": 0,
                    "y": 4,
                    "width": 1.2,
                    "floor_id": "floor-0",
                    "connected_space_id": "room_b",
                }
            ],
            "occupant_groups": [
                {
                    "id": "g",
                    "name": "Crowd",
                    "count": count,
                    "space_id": "room_a",
                    "floor_id": "floor-1",
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
                    "floors": [
                        {"id": "floor-0", "name": "G", "elevation_m": 0, "order": 0},
                        {"id": "floor-1", "name": "1", "elevation_m": 3, "order": 1},
                    ],
                    "spaces": [
                        {
                            "id": "stairs_a",
                            "name": "S",
                            "type": "stairs",
                            "floor_id": "floor-1",
                            "vertices": [[0, 0], [4, 0], [4, 4], [0, 4]],
                            "linked_stair_id": "room",
                        },
                        {
                            "id": "room",
                            "name": "R",
                            "type": "room",
                            "floor_id": "floor-0",
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

    def test_rejects_same_floor_link(self):
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
                            "linked_stair_id": "stairs_b",
                        },
                        {
                            "id": "stairs_b",
                            "name": "S2",
                            "type": "stairs",
                            "vertices": [[5, 0], [9, 0], [9, 4], [5, 4]],
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
        # Descent A(floor-1)->B(floor-0) faster than ascent
        self.assertGreater(forward[0].base_speed_factor, reverse[0].base_speed_factor)

    def test_unlinked_stairs_have_no_portal(self):
        layout = linked_floors_layout(link=False)
        graph = NavigationGraphBuilder().build(layout, self.defaults)
        a = graph.space_node_ids["stairs_a"]
        b = graph.space_node_ids["stairs_b"]
        to_b = [
            graph.edges[eid]
            for eid in graph.adjacency[a]
            if graph.edges[eid].to_id == b
        ]
        self.assertEqual(to_b, [])


class StairClimbSimTests(unittest.TestCase):
    def test_evacuee_climbs_and_reaches_exit(self):
        layout = linked_floors_layout(count=1)
        out = SimulationEngine().run(layout, SimulationParameters(max_time_s=120, frame_interval_s=0.5))
        self.assertEqual(out.results.evacuated_count, 1)
        climbing = [
            f
            for f in out.frames
            if any(o.status.value == "climbing" for o in f.occupants)
        ]
        self.assertTrue(climbing, "expected climbing frames on stairs")
        floors_seen = {
            o.floor_id
            for f in out.frames
            for o in f.occupants
        }
        self.assertIn("floor-1", floors_seen)
        self.assertIn("floor-0", floors_seen)

    def test_route_floors_span_both_storeys(self):
        layout = linked_floors_layout(count=1)
        out = SimulationEngine().run(layout, SimulationParameters(max_time_s=120, frame_interval_s=0.5))
        occ = out.results.occupants[0]
        self.assertEqual(len(occ.route_points), len(occ.route_floors))
        self.assertEqual(len(occ.route_points), len(occ.route_point_indexes))
        self.assertGreaterEqual(len(occ.route_floors), 2)
        self.assertIn("floor-1", occ.route_floors)
        self.assertIn("floor-0", occ.route_floors)
        # Walk polyline starts upstairs (door/stair) and ends at the ground exit.
        self.assertEqual(occ.route_floors[0], "floor-1")
        self.assertEqual(occ.route_floors[-1], "floor-0")
        # No room-centroid connectivity nodes in the walk polyline.
        for idx in occ.route_point_indexes:
            node_id = occ.route_node_ids[idx]
            if node_id.startswith("space:"):
                self.assertIn(
                    node_id,
                    {"space:stairs_a", "space:stairs_b"},
                    f"unexpected space node in walk path: {node_id}",
                )
            self.assertGreaterEqual(idx, 0)
            self.assertLess(idx, len(occ.route_node_ids))

    def test_frames_include_route_index(self):
        layout = linked_floors_layout(count=1)
        out = SimulationEngine().run(layout, SimulationParameters(max_time_s=120, frame_interval_s=0.5))
        self.assertTrue(out.frames)
        first = out.frames[0].occupants[0]
        self.assertEqual(first.route_index, 0)
        # Route progress advances before evacuation completes.
        max_index = max(o.route_index for f in out.frames for o in f.occupants)
        self.assertGreater(max_index, 0)


class WalkSegmentTests(unittest.TestCase):
    def test_project_onto_segment_clamps_to_endpoints(self):
        from app.simulation.movement import project_onto_segment

        self.assertEqual(project_onto_segment(0, 5, 0, 0, 10, 0), (0.0, 0.0))
        self.assertEqual(project_onto_segment(12, 3, 0, 0, 10, 0), (10.0, 0.0))
        x, y = project_onto_segment(5, 4, 0, 0, 10, 0)
        self.assertAlmostEqual(x, 5.0)
        self.assertAlmostEqual(y, 0.0)

    def test_occupant_stays_on_walk_segment_after_door(self):
        """Once past the start SPACE node, bodies stay on current→next centerline."""
        from app.simulation.graph import NavigationGraphBuilder, NodeKind
        from app.simulation.movement import is_walk_anchor

        layout = linked_floors_layout(count=2)
        out = SimulationEngine().run(
            layout,
            SimulationParameters(max_time_s=120, frame_interval_s=0.25, timestep_s=0.25),
        )
        graph = NavigationGraphBuilder().build(layout, SimulationParameters().model_dump())
        # Pick a mid-run frame where someone is between walk anchors on ground floor.
        checked = 0
        for frame in out.frames[1:]:
            for fo in frame.occupants:
                if fo.status.value in ("evacuated", "trapped", "climbing"):
                    continue
                result = next(r for r in out.results.occupants if r.id == fo.id)
                idx = fo.route_index
                if idx + 1 >= len(result.route_node_ids):
                    continue
                cur_id = result.route_node_ids[idx]
                nxt_id = result.route_node_ids[idx + 1]
                cur = graph.nodes[cur_id]
                nxt = graph.nodes[nxt_id]
                if not is_walk_anchor(cur, graph):
                    continue
                if (
                    cur.kind == NodeKind.SPACE
                    and nxt.kind == NodeKind.SPACE
                    and cur.id in graph.stair_space_node_ids
                ):
                    continue
                # Distance from point to segment should be tiny.
                ax, ay, bx, by = cur.x, cur.y, nxt.x, nxt.y
                dx, dy = bx - ax, by - ay
                len2 = dx * dx + dy * dy
                if len2 < 1e-9:
                    continue
                t = ((fo.x - ax) * dx + (fo.y - ay) * dy) / len2
                t = max(0.0, min(1.0, t))
                px, py = ax + t * dx, ay + t * dy
                dist = ((fo.x - px) ** 2 + (fo.y - py) ** 2) ** 0.5
                self.assertLess(dist, 0.08, f"{fo.id} at t={frame.t} off segment by {dist}")
                checked += 1
                if checked >= 8:
                    return
        self.assertGreater(checked, 0, "expected at least one on-segment sample")


if __name__ == "__main__":
    unittest.main()
