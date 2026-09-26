import pytest

from app.domain.building import BuildingLayout, Exit, OccupantGroup, Space, SpaceType, SimulationParameters
from app.simulation.engine import SimulationEngine
from app.simulation.flow import CapacityFlowModel, UnlimitedFlowModel
from app.simulation.graph import EdgeKind, GraphEdge


def _bottleneck_layout(count: int = 20) -> BuildingLayout:
    return BuildingLayout(
        name="Bottleneck",
        width=20,
        height=20,
        spaces=[
            Space(id="room", name="Room", type=SpaceType.ROOM, x=2, y=2, width=10, height=10),
        ],
        doors=[],
        exits=[
            Exit(
                id="exit",
                name="Exit",
                x=7,
                y=1,
                width=0.8,
                connected_space_id="room",
                flow_rate_per_s=0.5,
            ),
        ],
        occupant_groups=[
            OccupantGroup(
                id="g1",
                name="Crowd",
                count=count,
                space_id="room",
                walking_speed_mps=1.5,
            ),
        ],
    )


def test_congestion_increases_evacuation_time():
    layout = _bottleneck_layout(30)
    params = SimulationParameters(
        timestep_s=0.25,
        max_time_s=300,
        exit_flow_per_s=0.5,
        frame_interval_s=5.0,
    )

    congested = SimulationEngine(flow_model=CapacityFlowModel()).run(layout, params)
    unlimited = SimulationEngine(flow_model=UnlimitedFlowModel()).run(layout, params)

    assert congested.results.evacuated_count == 30
    assert unlimited.results.evacuated_count == 30
    assert congested.results.total_evacuation_time_s is not None
    assert unlimited.results.total_evacuation_time_s is not None
    assert congested.results.total_evacuation_time_s > unlimited.results.total_evacuation_time_s
    assert congested.results.average_wait_time_s is not None
    assert congested.results.average_wait_time_s > 0
    assert any(h.element_id == "exit" for h in congested.results.congestion_hotspots)


def test_capacity_flow_model_limits_door_throughput():
    model = CapacityFlowModel()
    edge = GraphEdge(
        id="e",
        from_id="a",
        to_id="b",
        distance_m=1.0,
        kind=EdgeKind.DOOR,
        width_m=1.0,
        flow_rate_per_s=2.0,
        capacity_density_per_m2=None,
        area_m2=None,
        element_id="d1",
    )
    assert model.calculate_capacity(edge, timestep_s=0.5, occupants_on_element=0) == pytest.approx(1.0)
