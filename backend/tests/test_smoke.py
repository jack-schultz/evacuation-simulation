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


def _smoke_floor_ids(layout: BuildingLayout, plumes) -> set[str]:
    spaces = {s.id: s for s in layout.spaces}
    return {
        (spaces[p.space_id].floor_id if p.space_id in spaces else "floor-0")
        for p in plumes
    }


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
        self.assertEqual(plumes[0].space_id, "r")
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


class SmokeDoorSpreadTests(unittest.TestCase):
    def test_neighbor_room_stays_clear_until_door_is_reached(self):
        layout = BuildingLayout.model_validate(
            {
                "width": 40,
                "height": 20,
                "spaces": [
                    {
                        "id": "a",
                        "name": "A",
                        "type": "room",
                        "vertices": [[0, 0], [10, 0], [10, 10], [0, 10]],
                    },
                    {
                        "id": "b",
                        "name": "B",
                        "type": "room",
                        "vertices": [[10, 0], [20, 0], [20, 10], [10, 10]],
                    },
                ],
                "doors": [
                    {"id": "ab", "x": 10, "y": 5, "width": 1, "connects": ["a", "b"]}
                ],
                "exits": [
                    {
                        "id": "e",
                        "x": 20,
                        "y": 5,
                        "width": 1,
                        "connected_space_id": "b",
                    }
                ],
                "occupant_groups": [
                    {"id": "g", "name": "G", "count": 1, "space_id": "a"}
                ],
                "fire": {
                    "enabled": True,
                    "x": 5,
                    "y": 5,
                    "radius_m": 0.5,
                    "spread_speed_mps": 0.1,
                    "intensity": 50,
                    "emit_smoke": True,
                },
            }
        )
        # Smoke speed = 0.1 * 2.5 = 0.25 m/s; r0 = 0.7 → door at ~17.2 s.
        early = active_smoke_plumes(layout, 0.0)
        self.assertEqual({p.space_id for p in early}, {"a"})
        mid = active_smoke_plumes(layout, 17.0)
        self.assertEqual({p.space_id for p in mid}, {"a"})
        after = active_smoke_plumes(layout, 18.0)
        self.assertEqual({p.space_id for p in after}, {"a", "b"})
        b_plume = next(p for p in after if p.space_id == "b")
        self.assertEqual((b_plume.x, b_plume.y), (10.0, 5.0))

    def test_fire_seeds_smoke_when_it_reaches_a_clear_room(self):
        """Fire keeps radial spread; when it hits a room, smoke starts there too."""
        layout = BuildingLayout.model_validate(
            {
                "width": 40,
                "height": 20,
                "spaces": [
                    {
                        "id": "a",
                        "name": "A",
                        "type": "room",
                        "vertices": [[0, 0], [10, 0], [10, 10], [0, 10]],
                    },
                    {
                        "id": "isolated",
                        "name": "Isolated",
                        "type": "room",
                        "vertices": [[12, 0], [22, 0], [22, 10], [12, 10]],
                    },
                ],
                "exits": [
                    {
                        "id": "e",
                        "x": 0,
                        "y": 5,
                        "width": 1,
                        "connected_space_id": "a",
                    }
                ],
                "occupant_groups": [
                    {"id": "g", "name": "G", "count": 1, "space_id": "a"}
                ],
                "fire": {
                    "enabled": True,
                    "x": 5,
                    "y": 5,
                    "radius_m": 0.5,
                    "spread_speed_mps": 1.0,
                    "intensity": 50,
                    "emit_smoke": True,
                },
            }
        )
        early = {p.space_id for p in active_smoke_plumes(layout, 0.0)}
        self.assertEqual(early, {"a"})
        # Isolated wall at x=12; fire reaches it at (12 - 5 - 0.5) / 1 = 6.5 s.
        mid = {p.space_id for p in active_smoke_plumes(layout, 6.0)}
        self.assertNotIn("isolated", mid)
        late = {p.space_id for p in active_smoke_plumes(layout, 7.0)}
        self.assertIn("isolated", late)


