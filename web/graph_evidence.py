from __future__ import annotations

from graph.evidence_spread import assess_change_scope, compute_scope_aware_spread
from graph.schema import ProgramGraph
from graph.weights import compute_node_weights


def build_scope_evidence_spread_debug(
    graph: ProgramGraph,
    query: str,
    *,
    target_node: str | None = None,
    seed_nodes: list[str] | None = None,
    top_n: int = 10,
) -> dict:
    """Build a read-only, JSON-safe explanation of scope-aware spread scores."""
    query = (query or "").strip()
    target = (target_node or "").strip()
    requested_seeds = [
        seed.strip()
        for seed in (seed_nodes or [])
        if isinstance(seed, str) and seed.strip()
    ]

    if not graph.nodes:
        return _empty_spread_result(
            query=query,
            target_node=target,
            message="No graph evidence available: the graph has no nodes.",
            total_nodes=0,
            total_edges=0,
        )

    valid_target = target if target in graph.nodes else ""
    valid_seeds = [seed for seed in requested_seeds if seed in graph.nodes]
    if valid_target and valid_target not in valid_seeds:
        valid_seeds.append(valid_target)

    if not query and not valid_seeds:
        return _empty_spread_result(
            query=query,
            target_node=valid_target,
            message="No graph evidence available: enter a query or selected target node.",
            total_nodes=len(graph.nodes),
            total_edges=len(graph.edges),
        )

    limit = max(1, min(int(top_n or 10), 50))
    base_weights = compute_node_weights(graph)
    scores = compute_scope_aware_spread(
        graph,
        query,
        base_weights=base_weights,
        seed_nodes=valid_seeds,
    )

    assessment_target = valid_target or _inferred_target(scores, valid_seeds)
    scope_assessment = None
    if assessment_target:
        scope = assess_change_scope(
            scores,
            graph=graph,
            target_node=assessment_target,
        )
        scope_assessment = {
            "target_node": assessment_target,
            "scope": scope.scope,
            "reasons": list(scope.reasons),
            "evidence_nodes": list(scope.evidence_nodes),
        }

    return {
        "ok": True,
        "empty": False,
        "message": "",
        "query": query,
        "target_node": assessment_target,
        "seed_nodes": sorted(valid_seeds),
        "top_n": limit,
        "total_nodes": len(graph.nodes),
        "total_edges": len(graph.edges),
        "scored_nodes": len(scores),
        "nodes": [_serialize_spread_score(score) for score in scores[:limit]],
        "scope_assessment": scope_assessment,
    }


def _empty_spread_result(
    *,
    query: str,
    target_node: str,
    message: str,
    total_nodes: int,
    total_edges: int,
) -> dict:
    return {
        "ok": True,
        "empty": True,
        "message": message,
        "query": query,
        "target_node": target_node,
        "seed_nodes": [],
        "top_n": 0,
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "scored_nodes": 0,
        "nodes": [],
        "scope_assessment": None,
    }


def _inferred_target(scores, seed_nodes: list[str]) -> str:
    for score in scores:
        if score.distance == 0 and (score.query_score > 0 or score.node_id in seed_nodes):
            return score.node_id
    return scores[0].node_id if scores else ""


def _serialize_spread_score(score) -> dict:
    return {
        "node_id": score.node_id,
        "final_score": score.final_score,
        "base_score": score.base_score,
        "spread_score": score.spread_boost,
        "query_score": score.query_score,
        "distance": score.distance,
        "seed_nodes": list(score.seed_nodes),
        "reasons": list(score.reasons),
    }
