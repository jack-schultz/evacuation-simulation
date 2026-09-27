"""RMS Titanic seed template: decks, flood, poop exits, runnable routes."""

import unittest

from app.domain.building import SimulationParameters
from app.domain.geometry import point_in_polygon
from app.services.seed import create_titanic_template
from app.simulation.engine import SimulationEngine


class TitanicTemplateTests(unittest.TestCase):
    def test_layout_shape(self):
        layout = create_titanic_template()
        self.assertEqual(layout.name, "RMS Titanic")
        self.assertGreaterEqual(len(layout.floors), 5)
        self.assertEqual([f.id for f in layout.floors], [f"floor-{i}" for i in range(6)])
        self.assertTrue(layout.floods)
        flood = layout.floods[0]
        self.assertEqual(flood.floor_id, "floor-0")
        bow = next(s for s in layout.spaces if s.id == "d0_bow")
        self.assertTrue(point_in_polygon(flood.x, flood.y, bow.vertices))
        self.assertTrue(layout.exits)
        self.assertTrue(all(e.floor_id == "floor-5" for e in layout.exits))
        self.assertTrue(all(e.connected_space_id == "poop_deck" for e in layout.exits))
        self.assertGreaterEqual(sum(g.count for g in layout.occupant_groups), 80)

    def test_stair_chains_reach_poop(self):
        layout = create_titanic_template()
        by_id = {s.id: s for s in layout.spaces}
        for bank in ("grand", "aft"):
            top_down = by_id[f"{bank}_stair_down_5"]
            self.assertEqual(top_down.floor_id, "floor-5")
            self.assertEqual(top_down.linked_stair_id, f"{bank}_stair_up_4")
            partner = by_id[top_down.linked_stair_id]
            self.assertEqual(partner.linked_stair_id, f"{bank}_stair_down_5")

    def test_partial_evacuation_runs(self):
        layout = create_titanic_template()
        params = SimulationParameters(
            max_time_s=180.0,
            timestep_s=0.5,
            frame_interval_s=10.0,
        )
        output = SimulationEngine().run(layout, params)
        self.assertEqual(output.results.total_occupants, sum(g.count for g in layout.occupant_groups))
        self.assertGreater(output.results.evacuated_count, 0)
        self.assertGreater(len(output.frames), 1)


if __name__ == "__main__":
    unittest.main()
