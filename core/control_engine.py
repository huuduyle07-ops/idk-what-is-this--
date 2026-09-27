from __future__ import annotations
from pathlib import Path
import re
import os
import json
import hashlib
from typing import Any

from graph.builder import build_graph_from_repo
from graph.project_map import load_project_map
from graph.query import explain_symbol, impact_analysis
from graph.weights import NodeWeight, compute_node_weights, get_node_weight
from reasoning.deep_project_understand import (
    deep_project_understand,
)
from reasoning.reasoning_engine import analyze_symbol_risk
from core.retriever import trace_execution_flow
from core.treesitter_parse import structural_definitions
from core.localization_candidate import (
    LocalizationVerdict,
    iter_graph_verdicts,
    localization_population_metrics,
)
from core.identifier_recall import (
    IdentifierEntryMatch,
    resolve_identifier_candidates,
    resolve_identifier_recall,
)
from core.localization_relevance import (
    describe_relevance,
    mark_localization_order,
    verify_entry_paths,
)
from core.localization_handoff import current_target_receipt
from core.authoritative_binding_context import load_authoritative_binding_context
from core.candidate_authoring_context import CandidateAuthoringContext
from core.authoring_repair_scope import (
    AuthoringScopeError, consume_repair_scope, enforce_authoring_scope,
)
from core.repair_scope import (
    REPAIR_SCOPE_COMPLETE,
    REPAIR_SCOPE_NOT_APPLICABLE,
    build_repair_scope,
    render_repair_scope_prompt,
)
from core.patch_authoring_contract import (
    PatchAuthoringContract,
    patch_output_format_block,
    render_patch_authoring_contract,
    safe_minimal_forbidden_block,
)
from core.repo_librarian import load_phantom_limb_report
from core.validation_outcome import is_executed_failure_evidence
from core.defect_probe import (
    attach_control_probe_telemetry,
    attach_defect_probe_receipt,
    build_control_probe_telemetry,
    carried_behavior_facts,
    execute_resolved_control_defect_probe,
    resolve_control_defect_probe,
    reproduced_probe_target,
)
from core.patch_basis import (
    FAILURE_BINDING_AMBIGUOUS,
    FAILURE_BINDING_BOUNDED_REPRODUCTION,
    FAILURE_BINDING_EXPLICIT_CHANGE_REQUEST,
    FAILURE_BINDING_UNAVAILABLE,
    PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
    PATCH_BASIS_GROUNDED_DEFECT,
    PATCH_BASIS_NONE,
    PATCH_BASIS_SOURCE_BOUNDED_REPRODUCTION,
    PATCH_BASIS_SOURCE_EXECUTED_FAILURE,
    PATCH_BASIS_SOURCE_EXPLICIT_REQUEST,
    PATCH_BASIS_SOURCE_UNAVAILABLE,
    PATCH_BASIS_UNRESOLVED,
    FailureRelevanceBinding,
    LocalizedCandidate,
    bind_executed_failure_to_candidates,
    explicit_change_scope_tokens,
    explicit_change_targets_match_scope,
    has_legitimate_patch_basis,
    normalize_patch_basis,
)
from core.live_task_routing import (
    CHANGE_NEED_GROUNDED_DEFECT,
    route_change_need_source,
    route_is_explicit_change,
    route_is_read_only,
)
from core.context_profiles import (
    identity_answer_framing,
    identity_prompt_hint,
    infer_context_profile,
    score_multiplier_for_path,
)
from config import LANGUAGE_MAP
from policy.decision_helper import build_patch_policy, policy_to_prompt_block

_graph_cache: dict[str, Any] = {}

LOCALIZATION_CONFIDENCE_KIND = "localization_rank_legacy"
LOCALIZATION_SCORE_SEMANTICS = (
    "relative navigation heuristic; non-probabilistic and non-authoritative"
)


def localization_strength(value: float) -> str:
    """Human-friendly navigation strength, never defect likelihood."""
    if value >= 0.75:
        return "strong"
    if value >= 0.4:
        return "moderate"
    return "weak"


def localization_value(hypothesis: dict | None) -> float:
    """Read new and historical CONTROL localization artifacts safely.

    Historical artifacts exposed only ``confidence``.  That field is retained
    as a deprecated localization-rank alias; this reader must never be used as
    defect certainty or patch authority.
    """
    if not isinstance(hypothesis, dict):
        return 0.0
    for key in ("localization_strength_value", "confidence"):
        try:
            return max(0.0, min(1.0, float(hypothesis.get(key, 0.0) or 0.0)))
        except (TypeError, ValueError):
            continue
    return 0.0


def infer_language_from_file(rel_file: str | None) -> str:
    if not rel_file:
        return "unknown"
    return LANGUAGE_MAP.get(Path(rel_file).suffix.lower(), "unknown")

def get_cached_graph(repo_path: str, *, inventory=None):
    repo_abs = os.path.abspath(repo_path)
    if inventory is not None:
        from core.repository_inventory import (
            validate_repository_inventory,
        )

        validate_repository_inventory(repo_abs, inventory)
        # Inventory-backed calls are operation-scoped and must not consume a
        # graph cached from an earlier repository snapshot or publish their
        # request-local graph into the legacy process cache.
        return build_graph_from_repo(
            repo_abs,
            inventory=inventory,
        )
    if repo_abs not in _graph_cache:
        _graph_cache[repo_abs] = build_graph_from_repo(
            repo_abs,
            inventory=inventory,
        )
    return _graph_cache[repo_abs]

def clear_graph_cache(repo_path: str | None = None) -> None:
    """Clear the CONTROL graph cache *and* every other module-level graph cache.

    Phase 13.1 (Graph Cache Invalidation Unification): CLI and web call this
    helper believing it invalidates all graph caches before a re-analysis.
    Historically it cleared only this module's ``_graph_cache``, leaving the
    retriever, semantic-graph pipeline, and deep-project-understand caches free
    to serve a stale graph. We now fan out to each of those caches so a re-index
    never leaves a stale graph behind any consumer. Imports are function-local
    to avoid any import cycle at module load.
    """
    if repo_path is None:
        _graph_cache.clear()
    else:
        repo_abs = os.path.abspath(repo_path)
        _graph_cache.pop(repo_abs, None)

    from core.retriever import clear_graph_cache as _clear_retriever_graph_cache
    from core.semantic_graph_pipeline import (
        clear_graph_cache as _clear_semantic_graph_cache,
    )
    from reasoning.deep_project_understand import (
        clear_graph_cache as _clear_deep_graph_cache,
    )

    _clear_retriever_graph_cache(repo_path)
    _clear_semantic_graph_cache(repo_path)
    _clear_deep_graph_cache(repo_path)

def extract_hotspots_from_project_map(project_map: str, limit: int = 10) -> list[str]:
    result: list[str] = []
    capture = False

    for line in project_map.splitlines():
        stripped = line.strip()

        if stripped.startswith("## Dynamic Hotspots") or stripped.startswith("## Critical Symbols"):
            capture = True
            continue

        if capture and stripped.startswith("## "):
            break

        if capture and stripped.startswith("- "):
            node = stripped[2:].split(" (score=")[0].strip()
            if node and node not in result:
                result.append(node)

    return result[:limit]

def called_names_from_snippet(snippet: str) -> set[str]:
    # JS/C#/Go-ish: object.method(...)
    names = set(re.findall(r"\.\s*([A-Za-z_][A-Za-z_0-9]*)\s*\(", snippet or ""))
    # plain call: Move(...)
    names |= set(re.findall(r"\b([A-Za-z_][A-Za-z_0-9]*)\s*\(", snippet or ""))
    return {n for n in names if n not in {"if", "for", "while", "switch", "return"}}

def build_related_snippets(
    control_result: dict,
    repo_path: str,
    *,
    graph=None,
    inventory=None,
) -> list[dict]:
    patch = control_result.get("patch_intent") or {}
    evidence = control_result.get("evidence") or []
    source_snippet = patch.get("source_snippet") or ""

    target_symbol = patch.get("target_symbol_full") or patch.get("target_node_name")
    call_names = called_names_from_snippet(source_snippet)

    related = []
    seen = set()

    # 0. Preflight-guided snippets first: stack trace / compiler locations
    preflight = control_result.get("preflight_validation") or {}
    locations = preflight.get("locations") or []

    for loc in locations:
        if len(related) >= 4:
            break

        rel_file = loc.get("file")
        line = loc.get("line")
        if not rel_file:
            continue

        symbol_name = symbol_name_from_location(loc)
        snippet = ""

        if symbol_name:
            snippet = extract_symbol_snippet(repo_path, rel_file, symbol_name)

        if not snippet and line:
            snippet = extract_line_window(repo_path, rel_file, int(line), radius=4)

        key = (rel_file, symbol_name, line)
        if snippet and key not in seen:
            related.append({
                "role": "preflight_location",
                "symbol": symbol_name or "",
                "file": rel_file,
                "line": line,
                "snippet": snippet,
            })
            seen.add(key)

    # 1. Search nearby graph evidence first
    for item in evidence:
        symbol = item.get("symbol")
        if not symbol or symbol == target_symbol:
            continue
        if "::expr::" in symbol or symbol.startswith("call::"):
            continue

        tail = symbol.split("::")[-1]
        should_include = (
            tail in call_names
            or any(c.endswith("::" + tail) or c == tail for c in item.get("calls", []))
            or any(c.endswith("::" + tail) or c == tail for c in item.get("called_by", []))
        )

        if not should_include:
            continue

        rel_file = infer_file_from_symbol(symbol)
        symbol_name = infer_name_from_symbol(symbol)

        if not rel_file or not symbol_name:
            continue

        snippet = extract_symbol_snippet(repo_path, rel_file, symbol_name)

        if snippet and symbol not in seen:
            related.append({
                "role": "callee_or_neighbor",
                "symbol": symbol,
                "file": rel_file,
                "snippet": snippet,
            })
            seen.add(symbol)

        if len(related) >= 4:
            break

    # 2. Fallback: search whole graph by called function names
    graph = graph or get_cached_graph(
        repo_path,
        inventory=inventory,
    )

    for node_id in graph.nodes.keys():
        if len(related) >= 4:
            break
        if node_id in seen:
            continue
        if node_id.startswith("call::") or "::expr::" in node_id:
            continue
        if "::" not in node_id:
            continue

        tail = node_id.split("::")[-1]
        if tail not in call_names:
            continue

        rel_file = infer_file_from_symbol(node_id)
        symbol_name = infer_name_from_symbol(node_id)

        if not rel_file or not symbol_name:
            continue

        snippet = extract_symbol_snippet(repo_path, rel_file, symbol_name)

        if snippet:
            related.append({
                "role": "callee_by_name",
                "symbol": node_id,
                "file": rel_file,
                "snippet": snippet,
            })
            seen.add(node_id)

    print("🐛 DEBUG related snippets:", [
        {
            "symbol": r.get("symbol"),
            "file": r.get("file"),
            "role": r.get("role"),
        }
        for r in related
    ])

    return related[:4]

def select_entry_nodes(
    query: str,
    repo_path: str,
    limit: int = 6,
    *,
    graph=None,
    inventory=None,
    return_details: bool = False,
) -> list[str] | dict[str, Any]:
    graph = graph or get_cached_graph(
        repo_path,
        inventory=inventory,
    )
    print("🐛 DEBUG graph node count:", len(graph.nodes))
    print("🐛 DEBUG first graph nodes:", list(graph.nodes.keys())[:20])
    print("🐛 DEBUG query words:", query_words(query))
    print(
        "🐛 DEBUG candidate population:",
        localization_population_metrics(graph),
    )

    eligible = eligible_localization_nodes(graph)

    # RETRIEVE.LIVE.3.  Production passes the raw query directly to the one
    # canonical identifier-recall primitive.  Extraction, normalization,
    # bounded morphology, matching, ordering and the cap therefore cannot drift
    # between focused fixtures and CONTROL.
    query_recall = resolve_identifier_recall(
        query,
        eligible,
        entry_limit=limit,
    )
    query_matches = list(query_recall.matches)
    result: list[str] = [match.node_id for match in query_matches]
    deep_entry_nodes: list[str] = []
    project_map_entry_nodes: list[str] = []

    # Preserve the established deep/project-map sources as bounded supplements
    # (or fallback when lexical resolution found nothing).  A full query-derived
    # set needs neither, avoiding query-independent hotspot work on that path.
    graph_nodes: list[str] = []
    map_nodes: list[str] = []
    if len(result) < limit:
        understanding = deep_project_understand(
            query,
            repo_path,
            graph=graph,
            inventory=inventory,
        )
        graph_nodes = [
            f["symbol"]
            for f in understanding.get("findings", [])
            if f.get("symbol")
        ]
        project_map = load_project_map(repo_path)
        map_nodes = extract_hotspots_from_project_map(project_map, limit=limit)

    for raw in graph_nodes + map_nodes:
        if len(result) >= limit:
            break
        resolved_nodes = resolve_symbol_to_graph_nodes(graph, raw, query=query, limit=3)

        # The direct-hit shortcut goes through the same boundary: a project-map
        # hotspot naming a bookkeeping node is still not a candidate.
        if not resolved_nodes and raw in eligible:
            resolved_nodes = [raw]

        for node in resolved_nodes:
            if node not in result:
                result.append(node)
                if raw in graph_nodes:
                    deep_entry_nodes.append(node)
                else:
                    project_map_entry_nodes.append(node)
                if len(result) >= limit:
                    break

    graph_fallback_nodes: list[str] = []
    if not result:
        for node in fallback_entry_nodes_from_graph(graph, query, limit=limit):
            if node not in result:
                result.append(node)
                graph_fallback_nodes.append(node)

    print("🐛 DEBUG entry_nodes:", result)

    entry_nodes = result[:limit]
    if not return_details:
        return entry_nodes

    query_entry_nodes = [match.node_id for match in query_matches]
    project_map_fallback_used = not query_entry_nodes and bool(project_map_entry_nodes)
    fallback_used = not query_entry_nodes and bool(entry_nodes)
    details = {
        "entry_nodes": entry_nodes,
        **query_recall.as_debug_dict(),
        # RETRIEVE.LIVE.2 compatibility aliases.
        "query_candidates": list(query_recall.raw_query_terms),
        "query_derived_entry_nodes": query_entry_nodes,
        "query_matches": [match.as_dict() for match in query_matches],
        "deep_graph_entry_nodes": deep_entry_nodes,
        "project_map_entry_nodes": project_map_entry_nodes,
        "graph_fallback_entry_nodes": graph_fallback_nodes,
        "project_map_fallback_used": project_map_fallback_used,
        "project_map_supplemented": bool(query_entry_nodes and project_map_entry_nodes),
        "graph_fallback_used": bool(graph_fallback_nodes),
        "fallback_used": fallback_used,
        "hotspot_only": bool(entry_nodes) and not bool(query_entry_nodes),
        "entry_candidate_count": len(entry_nodes),
        "entry_candidate_limit": limit,
    }
    return details

