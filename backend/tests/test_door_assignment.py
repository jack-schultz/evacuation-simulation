"""Crowds use multiple viable doors before the same final exit."""
import unittest
from collections import Counter

from app.domain.building import BuildingLayout, SimulationParameters
from app.simulation.engine import SimulationEngine


def building(count=12, two_doors=True, preferred=None, fire=None):
    return BuildingLayout.model_validate({
        "width": 20, "height": 20,
        "spaces": [
            {"id": "room", "name": "Room", "type": "room",
             "vertices": [[0, 0], [12, 0], [12, 10], [0, 10]]},
            {"id": "corridor", "name": "Corridor", "type": "corridor",
             "vertices": [[0, 10], [12, 10], [12, 15], [0, 15]]},
        ],
        "doors": [
            {"id": "left", "x": 3, "y": 10, "width": 0.6,
             "connects": ["room", "corridor"]},
        ] + ([{"id": "right", "x": 9, "y": 10, "width": 0.6,
               "connects": ["room", "corridor"]}] if two_doors else []),
        "exits": [{"id": "out", "x": 6, "y": 12.5, "width": 3,
                   "connected_space_id": "corridor"}],
        "occupant_groups": [{"id": "g", "name": "People", "count": count,
                             "space_id": "room", "spawn_x": 4, "spawn_y": 7,
                             "destination_exit_id": preferred}],
        "fire": fire,
    })


def run(layout):
    return SimulationEngine().run(layout, SimulationParameters(max_time_s=60))


class DoorAssignmentTests(unittest.TestCase):
    def test_two_viable_doors_split_crowd_and_finish_sooner(self):
        single = run(building(two_doors=False))
        both = run(building())
        doors = Counter(next(n for n in person.route_node_ids if n.startswith('door:'))
                        for person in both.results.occupants)
        self.assertGreater(doors['door:left'], 0)
        self.assertGreater(doors['door:right'], 0)
        self.assertEqual({person.route_node_ids[-1] for person in both.results.occupants},
                         {'exit:out'})
        self.assertEqual(single.results.evacuated_count, 12)
        self.assertEqual(both.results.evacuated_count, 12)
        self.assertLess(both.results.total_evacuation_time_s,
                        single.results.total_evacuation_time_s)

    def test_preferred_exit_does_not_force_one_door(self):
        output = run(building(preferred='out'))
        doors = {next(n for n in person.route_node_ids if n.startswith('door:'))
                 for person in output.results.occupants}
        self.assertEqual(doors, {'door:left', 'door:right'})
        self.assertEqual(output.results.evacuated_count, 12)

    def test_shared_downstream_door_does_not_hide_parallel_door_queues(self):
        # Mirrors the Office A -> Corridor -> Office B pattern: both first
        # doors lead to one narrow downstream door and the same final exit.
        layout = BuildingLayout.model_validate({
            "width": 30, "height": 36,
            "spaces": [
                {"id": "office_a", "name": "Office A", "type": "room",
                 "vertices": [[3.5, 4], [23.5, 4], [23.5, 14], [3.5, 14]]},
                {"id": "corridor", "name": "Corridor", "type": "corridor",
                 "vertices": [[12.5, 14], [18.5, 14], [18.5, 21], [12.5, 21]]},
                {"id": "office_b", "name": "Office B", "type": "room",
                 "vertices": [[4, 21], [24, 21], [24, 31], [4, 31]]},
            ],
            "doors": [
                {"id": "left", "x": 14, "y": 14, "width": 0.9,
                 "connects": ["office_a", "corridor"]},
                {"id": "right", "x": 16, "y": 14, "width": 0.9,
                 "connects": ["office_a", "corridor"]},
                {"id": "downstream", "x": 15.5, "y": 21, "width": 0.9,
                 "connects": ["corridor", "office_b"]},
            ],
            "exits": [{"id": "out", "x": 17, "y": 31, "width": 1.2,
                       "connected_space_id": "office_b"}],
            "occupant_groups": [{"id": "g", "name": "People", "count": 45,
                                 "space_id": "office_a", "spawn_x": 15,
                                 "spawn_y": 9}],
        })
        output = SimulationEngine().run(layout, SimulationParameters(max_time_s=1))
        counts = Counter(next(n for n in person.route_node_ids
                              if n in ('door:left', 'door:right'))
                         for person in output.results.occupants)
        self.assertGreater(counts['door:left'], 10)
        self.assertGreater(counts['door:right'], 10)
        self.assertEqual({person.route_node_ids[-1]
                          for person in output.results.occupants}, {'exit:out'})

    def test_wider_door_gets_more_people_at_equal_distance(self):
        layout = building(count=24)
        layout.occupant_groups[0].spawn_x = 6
        layout.doors[0].width = 0.5
        layout.doors[1].width = 2.0
        output = run(layout)
        counts = Counter(next(n for n in person.route_node_ids if n.startswith('door:'))
                         for person in output.results.occupants)
        self.assertGreater(counts['door:right'], counts['door:left'])

    def test_unreachable_second_door_is_not_selected(self):
        layout = building()
        layout.doors[1].connects = ('room', 'isolated')
        layout.spaces.append(layout.spaces[1].model_copy(update={
            'id': 'isolated', 'name': 'Isolated',
            'vertices': [(12, 0), (18, 0), (18, 10), (12, 10)],
        }))
        output = run(layout)
        self.assertEqual({next(n for n in person.route_node_ids if n.startswith('door:'))
                          for person in output.results.occupants}, {'door:left'})

    def test_fire_on_door_prevents_selection(self):
        layout = building(fire={"x": 9, "y": 10, "radius_m": 0.5,
                                "spread_speed_mps": 0, "intensity": 50})
        output = run(layout)
        doors = {next(n for n in person.route_node_ids if n.startswith('door:'))
                 for person in output.results.occupants}
        self.assertEqual(doors, {'door:left'})
