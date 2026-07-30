from __future__ import annotations
from pathlib import Path
import re
import os
import json
from typing import Any

from graph.builder import build_graph_from_repo
from graph.project_map import load_project_map
from graph.query import explain_symbol, impact_analysis
from graph.weights import NodeWeight, compute_node_weights, get_node_weight
from reasoning.deep_project_understand import deep_project_understand
from reasoning.reasoning_engine import analyze_symbol_risk
from core.retriever import trace_execution_flow
from core.repo_librarian import load_phantom_limb_report
from core.context_profiles import (
    identity_answer_framing,
    identity_prompt_hint,
    infer_context_profile,
    score_multiplier_for_path,
)
from config import LANGUAGE_MAP
from policy.decision_helper import build_patch_policy, policy_to_prompt_block

_graph_cache: dict[str, Any] = {}
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
) -> list[str]:
    graph = graph or get_cached_graph(
        repo_path,
        inventory=inventory,
    )
    print("🐛 DEBUG graph node count:", len(graph.nodes))
    print("🐛 DEBUG first graph nodes:", list(graph.nodes.keys())[:20])
    print("🐛 DEBUG query words:", query_words(query))

    project_map = load_project_map(repo_path)
    map_nodes = extract_hotspots_from_project_map(project_map, limit=limit)

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

    result: list[str] = []

    for raw in graph_nodes + map_nodes:
        resolved_nodes = resolve_symbol_to_graph_nodes(graph, raw, query=query, limit=3)

        if not resolved_nodes and raw in graph.nodes:
            resolved_nodes = [raw]

        for node in resolved_nodes:
            if node not in result:
                result.append(node)

    if not result:
        for node in fallback_entry_nodes_from_graph(graph, query, limit=limit):
            if node not in result:
                result.append(node)

    print("🐛 DEBUG entry_nodes:", result)

    return result[:limit]

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

    def dfs(symbol: str, depth: int):
        if depth > max_depth:
            return
        if symbol in visited:
            return
        if len(evidence) >= max_nodes:
            return

        visited.add(symbol)

        info = explain_symbol(graph, symbol)
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
            dfs(n, depth + 1)

    for node in entry_nodes:
        dfs(node, 0)

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

def infer_hypotheses(query: str, evidence: list[dict], execution_trace: str) -> list[dict]:
    hypotheses = []
    trace_lower = execution_trace.lower()

    for item in evidence[:8]:
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

        confidence = min(0.95, max(0.1, score / 25))
        if not reasons:
            confidence *= 0.5

        if item.get("depth", 0) > 1:
            confidence *= 0.9

        hypotheses.append({
            "symbol": symbol,
            "score": round(score, 2),
            "confidence": round(confidence, 2),
            "likely_issue": guess_issue_type(query, execution_trace),
            "reasons": reasons,
            "recommended_action": recommend_action(confidence, risk),
            "language": infer_language_from_file(infer_file_from_symbol(symbol)),
        })

    hypotheses.sort(key=lambda x: x["score"], reverse=True)
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


def recommend_action(confidence: float, risk: dict) -> str:
    risk_level = risk.get("risk_level", "low")

    if confidence >= 0.75 and risk_level == "low":
        return "auto_patch_candidate_allowed"

    if confidence >= 0.65 and risk_level in {"low", "medium"}:
        return "safe_patch_with_validation"

    if risk_level == "high":
        return "require_review_before_patch"

    return "collect_more_evidence"


def build_control_result(
    query: str,
    repo_path: str,
    entry_nodes: list[str],
    evidence: list[dict],
    execution_trace: str,
) -> dict:
    context_profile = infer_context_profile(query)
    hypotheses = infer_hypotheses(query, evidence, execution_trace)
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
        "version": "control_v4",
        "query": query,
        "repo_path": repo_path,
        "context_profile": context_profile,
        "entry_nodes": entry_nodes,
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
    return result