#: Attribute the eligible-node view is memoised under, so one CONTROL
#: operation classifies a graph once instead of once per resolved symbol.
_ELIGIBILITY_CACHE_ATTR = "_localization_eligibility_view"


def eligible_localization_nodes(graph) -> dict[str, LocalizationVerdict]:
    """The subset of ``graph`` allowed to enter localization competition.

    RETRIEVE.LIVE.1.  This replaces the ad-hoc ``call::`` / ``::expr::`` /
    "must contain ``::``" string sniffing that used to guard these two
    enumerators.  Same intent, but the decision now comes from node kind and
    source binding rather than from a prefix, so a malformed parser fragment
    or a bookkeeping node cannot slip in by having a plausible-looking id.

    Nothing is deleted: ``graph.nodes`` and ``graph.edges`` are untouched and
    every rejected node keeps its edges and its place in dependency analysis.
    The returned mapping preserves graph insertion order.
    """
    nodes = getattr(graph, "nodes", None) or {}
    cached = getattr(graph, _ELIGIBILITY_CACHE_ATTR, None)
    if isinstance(cached, tuple) and len(cached) == 2 and cached[0] == len(nodes):
        return cached[1]

    view = {
        verdict.node_id: verdict
        for verdict in iter_graph_verdicts(graph)
        if verdict.eligible
    }
    try:
        setattr(graph, _ELIGIBILITY_CACHE_ATTR, (len(nodes), view))
    except Exception:
        # A graph stand-in that rejects attributes still works, just uncached.
        pass
    return view


def query_words(query: str) -> set[str]:
    return {
        w.lower()
        for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", query)
        if len(w) >= 3
    }

def relevance_bonus(symbol: str, words: set[str]) -> float:
    tokens = {
        w.lower()
        for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", symbol)
        if len(w) >= 3
    }
    return sum(1 for w in words if w in tokens)


def score_control_node(item: dict) -> float:
    risk = item.get("risk", {})
    risk_level = risk.get("risk_level", "low")
    risk_score = risk.get("risk_score", 0)

    level_bonus = {
        "high": 5,
        "medium": 3,
        "low": 1,
    }.get(risk_level, 0)

    return (
        len(item.get("called_by", [])) * 2
        + len(item.get("calls", []))
        + len(item.get("impact", [])) * 2
        + risk_score
        + level_bonus
        + item.get("query_bonus", 0) * 2
        + item.get("graph_weight", 0)
        - item.get("depth", 0) * 0.5
    )


def control_dfs_v2(
    graph,
    entry_nodes: list[str],
    query: str = "",
    max_depth: int = 2,
    max_nodes: int = 20,
    neighbor_limit: int = 3,
    node_metrics: dict[str, NodeWeight] | None = None,
    repo_path: str | None = None,
) -> list[dict]:
    visited = set()
    evidence: list[dict] = []
    words = query_words(query)
    metrics = (
        node_metrics
        if node_metrics is not None
        else compute_node_weights(graph, repo_path=repo_path)
    )
    # RETRIEVE.LIVE.1.  Entry nodes already came through the eligibility
    # boundary, but neighbour expansion reaches whatever the graph connects -
    # including bookkeeping aggregates such as ``app.py::<top-level>``.  A
    # node that is not a localization candidate must not become one by being
    # adjacent to one.
    eligible = eligible_localization_nodes(graph)

    def dfs(symbol: str, depth: int, origin: str, trail: list[dict]):
        if depth > max_depth:
            return
        if symbol in visited:
            return
        if len(evidence) >= max_nodes:
            return
        # Preserve space for the bounded entries even when an early hub fills
        # the expansion budget. Neither the entry cap nor DFS bounds change.
        pending_entries = sum(node not in visited for node in entry_nodes)
        if symbol not in entry_nodes and len(evidence) >= max_nodes - pending_entries:
            return

        visited.add(symbol)

        info = explain_symbol(graph, symbol)

        # Traversal continues through an ineligible node either way: the
        # relation it carries is still real, so connectivity is preserved and
        # only its own candidacy is refused.
        if symbol in eligible or symbol not in graph.nodes:
            impact = impact_analysis(graph, symbol)
            risk = analyze_symbol_risk(graph, symbol)

            item = {
                "symbol": symbol,
                "depth": depth,
                "called_by": info.get("called_by", []),
                "calls": info.get("calls", []),
                "impact": impact,
                "risk": risk,
                "query_bonus": relevance_bonus(symbol, words),
                "graph_weight": get_node_weight(metrics, symbol),
                "originating_entry": origin,
                "entry_path": trail,
            }
            item["score"] = score_control_node(item)
            evidence.append(item)

        neighbors = []
        neighbors.extend(info.get("called_by", []))
        neighbors.extend(info.get("calls", []))

        ranked_neighbors = sorted(
            set(neighbors),
            key=lambda n: (
                -(relevance_bonus(n, words) * 2 + get_node_weight(metrics, n)),
                n,
            ),
        )[:neighbor_limit]

        for n in ranked_neighbors:
            dfs(n, depth + 1, origin, trail + [{
                "from": symbol,
                "to": n,
                "edge_kind": "resolved_call",
                "direction": "upstream" if n in info.get("called_by", []) else "downstream",
            }])

    for node in entry_nodes:
        dfs(node, 0, node, [])

    verify_entry_paths(graph, evidence)
    evidence.sort(key=lambda x: x.get("score", 0), reverse=True)
    return evidence[:max_nodes]

def caller_query_bonus(query: str, symbol: str, item: dict) -> float:
    q = query.lower()
    tail = symbol.split("::")[-1].lower()

    if not any(k in q for k in ["call", "calls", "argument", "arguments", "parameter", "parameters"]):
        return 0.0

    bonus = 0.0

    # Caller-like functions should win for call/argument tasks.
    if tail in {"update", "start", "main", "run"}:
        bonus += 6.0

    # Symbols that call something are more relevant than symbols only called by others.
    if item.get("calls"):
        bonus += 4.0

    # Exact query mentions Game.Update.
    if "game" in q and "update" in q and "update" == tail:
        bonus += 5.0

    return bonus

def infer_hypotheses(
    query: str, evidence: list[dict], execution_trace: str,
    *, entry_resolution: dict | None = None,
    failure_binding: FailureRelevanceBinding | None = None,
) -> list[dict]:
    hypotheses = []
    trace_lower = execution_trace.lower()

    # Gate the whole existing bounded candidate set before truncation. Taking
    # the eight largest graph scores first discarded query-derived evidence.
    for item in evidence[:20]:
        symbol = item["symbol"]
        risk = item.get("risk", {})
        score = item.get("score", 0)
        score += caller_query_bonus(query, symbol, item)
        reasons = []

        if item.get("query_bonus", 0) > 0:
            reasons.append("symbol/query name overlap")

        if item.get("called_by"):
            reasons.append("has upstream callers")

        if item.get("calls"):
            reasons.append("has downstream callees")

        if risk.get("risk_level") in {"medium", "high"}:
            reasons.append(f"graph risk is {risk.get('risk_level')}")

        symbol_tail = symbol.split("::")[-1].lower()
        if symbol_tail and symbol_tail in trace_lower:
            reasons.append("appears in execution/state trace")
            score += 3

        if "overwritten before being used" in trace_lower:
            reasons.append("state trace reports overwritten assignment")
            score += 4

        if "return value differs across execution paths" in trace_lower:
            reasons.append("state trace reports return conflict")
            score += 4

        if "stale" in query.lower() and "stale" in trace_lower:
            reasons.append("trace contains stale-state signal")
            score += 3

        # Compatibility-only presentation value.  This normalization was
        # historically called confidence, but it is derived entirely from
        # navigation heuristics and therefore is not a defect probability.
        legacy_localization_value = min(0.95, max(0.1, score / 25))
        if not reasons:
            legacy_localization_value *= 0.5

        if item.get("depth", 0) > 1:
            legacy_localization_value *= 0.9

        raw_localization_score = round(score, 2)
        normalized_localization_value = round(legacy_localization_value, 2)

        relevance = describe_relevance(
            query, item, entry_resolution or {}, failure_binding=failure_binding,
        )
        reasons.insert(0, relevance["anchor_relation"])
        hypotheses.append({
            "symbol": symbol,
            **relevance,
            # ``score`` and ``confidence`` remain readable for historical
            # artifacts.  The explicit fields below define their new contract.
            "score": raw_localization_score,
            "localization_score": raw_localization_score,
            "localization_strength_value": normalized_localization_value,
            "localization_strength": localization_strength(
                normalized_localization_value
            ),
            "localization_score_semantics": LOCALIZATION_SCORE_SEMANTICS,
            "confidence": normalized_localization_value,
            "confidence_kind": LOCALIZATION_CONFIDENCE_KIND,
            "legacy_control_confidence_deprecated": True,
            "likely_issue": guess_issue_type(query, execution_trace),
            "reasons": reasons,
            "localization_reasons": list(reasons),
            "evidence_classification": {
                "navigation": list(reasons),
                "defect_grounding": [],
            },
            "defect_established": False,
            "defect_grounding": [],
            "recommended_action": "inspect_candidate",
            "needs_escalation": True,
            "language": infer_language_from_file(infer_file_from_symbol(symbol)),
        })

    mark_localization_order(hypotheses)
    by_symbol = {item["symbol"]: item for item in hypotheses}
    for item in evidence[:20]:
        item["localization"] = by_symbol[item["symbol"]]
    return hypotheses[:5]


def guess_issue_type(query: str, execution_trace: str) -> str:
    q = query.lower()
    t = execution_trace.lower()

    if "overwritten before being used" in t:
        return "state_overwrite"
    if "return value differs across execution paths" in t:
        return "return_conflict"
    if "stale" in q or "stale" in t:
        return "stale_state"
    if "validation failed" in t or "failed" in q:
        return "validation_failure"
    if "import" in q:
        return "import_or_dependency_issue"

    return "unknown_logic_issue"


def build_control_result(
    query: str,
    repo_path: str,
    entry_nodes: list[str],
    evidence: list[dict],
    execution_trace: str,
    entry_resolution: dict[str, Any] | None = None,
) -> dict:
    context_profile = infer_context_profile(query)
    hypotheses = infer_hypotheses(
        query, evidence, execution_trace, entry_resolution=entry_resolution,
    )
    top = hypotheses[0] if hypotheses else None
    phantom_limb = load_phantom_limb_report(repo_path)
    print("🐛 DEBUG top hypothesis:", top)
    control_rules = [
        "Use PROJECT_MAP only as navigation, not truth.",
        "Prefer graph evidence before patching.",
        "Prefer AST-based patching when possible.",
        "If evidence is weak, do not auto-patch.",
        "If graph/project_map/code disagree, trust code and graph first.",
    ]
    hint = identity_prompt_hint(query)
    if hint:
        control_rules.insert(0, hint)
        control_rules.insert(1, identity_answer_framing(profile=context_profile))

    result = {
        "version": "control_v5",
        "query": query,
        "repo_path": repo_path,
        "context_profile": context_profile,
        "entry_nodes": entry_nodes,
        "entry_resolution": entry_resolution or {},
        "localization_candidates": [
            item["localization"] for item in evidence[:20] if "localization" in item
        ],
        "top_hypothesis": top,
        "hypotheses": hypotheses,
        "evidence": evidence[:12],
        "execution_trace": execution_trace[:4000] if execution_trace else "",
        "phantom_limb": phantom_limb,
        "control_rules": control_rules,
        "decision": {
            "symbol": top["symbol"] if top else None,
            "action": top["recommended_action"] if top else None,
        },
    }

    result["patch_intent"] = build_patch_intent(result)
    result["related_snippets"] = []
    refresh_control_safety(result)
    result["localization_handoff"] = current_target_receipt(result)
    return result


def _normalized_control_path(value: str | None) -> str:
    return str(value or "").strip().replace("\\", "/").lstrip("./").lower()


def _validation_binding(preflight: dict, relative_file: str) -> dict | None:
    """Bind an executed validation failure to one already-ranked file.

    This performs no search or traversal.  Typed preflight locations win; the
    bounded fallback accepts an exact candidate path already printed by the
    executed validation output (needed for Python tracebacks, whose legacy
    location extractor does not currently project frames into ``locations``).
    """
    wanted = _normalized_control_path(relative_file)
    if not wanted:
        return None

    for location in preflight.get("locations") or []:
        if not isinstance(location, dict):
            continue
        if _normalized_control_path(location.get("file")) == wanted:
            return {
                "binding": "preflight_location",
                "priority": 0,
                "file": relative_file,
                "line": location.get("line"),
                "col": location.get("col"),
                "location_kind": location.get("kind"),
            }

    normalized_output = str(preflight.get("output") or "").replace("\\", "/").lower()
    path_pattern = rf"(?<![a-z0-9_.-]){re.escape(wanted)}(?=[:\s\"'()])"
    if re.search(path_pattern, normalized_output):
        return {
            "binding": "executed_failure_output_path",
            "priority": 1,
            "file": relative_file,
            "line": None,
            "col": None,
            "location_kind": "validation_output_path",
        }
    return None


def _source_is_exactly_grounded(control_result: dict, patch_intent: dict) -> bool:
    repo_path = control_result.get("repo_path")
    rel = (
        patch_intent.get("relative_path")
        or patch_intent.get("file")
        or patch_intent.get("target_file")
    )
    source = patch_intent.get("source_snippet")
    if not repo_path or not rel or not isinstance(source, str) or not source:
        return False
    try:
        repo = Path(repo_path).resolve()
        target = (repo / rel).resolve()
        target.relative_to(repo)
        return target.is_file() and source in target.read_text(
            encoding="utf-8", errors="replace"
        )
    except (OSError, ValueError):
        return False


def _ensure_localization_metadata(hypothesis: dict, rank: int) -> None:
    previous_action = hypothesis.get("recommended_action")
    if (
        previous_action
        and previous_action
        not in {
            "inspect_candidate",
            "acquire_source_context",
            "grounded_defect_candidate",
            "needs_grounding",
            "insufficient_patch_evidence",
        }
        and "legacy_recommended_action" not in hypothesis
    ):
        hypothesis["legacy_recommended_action"] = previous_action

    raw_score = hypothesis.get("localization_score", hypothesis.get("score", 0.0))
    try:
        raw_score = float(raw_score or 0.0)
    except (TypeError, ValueError):
        raw_score = 0.0
    normalized = localization_value(hypothesis)
    reasons = hypothesis.get("localization_reasons", hypothesis.get("reasons", []))
    reasons = list(reasons) if isinstance(reasons, list) else [str(reasons)]

    hypothesis.update(
        {
            "localization_score": round(raw_score, 2),
            "localization_rank": rank,
            "localization_strength_value": normalized,
            "localization_strength": localization_strength(normalized),
            "localization_score_semantics": LOCALIZATION_SCORE_SEMANTICS,
            "localization_reasons": reasons,
            "confidence_kind": LOCALIZATION_CONFIDENCE_KIND,
            "legacy_control_confidence_deprecated": True,
            "defect_established": False,
            "defect_grounding": [],
            "evidence_classification": {
                "navigation": reasons,
                "defect_grounding": [],
            },
            "recommended_action": "inspect_candidate",
            "needs_escalation": True,
        }
    )


