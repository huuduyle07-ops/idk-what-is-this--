"""Phase 12.13a - Graph Attraction / Repulsion (explain-only MVP).

These tests pin down the read-only "magnetic graph" layer: nodes that match the
query/target/confidence pull attention (attraction), while generic utility hubs
push it away (repulsion). Nothing here may feed CONTROL ranking, Evidence Spread
scoring, patch generation, validation, or benchmark scoring.
"""
from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph.attraction import (
    GraphAttraction,
    classify_node_attraction,
    explain_attraction_batch,
    format_attraction_markdown,
    is_generic_utility_hub,
)


def test_graph_attraction_is_immutable():
    item = GraphAttraction(
        node_id="a",
        attraction=0.5,
        repulsion=0.1,
        net_score=0.4,
        reasons=("x",),
    )
    assert item.is_generic_hub is False
    try:
        item.attraction = 0.9
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("GraphAttraction must be immutable")


def test_query_match_increases_attraction():
    matched = classify_node_attraction("target.py::fib", query="fib")
    unmatched = classify_node_attraction("target.py::fib", query="zzz")

    assert matched.attraction > unmatched.attraction
    assert matched.attraction >= 0.50
    assert any("query" in r.lower() for r in matched.reasons)


def test_exact_target_match_increases_attraction():
    matched = classify_node_attraction("target.py::fib", target_node="target.py::fib")
    other = classify_node_attraction("target.py::fib", target_node="other.py::g")

    assert matched.attraction > other.attraction
    assert matched.attraction >= 0.40
    assert any("target" in r.lower() for r in matched.reasons)


def test_high_confidence_increases_attraction():
    high = classify_node_attraction("a.py::f", evidence_confidence=0.70)
    low = classify_node_attraction("a.py::f", evidence_confidence=0.10)

    assert high.attraction > low.attraction
    assert any("confidence" in r.lower() for r in high.reasons)


def test_failure_penalty_increases_attraction():
    penalized = classify_node_attraction("a.py::f", failure_penalty=0.5)
    clean = classify_node_attraction("a.py::f", failure_penalty=0.0)

    assert penalized.attraction > clean.attraction
    assert any("failure" in r.lower() for r in penalized.reasons)


def test_graph_weight_contributes_capped_attraction():
    weighted = classify_node_attraction("a.py::f", graph_weight=10.0)
    # Contribution is capped at 0.30 regardless of how large the weight is.
    assert weighted.attraction == 0.30
    assert any("weight" in r.lower() for r in weighted.reasons)


def test_generic_utility_hub_gets_repulsion():
    hub = classify_node_attraction("app/utils.py::helper", in_degree=5)

    assert hub.is_generic_hub is True
    assert hub.repulsion > 0.0
    assert hub.net_score < 0.0
    assert any("hub" in r.lower() or "generic" in r.lower() for r in hub.reasons)


def test_high_in_degree_without_query_match_gets_repulsion():
    hub = classify_node_attraction("core/router.py::dispatch", in_degree=42, query="login")

    assert hub.repulsion >= 0.25
    assert any("in-degree" in r.lower() or "in_degree" in r.lower() for r in hub.reasons)


def test_query_match_prevents_generic_hub_classification():
    # Generic name AND very high in-degree, but the query points right at it.
    assert is_generic_utility_hub("app/utils.py::helper", in_degree=99, query="helper") is False
    item = classify_node_attraction("app/utils.py::helper", in_degree=99, query="helper")
    assert item.is_generic_hub is False


def test_generic_hub_helpers_are_conservative():
    # No query, generic name -> hub.
    assert is_generic_utility_hub("a/logger.py::log") is True
    # No query, high in-degree -> hub.
    assert is_generic_utility_hub("a/service.py::run", in_degree=30) is True
    # Plain node, low degree, no generic name -> not a hub.
    assert is_generic_utility_hub("a/service.py::run", in_degree=2) is False


def test_net_score_clamps_to_unit_range():
    strongly_attractive = classify_node_attraction(
        "alpha",
        query="alpha",
        target_node="alpha",
        evidence_confidence=0.95,
        failure_penalty=1.0,
        graph_weight=5.0,
    )
    strongly_repulsive = classify_node_attraction(
        "app/utils.py::log",
        in_degree=80,
    )

    assert strongly_attractive.net_score == 1.0  # 1.65 raw -> clamped
    assert -1.0 <= strongly_repulsive.net_score <= 1.0
    assert strongly_repulsive.net_score < 0.0


def test_batch_explanation_with_spread_style_dicts():
    nodes = [
        {
            "node_id": "target.py::fib",
            "in_degree": 1,
            "out_degree": 1,
            "base_score": 0.2,
            "confidence": 0.70,
        },
        {
            "node_id": "app/utils.py::helper",
            "in_degree": 40,
            "out_degree": 2,
            "final_score": 0.05,
        },
    ]

    items = explain_attraction_batch(nodes, query="fib", target_node="target.py::fib")

    assert [i.node_id for i in items] == ["target.py::fib", "app/utils.py::helper"]
    assert all(isinstance(i, GraphAttraction) for i in items)
    # First node: query + target + confidence -> attractive.
    assert items[0].net_score > 0.0
    assert items[0].is_generic_hub is False
    # Second node: generic util + high in-degree, no query match -> repulsive.
    assert items[1].is_generic_hub is True
    assert items[1].net_score < 0.0


def test_batch_handles_missing_fields_gracefully():
    items = explain_attraction_batch([{"node_id": "a.py::f"}, {}])
    assert len(items) == 2
    assert items[0].node_id == "a.py::f"
    # A dict with no node_id still yields a safe, named placeholder.
    assert items[1].node_id != ""


def test_markdown_formatter_includes_columns_and_explain_only_guardrail():
    items = explain_attraction_batch(
        [
            {"node_id": "target.py::fib", "base_score": 0.2, "confidence": 0.7},
            {"node_id": "app/utils.py::helper", "in_degree": 40},
        ],
        query="fib",
        target_node="target.py::fib",
    )
    md = format_attraction_markdown(items)

    for header in ("node_id", "attraction", "repulsion", "net_score", "reasons"):
        assert header in md
    assert "hub" in md.lower()
    assert "target.py::fib" in md
    assert "app/utils.py::helper" in md
    # Guardrail-style explain-only wording must be present.
    assert "explain-only" in md.lower()
    for token in ("CONTROL", "Evidence Spread", "patch", "validation", "benchmark"):
        assert token in md


def test_markdown_formatter_empty_input_is_safe():
    md = format_attraction_markdown([])
    assert "explain-only" in md.lower()
    assert "node_id" in md  # header still rendered


def test_empty_batch_is_safe():
    assert explain_attraction_batch([]) == []
