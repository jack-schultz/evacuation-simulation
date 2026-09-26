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


def _forward_space_for_door(
    occupant: ContainedOccupant,
    door: Door,
    graph: object,
) -> str | None:
    """Space the occupant is trying to enter through this door along their route."""
    nodes = graph.nodes  # type: ignore[attr-defined]
    space_node_ids = graph.space_node_ids  # type: ignore[attr-defined]
    a, b = door.connects
    cur = nodes.get(occupant.current_node_id)
    if cur is not None and cur.kind == NodeKind.DOOR:
        nxt_id = occupant.next_node_id
        if nxt_id is None:
            return door_other_space(door, occupant.current_space_id)
        waypoint = nodes.get(nxt_id)
        a_nid = space_node_ids.get(a)
        b_nid = space_node_ids.get(b)
        if waypoint is None or a_nid is None or b_nid is None:
            return door_other_space(door, occupant.current_space_id)
        an, bn = nodes[a_nid], nodes[b_nid]
        da = dist(waypoint.x, waypoint.y, an.x, an.y)
        db = dist(waypoint.x, waypoint.y, bn.x, bn.y)
        return a if da <= db else b

    # Approaching the door: forward is the far side from current membership.
    return door_other_space(door, occupant.current_space_id)


def _closer_to_space(
    x: float,
    y: float,
    space_id: str,
    other_id: str,
    spaces: dict[str, Space],
) -> bool:
    """True if (x, y) is closer to space_id's interior than to other_id's."""
    from app.domain.geometry import interior_point

    if space_id not in spaces or other_id not in spaces:
        return False
    sx, sy = interior_point(spaces[space_id].vertices)
    ox, oy = interior_point(spaces[other_id].vertices)
    return dist(x, y, sx, sy) < dist(x, y, ox, oy) - 1e-9


def update_space_membership_from_position(
    occupants: list[ContainedOccupant],
    spaces: dict[str, Space],
    doors: dict[str, Door],
    graph: object,
    admitted: set[str] | None = None,
) -> None:
    """Flip current_space_id forward through an admitted door (never backward).

    Shared door edges count as inside both polygons, so a naive "enter other
    space" test oscillates membership. We only move membership toward the
    route's forward space, and only once the body is clearly on that side.
    """
    from app.domain.geometry import point_in_polygon

    for o in occupants:
        if o.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED, OccupantStatus.CLIMBING):
            continue
        if not o.current_space_id:
            continue
        door = _crossing_door(o, graph, doors, admitted)
        if door is None:
            continue
        forward_id = _forward_space_for_door(o, door, graph)
        if forward_id is None or forward_id not in spaces:
            continue
        if o.current_space_id == forward_id:
            continue
        origin_id = o.current_space_id
        if forward_id not in door.connects or origin_id not in door.connects:
            continue
        in_forward = point_in_polygon(o.x, o.y, spaces[forward_id].vertices)
        if not in_forward:
            continue
        in_origin = point_in_polygon(o.x, o.y, spaces[origin_id].vertices)
        # Interior of the destination only → always flip. Shared-edge points
        # belong to both polygons; require being closer to the forward interior
        # so membership does not oscillate backward.
        if (not in_origin) or _closer_to_space(
            o.x, o.y, forward_id, origin_id, spaces
        ):
            o.current_space_id = forward_id


def resolve_space_containment(
    occupants: list[ContainedOccupant],
    spaces: dict[str, Space],
    radius_m: float,
    doors: dict[str, Door] | None = None,
    graph: object | None = None,
    admitted: set[str] | None = None,
) -> None:
    """Clamp active occupants into their current space (plus door transit destination).

    While still on the origin side of an admitted door, the destination is also
    allowed and the body-radius inset is dropped so small timesteps can finish
    the crossing. After membership flips forward, normal single-space inset
    resumes. Wall solids still block everything except the punched opening.
    """
    if radius_m < 0:
        return
    doors = doors or {}

    for o in occupants:
        if o.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED, OccupantStatus.CLIMBING):
            continue
        if o.current_space_id not in spaces:
            continue
        allowed = [o.current_space_id]
        inset = radius_m
        if graph is not None and doors:
            door = _crossing_door(o, graph, doors, admitted)
            if door is not None:
                forward_id = _forward_space_for_door(o, door, graph)
                if (
                    forward_id is not None
                    and forward_id in spaces
                    and o.current_space_id != forward_id
                ):
                    allowed.append(forward_id)
                    # Inset against the shared door edge stranded the last person
                    # in the doorway: they could never step across unless a single
                    # timestep jumped more than radius_m.
                    inset = 0.0
        o.x, o.y = _clamp_to_nearest_space(o.x, o.y, allowed, spaces, inset)


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
        if o.status not in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED, OccupantStatus.CLIMBING)
    ]
    for o in active:
        floor = getattr(o, "floor_id", None)
        for solid in solids:
            if isinstance(solid, WallSegment):
                if floor is not None and getattr(solid, "floor_id", floor) != floor:
                    continue
                o.x, o.y = solid.push_out(o.x, o.y, r)
            else:
                inflated = Aabb(
                    solid.x - r,
                    solid.y - r,
                    solid.width + 2.0 * r,
                    solid.height + 2.0 * r,
                )
                o.x, o.y = push_out_of_aabb(o.x, o.y, inflated)