def format_control_context(result: dict) -> str:
    lines = []

    lines.append("=== CONTROL ENGINE CONTEXT ===")
    lines.append("")
    lines.append(f"Query: {result['query']}")
    lines.append(f"Repo: {result['repo_path']}")
    lines.append("")

    lines.append("## Top Hypothesis")
    top = result.get("top_hypothesis")
    if top:
        lines.append(f"- symbol: {top['symbol']}")
        lines.append(f"- likely_issue: {top['likely_issue']}")
        lines.append(f"- confidence: {top['confidence']}")
        lines.append(f"- recommended_action: {top['recommended_action']}")
        lines.append(f"- reasons: {top['reasons']}")
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

    lines.append("## Ranked Hypotheses")
    for h in result.get("hypotheses", []):
        lines.append(
            f"- {h['symbol']} | issue={h['likely_issue']} | "
            f"score={h['score']} | confidence={h['confidence']} | "
            f"action={h['recommended_action']}"
        )
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

    entry_nodes = select_entry_nodes(
        query=query,
        repo_path=repo_path,
        limit=6,
        graph=graph,
        inventory=inventory,
    )

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

def resolve_symbol_to_graph_nodes(graph, symbol: str, query: str = "", limit: int = 3) -> list[str]:
    if not symbol:
        return []

    # Already a real graph node id.
    if symbol in graph.nodes:
        return [symbol]

    words = query_words(query)
    name = symbol.split("::")[-1]

    matches = []
    for node_id, node in graph.nodes.items():
        if node_id.startswith("call::"):
            continue
        if "::expr::" in node_id:
            continue
        if "::" not in node_id:
            continue

        tail = node_id.split("::")[-1]
        if tail == name:
            score = relevance_bonus(node_id, words)

            # Prefer functions/methods over classes when query asks about calls/bugs.
            if getattr(node, "type", "") == "function":
                score += 2

            # Prefer entry-like names for game projects.
            if tail.lower() in {"update", "start", "main", "run"}:
                score += 2

            matches.append((score, node_id))

    matches.sort(key=lambda x: (-x[0], x[1]))
    return [node_id for _, node_id in matches[:limit]]

def fallback_entry_nodes_from_graph(graph, query: str, limit: int = 6) -> list[str]:
    words = query_words(query)
    profile = infer_context_profile(query)
    candidates = []

    for node_id, node in graph.nodes.items():
        if node_id.startswith("call::"):
            continue
        if "::expr::" in node_id:
            continue
        if "::" not in node_id:
            continue

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
    """Build a stark 'FORBIDDEN' block for safe_minimal mode.

    Lists the only identifiers the AI is allowed to use (those literally
    present in the source snippet) and reminds it that anything else is a
    hallucination. Reduces 'invented field' patches like `player.position`
    when only `player.speed` exists in the source.
    """
    if not source_snippet:
        return ""
    # Extract identifiers actually present so we can reflect them back at the AI.
    # This is a heuristic — strings/comments are filtered out crudely.
    cleaned = re.sub(r"//.*?$|/\*.*?\*/|\".*?\"|'.*?'", " ", source_snippet, flags=re.S | re.M)
    seen = sorted(set(re.findall(r"\b[A-Za-z_][A-Za-z_0-9]*\b", cleaned)))
    return f"""
SAFE_MINIMAL — HARD CONSTRAINTS:
You may ONLY reference identifiers that appear in the source_snippet below.
Identifiers visible in source: {seen}

FORBIDDEN in patched_snippet:
- Any field/method/class name not in the list above (e.g. `player.position` if only `player.speed` exists).
- New imports, new helper functions, new type declarations.
- Behavioural redesign — only fix the literal bug.

If a correct fix would require any of the above:
  set patch_candidate=null, confidence<=0.3, needs_escalation=true,
  and explain in `summary` what is missing from context.
""".strip()


