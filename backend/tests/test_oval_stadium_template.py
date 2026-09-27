"""Oval stadium template layout, vertical connections, and seed registration."""

import unittest

from app.domain.building import SimulationParameters
from app.services.seed import create_oval_stadium_template
from app.simulation.engine import SimulationEngine
from app.simulation.graph import NavigationGraphBuilder
from app.simulation.routing import DijkstraRouteSelector


class OvalStadiumTemplateTests(unittest.TestCase):
    def test_four_floors_and_exit_distribution(self):
        layout = create_oval_stadium_template()

        self.assertEqual(layout.name, "Oval Stadium")
        self.assertEqual(
            [(floor.name, floor.order) for floor in layout.floors],
            [("Basement", 0), ("Ground", 1), ("Upper Concourse", 2), ("Upper Deck", 3)],
        )
        for floor_id in ("floor-0", "floor-1"):
            self.assertEqual(sum(exit_.floor_id == floor_id for exit_ in layout.exits), 2)
        self.assertFalse(any(exit_.floor_id in ("floor-2", "floor-3") for exit_ in layout.exits))

    def test_every_occupied_section_has_a_route_to_a_lower_floor_exit(self):
        layout = create_oval_stadium_template()
        graph = NavigationGraphBuilder().build(
            layout, SimulationParameters().model_dump()
        )
        selector = DijkstraRouteSelector()

        for group in layout.occupant_groups:
            with self.subTest(group=group.id):
                route = selector.select_route(
                    graph, graph.space_node_ids[group.space_id]
                )
                self.assertTrue(route[-1].startswith("exit:"))
                self.assertIn(route[-1], {f"exit:{exit_.id}" for exit_ in layout.exits})

    def test_upper_deck_occupant_evacuates_through_linked_stairs(self):
        layout = create_oval_stadium_template()
        upper_group = next(
            group
            for group in layout.occupant_groups
            if group.floor_id == "floor-3" and "North-East" in group.name
        )
        layout.occupant_groups = [upper_group.model_copy(update={"count": 1})]

        output = SimulationEngine().run(
            layout,
            SimulationParameters(
                max_time_s=120,
                timestep_s=0.25,
                frame_interval_s=5,
            ),
        )

        self.assertEqual(output.results.evacuated_count, 1)
        self.assertEqual(output.results.occupants[0].route_node_ids[-1], "exit:stadium_exit_1_east")


if __name__ == "__main__":
    unittest.main()