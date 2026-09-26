"""Build a navigation graph from a building layout."""

from __future__ import annotations

from app.domain.building import BuildingLayout, Door, Exit, Space, SpaceType
from app.domain.geometry import (
    interior_point,
    point_in_polygon,
    segment_in_polygon,
    signed_area,
)
from app.simulation.graph_types import (
    EdgeKind,
    GraphEdge,
    GraphNode,
    NavigationGraph,
    NodeKind,
    edge_exists,
)

def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _edge_kind_for_space(space_type: SpaceType) -> EdgeKind:
    if space_type == SpaceType.CORRIDOR:
        return EdgeKind.CORRIDOR
    if space_type == SpaceType.STAIRS:
        return EdgeKind.STAIRS
    return EdgeKind.SPACE


def _opening_edge_props(
    node: GraphNode,
    doors: dict[str, Door],
    exits: dict[str, Exit],
    defaults: dict[str, float],
) -> tuple[EdgeKind, float, float | None, str]:
    """kind, width, flow, element_id for approaching this opening."""
    if node.kind == NodeKind.DOOR:
        door = doors[node.ref_id]
        flow = (
            door.flow_rate_per_s
            if door.flow_rate_per_s is not None
            else defaults["door_flow_per_s"]
        )
        return EdgeKind.DOOR, door.width, flow, door.id
    exit_ = exits[node.ref_id]
    flow = (
        exit_.flow_rate_per_s
        if exit_.flow_rate_per_s is not None
        else defaults["exit_flow_per_s"]
    )
    return EdgeKind.EXIT, exit_.width, flow, exit_.id


def _portal_point(
    x: float, y: float, vertices: list[tuple[float, float]], interior: tuple[float, float]
) -> tuple[float, float]:
    """Point used for visibility tests; nudge outside openings into the polygon."""
    if point_in_polygon(x, y, vertices):
        return x, y
    ix, iy = interior
    for t in (0.02, 0.05, 0.1, 0.2, 0.35, 0.5):
        px = x + (ix - x) * t
        py = y + (iy - y) * t
        if point_in_polygon(px, py, vertices):
            return px, py
    return interior


def _inward_bisector_nudge(
    prev: tuple[float, float],
    vertex: tuple[float, float],
    nxt: tuple[float, float],
    vertices: list[tuple[float, float]],
    distance: float = 0.4,
) -> tuple[float, float]:
    """Move a reflex corner into the polygon along the angle bisector.

    Tries the full clearance first, then shorter distances so narrow geometry
    still gets an interior waypoint instead of the raw corner.
    """
    bx, by = vertex
    v1x, v1y = prev[0] - bx, prev[1] - by
    v2x, v2y = nxt[0] - bx, nxt[1] - by
    l1 = (v1x * v1x + v1y * v1y) ** 0.5
    l2 = (v2x * v2x + v2y * v2y) ** 0.5
    if l1 < 1e-9 or l2 < 1e-9:
        return vertex
    v1x, v1y = v1x / l1, v1y / l1
    v2x, v2y = v2x / l2, v2y / l2
    sx, sy = v1x + v2x, v1y + v2y
    sl = (sx * sx + sy * sy) ** 0.5
    if sl < 1e-9:
        return vertex
    sx, sy = sx / sl, sy / sl
    for scale in (1.0, 0.75, 0.5, 0.25):
        d = distance * scale
        for sign in (1.0, -1.0):
            px = bx + sign * sx * d
            py = by + sign * sy * d
            if point_in_polygon(px, py, vertices):
                return px, py
    return vertex