def _patch_output_format_block(style: str) -> str:
    """Tell the AI when to use patch_candidate vs patch_plan.

    - safe_minimal: patch_candidate only — single-file edit, never create files.
    - balanced:     patch_candidate by default; patch_plan ALLOWED for feature work.
    - vibe:         patch_plan freely, but every path must stay inside the repo.

    Mirrors the split between the executor's snippet-replace path and the
    multi-file plan path. Putting this in the prompt prevents the AI from
    quietly cramming a multi-file change into a single patch_candidate.
    """
    common_shapes = """\
patch_candidate (single-file existing-code fix):
{
  "patch_candidate": {
    "file": "...",
    "relative_path": "...",
    "target_node_name": "...",
    "target_node_kind": "function|class",
    "target_snippet": "...",
    "patched_snippet": "..."
  }
}

patch_plan (multi-file or new-file work):
{
  "patch_plan": [
    {"op": "create_file",     "relative_path": "src/aml.rs", "content": "..."},
    {"op": "replace_snippet", "relative_path": "src/main.rs",
     "target_snippet": "mod agent;",
     "patched_snippet": "mod agent;\\nmod aml;"}
  ]
}

Rules:
- Output EITHER patch_candidate OR patch_plan, never both.
- Use patch_candidate only when editing one existing file.
- Use patch_plan when creating files, editing multiple files, or changing APIs across files.
- Every relative_path MUST stay inside the repo (no absolute paths, no '..').
- Every patch_candidate.target_snippet must be an exact quote from the target file.
- If it is not found, reject/demote the candidate before final result.
"""

    if style == "safe_minimal":
        return (
            "[PATCH OUTPUT FORMAT — safe_minimal]\n"
            "Use patch_candidate ONLY. Do NOT emit patch_plan. Do NOT create files.\n"
            "If the fix would require new files or multi-file changes, set\n"
            "patch_candidate=null and needs_escalation=true.\n\n"
            + common_shapes
            + "\nsafe_minimal-specific: patch_plan is FORBIDDEN. Single existing file or escalate."
        )

    if style == "balanced":
        return (
            "[PATCH OUTPUT FORMAT — balanced]\n"
            "Prefer patch_candidate. Use patch_plan ONLY when feature work genuinely\n"
            "requires touching multiple files or creating a new file. Justify in `summary`.\n\n"
            + common_shapes
            + "\nbalanced-specific: patch_plan allowed but every op must reference an existing\n"
              "module/API or be clearly justified. Bias toward smaller patch_candidate when possible."
        )

    # vibe
    return (
        "[PATCH OUTPUT FORMAT — vibe]\n"
        "Use whichever shape best fits the change. patch_plan is encouraged for feature work,\n"
        "refactors across files, or anything that needs new helpers. List every assumption in `summary`.\n\n"
        + common_shapes
        + "\nvibe-specific: patch_plan freely usable, but every relative_path MUST stay inside\n"
          "the repo. Auto-apply is disabled — the user will review your plan."
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
) -> str:
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
    related_snippets = control_result.get("related_snippets") or []
    scout = control_result.get("scout") or {}
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
        control_confidence=float(top.get("confidence", 0.0) or 0.0),
    )

    policy_block = policy_to_prompt_block(policy)
    style = policy.style
    output_format_block = _patch_output_format_block(style)

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

    if identity_framing:
        source_excerpt = patch_intent.get("source_snippet") or "No source excerpt."
        return f"""\
{identity_framing}

[CONTROL CONTEXT]
top_symbol={top.get("symbol")}
confidence={top.get("confidence")}
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

    if is_feature_extension:
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
feature_extension

[SCOUT RESULT — navigation hint]
{json.dumps(scout, ensure_ascii=False, indent=2)}

[CONTROL WARNING]
The CONTROL top hypothesis may be unrelated because this is a feature-extension task, not a localized bug fix.
Do not use the top hypothesis as the patch target unless it is directly relevant to the requested feature.

[RELATED SOURCE CONTEXT — patchable source]
{related_block}

[PHANTOM LIMB SUGGESTIONS - structural hints, not proof]
{phantom_block}
{linter_hints_block}{lessons_block}{anti_lessons_block}
[USER]
{user_query}

[RULES]
- This is a feature-extension task.
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

    style_constraints = ""
    if style == "safe_minimal":
        style_constraints = _safe_minimal_forbidden_block(
            patch_intent.get("source_snippet", "")
        )
    elif style == "balanced":
        style_constraints = (
            "BALANCED: design-level fixes allowed, but every identifier in patched_snippet "
            "must be either in source_snippet OR a clearly-existing API shown in RELATED CONTEXT. "
            "If you need a new field/method on a user-defined type, set needs_escalation=true."
        )
    else:
        style_constraints = (
            "VIBE: creative fixes allowed. You MAY introduce new helpers/fields, but mark each "
            "assumption explicitly in summary. auto_apply will be disabled — produce a reviewable patch."
        )

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

    return f"""\
