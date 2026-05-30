from __future__ import annotations

from datetime import datetime, timezone

from graph.evidence_spread import assess_change_scope, compute_scope_aware_spread
from graph.schema import ProgramGraph
from graph.weights import compute_node_weights

EVIDENCE_SPREAD_GUARDRAIL = (
    "Evidence spread is explain-only. It does not override grounding, "
    "harness modes, patch safety, or validation."
)


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


def _md_escape(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _fmt_score(value) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "-"


def format_evidence_spread_markdown(result: dict, *, generated_at: str | None = None) -> str:
    """Render a build_scope_evidence_spread_debug result as a Markdown report.

    Read-only formatter. Does not call models, mutate graph weights, or rank
    patches — it just prints what evidence spread already computed.
    """
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    result = result or {}
    query = (result.get("query") or "").strip()
    target = (result.get("target_node") or "").strip()
    nodes = list(result.get("nodes") or [])
    scope = result.get("scope_assessment") or {}
    empty = bool(result.get("empty"))
    message = (result.get("message") or "").strip()

    lines: list[str] = []
    lines.append("# Evidence Spread Report")
    lines.append("")
    lines.append(f"- **query**: {query or '_(none)_'}")
    lines.append(f"- **target_node**: {target or '_(none)_'}")
    lines.append(f"- **generated_at**: {generated_at}")
    lines.append(
        f"- **graph**: {result.get('total_nodes', 0)} nodes, "
        f"{result.get('total_edges', 0)} edges, "
        f"{result.get('scored_nodes', 0)} scored"
    )
    lines.append("")

    if empty:
        lines.append("## Status")
        lines.append("")
        lines.append(message or "No graph evidence available.")
        lines.append("")
    else:
        lines.append(f"## Top {len(nodes)} nodes")
        lines.append("")
        lines.append("| node_id | final_score | base_score | spread_score | reasons |")
        lines.append("| --- | --- | --- | --- | --- |")
        if not nodes:
            lines.append("| _(no scored nodes)_ | - | - | - | - |")
        else:
            for node in nodes:
                reasons = node.get("reasons") or []
                reasons_text = "; ".join(_md_escape(r) for r in reasons) or "-"
                lines.append(
                    "| {nid} | {fs} | {bs} | {ss} | {rs} |".format(
                        nid=_md_escape(node.get("node_id")),
                        fs=_fmt_score(node.get("final_score")),
                        bs=_fmt_score(node.get("base_score")),
                        ss=_fmt_score(node.get("spread_score")),
                        rs=reasons_text,
                    )
                )
        lines.append("")

    lines.append("## Change scope assessment")
    lines.append("")
    if scope:
        classification = scope.get("scope") or "_(unknown)_"
        scope_target = scope.get("target_node") or target or "_(none)_"
        lines.append(f"- **classification**: {classification}")
        lines.append(f"- **target_node**: {scope_target}")
        reasons = scope.get("reasons") or []
        if reasons:
            lines.append("- **reasons**:")
            for r in reasons:
                lines.append(f"  - {r}")
        else:
            lines.append("- **reasons**: _(none)_")
        impacted = scope.get("impacted_nodes") or scope.get("evidence_nodes") or []
        if impacted:
            lines.append("- **impacted_nodes**:")
            for n in impacted:
                lines.append(f"  - {n}")
        else:
            lines.append("- **impacted_nodes**: _(none)_")
    else:
        lines.append("_No scope assessment available._")
    lines.append("")

    lines.append("## Guardrail")
    lines.append("")
    lines.append(EVIDENCE_SPREAD_GUARDRAIL)
    lines.append("")

    return "\n".join(lines)


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
