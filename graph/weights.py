from __future__ import annotations

import dataclasses
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from graph.penalty import build_penalty_map


TYPE_NODES = {
    "class",
    "type",
    "interface",
    "struct",
    "enum",
    "trait",
    "union",
    "object",
    "record",
}


@dataclass(frozen=True)
class NodeWeight:
    node_id: str
    node_type: str
    in_degree: int = 0
    out_degree: int = 0
    complexity: int = 0
    weight: float = 0.0
    penalty: float = 0.0
    reasons: list[str] = field(default_factory=list)


def is_noise_node(node_id: str, node_type: str) -> bool:
    return (
        node_type in {"call", "expression"}
        or node_id.startswith("call::")
        or "::expr::" in node_id
    )


def compute_node_weights(
    graph,
    *,
    alpha: float = 2.0,
    beta: float = 1.0,
    gamma: float = 0.5,
    include_noise: bool = False,
    repo_path: str | None = None,
) -> dict[str, NodeWeight]:
    nodes = getattr(graph, "nodes", None)
    if not nodes:
        return {}

    included = {
        node_id: node
        for node_id, node in nodes.items()
        if include_noise or not is_noise_node(node_id, getattr(node, "type", ""))
    }
    if not included:
        return {}

    incoming: dict[str, int] = defaultdict(int)
    outgoing: dict[str, int] = defaultdict(int)
    contained: dict[str, int] = defaultdict(int)
    executed: dict[str, int] = defaultdict(int)

    for edge in getattr(graph, "edges", []) or []:
        source = getattr(edge, "source", "")
        target = getattr(edge, "target", "")
        edge_type = getattr(edge, "type", "")
        source_type = _node_type(included, source)
        target_type = _node_type(included, target)

        if edge_type == "resolved_call":
            if source_type == "function":
                outgoing[source] += 1
            if target_type == "function" or target_type in TYPE_NODES:
                incoming[target] += 1
        elif edge_type == "imports":
            if source_type == "file":
                outgoing[source] += 1
            if target_type == "file":
                incoming[target] += 1
        elif edge_type == "contains":
            if source in included and target in included:
                contained[source] += 1
        elif edge_type == "executes":
            if source_type == "function":
                executed[source] += 1

    raw_metrics: dict[str, tuple[int, int, int]] = {}
    for node_id, node in included.items():
        node_type = getattr(node, "type", "")
        in_degree = incoming[node_id]
        out_degree = outgoing[node_id]
        complexity = 0

        if node_type == "function":
            complexity = executed[node_id]
        elif node_type == "file":
            complexity = contained[node_id]
        elif node_type in TYPE_NODES:
            out_degree += contained[node_id]
            complexity = contained[node_id]

        raw_metrics[node_id] = (in_degree, out_degree, complexity)

    max_in = max((values[0] for values in raw_metrics.values()), default=0)
    max_out = max((values[1] for values in raw_metrics.values()), default=0)
    max_complexity = max((values[2] for values in raw_metrics.values()), default=0)

    metrics: dict[str, NodeWeight] = {}
    for node_id, node in included.items():
        in_degree, out_degree, complexity = raw_metrics[node_id]
        weight = (
            alpha * _normalize(in_degree, max_in)
            + beta * _normalize(out_degree, max_out)
            + gamma * _normalize(complexity, max_complexity)
        )
        metrics[node_id] = NodeWeight(
            node_id=node_id,
            node_type=getattr(node, "type", ""),
            in_degree=in_degree,
            out_degree=out_degree,
            complexity=complexity,
            weight=round(weight, 4),
            reasons=_build_reasons(in_degree, out_degree, complexity),
        )

    if repo_path is not None:
        _apply_penalty(metrics, graph, repo_path)

    return metrics


def _apply_penalty(
    metrics: dict[str, NodeWeight],
    graph,
    repo_path: str,
) -> None:
    result = build_penalty_map(graph, repo_path)
    for node_id, penalty_value in result.penalty_map.items():
        metric = metrics.get(node_id)
        if metric is None:
            continue
        extra: list[str] = []
        blocked_n = result.blocked_counts.get(node_id, 0)
        transient_n = result.transient_counts.get(node_id, 0)
        if blocked_n:
            extra.append(f"blocked_lessons={blocked_n}")
        if transient_n:
            extra.append(f"patch_failures={transient_n}")
        metrics[node_id] = dataclasses.replace(
            metric,
            weight=round(metric.weight + penalty_value, 4),
            penalty=round(penalty_value, 4),
            reasons=metric.reasons + extra,
        )


def get_node_weight(metrics: dict[str, NodeWeight], node_id: str) -> float:
    metric = metrics.get(node_id)
    if metric is None:
        return 0.0
    return metric.weight


def rank_nodes_by_weight(
    graph,
    *,
    limit: int = 10,
    include_noise: bool = False,
    node_types: Iterable[str] | None = None,
) -> list[NodeWeight]:
    allowed_types = set(node_types or [])
    metrics = compute_node_weights(graph, include_noise=include_noise)
    ranked = [
        metric
        for metric in metrics.values()
        if not allowed_types or metric.node_type in allowed_types
    ]
    ranked.sort(key=lambda metric: (-metric.weight, metric.node_id))
    return ranked[:limit]


def _node_type(nodes, node_id: str) -> str:
    node = nodes.get(node_id)
    if node is None:
        return ""
    return getattr(node, "type", "")


def _normalize(value: int, max_value: int) -> float:
    if max_value <= 0:
        return 0.0
    return value / max_value


def _build_reasons(in_degree: int, out_degree: int, complexity: int) -> list[str]:
    reasons: list[str] = []
    if in_degree:
        reasons.append(f"in_degree={in_degree}")
    if out_degree:
        reasons.append(f"out_degree={out_degree}")
    if complexity:
        reasons.append(f"complexity={complexity}")
    if not reasons:
        reasons.append("isolated_or_unresolved")
    return reasons
