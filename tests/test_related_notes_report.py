"""Phase 12.13d - Related Notes / Lessons report integration.

The report/debug integration is explain-only: it renders already-loaded
note-like records for inspection and must not alter Phantom Limb output,
CONTROL ranking, Evidence Spread scoring, patch generation, validation,
benchmark scoring, or model behavior.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _sample_notes() -> list[dict]:
    return [
        {
            "note_id": "weak",
            "title": "misc",
            "text": "",
            "source_type": "unknown",
        },
        {
            "note_id": "strong",
            "title": "fib lesson",
            "text": "Fix fib behavior in src/target.py.",
            "path": "src/target.py",
            "source_type": "lesson",
        },
        {
            "note_id": "mid",
            "title": "fib manual note",
            "text": "Manual observation about fib.",
            "source_type": "manual",
        },
    ]


def _debug_markdown(*, limit: int = 5) -> str:
    from web.graph_evidence import build_related_notes_debug_markdown

    return build_related_notes_debug_markdown(
        _sample_notes(),
        query="fib",
        target_path="src/target.py",
        target_node="target.py::fib",
        graph_nodes=["src/target.py"],
        limit=limit,
    )


def test_related_notes_lessons_section_appears():
    md = _debug_markdown()
    assert "## Related Notes / Lessons" in md
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


def test_related_notes_report_sorts_by_net_score():
    md = _debug_markdown()
    assert md.index("| strong |") < md.index("| mid |") < md.index("| weak |")


def test_related_notes_report_respects_limit():
    md = _debug_markdown(limit=2)
    assert "| strong |" in md
    assert "| mid |" in md
    assert "| weak |" not in md


def test_related_notes_report_includes_guardrail():
    from core.related_notes import RELATED_NOTES_GUARDRAIL

    md = _debug_markdown()
    assert RELATED_NOTES_GUARDRAIL in md
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


def test_related_notes_report_empty_notes_are_safe():
    from web.graph_evidence import build_related_notes_debug_markdown

    md = build_related_notes_debug_markdown([], query="fib")
    assert "## Related Notes / Lessons" in md
    assert "| _(no notes)_ |" in md
    assert "explain-only" in md.lower()


def test_existing_phantom_limb_output_remains_unchanged():
    from core import phantom_limb
    from web.graph_evidence import build_related_notes_debug_markdown

    summaries = [
        {
            "file": "test_example_a.py",
            "language": "python",
            "main_symbols": [{"name": "setUp"}, {"name": "test_value"}],
        },
        {
            "file": "test_example_b.py",
            "language": "python",
            "main_symbols": [{"name": "setUp"}, {"name": "test_other"}],
        },
    ]

    before = phantom_limb.scan(summaries, str(Path.cwd()))
    build_related_notes_debug_markdown(_sample_notes(), query="fib")
    after = phantom_limb.scan(summaries, str(Path.cwd()))

    assert after == before
    assert [item["rule"] for item in after] == [item["rule"] for item in before]


def test_related_notes_report_has_no_forbidden_imports_or_calls():
    import web.graph_evidence as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: list[str] = []
    call_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                call_names.append(func.id)
            elif isinstance(func, ast.Attribute):
                call_names.append(func.attr)

    forbidden_import_areas = (
        "model",
        "api",
        "patching",
        "validation",
        "validator",
        "run_benchmarks",
    )
    for imported in imported_modules:
        parts = imported.split(".")
        for forbidden in forbidden_import_areas:
            assert not any(part == forbidden for part in parts), imported

    forbidden_calls = {"call_model", "call_api", "validate", "run_benchmarks"}
    assert forbidden_calls.isdisjoint(call_names)
