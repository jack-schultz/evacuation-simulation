"""Direct simulation engine smoke test."""

from app.domain.building import SimulationParameters
from app.services.seed import create_seed_layout
from app.simulation.engine import SimulationEngine


def test_seed_building_evacuates():
    layout = create_seed_layout()
    layout.occupant_groups[0].count = 5
    layout.occupant_groups[1].count = 5
    params = SimulationParameters(timestep_s=0.25, max_time_s=300, frame_interval_s=2.0)
    output = SimulationEngine().run(layout, params)
    assert output.results.evacuated_count == 10
    assert output.results.total_evacuation_time_s is not None
    assert len(output.frames) > 0
