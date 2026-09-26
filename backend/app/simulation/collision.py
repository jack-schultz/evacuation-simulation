"""Spatial collision helpers: body radius, door apertures, space edges, overlap resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.building import Door, Exit, OccupantStatus, Space
from app.simulation.graph import NodeKind


class PositionedOccupant(Protocol):
    id: str
    x: float
    y: float
    status: OccupantStatus


@dataclass(frozen=True)
class Aabb:
    """Axis-aligned rectangle: top-left origin, positive width/height."""

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def contains_point(self, px: float, py: float) -> bool:
        return self.x <= px <= self.right and self.y <= py <= self.bottom

    def intersects(self, other: Aabb) -> bool:
        return not (
            self.right < other.x
            or other.right < self.x
            or self.bottom < other.y
            or other.bottom < self.y
        )


def aperture_slots(width_m: float, radius_m: float) -> int:
    """How many bodies fit abreast through an opening of the given clear width."""
    if radius_m <= 0:
        return 1
    return max(1, int(width_m / (2.0 * radius_m)))


def throat_radius(radius_m: float) -> float:
    """Distance from a door/exit node that counts as being in the opening throat."""
    return max(radius_m * 2.5, 0.6)


def dist(ax: float, ay: float, bx: float, by: float) -> float:
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def in_throat(x: float, y: float, node_x: float, node_y: float, radius_m: float) -> bool:
    return dist(x, y, node_x, node_y) <= throat_radius(radius_m)


def aperture_axis(from_x: float, from_y: float, to_x: float, to_y: float) -> tuple[float, float]:
    """Unit vector perpendicular to the approach direction (door opening axis)."""
    dx = to_x - from_x
    dy = to_y - from_y
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-9:
        return 1.0, 0.0
    return -dy / length, dx / length


def aperture_slot_point(
    door_x: float,
    door_y: float,
    axis_x: float,
    axis_y: float,
    width_m: float,
    slot_index: int,
    slot_count: int,
) -> tuple[float, float]:
    """World position of slot_index along the aperture segment centered on the door."""
    if slot_count <= 1:
        return door_x, door_y
    t = (slot_index + 0.5) / slot_count - 0.5
    offset = t * width_m
    return door_x + axis_x * offset, door_y + axis_y * offset


def clamp_outside_throat(
    x: float,
    y: float,
    node_x: float,
    node_y: float,
    radius_m: float,
) -> tuple[float, float]:
    """Push a point onto the throat circle if it lies inside."""
    tr = throat_radius(radius_m)
    dx = x - node_x
    dy = y - node_y
    d = (dx * dx + dy * dy) ** 0.5
    if d >= tr:
        return x, y
    if d < 1e-9:
        return node_x + tr, node_y
    scale = tr / d
    return node_x + dx * scale, node_y + dy * scale


def resolve_overlaps(
    occupants: list[PositionedOccupant],
    radius_m: float,
    iterations: int = 4,
) -> None:
    """Separating-axis push for pairs closer than 2 * radius (in-place)."""
    min_dist = 2.0 * radius_m
    if min_dist <= 0:
        return

    active = [
        o
        for o in occupants
        if o.status not in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED)
    ]

    for _ in range(iterations):
        for i in range(len(active)):
            a = active[i]
            for j in range(i + 1, len(active)):
                b = active[j]
                dx = b.x - a.x
                dy = b.y - a.y
                d = (dx * dx + dy * dy) ** 0.5
                if d < 1e-9:
                    # Coincident: unit push along a stable axis from ids
                    nx, ny = (1.0, 0.0) if a.id <= b.id else (-1.0, 0.0)
                    push = min_dist / 2.0
                    a.x -= nx * push
                    a.y -= ny * push
                    b.x += nx * push
                    b.y += ny * push
                    continue
                if d >= min_dist:
                    continue
                push = (min_dist - d) / 2.0
                nx = dx / d
                ny = dy / d
                a.x -= nx * push
                a.y -= ny * push
                b.x += nx * push
                b.y += ny * push


def _point_to_segment_dist(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    abx, aby = bx - ax, by - ay
    ab_len2 = abx * abx + aby * aby
    if ab_len2 < 1e-18:
        return dist(px, py, ax, ay)
    t = ((px - ax) * abx + (py - ay) * aby) / ab_len2
    t = max(0.0, min(1.0, t))
    qx = ax + t * abx
    qy = ay + t * aby
    return dist(px, py, qx, qy)


def _closest_on_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> tuple[float, float, float]:
    """Return (qx, qy, t) where t is the clamped parameter along AB."""
    abx, aby = bx - ax, by - ay
    ab_len2 = abx * abx + aby * aby
    if ab_len2 < 1e-18:
        return ax, ay, 0.0
    t = ((px - ax) * abx + (py - ay) * aby) / ab_len2
    t = max(0.0, min(1.0, t))
    return ax + t * abx, ay + t * aby, t


@dataclass(frozen=True)
class WallSegment:
    """Thick line segment used as a wall solid (arbitrary orientation)."""

    ax: float
    ay: float
    bx: float
    by: float
    thickness: float = 0.1

    @property
    def length(self) -> float:
        return dist(self.ax, self.ay, self.bx, self.by)

    def contains_point(self, px: float, py: float) -> bool:
        half = self.thickness / 2.0
        return _point_to_segment_dist(px, py, self.ax, self.ay, self.bx, self.by) <= half + 1e-9

    def push_out(self, px: float, py: float, radius_m: float) -> tuple[float, float]:
        """Push a body center so it clears this segment by radius_m."""
        half = self.thickness / 2.0 + radius_m
        qx, qy, _ = _closest_on_segment(px, py, self.ax, self.ay, self.bx, self.by)
        dx, dy = px - qx, py - qy
        d = (dx * dx + dy * dy) ** 0.5
        if d >= half - 1e-12:
            return px, py
        if d < 1e-9:
            # Degenerate: push along segment normal
            abx = self.bx - self.ax
            aby = self.by - self.ay
            length = (abx * abx + aby * aby) ** 0.5
            if length < 1e-9:
                return px + half, py
            nx, ny = -aby / length, abx / length
            return qx + nx * half, qy + ny * half
        scale = half / d
        return qx + dx * scale, qy + dy * scale


def _split_segment_for_opening(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    ox: float,
    oy: float,
    width_m: float,
    thickness_m: float,
) -> list[WallSegment] | None:
    """If opening lands on this edge, return remaining solid pieces; else None."""
    length = dist(ax, ay, bx, by)
    if length < 1e-9:
        return None
    qx, qy, t = _closest_on_segment(ox, oy, ax, ay, bx, by)
    # Opening must be near the edge line
    if dist(ox, oy, qx, qy) > max(0.25, thickness_m + 0.1):
        return None
    half_t = (width_m / 2.0) / length
    t0 = max(0.0, t - half_t)
    t1 = min(1.0, t + half_t)
    if t1 <= 0.0 or t0 >= 1.0 or t1 <= t0:
        return None

    pieces: list[WallSegment] = []
    if t0 > 1e-6:
        pieces.append(
            WallSegment(
                ax,
                ay,
                ax + (bx - ax) * t0,
                ay + (by - ay) * t0,
                thickness_m,
            )
        )
    if t1 < 1.0 - 1e-6:
        pieces.append(
            WallSegment(
                ax + (bx - ax) * t1,
                ay + (by - ay) * t1,
                bx,
                by,
                thickness_m,
            )
        )
    return pieces


def _punch_openings_on_edges(
    edges: list[tuple[tuple[float, float], tuple[float, float]]],
    openings: list[tuple[float, float, float]],
    thickness_m: float,
) -> list[WallSegment]:
    solids: list[WallSegment] = []
    for (a, b) in edges:
        pieces = [WallSegment(a[0], a[1], b[0], b[1], thickness_m)]
        for ox, oy, ow in openings:
            next_pieces: list[WallSegment] = []
            for seg in pieces:
                split = _split_segment_for_opening(
                    seg.ax, seg.ay, seg.bx, seg.by, ox, oy, ow, thickness_m
                )
                if split is None:
                    next_pieces.append(seg)
                else:
                    next_pieces.extend(split)
            pieces = next_pieces
        solids.extend(p for p in pieces if p.length > 1e-6)
    return solids


# Thin shell along each space edge; only door/exit widths are passable.
_SPACE_EDGE_THICKNESS_M = 0.1


def space_boundary_segments(
    spaces: list[Space],
    doors: list[Door],
    exits: list[Exit],
    thickness_m: float = _SPACE_EDGE_THICKNESS_M,
) -> list[WallSegment]:
    """Space perimeter edge segments as solids, with door/exit widths punched through."""
    from app.domain.geometry import edges as polygon_edges

    edge_list: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for s in spaces:
        edge_list.extend(polygon_edges(s.vertices))
    openings = [(d.x, d.y, d.width) for d in doors] + [(e.x, e.y, e.width) for e in exits]
    return _punch_openings_on_edges(edge_list, openings, thickness_m)


def space_boundary_rects(
    spaces: list[Space],
    doors: list[Door],
    exits: list[Exit],
    thickness_m: float = _SPACE_EDGE_THICKNESS_M,
) -> list[WallSegment]:
    """Alias kept for older call sites / tests."""
    return space_boundary_segments(spaces, doors, exits, thickness_m)


def build_collision_solids(
    spaces: list[Space],
    doors: list[Door],
    exits: list[Exit],
) -> list[WallSegment]:
    """Space boundaries as collision solids; openings stay passable."""
    return space_boundary_segments(spaces, doors, exits)


def push_out_of_aabb(x: float, y: float, box: Aabb) -> tuple[float, float]:
    """If (x, y) is inside box, push to the nearest outside face."""
    if not box.contains_point(x, y):
        return x, y
    dl = x - box.x
    dr = box.right - x
    dt = y - box.y
    db = box.bottom - y
    m = min(dl, dr, dt, db)
    if m == dl:
        return box.x, y
    if m == dr:
        return box.right, y
    if m == dt:
        return x, box.y
    return x, box.bottom


def inset_aabb(space: Space, radius_m: float) -> Aabb:
    """Walkable AABB inset of the space bounding box (exact for axis-aligned rects)."""
    from app.domain.geometry import bbox

    r = max(radius_m, 0.0)
    min_x, min_y, width, height = bbox(space.vertices)
    if width <= 2.0 * r or height <= 2.0 * r:
        cx, cy = space.centroid
        return Aabb(cx, cy, 0.0, 0.0)
    return Aabb(
        min_x + r,
        min_y + r,
        width - 2.0 * r,
        height - 2.0 * r,
    )


def clamp_point_to_aabb(x: float, y: float, box: Aabb) -> tuple[float, float]:
    """Project (x, y) onto the closed AABB."""
    return (
        min(max(x, box.x), box.right),
        min(max(y, box.y), box.bottom),
    )


def _clamp_to_nearest_aabb(
    x: float, y: float, boxes: list[Aabb]
) -> tuple[float, float]:
    """Keep point if inside any box; otherwise snap to the closest box."""
    if any(b.contains_point(x, y) for b in boxes):
        return x, y
    best_x, best_y = x, y
    best_d = float("inf")
    for box in boxes:
        cx, cy = clamp_point_to_aabb(x, y, box)
        d = dist(x, y, cx, cy)
        if d < best_d:
            best_d = d
            best_x, best_y = cx, cy
    return best_x, best_y


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


def _door_other_space(door: Door, space_id: str) -> str | None:
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


def _transit_destination_space_id(
    occupant: ContainedOccupant,
    graph: object,
    doors: dict[str, Door],
    admitted: set[str] | None,
) -> str | None:
    """Destination space when mid-door-crossing or admitted toward a connecting door."""
    nodes = graph.nodes  # type: ignore[attr-defined]
    space_id = occupant.current_space_id
    if not space_id:
        return None

    cur = nodes.get(occupant.current_node_id)
    if cur is not None and cur.kind == NodeKind.DOOR:
        door = doors.get(cur.ref_id)
        if door is not None:
            return _door_other_space(door, space_id)

    nxt_id = occupant.next_node_id
    if nxt_id is None:
        return None
    nxt = nodes.get(nxt_id)
    if nxt is None or nxt.kind != NodeKind.DOOR:
        return None
    if admitted is not None and occupant.id not in admitted:
        return None
    door = doors.get(nxt.ref_id)
    if door is None:
        return None
    return _door_other_space(door, space_id)


def resolve_space_containment(
    occupants: list[ContainedOccupant],
    spaces: dict[str, Space],
    doors: dict[str, Door],
    graph: object,
    radius_m: float,
    admitted: set[str] | None = None,
) -> None:
    """Clamp active occupants into their current space (plus door-transit destination)."""
    if radius_m < 0:
        return

    for o in occupants:
        if o.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED):
            continue
        if o.current_space_id not in spaces:
            continue
        allowed = [o.current_space_id]
        dest_id = _transit_destination_space_id(o, graph, doors, admitted)
        if dest_id is not None and dest_id in spaces:
            allowed.append(dest_id)
        o.x, o.y = _clamp_to_nearest_space(o.x, o.y, allowed, spaces, radius_m)


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
