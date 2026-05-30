"""Phase 12.13c - Phantom Limb related notes (explain-only).

Deterministic, read-only scoring that explains which lessons / proposal
summaries / memory notes look related to the current target/query/graph area,
and why. Nothing here may feed Phantom Limb ranking, CONTROL ranking, Evidence
Spread scoring, patch generation, validation, or benchmark scoring.
"""
from __future__ import annotations

import sys
import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.related_notes import (
    RelatedNoteAttraction,
    classify_related_note_attraction,
    explain_related_notes,
    format_related_notes_markdown,
)


def test_related_note_attraction_is_immutable():
    item = RelatedNoteAttraction(
        note_id="n1",
        title="t",
        source_type="lesson",
        attraction=0.4,
        repulsion=0.1,
        net_score=0.3,
        reasons=("x",),
        should_surface=True,
    )
    try:
        item.attraction = 0.9
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("RelatedNoteAttraction must be immutable")


def test_query_match_increases_attraction():
    note = {"note_id": "n1", "title": "Fix fib recursion", "text": "the fib helper"}
    matched = classify_related_note_attraction(note, query="fib")
    unmatched = classify_related_note_attraction(note, query="zzzz")

    assert matched.attraction > unmatched.attraction
    assert any("query" in r.lower() for r in matched.reasons)


def test_target_path_match_increases_attraction():
    note = {"note_id": "n1", "title": "note", "path": "src/target.py", "text": "x"}
    matched = classify_related_note_attraction(note, target_path="src/target.py")
    other = classify_related_note_attraction(note, target_path="src/other.py")

    assert matched.attraction > other.attraction
    assert any("path" in r.lower() for r in matched.reasons)


def test_summary_and_topic_fields_are_used_when_present():
    note = {
        "note_id": "n1",
        "title": "note",
        "path": "docs/elsewhere.md",
        "topic": "src/target.py",
        "text": "body without the query",
        "summary": "fib behavior lesson",
    }

    item = classify_related_note_attraction(
        note,
        query="fib",
        target_path="src/target.py",
    )

    assert item.attraction >= 0.75
    assert any("query" in r.lower() for r in item.reasons)
    assert any("path" in r.lower() for r in item.reasons)


def test_target_node_match_increases_attraction():
    note = {"note_id": "n1", "title": "about target.py::fib", "text": "details"}
    matched = classify_related_note_attraction(note, target_node="target.py::fib")
    other = classify_related_note_attraction(note, target_node="other.py::g")

    assert matched.attraction > other.attraction
    assert any("target node" in r.lower() or "node" in r.lower() for r in matched.reasons)


def test_lesson_and_benchmark_sources_get_useful_source_attraction():
    lesson = classify_related_note_attraction(
        {"note_id": "l", "title": "L", "text": "useful", "source_type": "lesson"}
    )
    benchmark = classify_related_note_attraction(
        {"note_id": "b", "title": "B", "text": "useful", "source_type": "benchmark"}
    )
    manual = classify_related_note_attraction(
        {"note_id": "m", "title": "M", "text": "useful", "source_type": "manual"}
    )

    assert lesson.attraction > manual.attraction
    assert benchmark.attraction > manual.attraction
    assert any("source" in r.lower() for r in lesson.reasons)


def test_graph_node_overlap_increases_attraction():
    note = {"note_id": "n", "title": "touches pricing.py", "text": "x"}
    matched = classify_related_note_attraction(note, graph_nodes=["pricing.py", "main.py"])
    none = classify_related_note_attraction(note, graph_nodes=["unrelated.py"])

    assert matched.attraction > none.attraction
    assert any("graph" in r.lower() for r in matched.reasons)


def test_empty_note_gets_repulsion():
    empty = classify_related_note_attraction({"note_id": "e", "title": "", "text": ""})
    assert empty.repulsion > 0.0
    assert any("empty" in r.lower() or "missing" in r.lower() for r in empty.reasons)


def test_unknown_source_gets_repulsion():
    note = classify_related_note_attraction(
        {"note_id": "u", "title": "Something", "text": "body", "source_type": "unknown"},
        query="Something",
    )
    assert any("unknown" in r.lower() for r in note.reasons)