def refresh_control_safety(control_result: dict) -> dict:
    """Separate localization, typed patch basis, target grounding and authority.

    Ranking remains unchanged and grants nothing.  A defect basis requires a
    genuine executed failure with a deterministic direct-location or bounded
    executed-reference binding, or a provenance-valid bounded reproduced
    probe, and acquired exact candidate source.  An
    explicit-change basis comes only from WAITER.LIVE.1's preserved route
    receipt and never fabricates a defect.  Neither basis grants write/apply
    authority; target grounding and the existing safety/authorization stack
    remain separate downstream questions.
    """
    if not isinstance(control_result, dict):
        return control_result

    previous_candidate_state = control_result.get("patch_candidate_state")
    previous_candidate_state = (
        dict(previous_candidate_state)
        if isinstance(previous_candidate_state, dict)
        else {}
    )

    hypotheses = control_result.get("hypotheses")
    if not isinstance(hypotheses, list):
        hypotheses = []
        control_result["hypotheses"] = hypotheses
    top = control_result.get("top_hypothesis")
    top_symbol = top.get("symbol") if isinstance(top, dict) else None
    top_is_represented = any(
        item is top
        or (
            isinstance(item, dict)
            and top_symbol
            and item.get("symbol") == top_symbol
        )
        for item in hypotheses
    )
    if isinstance(top, dict) and not top_is_represented:
        hypotheses.insert(0, top)

    for rank, hypothesis in enumerate(hypotheses, start=1):
        if isinstance(hypothesis, dict):
            _ensure_localization_metadata(hypothesis, rank)

    top = hypotheses[0] if hypotheses else (top if isinstance(top, dict) else None)
    control_result["top_hypothesis"] = top

    preflight = control_result.get("preflight_validation") or {}
    route = control_result.get("live_route")
    explicit_change_requested = route_is_explicit_change(route)
    genuine_failure = bool(
        isinstance(preflight, dict)
        and preflight.get("ran")
        and preflight.get("ok") is False
        and is_executed_failure_evidence(preflight.get("category"))
    )

    grounded_hypothesis = None
    defect_evidence: list[dict] = []
    exact_source_grounded = False
    probe_target = (
        None
        if explicit_change_requested
        else reproduced_probe_target(control_result.get("defect_probe"))
    )
    grounding_source = ""
    patch_intent = control_result.get("patch_intent")
    if not isinstance(patch_intent, dict):
        patch_intent = build_patch_intent(control_result)

    binding = FailureRelevanceBinding()
    candidate_descriptors: list[LocalizedCandidate] = []
    if genuine_failure and not explicit_change_requested:
        for rank, hypothesis in enumerate(hypotheses, start=1):
            if not isinstance(hypothesis, dict):
                continue
            symbol = str(hypothesis.get("symbol") or "")
            rel_file = infer_file_from_symbol(symbol) or ""
            symbol_name = infer_name_from_symbol(symbol) or ""
            if rel_file and symbol_name:
                candidate_descriptors.append(
                    LocalizedCandidate(
                        file=rel_file,
                        symbol=symbol_name,
                        rank=rank,
                    )
                )
        binding = bind_executed_failure_to_candidates(
            repo_path=control_result.get("repo_path") or "",
            preflight=preflight,
            candidates=candidate_descriptors,
        )

    if probe_target is not None and not genuine_failure:
        wanted_file = _normalized_control_path(probe_target.get("file"))
        wanted_symbol = str(probe_target.get("symbol") or "")
        for hypothesis in hypotheses:
            if not isinstance(hypothesis, dict):
                continue
            symbol = str(hypothesis.get("symbol") or "")
            if (
                _normalized_control_path(infer_file_from_symbol(symbol)) == wanted_file
                and infer_name_from_symbol(symbol) == wanted_symbol
            ):
                grounded_hypothesis = hypothesis
                grounding_source = "bounded_reproduction"
                break

    if binding.bound:
        wanted_file = _normalized_control_path(binding.candidate_file)
        wanted_symbol = binding.candidate_symbol
        for hypothesis in hypotheses:
            if not isinstance(hypothesis, dict):
                continue
            symbol = str(hypothesis.get("symbol") or "")
            if (
                _normalized_control_path(infer_file_from_symbol(symbol)) == wanted_file
                and infer_name_from_symbol(symbol) == wanted_symbol
            ):
                grounded_hypothesis = hypothesis
                grounding_source = "executed_validation_failure"
                break

    if grounded_hypothesis is not None:
        patch_intent = build_patch_intent(
            control_result,
            hypothesis=grounded_hypothesis,
            defect_location=(
                binding.location.as_dict() if binding.location is not None else None
            ),
        )
        exact_source_grounded = _source_is_exactly_grounded(control_result, patch_intent)
        if grounding_source == "bounded_reproduction":
            probe = control_result.get("defect_probe") or {}
            defect_evidence = [
                {
                    "kind": "bounded_defect_reproduction",
                    "probe_basis": probe.get("probe_basis"),
                    "input_basis": probe.get("input_basis"),
                    "expected_behavior_basis": probe.get(
                        "expected_behavior_basis"
                    ),
                    "probe_result": probe.get("probe_result"),
                    "observed": probe.get("probe_observed"),
                    "expected": probe.get("probe_expected"),
                    "execution_kind": probe.get("execution_kind"),
                    "freshness": probe.get("probe_freshness"),
                    "file": probe_target.get("file") if probe_target else "",
                    "symbol": probe_target.get("symbol") if probe_target else "",
                    "semantics": (
                        "bounded behavior reproduced; not repository validation, "
                        "patch correctness, or sole-cause certainty"
                    ),
                }
            ]
        else:
            defect_evidence = [
                {
                    "kind": "executed_validation_failure",
                    "category": preflight.get("category"),
                    "outcome": preflight.get("outcome", "failed"),
                    "command": preflight.get("command", ""),
                    "binding": binding.kind,
                    "file": binding.candidate_file,
                    "symbol": binding.candidate_symbol,
                    "failure_location": (
                        binding.location.as_dict() if binding.location is not None else None
                    ),
                    "semantics": "failure_relevant; not sole-cause certainty",
                }
            ]
        grounded_hypothesis["defect_established"] = True
        grounded_hypothesis["defect_grounding"] = defect_evidence
        grounded_hypothesis["evidence_classification"]["defect_grounding"] = (
            defect_evidence
        )
        grounded_hypothesis["recommended_action"] = (
            "grounded_defect_candidate"
            if exact_source_grounded
            else "acquire_source_context"
        )
        grounded_hypothesis["needs_escalation"] = not exact_source_grounded

    defect_established = bool(
        grounded_hypothesis is not None and not explicit_change_requested
    )

    # A historical projection is accepted only when the old artifact itself
    # retained executed-failure evidence and exact-source grounding.  A legacy
    # localization confidence or a naked ``defect_grounded=true`` is never
    # reinterpreted as proof.
    historical_evidence = previous_candidate_state.get("defect_grounding") or []
    historical_grounded = bool(
        not genuine_failure
        and probe_target is None
        and previous_candidate_state.get("defect_grounded") is True
        and previous_candidate_state.get("exact_source_grounded") is True
        and any(
            isinstance(item, dict)
            and item.get("kind") == "executed_validation_failure"
            for item in historical_evidence
        )
    )

    if explicit_change_requested:
        patch_basis = PATCH_BASIS_EXPLICIT_CHANGE_REQUEST
        patch_basis_source = PATCH_BASIS_SOURCE_EXPLICIT_REQUEST
        basis_binding_kind = FAILURE_BINDING_EXPLICIT_CHANGE_REQUEST
        basis_binding_location = None
        candidate_binding = None
    elif defect_established and exact_source_grounded:
        patch_basis = PATCH_BASIS_GROUNDED_DEFECT
        if grounding_source == "bounded_reproduction":
            patch_basis_source = PATCH_BASIS_SOURCE_BOUNDED_REPRODUCTION
            basis_binding_kind = FAILURE_BINDING_BOUNDED_REPRODUCTION
            basis_binding_location = None
            candidate_binding = dict(probe_target or {}) or None
        else:
            patch_basis_source = PATCH_BASIS_SOURCE_EXECUTED_FAILURE
            basis_binding_kind = binding.kind
            basis_binding_location = (
                binding.location.as_dict() if binding.location is not None else None
            )
            candidate_binding = binding.candidate_binding
    elif historical_grounded:
        patch_basis = PATCH_BASIS_GROUNDED_DEFECT
        patch_basis_source = PATCH_BASIS_SOURCE_EXECUTED_FAILURE
        basis_binding_kind = str(
            previous_candidate_state.get("failure_binding_kind")
            or FAILURE_BINDING_UNAVAILABLE
        )
        basis_binding_location = previous_candidate_state.get(
            "failure_binding_location"
        )
        candidate_binding = previous_candidate_state.get("candidate_binding")
        defect_established = True
        exact_source_grounded = True
        defect_evidence = list(historical_evidence)
    elif isinstance(route, dict) and route.get("defect_claim_present") is True:
        patch_basis = PATCH_BASIS_UNRESOLVED
        patch_basis_source = PATCH_BASIS_SOURCE_UNAVAILABLE
        basis_binding_kind = binding.kind
        basis_binding_location = None
        candidate_binding = None
    else:
        patch_basis = PATCH_BASIS_NONE
        patch_basis_source = PATCH_BASIS_SOURCE_UNAVAILABLE
        basis_binding_kind = binding.kind
        basis_binding_location = None
        candidate_binding = None

    handoff_ready = bool(
        patch_basis == PATCH_BASIS_GROUNDED_DEFECT and exact_source_grounded
    )
    current_action = (
        "grounded_defect_candidate"
        if handoff_ready
        else "change_request_candidate"
        if patch_basis == PATCH_BASIS_EXPLICIT_CHANGE_REQUEST
        else "acquire_source_context"
        if defect_established
        else "resolve_failure_reference"
        if binding.kind == FAILURE_BINDING_AMBIGUOUS
        else "needs_grounding"
    )
    # WAITER.LIVE.1 — why a change is needed, kept separate from whether a
    # defect exists.  A grounded defect outranks everything, because executed
    # failure evidence is the strongest reason there is; an explicit user
    # request is a real reason too, and it is *not* defect evidence.  Neither
    # grants any authority, and an unrouted run stays exactly where
    # CONTROL.SAFETY.LIVE.1 left it.
    #
    # A defect established while an explicit change was requested does not
    # relabel *why* the user wants the change.  Baseline health is not a task
    # shape: a repository that already fails its own tests does not turn "add
    # task priority support" into a bug report.  ``defect_established`` stays
    # an independent fact either way.
    change_need_source = route_change_need_source(route)
    if defect_established and not explicit_change_requested:
        change_need_source = CHANGE_NEED_GROUNDED_DEFECT
    patch_intent.update(
        {
            "intent_kind": "grounded_defect_candidate"
            if defect_established
            else "change_request_candidate"
            if explicit_change_requested
            else "source_acquisition_candidate",
            "change_need_source": change_need_source,
            "patch_basis": patch_basis,
            "patch_basis_source": patch_basis_source,
            "failure_binding_kind": basis_binding_kind,
            "failure_binding_location": basis_binding_location,
            "candidate_binding": candidate_binding,
            "localization_score": (
                grounded_hypothesis or top or {}
            ).get("localization_score"),
            "confidence_kind": LOCALIZATION_CONFIDENCE_KIND,
            "defect_established": defect_established,
            "defect_grounding": defect_evidence,
            "exact_source_grounded": exact_source_grounded,
            "target_source_grounded": exact_source_grounded,
            "eligible_for_patch_safety_handoff": handoff_ready,
            "recommended_action": current_action,
            "auto_patch_candidate_allowed": False,
        }
    )
    control_result["patch_intent"] = patch_intent
    control_result["grounded_hypothesis"] = grounded_hypothesis
    control_result["localization_assessment"] = {
        "candidate": top.get("symbol") if top else None,
        "raw_rank": top.get("localization_rank") if top else None,
        "localization_score": top.get("localization_score") if top else None,
        "localization_strength": top.get("localization_strength") if top else None,
        "localization_reasons": top.get("localization_reasons", []) if top else [],
        "semantics": LOCALIZATION_SCORE_SEMANTICS,
        "authoritative_for_defect": False,
        "authoritative_for_patch": False,
    }
    control_result["patch_candidate_state"] = {
        "localization_candidate_present": top is not None,
        "defect_established": defect_established,
        "defect_grounded": patch_basis == PATCH_BASIS_GROUNDED_DEFECT,
        "defect_grounding": defect_evidence,
        "patch_basis": patch_basis,
        "patch_basis_source": patch_basis_source,
        "failure_binding_kind": basis_binding_kind,
        "failure_binding_location": basis_binding_location,
        "candidate_binding": candidate_binding,
        "exact_source_grounded": exact_source_grounded,
        "target_source_grounded": exact_source_grounded,
        "eligible_for_patch_safety_handoff": handoff_ready,
        "recommended_action": current_action,
        "change_need_source": change_need_source,
        "explicit_change_requested": explicit_change_requested,
        "patch_eligibility_granted": False,
        "auto_patch_candidate_allowed": False,
        "write_authority": False,
        "patch_application_authority": False,
        "authority_source": (
            "existing patch safety, CTX.PATCH/CTX.APPLY, runtime authorization, "
            "and human approval where required"
        ),
    }
    control_result["patch_basis"] = patch_basis
    control_result["patch_basis_source"] = patch_basis_source
    control_result["failure_binding_kind"] = basis_binding_kind
    control_result["failure_binding_location"] = basis_binding_location
    control_result["candidate_binding"] = candidate_binding
    control_result["target_source_grounded"] = exact_source_grounded
    decision = control_result.setdefault("decision", {})
    decision["symbol"] = top.get("symbol") if top else None
    decision["action"] = top.get("recommended_action") if top else None
    decision["grounded_symbol"] = (
        grounded_hypothesis.get("symbol") if grounded_hypothesis else None
    )
    decision["patch_candidate_action"] = current_action
    decision["auto_patch_candidate_allowed"] = False
    control_result["legacy_control_confidence_deprecated"] = True
    return control_result