You are a verifier/patch writer inside an agentic coding system.

[STYLE & CONSTRAINTS — authoritative, overrides later rules]
{policy_block}

{style_constraints}

[REPO STYLE HINT — lower priority than correctness]
{code_dna_block}

[STYLE RULE]
- Match repo style when writing patched_snippet: indentation, naming convention, brace/comment style.
- Correctness > grounding > validation > style.

{output_format_block}

[CONTROL]
symbol={top.get("symbol")}
issue={top.get("likely_issue")}
confidence={top.get("confidence")}
action={top.get("recommended_action")}
language={language}
reasons={reasons}
{unknown_language_rule}

[PATCH TARGET]
file={target_file}
symbol={target_symbol}
kind={target_kind}

source_snippet:
```{language}
{source_snippet}
```

[RELATED CONTEXT — evidence only, do not patch directly unless PATCH TARGET changes]
{related_block}

[PHANTOM LIMB SUGGESTIONS - structural hints, not proof]
{phantom_block}
{linter_hints_block}{lessons_block}{anti_lessons_block}
[USER]
{user_query}

[RULES]

Style block above is authoritative.
Use source_snippet as target_snippet verbatim.
Make the smallest edit that satisfies constraints.
Do not invent identifiers unless style explicitly permits it.
If source does not support a safe fix, return patch_candidate=null and needs_escalation=true.
If preflight_validation ran and failed, treat it as the strongest evidence.
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
confidence={top.get("confidence")}
reasons: {reasons}

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

    return f"""\
You are explaining a bug to a human learner.

[CONTROL] symbol={top.get("symbol")} | issue={top.get("likely_issue")} | conf={top.get("confidence")}
reasons: {reasons}

[CODE]
{snippet}

[QUESTION]
{user_query}

Your job:
1. Explain what is happening and why the bug occurs.
2. Walk through the execution flow briefly.
3. Suggest a fix (with code if helpful).
4. Highlight the exact problematic line.

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


def build_patch_intent(control_result: dict) -> dict:
    top = control_result.get("top_hypothesis") or {}
    symbol = top.get("symbol")
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

    if not symbol_name or len(symbol_name) < 3:
        return {
            "target_file": None,
            "target_symbol": None,
            "target_symbol_full": symbol,
            "issue_type": top.get("likely_issue"),
            "confidence": top.get("confidence"),
            "recommended_action": "collect_more_evidence",
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
    if not source_snippet and repo_path and rel_file:
        query = control_result.get("query") or ""
        fallback_name = infer_symbol_from_query_in_file(repo_path, rel_file, query)
        if fallback_name:
            fallback_snippet = extract_symbol_snippet(repo_path, rel_file, fallback_name)
            if fallback_snippet:
                symbol_name = fallback_name
                source_snippet = fallback_snippet
                print(f"🐛 DEBUG fallback symbol resolved: {fallback_name}")

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
        "issue_type": top.get("likely_issue"),
        "confidence": top.get("confidence"),
        "recommended_action": top.get("recommended_action"),
        "source_snippet": source_snippet,
        "patch_rules": [
            "Patch only the target symbol unless evidence proves otherwise.",
            "Use source_snippet as exact target_snippet.",
            "Make the smallest safe edit.",
            "Do not invent files, functions, or APIs.",
            "If source_snippet is empty, set needs_escalation=true.",
        ],
    }
