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
    def test_flooded_exit_is_never_a_destination_at_any_positive_intensity(self):
        for intensity in (1, 25, 50, 79, 80, 100):
            for preferred in (None, 'near'):
                with self.subTest(intensity=intensity, preferred=preferred):
                    config = dict(x=7, y=5, radius_m=0.5, intensity=intensity)
                    output = run(layout(config, preferred=preferred))
                    self.assertEqual(output.results.occupants[0].route_node_ids[-1], 'exit:far')
                    self.assertTrue(all(frame.occupants[0].x <= 5 for frame in output.frames))

    def test_only_flooded_exit_leaves_people_trapped(self):
        output = run(layout(dict(x=7, y=5, radius_m=0.5, intensity=1), two_exits=False))
        self.assertEqual(output.results.evacuated_count, 0)
        self.assertTrue(all(frame.occupants[0].status == 'trapped' for frame in output.frames))

    def test_dry_exit_across_flood_is_avoided_even_at_low_intensity(self):
        output = run(layout(flood(1), preferred='near'))
        self.assertEqual(output.results.occupants[0].route_node_ids[-1], 'exit:far')
        self.assertTrue(all(frame.occupants[0].x <= 5 for frame in output.frames))

    def test_people_inside_flood_move_outward_to_dry_exit(self):
        for intensity in (1, 50, 80, 100):
            with self.subTest(intensity=intensity):
                config = dict(x=6, y=5, radius_m=2, intensity=intensity, spread_speed_mps=0)
                output = SimulationEngine().run(
                    layout(config, preferred='near'), SimulationParameters(max_time_s=60)
                )
                self.assertEqual(output.results.evacuated_count, 1)
                self.assertEqual(output.results.occupants[0].route_node_ids[-1], 'exit:far')
                distances = [(f.occupants[0].x - 6) ** 2 + (f.occupants[0].y - 5) ** 2 for f in output.frames]
                self.assertTrue(all(b >= a for a, b in zip(distances, distances[1:])))

    def test_all_exits_flooded_does_not_count_as_evacuation(self):
        output = run(layout(dict(x=5, y=5, radius_m=10, intensity=10)))
        self.assertEqual(output.results.evacuated_count, 0)
        self.assertEqual(output.results.remaining_count, 1)
        self.assertIsNone(output.results.total_evacuation_time_s)

    def test_exit_on_flood_boundary_is_blocked(self):
        output = run(layout(dict(x=8, y=5, radius_m=1, intensity=1)))
        self.assertEqual(output.results.occupants[0].route_node_ids[-1], 'exit:far')

    def test_disabled_or_zero_flood_at_exit_preserves_baseline(self):
        baseline = run(layout())
        for config in [dict(x=7, y=5, radius_m=1, intensity=0), dict(x=7, y=5, radius_m=1, intensity=100, enabled=False)]:
            output = run(layout(config))
            self.assertEqual(output.results, baseline.results)
            self.assertEqual(output.frames, baseline.frames)

    def test_escape_edges_are_one_way_and_do_not_allow_reentry(self):
        from app.simulation.graph import NavigationGraphBuilder
        from app.simulation.flood import apply_flood
        from app.simulation.routing import edge_between
        building = layout(dict(x=6, y=5, radius_m=2, intensity=50))
        graph = NavigationGraphBuilder().build(building, SimulationParameters().model_dump())
        apply_flood(graph, building.flood)
        self.assertGreater(edge_between(graph, 'space:room', 'exit:far').speed_factor, 0)
        self.assertEqual(edge_between(graph, 'exit:far', 'space:room').speed_factor, 0)
        self.assertEqual(edge_between(graph, 'space:room', 'exit:near').speed_factor, 0)

    def test_dry_exit_that_requires_moving_deeper_first_is_rejected(self):
        # Start is left of the flood centre; the near exit is dry but lies beyond
        # the centre, so reaching it would initially move deeper into the flood.
        building = layout(dict(x=5.5, y=5, radius_m=1, intensity=1), preferred='near')
        output = run(building)
        self.assertEqual(output.results.occupants[0].route_node_ids[-1], 'exit:far')

    def test_legacy_layout_and_round_trip(self):
        self.assertIsNone(layout().flood)
        original = layout(flood())
        self.assertEqual(BuildingLayout.model_validate_json(original.model_dump_json()), original)

    def test_disabled_and_zero_match_baseline(self):
        baseline = run(layout())
        for config in [flood(enabled=False), flood(0)]:
            actual = run(layout(config))
            self.assertEqual(actual.results, baseline.results)
            self.assertEqual(actual.frames, baseline.frames)

    def test_blocked_near_exit_uses_far_exit(self):
        result = run(layout(flood())).results
        self.assertEqual(result.evacuated_count, 1)
        self.assertEqual(result.occupants[0].route_node_ids[-1], 'exit:far')

    def test_blocked_preferred_exit_falls_back(self):
        result = run(layout(flood(), preferred='near')).results
        self.assertEqual(result.occupants[0].route_node_ids[-1], 'exit:far')

    def test_moderate_flood_chooses_longer_dry_route(self):
        result = run(layout(flood(70))).results
        self.assertEqual(result.occupants[0].route_node_ids[-1], 'exit:far')

    def test_flood_slows_movement_without_inflating_distance(self):
        baseline = run(layout(two_exits=False)).results
        wet = run(layout(dict(x=5, y=5, radius_m=0.5, intensity=50), two_exits=False)).results
        self.assertGreater(wet.total_evacuation_time_s, baseline.total_evacuation_time_s)
        # Waypoints snap within 0.35 m; different speeds reach that threshold
        # on different steps. Slowdown must not inflate the geometric distance.
        self.assertAlmostEqual(wet.occupants[0].distance_m, baseline.occupants[0].distance_m, delta=0.35)
        self.assertLessEqual(wet.occupants[0].distance_m, 2.05)

    def test_blocked_routes_are_trapped_in_all_frames(self):
        output = run(layout(flood(), two_exits=False))
        self.assertEqual(output.results.evacuated_count, 0)
        self.assertEqual(output.results.remaining_count, 1)
        self.assertIsNone(output.results.total_evacuation_time_s)
        self.assertTrue(all(f.occupants[0].status == 'trapped' for f in output.frames))
        self.assertEqual(output.results.occupants[0].distance_m, 0)

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
            self.assertEqual(buildings.get_layout(saved.id).flood.intensity, 80)
            snapshot = simulations.create(saved.id, SimulationParameters(max_time_s=30))
            buildings.update_building(saved.id, layout())
            result = simulations.run(snapshot.id)
            self.assertEqual(result.results.occupants[0].route_node_ids[-1], 'exit:far')
            self.assertIsNone(buildings.get_layout(saved.id).flood)
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
        self.assertEqual(building.flood.radius_m, 0.5)

    def test_flood_reaches_initially_dry_exit_during_run(self):
        config = dict(x=10, y=5, radius_m=0.5, intensity=50, spread_speed_mps=2)
        for dt in (0.1, 0.25, 0.5):
            output = SimulationEngine().run(layout(config, two_exits=False),
                SimulationParameters(timestep_s=dt, max_time_s=5, frame_interval_s=dt))
            self.assertEqual(output.frames[0].occupants[0].status, 'active')
            self.assertEqual(output.results.evacuated_count, 0)
            self.assertEqual(output.frames[-1].occupants[0].status, 'trapped')
        config['spread_speed_mps'] = 0
        self.assertEqual(run(layout(config, two_exits=False)).results.evacuated_count, 1)

    def test_spread_competes_with_actual_walking_speed(self):
        config = dict(x=10, y=5, radius_m=0.5, intensity=50, spread_speed_mps=0.5)
        fast = layout(config, two_exits=False)
        slow = fast.model_copy(deep=True)
        slow.occupant_groups[0].walking_speed_mps = 0.1
        self.assertEqual(run(fast).results.evacuated_count, 1)
        self.assertEqual(run(slow).results.evacuated_count, 0)

    def test_spread_behind_occupant_does_not_block_dry_remaining_path(self):
        config = dict(x=4, y=5, radius_m=0.1, intensity=50, spread_speed_mps=0.8)
        output = run(layout(config, two_exits=False))
        self.assertGreater(output.frames[-1].flood_radius_m, 1)
        self.assertEqual(output.results.evacuated_count, 1)

    def test_outward_escape_recovers_dry_speed(self):
        from app.simulation.flood import segment_speed_factor
        config = FloodEmergency(x=4, y=5, radius_m=2, intensity=50)
        self.assertEqual(segment_speed_factor(config, 2, 5, 5, 8, 5), 0.5)
        self.assertEqual(segment_speed_factor(config, 2, 6.5, 5, 8, 5), 1)
        self.assertEqual(segment_speed_factor(config, 2, 6.5, 5, 5, 5), 0)

    def test_disabled_spread_preserves_dry_frames(self):
        baseline = run(layout())
        for patch in [dict(enabled=False), dict(intensity=0)]:
            config = dict(x=5, y=5, radius_m=1, intensity=50, spread_speed_mps=10) | patch
            output = run(layout(config))
            self.assertEqual(output.frames, baseline.frames)
            self.assertEqual(output.results, baseline.results)


if __name__ == '__main__':
    unittest.main()
