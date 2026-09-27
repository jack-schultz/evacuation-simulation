import unittest
from app.domain.building import BuildingLayout, SimulationParameters
from app.simulation.engine import SimulationEngine


class FloodedAlternativeRouteTests(unittest.TestCase):
    def test_spreading_flood_does_not_divert_queue_to_flooded_exit(self):
        # The small obstacle lengthens the north path and its door queues.
        # The south exit seems quicker until the flood forecast is considered.
        building = BuildingLayout.model_validate({
            "width": 30, "height": 33,
            "spaces": [
                {"id": "office_a", "name": "Office A", "type": "room", "vertices": [[3.5, 4], [23.5, 4], [23.5, 14], [3.5, 14]]},
                {"id": "corridor", "name": "Corridor", "type": "corridor", "vertices": [[12.5, 14], [18.5, 14], [18.5, 21], [12.5, 21]]},
                {"id": "office_b", "name": "Office B", "type": "room", "vertices": [[4, 21], [24, 21], [24, 31], [4, 31]]},
                {"id": "upper", "name": "Upper room", "type": "room", "vertices": [[6, .5], [23, .5], [23, 2.5], [13, 2.5]]},
                {"id": "upper_hall", "name": "Upper hall", "type": "corridor", "vertices": [[16, 2.5], [16, 4], [18, 4], [18, 2.5]]},
            ],
            "doors": [
                {"id": "a", "x": 16, "y": 14, "width": .9, "connects": ["office_a", "corridor"]},
                {"id": "b", "x": 15.5, "y": 21, "width": .9, "connects": ["corridor", "office_b"]},
                {"id": "c", "x": 16.5, "y": 4, "width": .9, "connects": ["upper_hall", "office_a"]},
                {"id": "d", "x": 17, "y": 2.5, "width": .9, "connects": ["upper_hall", "upper"]},
                {"id": "e", "x": 14, "y": 14, "width": .9, "connects": ["office_a", "corridor"]},
            ],
            "exits": [
                {"id": "north", "x": 18, "y": .5, "width": 1.2, "connected_space_id": "upper"},
                {"id": "south", "x": 17, "y": 31, "width": 1.2, "connected_space_id": "office_b"},
            ],
            "obstacles": [
                {"id": "desk", "x": 8, "y": 7, "width": 4, "height": 4.5},
                {"id": "small", "x": 17.5, "y": 1.5, "width": .5, "height": .5},
            ],
            "occupant_groups": [
                {"id": "g", "name": "Group", "count": 45, "space_id": "office_a", "spawn_x": 15, "spawn_y": 12, "walking_speed_mps": 1.2},
            ],
            "flood": {"x": 6, "y": 27.5, "radius_m": 7, "spread_speed_mps": 1, "intensity": 100, "space_id": "office_b"},
        })
        result = SimulationEngine().run(
            building, SimulationParameters(max_time_s=90)
        ).results
        self.assertEqual(result.evacuated_count, 45)
        self.assertTrue(all(
            occupant.route_node_ids[-1] == "exit:north"
            for occupant in result.occupants
        ))
