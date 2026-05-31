"""Phase 12.14b - Memory Temperature in Related Notes / Explainability UI.

UI/report visibility only. Surfacing memory temperature in the Related Notes /
Lessons explainability output must not change lesson retrieval, CONTROL prompt
injection, ranking, graph weights, Phantom Limb scoring, patch generation,
validation, or benchmark scoring, and must make no model/API calls or DB writes.
"""
from __future__ import annotations

import ast
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

NOW = datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc)


def _days_ago(days: int) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def _banded_notes() -> list[dict]:
    """Notes engineered to land in each thermal band under a fixed `now`."""
    return [
        {
            "note_id": "hot1",
            "source_type": "lesson",
            "trusted": True,
            "updated_at": _days_ago(1),
            "title": "fib lesson",
            "text": "fix fib recursion",
            "path": "src/target.py",
        },
        {
            "note_id": "warm1",
            "source_type": "manual",
            "updated_at": _days_ago(15),
            "title": "warm note",
            "text": "observation about fib",
        },
        {
            "note_id": "cold1",
            "source_type": "manual",
            "updated_at": _days_ago(60),
            "title": "cold note",
            "text": "old observation",
        },
        {
            "note_id": "frozen1",
            "source_type": "lesson",
            "status": "blocked",
            "updated_at": _days_ago(1),
            "title": "blocked note",
            "text": "deletes tests",
        },
    ]


def _debug_md(notes, **kwargs) -> str:
    from web.graph_evidence import build_related_notes_debug_markdown

    return build_related_notes_debug_markdown(
        notes,
        query="fib",
        target_path="src/target.py",
        graph_nodes=["src/target.py"],
        include_memory_temperature=True,
        now=NOW,
        **kwargs,
    )


# ----------------------- 1. temperature included when notes exist ----------

def test_related_notes_output_includes_memory_temperature_when_notes_exist():
    md = _debug_md(_banded_notes())
    # Related Notes section is still there...
    assert "## Related Notes / Lessons" in md
    # ...and now a memory temperature subsection is appended.
    assert "## Memory Temperature" in md
    for header in ("item_id", "band", "temperature", "should_surface", "reasons"):
        assert header in md


def test_memory_temperature_not_added_by_default():
    """Existing callers (default off) keep their original output shape."""
    from web.graph_evidence import build_related_notes_debug_markdown

    md = build_related_notes_debug_markdown(_banded_notes(), query="fib")
    assert "## Related Notes / Lessons" in md
    assert "## Memory Temperature" not in md


# ----------------------- 2. hot/warm/cold/frozen labels --------------------

def test_hot_warm_cold_frozen_badges_render():
    md = _debug_md(_banded_notes())
    assert "🔥 hot" in md
    assert "🌤 warm" in md
    assert "❄️ cold" in md
    assert "🧊 frozen" in md


def test_badge_helper_maps_each_band():
    from web.graph_evidence import memory_temperature_badge

    assert memory_temperature_badge("hot") == "🔥 hot"
    assert memory_temperature_badge("warm") == "🌤 warm"
    assert memory_temperature_badge("cold") == "❄️ cold"
    assert memory_temperature_badge("frozen") == "🧊 frozen"
    # Unknown band degrades gracefully instead of crashing.
    assert "mystery" in memory_temperature_badge("mystery")


# ----------------------- 3. missing fields do not crash --------------------

def test_missing_fields_do_not_crash():
    notes = [
        {},
        {"note_id": "only_id"},
        {"title": "no id at all", "source_type": "manual"},
        "not-a-dict-record",
        None,
    ]
    md = _debug_md(notes)
    assert "## Memory Temperature" in md
    # The id-less / non-dict records still render under a fallback id.
    assert "unknown" in md


def test_section_handles_empty_notes():
    from web.graph_evidence import format_memory_temperature_section

    md = format_memory_temperature_section([])
    assert "## Memory Temperature" in md
    assert "_(no notes)_" in md


# ----------------------- 4. frozen note stays explain-only -----------------

def test_frozen_note_appears_but_is_not_retrieval_behavior():
    from core.memory_temperature import MEMORY_TEMPERATURE_GUARDRAIL

    md = _debug_md(_banded_notes())
    # Frozen note is visible...
    assert "frozen1" in md
    assert "🧊 frozen" in md
    # ...but flagged as not surfaced and clearly explain-only.
    assert "explain-only" in md.lower()
    assert MEMORY_TEMPERATURE_GUARDRAIL in md

    # The frozen row should mark should_surface = no.
    frozen_line = next(
        line for line in md.splitlines() if "frozen1" in line and "🧊 frozen" in line
    )
    assert "| no |" in frozen_line


def test_section_orders_hot_first_frozen_last():
    from web.graph_evidence import format_memory_temperature_section

    md = format_memory_temperature_section(_banded_notes(), now=NOW)
    assert md.index("hot1") < md.index("warm1") < md.index("cold1") < md.index("frozen1")


# ----------------------- 6. /graph/explainability/view --------------------

@pytest.fixture
def client():
    from web import app as web_app

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as test_client:
        yield test_client


def _repo_with_graph(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "fib.py").write_text(
        "def fib(n):\n    return helper(n)\n\n\ndef helper(n):\n    return n\n",
        encoding="utf-8",
    )
    return repo


def test_explainability_view_renders_memory_temperature_section(client, tmp_path, monkeypatch):
    from web import app as web_app

    monkeypatch.setattr(
        web_app,
        "run_gemini_request",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("model call not allowed")),
        raising=False,
    )

    repo = _repo_with_graph(tmp_path)
    resp = client.get(
        "/graph/explainability/view",
        query_string={"repo_path": str(repo), "query": "fib"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["ok"] is True
    assert "## Memory Temperature" in body["markdown"]
    assert "Memory Temperature" in body["sections"]


# ----------------------- 7. forbidden imports / calls ----------------------

def test_graph_evidence_has_no_forbidden_imports_or_calls():
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

    forbidden_calls = {
        "call_model",
        "call_api",
        "validate",
        "run_benchmarks",
        "promote_lesson",
        "save_candidate_lesson",
    }
    assert forbidden_calls.isdisjoint(call_names)