def test_generic_title_gets_repulsion():
    for generic in ("misc", "TODO", "general", "Notes"):
        note = classify_related_note_attraction(
            {"note_id": "g", "title": generic, "text": "body text here"}
        )
        assert any("generic" in r.lower() for r in note.reasons), generic


def test_no_overlap_gets_repulsion():
    note = classify_related_note_attraction(
        {"note_id": "n", "title": "Unrelated topic", "text": "nothing relevant"},
        query="fib",
        target_path="src/target.py",
        target_node="target.py::fib",
    )
    assert any("no" in r.lower() and "overlap" in r.lower() for r in note.reasons)
    assert note.repulsion > 0.0


def test_should_surface_only_above_threshold():
    strong = classify_related_note_attraction(
        {
            "note_id": "s",
            "title": "Fix target.py::fib",
            "text": "lesson about fib in src/target.py",
            "path": "src/target.py",
            "source_type": "lesson",
        },
        query="fib",
        target_path="src/target.py",
        target_node="target.py::fib",
    )
    weak = classify_related_note_attraction(
        {"note_id": "w", "title": "misc", "text": "", "source_type": "unknown"}
    )

    assert strong.net_score > 0.20
    assert strong.should_surface is True
    assert weak.should_surface is False


def test_net_score_clamps_to_unit_range():
    strong = classify_related_note_attraction(
        {
            "note_id": "s",
            "title": "target.py::fib in src/target.py",
            "text": "fib fib fib lesson",
            "path": "src/target.py",
            "source_type": "lesson",
            "tags": ["fib"],
        },
        query="fib",
        target_path="src/target.py",
        target_node="target.py::fib",
        graph_nodes=["src/target.py"],
    )
    repulsive = classify_related_note_attraction(
        {"note_id": "r", "title": "misc", "text": "", "source_type": "unknown"},
        query="fib",
    )
    assert -1.0 <= strong.net_score <= 1.0
    assert strong.net_score == 1.0
    assert -1.0 <= repulsive.net_score <= 1.0
    assert repulsive.net_score < 0.0


def test_explain_sorts_by_net_score_descending_and_respects_limit():
    notes = [
        {"note_id": "weak", "title": "misc", "text": "", "source_type": "unknown"},
        {
            "note_id": "strong",
            "title": "fib lesson",
            "text": "about fib",
            "source_type": "lesson",
        },
        {"note_id": "mid", "title": "fib mention", "text": "fib appears", "source_type": "manual"},
    ]
    items = explain_related_notes(notes, query="fib", limit=2)

    assert len(items) == 2
    assert items[0].net_score >= items[1].net_score
    assert items[0].note_id == "strong"


def test_explain_empty_input_is_safe():
    assert explain_related_notes([]) == []


def test_markdown_includes_columns_and_guardrail():
    items = explain_related_notes(
        [
            {"note_id": "a", "title": "fib lesson", "text": "about fib", "source_type": "lesson"},
            {"note_id": "b", "title": "misc", "text": "", "source_type": "unknown"},
        ],
        query="fib",
    )
    md = format_related_notes_markdown(items)

    for header in (
        "note_id",
        "title",
        "source_type",
        "attraction",
        "repulsion",
        "net_score",
        "should_surface",
        "reasons",
    ):
        assert header in md
    assert "explain-only" in md.lower()
    for token in (
        "Phantom Limb ranking",
        "CONTROL ranking",
        "Evidence Spread scoring",
        "patch generation",
        "validation",
        "benchmark scoring",
    ):
        assert token in md


def test_markdown_empty_input_is_safe():
    md = format_related_notes_markdown([])
    assert "explain-only" in md.lower()
    assert "note_id" in md


def test_module_has_no_forbidden_imports():
    import core.related_notes as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    forbidden_import_areas = ("patching", "control", "web", "model", "api")
    for imported in imported_modules:
        parts = imported.split(".")
        for forbidden in forbidden_import_areas:
            assert not any(
                part == forbidden
                or part.startswith(f"{forbidden}_")
                or part.endswith(f"_{forbidden}")
                for part in parts
            ), imported
