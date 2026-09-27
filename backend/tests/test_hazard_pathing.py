"""Dynamic hazard pathing: local skirts and mid-run exit switches."""

import math
import unittest

from app.domain.building import BuildingLayout, SimulationParameters, Space, SpaceType
from app.simulation.engine import SimulationEngine
from app.simulation.hazard_local_path import plan_local_path
from app.simulation.hazard_routing import HazardRoutingContext


class LocalSkirtTests(unittest.TestCase):
    def test_local_path_skirts_fire_instead_of_crossing(self):
        space = Space(
            id="room",
            name="Room",
            type=SpaceType.ROOM,
            vertices=[(0, 0), (20, 0), (20, 20), (0, 20)],
        )
        layout = BuildingLayout.model_validate({
            "width": 20,
            "height": 20,
            "spaces": [{
                "id": "room", "name": "Room", "type": "room",
                "vertices": [[0, 0], [20, 0], [20, 20], [0, 20]],
            }],
            "exits": [{
                "id": "e", "x": 20, "y": 10, "width": 1,
                "connected_space_id": "room", "flow_rate_per_s": 100,
            }],
            "occupant_groups": [{"id": "g", "name": "G", "count": 1, "space_id": "room"}],
            "fires": [{
                "id": "f1", "x": 10, "y": 10, "radius_m": 1.5,
                "spread_speed_mps": 0, "intensity": 80, "emit_smoke": False,
            }],
        })
        ctx = HazardRoutingContext.at(layout, 0.0, SimulationParameters())
        start, goal = (2.0, 10.0), (18.0, 10.0)
        # Direct chord would cross the fire clearance disk.
        result = plan_local_path(
            start, goal, space, "floor-0", [], ctx, body_radius=0.25
        )
        self.assertTrue(result.reachable)
        self.assertIsNotNone(result.first_hop)
        self.assertFalse(result.direct)
        hx, hy = result.first_hop
        # First hop stays outside the hard clearance ring around the fire.
        clearance = ctx.hard_fire_radius_extra
        self.assertGreater(
            math.hypot(hx - 10.0, hy - 10.0),
            1.5 + clearance - 0.2,
        )


class ExpandingFireReplanTests(unittest.TestCase):
    def test_expanding_fire_switches_exit_mid_run(self):
        # Near exit starts clear; fire grows onto it before the walker arrives.
        # Far exit stays reachable so they should switch and evacuate.
        building = BuildingLayout.model_validate({
            "width": 24,
            "height": 16,
            "spaces": [{
                "id": "room", "name": "Room", "type": "room",
                "vertices": [[0, 0], [20, 0], [20, 12], [0, 12]],
            }],
            "exits": [
                {"id": "near", "x": 19, "y": 2, "width": 1,
                 "connected_space_id": "room", "flow_rate_per_s": 100},
                {"id": "far", "x": 1, "y": 2, "width": 1,
                 "connected_space_id": "room", "flow_rate_per_s": 100},
            ],
            "occupant_groups": [{
                "id": "g", "name": "People", "count": 1, "space_id": "room",
                "spawn_x": 10, "spawn_y": 2, "walking_speed_mps": 1.2,
                "destination_exit_id": "near",
            }],
            "fires": [{
                "id": "f1", "x": 19, "y": 2, "radius_m": 0.1,
                "spread_speed_mps": 0.35, "intensity": 90, "emit_smoke": False,
            }],
        })
        output = SimulationEngine().run(
            building,
            SimulationParameters(max_time_s=40, timestep_s=0.25, frame_interval_s=0.5),
        )
        self.assertEqual(output.results.evacuated_count, 1)
        self.assertEqual(output.results.occupants[0].route_node_ids[-1], "exit:far")
