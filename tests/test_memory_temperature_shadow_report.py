"""Phase 13.8 - Memory Temperature Shadow Retrieval report integration."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

SHADOW_GUARDRAIL = (
    "Shadow retrieval is explain-only. It does not change lesson retrieval "
    "order, CONTROL prompts, ranking, patch generation, validation, benchmark "
    "scoring, or storage behavior."
)


def _days_ago(days: int) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def _sample_notes() -> list[dict]:
    return [
        {
            "note_id": "cold-first",
            "title": "old fib note",
            "text": "Fix fib behavior in src/target.py.",
            "path": "src/target.py",
            "source_type": "manual",
            "updated_at": _days_ago(60),
        },
        {
            "note_id": "hot-second",
            "title": "hot fib lesson",
            "text": "Fix fib behavior in src/target.py.",
            "path": "src/target.py",
            "source_type": "lesson",
            "trusted": True,
            "updated_at": _days_ago(1),
        },
        {
            "note_id": "audit-third",
            "title": "audit-only note",
            "text": "Audit-only historical observation.",
            "source_type": "lesson",
            "status": "audit-only",
            "updated_at": _days_ago(0),
        },
    ]


def _related_order_notes() -> list[dict]:
    return [
        {
            "note_id": "weak",
            "title": "misc",
            "text": "",
            "source_type": "unknown",
            "updated_at": _days_ago(1),
        },
        {
            "note_id": "strong",
            "title": "fib lesson",
            "text": "Fix fib behavior in src/target.py.",
            "path": "src/target.py",
            "source_type": "lesson",
            "trusted": True,
            "updated_at": _days_ago(1),
        },
        {
            "note_id": "mid",
            "title": "fib manual note",
            "text": "Manual observation about fib.",
            "source_type": "manual",
            "updated_at": _days_ago(20),
        },
    ]


def _debug_markdown(notes: list[dict] | None = None) -> str:
    from web.graph_evidence import build_related_notes_debug_markdown

    return build_related_notes_debug_markdown(
        _sample_notes() if notes is None else notes,
        query="fib",
        target_path="src/target.py",
        target_node="target.py::fib",
        graph_nodes=["src/target.py"],
        include_memory_temperature=True,
        include_shadow_retrieval=True,
        now=NOW,
    )


def test_explainability_report_includes_shadow_retrieval_when_notes_exist():
    md = _debug_markdown()

    assert "## Related Notes / Lessons" in md
    assert "## Memory Temperature" in md
    assert "## Memory Temperature Shadow Retrieval" in md


def test_shadow_report_includes_rank_delta_band_source_and_reason():
    md = _debug_markdown()

    for header in (
        "item_id",
        "source_key",
        "original_rank",
        "shadow_rank",
        "rank_delta",
        "temperature_band",
        "should_surface",
        "excluded",
        "reason",
    ):
        assert header in md
    assert "hot-second" in md
    assert "lesson:src/target.py" in md
    assert "trusted/useful source base temperature" in md


def test_shadow_report_uses_already_loaded_notes_only(monkeypatch):
    import web.graph_evidence as graph_evidence

    notes = _sample_notes()
    seen_records: list[object] = []

    def fake_build_shadow_retrieval_report(records, *, now=None, limit=None):
        seen_records.append(records)
        return {
            "items": [],
            "original_order": [],
            "shadow_order": [],
            "excluded_order": [],
        }

    monkeypatch.setattr(
        graph_evidence,
        "build_shadow_retrieval_report",
        fake_build_shadow_retrieval_report,
    )

    md = graph_evidence.format_memory_temperature_shadow_section(notes, now=NOW)

    assert "## Memory Temperature Shadow Retrieval" in md
    assert seen_records == [notes]


def test_related_notes_order_remains_unchanged_when_shadow_report_is_appended():
    md = _debug_markdown(_related_order_notes())

    related_block = md.split("## Memory Temperature", 1)[0]
    assert related_block.index("| strong |") < related_block.index("| mid |")
    assert related_block.index("| mid |") < related_block.index("| weak |")
    shadow_block = md.split("## Memory Temperature Shadow Retrieval", 1)[1]
    assert "strong" in shadow_block


def test_control_prompt_content_has_no_shadow_report_dependency():
    control_source = (PROJECT_ROOT / "core" / "control_engine.py").read_text(
        encoding="utf-8"
    )
    graph_source = (PROJECT_ROOT / "web" / "graph_evidence.py").read_text(
        encoding="utf-8"
    )

    assert "Memory Temperature Shadow Retrieval" not in control_source
    assert "memory_temperature_shadow" not in control_source
    assert "control_engine" not in graph_source


def test_frozen_audit_only_rows_show_excluded_and_blocked_in_report():
    md = _debug_markdown()

    shadow_block = md.split("## Memory Temperature Shadow Retrieval", 1)[1]
    row = next(line for line in shadow_block.splitlines() if "| audit-third |" in line)
    assert "frozen" in row
    assert "audit-only" in row
    assert "| yes | yes |" in row


def test_empty_notes_produce_safe_no_shadow_lessons_section():
    from web.graph_evidence import build_related_notes_debug_markdown

    md = build_related_notes_debug_markdown(
        [],
        query="fib",
        include_memory_temperature=True,
        include_shadow_retrieval=True,
        now=NOW,
    )

    assert "## Memory Temperature Shadow Retrieval" in md
    assert "_(no shadow lessons)_" in md


def test_shadow_report_guardrail_appears_in_markdown():
    assert SHADOW_GUARDRAIL in _debug_markdown()


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


def test_graph_explainability_view_surfaces_shadow_retrieval_section(
    client, tmp_path, monkeypatch
):
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
    assert "## Memory Temperature Shadow Retrieval" in body["markdown"]
    assert "Memory Temperature Shadow Retrieval" in body["sections"]
    assert SHADOW_GUARDRAIL in body["markdown"]


def test_ast_guard_shadow_report_integration_has_no_forbidden_sinks():
    source = (PROJECT_ROOT / "web" / "graph_evidence.py").read_text(encoding="utf-8")
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
        "lesson_store",
        "lesson_retrieval",
        "control_engine",
        "model",
        "api",
        "database",
        "db",
        "patching",
        "validation",
        "validator",
        "benchmark",
        "run_benchmarks",
        "subprocess",
        "docker",
    )
    for imported in imported_modules:
        parts = imported.split(".")
        for forbidden in forbidden_import_areas:
            assert not any(part == forbidden for part in parts), imported

    forbidden_calls = {
        "run_gemini_request",
        "call_model",
        "call_api",
        "execute",
        "commit",
        "insert",
        "update",
        "delete",
        "apply_patch_plan",
        "generate_patch",
        "validate_patch",
        "run_validation",
        "run_benchmarks",
        "Popen",
        "run",
        "call",
        "check_call",
        "check_output",
        "list_lessons",
        "list_active_lessons",
        "find_active_lessons",
    }
    assert forbidden_calls.isdisjoint(call_names)

    for forbidden_text in (
        "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED",
        "MEMORY_TEMPERATURE_TIEBREAK_ONLY",
        "os.environ",
        "getenv",
        "harness_controls",
    ):
        assert forbidden_text not in source