def attach_carried_behavior_facts(control_result: dict) -> dict:
    """DEFECT.FACT.LIVE.1 — carry the route's typed behavior facts, unchanged.

    CONTROL transports what INPUT typed.  It records the facts beside the
    localized target so *where* and *what behavior* travel together while
    staying separate fields, and it neither authors, edits, reorders nor
    resolves one: the values written here are exactly the values the route
    carried, and a contradicted claim stays contradicted.
    """
    facts, typed_transport = carried_behavior_facts(control_result)
    control_result["behavior_facts"] = [fact.as_dict() for fact in facts]
    control_result["behavior_fact_transport"] = (
        "typed_preserved_contract" if typed_transport else "legacy_untyped_transport"
    )
    return control_result


def attach_preflight_validation(control_result: dict, preflight: dict) -> dict:
    """Attach validation, then try one eligible bounded reproduction.

    DEFECT.PROBE.LIVE.1 is self-selecting and returns ``None`` for analysis,
    explicit-change, passing baseline and genuine executed-failure routes.  It
    therefore does not force the existing fast defect flows through a probe.

    DEFECT.FACT.LIVE.1 adds two things and changes neither the selection nor the
    execution: the typed behavior facts are carried onto the result, and the one
    resolution pass that ran is described in a read-only telemetry block so a
    later black-box run does not have to reconstruct why a probe was
    unavailable.
    """
    control_result["preflight_validation"] = preflight
    refresh_control_safety(control_result)
    attach_carried_behavior_facts(control_result)
    if "defect_probe" not in control_result:
        resolution = resolve_control_defect_probe(control_result)
        receipt = execute_resolved_control_defect_probe(control_result, resolution)
        if receipt is not None:
            attach_defect_probe_receipt(control_result, receipt)
        attach_control_probe_telemetry(
            control_result,
            build_control_probe_telemetry(resolution, receipt),
        )
    refresh_control_safety(control_result)
    control_result["localization_handoff"] = current_target_receipt(control_result)
    return control_result


def control_has_grounded_patch_candidate(control_result: dict | None) -> bool:
    if not isinstance(control_result, dict):
        return False
    state = refresh_control_safety(control_result).get("patch_candidate_state") or {}
    return bool(state.get("eligible_for_patch_safety_handoff"))


def control_has_legitimate_patch_basis(control_result: dict | None) -> bool:
    """Whether CONTROL carries either legitimate *reason* to consider a patch.

    This deliberately says nothing about target grounding or write authority.
    Consumers that operate on a concrete payload must also require that
    payload's ``eligible_for_patch_safety_handoff`` fact.
    """

    if not isinstance(control_result, dict):
        return False
    state = refresh_control_safety(control_result).get("patch_candidate_state") or {}
    return has_legitimate_patch_basis(state.get("patch_basis"))


def payload_is_eligible_for_patch_safety_handoff(block: dict | None) -> bool:
    return bool(
        isinstance(block, dict)
        and has_legitimate_patch_basis(block.get("patch_basis"))
        and block.get("target_source_grounded") is True
        and block.get("eligible_for_patch_safety_handoff") is True
    )


def acquired_source_files(control_result: dict | None) -> set[str]:
    """Repository files whose source this run actually read.

    The change-request path patches what it has read, not what it has ranked.
    Membership is drawn only from context that really carries source text: a
    related snippet with content, and CONTROL's own target when it has an exact
    source snippet.  A file that was merely *named* — by a rank, or by a Scout
    pick that never resolved to a real file — is deliberately absent, so naming
    a file cannot become permission to edit it.
    """
    if not isinstance(control_result, dict):
        return set()

    repo_path = control_result.get("repo_path")
    files: set[str] = set()

    def quote_is_exact(relative: Any, quote: Any) -> bool:
        if not repo_path or not isinstance(quote, str) or not quote:
            return False
        normalized = _normalized_control_path(relative)
        if not normalized:
            return False
        try:
            repo = Path(repo_path).resolve()
            target = (repo / str(relative)).resolve()
            target.relative_to(repo)
            return target.is_file() and quote in target.read_text(
                encoding="utf-8", errors="replace"
            )
        except (OSError, ValueError):
            return False

    for snippet in control_result.get("related_snippets") or []:
        if not isinstance(snippet, dict):
            continue
        text = snippet.get("snippet")
        if not isinstance(text, str) or not text.strip():
            continue
        normalized = _normalized_control_path(snippet.get("file"))
        if normalized and quote_is_exact(snippet.get("file"), text):
            files.add(normalized)

    intent = control_result.get("patch_intent")
    if isinstance(intent, dict) and str(intent.get("source_snippet") or "").strip():
        normalized = _normalized_control_path(
            intent.get("relative_path")
            or intent.get("file")
            or intent.get("target_file")
        )
        if normalized and quote_is_exact(
            intent.get("relative_path")
            or intent.get("file")
            or intent.get("target_file"),
            intent.get("source_snippet"),
        ):
            files.add(normalized)
    return files


def enforce_control_grounding_on_payload(
    control_result: dict,
    block: dict,
) -> dict:
    """Fail closed when model output outruns CONTROL's grounded-candidate facts.

    This gate grants nothing.  A passing result merely hands the candidate to
    the pre-existing quote grounding, patch safety, policy and apply gates.

    There are exactly two legitimate reasons a payload may pass, and they are
    not interchangeable:

    *defect grounding* — an executed OPS.VALIDATE.1 failure bound to a ranked
    file, whose exact source CONTROL supplied.  Unchanged by WAITER.LIVE.1.

    *change-request grounding* — the user explicitly asked for the change, and
    every proposed operation targets a file whose source this run really
    acquired.  This supplies a different reason **why** a change is needed; it
    weakens nothing about **how** one may be executed, and every quote is still
    checked against the file by the gates downstream.

    A read-only route passes under neither.  Localization rank alone still
    passes under neither, which is CONTROL.SAFETY.LIVE.1's whole point.
    """
    if not isinstance(control_result, dict) or not isinstance(block, dict):
        return block
    candidate = block.get("patch_candidate")
    plan = block.get("patch_plan")
    if not isinstance(candidate, dict) and not (isinstance(plan, list) and plan):
        return block

    # Authoring containment precedes acceptance; the CONTROL basis below is
    # unchanged. This also covers the direct Generate Patch endpoint.
    if control_result.get("repair_scope"):
        try:
            authoring = authoring_context_for_control_result(
                control_result, repo_path=control_result.get("repo_path"),
            )
            if not enforce_authoring_scope(authoring, block):
                return block
        except AuthoringScopeError as exc:
            block.update(patch_candidate=None, patch_plan=None, needs_escalation=True,
                         authoring_scope_status=exc.reason)
            return block

    control = refresh_control_safety(control_result)
    candidate_state = control.get("patch_candidate_state") or {}
    grounded_intent = control.get("patch_intent") or {}
    route = control.get("live_route")
    patch_basis = normalize_patch_basis(candidate_state.get("patch_basis"))
    grounded_file = _normalized_control_path(
        grounded_intent.get("relative_path")
        or grounded_intent.get("file")
        or grounded_intent.get("target_file")
    )
    handoff_ready = bool(
        candidate_state.get("eligible_for_patch_safety_handoff")
        and grounded_file
    )

    target_records: list[tuple[str, str]] = []
    if isinstance(candidate, dict):
        target_records.append(
            (
                _normalized_control_path(
                    candidate.get("relative_path") or candidate.get("file")
                ),
                str(candidate.get("op") or "replace_snippet"),
            )
        )
    if isinstance(plan, list):
        target_records.extend(
            (
                _normalized_control_path(
                    operation.get("relative_path") or operation.get("file")
                ),
                str(operation.get("op") or "replace_snippet"),
            )
            for operation in plan
            if isinstance(operation, dict)
        )
    named_targets = {target for target, _ in target_records if target}
    create_targets = {
        target for target, operation in target_records if operation == "create_file"
    }
    replacement_targets = named_targets - create_targets
    target_is_bound = grounded_file in named_targets

    read_only_route = route_is_read_only(route)
    acquired = acquired_source_files(control)
    requested_paths = {
        _normalized_control_path(path)
        for path in ((route or {}).get("requested_paths") or [])
        if _normalized_control_path(path)
    }
    replacements_grounded = bool(named_targets) and replacement_targets <= acquired
    creates_grounded = create_targets <= requested_paths
    target_source_grounded = bool(
        named_targets and replacements_grounded and creates_grounded
    )
    scope_tokens = explicit_change_scope_tokens(route)
    scope_grounded = explicit_change_targets_match_scope(route, named_targets)

    defect_payload_ready = bool(
        patch_basis == PATCH_BASIS_GROUNDED_DEFECT
        and handoff_ready
        and target_is_bound
        and target_source_grounded
    )
    explicit_payload_ready = bool(
        patch_basis == PATCH_BASIS_EXPLICIT_CHANGE_REQUEST
        and route_is_explicit_change(route)
        and not read_only_route
        and target_source_grounded
        and scope_grounded
    )

    block.update(
        {
            "patch_basis": patch_basis,
            "patch_basis_source": candidate_state.get("patch_basis_source"),
            "failure_binding_kind": candidate_state.get("failure_binding_kind"),
            "failure_binding_location": candidate_state.get(
                "failure_binding_location"
            ),
            "candidate_binding": candidate_state.get("candidate_binding"),
            "target_source_grounded": target_source_grounded,
            "change_scope_grounded": scope_grounded,
            "explicit_scope_tokens": list(scope_tokens),
            "eligible_for_patch_safety_handoff": bool(
                defect_payload_ready or explicit_payload_ready
            ),
            "write_authority": False,
            "patch_application_authority": False,
            "human_approval_required": True,
        }
    )
    if defect_payload_ready or explicit_payload_ready:
        return block

    block["patch_candidate"] = None
    block["patch_plan"] = None
    block["confidence"] = 0.0
    block["needs_escalation"] = True
    block["control_patch_candidate_rejected"] = True
    if read_only_route:
        block["control_patch_candidate_reject_reason"] = (
            "No repository change was requested; this route is read-only."
        )
    elif patch_basis == PATCH_BASIS_EXPLICIT_CHANGE_REQUEST and not target_source_grounded:
        block["control_patch_candidate_reject_reason"] = (
            "The requested change targets a file whose exact source this run did "
            "not acquire, or creates a path the preserved request did not name."
        )
    elif patch_basis == PATCH_BASIS_EXPLICIT_CHANGE_REQUEST and not scope_grounded:
        block["control_patch_candidate_reject_reason"] = (
            "The proposed targets do not preserve the explicit multi-surface scope "
            "recorded in the user request."
        )
    elif route_is_explicit_change(route):
        block["control_patch_candidate_reject_reason"] = (
            "The change was explicitly requested, but no source context was acquired "
            "to ground it."
        )
    else:
        block["control_patch_candidate_reject_reason"] = (
            "CONTROL has no exact-source candidate bound to genuine executed failure evidence."
            if not handoff_ready
            else "The proposed patch has an ungrounded target or does not include CONTROL's grounded target file."
        )
    issues = block.get("issues")
    if not isinstance(issues, list):
        issues = []
    if not any(
        isinstance(issue, dict)
        and issue.get("type") == "control_grounding"
        for issue in issues
    ):
        issues.insert(
            0,
            {
                "severity": "high",
                "type": "control_grounding",
                "file": grounded_file,
                "symbol": grounded_intent.get("target_symbol") or "",
                "reason": block["control_patch_candidate_reject_reason"],
                "fix": "Inspect the candidate or collect genuine target-bound failure evidence before patching.",
            },
        )
    block["issues"] = issues
    return block


def reject_ungrounded_control_patch(state: Any) -> None:
    """AgentState adapter for the shared CONTROL payload boundary."""
    if not getattr(state, "is_project_input", False):
        return
    control_result = getattr(state, "control_result", None)
    block = getattr(state, "json_block", None)
    if isinstance(control_result, dict) and isinstance(block, dict):
        enforce_control_grounding_on_payload(control_result, block)