class NavigationGraphBuilder:
    """Builds a navigable graph from polygonal spaces, doors, and exits.

    Space nodes define connectivity and spawn. Within each space, people path
    along a visibility graph (openings + reflex-corner waypoints).
    """

    def build(self, layout: BuildingLayout, defaults: dict[str, float]) -> NavigationGraph:
        graph = NavigationGraph()
        spaces = {s.id: s for s in layout.spaces}
        doors = {d.id: d for d in layout.doors}
        exits = {e.id: e for e in layout.exits}

        for space in layout.spaces:
            cx, cy = interior_point(space.vertices)
            node = GraphNode(
                id=f"space:{space.id}", kind=NodeKind.SPACE, x=cx, y=cy, ref_id=space.id
            )
            graph.add_node(node)
            graph.space_node_ids[space.id] = node.id

        openings_by_space: dict[str, list[str]] = {s.id: [] for s in layout.spaces}

        for door in layout.doors:
            node = GraphNode(
                id=f"door:{door.id}",
                kind=NodeKind.DOOR,
                x=door.x,
                y=door.y,
                ref_id=door.id,
            )
            graph.add_node(node)
            flow = (
                door.flow_rate_per_s
                if door.flow_rate_per_s is not None
                else defaults["door_flow_per_s"]
            )
            for space_id in door.connects:
                space = spaces[space_id]
                space_node_id = graph.space_node_ids[space_id]
                sn = graph.nodes[space_node_id]
                portal = _portal_point(door.x, door.y, space.vertices, (sn.x, sn.y))
                if segment_in_polygon((sn.x, sn.y), portal, space.vertices):
                    distance = max(_dist(sn.x, sn.y, door.x, door.y), 0.5)
                    edge = GraphEdge(
                        id=f"edge:door:{door.id}:{space_id}",
                        from_id=space_node_id,
                        to_id=node.id,
                        distance_m=distance,
                        kind=EdgeKind.DOOR,
                        width_m=door.width,
                        flow_rate_per_s=flow,
                        capacity_density_per_m2=None,
                        area_m2=None,
                        element_id=door.id,
                    )
                    graph.add_edge(edge)

                # Space traversal component (room/corridor capacity)
                area = space.area_m2
                density = space.capacity_density_per_m2
                if density is None and space.type in (SpaceType.CORRIDOR, SpaceType.STAIRS):
                    density = defaults["corridor_density_per_m2"]
                _, _, bw, bh = space.bbox
                space_edge = GraphEdge(
                    id=f"edge:space:{space_id}:door:{door.id}",
                    from_id=space_node_id,
                    to_id=space_node_id,
                    distance_m=0.0,
                    kind=_edge_kind_for_space(space.type),
                    width_m=min(bw, bh) if bw > 0 and bh > 0 else 1.0,
                    flow_rate_per_s=(
                        defaults["stairs_flow_per_s"] if space.type == SpaceType.STAIRS else None
                    ),
                    capacity_density_per_m2=density,
                    area_m2=area,
                    element_id=space.id,
                )
                graph.edges[space_edge.id] = space_edge
                openings_by_space[space_id].append(node.id)

        for exit_ in layout.exits:
            node = GraphNode(
                id=f"exit:{exit_.id}",
                kind=NodeKind.EXIT,
                x=exit_.x,
                y=exit_.y,
                ref_id=exit_.id,
            )
            graph.add_node(node)
            graph.exit_node_ids.append(node.id)
            space = spaces[exit_.connected_space_id]
            space_node_id = graph.space_node_ids[exit_.connected_space_id]
            sn = graph.nodes[space_node_id]
            flow = (
                exit_.flow_rate_per_s
                if exit_.flow_rate_per_s is not None
                else defaults["exit_flow_per_s"]
            )
            portal = _portal_point(exit_.x, exit_.y, space.vertices, (sn.x, sn.y))
            if segment_in_polygon((sn.x, sn.y), portal, space.vertices):
                distance = max(_dist(sn.x, sn.y, exit_.x, exit_.y), 0.5)
                edge = GraphEdge(
                    id=f"edge:exit:{exit_.id}",
                    from_id=space_node_id,
                    to_id=node.id,
                    distance_m=distance,
                    kind=EdgeKind.EXIT,
                    width_m=exit_.width,
                    flow_rate_per_s=flow,
                    capacity_density_per_m2=None,
                    area_m2=None,
                    element_id=exit_.id,
                )
                graph.add_edge(edge)
            openings_by_space[exit_.connected_space_id].append(node.id)

        # Per-space visibility graph: openings + reflex waypoints + space node
        for space_id, opening_ids in openings_by_space.items():
            space = spaces[space_id]
            self._add_visibility_edges(
                graph, space, opening_ids, doors, exits, defaults
            )

        return graph

    def _add_visibility_edges(
        self,
        graph: NavigationGraph,
        space: Space,
        opening_ids: list[str],
        doors: dict[str, Door],
        exits: dict[str, Exit],
        defaults: dict[str, float],
    ) -> None:
        space_node_id = graph.space_node_ids[space.id]
        sn = graph.nodes[space_node_id]
        interior = (sn.x, sn.y)
        verts = space.vertices

        waypoint_ids: list[str] = []
        n = len(verts)
        if n >= 3:
            ccw = signed_area(verts) > 0
            wp_i = 0
            radius = float(defaults.get("occupant_radius_m", 0.25))
            nudge = max(radius * 1.5, 0.4)
            for i in range(n):
                ax, ay = verts[(i - 1) % n]
                bx, by = verts[i]
                cx, cy = verts[(i + 1) % n]
                cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
                is_reflex = cross < -1e-12 if ccw else cross > 1e-12
                if not is_reflex:
                    continue
                wx, wy = _inward_bisector_nudge(
                    (ax, ay), (bx, by), (cx, cy), verts, distance=nudge
                )
                wid = f"waypoint:{space.id}:{wp_i}"
                wp_i += 1
                graph.add_node(
                    GraphNode(id=wid, kind=NodeKind.WAYPOINT, x=wx, y=wy, ref_id=space.id)
                )
                waypoint_ids.append(wid)

        # Deduplicate opening ids (door listed once per space already)
        unique_openings = list(dict.fromkeys(opening_ids))
        candidates = [space_node_id] + unique_openings + waypoint_ids

        portal_cache: dict[str, tuple[float, float]] = {}
        for nid in candidates:
            node = graph.nodes[nid]
            if node.kind in (NodeKind.DOOR, NodeKind.EXIT):
                portal_cache[nid] = _portal_point(node.x, node.y, verts, interior)
            else:
                portal_cache[nid] = (node.x, node.y)

        space_kind = _edge_kind_for_space(space.type)
        _, _, bw, bh = space.bbox
        space_width = min(bw, bh) if bw > 0 and bh > 0 else 1.0

        for i, from_id in enumerate(candidates):
            for to_id in candidates[i + 1 :]:
                pa = portal_cache[from_id]
                pb = portal_cache[to_id]
                if not segment_in_polygon(pa, pb, verts):
                    continue
                a = graph.nodes[from_id]
                b = graph.nodes[to_id]
                distance = max(_dist(a.x, a.y, b.x, b.y), 0.5)

                # Skip if a direct space↔opening edge already exists (same geometry)
                # Visibility may still add opening↔opening and waypoint hops.
                self._add_directed_visibility_edge(
                    graph,
                    from_id,
                    to_id,
                    distance,
                    space,
                    space_kind,
                    space_width,
                    doors,
                    exits,
                    defaults,
                )
                self._add_directed_visibility_edge(
                    graph,
                    to_id,
                    from_id,
                    distance,
                    space,
                    space_kind,
                    space_width,
                    doors,
                    exits,
                    defaults,
                )

    def _add_directed_visibility_edge(
        self,
        graph: NavigationGraph,
        from_id: str,
        to_id: str,
        distance: float,
        space: Space,
        space_kind: EdgeKind,
        space_width: float,
        doors: dict[str, Door],
        exits: dict[str, Exit],
        defaults: dict[str, float],
    ) -> None:
        # Avoid duplicate adjacency if space↔opening already added
        if edge_exists(graph, from_id, to_id):
            return

        dest = graph.nodes[to_id]
        if dest.kind in (NodeKind.DOOR, NodeKind.EXIT):
            kind, width, flow, elem = _opening_edge_props(dest, doors, exits, defaults)
        else:
            kind = space_kind
            width = space_width
            flow = (
                defaults["stairs_flow_per_s"] if space.type == SpaceType.STAIRS else None
            )
            elem = space.id

        edge_id = f"edge:vis:{from_id}->{to_id}:{space.id}"
        graph.add_edge(
            GraphEdge(
                id=edge_id,
                from_id=from_id,
                to_id=to_id,
                distance_m=distance,
                kind=kind,
                width_m=width,
                flow_rate_per_s=flow,
                capacity_density_per_m2=None,
                area_m2=None,
                element_id=elem,
            ),
            bidirectional=False,
        )

