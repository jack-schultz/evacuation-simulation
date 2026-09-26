"""Navigation graph data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

class NodeKind(str, Enum):
    SPACE = "space"
    DOOR = "door"
    EXIT = "exit"
    WAYPOINT = "waypoint"


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
    # Space nodes retained on movement routes (linked stair teleport waypoints)
    stair_space_node_ids: set[str] = field(default_factory=set)
    # stair space id -> host room/corridor that contains the stair center
    stair_host_space_ids: dict[str, str] = field(default_factory=dict)

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



def edge_exists(graph: NavigationGraph, from_id: str, to_id: str) -> bool:
    for edge_id in graph.adjacency.get(from_id, []):
        edge = graph.edges[edge_id]
        if edge.to_id == to_id and edge.from_id != edge.to_id:
            return True
    return False
