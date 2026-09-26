"""Route choice accounts for both walking time and exit queues at spawn."""
import unittest
from collections import Counter

from app.domain.building import BuildingLayout, SimulationParameters
from app.simulation.engine import SimulationEngine


def building(count=30, preferred=None, two_exits=True, flood=None):
    return BuildingLayout.model_validate({
        "width": 20, "height": 12,
        "spaces": [{"id": "room", "name": "Room", "type": "room",
                    "vertices": [[0, 0], [12, 0], [12, 10], [0, 10]]}],
        "exits": [{"id": "left", "x": 0, "y": 5, "width": 1,
                   "connected_space_id": "room"}]
        + ([{"id": "right", "x": 12, "y": 5, "width": 1,
             "connected_space_id": "room"}] if two_exits else []),
        "occupant_groups": [{"id": "group", "name": "People", "count": count,
                             "space_id": "room", "spawn_x": 4, "spawn_y": 5,
                             "destination_exit_id": preferred}],
        "flood": flood,
    })


def run(layout):
    return SimulationEngine().run(layout, SimulationParameters(max_time_s=60))


class ExitAssignmentTests(unittest.TestCase):
    def test_crowd_uses_both_exits_and_finishes_sooner(self):
        single = run(building(two_exits=False))
        distributed = run(building())
        counts = Counter(o.route_node_ids[-1] for o in distributed.results.occupants)
        self.assertGreater(counts['exit:left'], 0)
        self.assertGreater(counts['exit:right'], 0)
        self.assertEqual(distributed.results.evacuated_count, 30)
        self.assertLess(distributed.results.total_evacuation_time_s,
                        single.results.total_evacuation_time_s)

    def test_preferred_exit_is_respected_while_viable(self):
        output = run(building(count=12, preferred='left'))
        self.assertEqual({o.route_node_ids[-1] for o in output.results.occupants},
                         {'exit:left'})

    def test_blocked_preferred_exit_falls_back_to_viable_exit(self):
        output = run(building(count=6, preferred='left',
                              flood={"x": 0, "y": 5, "radius_m": 1,
                                     "spread_speed_mps": 0, "intensity": 50}))
        self.assertEqual({o.route_node_ids[-1] for o in output.results.occupants},
                         {'exit:right'})
        self.assertEqual(output.results.evacuated_count, 6)

    def test_wider_exit_takes_more_of_an_equally_distant_crowd(self):
        layout = building(count=30)
        layout.occupant_groups[0].spawn_x = 6
        layout.exits[0].width = 0.5
        layout.exits[1].width = 2.0
        output = run(layout)
        counts = Counter(o.route_node_ids[-1] for o in output.results.occupants)
        self.assertGreater(counts['exit:right'], counts['exit:left'])

    def test_one_person_keeps_shorter_clear_route(self):
        output = run(building(count=1))
        self.assertEqual(output.results.occupants[0].route_node_ids[-1], 'exit:left')
