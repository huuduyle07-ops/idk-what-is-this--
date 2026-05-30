"""Phase 12.13a - Graph Attraction / Repulsion (explain-only MVP).

The "magnetic graph" idea, made into engineering: some nodes should *pull*
attention toward them (they match the query/target, carry high evidence
confidence, or recently failed), while generic utility hubs should *push*
attention away (they are referenced from everywhere and have generic names, so
landing on them is usually a distraction from the real change site).

This module is intentionally **read-only / explain-only**. It produces scores
and human-readable reasons only. It is NOT wired into CONTROL ranking, Evidence
Spread scoring, patch generation, validation, benchmark scoring, or the web UI.
It performs no model/API calls, no subprocess, and no database access - it only
inspects values that callers already computed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Tunables (all local to this explain-only layer)
# --------------------------------------------------------------------------

# Attraction contributions.
_ATTRACT_QUERY = 0.50
_ATTRACT_TARGET = 0.40
_ATTRACT_CONFIDENCE = 0.25
_ATTRACT_FAILURE = 0.20
_ATTRACT_WEIGHT_CAP = 0.30

# Confidence at or above this is treated as strong evidence.
_CONFIDENCE_STRONG = 0.70

# Repulsion contributions.
_REPULSE_HUB = 0.45
_REPULSE_HIGH_DEGREE = 0.25
_REPULSE_GENERIC_NAME = 0.15

# A node with at least this many inbound references is "high in-degree".
_HIGH_IN_DEGREE = 30

# Generic utility names. These are matched as whole tokens inside the node id
# (so "logger" matches via "log"-free word boundaries, and "config" matches
# "config" but not "configuration_service").
_GENERIC_NAMES = (
    "write_text",
    "read_text",
    "helper",
    "helpers",
    "utils",
    "util",
    "log",
    "logger",
    "logging",
    "config",
    "common",
)
_GENERIC_NAME_RE = re.compile(
    r"(?:^|[\\/_.:])(" + "|".join(re.escape(n) for n in _GENERIC_NAMES) + r")(?:[\\/_.:]|$)",
    re.IGNORECASE,
)

GRAPH_ATTRACTION_GUARDRAIL = (
    "Graph attraction/repulsion is explain-only. It does not change CONTROL "
    "ranking, Evidence Spread scoring, patch generation, validation, or "
    "benchmark scoring."
)


@dataclass(frozen=True)
class GraphAttraction:
    node_id: str
    attraction: float
    repulsion: float
    net_score: float
    reasons: tuple[str, ...] = field(default_factory=tuple)
    is_generic_hub: bool = False


# --------------------------------------------------------------------------
# Helpers (pure)
# --------------------------------------------------------------------------

def _query_matches(query: str, node_id: str) -> bool:
    """True when non-empty query text appears (case-insensitively) in node_id."""
    query = (query or "").strip().lower()
    if not query:
        return False
    return query in (node_id or "").lower()


def _has_generic_name(node_id: str) -> bool:
    return bool(_GENERIC_NAME_RE.search(node_id or ""))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _coerce_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def is_generic_utility_hub(
    node_id: str,
    in_degree: int = 0,
    out_degree: int = 0,
    query: str = "",
) -> bool:
    """Conservatively decide whether a node is a generic utility hub.

    A node is a hub only when it has a high in-degree OR a generic utility name,
    AND the query does not point directly at it. Direct query matches always win:
    if the user is asking about this node by name, it is a target, not noise.
    """
    if _query_matches(query, node_id):
        return False
    return in_degree >= _HIGH_IN_DEGREE or _has_generic_name(node_id)


def classify_node_attraction(
    node_id: str,
    *,
    query: str = "",
    target_node: str = "",
    in_degree: int = 0,
    out_degree: int = 0,
    graph_weight: float = 0.0,
    evidence_confidence: float | None = None,
    failure_penalty: float = 0.0,
) -> GraphAttraction:
    """Explain why a node should attract or repel attention (read-only).

    Attraction rewards query/target matches, strong evidence confidence, recent
    failure association, and global graph weight (capped). Repulsion penalizes
    generic utility hubs, very-high in-degree nodes the query does not target,
    and generic names. ``net_score`` is ``attraction - repulsion`` clamped to
    ``[-1.0, 1.0]``.
    """
    node_id = node_id or ""
    reasons: list[str] = []

    # ---- Attraction ----------------------------------------------------
    attraction = 0.0
    if _query_matches(query, node_id):
        attraction += _ATTRACT_QUERY
        reasons.append(f"query text matches node id (+{_ATTRACT_QUERY:.2f})")
    if target_node and node_id == target_node:
        attraction += _ATTRACT_TARGET
        reasons.append(f"exact target match (+{_ATTRACT_TARGET:.2f})")
    if evidence_confidence is not None and _coerce_float(evidence_confidence) >= _CONFIDENCE_STRONG:
        attraction += _ATTRACT_CONFIDENCE
        reasons.append(
            f"strong evidence confidence >= {_CONFIDENCE_STRONG:.2f} "
            f"(+{_ATTRACT_CONFIDENCE:.2f})"
        )
    if _coerce_float(failure_penalty) > 0:
        attraction += _ATTRACT_FAILURE
        reasons.append(f"associated with a recent failure (+{_ATTRACT_FAILURE:.2f})")
    weight_contrib = min(max(_coerce_float(graph_weight), 0.0), _ATTRACT_WEIGHT_CAP)
    if weight_contrib > 0:
        attraction += weight_contrib
        reasons.append(f"graph weight (+{weight_contrib:.2f}, capped at {_ATTRACT_WEIGHT_CAP:.2f})")

    # ---- Repulsion -----------------------------------------------------
    repulsion = 0.0
    is_hub = is_generic_utility_hub(node_id, in_degree, out_degree, query)
    if is_hub:
        repulsion += _REPULSE_HUB
        reasons.append(f"generic utility hub (-{_REPULSE_HUB:.2f})")
    if in_degree >= _HIGH_IN_DEGREE and not _query_matches(query, node_id):
        repulsion += _REPULSE_HIGH_DEGREE
        reasons.append(
            f"high in-degree (>= {_HIGH_IN_DEGREE}) without query match "
            f"(-{_REPULSE_HIGH_DEGREE:.2f})"
        )
    if _has_generic_name(node_id):
        repulsion += _REPULSE_GENERIC_NAME
        reasons.append(f"generic utility name (-{_REPULSE_GENERIC_NAME:.2f})")

    net_score = _clamp(attraction - repulsion, -1.0, 1.0)

    return GraphAttraction(
        node_id=node_id,
        attraction=round(attraction, 6),
        repulsion=round(repulsion, 6),
        net_score=round(net_score, 6),
        reasons=tuple(reasons),
        is_generic_hub=is_hub,
    )


def explain_attraction_batch(
    nodes: list[dict],
    query: str = "",
    target_node: str = "",
) -> list[GraphAttraction]:
    """Classify a batch of node dicts (e.g. Evidence Spread/debug output).

    Recognized keys (all optional except a usable id):
      * ``node_id``
      * ``in_degree`` / ``out_degree``
      * ``graph_weight`` -> ``base_score`` -> ``final_score`` (first present)
      * ``evidence_confidence`` -> ``confidence`` (first present)
      * ``failure_penalty``

    Order is preserved. Unknown/missing fields fall back to safe defaults so the
    caller never has to pre-clean Evidence Spread output.
    """
    items: list[GraphAttraction] = []
    for index, raw in enumerate(nodes or []):
        node = raw if isinstance(raw, dict) else {}
        node_id = str(node.get("node_id") or "").strip() or f"node_{index}"

        weight = node.get("graph_weight")
        if weight is None:
            weight = node.get("base_score")
        if weight is None:
            weight = node.get("final_score")

        confidence = node.get("evidence_confidence")
        if confidence is None:
            confidence = node.get("confidence")

        items.append(
            classify_node_attraction(
                node_id,
                query=query,
                target_node=target_node,
                in_degree=_coerce_int(node.get("in_degree")),
                out_degree=_coerce_int(node.get("out_degree")),
                graph_weight=_coerce_float(weight),
                evidence_confidence=(None if confidence is None else _coerce_float(confidence)),
                failure_penalty=_coerce_float(node.get("failure_penalty")),
            )
        )
    return items


def format_attraction_markdown(
    items: list[GraphAttraction],
    *,
    heading: str = "# Graph Attraction / Repulsion (explain-only)",
    guardrail: str = GRAPH_ATTRACTION_GUARDRAIL,
    total_weights: dict[str, float] | None = None,
) -> str:
    """Render attraction/repulsion explanations as a read-only Markdown table."""
    lines: list[str] = []
    lines.append(heading)
    lines.append("")
    if total_weights is None:
        lines.append("| node_id | attraction | repulsion | net_score | generic hub? | reasons |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
    else:
        lines.append(
            "| node_id | total_weight | attraction | repulsion | net_score | "
            "generic hub? | reasons |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    if not items:
        if total_weights is None:
            lines.append("| _(no nodes)_ | - | - | - | - | - |")
        else:
            lines.append("| _(no nodes)_ | - | - | - | - | - | - |")
    else:
        for item in items:
            reasons = "; ".join(item.reasons) if item.reasons else "-"
            reasons = reasons.replace("|", "\\|").replace("\n", " ")
            if total_weights is None:
                lines.append(
                    "| {nid} | {a:.2f} | {r:.2f} | {n:+.2f} | {hub} | {rs} |".format(
                        nid=str(item.node_id).replace("|", "\\|"),
                        a=item.attraction,
                        r=item.repulsion,
                        n=item.net_score,
                        hub="yes" if item.is_generic_hub else "no",
                        rs=reasons,
                    )
                )
            else:
                lines.append(
                    "| {nid} | {tw:.2f} | {a:.2f} | {r:.2f} | {n:+.2f} | {hub} | {rs} |".format(
                        nid=str(item.node_id).replace("|", "\\|"),
                        tw=float(total_weights.get(item.node_id, 0.0)),
                        a=item.attraction,
                        r=item.repulsion,
                        n=item.net_score,
                        hub="yes" if item.is_generic_hub else "no",
                        rs=reasons,
                    )
                )
    lines.append("")
    lines.append(f"> {guardrail}")
    lines.append("")
    return "\n".join(lines)
