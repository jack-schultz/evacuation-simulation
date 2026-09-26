"""Seed example building demonstrating a corridor bottleneck."""

from app.domain.building import (
    BuildingLayout,
    Door,
    Exit,
    OccupantGroup,
    Space,
    SpaceType,
)


def create_seed_layout() -> BuildingLayout:
    """Office A --door--> Corridor --door--> Office B with exits at both ends.

    The narrow corridor and doors create a measurable congestion bottleneck when
    ~80 occupants evacuate simultaneously.
    """
    return BuildingLayout(
        name="Example Two-Office Building",
        width=30.0,
        height=36.0,
        meters_per_cell=1.0,
        spaces=[
            Space(
                id="office_a",
                name="Office A",
                type=SpaceType.ROOM,
                x=5.0,
                y=4.0,
                width=20.0,
                height=10.0,
            ),
            Space(
                id="corridor",
                name="Corridor",
                type=SpaceType.CORRIDOR,
                x=12.0,
                y=14.5,
                width=6.0,
                height=7.0,
                capacity_density_per_m2=1.5,
            ),
            Space(
                id="office_b",
                name="Office B",
                type=SpaceType.ROOM,
                x=5.0,
                y=22.0,
                width=20.0,
                height=10.0,
            ),
        ],
        doors=[
            Door(
                id="door_a",
                name="Door A",
                x=15.0,
                y=14.0,
                width=0.9,
                connects=("office_a", "corridor"),
                flow_rate_per_s=0.8,
            ),
            Door(
                id="door_b",
                name="Door B",
                x=15.0,
                y=21.5,
                width=0.9,
                connects=("corridor", "office_b"),
                flow_rate_per_s=0.8,
            ),
        ],
        exits=[
            Exit(
                id="exit_1",
                name="Exit 1 (North)",
                x=15.0,
                y=3.5,
                width=1.2,
                connected_space_id="office_a",
                flow_rate_per_s=1.0,
            ),
            Exit(
                id="exit_2",
                name="Exit 2 (South)",
                x=15.0,
                y=32.5,
                width=1.2,
                connected_space_id="office_b",
                flow_rate_per_s=1.0,
            ),
        ],
        occupant_groups=[
            OccupantGroup(
                id="group_office_a",
                name="Office A occupants",
                count=45,
                space_id="office_a",
                walking_speed_mps=1.2,
            ),
            OccupantGroup(
                id="group_office_b",
                name="Office B occupants",
                count=40,
                space_id="office_b",
                walking_speed_mps=1.1,
            ),
        ],
    )
