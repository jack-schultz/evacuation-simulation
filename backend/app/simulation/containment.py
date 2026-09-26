"""Space membership clamping and wall collision resolution."""

from __future__ import annotations

from typing import Protocol

from app.domain.building import Door, OccupantStatus, Space
from app.simulation.apertures import PositionedOccupant, dist
from app.simulation.collision_aabb import Aabb, push_out_of_aabb
from app.simulation.graph import NodeKind
from app.simulation.walls import WallSegment


def _clamp_to_nearest_space(
    x: float,
    y: float,
    space_ids: list[str],
    spaces: dict[str, Space],
    radius_m: float,
) -> tuple[float, float]:
    """Keep point if inside any allowed space (inset); else clamp into the nearest."""
    from app.domain.geometry import clamp_into_polygon, point_in_polygon, distance_to_boundary

    allowed = [spaces[sid] for sid in space_ids if sid in spaces]
    if not allowed:
        return x, y

    for space in allowed:
        if point_in_polygon(x, y, space.vertices) and distance_to_boundary(
            x, y, space.vertices
        ) >= radius_m - 1e-9:
            return x, y

    best_x, best_y = x, y
    best_d = float("inf")
    for space in allowed:
        cx, cy = clamp_into_polygon(x, y, space.vertices, inset_m=radius_m)
        d = dist(x, y, cx, cy)
        if d < best_d:
            best_d = d
            best_x, best_y = cx, cy
    return best_x, best_y


def door_other_space(door: Door, space_id: str) -> str | None:
    a, b = door.connects
    if a == space_id:
        return b
    if b == space_id:
        return a
    return None


class ContainedOccupant(Protocol):
    id: str
    x: float
    y: float
    status: OccupantStatus
    current_space_id: str
    route: list[str]
    route_index: int

    @property
    def current_node_id(self) -> str: ...

    @property
    def next_node_id(self) -> str | None: ...


def _crossing_door(
    occupant: ContainedOccupant,
    graph: object,
    doors: dict[str, Door],
    admitted: set[str] | None,
) -> Door | None:
    """Door the occupant is on or admitted toward, if any."""
    nodes = graph.nodes  # type: ignore[attr-defined]
    cur = nodes.get(occupant.current_node_id)
    if cur is not None and cur.kind == NodeKind.DOOR:
        return doors.get(cur.ref_id)

    nxt_id = occupant.next_node_id
    if nxt_id is None:
        return None
    nxt = nodes.get(nxt_id)
    if nxt is None or nxt.kind != NodeKind.DOOR:
        return None
    if admitted is not None and occupant.id not in admitted:
        return None
    return doors.get(nxt.ref_id)


def update_space_membership_from_position(
    occupants: list[ContainedOccupant],
    spaces: dict[str, Space],
    doors: dict[str, Door],
    graph: object,
    admitted: set[str] | None = None,
) -> None:
    """Flip current_space_id when the body enters the far side of an admitted door."""
    from app.domain.geometry import point_in_polygon

    for o in occupants:
        if o.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED):
            continue
        if not o.current_space_id:
            continue
        door = _crossing_door(o, graph, doors, admitted)
        if door is None:
            continue
        dest_id = door_other_space(door, o.current_space_id)
        if dest_id is None or dest_id not in spaces:
            continue
        if point_in_polygon(o.x, o.y, spaces[dest_id].vertices):
            o.current_space_id = dest_id


def resolve_space_containment(
    occupants: list[ContainedOccupant],
    spaces: dict[str, Space],
    radius_m: float,
) -> None:
    """Clamp active occupants into their current space only."""
    if radius_m < 0:
        return

    for o in occupants:
        if o.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED):
            continue
        if o.current_space_id not in spaces:
            continue
        o.x, o.y = _clamp_to_nearest_space(
            o.x, o.y, [o.current_space_id], spaces, radius_m
        )


def resolve_wall_collisions(
    occupants: list[PositionedOccupant],
    solids: list[WallSegment | Aabb],
    radius_m: float,
) -> None:
    """Push active occupants so their body circle does not overlap wall solids."""
    if not solids or radius_m < 0:
        return
    r = radius_m
    active = [
        o
        for o in occupants
        if o.status not in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED)
    ]
    for o in active:
        for solid in solids:
            if isinstance(solid, WallSegment):
                o.x, o.y = solid.push_out(o.x, o.y, r)
            else:
                inflated = Aabb(
                    solid.x - r,
                    solid.y - r,
                    solid.width + 2.0 * r,
                    solid.height + 2.0 * r,
                )
                o.x, o.y = push_out_of_aabb(o.x, o.y, inflated)