def format_control_context(result: dict) -> str:
    result = refresh_control_safety(result)
    lines = []

    lines.append("=== CONTROL ENGINE CONTEXT ===")
    lines.append("")
    lines.append(f"Query: {result['query']}")
    lines.append(f"Repo: {result['repo_path']}")
    lines.append("")

    entry_resolution = result.get("entry_resolution") or {}
    lines.append("## Query Recall Facts")
    lines.append(
        f"- raw_query_terms: {entry_resolution.get('raw_query_terms', [])}"
    )
    lines.append(
        "- normalized_query_terms: "
        f"{entry_resolution.get('normalized_query_terms', [])}"
    )
    lines.append(
        f"- resolved_entry_nodes: {entry_resolution.get('resolved_entry_nodes', [])}"
    )
    lines.append(
        f"- entry_match_kind: {entry_resolution.get('entry_match_kind', {})}"
    )
    lines.append(f"- fallback_used: {entry_resolution.get('fallback_used', False)}")
    lines.append(
        "- query_resolution_seconds: "
        f"{entry_resolution.get('query_resolution_seconds', 0.0)}"
    )
    lines.append("")

    lines.append("## Top Localization Candidate")
    top = result.get("top_hypothesis")
    if top:
        lines.append(f"- symbol: {top['symbol']}")
        lines.append(f"- likely_issue_hint: {top['likely_issue']}")
        lines.append(f"- localization_score: {top['localization_score']}")
        lines.append(f"- localization_strength: {top['localization_strength']}")
        lines.append(
            f"- legacy confidence ({top['confidence_kind']}): {top.get('confidence')}"
        )
        lines.append(f"- defect_established: {top['defect_established']}")
        lines.append(f"- recommended_action: {top['recommended_action']}")
        lines.append(f"- localization_reasons: {top['localization_reasons']}")
        for key in (
            "anchor_relation", "originating_entry", "entry_rank",
            "query_relevance_support", "source_support", "graph_support",
            "centrality_support", "final_localization_class", "selected_reason",
        ):
            lines.append(f"- {key}: {top.get(key)}")
        lines.append(f"- language: {top.get('language', 'unknown')}")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Entry Nodes")
    for n in result.get("entry_nodes", []):
        lines.append(f"- {n}")
    if not result.get("entry_nodes"):
        lines.append("- none")
    lines.append("")

    lines.append("## Ranked Localization Candidates")
    for h in result.get("hypotheses", []):
        lines.append(
            f"- {h['symbol']} | issue_hint={h['likely_issue']} | "
            f"localization_score={h['localization_score']} | "
            f"strength={h['localization_strength']} | "
            f"defect_established={h['defect_established']} | "
            f"action={h['recommended_action']}"
        )
        lines.append(f"  anchor={h.get('anchor_relation')} | class={h.get('final_localization_class')} | reason={h.get('selected_reason')}")
    if not result.get("hypotheses"):
        lines.append("- none")
    lines.append("")

    lines.append("## Graph Evidence")
    for item in result.get("evidence", []):
        risk = item.get("risk", {})
        lines.append(f"### {item['symbol']}")
        lines.append(f"- depth: {item['depth']}")
        lines.append(f"- score: {item.get('score', 0):.2f}")
        lines.append(f"- graph_weight: {item.get('graph_weight', 0):.2f}")
        lines.append(f"- risk: {risk.get('risk_level')} ({risk.get('risk_score')})")
        lines.append(f"- score_semantics: {LOCALIZATION_SCORE_SEMANTICS}")
        lines.append(f"- called_by: {item.get('called_by', [])[:5]}")
        lines.append(f"- calls: {item.get('calls', [])[:5]}")
        lines.append(f"- impact: {item.get('impact', [])[:5]}")
        lines.append("")
    if not result.get("evidence"):
        lines.append("- no strong graph evidence")
        lines.append("")

    lines.append("## Execution / State Trace")
    lines.append(result.get("execution_trace") or "No execution trace found.")
    lines.append("")

    phantom = result.get("phantom_limb") or {}
    phantom_findings = phantom.get("findings") or []
    lines.append("## Phantom Limb Suggestions")
    if phantom_findings:
        for item in phantom_findings[:12]:
            lines.append(
                f"- {item.get('severity', 'info')}: {item.get('file', '?')} "
                f"[{item.get('rule', 'unknown')}] missing {item.get('missing', '')}"
            )
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Structured Control JSON")
    lines.append("```json")
    lines.append(json.dumps({
        "entry_resolution": result.get("entry_resolution"),
        "top_hypothesis": result.get("top_hypothesis"),
        "hypotheses": result.get("hypotheses"),
        "phantom_limb": {
            "count": len(phantom_findings),
            "findings": phantom_findings[:12],
        },
    }, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")

    lines.append("## Control Rules")
    for rule in result.get("control_rules", []):
        lines.append(f"- {rule}")

    return "\n".join(lines)


def run_control_structured(
    query: str,
    repo_path: str,
    *,
    inventory=None,
    graph=None,
) -> dict:
    if inventory is not None:
        from core.repository_inventory import (
            validate_repository_inventory,
        )

        validate_repository_inventory(repo_path, inventory)
    graph = graph or get_cached_graph(
        repo_path,
        inventory=inventory,
    )

    entry_selection = select_entry_nodes(
        query=query,
        repo_path=repo_path,
        limit=6,
        graph=graph,
        inventory=inventory,
        return_details=True,
    )
    if isinstance(entry_selection, dict):
        entry_nodes = list(entry_selection.get("entry_nodes") or [])
        entry_resolution = entry_selection
    else:
        # Compatibility for existing embedders/tests that replace the selector.
        entry_nodes = list(entry_selection)
        entry_resolution = {}

    evidence = control_dfs_v2(
        graph=graph,
        entry_nodes=entry_nodes,
        query=query,
        max_depth=2,
        max_nodes=20,
        neighbor_limit=3,
        repo_path=repo_path,
    )

    execution_trace = trace_execution_flow(
        query=query,
        repo_path=repo_path,
        top_k=3,
        graph=graph,
        inventory=inventory,
    )

    return build_control_result(
        query=query,
        repo_path=repo_path,
        entry_nodes=entry_nodes,
        evidence=evidence,
        execution_trace=execution_trace,
        entry_resolution=entry_resolution,
    )

def run_control(
    query: str,
    repo_path: str,
    *,
    inventory=None,
    graph=None,
) -> str:
    result = run_control_structured(
        query,
        repo_path,
        inventory=inventory,
        graph=graph,
    )
    return format_control_context(result)

def resolve_query_to_graph_nodes(
    graph,
    query_candidates: list[str] | tuple[str, ...],
    *,
    limit: int = 6,
) -> list[IdentifierEntryMatch]:
    """Resolve bounded query concepts against eligible source identifiers.

    Eligibility is evaluated first, so structural call nodes and malformed
    historical nodes never reach decomposition.  The scan is linear in the
    already-loaded eligible population; ordering uses lexical entry facts only,
    never centrality, caller count, hotspot score, or CONTROL rank.
    """
    return list(
        resolve_identifier_candidates(
            eligible_localization_nodes(graph),
            query_candidates,
            limit=limit,
        ).matches
    )


def resolve_symbol_to_graph_nodes(
    graph,
    symbol: str,
    query: str = "",
    limit: int = 3,
) -> list[str]:
    """Compatibility resolver for one canonical symbol or lexical concept."""
    del query  # Ranking relevance remains downstream and unchanged.
    return [
        match.node_id
        for match in resolve_identifier_candidates(
            eligible_localization_nodes(graph),
            [symbol] if symbol else [],
            limit=limit,
        ).matches
    ]

def fallback_entry_nodes_from_graph(graph, query: str, limit: int = 6) -> list[str]:
    words = query_words(query)
    profile = infer_context_profile(query)
    candidates = []

    for node_id in eligible_localization_nodes(graph):
        node = graph.nodes[node_id]

        score = relevance_bonus(node_id, words)

        tail = node_id.split("::")[-1].lower()
        if tail in {"update", "start", "main", "run"}:
            score += 5
        
        q = query.lower()
        if any(k in q for k in ["call", "calls", "argument", "arguments", "parameter", "parameters"]):
            if tail in {"update", "start", "main", "run"}:
                score += 3

        if getattr(node, "type", "") == "function":
            score += 1

        multiplier = score_multiplier_for_path(node_id, profile)
        if profile == "identity" and multiplier > 1.0:
            score = max(score, 1.0)
        score *= multiplier

        if score > 0:
            candidates.append((score, node_id))

    candidates.sort(key=lambda x: (-x[0], x[1]))
    print("🐛 DEBUG fallback candidates:", candidates[:10])
    return [node_id for _, node_id in candidates[:limit]]

def _safe_minimal_forbidden_block(source_snippet: str) -> str:
    """Compatibility shim over the shared contract (PATCH.AUTHOR.LIVE.2).

    The derivation is unchanged and still bounded by the source snippet the
    author was already handed — no repository is rescanned.  It moved to
    ``core.patch_authoring_contract`` so the revision author receives the
    identical identifier constraints rather than none at all.
    """
    return safe_minimal_forbidden_block(source_snippet)


def authoring_contract_for_control_result(
    control_result: dict,
) -> PatchAuthoringContract:
    """PATCH.AUTHOR.LIVE.2 §1 — the contract this result's patch author gets.

    Resolved from exactly the two inputs :func:`build_control_prompt` resolves
    it from: the patch policy's normalized style, and the bounded source
    snippet already on ``patch_intent``.  Every authoring call for this
    CONTROL result — the initial draft and the single verification-guided
    revision — reads the contract here instead of describing the protocol
    again, which is what makes the two one contract rather than two.

    Pure prompt construction: no retrieval, no graph work, no repository
    traversal, no indexing and no model call.
    """

    patch_intent = control_result.get("patch_intent") or {}
    top = control_result.get("top_hypothesis") or {}
    candidate_state = control_result.get("patch_candidate_state") or {}
    policy = build_patch_policy(
        control_result.get("patch_style"),
        language=(patch_intent.get("language") or top.get("language") or "unknown"),
        defect_grounded=bool(candidate_state.get("defect_grounded")),
        patch_basis=candidate_state.get("patch_basis"),
        patch_confidence=0.0,
    )
    return render_patch_authoring_contract(
        style=policy.style,
        source_snippet=patch_intent.get("source_snippet", "") or "",
    )


def _patch_output_format_block(style: str) -> str:
    """Compatibility shim over the shared contract (PATCH.AUTHOR.LIVE.2).

    The wire shapes, the exact field names and the per-style output rules now
    live in ``core.patch_authoring_contract`` so the verification-guided
    revision author is held to the same contract as the initial author.  The
    rendered text is byte-identical to what this function returned before;
    there is simply one definition of it.
    """
    return patch_output_format_block(style)


def authoring_context_for_control_result(
    control_result: dict, *, repo_path: str | None = None,
) -> CandidateAuthoringContext:
    """Use PATCH.MINIMAL's named-target loader, never a separate lexical scan."""

    intent = control_result.get("patch_intent") or {}
    path = str(intent.get("relative_path") or intent.get("file")
               or intent.get("target_file") or "").replace("\\", "/")
    symbol = str(intent.get("target_symbol")
                 or str(intent.get("target_symbol_full") or "").rsplit("::", 1)[-1]
                 or "").strip()
    context, source, source_raw = (None, "", b"")
    if repo_path and path and symbol:
        if path.lower().endswith(".java"):
            from core.candidate_authoring_context import load_java_authoring_source
            source, source_raw = load_java_authoring_source(repo_path, path)
        else:
            context, source = load_authoritative_binding_context(
                repo_root=repo_path, source_path=path, target_symbol=symbol,
            )
    repair = None
    measured = control_result.get("repair_scope")
    if measured and measured.get("status") != REPAIR_SCOPE_NOT_APPLICABLE:
        repair = consume_repair_scope(
            measured, repo_path=repo_path or control_result.get("repo_path") or "",
            primary_file=path, primary_symbol=symbol,
            primary_source=str(intent.get("source_snippet") or ""),
            preflight=control_result.get("preflight_validation") or {},
            language=str(intent.get("language") or ""),
        )
    contract = authoring_contract_for_control_result(control_result)
    if repair is not None and len(repair.measured.members) > 1:
        from core.patch_authoring_contract import for_measured_repair_scope
        contract = for_measured_repair_scope(contract)
    oop_projection = oop_target = None
    if path.lower().endswith(".java") and source:
        from core.oop_reasoning_context import project_oop_author_source
        oop_projection, oop_target = project_oop_author_source(
            source=source, file=path, symbol=symbol,
            source_snippet=str(intent.get("source_snippet") or ""),
            raw=source_raw,
        )
    return CandidateAuthoringContext(
        contract=contract,
        source_path=path, target_symbol=symbol,
        source_snippet=str(intent.get("source_snippet") or ""),
        binding_context=context, authoritative_source=source,
        authoring_repair_scope=repair,
        oop_projection=oop_projection, oop_target=oop_target,
        oop_source_bytes=source_raw,
    )


def _resolve_code_dna_block(control_result: dict) -> str:
    """Return the repo style hint for patch prompts.

    Preferred path: main.py/web mode injects `code_dna_prompt` so UI toggles can
    choose match/ignore once. Fallback path: load cached DNA from the repo so
    direct web endpoints that only carry CONTROL JSON still get a style hint.
    """
    mode = control_result.get("code_dna_mode") or "match"

    injected = control_result.get("code_dna_prompt")
    if injected:
        return injected

    repo_path = control_result.get("repo_path") or ""
    try:
        from core.code_dna import load_dna, dna_to_prompt_block

        dna = load_dna(repo_path) if repo_path else None
        if dna:
            return dna_to_prompt_block(dna, mode=mode)
        if mode == "ignore":
            return dna_to_prompt_block({}, mode="ignore")
    except Exception:
        pass

    return "REPO STYLE: not available. Use idiomatic style for the language."


def _lessons_prompt_block(repo_path: str | None, user_query: str) -> str:
    """Phase 6.3: return an [ACTIVE LESSONS] advisory section, or "" on any
    disabled/empty/error condition.

    Fail-closed: never raises. Reads only from core.lesson_retrieval (which
    in turn reads only `lessons/active/`). The block is intentionally framed
    as advisory hints with lower priority than user request / repo state /
    validation / forbidden files / patch safety rules.
    """
    try:
        import config as _config
    except Exception:
        return ""
    if not getattr(_config, "LESSON_RETRIEVAL_ENABLED", False):
        return ""
    try:
        from core import lesson_retrieval
        try:
            limit = int(getattr(_config, "LESSON_RETRIEVAL_LIMIT", 5))
        except (TypeError, ValueError):
            limit = 5
        try:
            max_chars = int(getattr(_config, "LESSON_RETRIEVAL_MAX_CHARS", 3000))
        except (TypeError, ValueError):
            max_chars = 3000
        lessons = lesson_retrieval.find_active_lessons(
            repo_path=repo_path,
            query=user_query or None,
            limit=limit,
        )
        if not lessons:
            return ""
        formatted = lesson_retrieval.format_lessons_for_prompt(
            lessons, max_chars=max_chars
        )
        if not formatted.strip():
            return ""
        return (
            "\n[ACTIVE LESSONS — advisory hints, lowest priority]\n"
            "These are advisory hints from past auto-approved lessons.\n"
            "User request, repo state, validation command, forbidden files,\n"
            "and patch safety rules all have higher priority. Do NOT copy a\n"
            "lesson blindly.\n"
            "\n"
            f"{formatted}\n"
        )
    except Exception as exc:
        # Fail closed: lessons are advisory, never block the patch flow.
        try:
            import sys
            sys.stderr.write(
                f"[control_engine] lesson retrieval skipped: {type(exc).__name__}: {exc}\n"
            )
        except Exception:
            pass
        return ""


def _anti_lessons_prompt_block(
    repo_path: str | None,
    user_query: str,
    *,
    requested: bool,
    max_items: int = 3,
) -> str:
    """Phase 11.7c: return an [ANTI-LESSONS / DO NOT REPEAT — EXPERIMENTAL] block,
    or "" unless BOTH the server flag and the per-request flag are set.

    Two-key gate (fail-closed). When ``requested`` is false this returns ""
    *without importing anything*, keeping the default CONTROL prompt
    byte-identical to Phase 11.7b. When requested, it delegates to
    ``core.anti_lesson_control_injection.build_anti_lesson_control_block``, which
    re-checks ``config.ANTI_LESSONS_CONTROL_ENABLED`` and reads anti-lessons
    read-only. Never raises.
    """
    if not requested:
        return ""
    try:
        from core.anti_lesson_control_injection import build_anti_lesson_control_block

        return build_anti_lesson_control_block(
            repo_path, user_query, requested=True, max_items=max_items
        )
    except Exception as exc:
        # Fail closed: anti-lessons are advisory, never block the patch flow.
        try:
            import sys
            sys.stderr.write(
                f"[control_engine] anti-lesson control block skipped: "
                f"{type(exc).__name__}: {exc}\n"
            )
        except Exception:
            pass
        return ""


def build_control_prompt(
    control_result: dict,
    user_query: str,
    *,
    repo_path: str | None = None,
    anti_lesson_control_requested: bool = False,
    anti_lesson_control_max_items: int = 3,
    authoring_context: CandidateAuthoringContext | None = None,
) -> str:
    # The receipt's CONTROL binding predates the preflight handoff and all
    # later CONTROL bookkeeping.  Capture it before ``refresh_control_safety``
    # mutates the in-memory projection; this is a verification input, never a
    # new source of target selection.
    receipt_control = dict(control_result) if isinstance(control_result, dict) else {}
    receipt_control.pop("preflight_validation", None)
    receipt_control_fingerprint = hashlib.sha256(json.dumps(
        receipt_control, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    control_result = refresh_control_safety(control_result)
    context_profile = (
        control_result.get("context_profile")
        or infer_context_profile(control_result.get("query") or user_query)
    )
    identity_framing = identity_answer_framing(
        user_query,
        profile=context_profile,
    )
    top = control_result.get("top_hypothesis") or {}
    patch_intent = control_result.get("patch_intent") or {}
    preflight = control_result.get("preflight_validation") or {}
    candidate_state = control_result.get("patch_candidate_state") or {}
    # Re-rendering/revision consumes the BASIS receipt already produced by this
    # run. It must not select membership again from enriched CONTROL state.
    existing_authoring = None
    if (control_result.get("repair_scope") or {}).get("status") == REPAIR_SCOPE_COMPLETE:
        existing_authoring = authoring_context_for_control_result(control_result, repo_path=repo_path)
    if existing_authoring is not None:
        repair_scope = existing_authoring.authoring_repair_scope.measured
    else:
        repair_scope = build_repair_scope(
            repo_path=control_result.get("repo_path"),
            primary_file=(patch_intent.get("relative_path") or patch_intent.get("file")
                          or patch_intent.get("target_file")),
            primary_symbol=(patch_intent.get("target_symbol")
                            or patch_intent.get("target_node_name")),
            primary_kind=patch_intent.get("target_node_kind") or "function",
            language=patch_intent.get("language"),
            preflight=preflight,
            receipt_control_fingerprint=receipt_control_fingerprint,
        )
    # Scope is additive evidence on the grounded basis.  ``target_file`` and
    # ``target_symbol`` continue to name only the existing primary target.
    if repair_scope.status != REPAIR_SCOPE_NOT_APPLICABLE:
        repair_scope_data = repair_scope.as_dict()
        control_result["repair_scope"] = repair_scope_data
        patch_intent["repair_scope"] = repair_scope_data
        candidate_state["repair_scope_status"] = repair_scope.status
    repair_scope_prompt = render_repair_scope_prompt(repair_scope)
    related_snippets = control_result.get("related_snippets") or []
    scout = control_result.get("scout") or {}
    # WAITER.LIVE.1 — what kind of order this is.  An unrouted call (Dream, the
    # proposal queue, a direct CONTROL inspection) reads as neither, and every
    # branch below then behaves exactly as it did before this phase.
    live_route = control_result.get("live_route")
    explicit_change_route = route_is_explicit_change(live_route)
    read_only_route = route_is_read_only(live_route)
    code_dna_block = _resolve_code_dna_block(control_result)
    lessons_block = _lessons_prompt_block(repo_path, user_query)
    # Phase 11.7c: default-off, two-key-gated. "" unless the server flag AND the
    # per-request flag are both set — so the default prompt is byte-identical.
    anti_lessons_block = _anti_lessons_prompt_block(
        repo_path,
        user_query,
        requested=bool(anti_lesson_control_requested),
        max_items=anti_lesson_control_max_items,
    )

    # Use the canonical schema constant from prompter.py.
    from core.prompter import PATCH_RESPONSE_SCHEMA

    # Prefer actual known language from patch intent/top hypothesis.
    language = (
        patch_intent.get("language")
        or top.get("language")
        or "unknown"
    )

    policy = build_patch_policy(
        control_result.get("patch_style"),
        language=language,
        defect_grounded=bool(candidate_state.get("defect_grounded")),
        patch_basis=candidate_state.get("patch_basis"),
        patch_confidence=0.0,
    )

    policy_block = policy_to_prompt_block(policy)
    style = policy.style
    # PATCH.AUTHOR.LIVE.2 — one rendering of the authoritative patch-authoring
    # contract.  A later authoring call for the same artifact asks the same
    # accessor rather than restating the protocol, so the two cannot drift.
    contract = authoring_contract_for_control_result(control_result)
    authoring_context = authoring_context or authoring_context_for_control_result(
        control_result, repo_path=repo_path,
    )
    # Consume the just-built BASIS result, never a model-proposed member list.
    # A context supplied before BASIS ran must gain this same measured boundary.
    if repair_scope.is_complete and authoring_context.authoring_repair_scope is None:
        authoring_context = authoring_context_for_control_result(control_result, repo_path=repo_path)
    if authoring_context.authoring_repair_scope is not None:
        authoring_context.authoring_repair_scope.assert_current(preflight)
        if authoring_context.authoring_repair_scope.measured.as_dict()["members"] != repair_scope.as_dict()["members"]:
            raise AuthoringScopeError("author_scope_receipt_mismatch")
    contract = authoring_context.contract
    if authoring_context.authoring_repair_scope is not None and len(repair_scope.members) > 1:
        repair_scope_prompt = (
            "[MEASURED REPAIR SCOPE — authoritative compiler evidence]\n"
            "Receipt-bound sources and member diagnostics are projected without alteration "
            "in AUTHORITATIVE AUTHORING SCOPE above."
        )
    current_binding, current_source, current_raw = authoring_context.source_inputs(repo_path)
    expected_path = str(patch_intent.get("relative_path") or patch_intent.get("file")
                        or patch_intent.get("target_file") or "").replace("\\", "/")
    expected_symbol = str(patch_intent.get("target_symbol")
                          or str(patch_intent.get("target_symbol_full") or "").rsplit("::", 1)[-1]
                          or "").strip()
    if (authoring_context.source_path != expected_path
            or authoring_context.target_symbol != expected_symbol
            or authoring_context.source_snippet != str(patch_intent.get("source_snippet") or "")):
        current_binding, current_source, current_raw = None, "", b""
    # Rendering from a stale scope can only omit the expansion, never refresh
    # it silently into capabilities the first author did not see.
    from dataclasses import replace
    scope_text = replace(
        authoring_context, binding_context=current_binding,
        authoritative_source=current_source,
    ).scope_text
    oop_attachment = replace(authoring_context, authoritative_source=current_source,
                             oop_source_bytes=current_raw).oop_attachment
    output_format_block = contract.output_format_block

    # Render related snippets. For feature tasks, this becomes patchable source.
    related_block = "No related snippets."
    if related_snippets:
        parts = []
        for idx, item in enumerate(related_snippets[:8], start=1):
            snippet_lang = infer_language_from_file(item.get("file", "")) or language
            parts.append(
                f"""--- RELATED SNIPPET [{idx}] ---
role={item.get("role", "related")}
file={item.get("file", "")}
symbol={item.get("symbol", "")}

```{snippet_lang}
{item.get("snippet", "")}
```"""
            )
        related_block = "\n\n".join(parts)

    phantom = control_result.get("phantom_limb") or {}
    phantom_findings = phantom.get("findings") or []
    phantom_block = "No phantom limb suggestions."
    if phantom_findings:
        phantom_block = "\n".join(
            f"- {item.get('severity', 'info')}: {item.get('file', '?')} "
            f"[{item.get('rule', 'unknown')}] missing {item.get('missing', '')}"
            for item in phantom_findings[:12]
        )

    # Phase 12.5k: pull a budgeted [LINTER HINTS] block from the fused
    # phantom + linter evidence. Empty when no relevant findings exist —
    # we never inject the full findings.json into a prompt.
    linter_hints_block = ""
    if repo_path:
        try:
            from core.linter_fusion import fuse_for_repo

            fusion = fuse_for_repo(repo_path, phantom_findings)
            if fusion.get("prompt_block"):
                linter_hints_block = "\n" + fusion["prompt_block"] + "\n"
            # Mutate the in-memory control_result so downstream consumers can
            # see linter_evidence per phantom candidate. PHANTOM_LIMB.json on
            # disk is left alone (write-side belongs to the scanner).
            if isinstance(phantom, dict):
                phantom["findings"] = fusion["findings"]
                phantom["linter_summary"] = fusion["linter_summary"]
        except Exception as exc:
            try:
                import sys
                sys.stderr.write(
                    f"[control_engine] linter fusion skipped: "
                    f"{type(exc).__name__}: {exc}\n"
                )
            except Exception:
                pass
            linter_hints_block = ""

    is_feature_extension = scout.get("request_type") == "feature_extension"

    # A read-only order must never reach a patch prompt.  Production routes it
    # away from CONTROL entirely, so arriving here means something upstream
    # forgot; answer the question rather than ask for a snippet nobody needs.
    if read_only_route:
        return f"""\
You are inspecting a repository to answer a question. No code change was requested.

[CONTROL CONTEXT — INSPECTION ONLY]
highest_ranked_candidate={top.get("symbol")}
score_semantics={LOCALIZATION_SCORE_SEMANTICS}

[RELATED CONTEXT]
{related_block}
{lessons_block}{anti_lessons_block}
[USER]
{user_query}

[RULES]
- Answer in plain natural language, not JSON.
- No repository change was requested: do not propose or emit a patch or a diff.
- Ground every claim in the context above and name the file it came from.
- If the context is insufficient, say what is missing rather than guessing.
""".strip()

    if identity_framing:
        source_excerpt = patch_intent.get("source_snippet") or "No source excerpt."
        return f"""\
{identity_framing}

[CONTROL CONTEXT]
top_symbol={top.get("symbol")}
localization_score={top.get("localization_score")}
localization_strength={top.get("localization_strength")}
defect_established={candidate_state.get("defect_established", False)}
language={language}

[SOURCE EXCERPT]
{source_excerpt}

[RELATED SOURCE CONTEXT]
{related_block}

[PHANTOM LIMB SUGGESTIONS - structural hints, not proof]
{phantom_block}
{linter_hints_block}{lessons_block}{anti_lessons_block}
[USER]
{user_query}

[RULES]
- Answer in plain natural language, not JSON.
- Explain the product/workspace identity before subsystem details.
- Include repair, patching, and benchmarks as parts of the system when supported by context.
- Do not invent features that are not present in provided context.
""".strip()

    # Localization can identify useful code without establishing any defect or
    # requested change.  Until independently grounded failure evidence binds to
    # exact source, the existing model call is inspection-only and may not mint
    # a patch candidate.
    #
    # WAITER.LIVE.1 adds the one case this gate could not previously express: an
    # explicit change request is grounded in the user's own words rather than in
    # a failing test, so it is not "ungrounded" and must not be told to return
    # nothing.  It falls through to the change-oriented branch below, where the
    # target must still be quoted verbatim from acquired source and every patch
    # safety, CTX and authorization gate still applies.
    if not candidate_state.get("eligible_for_patch_safety_handoff") and (
        not explicit_change_route
    ):
        return f"""\
You are inspecting a repository candidate selected by CONTROL navigation.

[CONTROL LOCALIZATION — NON-AUTHORITATIVE]
highest_ranked_candidate={top.get("symbol")}
localization_score={top.get("localization_score")}
localization_strength={top.get("localization_strength")}
score_semantics={LOCALIZATION_SCORE_SEMANTICS}
localization_reasons={top.get("localization_reasons", [])}

[DEFECT GROUNDING]
defect_established={candidate_state.get("defect_established", False)}
patch_basis={candidate_state.get("patch_basis", "none")}
failure_binding_kind={candidate_state.get("failure_binding_kind", "unavailable")}
exact_source_grounded={candidate_state.get("exact_source_grounded", False)}
recommended_action={candidate_state.get("recommended_action", "needs_grounding")}
auto_patch_candidate_allowed=false

[RELATED CONTEXT — INSPECTION ONLY]
{related_block}

[PHANTOM LIMB SUGGESTIONS - structural hints, not proof]
{phantom_block}
{linter_hints_block}{lessons_block}{anti_lessons_block}
[USER]
{user_query}

[RULES]
- Localization rank is useful for inspection only; it is not defect probability.
- Do not infer a defect from lexical overlap, callers, topology, trace proximity, or score magnitude.
- A validation command, a passing validation, or an inconclusive validation establishes no defect.
- Return no patch candidate and request grounding; do not claim write or apply authority.
- Return ONLY valid JSON matching this schema:
{PATCH_RESPONSE_SCHEMA}
- Set patch_candidate=null, patch_plan=null, confidence=0.0, and needs_escalation=true.
""".strip()

    # A receipt that proved same-file compiler errors but cannot safely bind
    # every one of them may not be presented as a complete repair problem.
    # This does not alter PATCH.BASIS, PATCH.AUTHOR or PATCH.MINIMAL; it stops
    # before the existing authoring call with an explicit typed scope result.
    if (
        repair_scope.status != REPAIR_SCOPE_NOT_APPLICABLE
        and repair_scope.status != REPAIR_SCOPE_COMPLETE
    ):
        return f"""\
Measured compiler evidence cannot be safely represented as a bounded repair scope.

[MEASURED REPAIR SCOPE]
{json.dumps(repair_scope.as_dict(), ensure_ascii=False, indent=2)}

[RULES]
- Do not infer additional definitions from nearby source, sibling methods, model suggestions, or graph context.
- Return no patch candidate because the authoritative compiler receipt is incomplete for repair-scope purposes.
- Return ONLY valid JSON matching this schema:
{PATCH_RESPONSE_SCHEMA}
- Set patch_candidate=null, patch_plan=null, confidence=0.0, and needs_escalation=true.
""".strip()

    # ============================================================
    # 1. Feature-extension branch
    # ============================================================
    # Important:
    # - Feature tasks should NOT be forced to patch CONTROL's top hypothesis.
    # - Scout/related snippets are the primary source of truth.
    # - safe_minimal cannot create files or coordinate multi-file feature work.
    if is_feature_extension and style == "safe_minimal":
        return f"""\
This is a feature-extension task, but current patch style is safe_minimal.
safe_minimal forbids multi-file edits and new files.


Return ONLY valid JSON:
{{
  "summary": "Feature extension requires balanced or vibe patch style.",
  "issues": [
    {{
      "severity": "medium",
      "type": "policy",
      "file": "",
      "symbol": "",
      "reason": "safe_minimal mode cannot safely create new modules or coordinate multi-file edits for this feature task.",
      "fix": "Switch vibecoding style to balanced or vibe."
    }}
  ],
  "patch_candidate": null,
  "patch_plan": null,
  "confidence": 0.0,
  "needs_escalation": true
}}
""".strip()

    if is_feature_extension or explicit_change_route:
        request_type = "explicit_change_request" if explicit_change_route else "feature_extension"
        obligations = (live_route or {}).get("obligations") or []
        change_need_block = f"""\
[CHANGE NEED — WAITER.LIVE.1]
change_need_source={candidate_state.get("change_need_source", "unresolved")}
defect_established={candidate_state.get("defect_established", False)}
patch_basis={candidate_state.get("patch_basis", "none")}
The user explicitly asked for this change. That establishes why a change is
needed. It does not establish a defect, a target, a correct patch, write
authority or apply authority — those remain with patch safety, CTX and the
existing authorization gates.

[REQUESTED OBLIGATIONS — preserved in the order the user wrote them]
{chr(10).join(f"{index}. {item}" for index, item in enumerate(obligations, start=1)) or "1. " + user_query[:240]}
""" if explicit_change_route else ""
        return f"""\
You are a verifier/patch writer inside an agentic coding system.

[STYLE & CONSTRAINTS — authoritative]
{policy_block}

{output_format_block}

[REPO STYLE HINT — lower priority than correctness]
{code_dna_block}

[STYLE RULE]
- Match repo style when writing patched_snippet: indentation, naming convention, brace/comment style.
- Correctness > grounding > validation > style.

[REQUEST TYPE]
{request_type}
{change_need_block}
[SCOUT RESULT — navigation hint]
{json.dumps(scout, ensure_ascii=False, indent=2)}

[CONTROL WARNING]
The CONTROL top hypothesis may be unrelated because this is a requested change, not a localized bug fix.
Do not use the top hypothesis as the patch target unless it is directly relevant to the requested change.

[RELATED SOURCE CONTEXT — patchable source]
{related_block}

[PHANTOM LIMB SUGGESTIONS - structural hints, not proof]
{phantom_block}
{linter_hints_block}{lessons_block}{anti_lessons_block}
[USER]
{user_query}

[RULES]
- This is a requested change, not a defect repair. Do not claim a defect exists.
- The patch basis is explicit_change_request; it grants no write/apply authority.
- Deliver the change the user asked for; do not reduce it to one suspicious symbol.
- Use Scout and RELATED SOURCE CONTEXT as the primary source of truth.
- You may patch files shown in RELATED SOURCE CONTEXT.
- For every replace_snippet operation, target_snippet must be copied verbatim from RELATED SOURCE CONTEXT.
- Do not invent files, functions, structs, methods, imports, modules, or dependencies not shown.
- Do not say project context is missing if RELATED SOURCE CONTEXT contains source files.
- If multi-file edits or new files are needed, use patch_plan.
- If the safest change is single-file, use patch_candidate.
- Keep the patch minimal and cargo-check safe.
- Prefer existing project style and existing error handling patterns.
- Do not reuse unrelated data structures as AML/blacklist storage unless the source code explicitly shows that purpose.
- Do not invent global accessors such as get_avl_root().
- Prefer a minimal self-contained AML module or a local check over wiring through unrelated structures.
- A comment is not an implementation. The patch must actually enforce the AML decision before mutation.
- Repo style hints are lower priority than correctness, grounding, and validation.
- Return ONLY valid JSON matching this schema:
{PATCH_RESPONSE_SCHEMA}

[PREFLIGHT VALIDATION]
{json.dumps(preflight, ensure_ascii=False, indent=2)}
""".strip()

    # ============================================================
    # 2. Non-feature missing-source guard
    # ============================================================
    # For normal bug-fix tasks, CONTROL must have exact source_snippet.
    if not patch_intent.get("source_snippet"):
        return f"""\
CONTROL ENGINE RESULT indicates missing source snippet.

User query:
{user_query}

Return ONLY valid JSON:
{{
  "summary": "Cannot safely generate patch because CONTROL did not provide an exact source snippet.",
  "issues": [
    {{
      "severity": "high",
      "type": "context",
      "file": "",
      "symbol": "",
      "reason": "No exact source_snippet was available for the localized patch target.",
      "fix": "Collect more context or improve CONTROL/source extraction before patching."
    }}
  ],
  "patch_candidate": null,
  "patch_plan": null,
  "confidence": 0.0,
  "needs_escalation": true
}}
""".strip()

    # ============================================================
    # 3. Normal localized bug-fix branch
    # ============================================================
    unknown_language_rule = ""
    if language == "unknown":
        unknown_language_rule = """
Language is unknown. Infer likely language only for analysis.
Do not invent syntax or APIs. Do not propose a patch unless source_snippet is exact and sufficient.
""".strip()

    # PATCH.AUTHOR.LIVE.2 — the candidate-language constraints, from the one
    # producer that also renders them for the verification-guided revision
    # author.  The safe_minimal/balanced/vibe dispatch that used to sit inline
    # here is unchanged; it simply has a single definition now.
    style_constraints = contract.candidate_language_block

    reasons_raw = top.get("reasons") or []
    if isinstance(reasons_raw, list):
        reasons = "; ".join(str(r)[:80] for r in reasons_raw[:3])
    else:
        reasons = str(reasons_raw)[:240]

    target_file = patch_intent.get("file") or patch_intent.get("relative_path") or ""
    target_symbol = (
        patch_intent.get("target_node_name")
        or patch_intent.get("target_symbol")
        or ""
    )
    target_kind = patch_intent.get("target_node_kind") or "function"
    source_snippet = patch_intent.get("source_snippet") or ""

    target_quote_rule = "Use source_snippet as target_snippet verbatim."
    primary_scope_rule = "PATCH TARGET remains the primary grounded target and must remain included."
    if authoring_context.authoring_repair_scope is not None and len(repair_scope.members) > 1:
        target_quote_rule = "For multi-member edits, quote replacement_envelope.original_snippet verbatim as target_snippet and replace that same envelope."
        primary_scope_rule = "PATCH TARGET remains the primary grounded target; editing every member is not required."

    return f"""\
You are a verifier/patch writer inside an agentic coding system.

[STYLE & CONSTRAINTS — authoritative, overrides later rules]
{policy_block}

{style_constraints}

{scope_text}

[REPO STYLE HINT — lower priority than correctness]
{code_dna_block}

[STYLE RULE]
- Match repo style when writing patched_snippet: indentation, naming convention, brace/comment style.
- Correctness > grounding > validation > style.

{output_format_block}

[CONTROL]
symbol={top.get("symbol")}
issue_hint={top.get("likely_issue")}
localization_score={top.get("localization_score")}
localization_strength={top.get("localization_strength")}
confidence_kind={top.get("confidence_kind")}
defect_established={candidate_state.get("defect_established", False)}
action={top.get("recommended_action")}
language={language}
localization_reasons={reasons}
{unknown_language_rule}

[PATCH TARGET]
file={target_file}
symbol={target_symbol}
kind={target_kind}

source_snippet:
```{language}
{source_snippet}
```

{repair_scope_prompt}

{oop_attachment.prompt}

[RELATED CONTEXT — evidence only, do not patch directly unless PATCH TARGET changes]
{related_block}

[PHANTOM LIMB SUGGESTIONS - structural hints, not proof]
{phantom_block}
{linter_hints_block}{lessons_block}{anti_lessons_block}
[USER]
{user_query}

[RULES]

Style block above is authoritative.
{target_quote_rule}
Make the smallest edit that satisfies constraints.
{primary_scope_rule}
When [MEASURED REPAIR SCOPE] is present, its exact members are the only
additional same-file definitions the compiler receipt grounds for this repair.
Do not add a file or definition because it is adjacent, a sibling, or otherwise
appears related.  The source and diagnostics in that section are authoritative.
Do not invent identifiers unless style explicitly permits it.
If source does not support a safe fix, return patch_candidate=null and needs_escalation=true.
Only a genuine executed preflight failure may ground a defect; inconclusive or passing validation may not.
Fix compile/build errors before guessing runtime/gameplay logic.
Do not speculate about architecture or behavior until compiler/runtime errors are resolved.
If preflight stack trace points to a callee and the current source_snippet is the caller, infer the smallest caller-side fix first.
For TypeError caused by primitive/object argument mismatch, prefer reordering existing arguments before changing function bodies.
If the patch can be made by reordering identifiers already present in source_snippet, it is allowed in safe_minimal.
RELATED CONTEXT is evidence only for normal bug-fix tasks.
Use RELATED CONTEXT to verify callees, signatures, tests, and stack traces.
Return ONLY valid JSON matching this schema:
{PATCH_RESPONSE_SCHEMA}

[PREFLIGHT VALIDATION]
{json.dumps(preflight, ensure_ascii=False, indent=2)}
""".strip()

def allow_create_file(patch_style: str) -> bool:
    return patch_style in {"balanced", "vibe"}

def build_control_prompt_human(control_result: dict, user_query: str) -> str:
    control_result = refresh_control_safety(control_result)
    context_profile = (
        control_result.get("context_profile")
        or infer_context_profile(control_result.get("query") or user_query)
    )
    identity_framing = identity_answer_framing(
        user_query,
        profile=context_profile,
    )
    top = control_result.get("top_hypothesis") or {}
    reasons_raw = top.get("reasons") or []
    reasons = "; ".join(
        str(r)[:80] for r in (reasons_raw[:3] if isinstance(reasons_raw, list) else [reasons_raw])
    )
    patch_intent = control_result.get("patch_intent") or {}
    snippet = patch_intent.get("source_snippet") or ""
    candidate_state = control_result.get("patch_candidate_state") or {}
    if identity_framing:
        entry_nodes = "\n".join(
            f"- {node}" for node in control_result.get("entry_nodes", [])[:8]
        )
        evidence = "\n".join(
            f"- {item.get('symbol')}" for item in control_result.get("evidence", [])[:8]
        )
        return f"""\
{identity_framing}

[CONTROL]
top_symbol={top.get("symbol")}
localization_score={top.get("localization_score")}
localization_strength={top.get("localization_strength")}
defect_established={(control_result.get("patch_candidate_state") or {}).get("defect_established", False)}
localization_reasons: {reasons}

[AUTHORITATIVE / SUPPORTING CONTEXT]
entry_nodes:
{entry_nodes or "- none"}

evidence:
{evidence or "- none"}

[SOURCE EXCERPT]
{snippet}

[QUESTION]
{user_query}

Your job:
1. Explain what C.A.T.T.U.S is as a product/workspace first.
2. Then summarize the major subsystems supported by the context.
3. Include repair, patching, and benchmarks as parts of the system, without making them the whole identity.
4. Do not invent features that are not present in the provided context.

Plain natural language. No JSON.
"""

    human_task = (
        """1. Explain what the grounded failure evidence establishes and why the bug occurs.
2. Walk through the execution flow briefly.
3. Suggest a fix (with code if helpful).
4. Highlight the exact grounded problematic line."""
        if candidate_state.get("defect_established")
        else """1. Explain why this is the highest-ranked localization candidate.
2. State clearly that no defect has been established at this candidate.
3. Describe what evidence or source inspection would be needed next.
4. Do not claim an exact problematic line or warranted patch from rank alone."""
    )

    return f"""\
You are explaining a bug to a human learner.

[CONTROL LOCALIZATION] symbol={top.get("symbol")} | issue_hint={top.get("likely_issue")} | localization_score={top.get("localization_score")}
defect_established={(control_result.get("patch_candidate_state") or {}).get("defect_established", False)}
localization_reasons: {reasons}

[CODE]
{snippet}

[QUESTION]
{user_query}

Your job:
{human_task}

Plain natural language. No JSON.
"""

def get_patch_payload(json_block: dict | None) -> dict:
    if not json_block:
        return {"kind": "none"}

    if isinstance(json_block.get("patch_candidate"), dict):
        return {
            "kind": "single",
            "patch": json_block["patch_candidate"],
        }

    if isinstance(json_block.get("patch_plan"), list):
        return {
            "kind": "plan",
            "patches": json_block["patch_plan"],
        }

    return {"kind": "none"}

def infer_file_from_symbol(symbol: str) -> str | None:
    if not symbol:
        return None

    head = symbol.split("::", 1)[0]

    # Plain file node, e.g. inventory.cpp
    if Path(head).suffix:
        return head

    if "::" not in symbol:
        return None

    file_part = symbol.split("::", 1)[0]

    if Path(file_part).suffix:
        return file_part

    return f"{file_part}.py"


def infer_name_from_symbol(symbol: str) -> str | None:
    if not symbol:
        return None
    return symbol.split("::")[-1]


def infer_symbol_from_query_in_file(repo_path: str, rel_file: str, query: str) -> str | None:
    path = Path(repo_path) / rel_file
    if not path.exists():
        return None

    text = path.read_text(encoding="utf-8", errors="replace")
    words = query_words(query)

    candidates = []
    for m in re.finditer(
        r"\b(?:bool|int|void|float|double|string|std::string|auto)\s+"
        r"(?:[A-Za-z_][A-Za-z_0-9]*::)?"
        r"([A-Za-z_][A-Za-z_0-9]*)\s*\([^;{}]*\)\s*(?:const\s*)?\{",
        text,
    ):
        name = m.group(1)
        if name in {"if", "for", "while", "switch"}:
            continue

        score = 0
        if name.lower() in words:
            score += 10
        if any(w in name.lower() for w in words):
            score += 3

        candidates.append((score, name))

    candidates.sort(reverse=True)
    if candidates and candidates[0][0] > 0:
        return candidates[0][1]

    return candidates[0][1] if candidates else None


def _patterns_for_language(symbol_name: str, ext: str) -> list[str]:
    """Return symbol-definition regexes appropriate for the file extension.

    Each language has slightly different syntax. We use a language-aware list
    so that, for example, C# Allman braces or Rust `fn` keyword get matched
    instead of falling through to a generic pattern that misses everything.
    """
    n = re.escape(symbol_name)

    # Common cross-language fallbacks (always included).
    common = [
        rf"\bclass\s+{n}\b",
        rf"\bstruct\s+{n}\b",
        rf"\benum\s+{n}\b",
        rf"\binterface\s+{n}\b",
    ]

    if ext == ".py":
        return common + [
            rf"^\s*def\s+{n}\s*\(",
            rf"^\s*async\s+def\s+{n}\s*\(",
        ]

    if ext in {".cs"}:
        # C# methods: optional modifiers, optional <generics>, return type, name, params.
        modifiers = r"(?:public|private|protected|internal|static|virtual|override|sealed|abstract|async|unsafe|partial|extern|new|readonly|const|\s)*"
        return common + [
            # `[Attr] public static Task<int> Update<T>(...)`
            rf"^\s*(?:\[[^\]]*\]\s*)*{modifiers}[\w<>,\[\]\s\?]*?\b{n}\s*(?:<[\w,\s]+>)?\s*\(",
            # Constructor: `public Game(...)`
            rf"^\s*(?:\[[^\]]*\]\s*)*{modifiers}\b{n}\s*\(",
            # Property: `public int Update { get; set; }`
            rf"^\s*(?:\[[^\]]*\]\s*)*{modifiers}[\w<>,\[\]\s\?]+\b{n}\s*\{{",
        ]

    if ext == ".rs":
        return common + [
            rf"^\s*(?:pub\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+{n}\s*[(<]",
            rf"^\s*impl\s+{n}\b",
            rf"^\s*trait\s+{n}\b",
            rf"^\s*type\s+{n}\b",
        ]

    if ext in {".ts", ".tsx", ".js", ".jsx"}:
        return common + [
            rf"\bfunction\s*\*?\s+{n}\s*\(",
            rf"\bexport\s+(?:default\s+)?(?:async\s+)?function\s*\*?\s+{n}\s*\(",
            rf"\b{n}\s*=\s*(?:async\s*)?\(.*?\)\s*=>",
            rf"\b{n}\s*:\s*(?:async\s*)?\(.*?\)\s*=>",
            rf"\b(?:public|private|protected|static|async)?\s*{n}\s*\(.*?\)\s*[:{{]",  # class method
        ]

    if ext in {".cpp", ".cc", ".cxx", ".c", ".h", ".hpp"}:
        # C/C++: return-type name(...) — possibly with class:: qualifier
        return common + [
            rf"\b{n}\s*\(.*?\)\s*(?:const)?\s*(?:noexcept)?\s*[{{]?\s*$",
            rf"::\s*{n}\s*\(",
        ]

    if ext == ".go":
        return common + [
            # `func Name(...)` and methods `func (r *Recv) Name(...)`
            rf"^\s*func\s+(?:\(.*?\)\s+)?{n}\s*\(",
            # Type declarations: `type Name struct { ... }`, `type Name interface { ... }`
            rf"^\s*type\s+{n}\b",
        ]

    if ext == ".java":
        # Java methods: optional annotations + visibility/static/etc + return type + name(args).
        modifiers = r"(?:public|private|protected|static|final|abstract|synchronized|native|default|\s)*"
        return common + [
            rf"^\s*(?:@\w+(?:\([^)]*\))?\s+)*{modifiers}[\w<>,\[\]\s\?]+?\b{n}\s*\(",
            # Constructor: same visibility rules but no return type.
            rf"^\s*(?:@\w+(?:\([^)]*\))?\s+)*{modifiers}\b{n}\s*\(",
            # Record/sealed class declarations.
            rf"^\s*(?:public|private|protected)?\s*(?:sealed\s+|final\s+|abstract\s+)*record\s+{n}\b",
        ]

    if ext in {".kt", ".kts"}:
        # Kotlin uses `fun`, with optional modifiers (suspend, inline, override, etc.)
        kotlin_mods = r"(?:public|private|protected|internal|open|override|final|abstract|sealed|inline|suspend|tailrec|operator|infix|external|\s)*"
        return common + [
            # `fun update()`, `suspend fun update()`, `inline override fun update()`
            rf"^\s*(?:@\w+(?:\([^)]*\))?\s+)*{kotlin_mods}fun(?:\s*<[^>]*>)?\s+{n}\s*[(<]",
            # Top-level / member val/var with explicit type for getters
            rf"^\s*{kotlin_mods}(?:val|var)\s+{n}\b",
            # Object declarations: `object Name { ... }`
            rf"^\s*{kotlin_mods}object\s+{n}\b",
            # `data class`, `sealed class`, etc. handled by `class\s+{n}` in common.
        ]

    # Generic fallback — best-effort, may have false positives.
    return common + [
        rf"\bfunction\s+{n}\s*\(",
        rf"\bdef\s+{n}\s*\(",
        rf"\bfn\s+{n}\s*[(<]",
        rf"\b{n}\s*\(.*?\)\s*\{{",
        rf"\b{n}\s*=\s*\(.*?\)\s*=>",
    ]

def extract_line_window(repo_path: str, rel_file: str, line: int, radius: int = 4) -> str:
    path = Path(repo_path) / rel_file
    if not path.exists():
        return ""

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return ""

    idx = max(0, line - 1)
    start = max(0, idx - radius)
    end = min(len(lines), idx + radius + 1)

    return "\n".join(lines[start:end]).strip()


def symbol_name_from_location(loc: dict) -> str | None:
    hint = loc.get("symbol_hint") or ""
    if hint:
        # Movement.move -> move
        name = hint.split(".")[-1]
        if name and name not in {"<anonymous>", "anonymous"}:
            return name

    return None

def extract_symbol_snippet(repo_path: str, rel_file: str, symbol_name: str) -> str:
    """Read the file, find the line that defines `symbol_name`, return the
    full block including the body. Language-aware so C#/Rust/Go also work."""
    path = Path(repo_path) / rel_file
    if not path.exists():
        return ""

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    ext = Path(rel_file).suffix.lower()
    patterns = _patterns_for_language(symbol_name, ext)

    start = None
    for i, line in enumerate(lines):
        if any(re.search(p, line) for p in patterns):
            start = i
            break

    if start is None:
        return ""

    # Brace-aware extractor that handles Allman style (brace on the next line).
    # We don't decide we're "inside" the block until we see the FIRST `{`,
    # so signatures with the body opener on a later line still extract correctly.
    snippet: list[str] = []
    brace_count = 0
    started_brace = False
    is_python = ext == ".py"


    for offset, line in enumerate(lines[start:start + 200]):
        snippet.append(line)

        if not is_python:
            brace_count += line.count("{")
            brace_count -= line.count("}")
            if "{" in line:
                started_brace = True
            if started_brace and brace_count <= 0:
                break
            # Safety: if we've read 30+ lines without finding a brace, the
            # match was probably a false positive (e.g., interface method
            # signature with no body).
            if not started_brace and len(snippet) >= 30:
                break
        else:
            # Python: indentation-based. Stop when we see a non-empty line
            # at indentation <= the def's, after we've read at least one body line.
            if offset == 0:
                continue
            stripped = line.strip()
            if stripped and not line.startswith((" ", "\t")):
                # Hit something at column 0 → previous block ended.
                snippet.pop()  # drop the line that started the next block
                break
            if len(snippet) >= 100:
                break

    return "\n".join(snippet).strip()


# --- PATCH.BASIS.TARGET.1: structural target-source grounding --------------
#
# Identifier length is not evidence.  A short spelling such as ``m1`` is a
# legitimate patch target when the repository's existing language-aware
# extractor structurally resolves exactly one definition for it inside the
# exact file already grounded, and the measured defect location - when one
# exists - belongs to that definition.  A short spelling that merely occurs in
# a comment, a string literal or another identifier still grounds nothing, and
# two plausible definitions are refused rather than guessed.

TARGET_GROUNDING_RESOLVED = "structurally_resolved"
TARGET_GROUNDING_NOT_FOUND = "not_found"
TARGET_GROUNDING_AMBIGUOUS = "ambiguous"
TARGET_GROUNDING_LOCATION_MISMATCH = "location_mismatch"
TARGET_GROUNDING_UNAVAILABLE = "structure_unavailable"
TARGET_GROUNDING_FILE_TARGET = "file_target"

#: Statuses where the structural extractor positively contradicts the target.
#: Every other status either proves the target or says nothing about it, and
#: saying nothing must leave the pre-existing behaviour exactly as it was.
TARGET_GROUNDING_REFUSES_TARGET = frozenset({
    TARGET_GROUNDING_NOT_FOUND,
    TARGET_GROUNDING_AMBIGUOUS,
    TARGET_GROUNDING_LOCATION_MISMATCH,
})

#: An unqualified single-token spelling, i.e. the shape the structural
#: extractor is able to name.  This is a *shape* test, never a length test:
#: ``f``, ``m1`` and ``calculate_total`` all pass it equally.
_SIMPLE_IDENTIFIER = re.compile(r"[^\W\d]\w*\Z", re.UNICODE)


def _structural_target_definition(
    definitions: list[dict],
    symbol_name: str,
    defect_line: int | None,
) -> tuple[str, dict | None, int]:
    """Pick at most one definition for ``symbol_name``, or refuse.

    Never "first match in file order wins": more than one plausible definition
    is ambiguous unless the measured defect location singles one out.
    """
    matches = [item for item in definitions if item.get("name") == symbol_name]
    if not matches:
        return TARGET_GROUNDING_NOT_FOUND, None, 0

    def owns(item: dict) -> bool:
        return item["start_line"] <= defect_line <= item["end_line"]

    if defect_line is not None:
        owning = [item for item in matches if owns(item)]
        if len(owning) == 1:
            return TARGET_GROUNDING_RESOLVED, owning[0], len(matches)
        if owning:
            # Nested or overlapping definitions share the line, so the location
            # does not single one out either.
            return TARGET_GROUNDING_AMBIGUOUS, None, len(matches)
        if any(owns(item) for item in definitions):
            # The spelling resolves, but the measured defect belongs to another
            # definition, so this source must not be bound to that defect.
            return TARGET_GROUNDING_LOCATION_MISMATCH, None, len(matches)
        # Otherwise the line lies outside every definition in the file - module
        # level, an import, a blank line, or past the end - so it discriminates
        # nothing and the structural result stands on its own.

    if len(matches) == 1:
        return TARGET_GROUNDING_RESOLVED, matches[0], 1
    return TARGET_GROUNDING_AMBIGUOUS, None, len(matches)


def ground_target_symbol(
    repo_path: str | None,
    rel_file: str | None,
    symbol_name: str | None,
    *,
    defect_location: dict | None = None,
) -> dict:
    """Structurally resolve an already-localized target inside its own file.

    Reads exactly the one named file - no walk, index, graph or retrieval - and
    asks the existing tree-sitter extractor which definitions it declares.  The
    returned ``status`` is one of the ``TARGET_GROUNDING_*`` constants;
    ``definition`` is populated only for ``structurally_resolved``.  This
    acquires no authority and decides no patch basis.
    """
    unavailable = {
        "status": TARGET_GROUNDING_UNAVAILABLE,
        "definition": None,
        "matches": 0,
    }
    if not symbol_name or not rel_file or not repo_path:
        return unavailable

    # A file node carries no symbol target.  File-only and no-symbol behaviour
    # is out of scope for this phase and passes straight through.
    if symbol_name == rel_file or symbol_name == Path(rel_file).stem:
        return {
            "status": TARGET_GROUNDING_FILE_TARGET,
            "definition": None,
            "matches": 0,
        }

    # A qualified or otherwise non-simple spelling (``Class::method``,
    # ``Outer.inner``) is a legacy target form the structural extractor never
    # names, so it yields no structural proof either way.
    if not _SIMPLE_IDENTIFIER.match(symbol_name):
        return unavailable

    try:
        path = Path(repo_path) / rel_file
        if not path.is_file():
            return unavailable
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return unavailable

    parsed = structural_definitions(text, infer_language_from_file(rel_file))
    if not parsed["available"]:
        # No structural extractor for this language: nothing is proven and
        # nothing is contradicted, so the pre-existing path is preserved.
        return unavailable

    defect_line = None
    if isinstance(defect_location, dict):
        line = defect_location.get("line")
        same_file = _normalized_control_path(
            defect_location.get("file")
        ) == _normalized_control_path(rel_file)
        if same_file and isinstance(line, int) and line > 0:
            defect_line = line

    status, definition, matches = _structural_target_definition(
        parsed["definitions"], symbol_name, defect_line
    )
    return {"status": status, "definition": definition, "matches": matches}


def build_patch_intent(
    control_result: dict,
    *,
    hypothesis: dict | None = None,
    defect_location: dict | None = None,
) -> dict:
    candidate = hypothesis or control_result.get("top_hypothesis") or {}
    symbol = candidate.get("symbol")
    repo_path = control_result.get("repo_path")

    rel_file = infer_file_from_symbol(symbol)
    symbol_name = infer_name_from_symbol(symbol)

    if rel_file and (not symbol_name or symbol_name == Path(rel_file).stem):
        guessed = infer_symbol_from_query_in_file(
            repo_path=repo_path,
            rel_file=rel_file,
            query=control_result.get("query", ""),
        )

        if guessed:
            symbol_name = guessed
            symbol = f"{rel_file}::{guessed}"

    target_grounding = ground_target_symbol(
        repo_path,
        rel_file,
        symbol_name,
        defect_location=defect_location,
    )

    if not symbol_name or target_grounding["status"] in TARGET_GROUNDING_REFUSES_TARGET:
        return {
            "target_file": None,
            "target_symbol": None,
            "target_symbol_full": symbol,
            "issue_type": candidate.get("likely_issue"),
            "confidence": candidate.get("confidence"),
            "confidence_kind": LOCALIZATION_CONFIDENCE_KIND,
            "localization_score": candidate.get("localization_score"),
            "recommended_action": "acquire_source_context",
            "source_snippet": "",
            "patch_rules": [],
            "language": infer_language_from_file(rel_file),
        }

    source_snippet = ""
    if repo_path and rel_file and symbol_name:
        source_snippet = extract_symbol_snippet(repo_path, rel_file, symbol_name)

    # Fallback: tree-sitter sometimes fails to name C/C++ symbols (e.g. when
    # the parser returns "unknown"), leaving symbol_name pointing at a
    # filename. If we have a real file but no snippet, regex-scan the file
    # for query-relevant function definitions.
    if not source_snippet and repo_path and rel_file and (
        not symbol_name or symbol_name == Path(rel_file).stem
    ):
        query = control_result.get("query") or ""
        fallback_name = infer_symbol_from_query_in_file(repo_path, rel_file, query)
        if fallback_name:
            fallback_snippet = extract_symbol_snippet(repo_path, rel_file, fallback_name)
            if fallback_snippet:
                symbol_name = fallback_name
                source_snippet = fallback_snippet
                print(f"🐛 DEBUG fallback symbol resolved: {fallback_name}")

    print("🐛 DEBUG target grounding:", target_grounding["status"])
    print("🐛 DEBUG symbol:", symbol)
    print("🐛 DEBUG file:", rel_file)
    print("🐛 DEBUG name:", symbol_name)
    print("🐛 DEBUG snippet:", source_snippet[:200])

    return {
        "file": rel_file,
        "relative_path": rel_file,
        "target_node_name": symbol_name,
        "target_node_kind": "function",
        "language": infer_language_from_file(rel_file),
        "target_file": rel_file,
        "target_symbol": symbol_name,
        "target_symbol_full": symbol,
        "issue_type": candidate.get("likely_issue"),
        "confidence": candidate.get("confidence"),
        "confidence_kind": LOCALIZATION_CONFIDENCE_KIND,
        "localization_score": candidate.get("localization_score"),
        "recommended_action": candidate.get("recommended_action"),
        "source_snippet": source_snippet,
        "patch_rules": [
            "Patch only the target symbol unless evidence proves otherwise.",
            "Use source_snippet as exact target_snippet.",
            "Make the smallest safe edit.",
            "Do not invent files, functions, or APIs.",
            "If source_snippet is empty, set needs_escalation=true.",
        ],
    }
