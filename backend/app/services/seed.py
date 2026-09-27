"""Seed example buildings used by the editor."""

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


def create_23_floor_template() -> BuildingLayout:
    """Create a 23-floor, WTC-inspired twin-tower evacuation template.

    The plan uses the published 208 ft square tower footprint and 87 ft by
    135 ft central core proportions, scaled to metres for this estimator.
    """
    floor_count = 23
    tower_size = 63.0
    core_width = 27.0
    core_height = 41.0
    tower_gap = 18.0
    left_x = 4.0
    right_x = left_x + tower_size + tower_gap
    top_y = 2.0
    core_y = top_y + (tower_size - core_height) / 2
    core_x_offset = (tower_size - core_width) / 2
    tower_names = ("North Tower", "South Tower")

    floors = [
        Floor(
            id=f"floor-{index}",
            name="Ground" if index == 0 else f"Level {index}",
            elevation_m=index * 3.2,
            order=index,
        )
        for index in range(floor_count)
    ]

    spaces: list[Space] = []
    doors: list[Door] = []
    occupant_groups: list[OccupantGroup] = []
    for floor_index in range(floor_count):
        floor_id = f"floor-{floor_index}"
        for tower_index, tower_x in enumerate((left_x, right_x)):
            tower_name = tower_names[tower_index]
            tower_key = "north" if tower_index == 0 else "south"
            core_x = tower_x + core_x_offset
            office_zones = [
                ("north", tower_x, top_y, tower_size, core_y - top_y),
                (
                    "south",
                    tower_x,
                    core_y + core_height,
                    tower_size,
                    top_y + tower_size - (core_y + core_height),
                ),
                ("west", tower_x, core_y, core_x_offset, core_height),
                (
                    "east",
                    core_x + core_width,
                    core_y,
                    tower_size - core_x_offset - core_width,
                    core_height,
                ),
            ]
            core_id = f"{tower_key}_core_{floor_index}"
            spaces.append(
                Space(
                    id=core_id,
                    name=(
                        f"{tower_name} sky lobby {floor_index + 1}"
                        if floor_index in (9, 16)
                        else f"{tower_name} central core {floor_index + 1}"
                    ),
                    type=SpaceType.CORRIDOR,
                    floor_id=floor_id,
                    vertices=rect_vertices(core_x, core_y, core_width, core_height),
                )
            )

            for zone, x, y, width, height in office_zones:
                office_id = f"{tower_key}_{zone}_office_{floor_index}"
                spaces.append(
                    Space(
                        id=office_id,
                        name=f"{tower_name} {zone} offices {floor_index + 1}",
                        type=SpaceType.ROOM,
                        floor_id=floor_id,
                        vertices=rect_vertices(x, y, width, height),
                    )
                )
                occupant_groups.append(
                    OccupantGroup(
                        id=f"occupants_{office_id}",
                        name=f"{tower_name} {zone} occupants {floor_index + 1}",
                        count=2,
                        space_id=office_id,
                        floor_id=floor_id,
                        walking_speed_mps=1.2,
                    )
                )

            for zone, door_x, door_y in (
                ("north", core_x + core_width / 2, core_y),
                ("south", core_x + core_width / 2, core_y + core_height),
                ("west", core_x, core_y + core_height / 2),
                ("east", core_x + core_width, core_y + core_height / 2),
            ):
                doors.append(
                    Door(
                        id=f"door_{tower_key}_{zone}_{floor_index}",
                        name=f"{tower_name} {zone} core door {floor_index + 1}",
                        x=door_x,
                        y=door_y,
                        width=1.2,
                        connects=(f"{tower_key}_{zone}_office_{floor_index}", core_id),
                        floor_id=floor_id,
                    )
                )

            for stair_index in range(3):
                stair_x = core_x + 1.5 + stair_index * 8.0
                down_id = f"{tower_key}_stair_{stair_index}_down_{floor_index}"
                up_id = f"{tower_key}_stair_{stair_index}_up_{floor_index}"
                spaces.extend(
                    [
                        Space(
                            id=down_id,
                            name=f"{tower_name} stair {stair_index + 1} down {floor_index + 1}",
                            type=SpaceType.STAIRS,
                            floor_id=floor_id,
                            linked_stair_id=(
                                f"{tower_key}_stair_{stair_index}_up_{floor_index - 1}"
                                if floor_index > 0
                                else None
                            ),
                            vertices=rect_vertices(stair_x, core_y + 2.0, 4.5, 16.0),
                        ),
                        Space(
                            id=up_id,
                            name=f"{tower_name} stair {stair_index + 1} up {floor_index + 1}",
                            type=SpaceType.STAIRS,
                            floor_id=floor_id,
                            linked_stair_id=(
                                f"{tower_key}_stair_{stair_index}_down_{floor_index + 1}"
                                if floor_index < floor_count - 1
                                else None
                            ),
                            vertices=rect_vertices(stair_x, core_y + 23.0, 4.5, 16.0),
                        ),
                    ]
                )
                doors.append(
                    Door(
                        id=f"door_{down_id}_{up_id}",
                        name=f"{tower_name} stair {stair_index + 1} landing {floor_index + 1}",
                        x=stair_x + 2.25,
                        y=core_y + 20.0,
                        width=1.2,
                        connects=(down_id, up_id),
                        floor_id=floor_id,
                    )
                )

    ground_y = core_y + core_height / 2

    return BuildingLayout(
        name= "Dual NYC Office Template (2001)",
        width=right_x + tower_size + 4.0,
        height=top_y + tower_size + 4.0,
        meters_per_cell=1.0,
        floors=floors,
        spaces=spaces,
        doors=doors,
        exits=[
            Exit(
                id="exit_north_tower",
                name="North Tower ground exit",
                x=left_x,
                y=ground_y,
                width=1.4,
                connected_space_id="north_west_office_0",
                floor_id="floor-0",
                flow_rate_per_s=1.2,
            ),
            Exit(
                id="exit_south_tower",
                name="South Tower ground exit",
                x=right_x,
                y=ground_y,
                width=1.4,
                connected_space_id="south_west_office_0",
                floor_id="floor-0",
                flow_rate_per_s=1.2,
            ),
        ],
        occupant_groups=occupant_groups,
    )
