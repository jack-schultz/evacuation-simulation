"""Smoke is produced by fire (emit_smoke): soft slowdown, visibility, stair spread."""

import unittest

from app.domain.building import (
    BuildingLayout,
    FireEmergency,
    SimulationParameters,
    SmokeEmergency,
)
from app.simulation.engine import SimulationEngine
from app.simulation.hazards import (
    SMOKE_SPREAD_MULTIPLIER,
    active_fire_plumes,
    active_smoke_plumes,
    resolve_origin_smoke,
    smoke_speed_factor,
)
from tests.test_stair_link import linked_floors_layout


class SmokeUnitTests(unittest.TestCase):
    def test_smoke_never_hard_blocks(self):
        smoke = SmokeEmergency(
            enabled=True, x=5, y=5, radius_m=3, intensity=100, floor_id="floor-0"
        )
        self.assertGreater(smoke_speed_factor(smoke, 3.0, 5.0, 5.0), 0.0)
        self.assertLess(smoke_speed_factor(smoke, 3.0, 5.0, 5.0), 1.0)

    def test_fire_emit_smoke_synthesizes_faster_plume(self):
        layout = BuildingLayout.model_validate(
            {
                "width": 20,
                "height": 20,
                "spaces": [
                    {
                        "id": "r",
                        "name": "R",
                        "type": "room",
                        "vertices": [[0, 0], [10, 0], [10, 10], [0, 10]],
                    }
                ],
                "exits": [
                    {
                        "id": "e",
                        "x": 10,
                        "y": 5,
                        "width": 1,
                        "connected_space_id": "r",
                    }
                ],
                "occupant_groups": [
                    {
                        "id": "g",
                        "name": "G",
                        "count": 1,
                        "space_id": "r",
                        "spawn_x": 2,
                        "spawn_y": 5,
                        "walking_speed_mps": 1.2,
                    }
                ],
                "fire": {
                    "enabled": True,
                    "x": 8,
                    "y": 5,
                    "radius_m": 2,
                    "spread_speed_mps": 0.2,
                    "intensity": 80,
                    "emit_smoke": True,
                },
            }
        )
        origin = resolve_origin_smoke(layout)
        self.assertIsNotNone(origin)
        assert origin is not None
        self.assertAlmostEqual(
            origin.spread_speed_mps, 0.2 * SMOKE_SPREAD_MULTIPLIER
        )
        plumes = active_smoke_plumes(layout, 0.0)
        self.assertEqual(len(plumes), 1)
        self.assertGreater(plumes[0].radius_m, 2.0)
        smoke_r = active_smoke_plumes(layout, 10.0)[0].radius_m
        fire_r = active_fire_plumes(layout, 10.0)[0].radius_m
        self.assertGreater(smoke_r, fire_r)

    def test_standalone_layout_smoke_is_ignored(self):
        layout = BuildingLayout.model_validate(
            {
                "width": 20,
                "height": 20,
                "spaces": [
                    {
                        "id": "r",
                        "name": "R",
                        "type": "room",
                        "vertices": [[0, 0], [10, 0], [10, 10], [0, 10]],
                    }
                ],
                "smoke": {
                    "enabled": True,
                    "x": 5,
                    "y": 5,
                    "radius_m": 4,
                    "intensity": 90,
                },
            }
        )
        self.assertIsNone(resolve_origin_smoke(layout))


class SmokeChimneyTests(unittest.TestCase):
    def test_smoke_rises_through_linked_stairs(self):
        layout = linked_floors_layout(count=1)
        layout.fire = FireEmergency(
            enabled=True,
            x=10.0,
            y=4.0,
            radius_m=1.0,
            spread_speed_mps=2.0,
            intensity=70,
            floor_id="floor-0",
            emit_smoke=True,
            smoke_stair_spread_delay_s=1.0,
            smoke_stair_intensity_factor=0.8,
        )
        early = active_smoke_plumes(layout, 0.0)
        self.assertEqual({p.floor_id for p in early}, {"floor-0"})
        late = active_smoke_plumes(layout, 30.0)
        floors = {p.floor_id for p in late}
        self.assertIn("floor-0", floors)
        self.assertIn("floor-1", floors)

    def test_smoke_descends_when_origin_is_top_floor(self):
        layout = linked_floors_layout(count=1)
        layout.fire = FireEmergency(
            enabled=True,
            x=10.0,
            y=4.0,
            radius_m=5.0,
            spread_speed_mps=0.0,
            intensity=70,
            floor_id="floor-1",
            emit_smoke=True,
            smoke_stair_spread_delay_s=0.0,
        )
        plumes = active_smoke_plumes(layout, 20.0)
        self.assertEqual({p.floor_id for p in plumes}, {"floor-0", "floor-1"})

    def test_fire_follows_stairs_slower_than_smoke(self):
        layout = linked_floors_layout(count=1)
        layout.fire = FireEmergency(
            enabled=True,
            x=10.0,
            y=4.0,
            radius_m=1.0,
            spread_speed_mps=2.0,
            intensity=70,
            floor_id="floor-0",
            emit_smoke=True,
            smoke_stair_spread_delay_s=2.0,
            smoke_stair_intensity_factor=0.8,
        )
        # At an intermediate time smoke has reached the upper floor but fire has not.
        mid_t = 4.0
        smoke_floors = {p.floor_id for p in active_smoke_plumes(layout, mid_t)}
        fire_floors = {p.floor_id for p in active_fire_plumes(layout, mid_t)}
        self.assertIn("floor-1", smoke_floors)
        self.assertNotIn("floor-1", fire_floors)
        late_fire = {p.floor_id for p in active_fire_plumes(layout, 40.0)}
        self.assertIn("floor-1", late_fire)


class SmokeSimTests(unittest.TestCase):
    def test_fire_smoke_slows_but_does_not_trap(self):
        layout = BuildingLayout.model_validate(
            {
                "width": 20,
                "height": 12,
                "spaces": [
                    {
                        "id": "r",
                        "name": "R",
                        "type": "room",
                        "vertices": [[0, 0], [16, 0], [16, 10], [0, 10]],
                    }
                ],
                "exits": [
                    {
                        "id": "e",
                        "x": 16,
                        "y": 5,
                        "width": 1.2,
                        "connected_space_id": "r",
                    }
                ],
                "occupant_groups": [
                    {
                        "id": "g",
                        "name": "G",
                        "count": 1,
                        "space_id": "r",
                        "spawn_x": 2,
                        "spawn_y": 5,
                        "walking_speed_mps": 1.2,
                    }
                ],
                "fire": {
                    "enabled": True,
                    "x": 8,
                    "y": 8,
                    "radius_m": 1.5,
                    "spread_speed_mps": 0,
                    "intensity": 40,
                    "emit_smoke": True,
                    "smoke_visibility_m": 8,
                },
            }
        )
        out = SimulationEngine().run(layout, SimulationParameters(max_time_s=60))
        self.assertEqual(out.results.evacuated_count, 1)
        self.assertTrue(any(f.smoke_floors for f in out.frames))
        self.assertTrue(any(f.fire_floors for f in out.frames))


if __name__ == "__main__":
    unittest.main()
