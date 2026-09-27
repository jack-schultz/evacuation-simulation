"""Seed example buildings used by the editor."""

import math

from app.domain.building import (
    BuildingLayout,
    Door,
    Exit,
    FloodEmergency,
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


def create_titanic_template() -> BuildingLayout:
    """RMS Titanic–inspired multi-deck evacuation template.

    Condensed ship plan (~106 m × 14 m beam on a 110 × 20 m canvas). Flood
    starts at the bow on F Deck; occupants climb and move aft to Poop Deck exits.
    """
    # Canvas and hull extents (bow west / left, stern east / right).
    width, height = 110.0, 20.0
    ship_top, ship_bot = 3.0, 17.0
    mid_y = (ship_top + ship_bot) / 2.0  # 10.0
    corridor_top, corridor_bot = 8.5, 11.5

    bow_x0, bow_x1 = 2.0, 16.0
    fwd_x0, fwd_x1 = 16.0, 40.0
    mid_x0, mid_x1 = 40.0, 70.0
    aft_x0, aft_x1 = 70.0, 94.0
    stern_x0, stern_x1 = 94.0, 108.0

    deck_specs = [
        ("floor-0", "F Deck (Orlop)", 0.0, 0),
        ("floor-1", "E Deck", 3.2, 1),
        ("floor-2", "D Deck", 6.4, 2),
        ("floor-3", "B Deck", 9.6, 3),
        ("floor-4", "Boat Deck", 12.8, 4),
        ("floor-5", "Poop Deck", 16.0, 5),
    ]
    floors = [
        Floor(id=fid, name=name, elevation_m=elev, order=order)
        for fid, name, elev, order in deck_specs
    ]

    def bow_vertices() -> list[tuple[float, float]]:
        # Pointed bow taper into the full beam at bow_x1.
        return [
            (bow_x0, mid_y),
            (bow_x0 + 6.0, ship_top + 1.5),
            (bow_x1, ship_top),
            (bow_x1, ship_bot),
            (bow_x0 + 6.0, ship_bot - 1.5),
        ]

    def stern_vertices() -> list[tuple[float, float]]:
        # Slightly narrowed but blunt stern (room for embarkation width).
        return [
            (stern_x0, ship_top),
            (stern_x1, ship_top + 1.5),
            (stern_x1, ship_bot - 1.5),
            (stern_x0, ship_bot),
        ]

    def poop_vertices() -> list[tuple[float, float]]:
        # Stern raised deck with a wide aft face for lifeboat exits.
        poop_x0 = 86.0
        return [
            (poop_x0, ship_top + 1.0),
            (stern_x1, ship_top + 1.5),
            (stern_x1, ship_bot - 1.5),
            (poop_x0, ship_bot - 1.0),
        ]

    spaces: list[Space] = []
    doors: list[Door] = []
    occupant_groups: list[OccupantGroup] = []

    # --- Habitable lower decks: F, E, D, B (floors 0–3) ---
    lower_room_names = {
        0: {
            "bow": "F Deck bow hold",
            "corridor": "F Deck alleyway",
            "port_fwd": "F Deck port stores",
            "stbd_fwd": "F Deck starboard stores",
            "port_mid": "F Deck port boiler flats",
            "stbd_mid": "F Deck starboard boiler flats",
            "port_aft": "F Deck port third-class",
            "stbd_aft": "F Deck starboard third-class",
            "stern": "F Deck stern hold",
        },
        1: {
            "bow": "E Deck bow cabins",
            "corridor": "Scotland Road",
            "port_fwd": "E Deck port cabins",
            "stbd_fwd": "E Deck starboard cabins",
            "port_mid": "E Deck port cabins mid",
            "stbd_mid": "E Deck starboard cabins mid",
            "port_aft": "E Deck port aft cabins",
            "stbd_aft": "E Deck starboard aft cabins",
            "stern": "E Deck stern cabins",
        },
        2: {
            "bow": "D Deck bow",
            "corridor": "D Deck reception corridor",
            "port_fwd": "D Deck port dining",
            "stbd_fwd": "D Deck starboard dining",
            "port_mid": "First-class dining saloon (port)",
            "stbd_mid": "First-class dining saloon (stbd)",
            "port_aft": "D Deck port reception",
            "stbd_aft": "D Deck starboard reception",
            "stern": "D Deck second-class dining",
        },
        3: {
            "bow": "B Deck bow suites",
            "corridor": "B Deck corridor",
            "port_fwd": "B Deck port suites",
            "stbd_fwd": "B Deck starboard suites",
            "port_mid": "B Deck port cabins",
            "stbd_mid": "B Deck starboard cabins",
            "port_aft": "B Deck port aft",
            "stbd_aft": "B Deck starboard aft",
            "stern": "B Deck second-class",
        },
    }

    for floor_index in range(4):
        floor_id = f"floor-{floor_index}"
        names = lower_room_names[floor_index]
        prefix = f"d{floor_index}"

        bow_id = f"{prefix}_bow"
        corridor_id = f"{prefix}_corridor"
        stern_id = f"{prefix}_stern"
        port_fwd_id = f"{prefix}_port_fwd"
        stbd_fwd_id = f"{prefix}_stbd_fwd"
        port_mid_id = f"{prefix}_port_mid"
        stbd_mid_id = f"{prefix}_stbd_mid"
        port_aft_id = f"{prefix}_port_aft"
        stbd_aft_id = f"{prefix}_stbd_aft"

        spaces.extend(
            [
                Space(
                    id=bow_id,
                    name=names["bow"],
                    type=SpaceType.ROOM,
                    floor_id=floor_id,
                    vertices=bow_vertices(),
                ),
                Space(
                    id=corridor_id,
                    name=names["corridor"],
                    type=SpaceType.CORRIDOR,
                    floor_id=floor_id,
                    vertices=rect_vertices(
                        fwd_x0, corridor_top, stern_x0 - fwd_x0, corridor_bot - corridor_top
                    ),
                ),
                Space(
                    id=port_fwd_id,
                    name=names["port_fwd"],
                    type=SpaceType.ROOM,
                    floor_id=floor_id,
                    vertices=rect_vertices(
                        fwd_x0, ship_top, fwd_x1 - fwd_x0, corridor_top - ship_top
                    ),
                ),
                Space(
                    id=stbd_fwd_id,
                    name=names["stbd_fwd"],
                    type=SpaceType.ROOM,
                    floor_id=floor_id,
                    vertices=rect_vertices(
                        fwd_x0, corridor_bot, fwd_x1 - fwd_x0, ship_bot - corridor_bot
                    ),
                ),
                Space(
                    id=port_mid_id,
                    name=names["port_mid"],
                    type=SpaceType.ROOM,
                    floor_id=floor_id,
                    vertices=rect_vertices(
                        mid_x0, ship_top, mid_x1 - mid_x0, corridor_top - ship_top
                    ),
                ),
                Space(
                    id=stbd_mid_id,
                    name=names["stbd_mid"],
                    type=SpaceType.ROOM,
                    floor_id=floor_id,
                    vertices=rect_vertices(
                        mid_x0, corridor_bot, mid_x1 - mid_x0, ship_bot - corridor_bot
                    ),
                ),
                Space(
                    id=port_aft_id,
                    name=names["port_aft"],
                    type=SpaceType.ROOM,
                    floor_id=floor_id,
                    vertices=rect_vertices(
                        aft_x0, ship_top, aft_x1 - aft_x0, corridor_top - ship_top
                    ),
                ),
                Space(
                    id=stbd_aft_id,
                    name=names["stbd_aft"],
                    type=SpaceType.ROOM,
                    floor_id=floor_id,
                    vertices=rect_vertices(
                        aft_x0, corridor_bot, aft_x1 - aft_x0, ship_bot - corridor_bot
                    ),
                ),
                Space(
                    id=stern_id,
                    name=names["stern"],
                    type=SpaceType.ROOM,
                    floor_id=floor_id,
                    vertices=stern_vertices(),
                ),
            ]
        )

        # Longitudinal + cabin doors (shared edges).
        door_specs = [
            (f"door_{prefix}_bow", bow_x1, mid_y, bow_id, corridor_id, 1.4),
            (f"door_{prefix}_stern", stern_x0, mid_y, corridor_id, stern_id, 1.4),
            (
                f"door_{prefix}_port_fwd",
                (fwd_x0 + fwd_x1) / 2,
                corridor_top,
                port_fwd_id,
                corridor_id,
                1.2,
            ),
            (
                f"door_{prefix}_stbd_fwd",
                (fwd_x0 + fwd_x1) / 2,
                corridor_bot,
                stbd_fwd_id,
                corridor_id,
                1.2,
            ),
            (
                f"door_{prefix}_port_mid",
                (mid_x0 + mid_x1) / 2,
                corridor_top,
                port_mid_id,
                corridor_id,
                1.2,
            ),
            (
                f"door_{prefix}_stbd_mid",
                (mid_x0 + mid_x1) / 2,
                corridor_bot,
                stbd_mid_id,
                corridor_id,
                1.2,
            ),
            (
                f"door_{prefix}_port_aft",
                (aft_x0 + aft_x1) / 2,
                corridor_top,
                port_aft_id,
                corridor_id,
                1.2,
            ),
            (
                f"door_{prefix}_stbd_aft",
                (aft_x0 + aft_x1) / 2,
                corridor_bot,
                stbd_aft_id,
                corridor_id,
                1.2,
            ),
        ]
        for door_id, dx, dy, a, b, w in door_specs:
            doors.append(
                Door(
                    id=door_id,
                    name=door_id.replace("_", " "),
                    x=dx,
                    y=dy,
                    width=w,
                    connects=(a, b),
                    floor_id=floor_id,
                )
            )

    # Occupants on lower decks.
    occupant_specs = [
        (0, "d0_bow", "F Deck bow crew", 6, 1.15),
        (0, "d0_port_aft", "F Deck third-class port", 8, 1.1),
        (0, "d0_stbd_aft", "F Deck third-class stbd", 8, 1.1),
        (1, "d1_port_fwd", "E Deck third-class port", 10, 1.15),
        (1, "d1_stbd_fwd", "E Deck third-class stbd", 10, 1.15),
        (1, "d1_port_aft", "E Deck aft port", 8, 1.15),
        (1, "d1_stbd_aft", "E Deck aft stbd", 8, 1.15),
        (2, "d2_port_mid", "D Deck diners port", 12, 1.2),
        (2, "d2_stbd_mid", "D Deck diners stbd", 12, 1.2),
        (2, "d2_stern", "D Deck second-class diners", 8, 1.2),
        (3, "d3_port_fwd", "B Deck first-class port", 6, 1.25),
        (3, "d3_stbd_fwd", "B Deck first-class stbd", 6, 1.25),
        (3, "d3_port_mid", "B Deck cabins port", 4, 1.2),
        (3, "d3_stbd_mid", "B Deck cabins stbd", 4, 1.2),
        (3, "d3_stern", "B Deck second-class", 6, 1.2),
        (4, "boat_mid", "Boat Deck promenaders", 6, 1.25),
    ]
    for floor_index, space_id, name, count, speed in occupant_specs:
        occupant_groups.append(
            OccupantGroup(
                id=f"occ_{space_id}",
                name=name,
                count=count,
                space_id=space_id,
                floor_id=f"floor-{floor_index}",
                walking_speed_mps=speed,
            )
        )

    # --- Boat Deck (floor 4): open promenade bow → mid → stern ---
    boat_floor = "floor-4"
    boat_bow_id = "boat_bow"
    boat_mid_id = "boat_mid"
    boat_stern_id = "boat_stern"
    spaces.extend(
        [
            Space(
                id=boat_bow_id,
                name="Boat Deck forward promenade",
                type=SpaceType.ROOM,
                floor_id=boat_floor,
                vertices=[
                    (bow_x0, mid_y),
                    (bow_x0 + 6.0, ship_top + 1.5),
                    (fwd_x1, ship_top),
                    (fwd_x1, ship_bot),
                    (bow_x0 + 6.0, ship_bot - 1.5),
                ],
            ),
            Space(
                id=boat_mid_id,
                name="Boat Deck midships promenade",
                type=SpaceType.ROOM,
                floor_id=boat_floor,
                vertices=rect_vertices(
                    mid_x0, ship_top, aft_x0 - mid_x0, ship_bot - ship_top
                ),
            ),
            Space(
                id=boat_stern_id,
                name="Boat Deck aft promenade",
                type=SpaceType.ROOM,
                floor_id=boat_floor,
                vertices=[
                    (aft_x0, ship_top),
                    (stern_x1, ship_top + 1.5),
                    (stern_x1, ship_bot - 1.5),
                    (aft_x0, ship_bot),
                ],
            ),
        ]
    )
    doors.extend(
        [
            Door(
                id="door_boat_bow_mid",
                name="Boat Deck forward–mid",
                x=fwd_x1,
                y=mid_y,
                width=2.0,
                connects=(boat_bow_id, boat_mid_id),
                floor_id=boat_floor,
            ),
            Door(
                id="door_boat_mid_stern",
                name="Boat Deck mid–aft",
                x=aft_x0,
                y=mid_y,
                width=2.0,
                connects=(boat_mid_id, boat_stern_id),
                floor_id=boat_floor,
            ),
        ]
    )

    # --- Poop Deck (floor 5): midships landing + stern exits ---
    poop_floor = "floor-5"
    poop_mid_id = "poop_mid"
    poop_walk_id = "poop_walk"
    poop_id = "poop_deck"
    spaces.extend(
        [
            Space(
                id=poop_mid_id,
                name="Poop Deck midships landing",
                type=SpaceType.ROOM,
                floor_id=poop_floor,
                vertices=rect_vertices(
                    mid_x0 + 4.0,
                    ship_top + 1.0,
                    16.0,
                    ship_bot - ship_top - 2.0,
                ),
            ),
            Space(
                id=poop_walk_id,
                name="Poop Deck aft walkway",
                type=SpaceType.CORRIDOR,
                floor_id=poop_floor,
                vertices=rect_vertices(
                    mid_x0 + 20.0,
                    corridor_top,
                    86.0 - (mid_x0 + 20.0),
                    corridor_bot - corridor_top,
                ),
            ),
            Space(
                id=poop_id,
                name="Poop Deck",
                type=SpaceType.ROOM,
                floor_id=poop_floor,
                vertices=poop_vertices(),
            ),
        ]
    )
    doors.extend(
        [
            Door(
                id="door_poop_mid_walk",
                name="Poop midships–walkway",
                x=mid_x0 + 20.0,
                y=mid_y,
                width=1.6,
                connects=(poop_mid_id, poop_walk_id),
                floor_id=poop_floor,
            ),
            Door(
                id="door_poop_walk_stern",
                name="Poop walkway–stern",
                x=86.0,
                y=mid_y,
                width=1.6,
                connects=(poop_walk_id, poop_id),
                floor_id=poop_floor,
            ),
        ]
    )

    # --- Stair banks (overlay inside host corridors / promenades) ---
    # Forward: F–Boat. Grand + aft: F–Poop (both reach poop exits).
    # Aft stairs sit in the full-beam stern so cabins can reach them without
    # squeezing through the narrow corridor against the stair polygons.
    stair_banks = [
        # key, label, x, boat_host, poop_host, max_floor, lower_host_kind
        ("fwd", "Forward", 22.0, boat_bow_id, None, 4, "corridor"),
        ("grand", "Grand staircase", 52.0, boat_mid_id, poop_mid_id, 5, "corridor"),
        ("aft", "Aft", 97.0, boat_stern_id, poop_id, 5, "stern"),
    ]

    for bank_key, bank_label, stair_x, boat_host, poop_host, max_floor, lower_host in stair_banks:
        for floor_index in range(max_floor + 1):
            floor_id = f"floor-{floor_index}"
            down_id = f"{bank_key}_stair_down_{floor_index}"
            up_id = f"{bank_key}_stair_up_{floor_index}"

            if floor_index <= 3 and lower_host == "corridor":
                stair_y = corridor_top + 0.25
                stair_h = corridor_bot - corridor_top - 0.5
            else:
                # Full-beam landings on boat/poop, or stern host on lower decks.
                stair_y = mid_y - 2.0
                stair_h = 4.0

            spaces.append(
                Space(
                    id=down_id,
                    name=f"{bank_label} down ({deck_specs[floor_index][1]})",
                    type=SpaceType.STAIRS,
                    floor_id=floor_id,
                    linked_stair_id=(
                        f"{bank_key}_stair_up_{floor_index - 1}"
                        if floor_index > 0
                        else None
                    ),
                    vertices=rect_vertices(stair_x, stair_y, 3.2, stair_h),
                )
            )
            spaces.append(
                Space(
                    id=up_id,
                    name=f"{bank_label} up ({deck_specs[floor_index][1]})",
                    type=SpaceType.STAIRS,
                    floor_id=floor_id,
                    linked_stair_id=(
                        f"{bank_key}_stair_down_{floor_index + 1}"
                        if floor_index < max_floor
                        else None
                    ),
                    vertices=rect_vertices(stair_x + 3.5, stair_y, 3.2, stair_h),
                )
            )
            doors.append(
                Door(
                    id=f"door_{bank_key}_landing_{floor_index}",
                    name=f"{bank_label} landing {floor_index}",
                    x=stair_x + 3.35,
                    y=stair_y + stair_h / 2,
                    width=1.2,
                    connects=(down_id, up_id),
                    floor_id=floor_id,
                )
            )

            if floor_index <= 3:
                host_id = f"d{floor_index}_{lower_host}"
            elif floor_index == 4:
                host_id = boat_host
            else:
                host_id = poop_host
            doors.append(
                Door(
                    id=f"door_{bank_key}_host_{floor_index}",
                    name=f"{bank_label} entry {floor_index}",
                    x=stair_x,
                    y=stair_y + stair_h / 2,
                    width=1.4,
                    connects=(host_id, down_id),
                    floor_id=floor_id,
                )
            )

    exits = [
        Exit(
            id="exit_poop_port",
            name="Poop Deck port lifeboat station",
            x=stern_x1,
            y=mid_y - 3.5,
            width=1.8,
            connected_space_id=poop_id,
            floor_id=poop_floor,
            flow_rate_per_s=1.2,
        ),
        Exit(
            id="exit_poop_centre",
            name="Poop Deck centre embarkation",
            x=stern_x1,
            y=mid_y,
            width=2.0,
            connected_space_id=poop_id,
            floor_id=poop_floor,
            flow_rate_per_s=1.4,
        ),
        Exit(
            id="exit_poop_stbd",
            name="Poop Deck starboard lifeboat station",
            x=stern_x1,
            y=mid_y + 3.5,
            width=1.8,
            connected_space_id=poop_id,
            floor_id=poop_floor,
            flow_rate_per_s=1.2,
        ),
    ]

    return BuildingLayout(
        name="RMS Titanic",
        width=width,
        height=height,
        meters_per_cell=1.0,
        floors=floors,
        spaces=spaces,
        doors=doors,
        exits=exits,
        occupant_groups=occupant_groups,
        floods=[
            FloodEmergency(
                id="flood-bow",
                enabled=True,
                x=8.0,
                y=mid_y,
                radius_m=2.0,
                spread_speed_mps=0.15,
                intensity=60.0,
                floor_id="floor-0",
            )
        ],
    )


def create_oval_stadium_template() -> BuildingLayout:
    """Create a four-floor oval stadium with lower-level perimeter exits."""
    floor_specs = [
        ("floor-0", "Basement", -4.0, 0),
        ("floor-1", "Ground", 0.0, 1),
        ("floor-2", "Upper Concourse", 5.0, 2),
        ("floor-3", "Upper Deck", 10.0, 3),
    ]
    floors = [
        Floor(id=floor_id, name=name, elevation_m=elevation, order=order)
        for floor_id, name, elevation, order in floor_specs
    ]

    width, height = 96.0, 64.0
    center_x, center_y = width / 2, height / 2
    radius_x, radius_y = 42.0, 28.0
    sector_count = 8
    vertices_per_oval = sector_count * 2
    inner_scale = 0.55
    boundary_angle = -math.pi / sector_count

    def ellipse_points(scale: float) -> list[tuple[float, float]]:
        return [
            (
                center_x + radius_x * scale * math.cos(
                    boundary_angle + index * 2 * math.pi / vertices_per_oval
                ),
                center_y - radius_y * scale * math.sin(
                    boundary_angle + index * 2 * math.pi / vertices_per_oval
                ),
            )
            for index in range(vertices_per_oval)
        ]

    outer_points = ellipse_points(1.0)
    inner_points = ellipse_points(inner_scale)
    section_names = (
        "East", "North-East", "North", "North-West",
        "West", "South-West", "South", "South-East",
    )
    spaces: list[Space] = []
    doors: list[Door] = []
    exits: list[Exit] = []
    occupant_groups: list[OccupantGroup] = []
    section_ids: dict[tuple[int, int], str] = {}

    for floor_index, (floor_id, floor_name, _, _) in enumerate(floor_specs):
        for section_index, section_name in enumerate(section_names):
            first_vertex = section_index * 2
            next_vertex = (first_vertex + 2) % vertices_per_oval
            section_id = f"stadium_{floor_index}_{section_name.lower().replace('-', '_')}"
            section_ids[(floor_index, section_index)] = section_id
            spaces.append(
                Space(
                    id=section_id,
                    name=f"{floor_name} {section_name} stands and concourse",
                    type=SpaceType.ROOM,
                    floor_id=floor_id,
                    vertices=[
                        outer_points[first_vertex],
                        outer_points[next_vertex],
                        inner_points[next_vertex],
                        inner_points[first_vertex],
                    ],
                )
            )
            occupant_groups.append(
                OccupantGroup(
                    id=f"stadium_crowd_{floor_index}_{section_index}",
                    name=f"{floor_name} {section_name} crowd",
                    count=floor_index + 2,
                    space_id=section_id,
                    floor_id=floor_id,
                    walking_speed_mps=1.25,
                )
            )

        for section_index in range(sector_count):
            first_vertex = section_index * 2
            previous_section = (section_index - 1) % sector_count
            outer = outer_points[first_vertex]
            inner = inner_points[first_vertex]
            doors.append(
                Door(
                    id=f"stadium_ring_door_{floor_index}_{section_index}",
                    name=f"{floor_name} concourse connection {section_index + 1}",
                    x=(outer[0] + inner[0]) / 2,
                    y=(outer[1] + inner[1]) / 2,
                    width=0.9,
                    connects=(
                        section_ids[(floor_index, previous_section)],
                        section_ids[(floor_index, section_index)],
                    ),
                    floor_id=floor_id,
                )
            )

        if floor_index == 1:
            field_id = "stadium_arena_floor"
            spaces.append(
                Space(
                    id=field_id,
                    name="Oval playing field",
                    type=SpaceType.ROOM,
                    floor_id=floor_id,
                    vertices=inner_points,
                )
            )
            occupant_groups.append(
                OccupantGroup(
                    id="stadium_arena_crowd",
                    name="Playing field crowd",
                    count=20,
                    space_id=field_id,
                    floor_id=floor_id,
                    walking_speed_mps=1.3,
                )
            )
            for section_index in range(sector_count):
                first_vertex = section_index * 2
                next_vertex = (first_vertex + 2) % vertices_per_oval
                start = inner_points[first_vertex]
                end = inner_points[next_vertex]
                doors.append(
                    Door(
                        id=f"stadium_field_door_{section_index}",
                        name=f"Playing field gate {section_index + 1}",
                        x=(start[0] + end[0]) / 2,
                        y=(start[1] + end[1]) / 2,
                        width=0.9,
                        connects=(section_ids[(floor_index, section_index)], field_id),
                        floor_id=floor_id,
                    )
                )

        if floor_index < 2:
            for section_index, gate_name in ((0, "East"), (4, "West")):
                first_vertex = section_index * 2
                next_vertex = (first_vertex + 2) % vertices_per_oval
                start = outer_points[first_vertex]
                end = outer_points[next_vertex]
                exits.append(
                    Exit(
                        id=f"stadium_exit_{floor_index}_{gate_name.lower()}",
                        name=f"{floor_name} {gate_name} exit",
                        x=(start[0] + end[0]) / 2,
                        y=(start[1] + end[1]) / 2,
                        width=2.4,
                        connected_space_id=section_ids[(floor_index, section_index)],
                        floor_id=floor_id,
                        flow_rate_per_s=1.8,
                    )
                )

    stair_banks = ((0, "east"), (2, "north"), (4, "west"), (6, "south"))
    for floor_index, (floor_id, _, _, _) in enumerate(floor_specs):
        for section_index, bank_name in stair_banks:
            angle = section_index * 2 * math.pi / sector_count
            stair_center_x = center_x + radius_x * 0.76 * math.cos(angle)
            stair_center_y = center_y - radius_y * 0.76 * math.sin(angle)
            down_id = f"stadium_stair_{bank_name}_down_{floor_index}"
            up_id = f"stadium_stair_{bank_name}_up_{floor_index}"
            stair_y = stair_center_y - 1.7
            down_x = stair_center_x - 2.2
            up_x = stair_center_x
            spaces.extend(
                [
                    Space(
                        id=down_id,
                        name=f"{bank_name.title()} stair down ({floor_specs[floor_index][1]})",
                        type=SpaceType.STAIRS,
                        floor_id=floor_id,
                        linked_stair_id=(
                            f"stadium_stair_{bank_name}_up_{floor_index - 1}"
                            if floor_index > 0
                            else None
                        ),
                        vertices=rect_vertices(down_x, stair_y, 2.2, 3.4),
                    ),
                    Space(
                        id=up_id,
                        name=f"{bank_name.title()} stair up ({floor_specs[floor_index][1]})",
                        type=SpaceType.STAIRS,
                        floor_id=floor_id,
                        linked_stair_id=(
                            f"stadium_stair_{bank_name}_down_{floor_index + 1}"
                            if floor_index < len(floor_specs) - 1
                            else None
                        ),
                        vertices=rect_vertices(up_x, stair_y, 2.2, 3.4),
                    ),
                ]
            )
            doors.extend(
                [
                    Door(
                        id=f"stadium_stair_landing_{bank_name}_{floor_index}",
                        name=f"{bank_name.title()} stair landing",
                        x=up_x,
                        y=stair_center_y,
                        width=0.9,
                        connects=(down_id, up_id),
                        floor_id=floor_id,
                    ),
                    Door(
                        id=f"stadium_stair_entry_{bank_name}_{floor_index}",
                        name=f"{bank_name.title()} stair entry",
                        x=down_x,
                        y=stair_center_y,
                        width=0.9,
                        connects=(section_ids[(floor_index, section_index)], down_id),
                        floor_id=floor_id,
                    ),
                ]
            )

    return BuildingLayout(
        name="Oval Stadium",
        width=width,
        height=height,
        meters_per_cell=1.0,
        floors=floors,
        spaces=spaces,
        doors=doors,
        exits=exits,
        occupant_groups=occupant_groups,
    )
