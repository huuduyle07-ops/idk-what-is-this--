"""Phase 12.11 - Scope-Aware Evidence Spread.

Query-time, deterministic scoring that understands the *bounded scope* of a
possible change: it spreads relevance from seed nodes (direct query/file
matches, provided target/validation/linter locations) through a few graph
neighbors, so the agent inspects callers/callees/tests/same-file symbols rather
than only the exact snippet.

Architecture rule under test: base graph weights are NEVER mutated; spread is
query-time only.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph.schema import build_graph
from graph.weights import compute_node_weights
from graph.evidence_spread import (
    ChangeScopeAssessment,
    SpreadScore,
    assess_change_scope,
    compute_scope_aware_spread,
    format_spread_explanation,
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _by_id(scores):
    return {s.node_id: s for s in scores}


def _chain_graph():
    """fib -> helper (d1) -> helper2 (d2) -> helper3 (d3), all via calls."""
    nodes = [
        {"id": "target.py", "type": "file", "label": "target.py"},
        {"id": "target.py::fib", "type": "function", "label": "fib"},
        {"id": "target.py::helper", "type": "function", "label": "helper"},
        {"id": "target.py::helper2", "type": "function", "label": "helper2"},
        {"id": "target.py::helper3", "type": "function", "label": "helper3"},
    ]
    edges = [
        {"source": "target.py", "target": "target.py::fib", "type": "contains"},
        {"source": "target.py::fib", "target": "target.py::helper", "type": "calls"},
        {"source": "target.py::helper", "target": "target.py::helper2", "type": "calls"},
        {"source": "target.py::helper2", "target": "target.py::helper3", "type": "calls"},
    ]
    return build_graph(nodes, edges)


# --------------------------------------------------------------------------
# Distance-based boost (tests 1-5)
# --------------------------------------------------------------------------

def test_direct_query_seed_gets_distance_zero_boost():
    graph = _chain_graph()
    scores = _by_id(compute_scope_aware_spread(graph, "optimize fib"))
    fib = scores["target.py::fib"]
    assert fib.distance == 0
    assert fib.spread_boost == 1.0
    assert fib.query_score > 0


def test_distance_one_neighbor_gets_smaller_boost():
    graph = _chain_graph()
    scores = _by_id(compute_scope_aware_spread(graph, "optimize fib"))
    helper = scores["target.py::helper"]
    assert helper.distance == 1
    assert helper.spread_boost == 0.4
    assert scores["target.py::fib"].spread_boost > helper.spread_boost


def test_distance_two_neighbor_smaller_than_distance_one():
    graph = _chain_graph()
    scores = _by_id(compute_scope_aware_spread(graph, "optimize fib"))
    d1 = scores["target.py::helper"].spread_boost
    d2 = scores["target.py::helper2"].spread_boost
    assert d2 == 0.15
    assert d2 < d1


def test_distance_three_node_receives_no_boost():
    graph = _chain_graph()
    scores = _by_id(compute_scope_aware_spread(graph, "optimize fib", max_distance=2))
    d3 = scores["target.py::helper3"]
    assert d3.spread_boost == 0.0
    assert d3.distance is None


def test_spread_boost_is_capped():
    graph = _chain_graph()
    scores = _by_id(compute_scope_aware_spread(graph, "optimize fib", cap=0.5))
    # The seed would otherwise get 1.0; the cap clamps it.
    assert scores["target.py::fib"].spread_boost == 0.5


# --------------------------------------------------------------------------
# Inspectable reasons (test 6)
# --------------------------------------------------------------------------

def test_reasons_include_source_seed_and_distance():
    graph = _chain_graph()
    scores = _by_id(compute_scope_aware_spread(graph, "optimize fib"))
    helper = scores["target.py::helper"]
    joined = " | ".join(helper.reasons)
    assert "distance-1" in joined
    assert "target.py::fib" in joined
    assert helper.seed_nodes == ["target.py::fib"]


def test_seed_reason_distinguishes_file_vs_symbol_match():
    graph = _chain_graph()
    scores = _by_id(compute_scope_aware_spread(graph, "look at target.py please"))
    file_node = scores["target.py"]
    assert file_node.distance == 0
    assert any("file path match" in r for r in file_node.reasons)


# --------------------------------------------------------------------------
# Hub suppression (test 7)
# --------------------------------------------------------------------------

def test_utility_hub_does_not_outrank_direct_query_match():
    nodes = [
        {"id": "target.py", "type": "file", "label": "target.py"},
        {"id": "target.py::fib", "type": "function", "label": "fib"},
        {"id": "util.py", "type": "file", "label": "util.py"},
        {"id": "util.py::log", "type": "function", "label": "log"},
    ]
    edges = [{"source": "target.py", "target": "target.py::fib", "type": "contains"}]
    # Make util.py::log a high-degree hub: many callers point at it.
    for i in range(6):
        caller = f"mod{i}.py::caller{i}"
        nodes.append({"id": caller, "type": "function", "label": f"caller{i}"})
        edges.append({"source": caller, "target": "util.py::log", "type": "calls"})

    graph = build_graph(nodes, edges)
    # Give the hub a large global base weight (as the real graph would for a
    # high in-degree utility) and the target a small one, via the documented
    # base_weights parameter.
    base = {"util.py::log": 5.0, "target.py::fib": 0.2}
    scores = _by_id(
        compute_scope_aware_spread(graph, "optimize fib", base_weights=base)
    )

    fib = scores["target.py::fib"]
    log = scores["util.py::log"]
    # The hub has a large base weight, but with no direct query match it must
    # not outrank the direct target.
    assert log.base_score > fib.base_score
    assert fib.final_score > log.final_score
    assert any("hub" in r.lower() for r in log.reasons)


# --------------------------------------------------------------------------
# Scope assessment (tests 8-10)
# --------------------------------------------------------------------------

def _assess_for(graph, query, target):
    scores = compute_scope_aware_spread(graph, query)
    return assess_change_scope(scores, graph=graph, target_node=target)


def test_cross_file_caller_produces_cross_file_impact():
    nodes = [
        {"id": "target.py", "type": "file", "label": "target.py"},
        {"id": "target.py::fib", "type": "function", "label": "fib"},
        {"id": "caller.py", "type": "file", "label": "caller.py"},
        {"id": "caller.py::main", "type": "function", "label": "main"},
    ]
    edges = [
        {"source": "target.py", "target": "target.py::fib", "type": "contains"},
        {"source": "caller.py", "target": "caller.py::main", "type": "contains"},
        {"source": "caller.py::main", "target": "target.py::fib", "type": "calls"},
    ]
    graph = build_graph(nodes, edges)
    assessment = _assess_for(graph, "optimize fib", "target.py::fib")
    assert isinstance(assessment, ChangeScopeAssessment)
    assert assessment.scope == "cross_file_impact"
    assert "caller.py::main" in assessment.evidence_nodes


def test_same_file_caller_produces_scope_uncertain():
    nodes = [
        {"id": "target.py", "type": "file", "label": "target.py"},
        {"id": "target.py::fib", "type": "function", "label": "fib"},
        {"id": "target.py::helper", "type": "function", "label": "helper"},
    ]
    edges = [
        {"source": "target.py", "target": "target.py::fib", "type": "contains"},
        {"source": "target.py", "target": "target.py::helper", "type": "contains"},
        # helper calls fib: a caller, but in the SAME file -> ambiguous/local.
        {"source": "target.py::helper", "target": "target.py::fib", "type": "calls"},
    ]
    graph = build_graph(nodes, edges)
    assessment = _assess_for(graph, "optimize fib", "target.py::fib")
    assert assessment.scope == "scope_uncertain"


def test_test_reference_produces_api_contract_risk():
    nodes = [
        {"id": "target.py", "type": "file", "label": "target.py"},
        {"id": "target.py::fib", "type": "function", "label": "fib"},
        {"id": "tests/test_target.py", "type": "file", "label": "test_target.py"},
        {"id": "tests/test_target.py::test_fib", "type": "function", "label": "test_fib"},
    ]
    edges = [
        {"source": "target.py", "target": "target.py::fib", "type": "contains"},
        {"source": "tests/test_target.py", "target": "tests/test_target.py::test_fib", "type": "contains"},
        {"source": "tests/test_target.py::test_fib", "target": "target.py::fib", "type": "calls"},
    ]
    graph = build_graph(nodes, edges)
    assessment = _assess_for(graph, "optimize fib", "target.py::fib")
    assert assessment.scope == "api_contract_risk"
    assert any("test" in r.lower() for r in assessment.reasons)


def test_local_only_callee_produces_local_safe():
    nodes = [
        {"id": "target.py", "type": "file", "label": "target.py"},
        {"id": "target.py::fib", "type": "function", "label": "fib"},
        {"id": "target.py::helper", "type": "function", "label": "helper"},
    ]
    edges = [
        {"source": "target.py", "target": "target.py::fib", "type": "contains"},
        {"source": "target.py", "target": "target.py::helper", "type": "contains"},
        # fib calls helper (callee only); nothing calls fib -> safe to optimize.
        {"source": "target.py::fib", "target": "target.py::helper", "type": "calls"},
    ]
    graph = build_graph(nodes, edges)
    assessment = _assess_for(graph, "optimize fib", "target.py::fib")
    assert assessment.scope == "local_safe"


# --------------------------------------------------------------------------
# Non-mutation + purity (tests 11-12)
# --------------------------------------------------------------------------

def test_base_graph_weights_not_mutated():
    graph = _chain_graph()
    before = compute_node_weights(graph)
    snapshot = dict(before)
    compute_scope_aware_spread(graph, "optimize fib", base_weights=before)
    after = compute_node_weights(graph)
    assert before == snapshot, "passed-in base_weights dict was mutated"
    assert after == snapshot, "graph-derived weights changed (base must be stable)"


def test_module_has_no_model_api_or_subprocess_imports():
    src = Path("graph/evidence_spread.py").read_text(encoding="utf-8")
    forbidden = [
        "import subprocess",
        "import requests",
        "import openai",
        "import google.generativeai",
        "from agents",
        "import socket",
        "import urllib",
        "run_gemini",
        "run_validation_command",
    ]
    for needle in forbidden:
        assert needle not in src, f"evidence_spread must stay pure; found {needle!r}"


# --------------------------------------------------------------------------
# format_spread_explanation
# --------------------------------------------------------------------------

def test_format_spread_explanation_is_readable_and_limited():
    graph = _chain_graph()
    scores = compute_scope_aware_spread(graph, "optimize fib")
    text = format_spread_explanation(scores, limit=2)
    assert "target.py::fib" in text
    # Limit respected: at most 2 node lines (plus optional header).
    node_lines = [ln for ln in text.splitlines() if "::" in ln]
    assert len(node_lines) <= 2
