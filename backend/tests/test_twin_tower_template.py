"""Twin Towers 20m seed template: rooms, offset stairs, and runnable routes."""

import unittest

from app.domain.building import SimulationParameters, SpaceType
from app.services.seed import create_twin_tower_template
from app.simulation.engine import SimulationEngine
from app.simulation.graph import NavigationGraphBuilder
from app.simulation.routing import DijkstraRouteSelector


class TwinTowerTemplateTests(unittest.TestCase):
    def test_geometry_and_room_layout(self):
        layout = create_twin_tower_template()

        self.assertEqual(layout.name, "Twin Towers 20m")
        self.assertEqual(layout.width, 54.0)
        self.assertEqual(layout.height, 24.0)
        self.assertEqual(len(layout.floors), 7)
        self.assertEqual(len(layout.exits), 2)

        for floor_index in range(7):
            for tower in ("west", "east"):
                for zone in ("top", "bottom", "left", "right", "middle"):
                    space = next(s for s in layout.spaces if s.id == f"{tower}_{zone}_{floor_index}")
                    self.assertEqual(space.type, SpaceType.ROOM)
                down = next(s for s in layout.spaces if s.id == f"{tower}_stair_down_{floor_index}")
                up = next(s for s in layout.spaces if s.id == f"{tower}_stair_up_{floor_index}")
                self.assertEqual(down.type, SpaceType.STAIRS)
                self.assertEqual(up.type, SpaceType.STAIRS)
                # Walk gap between south (down) and north (up) flights
                self.assertGreater(min(y for _, y in up.vertices) - max(y for _, y in down.vertices), 2.5)

    def test_stair_links_force_crossing_each_floor(self):
        layout = create_twin_tower_template()
        by_id = {s.id: s for s in layout.spaces}

        for tower in ("west", "east"):
            self.assertIsNone(by_id[f"{tower}_stair_down_0"].linked_stair_id)
            self.assertIsNone(by_id[f"{tower}_stair_up_6"].linked_stair_id)
            for floor_index in range(1, 7):
                down = by_id[f"{tower}_stair_down_{floor_index}"]
                self.assertEqual(down.linked_stair_id, f"{tower}_stair_up_{floor_index - 1}")
            for floor_index in range(6):
                up = by_id[f"{tower}_stair_up_{floor_index}"]
                self.assertEqual(up.linked_stair_id, f"{tower}_stair_down_{floor_index + 1}")

    def test_every_occupant_group_has_a_route_to_an_exit(self):
        layout = create_twin_tower_template()
        graph = NavigationGraphBuilder().build(
            layout, SimulationParameters().model_dump()
        )
        selector = DijkstraRouteSelector()
        exit_nodes = {f"exit:{exit_.id}" for exit_ in layout.exits}

        for group in layout.occupant_groups:
            with self.subTest(group=group.id):
                route = selector.select_route(
                    graph, graph.space_node_ids[group.space_id]
                )
                self.assertTrue(route[-1].startswith("exit:"))
                self.assertIn(route[-1], exit_nodes)

    def test_upper_floor_occupant_evacuates_via_offset_stairs(self):
        layout = create_twin_tower_template()
        upper_group = next(
            group
            for group in layout.occupant_groups
            if group.id == "occupants_west_top_6"
        )
        layout.occupant_groups = [upper_group.model_copy(update={"count": 1})]

        output = SimulationEngine().run(
            layout,
            SimulationParameters(
                max_time_s=300,
                timestep_s=0.25,
                frame_interval_s=5,
            ),
        )

        self.assertEqual(output.results.evacuated_count, 1)
        route = output.results.occupants[0].route_node_ids
        self.assertEqual(route[-1], "exit:exit_west")
        # Must visit both stair flights on an intermediate floor (walk between sets)
        self.assertTrue(
            any("stair_up_3" in node for node in route)
            and any("stair_down_3" in node for node in route)
        )


if __name__ == "__main__":
    unittest.main()
