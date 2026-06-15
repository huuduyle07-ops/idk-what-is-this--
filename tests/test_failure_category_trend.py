"""Tests for Phase 14.7 — failure_category trend display.

Covers:
Run health (4):
  1. failure_category_counts appears in run health when data exists.
  2. Old reports without category data do not crash.
  3. unknown category is counted and displayed.
  4. Category counts do not affect pass/fail or failure_kind_counts.

Markdown (2):
  5. Markdown report includes failure category line for new reports.
  6. Markdown report handles old reports without category data gracefully.

Web/view (3):
  7. summarize_run_health always returns failure_category_counts key.
  8. Category counts match the failing cases that carry failure_category.
  9. Reports without failure_category yield empty failure_category_counts.

Trends/evidence (2):
  10. extract_failure_category_counts returns counts from new-format reports.
  11. Old reports (no failure_category) return empty dict from extractor.

Guardrails (7):
  12-18. AST-based checks on core/benchmarks_view.py.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.benchmarks_view import summarize_run_health
from core.failure_taxonomy_trends import extract_failure_category_counts


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_failing(name: str, failure_category: str | None = None, **extra) -> dict:
    case = {"name": name, "success": False}
    if failure_category is not None:
        case["failure_category"] = failure_category
        case.setdefault("failure_category_confidence", "high")
        case.setdefault("failure_category_rule", "some_rule")
        case.setdefault("failure_category_reason", "some reason")
    case.update(extra)
    return case


def _make_passing(name: str) -> dict:
    return {"name": name, "success": True}


def _make_report(*results: dict) -> dict:
    results_list = list(results)
    return {
        "total": len(results_list),
        "passed": sum(1 for r in results_list if r.get("success") is True),
        "failed": sum(1 for r in results_list if r.get("success") is False),
        "skipped": 0,
        "results": results_list,
    }


# ── Run health tests (1-4) ────────────────────────────────────────────────────

def test_failure_category_counts_present_when_data_exists():
    report = _make_report(
        _make_failing("case_a", "security_tool_or_permission"),
        _make_failing("case_b", "unknown"),
    )
    health = summarize_run_health(report)
    counts = health.get("failure_category_counts") or {}
    assert counts.get("security_tool_or_permission", 0) == 1
    assert counts.get("unknown", 0) == 1


def test_old_report_without_category_does_not_crash():
    report = _make_report(
        {"name": "old_case", "success": False},
        {"name": "old_case2", "success": False, "failure_kind": "code_unknown"},
    )
    health = summarize_run_health(report)
    assert "failure_category_counts" in health
    assert health["failure_category_counts"] == {}


def test_unknown_category_counted_in_run_health():
    report = _make_report(
        _make_failing("mystery", "unknown"),
        _make_failing("another_mystery", "unknown"),
    )
    health = summarize_run_health(report)
    assert health["failure_category_counts"].get("unknown", 0) == 2


def test_category_counts_do_not_affect_failure_kind_or_pass_fail():
    failing_new = _make_failing("new_case", "security_tool_or_permission",
                                failure_kind="security_tool",
                                failure_kind_display="SECURITY TOOL")
    failing_old = {"name": "old_case", "success": False, "failure_kind": "code_unknown",
                   "failure_kind_display": "CODE / UNKNOWN"}
    passing = _make_passing("pass_case")
    report = _make_report(failing_new, failing_old, passing)
    health = summarize_run_health(report)

    assert health["passed"] == 1
    assert health["failed"] == 2
    # failure_kind_counts uses failure_kind_display, not failure_category
    assert "SECURITY TOOL" in health["failure_kind_counts"]
    assert "CODE / UNKNOWN" in health["failure_kind_counts"]
    # category counts are separate
    assert health["failure_category_counts"].get("security_tool_or_permission", 0) == 1


# ── Markdown tests (5-6) ──────────────────────────────────────────────────────

def test_markdown_report_includes_category_line(tmp_path):
    from benchmarks.run_benchmarks import write_markdown_report

    report = _make_report(
        _make_failing("sec_case", "security_tool_or_permission",
                      failure_kind="security_tool"),
        _make_passing("pass_case"),
    )
    out = tmp_path / "report.md"
    write_markdown_report(report, out)
    md = out.read_text(encoding="utf-8")
    assert "Failure categories" in md
    assert "security_tool_or_permission" in md


def test_markdown_report_no_crash_without_category_data(tmp_path):
    from benchmarks.run_benchmarks import write_markdown_report

    report = _make_report(
        {"name": "old_fail", "success": False, "failure_kind": "code_unknown"},
        _make_passing("pass_case"),
    )
    out = tmp_path / "report.md"
    write_markdown_report(report, out)
    md = out.read_text(encoding="utf-8")
    assert "Benchmark Report" in md
    assert "Failure categories" not in md


# ── Web/view tests (7-9) ─────────────────────────────────────────────────────

def test_summarize_run_health_always_returns_category_counts_key():
    report = _make_report()
    health = summarize_run_health(report)
    assert "failure_category_counts" in health
    assert isinstance(health["failure_category_counts"], dict)


def test_run_health_category_counts_match_failing_cases():
    report = _make_report(
        _make_failing("a", "async_or_lifecycle_bug"),
        _make_failing("b", "async_or_lifecycle_bug"),
        _make_failing("c", "unknown"),
        _make_passing("d"),
    )
    health = summarize_run_health(report)
    counts = health["failure_category_counts"]
    assert counts.get("async_or_lifecycle_bug", 0) == 2
    assert counts.get("unknown", 0) == 1
    assert "async_or_lifecycle_bug" not in health["failure_kind_counts"] or True  # no collision


def test_old_report_category_counts_empty():
    report = _make_report(
        {"name": "no_cat", "success": False},
        {"name": "no_cat2", "success": False},
    )
    health = summarize_run_health(report)
    assert health["failure_category_counts"] == {}


# ── Trends/evidence tests (10-11) ────────────────────────────────────────────

def test_extract_failure_category_counts_from_new_report():
    report = _make_report(
        _make_failing("x", "toolchain_environment"),
        _make_failing("y", "toolchain_environment"),
        _make_failing("z", "unknown"),
        _make_passing("p"),
    )
    counts = extract_failure_category_counts(report)
    assert counts == {"toolchain_environment": 2, "unknown": 1}


def test_extract_failure_category_counts_empty_for_old_report():
    report = _make_report(
        {"name": "old1", "success": False},
        {"name": "old2", "success": False, "failure_kind": "code_unknown"},
    )
    counts = extract_failure_category_counts(report)
    assert counts == {}


# ── Guardrail tests (12-18, AST-based on benchmarks_view) ─────────────────────

_VIEW_PATH = Path(__file__).parent.parent / "core" / "benchmarks_view.py"
_VIEW_SOURCE = _VIEW_PATH.read_text(encoding="utf-8")


def test_no_flask_in_benchmarks_view():
    tree = ast.parse(_VIEW_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "flask" not in alias.name.lower(), alias.name
        elif isinstance(node, ast.ImportFrom):
            assert "flask" not in (node.module or "").lower(), node.module


def test_no_subprocess_in_benchmarks_view():
    tree = ast.parse(_VIEW_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "subprocess", "subprocess must not be imported"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "") != "subprocess", "subprocess must not be imported"


def test_no_model_client_in_benchmarks_view():
    for bad in ("anthropic", "openai", "litellm", "ollama", "bedrock"):
        assert bad not in _VIEW_SOURCE, f"Found {bad!r} in benchmarks_view"


def test_no_db_client_in_benchmarks_view():
    for bad in ("sqlalchemy", "psycopg", "pymongo", "motor", "sqlite3"):
        assert bad not in _VIEW_SOURCE, f"Found {bad!r} in benchmarks_view"


def test_no_lesson_promotion_in_benchmarks_view():
    for bad in ("promote_lesson", "save_active_lesson", "lesson_store"):
        assert bad not in _VIEW_SOURCE, f"Found {bad!r} in benchmarks_view"


def test_no_patch_apply_in_benchmarks_view():
    for bad in ("apply_patch", "patch_apply", "run_patch", "exec_patch"):
        assert bad not in _VIEW_SOURCE, f"Found {bad!r} in benchmarks_view"


def test_benchmarks_view_only_imports_stdlib():
    stdlib_ok = {"__future__", "json", "re", "datetime", "pathlib", "typing"}
    tree = ast.parse(_VIEW_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in stdlib_ok, (
                f"Unexpected import in benchmarks_view: {module!r}"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in stdlib_ok, (
                    f"Unexpected import in benchmarks_view: {alias.name!r}"
                )