class SmokeChimneyTests(unittest.TestCase):
    def test_smoke_rises_through_linked_stairs(self):
        layout = linked_floors_layout(count=1)
        layout.fires = [FireEmergency(
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
        )]
        early = active_smoke_plumes(layout, 0.0)
        self.assertEqual(_smoke_floor_ids(layout, early), {"floor-0"})
        late = active_smoke_plumes(layout, 30.0)
        floors = _smoke_floor_ids(layout, late)
        self.assertIn("floor-0", floors)
        self.assertIn("floor-1", floors)

    def test_smoke_descends_when_origin_is_top_floor(self):
        layout = linked_floors_layout(count=1)
        layout.fires = [FireEmergency(
            enabled=True,
            x=10.0,
            y=4.0,
            radius_m=5.0,
            spread_speed_mps=0.0,
            intensity=70,
            floor_id="floor-1",
            emit_smoke=True,
            smoke_stair_spread_delay_s=0.0,
        )]
        plumes = active_smoke_plumes(layout, 20.0)
        self.assertEqual(_smoke_floor_ids(layout, plumes), {"floor-0", "floor-1"})

    def test_fire_descends_from_top_floor_through_stairs(self):
        layout = linked_floors_layout(count=1)
        layout.fires = [FireEmergency(
            enabled=True,
            x=10.0,
            y=4.0,
            radius_m=5.0,
            spread_speed_mps=0.0,
            intensity=70,
            floor_id="floor-1",
            emit_smoke=True,
            smoke_stair_spread_delay_s=2.0,
        )]
        # Fire stair delay is 2×2.5 = 5s; still only on the top floor early on.
        early = active_fire_plumes(layout, 1.0)
        self.assertEqual({p.floor_id for p in early}, {"floor-1"})
        late = active_fire_plumes(layout, 6.0)
        self.assertEqual({p.floor_id for p in late}, {"floor-0", "floor-1"})
        ground = next(p for p in late if p.floor_id == "floor-0")
        self.assertAlmostEqual(ground.x, 10.0)
        self.assertAlmostEqual(ground.y, 4.0)

    def test_fire_climbs_then_lower_floors_can_descend_further(self):
        """Middle origin spreads both up and down through stairs."""
        layout = BuildingLayout.model_validate(
            {
                "width": 40,
                "height": 20,
                "floors": [
                    {"id": "floor-0", "name": "G", "elevation_m": 0, "order": 0},
                    {"id": "floor-1", "name": "1", "elevation_m": 3.2, "order": 1},
                    {"id": "floor-2", "name": "2", "elevation_m": 6.4, "order": 2},
                ],
                "spaces": [
                    {
                        "id": "r0",
                        "name": "R0",
                        "type": "room",
                        "floor_id": "floor-0",
                        "vertices": [[0, 0], [8, 0], [8, 8], [0, 8]],
                    },
                    {
                        "id": "s0",
                        "name": "S0",
                        "type": "stairs",
                        "floor_id": "floor-0",
                        "vertices": [[8, 2], [12, 2], [12, 6], [8, 6]],
                        "linked_stair_id": "s1",
                    },
                    {
                        "id": "r1",
                        "name": "R1",
                        "type": "room",
                        "floor_id": "floor-1",
                        "vertices": [[0, 0], [8, 0], [8, 8], [0, 8]],
                    },
                    {
                        "id": "s1",
                        "name": "S1",
                        "type": "stairs",
                        "floor_id": "floor-1",
                        "vertices": [[8, 2], [12, 2], [12, 6], [8, 6]],
                        "linked_stair_id": "s0",
                    },
                    {
                        "id": "s1u",
                        "name": "S1u",
                        "type": "stairs",
                        "floor_id": "floor-1",
                        "vertices": [[8, 2], [12, 2], [12, 6], [8, 6]],
                        "linked_stair_id": "s2",
                    },
                    {
                        "id": "r2",
                        "name": "R2",
                        "type": "room",
                        "floor_id": "floor-2",
                        "vertices": [[0, 0], [8, 0], [8, 8], [0, 8]],
                    },
                    {
                        "id": "s2",
                        "name": "S2",
                        "type": "stairs",
                        "floor_id": "floor-2",
                        "vertices": [[8, 2], [12, 2], [12, 6], [8, 6]],
                        "linked_stair_id": "s1u",
                    },
                ],
                "doors": [
                    {
                        "id": "d0",
                        "x": 8,
                        "y": 4,
                        "width": 1.2,
                        "floor_id": "floor-0",
                        "connects": ["r0", "s0"],
                    },
                    {
                        "id": "d1",
                        "x": 8,
                        "y": 4,
                        "width": 1.2,
                        "floor_id": "floor-1",
                        "connects": ["r1", "s1"],
                    },
                    {
                        "id": "d1u",
                        "x": 8,
                        "y": 4,
                        "width": 1.2,
                        "floor_id": "floor-1",
                        "connects": ["r1", "s1u"],
                    },
                    {
                        "id": "d2",
                        "x": 8,
                        "y": 4,
                        "width": 1.2,
                        "floor_id": "floor-2",
                        "connects": ["r2", "s2"],
                    },
                ],
                "exits": [
                    {
                        "id": "e",
                        "x": 0,
                        "y": 4,
                        "width": 1.2,
                        "floor_id": "floor-0",
                        "connected_space_id": "r0",
                    }
                ],
                "occupant_groups": [
                    {
                        "id": "g",
                        "name": "G",
                        "count": 1,
                        "space_id": "r1",
                        "floor_id": "floor-1",
                        "spawn_x": 2,
                        "spawn_y": 4,
                        "walking_speed_mps": 1.2,
                    }
                ],
            }
        )
        layout.fires = [FireEmergency(
            enabled=True,
            x=10.0,
            y=4.0,
            radius_m=2.0,
            spread_speed_mps=1.0,
            intensity=70,
            floor_id="floor-1",
            emit_smoke=False,
            smoke_stair_spread_delay_s=1.0,
            smoke_stair_intensity_factor=0.9,
        )]
        early = {p.floor_id for p in active_fire_plumes(layout, 0.5)}
        # Too early for stair delay: still only origin floor.
        self.assertEqual(early, {"floor-1"})
        late = {p.floor_id for p in active_fire_plumes(layout, 30.0)}
        self.assertEqual(late, {"floor-0", "floor-1", "floor-2"})

    def test_fire_follows_stairs_slower_than_smoke(self):
        layout = linked_floors_layout(count=1)
        layout.fires = [FireEmergency(
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
        )]
        # At an intermediate time smoke has reached the upper floor but fire has not.
        mid_t = 4.0
        smoke_floors = _smoke_floor_ids(layout, active_smoke_plumes(layout, mid_t))
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
        self.assertTrue(any(f.smoke_rooms for f in out.frames))
        self.assertTrue(any(f.fire_floors for f in out.frames))

    def test_smoke_alone_does_not_kill(self):
        """Smoke slowdown must not mark people trapped when fire does not touch them."""
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
                    "radius_m": 0.5,
                    "spread_speed_mps": 0,
                    "intensity": 90,
                    "emit_smoke": True,
                    "smoke_visibility_m": 8,
                },
            }
        )
        out = SimulationEngine().run(layout, SimulationParameters(max_time_s=60))
        self.assertEqual(out.results.evacuated_count, 1)
        self.assertFalse(
            any(
                o.status == "trapped"
                for f in out.frames
                for o in f.occupants
            )
        )

    def test_fire_kills_climbers_on_stairs(self):
        layout = linked_floors_layout(count=1)
        # Fire covers the stair shaft on both floors.
        layout.fires = [FireEmergency(
            enabled=True,
            x=10.0,
            y=4.0,
            radius_m=3.0,
            spread_speed_mps=0.0,
            intensity=80,
            floor_id="floor-1",
            emit_smoke=False,
            smoke_stair_spread_delay_s=0.0,
        )]
        out = SimulationEngine().run(
            layout, SimulationParameters(max_time_s=60, frame_interval_s=0.5)
        )
        self.assertEqual(out.results.evacuated_count, 0)
        self.assertTrue(
            any(o.status == "trapped" for f in out.frames for o in f.occupants)
        )


