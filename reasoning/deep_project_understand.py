from __future__ import annotations
from typing import Any

from graph.builder import build_graph_from_repo
from graph.query import explain_symbol, impact_analysis, trace_path


_graph_cache = {}


def get_cached_graph(repo_path: str, *, inventory=None):
    if inventory is not None:
        from core.repository_inventory import (
            validate_repository_inventory,
        )

        validate_repository_inventory(repo_path, inventory)
        # A new operation inventory invalidates the authority of any graph
        # left in the compatibility cache by a previous operation, and its
        # graph remains request-local.
        return build_graph_from_repo(
            repo_path,
            inventory=inventory,
        )
    if repo_path not in _graph_cache:
        _graph_cache[repo_path] = build_graph_from_repo(
            repo_path,
            inventory=inventory,
        )
    return _graph_cache[repo_path]


def clear_graph_cache(repo_path: str | None = None) -> None:
    """Invalidate this module's graph cache (Phase 13.1).

    Keyed by the raw ``repo_path``, mirroring ``get_cached_graph``. Passing
    ``None`` clears everything; popping a missing key is a no-op, so repeated
    clearing is safe.
    """
    if repo_path is None:
        _graph_cache.clear()
        return
    _graph_cache.pop(repo_path, None)


def extract_symbol_candidates(query: str) -> list[str]:
    import re

    stop_words = {
        "the", "a", "an", "and", "or", "to", "from", "in", "on", "for", "with",
        "is", "are", "was", "were", "why", "how", "what", "where", "when",
        "this", "that", "it", "of", "not", "bug", "fix",
    }

    result = []
    seen = set()

    for c in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", query):
        low = c.lower()
        if len(c) < 2 or low in stop_words or low in seen:
            continue
        seen.add(low)
        result.append(c)

    return result[:12]


def expand_candidates(words: list[str]) -> list[str]:
    expanded = set(words)

    for w in words:
        expanded.add(w.lower())
        expanded.add(w.capitalize())

    return list(expanded)


def deep_project_understand(
    query: str,
    repo_path: str,
    *,
    graph=None,
    inventory=None,
) -> dict[str, Any]:
    if inventory is not None:
        from core.repository_inventory import (
            validate_repository_inventory,
        )

        validate_repository_inventory(repo_path, inventory)
    graph = graph or get_cached_graph(
        repo_path,
        inventory=inventory,
    )

    candidates = expand_candidates(extract_symbol_candidates(query))

    if "move" in query.lower():
        candidates.append("Move")

    findings = []

    for name in candidates:
        info = explain_symbol(graph, name)
        impact = impact_analysis(graph, name)
        paths = trace_path(graph, name, name)

        if not (info["called_by"] or info["calls"] or impact or paths):
            continue

        findings.append({
            "symbol": name,
            "called_by": info["called_by"],
            "calls": info["calls"],
            "impact": impact,
            "paths": paths[:3],
        })

    return {
        "query": query,
        "repo_path": repo_path,
        "graph": {
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
        },
        "findings": findings,
    }
