"""Phase 12.11 - Scope-Aware Evidence Spread.

Deterministic, query-time scoring that understands the *bounded scope* of a
possible change. Instead of inspecting only the exact target snippet, the agent
spreads relevance from seed nodes (direct query/file matches, or explicitly
provided target/validation/linter locations) through a few graph neighbors -
callers, callees, tests, same-file related symbols, imports/exports - and then
classifies the likely blast radius of a patch.

Architecture rules (enforced by tests):
* Base graph weights are NEVER mutated. Base weight stays stable/global; the
  spread is query-time only and lives entirely in the returned scores.
* Pure module: no model calls, no network, no subprocess, no agent imports.
  It depends only on the in-memory graph and (optionally) precomputed weights.

The spread is intentionally bounded and explainable - every boost carries
human-readable reasons naming the seed and the distance.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from graph.schema import ProgramGraph
from graph.weights import compute_node_weights

# Distance -> boost contribution. Distances beyond the table are ignored.
_DISTANCE_BOOST = {0: 1.0, 1: 0.4, 2: 0.15}

# A node is treated as a "utility hub" when its total degree reaches this, or
# when its name looks like a generic shared utility. Hubs with no direct query
# match are suppressed so they cannot dominate ranking.
_HUB_DEGREE = 4
_HUB_FINAL_CAP = 0.25
_UTILITY_NAME_RE = re.compile(
    r"(^|[\\/_.:])(utils?|helpers?|common|shared|logger|logging|log|misc)([\\/_.:]|$)",
    re.IGNORECASE,
)


@dataclass
class SpreadScore:
    node_id: str
    base_score: float
    query_score: float
    spread_boost: float
    final_score: float
    reasons: list[str] = field(default_factory=list)
    seed_nodes: list[str] = field(default_factory=list)
    distance: int | None = None


@dataclass
class ChangeScopeAssessment:
    scope: str
    reasons: list[str] = field(default_factory=list)
    evidence_nodes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Helpers (pure)
# --------------------------------------------------------------------------

def _weight_value(entry) -> float:
    """Extract a float weight from either a NodeWeight or a raw number.

    ``compute_node_weights`` returns ``dict[str, NodeWeight]``; callers may also
    pass a precomputed ``dict[str, float]``. Support both without importing the
    NodeWeight type (keeps this module decoupled).
    """
    if entry is None:
        return 0.0
    if isinstance(entry, (int, float)):
        return float(entry)
    weight = getattr(entry, "weight", None)
    if isinstance(weight, (int, float)):
        return float(weight)
    return 0.0


def _file_of(node_id: str) -> str:
    return node_id.split("::", 1)[0] if "::" in node_id else node_id


def _is_test_node(node_id: str) -> bool:
    file = _file_of(node_id).lower()
    name = file.replace("\\", "/").split("/")[-1]
    return (
        "test" in name
        or "spec" in name
        or "/test" in file
        or "/tests/" in file
        or file.startswith("tests/")
    )


_CONTRACT_NAME_RE = re.compile(
    r"(export|__all__|public[_-]?api|\bapi\b|contract|schema|interface|readme|\.md\b)",
    re.IGNORECASE,
)
_CONTRACT_TYPES = {"interface", "type", "enum", "export"}


def _is_contract_node(node_id: str, node_type: str) -> bool:
    if (node_type or "").lower() in _CONTRACT_TYPES:
        return True
    return bool(_CONTRACT_NAME_RE.search(node_id))


def _tokenize(query: str) -> set[str]:
    tokens: set[str] = set()
    for raw in re.findall(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*", (query or "").lower()):
        tokens.add(raw)
        for part in re.split(r"[./\\]", raw):
            if part:
                tokens.add(part)
    return tokens


def _query_match_kind(node, node_id: str, tokens: set[str]) -> str | None:
    """Return 'file', 'symbol', or None for how the query matches this node."""
    nid = node_id.lower()
    if (node.type or "").lower() == "file":
        base = nid.replace("\\", "/").split("/")[-1]
        if nid in tokens or base in tokens:
            return "file"
        return None
    label = (node.label or "").lower()
    if label and label in tokens:
        return "symbol"
    # Also allow the symbol portion of the id to match.
    if "::" in nid and nid.split("::", 1)[1] in tokens:
        return "symbol"
    return None


def _build_adjacency(graph: ProgramGraph) -> dict[str, list[tuple[str, str]]]:
    """Undirected adjacency: node -> sorted list of (neighbor, edge_type).

    Spread is about *impact proximity*, which is bidirectional: a caller is as
    relevant to a callee as the reverse. Self-loops (e.g. import_hint) are
    skipped so they do not create spurious distance.
    """
    adj: dict[str, list[tuple[str, str]]] = {nid: [] for nid in graph.nodes}
    for edge in graph.edges:
        if edge.source == edge.target:
            continue
        if edge.source in adj and edge.target in graph.nodes:
            adj[edge.source].append((edge.target, edge.type))
        if edge.target in adj and edge.source in graph.nodes:
            adj[edge.target].append((edge.source, edge.type))
    for nid in adj:
        adj[nid].sort()
    return adj


def _bfs_distances(
    adj: dict[str, list[tuple[str, str]]],
    seed: str,
    max_distance: int,
) -> dict[str, int]:
    """Shortest hop distance from a single seed, bounded by max_distance."""
    dist = {seed: 0}
    frontier = [seed]
    d = 0
    while frontier and d < max_distance:
        d += 1
        nxt: list[str] = []
        for node in frontier:
            for neighbor, _etype in adj.get(node, []):
                if neighbor not in dist:
                    dist[neighbor] = d
                    nxt.append(neighbor)
        frontier = nxt
    return dist


def _edge_reason(adj, node_id: str, predecessor: str | None) -> str | None:
    if predecessor is None:
        return None
    etype = ""
    for neighbor, edge_type in adj.get(node_id, []):
        if neighbor == predecessor:
            etype = (edge_type or "").lower()
            break
    if etype in {"calls", "call", "references", "reference", "invokes"}:
        return "caller/callee relationship"
    if etype in {"contains", "contain", "defines"}:
        return "same-file related symbol"
    if "import" in etype or "export" in etype:
        return "import/export relationship"
    return None


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def compute_scope_aware_spread(
    graph: ProgramGraph,
    query: str,
    base_weights: dict[str, float] | None = None,
    seed_nodes: list[str] | None = None,
    max_distance: int = 2,
    cap: float = 1.0,
) -> list[SpreadScore]:
    """Score every node by query-time, scope-aware evidence spread.

    Seeds come from (a) explicitly provided ``seed_nodes`` (e.g. the current
    target symbol/file, validation locations, or linter findings) and (b)
    direct query/file-path text matches. Relevance spreads to bounded graph
    neighbors: distance 0 contributes +1.0, distance 1 +0.4, distance 2 +0.15,
    distance >=3 nothing. ``spread_boost`` is the (capped) accumulation.

    ``base_weights`` (global graph weight) is read only and never mutated; when
    omitted it is derived via :func:`compute_node_weights`.
    """
    if base_weights is None:
        base_weights = compute_node_weights(graph)

    tokens = _tokenize(query)

    # --- Seed selection -------------------------------------------------
    # origin reason per seed; query_score marks textual (query/file) matches.
    seed_reason: dict[str, str] = {}
    query_matched: set[str] = set()

    for node_id, node in graph.nodes.items():
        kind = _query_match_kind(node, node_id, tokens)
        if kind == "file":
            seed_reason[node_id] = "explicit file path match"
            query_matched.add(node_id)
        elif kind == "symbol":
            seed_reason[node_id] = "direct query match"
            query_matched.add(node_id)

    for s in seed_nodes or []:
        if s in graph.nodes:
            seed_reason.setdefault(s, "provided seed node")

    seeds = sorted(seed_reason)
    adj = _build_adjacency(graph)

    # --- Accumulate spread_boost from each seed -------------------------
    boost: dict[str, float] = {nid: 0.0 for nid in graph.nodes}
    min_dist: dict[str, int] = {}
    reach_seeds: dict[str, list[str]] = {nid: [] for nid in graph.nodes}

    for seed in seeds:
        distances = _bfs_distances(adj, seed, max_distance)
        for node_id, d in distances.items():
            contrib = _DISTANCE_BOOST.get(d)
            if contrib is None:
                continue
            boost[node_id] += contrib
            reach_seeds[node_id].append(seed)
            if node_id not in min_dist or d < min_dist[node_id]:
                min_dist[node_id] = d

    # --- Shortest-path predecessor + originating seed (for reasons) -----
    pred: dict[str, str | None] = {}
    root_seed: dict[str, str] = {}
    visited: dict[str, int] = {}
    frontier: list[str] = []
    for seed in seeds:
        if seed not in visited:
            visited[seed] = 0
            pred[seed] = None
            root_seed[seed] = seed
            frontier.append(seed)
    d = 0
    while frontier and d < max_distance:
        d += 1
        nxt: list[str] = []
        for node in frontier:
            for neighbor, _etype in adj.get(node, []):
                if neighbor not in visited:
                    visited[neighbor] = d
                    pred[neighbor] = node
                    root_seed[neighbor] = root_seed[node]
                    nxt.append(neighbor)
        frontier = nxt

    in_deg = _degree(graph, source=False)
    out_deg = _degree(graph, source=True)

    scores: list[SpreadScore] = []
    for node_id, node in graph.nodes.items():
        base = _weight_value(base_weights.get(node_id))
        q_score = 1.0 if node_id in query_matched else 0.0
        raw_boost = boost.get(node_id, 0.0)
        capped_boost = min(raw_boost, cap)
        dist = min_dist.get(node_id)

        reasons: list[str] = []
        if dist == 0:
            reasons.append(seed_reason.get(node_id, "seed node"))
        elif dist is not None:
            origin = root_seed.get(node_id, "")
            reasons.append(f"distance-{dist} neighbor of {origin}")
            edge_reason = _edge_reason(adj, node_id, pred.get(node_id))
            if edge_reason:
                reasons.append(edge_reason)
            if _is_test_node(node_id):
                reasons.append("test file references target symbol")

        final = base + q_score + capped_boost

        # Utility-hub suppression: a generic/high-degree hub with no direct
        # query match must not outrank a direct target.
        degree = in_deg.get(node_id, 0) + out_deg.get(node_id, 0)
        is_hub = degree >= _HUB_DEGREE or bool(_UTILITY_NAME_RE.search(node_id))
        if is_hub and q_score == 0.0 and node_id not in seed_reason:
            if final > _HUB_FINAL_CAP:
                final = _HUB_FINAL_CAP
                reasons.append("utility hub suppressed (no direct query match)")

        scores.append(
            SpreadScore(
                node_id=node_id,
                base_score=round(base, 6),
                query_score=q_score,
                spread_boost=round(capped_boost, 6),
                final_score=round(final, 6),
                reasons=reasons,
                seed_nodes=sorted(reach_seeds.get(node_id, [])),
                distance=dist,
            )
        )

    scores.sort(key=lambda s: (-s.final_score, s.node_id))
    return scores


def _degree(graph: ProgramGraph, *, source: bool) -> dict[str, int]:
    counts: dict[str, int] = {nid: 0 for nid in graph.nodes}
    for edge in graph.edges:
        key = edge.source if source else edge.target
        if key in counts:
            counts[key] += 1
    return counts


def assess_change_scope(
    spread_scores: list[SpreadScore],
    graph: ProgramGraph | None = None,
    target_node: str | None = None,
) -> ChangeScopeAssessment:
    """Classify the likely patch scope from spread evidence.

    Priority (most to least risky):
      api_contract_risk  - tests/docs/exports/types/interfaces reference the
                           target: behavior is part of an expected contract.
      cross_file_impact  - callers/importers in *other* files depend on it.
      scope_uncertain    - bounded neighbors exist (e.g. a same-file caller)
                           but no clear external contract.
      local_safe         - target is local with no callers/tests/API hints.
    """
    by_id = {s.node_id: s for s in spread_scores}

    # Determine the target + its file.
    if target_node is None:
        seeds0 = [s for s in spread_scores if s.distance == 0 and s.query_score > 0]
        target_node = seeds0[0].node_id if seeds0 else (
            spread_scores[0].node_id if spread_scores else ""
        )
    target_file = _file_of(target_node)

    reasons: list[str] = []
    evidence: list[str] = []
    contract = False
    cross_file = False
    same_file_caller = False

    # Prefer precise edge inspection when the graph is available.
    if graph is not None and target_node in graph.nodes:
        for edge in graph.edges:
            if edge.target != target_node or edge.source == edge.target:
                continue
            src = edge.source
            etype = (edge.type or "").lower()
            # Only relationships where the source depends on the target.
            if etype in {"contains", "contain", "defines"} and _file_of(src) == target_file:
                continue  # the declaring file, not a caller
            evidence.append(src)
            if _is_test_node(src) or _is_contract_node(src, _node_type(graph, src)):
                contract = True
                reasons.append(f"contract/test reference from {src}")
            elif _file_of(src) != target_file:
                cross_file = True
                reasons.append(f"cross-file caller/importer {src}")
            else:
                same_file_caller = True
                reasons.append(f"same-file caller {src}")
    else:
        # Fall back to spread evidence only.
        for s in spread_scores:
            if s.node_id == target_node or s.distance in (None, 0):
                continue
            if s.spread_boost <= 0:
                continue
            evidence.append(s.node_id)
            if _is_test_node(s.node_id) or any("test" in r.lower() for r in s.reasons):
                contract = True
                reasons.append(f"contract/test reference from {s.node_id}")
            elif _file_of(s.node_id) != target_file:
                cross_file = True
                reasons.append(f"cross-file neighbor {s.node_id}")
            else:
                same_file_caller = True
                reasons.append(f"same-file neighbor {s.node_id}")

    evidence = sorted(set(evidence))

    if contract:
        scope = "api_contract_risk"
    elif cross_file:
        scope = "cross_file_impact"
    elif same_file_caller:
        scope = "scope_uncertain"
    else:
        scope = "local_safe"
        reasons.append("no external callers, tests, or API references found")

    return ChangeScopeAssessment(scope=scope, reasons=reasons, evidence_nodes=evidence)


def _node_type(graph: ProgramGraph, node_id: str) -> str:
    node = graph.nodes.get(node_id)
    return node.type if node else ""


def format_spread_explanation(spread_scores: list[SpreadScore], limit: int = 10) -> str:
    """Human-readable, inspectable explanation of the top spread scores."""
    lines = ["Scope-aware evidence spread (top results):"]
    for s in spread_scores[: max(0, limit)]:
        reason = "; ".join(s.reasons) if s.reasons else "base weight only"
        dist = "seed" if s.distance == 0 else (
            f"d{s.distance}" if s.distance is not None else "-"
        )
        lines.append(
            f"- {s.node_id} [{dist}] "
            f"final={s.final_score} (base={s.base_score}, "
            f"query={s.query_score}, spread={s.spread_boost}) :: {reason}"
        )
    return "\n".join(lines)
