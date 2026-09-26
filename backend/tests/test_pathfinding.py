"""Pathfinding unit tests."""

import pytest

from app.domain.building import BuildingLayout, Door, Exit, OccupantGroup, Space, SpaceType
from app.simulation.graph import NavigationGraphBuilder
from app.simulation.routing import DijkstraRouteSelector


def _simple_layout() -> BuildingLayout:
    return BuildingLayout(
        name="Test",
        width=20,
        height=20,
        spaces=[
            Space(id="r1", name="R1", type=SpaceType.ROOM, x=0, y=0, width=8, height=8),
            Space(id="r2", name="R2", type=SpaceType.ROOM, x=10, y=0, width=8, height=8),
        ],
        doors=[
            Door(id="d1", x=9, y=4, width=1.0, connects=("r1", "r2")),
        ],
        exits=[
            Exit(id="e1", x=18, y=4, width=1.0, connected_space_id="r2"),
        ],
        occupant_groups=[
            OccupantGroup(id="g1", name="G1", count=1, space_id="r1", walking_speed_mps=1.2),
        ],
    )


def test_dijkstra_finds_path_to_exit():
    layout = _simple_layout()
    defaults = {
        "door_flow_per_s": 1.0,
        "stairs_flow_per_s": 0.8,
        "exit_flow_per_s": 1.5,
        "corridor_density_per_m2": 2.0,
    }
    graph = NavigationGraphBuilder().build(layout, defaults)
    selector = DijkstraRouteSelector()
    route = selector.select_route(graph, graph.space_node_ids["r1"])
    assert route[0] == "space:r1"
    assert route[-1] == "exit:e1"
    assert "door:d1" in route


def test_dijkstra_preferred_exit():
    layout = BuildingLayout(
        name="Two exits",
        width=30,
        height=10,
        spaces=[
            Space(id="r1", name="R1", type=SpaceType.ROOM, x=10, y=0, width=10, height=10),
        ],
        doors=[],
        exits=[
            Exit(id="east", x=21, y=5, width=1, connected_space_id="r1"),
            Exit(id="west", x=9, y=5, width=1, connected_space_id="r1"),
        ],
        occupant_groups=[
            OccupantGroup(
                id="g1",
                name="G1",
                count=1,
                space_id="r1",
                walking_speed_mps=1.2,
                destination_exit_id="east",
            ),
        ],
    )
    defaults = {
        "door_flow_per_s": 1.0,
        "stairs_flow_per_s": 0.8,
        "exit_flow_per_s": 1.5,
        "corridor_density_per_m2": 2.0,
    }
    graph = NavigationGraphBuilder().build(layout, defaults)
    route = DijkstraRouteSelector().select_route(
        graph, graph.space_node_ids["r1"], preferred_exit_id="east"
    )
    assert route[-1] == "exit:east"


def test_no_path_raises():
    layout = BuildingLayout(
        name="Disconnected",
        width=30,
        height=10,
        spaces=[
            Space(id="r1", name="R1", type=SpaceType.ROOM, x=0, y=0, width=5, height=5),
            Space(id="r2", name="R2", type=SpaceType.ROOM, x=20, y=0, width=5, height=5),
        ],
        doors=[],
        exits=[Exit(id="e1", x=25, y=2, width=1, connected_space_id="r2")],
        occupant_groups=[
            OccupantGroup(id="g1", name="G1", count=1, space_id="r1", walking_speed_mps=1.2),
        ],
    )
    defaults = {
        "door_flow_per_s": 1.0,
        "stairs_flow_per_s": 0.8,
        "exit_flow_per_s": 1.5,
        "corridor_density_per_m2": 2.0,
    }
    graph = NavigationGraphBuilder().build(layout, defaults)
    with pytest.raises(ValueError, match="No path"):
        DijkstraRouteSelector().select_route(graph, graph.space_node_ids["r1"])
