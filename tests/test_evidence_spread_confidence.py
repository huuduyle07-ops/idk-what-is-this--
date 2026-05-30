"""Phase 12.12b - Evidence Confidence inside Evidence Spread reports.

Explain-only: these tests assert that the exported Markdown surfaces how
trustworthy each spread signal is, and that the confidence layer never claims
to change patch generation, CONTROL ranking, validation, or benchmark scoring.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph.schema import ProgramGraph, build_graph


def _target_graph() -> ProgramGraph:
    return build_graph(
        [
            {"id": "target.py", "type": "file", "label": "target.py"},
            {"id": "target.py::fib", "type": "function", "label": "fib"},
            {"id": "target.py::helper", "type": "function", "label": "helper"},
            {"id": "tests/test_target.py", "type": "file", "label": "test_target.py"},
            {
                "id": "tests/test_target.py::test_fib",
                "type": "function",
                "label": "test_fib",
            },
        ],
        [
            {"source": "target.py", "target": "target.py::fib", "type": "contains"},
            {"source": "target.py", "target": "target.py::helper", "type": "contains"},
            {
                "source": "target.py::fib",
                "target": "target.py::helper",
                "type": "calls",
            },
            {
                "source": "tests/test_target.py",
                "target": "tests/test_target.py::test_fib",
                "type": "contains",
            },
            {
                "source": "tests/test_target.py::test_fib",
                "target": "target.py::fib",
                "type": "calls",
            },
        ],
    )


def _confidence_md(target="target.py::fib", query="optimize fib", top_n=5) -> str:
    from web.graph_evidence import (
        build_scope_evidence_spread_debug,
        format_evidence_spread_markdown,
    )

    graph = _target_graph()
    result = build_scope_evidence_spread_debug(
        graph, query, target_node=target, top_n=top_n
    )
    return format_evidence_spread_markdown(result)


# ----------------------------- integration ---------------------------------

def test_markdown_includes_evidence_confidence_section():
    md = _confidence_md()
    assert "## Evidence Confidence" in md


def test_markdown_includes_combined_confidence():
    md = _confidence_md()
    assert "combined_confidence" in md
    assert "strongest_evidence" in md
    # The direct target match is graph_proximity distance 0 -> 0.70 combined.
    assert "0.70" in md


def test_markdown_includes_per_node_confidence():
    md = _confidence_md()
    assert "| node_id | confidence | source | reason |" in md
    assert "target.py::fib" in md
    assert "graph_proximity" in md


def test_markdown_includes_confidence_guardrail():
    from web.graph_evidence import EVIDENCE_CONFIDENCE_GUARDRAIL

    md = _confidence_md()
    assert EVIDENCE_CONFIDENCE_GUARDRAIL in md
    assert "explain-only" in EVIDENCE_CONFIDENCE_GUARDRAIL.lower()
    for token in ("patch", "CONTROL", "validation", "benchmark"):
        assert token in EVIDENCE_CONFIDENCE_GUARDRAIL


def test_existing_spread_guardrail_still_present():
    from web.graph_evidence import EVIDENCE_SPREAD_GUARDRAIL

    md = _confidence_md()
    # Confidence layer must not displace the original spread guardrail.
    assert EVIDENCE_SPREAD_GUARDRAIL in md


def test_empty_result_confidence_section_is_safe():
    from web.graph_evidence import (
        build_scope_evidence_spread_debug,
        format_evidence_spread_markdown,
    )

    result = build_scope_evidence_spread_debug(ProgramGraph(), "anything")
    md = format_evidence_spread_markdown(result)
    assert "## Evidence Confidence" in md
    assert "combined_confidence" in md  # blocking/unknown, but must not crash


# ------------------------- per-node classification -------------------------

def test_classify_distance_zero_one_two():
    from web.graph_evidence import classify_spread_node_confidence

    d0 = classify_spread_node_confidence(
        {"node_id": "a", "distance": 0, "reasons": ["direct query match"]}, "a"
    )
    d1 = classify_spread_node_confidence(
        {"node_id": "b", "distance": 1, "reasons": ["distance-1 neighbor of a"]}, "a"
    )
    d2 = classify_spread_node_confidence(
        {"node_id": "c", "distance": 2, "reasons": ["distance-2 neighbor of a"]}, "a"
    )

    assert d0.source_type == "graph_proximity" and d0.confidence == 0.70
    assert d1.source_type == "graph_proximity" and d1.confidence == 0.55
    assert d2.source_type == "graph_proximity" and d2.confidence == 0.40


def test_classify_distance_from_reason_when_field_missing():
    from web.graph_evidence import classify_spread_node_confidence

    node = {"node_id": "b", "reasons": ["distance-1 neighbor of a"]}
    conf = classify_spread_node_confidence(node, "a")

    assert conf.source_type == "graph_proximity"
    assert conf.confidence == 0.55


def test_direct_target_match_is_distance_zero():
    from web.graph_evidence import classify_spread_node_confidence

    # No distance info at all, but the node *is* the target.
    node = {"node_id": "a", "reasons": []}
    conf = classify_spread_node_confidence(node, "a")

    assert conf.source_type == "graph_proximity"
    assert conf.confidence == 0.70


def test_missing_or_unknown_evidence_is_low_confidence():
    from web.graph_evidence import classify_spread_node_confidence

    node = {"node_id": "z", "distance": None, "reasons": []}
    conf = classify_spread_node_confidence(node, "a")

    assert conf.confidence == 0.0
    assert conf.source_type in {"missing", "unknown"}


def test_out_of_window_distance_is_low_confidence():
    from web.graph_evidence import classify_spread_node_confidence

    # distance 3 is outside the supported 0/1/2 window -> treated as missing.
    node = {"node_id": "z", "distance": 3, "reasons": ["distance-3 neighbor of a"]}
    conf = classify_spread_node_confidence(node, "a")

    assert conf.confidence == 0.0
