import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.domain.building import BuildingLayout, SimulationParameters
from app.services.building_service import BuildingService
from app.services.simulation_service import SimulationService


class ExitMoveTests(unittest.TestCase):
    def test_saved_exit_move_updates_new_runs_and_preserves_old_snapshots(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                buildings = BuildingService(db)
                simulations = SimulationService(db)
                layout = BuildingLayout.model_validate({
                    "name": "Two rooms", "width": 20, "height": 10,
                    "spaces": [
                        {"id": sid, "name": sid, "type": "room", "x": x, "y": 0,
                         "width": 10, "height": 10}
                        for sid, x in (("a", 0), ("b", 10))
                    ],
                    "doors": [{"id": "door", "x": 10, "y": 5, "width": 1.2, "connects": ["a", "b"]}],
                    "exits": [{"id": "exit", "x": 0, "y": 5, "width": 1.2,
                               "connected_space_id": "a"}],
                    "occupant_groups": [
                        {"id": sid, "name": sid, "count": 1, "space_id": sid}
                        for sid in ("a",)
                    ],
                })
                building = buildings.create_building(layout)
                params = SimulationParameters(max_time_s=30)
                old_sim = simulations.create(building.id, params)

                payload = layout.model_dump()
                payload["exits"][0].update(x=20, y=5, connected_space_id="b")
                buildings.update_building(building.id, BuildingLayout.model_validate(payload))
                saved_exit = buildings.get_layout(building.id).exits[0]
                self.assertEqual((saved_exit.x, saved_exit.y, saved_exit.connected_space_id),
                                 (20, 5, "b"))

                new_sim = simulations.create(building.id, params)
                for simulation, expected_route, exit_x in (
                    (old_sim, ["space:a", "exit:exit"], 0),
                    (new_sim, ["space:a", "door:door", "space:b", "exit:exit"], 20),
                ):
                    result = simulations.run(simulation.id)
                    evacuated = [o for o in result.results.occupants if o.evacuated]
                    self.assertEqual([o.group_id for o in evacuated], ["a"])
                    self.assertEqual(evacuated[0].route_node_ids, expected_route)
                    last = next(o for o in result.frames[-1].occupants
                                if o.group_id == "a")
                    self.assertLess(abs(last.x - exit_x), 1)
        finally:
            engine.dispose()