class HazardPlaybackTests(unittest.TestCase):
    def test_sim_continues_for_downward_fire_after_egress(self):
        """Egress alone must not truncate frames before stair spread finishes."""
        from app.services.seed import create_seed_layout

        layout = create_seed_layout()
        layout.fires = [FireEmergency(
            enabled=True,
            x=12.0,
            y=10.0,
            radius_m=3.0,
            spread_speed_mps=0.5,
            intensity=70,
            floor_id="floor-1",
            emit_smoke=True,
            smoke_stair_spread_delay_s=2.0,
        )]
        out = SimulationEngine().run(
            layout, SimulationParameters(max_time_s=120, frame_interval_s=1.0)
        )
        self.assertTrue(out.frames[-1].t > 15.0)
        self.assertTrue(
            any(
                any(p.floor_id == "floor-0" for p in f.fire_floors)
                for f in out.frames
            ),
            "expected fire on ground floor in playback frames",
        )
        self.assertTrue(
            any(
                any(
                    next(
                        (s.floor_id for s in layout.spaces if s.id == p.space_id),
                        None,
                    )
                    == "floor-0"
                    for p in f.smoke_rooms
                )
                for f in out.frames
            ),
            "expected smoke on ground floor in playback frames",
        )

    def test_one_way_stair_chain_still_reaches_ground(self):
        """Climb chain s0→s1→s2→s3 must still allow smoke back down to ground."""
        layout = BuildingLayout.model_validate(
            {
                "width": 40,
                "height": 20,
                "floors": [
                    {"id": "floor-0", "name": "Ground", "elevation_m": 0, "order": 0},
                    {"id": "floor-1", "name": "1", "elevation_m": 3.2, "order": 1},
                    {"id": "floor-2", "name": "2", "elevation_m": 6.4, "order": 2},
                    {"id": "floor-3", "name": "3", "elevation_m": 9.6, "order": 3},
                ],
                "spaces": [
                    {
                        "id": "r0",
                        "name": "R0",
                        "type": "room",
                        "floor_id": "floor-0",
                        "vertices": [[0, 0], [16, 0], [16, 10], [0, 10]],
                    },
                    {
                        "id": "r1",
                        "name": "R1",
                        "type": "room",
                        "floor_id": "floor-1",
                        "vertices": [[0, 0], [16, 0], [16, 10], [0, 10]],
                    },
                    {
                        "id": "r2",
                        "name": "R2",
                        "type": "room",
                        "floor_id": "floor-2",
                        "vertices": [[0, 0], [16, 0], [16, 10], [0, 10]],
                    },
                    {
                        "id": "r3",
                        "name": "R3",
                        "type": "room",
                        "floor_id": "floor-3",
                        "vertices": [[0, 0], [16, 0], [16, 10], [0, 10]],
                    },
                    {
                        "id": "s0",
                        "name": "S0",
                        "type": "stairs",
                        "floor_id": "floor-0",
                        "vertices": [[8, 2], [12, 2], [12, 6], [8, 6]],
                        "linked_stair_id": "s1",
                    },
                    {
                        "id": "s1",
                        "name": "S1",
                        "type": "stairs",
                        "floor_id": "floor-1",
                        "vertices": [[8, 2], [12, 2], [12, 6], [8, 6]],
                        "linked_stair_id": "s2",
                    },
                    {
                        "id": "s2",
                        "name": "S2",
                        "type": "stairs",
                        "floor_id": "floor-2",
                        "vertices": [[8, 2], [12, 2], [12, 6], [8, 6]],
                        "linked_stair_id": "s3",
                    },
                    {
                        "id": "s3",
                        "name": "S3",
                        "type": "stairs",
                        "floor_id": "floor-3",
                        "vertices": [[8, 2], [12, 2], [12, 6], [8, 6]],
                        "linked_stair_id": "s2",
                    },
                ],
                "doors": [
                    {
                        "id": "d0",
                        "x": 8,
                        "y": 4,
                        "width": 1.2,
                        "floor_id": "floor-0",
                        "connects": ["r0", "s0"],
                    },
                    {
                        "id": "d1",
                        "x": 8,
                        "y": 4,
                        "width": 1.2,
                        "floor_id": "floor-1",
                        "connects": ["r1", "s1"],
                    },
                    {
                        "id": "d2",
                        "x": 8,
                        "y": 4,
                        "width": 1.2,
                        "floor_id": "floor-2",
                        "connects": ["r2", "s2"],
                    },
                    {
                        "id": "d3",
                        "x": 8,
                        "y": 4,
                        "width": 1.2,
                        "floor_id": "floor-3",
                        "connects": ["r3", "s3"],
                    },
                ],
                "exits": [
                    {
                        "id": "e",
                        "x": 0,
                        "y": 4,
                        "width": 1.2,
                        "floor_id": "floor-0",
                        "connected_space_id": "r0",
                    }
                ],
                "occupant_groups": [
                    {
                        "id": "g",
                        "name": "G",
                        "count": 1,
                        "space_id": "r1",
                        "floor_id": "floor-1",
                        "spawn_x": 2,
                        "spawn_y": 4,
                        "walking_speed_mps": 1.2,
                    }
                ],
                "fire": {
                    "enabled": True,
                    "x": 10,
                    "y": 4,
                    "radius_m": 2,
                    "spread_speed_mps": 1,
                    "intensity": 70,
                    "floor_id": "floor-1",
                    "emit_smoke": True,
                    "smoke_stair_spread_delay_s": 1,
                },
            }
        )
        late = _smoke_floor_ids(layout, active_smoke_plumes(layout, 30.0))
        self.assertEqual(late, {"floor-0", "floor-1", "floor-2", "floor-3"})


if __name__ == "__main__":
    unittest.main()
