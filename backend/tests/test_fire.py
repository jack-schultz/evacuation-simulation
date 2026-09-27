import unittest

from pydantic import ValidationError
from app.domain.building import BuildingLayout, FireEmergency, SimulationFrame, SimulationParameters
from app.simulation.engine import SimulationEngine
from test_flood import layout, run


def fire_layout(config=None, **kwargs):
    data = layout(**kwargs).model_dump()
    data['fire'] = config
    return BuildingLayout.model_validate(data)


class FireTests(unittest.TestCase):
    def test_legacy_and_json_round_trip(self):
        self.assertEqual(layout().fires, [])
        self.assertIsNone(SimulationFrame(t=0, occupants=[]).fire_radius_m)
        original = fire_layout(dict(x=6, y=5, radius_m=1, intensity=40, spread_speed_mps=0.2))
        self.assertEqual(BuildingLayout.model_validate_json(original.model_dump_json()), original)

    def test_invalid_settings(self):
        for patch in [dict(radius_m=0), dict(radius_m=-1), dict(intensity=-1),
                      dict(intensity=101), dict(spread_speed_mps=-1), dict(x=-1),
                      dict(y=float('nan')), dict(radius_m=float('inf')),
                      dict(intensity=float('nan')), dict(spread_speed_mps=float('inf'))]:
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                FireEmergency.model_validate(dict(x=5, y=5) | patch)
        for patch in [dict(x=21, y=5), dict(x=5, y=21)]:
            with self.assertRaises(ValidationError):
                fire_layout(patch)

    def test_disabled_and_zero_intensity_preserve_baseline(self):
        baseline = run(layout())
        for patch in [dict(enabled=False), dict(intensity=0)]:
            output = run(fire_layout(dict(x=5, y=5, radius_m=10, spread_speed_mps=5) | patch))
            self.assertEqual(output.results, baseline.results)
            self.assertEqual(output.frames, baseline.frames)

    def test_fire_on_preferred_exit_does_not_reroute(self):
        # Disasters do not change pathing; preferred exit stays binding.
        for intensity in (1, 50, 100):
            output = run(fire_layout(dict(x=7, y=5, radius_m=0.5, intensity=intensity), preferred='near'))
            self.assertEqual(output.results.occupants[0].route_node_ids[-1], 'exit:near')

    def test_fire_contact_is_lethal(self):
        """Anyone inside the fire circle is trapped; no outward escape."""
        output = run(fire_layout(dict(x=5, y=5, radius_m=2, intensity=50, spread_speed_mps=0),
                                 two_exits=False))
        self.assertEqual(output.results.evacuated_count, 0)
        self.assertTrue(all(f.occupants[0].status == 'trapped' for f in output.frames[1:]))

    def test_higher_intensity_does_not_allow_escape_from_fire(self):
        """Legacy escape-through-fire behaviour is removed; contact kills."""
        for intensity in (25, 75, 100):
            result = run(fire_layout(dict(x=5, y=5, radius_m=1, intensity=intensity,
                                         spread_speed_mps=0), two_exits=False)).results
            self.assertEqual(result.evacuated_count, 0)

    def test_size_kills_more_by_contact_not_reroute(self):
        small = run(fire_layout(dict(x=10, y=5, radius_m=1, spread_speed_mps=0), two_exits=False))
        large = run(fire_layout(dict(x=10, y=5, radius_m=4, spread_speed_mps=0), two_exits=False))
        self.assertEqual(small.results.evacuated_count, 1)
        self.assertEqual(large.results.evacuated_count, 0)

    def test_spread_uses_simulation_clock_and_can_trap_people(self):
        for dt, interval in [(0.1, 0.2), (0.25, 0.5), (0.5, 1)]:
            building = fire_layout(dict(x=10, y=5, radius_m=0.5, spread_speed_mps=2), two_exits=False)
            output = SimulationEngine().run(building, SimulationParameters(
                timestep_s=dt, frame_interval_s=interval, max_time_s=5))
            self.assertEqual(output.frames[0].occupants[0].status, 'active')
            self.assertEqual(output.frames[-1].occupants[0].status, 'trapped')
            for frame in output.frames:
                self.assertAlmostEqual(frame.fire_radius_m, 0.5 + 2 * frame.t)
            self.assertEqual(building.fires[0].radius_m, 0.5)
        fixed = run(fire_layout(dict(x=10, y=5, radius_m=0.5, spread_speed_mps=0), two_exits=False))
        self.assertEqual(fixed.results.evacuated_count, 1)
        self.assertTrue(all(frame.fire_radius_m == 0.5 for frame in fixed.frames))

    def test_fire_and_flood_do_not_change_routes(self):
        building = fire_layout(dict(x=0, y=5, radius_m=0.5),
                               flood=dict(x=7, y=5, radius_m=0.5, intensity=80))
        output = run(building)
        # Shortest path is near; disasters no longer divert routing.
        self.assertEqual(output.results.evacuated_count, 1)
        self.assertEqual(output.results.occupants[0].route_node_ids[-1], 'exit:near')
        self.assertIsNotNone(output.frames[-1].fire_radius_m)
        self.assertIsNotNone(output.frames[-1].flood_radius_m)

    def test_fire_settings_and_frames_survive_persistence_and_snapshot(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.models.building import BuildingRecord
        from app.services.building_service import BuildingService
        from app.services.simulation_service import SimulationService
        engine = create_engine('sqlite:///:memory:')
        BuildingRecord.metadata.create_all(engine)
        with Session(engine) as db:
            buildings, simulations = BuildingService(db), SimulationService(db)
            original = fire_layout(dict(x=7, y=5, radius_m=0.5, intensity=70, spread_speed_mps=0.02))
            saved = buildings.create_building(original)
            self.assertEqual(buildings.get_layout(saved.id).fires, original.fires)
            snapshot = simulations.create(saved.id, SimulationParameters(max_time_s=10))
            buildings.update_building(saved.id, layout())
            result = simulations.run(snapshot.id)
            self.assertEqual(result.results.occupants[0].route_node_ids[-1], 'exit:near')
            self.assertEqual(result.frames[0].fire_radius_m, 0.5)
            self.assertEqual(simulations.get(snapshot.id).frames, result.frames)
            self.assertEqual(buildings.get_layout(saved.id).fires, [])
        engine.dispose()


class MultiFireTests(unittest.TestCase):
    def test_two_fires_produce_separate_plumes(self):
        from app.simulation.hazards import active_fire_plumes

        building = BuildingLayout.model_validate({
            "width": 30,
            "height": 20,
            "spaces": [
                {"id": "a", "name": "A", "type": "room", "x": 0, "y": 0, "width": 10, "height": 10},
                {"id": "b", "name": "B", "type": "room", "x": 15, "y": 0, "width": 10, "height": 10},
            ],
            "exits": [
                {"id": "ea", "x": 0, "y": 5, "width": 1, "connected_space_id": "a", "flow_rate_per_s": 100},
            ],
            "occupant_groups": [
                {"id": "g", "name": "People", "count": 1, "space_id": "a"},
            ],
            "fires": [
                {"id": "f1", "x": 5, "y": 5, "radius_m": 1, "intensity": 50, "spread_speed_mps": 0,
                 "emit_smoke": False},
                {"id": "f2", "x": 20, "y": 5, "radius_m": 1, "intensity": 50, "spread_speed_mps": 0,
                 "emit_smoke": False},
            ],
        })
        plumes = active_fire_plumes(building, 0.0)
        self.assertEqual(len(plumes), 2)
        self.assertEqual({(round(p.x), round(p.y)) for p in plumes}, {(5, 5), (20, 5)})
