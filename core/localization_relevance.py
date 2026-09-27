"""CONTROL.LOCALIZE.LIVE.2: relevance classes before structural magnitude.

Consumes bounded CONTROL rows and RETRIEVE receipts. No discovery, source
acquisition, token-frequency calculation, execution or authority decisions.
"""
from __future__ import annotations

import re

from core.patch_basis import FailureRelevanceBinding


ANCHOR_RELATIONS = (
    "direct_query_entry", "anchored_expansion", "unanchored_expansion",
)


def verify_entry_paths(graph, evidence: list[dict]) -> None:
    """Verify only the bounded DFS trails against the already-loaded edges.

    The legacy graph query uses substring matching. Its navigation result is
    not by itself an exact edge receipt. This bounded set is discarded after
    verification; no graph, index or expansion is created or changed.
    """
    wanted = set()
    for item in evidence:
        for step in item.get("entry_path", []):
            pair = (step["from"], step["to"])
            wanted.add(pair[::-1] if step["direction"] == "upstream" else pair)
    found = set()
    if wanted:
        for edge in graph.edges:
            pair = (edge.source, edge.target)
            if edge.type == "resolved_call" and pair in wanted:
                found.add(pair)
                if found == wanted:
                    break
    for item in evidence:
        for step in item.get("entry_path", []):
            pair = (step["from"], step["to"])
            if (pair[::-1] if step["direction"] == "upstream" else pair) not in found:
                item["entry_path"] = []
                item["originating_entry"] = None
                break


def describe_relevance(
    query: str,
    item: dict,
    entry_resolution: dict,
    *,
    failure_binding: FailureRelevanceBinding | None = None,
) -> dict:
    """Describe navigation relevance; a binding must come from the existing binder."""
    symbol = item["symbol"]
    entries = list(entry_resolution.get("query_derived_entry_nodes") or [])
    ordering = {
        row["node_id"]: row
        for row in entry_resolution.get("entry_ordering", [])
    }
    direct = symbol in entries
    path = item.get("entry_path") or []
    origin = item.get("originating_entry")
    anchored = bool(
        origin in entries and path and len(path) <= 2
        and path[0].get("from") == origin
        and path[-1].get("to") == symbol
        and all(step.get("edge_kind") == "resolved_call" for step in path)
        and all(left.get("to") == right.get("from") for left, right in zip(path, path[1:]))
    )
    relation = (
        "direct_query_entry" if direct else
        "anchored_expansion" if anchored else "unanchored_expansion"
    )
    origin = symbol if direct else origin if anchored else None
    row = ordering.get(origin, {})
    file, _, name = symbol.partition("::")
    explicit_reference = any(
        re.search(r"(?<![\w/\\])" + re.escape(value) + r"(?![\w/\\])", query)
        for value in (symbol, file, f"`{name}`") if value
    )
    bound = bool(
        isinstance(failure_binding, FailureRelevanceBinding)
        and failure_binding.bound
        and failure_binding.candidate_file.replace("\\", "/").casefold() == file.casefold()
        and failure_binding.candidate_symbol == name
    )
    final_class = (
        "executed_failure_reference" if bound else
        "explicit_query_reference" if explicit_reference else relation
    )
    return {
        "anchor_relation": relation,
        "originating_entry": origin,
        "entry_rank": entries.index(origin) + 1 if origin in entries else None,
        "query_relevance_support": {
            "direct_entry": direct,
            "explicit_reference": explicit_reference,
            "matched_tokens": list(row.get("matched_query_tokens") or []),
            "lexical_specificity_score": row.get("lexical_specificity_score", 0),
            "match_kind": row.get("entry_match_kind"),
        },
        "source_support": {"status": "unavailable", "reason": "no bounded candidate body supplied"},
        "execution_support": failure_binding.as_dict() if bound else None,
        "graph_support": {
            "hop_count": 0 if direct else len(path) if anchored else None,
            "path": path if anchored else [],
        },
        "centrality_support": {
            "upstream_callers": len(item.get("called_by") or []),
            "downstream_callees": len(item.get("calls") or []),
            "impact_count": len(item.get("impact") or []),
            "graph_weight": item.get("graph_weight", 0),
            "legacy_navigation_score": item.get("score", 0),
        },
        "final_localization_class": final_class,
    }


def localization_order_key(hypothesis: dict) -> tuple:
    """Numeric centrality cannot cross a relevance class, at any magnitude."""
    classes = {
        "executed_failure_reference": 4,
        "explicit_query_reference": 3,
        "direct_query_entry": 2,
        "anchored_expansion": 1,
        "unanchored_expansion": 0,
    }
    support = hypothesis.get("query_relevance_support") or {}
    hops = (hypothesis.get("graph_support") or {}).get("hop_count")
    return (
        -classes.get(hypothesis.get("final_localization_class"), 0),
        -support.get("lexical_specificity_score", 0),
        hops if hops is not None else 3,
        -hypothesis.get("localization_score", 0),
        hypothesis["symbol"],
    )


def mark_localization_order(hypotheses: list[dict]) -> list[dict]:
    hypotheses.sort(key=localization_order_key)
    for rank, hypothesis in enumerate(hypotheses, start=1):
        hypothesis["localization_rank"] = rank
        hypothesis["selection_result"] = "selected" if rank == 1 else "rejected"
        hypothesis["selected_reason"] = (
            f"{hypothesis['final_localization_class']}; query specificity, bounded path, "
            "then structural support; canonical identity breaks ties"
            if rank == 1 else "lower in structural relevance ordering"
        )
    return hypotheses
