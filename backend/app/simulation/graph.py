"""Navigation graph construction from building layout.

Compatibility barrel — types live in graph_types, builder in graph_builder.
"""

from __future__ import annotations

from app.simulation.graph_builder import NavigationGraphBuilder
from app.simulation.graph_types import (
    EdgeKind,
    GraphEdge,
    GraphNode,
    NavigationGraph,
    NodeKind,
    edge_exists,
)

__all__ = [
    "EdgeKind",
    "GraphEdge",
    "GraphNode",
    "NavigationGraph",
    "NavigationGraphBuilder",
    "NodeKind",
    "edge_exists",
]
