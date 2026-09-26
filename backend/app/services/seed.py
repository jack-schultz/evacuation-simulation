"""Seed example building: two floors linked by stairs."""

from app.domain.building import (
    BuildingLayout,
    Door,
    Exit,
    Floor,
    OccupantGroup,
    Space,
    SpaceType,
)
from app.domain.geometry import rect_vertices


def create_seed_layout() -> BuildingLayout:
    """Upper offices evacuate down stairs to a ground exit.

    Floors share the same XY footprint so the editor floor tabs show stacked plans.
    """
    ground = Floor(id="floor-0", name="Ground", elevation_m=0.0, order=0)
    level1 = Floor(id="floor-1", name="Level 1", elevation_m=3.2, order=1)

    return BuildingLayout(
        name="Two-Floor Office",
        width=30.0,
        height=24.0,
        meters_per_cell=1.0,
        floors=[ground, level1],
        spaces=[
            Space(
                id="lobby",
                name="Lobby",
                type=SpaceType.ROOM,
                floor_id="floor-0",
                vertices=rect_vertices(4.0, 4.0, 16.0, 12.0),
            ),
            Space(
                id="stairs_g",
                name="Stairs (Ground)",
                type=SpaceType.STAIRS,
                floor_id="floor-0",
                linked_stair_id="stairs_1",
                vertices=rect_vertices(20.0, 6.0, 4.0, 8.0),
            ),
            Space(
                id="office_1",
                name="Office Level 1",
                type=SpaceType.ROOM,
                floor_id="floor-1",
                vertices=rect_vertices(4.0, 4.0, 16.0, 12.0),
            ),
            Space(
                id="stairs_1",
                name="Stairs (Level 1)",
                type=SpaceType.STAIRS,
                floor_id="floor-1",
                linked_stair_id="stairs_g",
                vertices=rect_vertices(20.0, 6.0, 4.0, 8.0),
            ),
        ],
        doors=[
            Door(
                id="door_lobby_stairs",
                name="Lobby–Stairs",
                x=20.0,
                y=10.0,
                width=1.2,
                connects=("lobby", "stairs_g"),
                floor_id="floor-0",
            ),
            Door(
                id="door_office_stairs",
                name="Office–Stairs",
                x=20.0,
                y=10.0,
                width=1.2,
                connects=("office_1", "stairs_1"),
                floor_id="floor-1",
            ),
        ],
        exits=[
            Exit(
                id="exit_street",
                name="Street Exit",
                x=4.0,
                y=10.0,
                width=1.4,
                connected_space_id="lobby",
                floor_id="floor-0",
                flow_rate_per_s=1.2,
            ),
        ],
        occupant_groups=[
            OccupantGroup(
                id="group_l1",
                name="Level 1 occupants",
                count=28,
                space_id="office_1",
                floor_id="floor-1",
                walking_speed_mps=1.2,
            ),
            OccupantGroup(
                id="group_lobby",
                name="Lobby occupants",
                count=12,
                space_id="lobby",
                floor_id="floor-0",
                walking_speed_mps=1.15,
            ),
        ],
    )
