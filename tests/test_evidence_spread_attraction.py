"""Phase 12.13b - Graph Attraction / Repulsion inside Evidence Spread reports.

Explain-only: the spread Markdown should surface which nodes pull attention and
which generic hubs push it away, without changing Evidence Spread scoring,
CONTROL ranking, Phantom Limb ranking, patch generation, validation, or
benchmark scoring.
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


def _attraction_md(target="target.py::fib", query="fib", top_n=5) -> str:
    from web.graph_evidence import (
        build_scope_evidence_spread_debug,
        format_evidence_spread_markdown,
    )

    graph = _target_graph()
    result = build_scope_evidence_spread_debug(
        graph, query, target_node=target, top_n=top_n
    )
    return format_evidence_spread_markdown(result)


def test_markdown_includes_graph_attraction_section():
    md = _attraction_md()
    assert "## Graph Attraction / Repulsion" in md
    # Table columns from format_attraction_markdown must be present.
    for header in ("attraction", "repulsion", "net_score", "reasons"):
        assert header in md


def test_attraction_section_after_evidence_confidence():
    md = _attraction_md()
    assert "## Evidence Confidence" in md
    assert "## Graph Attraction / Repulsion" in md
    assert md.index("## Graph Attraction / Repulsion") > md.index("## Evidence Confidence")


def test_query_target_node_shows_attraction():
    md = _attraction_md()
    # The query/target node should appear and read as attractive (positive net).
    fib_rows = [ln for ln in md.splitlines() if ln.startswith("| target.py::fib |")]
    assert fib_rows, "expected an attraction row for the target node"
    row = fib_rows[-1]  # attraction table row (after spread/confidence tables)
    assert "+" in row  # net_score rendered with explicit sign, positive


def test_generic_utility_hub_shows_repulsion():
    md = _attraction_md()
    helper_rows = [ln for ln in md.splitlines() if ln.startswith("| target.py::helper |")]
    assert helper_rows
    row = helper_rows[-1]
    # Marked as a generic hub with a negative net_score.
    assert "| yes |" in row
    assert "-" in row.split("|")[4]  # net_score column is negative


def test_phantom_limb_guardrail_present():
    from web.graph_evidence import GRAPH_ATTRACTION_REPORT_GUARDRAIL

    md = _attraction_md()
    assert GRAPH_ATTRACTION_REPORT_GUARDRAIL in md
    assert "explain-only" in GRAPH_ATTRACTION_REPORT_GUARDRAIL.lower()
    for token in (
        "Evidence Spread scoring",
        "CONTROL ranking",
        "Phantom Limb ranking",
        "patch generation",
        "validation",
        "benchmark scoring",
    ):
        assert token in GRAPH_ATTRACTION_REPORT_GUARDRAIL


def test_existing_spread_and_confidence_sections_still_present():
    from web.graph_evidence import (
        EVIDENCE_CONFIDENCE_GUARDRAIL,
        EVIDENCE_SPREAD_GUARDRAIL,
    )

    md = _attraction_md()
    assert "# Evidence Spread Report" in md
    assert EVIDENCE_SPREAD_GUARDRAIL in md
    assert EVIDENCE_CONFIDENCE_GUARDRAIL in md


def test_empty_result_attraction_section_is_safe():
    from web.graph_evidence import (
        build_scope_evidence_spread_debug,
        format_evidence_spread_markdown,
    )

    result = build_scope_evidence_spread_debug(ProgramGraph(), "anything")
    md = format_evidence_spread_markdown(result)
    assert "## Graph Attraction / Repulsion" in md
    # No crash, and the explain-only guardrail still renders.
    assert "explain-only" in md.lower()
