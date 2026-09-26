"""Spatial door aperture / collision behaviour."""

import unittest

from app.domain.building import BuildingLayout, SimulationParameters
from app.simulation.collision import aperture_slots, dist, resolve_overlaps
from app.simulation.engine import SimulationEngine
from app.simulation.movement import SimulatedOccupant


def packed_room(door_width: float, count: int = 12) -> BuildingLayout:
    return BuildingLayout.model_validate(
        {
            "width": 20,
            "height": 20,
            "spaces": [
                {
                    "id": "room",
                    "name": "Room",
                    "type": "room",
                    "x": 0,
                    "y": 0,
                    "width": 10,
                    "height": 10,
                }
            ],
            "exits": [
                {
                    "id": "out",
                    "x": 10,
                    "y": 5,
                    "width": door_width,
                    "connected_space_id": "room",
                }
            ],
            "occupant_groups": [
                {
                    "id": "g",
                    "name": "Crowd",
                    "count": count,
                    "space_id": "room",
                    "walking_speed_mps": 1.4,
                }
            ],
        }
    )


class ApertureHelpersTests(unittest.TestCase):
    def test_aperture_slots_scales_with_width(self):
        self.assertEqual(aperture_slots(0.9, 0.25), 1)
        self.assertEqual(aperture_slots(1.2, 0.25), 2)
        self.assertEqual(aperture_slots(2.0, 0.25), 4)

    def test_resolve_overlaps_separates_coincident_bodies(self):
        a = SimulatedOccupant(
            id="a", group_id="g", speed_mps=1.0, route=["n"], x=0.0, y=0.0
        )
        b = SimulatedOccupant(
            id="b", group_id="g", speed_mps=1.0, route=["n"], x=0.0, y=0.0
        )
        resolve_overlaps([a, b], radius_m=0.25, iterations=6)
        self.assertGreaterEqual(dist(a.x, a.y, b.x, b.y), 0.5 - 1e-6)


class DoorJamTests(unittest.TestCase):
    def test_narrow_exit_serializes_passage_with_waiting(self):
        radius = 0.25
        output = SimulationEngine().run(
            packed_room(door_width=0.9, count=10),
            SimulationParameters(
                max_time_s=120,
                occupant_radius_m=radius,
                frame_interval_s=0.25,
                timestep_s=0.25,
            ),
        )
        self.assertEqual(output.results.evacuated_count, 10)
        self.assertGreater(output.results.average_wait_time_s or 0, 0)

        # At most one body should sit deep in the exit throat at once
        exit_x, exit_y = 10.0, 5.0
        throat = max(radius * 2.5, 0.6)
        max_in_throat = 0
        for frame in output.frames:
            in_throat = 0
            for o in frame.occupants:
                if o.status == "evacuated":
                    continue
                if dist(o.x, o.y, exit_x, exit_y) <= throat:
                    in_throat += 1
            max_in_throat = max(max_in_throat, in_throat)
        self.assertLessEqual(max_in_throat, aperture_slots(0.9, radius))

    def test_wide_exit_evacuates_faster_than_narrow(self):
        params = SimulationParameters(
            max_time_s=180,
            occupant_radius_m=0.25,
            frame_interval_s=0.5,
        )
        narrow = SimulationEngine().run(packed_room(0.9, count=12), params).results
        wide = SimulationEngine().run(packed_room(2.0, count=12), params).results
        self.assertEqual(narrow.evacuated_count, 12)
        self.assertEqual(wide.evacuated_count, 12)
        self.assertLess(
            wide.total_evacuation_time_s or 0,
            narrow.total_evacuation_time_s or 0,
        )

    def test_bodies_do_not_stack_on_identical_points_mid_sim(self):
        radius = 0.25
        output = SimulationEngine().run(
            packed_room(door_width=0.9, count=8),
            SimulationParameters(max_time_s=60, occupant_radius_m=radius),
        )
        min_sep = 2 * radius - 0.05  # allow tiny numerical overlap after rounding
        for frame in output.frames:
            active = [o for o in frame.occupants if o.status != "evacuated"]
            for i in range(len(active)):
                for j in range(i + 1, len(active)):
                    d = dist(active[i].x, active[i].y, active[j].x, active[j].y)
                    self.assertGreaterEqual(
                        d,
                        min_sep,
                        f"overlap at t={frame.t}: {active[i].id} and {active[j].id}",
                    )


if __name__ == "__main__":
    unittest.main()
