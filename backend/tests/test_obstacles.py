"""Rectangle persistence, visibility and physical movement regression tests."""
import unittest
from pydantic import ValidationError
from app.domain.building import BuildingLayout, SimulationParameters
from app.simulation.engine import SimulationEngine
from app.simulation.obstacles import segment_hits_rectangle


def layout_with_obstacles(obstacles=None, count=1, spawn=(2, 5)):
    return BuildingLayout.model_validate({
        "width": 20, "height": 12,
        "spaces": [{"id": "room", "name": "Room", "type": "room",
                    "vertices": [[0, 0], [20, 0], [20, 12], [0, 12]]}],
        "exits": [{"id": "exit", "x": 20, "y": 5, "width": 1.2,
                   "connected_space_id": "room"}],
        "occupant_groups": [{"id": "group", "name": "People", "count": count,
            "space_id": "room", "spawn_x": spawn[0], "spawn_y": spawn[1]}],
        "obstacles": obstacles if obstacles is not None else [
            {"id": "block", "x": 8, "y": 3, "width": 4, "height": 4}],
    })


class ObstacleTests(unittest.TestCase):
    def run_layout(self, layout, timestep=0.1):
        return SimulationEngine().run(layout, SimulationParameters(
            max_time_s=120, timestep_s=timestep, frame_interval_s=timestep))

    def assert_clear_frames(self, layout, output):
        previous = {}
        for frame in output.frames:
            for person in frame.occupants:
                for obstacle in layout.obstacles:
                    if obstacle.floor_id != person.floor_id:
                        continue
                    # Frame coordinates are rounded to millimetres.
                    self.assertFalse(segment_hits_rectangle(
                        (person.x, person.y), (person.x, person.y), obstacle, 0.249),
                        (frame.t, person))
                    if person.id in previous:
                        self.assertFalse(segment_hits_rectangle(
                            previous[person.id], (person.x, person.y), obstacle, 0.249),
                            (frame.t, previous[person.id], person))
                previous[person.id] = (person.x, person.y)

    def test_detour_evacuates_and_frames_never_cross_obstacle(self):
        layout = layout_with_obstacles()
        output = self.run_layout(layout)
        self.assertEqual(output.results.evacuated_count, 1)
        self.assertTrue(any(":obstacle:" in n for n in output.results.occupants[0].route_node_ids))
        self.assert_clear_frames(layout, output)

    def test_crowd_detours(self):
        layout = layout_with_obstacles(count=10)
        output = self.run_layout(layout)
        self.assertEqual(output.results.evacuated_count, 10)
        self.assert_clear_frames(layout, output)

    def test_centroid_and_spawn_inside_rectangle_are_relocated(self):
        layout = layout_with_obstacles(spawn=(10, 5))
        output = self.run_layout(layout)
        self.assertEqual(output.results.evacuated_count, 1)
        self.assert_clear_frames(layout, output)

    def test_full_barrier_traps_without_exception(self):
        layout = layout_with_obstacles([{"id": "wall", "x": 8, "y": 0, "width": 1, "height": 12}])
        output = self.run_layout(layout)
        self.assertEqual(output.results.evacuated_count, 0)
        self.assertEqual(output.frames[0].occupants[0].status.value, "trapped")

    def test_other_floor_does_not_block(self):
        data = layout_with_obstacles().model_dump()
        data["floors"].append({"id": "upper", "name": "Upper"})
        data["obstacles"][0]["floor_id"] = "upper"
        layout = BuildingLayout.model_validate(data)
        output = self.run_layout(layout)
        self.assertEqual(output.results.evacuated_count, 1)
        self.assertFalse(any(":obstacle:" in n for n in output.results.occupants[0].route_node_ids))

    def test_thin_rectangle_with_large_step(self):
        layout = layout_with_obstacles([{"id": "thin", "x": 8, "y": 3, "width": 0.05, "height": 4}])
        output = self.run_layout(layout, timestep=0.5)
        self.assertEqual(output.results.evacuated_count, 1)
        self.assert_clear_frames(layout, output)

    def test_overlapping_rectangles(self):
        layout = layout_with_obstacles([
            {"id": "a", "x": 7, "y": 3, "width": 3, "height": 4},
            {"id": "b", "x": 9, "y": 4, "width": 3, "height": 4}])
        output = self.run_layout(layout)
        self.assertEqual(output.results.evacuated_count, 1)
        self.assert_clear_frames(layout, output)

    def test_no_body_clearance_in_gap(self):
        layout = layout_with_obstacles([{"id": "wall", "x": 8, "y": 0.4, "width": 1, "height": 11.6}])
        output = self.run_layout(layout)
        self.assertEqual(output.results.evacuated_count, 0)

    def test_saved_layout_round_trip_and_legacy_default(self):
        layout = layout_with_obstacles()
        self.assertEqual(BuildingLayout.model_validate_json(layout.model_dump_json()).obstacles, layout.obstacles)
        data = layout.model_dump()
        del data["obstacles"]
        self.assertEqual(BuildingLayout.model_validate(data).obstacles, [])

    def test_invalid_rectangles_rejected(self):
        for patch in ({"width": 0}, {"height": -1}, {"x": -1}, {"floor_id": "missing"},
                      {"width": float("inf")}, {"x": 19}):
            data = layout_with_obstacles().model_dump()
            data["obstacles"][0].update(patch)
            with self.assertRaises(ValidationError):
                BuildingLayout.model_validate(data)

    def test_narrow_but_passable_gap(self):
        layout = layout_with_obstacles([{"id": "wall", "x": 8, "y": 0.9, "width": 1, "height": 11.1}])
        output = self.run_layout(layout)
        self.assertEqual(output.results.evacuated_count, 1)
        self.assert_clear_frames(layout, output)

    def test_exit_on_spawn_side_of_full_barrier(self):
        layout = layout_with_obstacles([{"id": "wall", "x": 8, "y": 0, "width": 1, "height": 12}],
                                       spawn=(15, 5))
        output = self.run_layout(layout)
        self.assertEqual(output.results.evacuated_count, 1)
        self.assert_clear_frames(layout, output)

    def test_detour_then_door_to_adjacent_room(self):
        data = layout_with_obstacles().model_dump()
        data["width"] = 30
        data["spaces"].append({"id": "next", "name": "Next", "type": "room",
                              "vertices": [[20, 0], [30, 0], [30, 12], [20, 12]]})
        data["doors"] = [{"id": "door", "x": 20, "y": 5, "width": 1.2, "connects": ["room", "next"]}]
        data["exits"][0].update(x=30, connected_space_id="next")
        layout = BuildingLayout.model_validate(data)
        output = self.run_layout(layout)
        self.assertEqual(output.results.evacuated_count, 1)
        self.assert_clear_frames(layout, output)

    def test_snapshot_keeps_obstacles_after_building_edit(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.core.database import Base
        from app.services.building_service import BuildingService
        from app.services.simulation_service import SimulationService
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                buildings = BuildingService(db)
                simulations = SimulationService(db)
                layout = layout_with_obstacles()
                building = buildings.create_building(layout)
                params = SimulationParameters(max_time_s=120)
                before = simulations.create(building.id, params)
                buildings.update_building(building.id, layout_with_obstacles([]))
                after = simulations.create(building.id, params)
                result_before = simulations.run(before.id)
                result_after = simulations.run(after.id)
                self.assertTrue(any(":obstacle:" in n for n in result_before.results.occupants[0].route_node_ids))
                self.assertFalse(any(":obstacle:" in n for n in result_after.results.occupants[0].route_node_ids))
        finally:
            engine.dispose()
