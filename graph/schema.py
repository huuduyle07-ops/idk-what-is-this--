from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    id: str
    type: str
    label: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProgramGraph:
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)

    def add_node(self, node_id: str, node_type: str, label: str | None = None, **metadata):
        if node_id not in self.nodes:
            self.nodes[node_id] = GraphNode(
                id=node_id,
                type=node_type,
                label=label or node_id,
                metadata=metadata,
            )

    def add_edge(self, source: str, target: str, edge_type: str, **metadata):
        self.edges.append(GraphEdge(
            source=source,
            target=target,
            type=edge_type,
            metadata=metadata,
        ))

    def to_dict(self):
        return {
            "nodes": [n.__dict__ for n in self.nodes.values()],
            "edges": [e.__dict__ for e in self.edges],
        }


def build_graph(
    nodes: list[dict[str, Any]] | None = None,
    edges: list[dict[str, Any]] | None = None,
) -> ProgramGraph:
    """Construct a ProgramGraph from plain node/edge dicts.

    Convenience constructor for callers and tests that have node/edge data as
    dicts. Node dicts use ``id``/``type``/``label`` (plus optional metadata);
    edge dicts use ``source``/``target``/``type`` (plus optional metadata).
    Unknown keys are preserved as node/edge metadata.
    """
    graph = ProgramGraph()
    for node in nodes or []:
        meta = {
            k: v for k, v in node.items() if k not in {"id", "type", "label"}
        }
        graph.add_node(
            node["id"],
            node.get("type", "symbol"),
            node.get("label"),
            **meta,
        )
    for edge in edges or []:
        meta = {
            k: v for k, v in edge.items() if k not in {"source", "target", "type"}
        }
        graph.add_edge(
            edge["source"],
            edge["target"],
            edge.get("type", "edge"),
            **meta,
        )
    return graph