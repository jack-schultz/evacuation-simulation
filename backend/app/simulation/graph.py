"""Navigation graph construction from building layout."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.domain.building import BuildingLayout, Door, Exit, SpaceType


class NodeKind(str, Enum):
    SPACE = "space"
    DOOR = "door"
    EXIT = "exit"


class EdgeKind(str, Enum):
    SPACE = "space"
    DOOR = "door"
    CORRIDOR = "corridor"
    STAIRS = "stairs"
    EXIT = "exit"


@dataclass(frozen=True)
class GraphNode:
    id: str
    kind: NodeKind
    x: float
    y: float
    ref_id: str  # space / door / exit id


@dataclass
class GraphEdge:
    id: str
    from_id: str
    to_id: str
    distance_m: float
    kind: EdgeKind
    width_m: float
    flow_rate_per_s: float | None
    capacity_density_per_m2: float | None
    area_m2: float | None
    element_id: str
    speed_factor: float = 1.0


@dataclass
class NavigationGraph:
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: dict[str, GraphEdge] = field(default_factory=dict)
    adjacency: dict[str, list[str]] = field(default_factory=dict)
    exit_node_ids: list[str] = field(default_factory=list)
    space_node_ids: dict[str, str] = field(default_factory=dict)  # space_id -> node_id

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.id] = node
        self.adjacency.setdefault(node.id, [])

    def add_edge(self, edge: GraphEdge, *, bidirectional: bool = True) -> None:
        self.edges[edge.id] = edge
        self.adjacency.setdefault(edge.from_id, []).append(edge.id)
        if not bidirectional:
            return
        # undirected: mirror edge
        mirror_id = f"{edge.id}__rev"
        if mirror_id not in self.edges:
            mirror = GraphEdge(
                id=mirror_id,
                from_id=edge.to_id,
                to_id=edge.from_id,
                distance_m=edge.distance_m,
                kind=edge.kind,
                width_m=edge.width_m,
                flow_rate_per_s=edge.flow_rate_per_s,
                capacity_density_per_m2=edge.capacity_density_per_m2,
                area_m2=edge.area_m2,
                element_id=edge.element_id,
            )
            self.edges[mirror_id] = mirror
            self.adjacency.setdefault(mirror.from_id, []).append(mirror_id)


def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _space_center(space) -> tuple[float, float]:
    return space.centroid


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


class NavigationGraphBuilder:
    """Builds a navigable graph from polygonal spaces, doors, and exits.

    Space nodes define connectivity (which openings share a room) and spawn
    start points. People path opening-to-opening within each space.
    """

    def build(self, layout: BuildingLayout, defaults: dict[str, float]) -> NavigationGraph:
        graph = NavigationGraph()
        spaces = {s.id: s for s in layout.spaces}
        doors = {d.id: d for d in layout.doors}
        exits = {e.id: e for e in layout.exits}

        for space in layout.spaces:
            cx, cy = _space_center(space)
            node = GraphNode(id=f"space:{space.id}", kind=NodeKind.SPACE, x=cx, y=cy, ref_id=space.id)
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
            flow = door.flow_rate_per_s if door.flow_rate_per_s is not None else defaults["door_flow_per_s"]
            for space_id in door.connects:
                space = spaces[space_id]
                space_node_id = graph.space_node_ids[space_id]
                sn = graph.nodes[space_node_id]
                distance = _dist(sn.x, sn.y, door.x, door.y)
                # Minimum distance avoids zero-length edges for centered doors
                distance = max(distance, 0.5)
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
                # Space self-edges are tracked for capacity bookkeeping only (not for routing)
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
            space_node_id = graph.space_node_ids[exit_.connected_space_id]
            sn = graph.nodes[space_node_id]
            distance = max(_dist(sn.x, sn.y, exit_.x, exit_.y), 0.5)
            flow = (
                exit_.flow_rate_per_s
                if exit_.flow_rate_per_s is not None
                else defaults["exit_flow_per_s"]
            )
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

        # Opening-to-opening edges within each space (people path these, not centroids)
        for space_id, opening_ids in openings_by_space.items():
            for i, from_id in enumerate(opening_ids):
                for to_id in opening_ids[i + 1 :]:
                    a = graph.nodes[from_id]
                    b = graph.nodes[to_id]
                    distance = max(_dist(a.x, a.y, b.x, b.y), 0.5)
                    kind_b, width_b, flow_b, elem_b = _opening_edge_props(
                        b, doors, exits, defaults
                    )
                    kind_a, width_a, flow_a, elem_a = _opening_edge_props(
                        a, doors, exits, defaults
                    )
                    graph.add_edge(
                        GraphEdge(
                            id=f"edge:open:{a.ref_id}->{b.ref_id}:{space_id}",
                            from_id=from_id,
                            to_id=to_id,
                            distance_m=distance,
                            kind=kind_b,
                            width_m=width_b,
                            flow_rate_per_s=flow_b,
                            capacity_density_per_m2=None,
                            area_m2=None,
                            element_id=elem_b,
                        ),
                        bidirectional=False,
                    )
                    graph.add_edge(
                        GraphEdge(
                            id=f"edge:open:{b.ref_id}->{a.ref_id}:{space_id}",
                            from_id=to_id,
                            to_id=from_id,
                            distance_m=distance,
                            kind=kind_a,
                            width_m=width_a,
                            flow_rate_per_s=flow_a,
                            capacity_density_per_m2=None,
                            area_m2=None,
                            element_id=elem_a,
                        ),
                        bidirectional=False,
                    )

        return graph
