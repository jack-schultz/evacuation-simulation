import unittest

from pydantic import ValidationError
from app.domain.building import BuildingLayout, FloodEmergency, SimulationParameters
from app.simulation.engine import SimulationEngine


def layout(flood=None, preferred=None, two_exits=True):
    return BuildingLayout.model_validate({
        "width": 20, "height": 20,
        "spaces": [{"id": "room", "name": "Room", "type": "room", "x": 0, "y": 0, "width": 10, "height": 10}],
        "exits": [{"id": "near", "x": 7, "y": 5, "width": 1, "connected_space_id": "room", "flow_rate_per_s": 100}]
            + ([{"id": "far", "x": 0, "y": 5, "width": 1, "connected_space_id": "room", "flow_rate_per_s": 100}] if two_exits else []),
        "occupant_groups": [{"id": "g", "name": "People", "count": 1, "space_id": "room", "destination_exit_id": preferred}],
        "flood": flood,
    })


def run(building):
    return SimulationEngine().run(building, SimulationParameters(max_time_s=30))


def flood(intensity=80, **kwargs):
    return dict(x=6, y=5, radius_m=0.5, intensity=intensity, **kwargs)


class FloodTests(unittest.TestCase):
    def test_high_intensity_does_not_change_route(self):
        # Flood no longer affects route choice; take the nearer exit even if wet.
        config = dict(x=7, y=5, radius_m=0.5, intensity=80)
        output = run(layout(config))
        self.assertEqual(output.results.occupants[0].route_node_ids[-1], 'exit:near')
        self.assertEqual(output.results.evacuated_count, 1)

    def test_preferred_exit_stays_binding_when_only_slowed(self):
        # Soft flood keeps a preferred exit reachable, so it remains binding.
        result = run(layout(flood(), preferred='near')).results
        self.assertEqual(result.occupants[0].route_node_ids[-1], 'exit:near')
        self.assertEqual(result.evacuated_count, 1)

    def test_only_flooded_exit_remains_usable(self):
        # Soft flood: people may wade through a wet exit if it is the only option.
        output = run(layout(dict(x=7, y=5, radius_m=0.5, intensity=50), two_exits=False))
        self.assertEqual(output.results.evacuated_count, 1)
        self.assertTrue(all(f.occupants[0].status != 'trapped' for f in output.frames))

    def test_brief_contact_does_not_kill(self):
        output = run(layout(dict(x=5, y=5, radius_m=0.5, intensity=50), two_exits=False))
        self.assertEqual(output.frames[0].occupants[0].status, 'active')
        self.assertEqual(output.results.evacuated_count, 1)

    def test_prolonged_immersion_is_lethal(self):
        # Full-room flood at intensity 100 → lethal after FLOOD_LETHAL_EXPOSURE_S.
        # Very slow walker cannot clear the room before drowning.
        building = layout(
            dict(x=5, y=5, radius_m=10, intensity=100, spread_speed_mps=0),
            two_exits=False,
        )
        building.occupant_groups[0].walking_speed_mps = 0.05
        output = SimulationEngine().run(
            building, SimulationParameters(max_time_s=60, timestep_s=0.25)
        )
        self.assertEqual(output.results.evacuated_count, 0)
        self.assertTrue(any(f.occupants[0].status == 'trapped' for f in output.frames))
        self.assertEqual(output.frames[-1].occupants[0].status, 'trapped')

    def test_people_inside_flood_can_reach_an_exit(self):
        for intensity in (1, 50, 80):
            with self.subTest(intensity=intensity):
                config = dict(x=6, y=5, radius_m=2, intensity=intensity, spread_speed_mps=0)
                output = SimulationEngine().run(
                    layout(config, preferred='near'), SimulationParameters(max_time_s=60)
                )
                self.assertEqual(output.results.evacuated_count, 1)

    def test_disabled_or_zero_flood_at_exit_preserves_baseline(self):
        baseline = run(layout())
        for config in [dict(x=7, y=5, radius_m=1, intensity=0), dict(x=7, y=5, radius_m=1, intensity=100, enabled=False)]:
            output = run(layout(config))
            self.assertEqual(output.results, baseline.results)
            self.assertEqual(output.frames, baseline.frames)

    def test_wet_regions_are_slowed_not_blocked(self):
        from app.simulation.flood import active_flood_plumes, flood_soft_speed_factor
        building = layout(dict(x=6, y=5, radius_m=2, intensity=50))
        plumes = active_flood_plumes(building, 0.0)
        self.assertAlmostEqual(flood_soft_speed_factor(plumes, 'room', 7, 5), 0.5)
        self.assertEqual(flood_soft_speed_factor(plumes, 'room', 0, 5), 1.0)

    def test_legacy_layout_and_round_trip(self):
        self.assertEqual(layout().floods, [])
        original = layout(flood())
        self.assertEqual(BuildingLayout.model_validate_json(original.model_dump_json()), original)

    def test_disabled_and_zero_match_baseline(self):
        baseline = run(layout())
        for config in [flood(enabled=False), flood(0)]:
            actual = run(layout(config))
            self.assertEqual(actual.results, baseline.results)
            self.assertEqual(actual.frames, baseline.frames)

    def test_flooded_near_exit_still_chosen_when_intensity_is_high(self):
        result = run(layout(flood())).results
        self.assertEqual(result.evacuated_count, 1)
        self.assertEqual(result.occupants[0].route_node_ids[-1], 'exit:near')

    def test_flood_slows_movement_without_inflating_distance(self):
        baseline = run(layout(two_exits=False)).results
        wet = run(layout(dict(x=5, y=5, radius_m=0.5, intensity=50), two_exits=False)).results
        self.assertGreater(wet.total_evacuation_time_s, baseline.total_evacuation_time_s)
        self.assertAlmostEqual(wet.occupants[0].distance_m, baseline.occupants[0].distance_m, delta=0.35)
        self.assertLessEqual(wet.occupants[0].distance_m, 2.05)

    def test_flood_away_from_routes_has_no_effect(self):
        self.assertEqual(run(layout(dict(x=15, y=15, radius_m=1, intensity=100))).results, run(layout()).results)

    def test_fractional_flow_reaches_exit_without_asymptotic_slowdown(self):
        building = layout(dict(x=5, y=5, radius_m=0.5, intensity=50), two_exits=False)
        building.exits[0].flow_rate_per_s = 1.5
        result = run(building).results
        self.assertEqual(result.evacuated_count, 1)
        self.assertLess(result.total_evacuation_time_s, 10)

    def test_save_reload_and_simulation_snapshot(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.models.building import BuildingRecord
        from app.services.building_service import BuildingService
        from app.services.simulation_service import SimulationService
        engine = create_engine('sqlite:///:memory:')
        BuildingRecord.metadata.create_all(engine)
        with Session(engine) as db:
            buildings = BuildingService(db)
            simulations = SimulationService(db)
            saved = buildings.create_building(layout(flood()))
            self.assertEqual(buildings.get_layout(saved.id).floods[0].intensity, 80)
            snapshot = simulations.create(saved.id, SimulationParameters(max_time_s=30))
            buildings.update_building(saved.id, layout())
            result = simulations.run(snapshot.id)
            self.assertEqual(result.results.occupants[0].route_node_ids[-1], 'exit:near')
            self.assertEqual(buildings.get_layout(saved.id).floods, [])
        engine.dispose()

    def test_invalid_flood_values(self):
        for patch in [dict(radius_m=0), dict(intensity=-1), dict(intensity=101), dict(x=-1), dict(y=float('nan')), dict(radius_m=float('inf')), dict(spread_speed_mps=-1), dict(spread_speed_mps=float('inf')), dict(spread_speed_mps=float('nan'))]:
            with self.assertRaises(ValidationError):
                FloodEmergency.model_validate(flood() | patch)
        with self.assertRaises(ValidationError):
            layout(flood() | dict(x=21))

    def test_partial_evacuation_has_no_total_completion_time(self):
        building = layout(flood())
        building.spaces.append(building.spaces[0].model_copy(update=dict(id='isolated', x=12)))
        building.occupant_groups.append(building.occupant_groups[0].model_copy(update=dict(id='stranded', space_id='isolated')))
        result = run(building).results
        self.assertEqual(result.evacuated_count, 1)
        self.assertEqual(result.remaining_count, 1)
        self.assertIsNone(result.total_evacuation_time_s)

    def test_exposure_dose_scales_with_intensity(self):
        from app.simulation.flood import FLOOD_LETHAL_EXPOSURE_S, apply_flood_exposure, active_flood_plumes
        from app.simulation.movement import SimulatedOccupant
        building = layout(dict(x=5, y=5, radius_m=3, intensity=50, spread_speed_mps=0))
        plumes = active_flood_plumes(building, 0.0)
        occ = SimulatedOccupant(
            id='g:0', group_id='g', speed_mps=1.2, route=['space:room'],
            current_space_id='room', x=5, y=5,
        )
        # At intensity 50, dose rate is 0.5/s → lethal after 60s.
        apply_flood_exposure([occ], plumes, FLOOD_LETHAL_EXPOSURE_S / 0.5 - 0.1)
        self.assertEqual(occ.status.value, 'active')
        apply_flood_exposure([occ], plumes, 0.2)
        self.assertEqual(occ.status.value, 'trapped')


class SpreadingFloodTests(unittest.TestCase):
    def test_radius_uses_elapsed_seconds_and_legacy_default(self):
        from app.simulation.flood import flood_radius_at
        config = FloodEmergency(x=5, y=5, radius_m=2)
        self.assertAlmostEqual(flood_radius_at(config, 60), 8)
        self.assertEqual(config.spread_speed_mps, 0.1)
        config.spread_speed_mps = 0
        self.assertEqual(flood_radius_at(config, 60), 2)
        for patch in [dict(enabled=False), dict(intensity=0)]:
            self.assertIsNone(flood_radius_at(config.model_copy(update=patch), 60))

    def test_frame_radius_is_independent_of_timestep_and_recording_interval(self):
        building = layout(dict(x=7, y=5, radius_m=0.5, intensity=50), two_exits=False)
        for dt, interval in [(0.1, 0.2), (0.25, 0.5), (0.5, 1)]:
            output = SimulationEngine().run(building, SimulationParameters(
                timestep_s=dt, frame_interval_s=interval, max_time_s=5))
            for frame in output.frames:
                self.assertAlmostEqual(frame.flood_radius_m, 0.5 + 0.1 * frame.t)
            self.assertEqual(output.frames[0].flood_radius_m, 0.5)
        self.assertEqual(building.floods[0].radius_m, 0.5)

    def test_flood_reaching_exit_does_not_instantly_trap(self):
        config = dict(x=10, y=5, radius_m=0.5, intensity=50, spread_speed_mps=2)
        for dt in (0.1, 0.25, 0.5):
            output = SimulationEngine().run(layout(config, two_exits=False),
                SimulationParameters(timestep_s=dt, max_time_s=5, frame_interval_s=dt))
            self.assertEqual(output.frames[0].occupants[0].status, 'active')
            # Soft flood: newly wet exits remain usable; brief immersion is not lethal.
            self.assertNotEqual(output.frames[-1].occupants[0].status, 'trapped')
        config['spread_speed_mps'] = 0
        self.assertEqual(run(layout(config, two_exits=False)).results.evacuated_count, 1)

    def test_spread_competes_with_actual_walking_speed(self):
        config = dict(x=10, y=5, radius_m=0.5, intensity=100, spread_speed_mps=0.5)
        fast = layout(config, two_exits=False)
        slow = fast.model_copy(deep=True)
        slow.occupant_groups[0].walking_speed_mps = 0.05
        self.assertEqual(run(fast).results.evacuated_count, 1)
        # Very slow walker accumulates a lethal immersion dose before escaping.
        slow_out = SimulationEngine().run(slow, SimulationParameters(max_time_s=90))
        self.assertEqual(slow_out.results.evacuated_count, 0)
        self.assertEqual(slow_out.frames[-1].occupants[0].status, 'trapped')

    def test_spread_behind_occupant_does_not_block_dry_remaining_path(self):
        config = dict(x=4, y=5, radius_m=0.1, intensity=50, spread_speed_mps=0.8)
        output = run(layout(config, two_exits=False))
        self.assertGreater(output.frames[-1].flood_radius_m, 1)
        self.assertEqual(output.results.evacuated_count, 1)

    def test_soft_factor_inside_water(self):
        from app.simulation.flood import flood_soft_speed_factor, active_flood_plumes
        building = layout(dict(x=4, y=5, radius_m=2, intensity=50, spread_speed_mps=0))
        plumes = active_flood_plumes(building, 0.0)
        self.assertAlmostEqual(flood_soft_speed_factor(plumes, 'room', 5, 5), 0.5)
        self.assertEqual(flood_soft_speed_factor(plumes, 'room', 8, 5), 1.0)

    def test_disabled_spread_preserves_dry_frames(self):
        baseline = run(layout())
        for patch in [dict(enabled=False), dict(intensity=0)]:
            config = dict(x=5, y=5, radius_m=1, intensity=50, spread_speed_mps=10) | patch
            output = run(layout(config))
            self.assertEqual(output.frames, baseline.frames)
            self.assertEqual(output.results, baseline.results)


def two_room_layout(flood=None, occupant_space='a', exit_space='b'):
    """Room A (0–10) and room B (10–20) share a door at x=10."""
    exits = []
    if exit_space == 'a':
        exits.append({"id": "exit-a", "x": 0, "y": 5, "width": 1, "connected_space_id": "a", "flow_rate_per_s": 100})
    if exit_space == 'b':
        exits.append({"id": "exit-b", "x": 20, "y": 5, "width": 1, "connected_space_id": "b", "flow_rate_per_s": 100})
    return BuildingLayout.model_validate({
        "width": 40, "height": 20,
        "spaces": [
            {"id": "a", "name": "A", "type": "room", "x": 0, "y": 0, "width": 10, "height": 10},
            {"id": "b", "name": "B", "type": "room", "x": 10, "y": 0, "width": 10, "height": 10},
        ],
        "doors": [{"id": "ab", "x": 10, "y": 5, "width": 1, "connects": ["a", "b"]}],
        "exits": exits,
        "occupant_groups": [{
            "id": "g", "name": "People", "count": 1, "space_id": occupant_space,
        }],
        "flood": flood,
    })


class RoomScopedFloodTests(unittest.TestCase):
    def test_neighbor_room_stays_dry_until_door_is_reached(self):
        from app.simulation.flood import active_flood_plumes
        building = two_room_layout(dict(x=5, y=5, radius_m=0.5, intensity=50, spread_speed_mps=1))
        early = active_flood_plumes(building, 0.0)
        self.assertEqual([p.space_id for p in early], ['a'])
        self.assertAlmostEqual(early[0].radius_m, 0.5)
        mid = active_flood_plumes(building, 4.0)
        self.assertEqual([p.space_id for p in mid], ['a'])
        after = active_flood_plumes(building, 4.5)
        self.assertEqual({p.space_id for p in after}, {'a', 'b'})
        b_plume = next(p for p in after if p.space_id == 'b')
        self.assertEqual((b_plume.x, b_plume.y), (10.0, 5.0))
        self.assertAlmostEqual(b_plume.radius_m, 0.0)

    def test_doorway_plume_grows_into_neighbor_room(self):
        from app.simulation.flood import active_flood_plumes
        building = two_room_layout(dict(x=5, y=5, radius_m=0.5, intensity=50, spread_speed_mps=1))
        later = active_flood_plumes(building, 6.5)
        b_plume = next(p for p in later if p.space_id == 'b')
        self.assertAlmostEqual(b_plume.radius_m, 2.0)

    def test_disconnected_room_is_never_flooded_by_euclidean_overlap(self):
        from app.simulation.flood import active_flood_plumes
        building = two_room_layout(dict(x=5, y=5, radius_m=50, intensity=50, spread_speed_mps=0))
        building.spaces.append(building.spaces[0].model_copy(update=dict(
            id='isolated', name='Isolated', x=25, y=0, width=10, height=10,
        )))
        plumes = active_flood_plumes(building, 0.0)
        self.assertEqual({p.space_id for p in plumes}, {'a', 'b'})
        self.assertNotIn('isolated', {p.space_id for p in plumes})

    def test_exit_in_neighbor_floods_only_after_doorway_spread(self):
        from app.simulation.flood import active_flood_plumes
        config = dict(x=5, y=5, radius_m=0.5, intensity=50, spread_speed_mps=1)
        building = two_room_layout(config, occupant_space='b', exit_space='b')
        early = {p.space_id: p for p in active_flood_plumes(building, 4.5)}
        self.assertIn('a', early)
        early_b = early.get('b')
        self.assertTrue(early_b is None or early_b.radius_m <= 0.0)
        late = {p.space_id: p for p in active_flood_plumes(building, 14.5)}
        self.assertIn('b', late)
        self.assertAlmostEqual(late['b'].radius_m, 10.0)

    def test_frames_include_flood_rooms(self):
        building = two_room_layout(dict(x=5, y=5, radius_m=0.5, intensity=50, spread_speed_mps=1))
        output = SimulationEngine().run(building, SimulationParameters(max_time_s=6, timestep_s=0.5))
        self.assertTrue(any(len(f.flood_rooms) >= 2 for f in output.frames))
        late = output.frames[-1]
        self.assertEqual({p.space_id for p in late.flood_rooms}, {'a', 'b'})


def _past_stairs_layout():
    """Upper: left room — stairs — right room; stairs dump to ground room."""
    return BuildingLayout.model_validate({
        "width": 40, "height": 20,
        "floors": [
            {"id": "floor-0", "name": "G", "elevation_m": 0, "order": 0},
            {"id": "floor-1", "name": "1", "elevation_m": 3.2, "order": 1},
        ],
        "spaces": [
            {
                "id": "left", "name": "Left", "type": "room", "floor_id": "floor-1",
                "vertices": [[0, 0], [8, 0], [8, 8], [0, 8]],
            },
            {
                "id": "stairs_u", "name": "Stairs U", "type": "stairs", "floor_id": "floor-1",
                "vertices": [[8, 2], [12, 2], [12, 6], [8, 6]],
                "linked_stair_id": "stairs_g",
            },
            {
                "id": "right", "name": "Right", "type": "room", "floor_id": "floor-1",
                "vertices": [[12, 0], [20, 0], [20, 8], [12, 8]],
            },
            {
                "id": "stairs_g", "name": "Stairs G", "type": "stairs", "floor_id": "floor-0",
                "vertices": [[8, 2], [12, 2], [12, 6], [8, 6]],
                "linked_stair_id": "stairs_u",
            },
            {
                "id": "ground", "name": "Ground", "type": "room", "floor_id": "floor-0",
                "vertices": [[0, 0], [8, 0], [8, 8], [0, 8]],
            },
        ],
        "doors": [
            {"id": "d_left", "x": 8, "y": 4, "width": 1, "floor_id": "floor-1",
             "connects": ["left", "stairs_u"]},
            {"id": "d_right", "x": 12, "y": 4, "width": 1, "floor_id": "floor-1",
             "connects": ["stairs_u", "right"]},
            {"id": "d_ground", "x": 8, "y": 4, "width": 1, "floor_id": "floor-0",
             "connects": ["stairs_g", "ground"]},
        ],
        "exits": [
            {"id": "out", "x": 0, "y": 4, "width": 1, "floor_id": "floor-0",
             "connected_space_id": "ground"},
        ],
        "occupant_groups": [
            {"id": "g", "name": "People", "count": 1, "space_id": "left",
             "floor_id": "floor-1", "spawn_x": 2, "spawn_y": 4},
        ],
        "flood": {
            "enabled": True, "x": 2, "y": 4, "radius_m": 0.5, "intensity": 50,
            "spread_speed_mps": 1.0, "floor_id": "floor-1",
        },
    })


class StairFloodTests(unittest.TestCase):
    def test_flood_dumps_down_stairs_before_wetting_room_past_them(self):
        from app.simulation.flood import active_flood_plumes
        building = _past_stairs_layout()
        # Early: only origin room.
        early = {p.space_id for p in active_flood_plumes(building, 1.0)}
        self.assertEqual(early, {"left"})

        # After reaching stairs and dumping down, ground should wet before right.
        ids_over_time = []
        right_first_t = None
        ground_first_t = None
        for t in [i * 0.5 for i in range(0, 80)]:
            ids = {p.space_id for p in active_flood_plumes(building, t)}
            ids_over_time.append((t, ids))
            if "ground" in ids and ground_first_t is None:
                ground_first_t = t
            if "right" in ids and right_first_t is None:
                right_first_t = t
        self.assertIsNotNone(ground_first_t)
        self.assertIsNotNone(right_first_t)
        self.assertLess(ground_first_t, right_first_t)

    def test_flood_rises_only_after_origin_floor_is_filled(self):
        from app.simulation.flood import active_flood_plumes
        from tests.test_stair_link import linked_floors_layout
        building = linked_floors_layout(count=1)
        building.floods = [FloodEmergency(
            enabled=True,
            x=2.0,
            y=4.0,
            radius_m=0.5,
            spread_speed_mps=2.0,
            intensity=50,
            floor_id="floor-0",
        )]
        # Move occupants to ground so the layout validates; flood starts on ground.
        building.occupant_groups[0].space_id = "room_b"
        building.occupant_groups[0].floor_id = "floor-0"
        building.occupant_groups[0].spawn_x = 2.0
        building.occupant_groups[0].spawn_y = 4.0

        early = {p.space_id for p in active_flood_plumes(building, 0.5)}
        self.assertTrue(early <= {"room_b", "stairs_b"})
        self.assertNotIn("stairs_a", early)
        self.assertNotIn("room_a", early)

        late = {p.space_id for p in active_flood_plumes(building, 60.0)}
        self.assertIn("stairs_a", late)
        self.assertIn("room_a", late)

        # Upper stairs appear only after ground floor spaces are present and filling.
        upper_t = None
        for t in [i * 0.5 for i in range(0, 120)]:
            ids = {p.space_id for p in active_flood_plumes(building, t)}
            if "stairs_a" in ids:
                upper_t = t
                # Ground stair and room should already be wet.
                self.assertIn("stairs_b", ids)
                self.assertIn("room_b", ids)
                break
        self.assertIsNotNone(upper_t)

    def test_top_floor_flood_reaches_ground_through_stairs(self):
        from app.simulation.flood import active_flood_plumes
        from tests.test_stair_link import linked_floors_layout
        building = linked_floors_layout(count=1)
        building.floods = [FloodEmergency(
            enabled=True,
            x=2.0,
            y=4.0,
            radius_m=1.0,
            spread_speed_mps=2.0,
            intensity=50,
            floor_id="floor-1",
        )]
        late = {p.space_id for p in active_flood_plumes(building, 40.0)}
        self.assertIn("stairs_a", late)
        self.assertIn("stairs_b", late)
        self.assertIn("room_b", late)


class MultiFloodTests(unittest.TestCase):
    def test_two_flood_origins_wet_separate_rooms(self):
        from app.simulation.flood import active_flood_plumes

        building = BuildingLayout.model_validate({
            "width": 30,
            "height": 20,
            "spaces": [
                {"id": "a", "name": "A", "type": "room", "x": 0, "y": 0, "width": 10, "height": 10},
                {"id": "b", "name": "B", "type": "room", "x": 15, "y": 0, "width": 10, "height": 10},
            ],
            "exits": [
                {"id": "ea", "x": 0, "y": 5, "width": 1, "connected_space_id": "a", "flow_rate_per_s": 100},
                {"id": "eb", "x": 25, "y": 5, "width": 1, "connected_space_id": "b", "flow_rate_per_s": 100},
            ],
            "occupant_groups": [
                {"id": "g", "name": "People", "count": 1, "space_id": "a"},
            ],
            "floods": [
                {"id": "f1", "x": 5, "y": 5, "radius_m": 1, "intensity": 50, "spread_speed_mps": 0},
                {"id": "f2", "x": 20, "y": 5, "radius_m": 1, "intensity": 50, "spread_speed_mps": 0},
            ],
        })
        plumes = active_flood_plumes(building, 0.0)
        self.assertEqual({p.space_id for p in plumes}, {"a", "b"})


if __name__ == '__main__':
    unittest.main()
