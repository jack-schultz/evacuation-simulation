"""Space-edge wall solids with openings punched through."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.building import Door, Exit, Space, SpaceType
from app.simulation.apertures import dist

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
    floor_id: str = "floor-0"

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
    floor_id: str = "floor-0",
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
                floor_id,
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
                floor_id,
            )
        )
    return pieces


def _punch_openings_on_edges(
    edges: list[tuple[tuple[float, float], tuple[float, float]]],
    openings: list[tuple[float, float, float]],
    thickness_m: float,
    floor_id: str = "floor-0",
) -> list[WallSegment]:
    solids: list[WallSegment] = []
    for (a, b) in edges:
        pieces = [WallSegment(a[0], a[1], b[0], b[1], thickness_m, floor_id)]
        for ox, oy, ow in openings:
            next_pieces: list[WallSegment] = []
            for seg in pieces:
                split = _split_segment_for_opening(
                    seg.ax, seg.ay, seg.bx, seg.by, ox, oy, ow, thickness_m, floor_id
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


def _is_overlay_stair(space: Space, spaces: list[Space]) -> bool:
    """True when a stairs polygon's center lies inside another space (portal overlay)."""
    if space.type != SpaceType.STAIRS:
        return False
    from app.domain.geometry import interior_point, point_in_polygon

    cx, cy = interior_point(space.vertices)
    for other in spaces:
        if other.id == space.id or other.type == SpaceType.STAIRS:
            continue
        if getattr(other, "floor_id", None) != getattr(space, "floor_id", None):
            continue
        if point_in_polygon(cx, cy, other.vertices):
            return True
    return False


def space_boundary_segments(
    spaces: list[Space],
    doors: list[Door],
    exits: list[Exit],
    thickness_m: float = _SPACE_EDGE_THICKNESS_M,
) -> list[WallSegment]:
    """Space perimeter edge segments as solids, with door/exit widths punched through.

    Overlay stairs (center inside a host room/corridor) do not emit walls — they are
    portals, and their edges would otherwise trap anyone who teleports to the center.
    Solids are tagged with floor_id so stacked storeys do not collide across floors.
    """
    from app.domain.geometry import edges as polygon_edges

    solids: list[WallSegment] = []
    floor_ids = {s.floor_id for s in spaces}
    for floor_id in floor_ids:
        floor_spaces = [s for s in spaces if s.floor_id == floor_id]
        edge_list: list[tuple[tuple[float, float], tuple[float, float]]] = []
        for s in floor_spaces:
            if _is_overlay_stair(s, floor_spaces):
                continue
            edge_list.extend(polygon_edges(s.vertices))
        openings = [
            (d.x, d.y, d.width) for d in doors if d.floor_id == floor_id
        ] + [
            (e.x, e.y, e.width) for e in exits if e.floor_id == floor_id
        ]
        punched = _punch_openings_on_edges(edge_list, openings, thickness_m, floor_id)
        solids.extend(punched)
    return solids


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
