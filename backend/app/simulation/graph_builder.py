"""Build a navigation graph from a building layout."""

from __future__ import annotations

from app.domain.building import BuildingLayout, Door, Exit, Space, SpaceType
from app.domain.geometry import (
    interior_point,
    point_in_polygon,
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

from app.simulation.obstacles import corner_points, free_position, visible, wall_clearance_cost

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
        graph = NavigationGraph(obstacles=layout.obstacles, spaces={s.id: s for s in layout.spaces})
        spaces = {s.id: s for s in layout.spaces}
        doors = {d.id: d for d in layout.doors}
        exits = {e.id: e for e in layout.exits}

        radius = float(defaults.get("occupant_radius_m", 0.25))
        obstacle_floors = {o.floor_id for o in layout.obstacles}
        for space in layout.spaces:
            cx, cy = interior_point(space.vertices)
            obstacles = [o for o in layout.obstacles if o.floor_id == space.floor_id]
            if obstacles:
                cx, cy = free_position((cx, cy), space, obstacles, radius) or (cx, cy)
            node = GraphNode(
                id=f"space:{space.id}", kind=NodeKind.SPACE, x=cx, y=cy, ref_id=space.id
            )
            graph.add_node(node)
            graph.space_node_ids[space.id] = node.id
            graph.space_floor_ids[space.id] = space.floor_id
            if space.type == SpaceType.STAIRS:
                graph.stair_space_node_ids.add(node.id)

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
                if visible((sn.x, sn.y), portal, space, [o for o in layout.obstacles if o.floor_id == space.floor_id], radius):
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
                        route_penalty_m=wall_clearance_cost(
                            (sn.x, sn.y), portal, space, radius,
                        ) if space.floor_id in obstacle_floors else 0.0,
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
            if visible((sn.x, sn.y), portal, space, [o for o in layout.obstacles if o.floor_id == space.floor_id], radius):
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
                    route_penalty_m=wall_clearance_cost(
                        (sn.x, sn.y), portal, space, radius,
                    ) if space.floor_id in obstacle_floors else 0.0,
                )
                graph.add_edge(edge)
            openings_by_space[exit_.connected_space_id].append(node.id)

        # Stairs overlay their host spaces: register as openings so people can
        # path to the stair center without a separate door.
        self._register_stair_hosts(graph, spaces, openings_by_space)

        # Per-space visibility graph: openings + reflex waypoints + space node
        for space_id, opening_ids in openings_by_space.items():
            space = spaces[space_id]
            self._add_visibility_edges(
                graph, space, opening_ids, doors, exits, defaults,
                [o for o in layout.obstacles if o.floor_id == space.floor_id]
            )

        if layout.obstacles:
            from app.domain.geometry import edges
            from app.simulation.walls import _point_to_segment_dist
            for opening in [*layout.doors, *layout.exits]:
                host_id = opening.connects[0] if isinstance(opening, Door) else opening.connected_space_id
                segments = list(edges(spaces[host_id].vertices))
                a, b = min(segments, key=lambda pair: _point_to_segment_dist(opening.x, opening.y, *pair[0], *pair[1]))
                length = _dist(*a, *b)
                if length > 1e-9 and _point_to_segment_dist(opening.x, opening.y, *a, *b) < 0.25:
                    nid = f"door:{opening.id}" if isinstance(opening, Door) else f"exit:{opening.id}"
                    graph.opening_axes[nid] = ((b[0]-a[0])/length, (b[1]-a[1])/length)

        self._add_stair_link_edges(graph, spaces, defaults, layout)

        return graph

    def add_spawn_node(self, graph, layout, space, position, node_id, defaults):
        radius = float(defaults.get("occupant_radius_m", 0.25))
        obstacles = [o for o in layout.obstacles if o.floor_id == space.floor_id]
        doors = {d.id: d for d in layout.doors}
        exits = {e.id: e for e in layout.exits}
        graph.add_node(GraphNode(node_id, NodeKind.WAYPOINT, *position, space.id))
        for node in list(graph.nodes.values()):
            if node.id.startswith("spawn:"):
                continue
            belongs = (
                (node.kind in (NodeKind.SPACE, NodeKind.WAYPOINT) and node.ref_id == space.id)
                or (node.kind == NodeKind.DOOR and space.id in doors[node.ref_id].connects)
                or (node.kind == NodeKind.EXIT and exits[node.ref_id].connected_space_id == space.id)
                or graph.stair_host_space_ids.get(node.ref_id) == space.id
            )
            if not belongs or not visible(position, (node.x, node.y), space, obstacles, radius):
                continue
            self._add_directed_visibility_edge(
                graph, node_id, node.id, max(_dist(*position, node.x, node.y), 0.01),
                space, _edge_kind_for_space(space.type), min(space.bbox[2:]),
                doors, exits, defaults,
                wall_clearance_cost(position, (node.x, node.y), space, radius)
                if obstacles else 0.0,
            )

    def _register_stair_hosts(
        self,
        graph: NavigationGraph,
        spaces: dict[str, Space],
        openings_by_space: dict[str, list[str]],
    ) -> None:
        """Treat each stair as an opening inside same-floor spaces that contain its center."""
        for space in spaces.values():
            if space.type != SpaceType.STAIRS:
                continue
            stair_nid = graph.space_node_ids[space.id]
            sn = graph.nodes[stair_nid]
            hosts: list[Space] = []
            for other in spaces.values():
                if other.id == space.id or other.type == SpaceType.STAIRS:
                    continue
                if other.floor_id != space.floor_id:
                    continue
                if point_in_polygon(sn.x, sn.y, other.vertices):
                    hosts.append(other)
            if not hosts:
                continue
            host = min(hosts, key=lambda s: s.area_m2)
            graph.stair_host_space_ids[space.id] = host.id
            openings_by_space[host.id].append(stair_nid)

    def _add_stair_link_edges(
        self,
        graph: NavigationGraph,
        spaces: dict[str, Space],
        defaults: dict[str, float],
        layout: BuildingLayout,
    ) -> None:
        """Directed climb edges between linked stair space nodes (ascent slower)."""
        from app.simulation.stair_geometry import climb_path_length_m, floor_elevation

        floors = {f.id: f for f in layout.floors}
        seen_pairs: set[frozenset[str]] = set()
        for space in spaces.values():
            if space.type != SpaceType.STAIRS or not space.linked_stair_id:
                continue
            other = spaces.get(space.linked_stair_id)
            if other is None or other.type != SpaceType.STAIRS:
                continue
            pair = frozenset({space.id, other.id})
            if len(pair) < 2 or pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            a_id = graph.space_node_ids[space.id]
            b_id = graph.space_node_ids[other.id]
            distance = max(climb_path_length_m(space, other, floors), 0.5)
            _, _, bw, bh = space.bbox
            width = min(bw, bh) if bw > 0 and bh > 0 else 1.0
            elev_a = floor_elevation(floors, space.floor_id)
            elev_b = floor_elevation(floors, other.floor_id)
            descent = float(defaults.get("stair_descent_speed_factor", 0.55))
            ascent = float(defaults.get("stair_ascent_speed_factor", 0.35))
            a_to_b = descent if elev_a >= elev_b else ascent
            b_to_a = descent if elev_b >= elev_a else ascent
            graph.add_edge(
                GraphEdge(
                    id=f"edge:stair_link:{space.id}:{other.id}",
                    from_id=a_id,
                    to_id=b_id,
                    distance_m=distance,
                    kind=EdgeKind.STAIRS,
                    width_m=width,
                    flow_rate_per_s=defaults.get("stairs_flow_per_s"),
                    capacity_density_per_m2=None,
                    area_m2=None,
                    element_id=space.id,
                    base_speed_factor=a_to_b,
                    speed_factor=a_to_b,
                ),
                bidirectional=False,
            )
            graph.add_edge(
                GraphEdge(
                    id=f"edge:stair_link:{other.id}:{space.id}",
                    from_id=b_id,
                    to_id=a_id,
                    distance_m=distance,
                    kind=EdgeKind.STAIRS,
                    width_m=width,
                    flow_rate_per_s=defaults.get("stairs_flow_per_s"),
                    capacity_density_per_m2=None,
                    area_m2=None,
                    element_id=other.id,
                    base_speed_factor=b_to_a,
                    speed_factor=b_to_a,
                ),
                bidirectional=False,
            )

    def _add_visibility_edges(
        self,
        graph: NavigationGraph,
        space: Space,
        opening_ids: list[str],
        doors: dict[str, Door],
        exits: dict[str, Exit],
        defaults: dict[str, float],
        obstacles=(),
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

        radius = float(defaults.get("occupant_radius_m", 0.25))
        for i, (wx, wy) in enumerate(corner_points(obstacles, radius, space)):
            wid = f"waypoint:{space.id}:obstacle:{i}"
            graph.add_node(GraphNode(id=wid, kind=NodeKind.WAYPOINT, x=wx, y=wy, ref_id=space.id))
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
                if not visible(pa, pb, space, obstacles, radius):
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
                    wall_clearance_cost(pa, pb, space, radius) if obstacles else 0.0,
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
                    wall_clearance_cost(pa, pb, space, radius) if obstacles else 0.0,
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
        route_penalty_m: float = 0.0,
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
                route_penalty_m=route_penalty_m,
            ),
            bidirectional=False,
        )

