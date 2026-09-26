"""Navigation graph construction from building layout."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.domain.building import BuildingLayout, SpaceType


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


@dataclass()
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

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges[edge.id] = edge
        self.adjacency.setdefault(edge.from_id, []).append(edge.id)
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
    return space.x + space.width / 2, space.y + space.height / 2


def _edge_kind_for_space(space_type: SpaceType) -> EdgeKind:
    if space_type == SpaceType.CORRIDOR:
        return EdgeKind.CORRIDOR
    if space_type == SpaceType.STAIRS:
        return EdgeKind.STAIRS
    return EdgeKind.SPACE


class NavigationGraphBuilder:
    """Builds a navigable graph from rectangular spaces, doors, and exits."""

    def build(self, layout: BuildingLayout, defaults: dict[str, float]) -> NavigationGraph:
        graph = NavigationGraph()
        spaces = {s.id: s for s in layout.spaces}

        for space in layout.spaces:
            cx, cy = _space_center(space)
            node = GraphNode(id=f"space:{space.id}", kind=NodeKind.SPACE, x=cx, y=cy, ref_id=space.id)
            graph.add_node(node)
            graph.space_node_ids[space.id] = node.id

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
                area = space.width * space.height
                density = space.capacity_density_per_m2
                if density is None and space.type in (SpaceType.CORRIDOR, SpaceType.STAIRS):
                    density = defaults["corridor_density_per_m2"]
                space_edge = GraphEdge(
                    id=f"edge:space:{space_id}:door:{door.id}",
                    from_id=space_node_id,
                    to_id=space_node_id,
                    distance_m=0.0,
                    kind=_edge_kind_for_space(space.type),
                    width_m=min(space.width, space.height),
                    flow_rate_per_s=(
                        defaults["stairs_flow_per_s"] if space.type == SpaceType.STAIRS else None
                    ),
                    capacity_density_per_m2=density,
                    area_m2=area,
                    element_id=space.id,
                )
                # Space self-edges are tracked for capacity bookkeeping only (not for routing)
                graph.edges[space_edge.id] = space_edge

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

        return graph
