"""Phase 14.7a — Failure Category Fresh Run Smoke tests.

Covers:
  1. Smoke parser detects category fields in a sample fresh report.
  2. Smoke parser detects missing category fields as warning, not crash.
  3. Web render smoke with category row.
  4. Old report render smoke without category row.
  5. Smoke script does not import model clients, DB, subprocess,
     patch/apply, or lesson promotion (AST-based).
"""
from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = PROJECT_ROOT / "scripts" / "create_failure_category_smoke_report.py"


# ── helpers ───────────────────────────────────────────────────────────────────

def _failing(name: str, **extra) -> dict:
    return {"name": name, "success": False, **extra}


def _passing(name: str) -> dict:
    return {"name": name, "success": True}


def _make_report(*results) -> dict:
    results_list = list(results)
    return {
        "total": len(results_list),
        "passed": sum(1 for r in results_list if r.get("success") is True),
        "failed": sum(1 for r in results_list if r.get("success") is False),
        "skipped": 0,
        "results": results_list,
    }


def _enrich_report(report: dict) -> dict:
    """Re-enrich a report through with_failure_category_fields, same as a real run."""
    from benchmarks.run_benchmarks import with_failure_category_fields

    enriched_results = [
        with_failure_category_fields(dict(r)) if isinstance(r, dict) else r
        for r in (report.get("results") or [])
    ]
    out = dict(report)
    out["results"] = enriched_results
    return out


# ── Test 1: category fields present on re-enriched failing cases ──────────────

def test_smoke_fresh_report_has_category_fields():
    """Re-enriching a report through with_failure_category_fields adds all 4 fields."""
    # Simulate a pre-Phase-14.6 report with a security_tool failing case
    old_case = _failing("go_sec_case", failure_kind="security_tool")
    old_report = _make_report(old_case, _passing("pass_case"))

    enriched = _enrich_report(old_report)
    failing = [r for r in enriched["results"] if r.get("success") is not True]
    assert failing, "expected at least one failing case"

    for r in failing:
        for field in ("failure_category", "failure_category_confidence", "failure_category_rule", "failure_category_reason"):
            assert field in r, f"missing {field!r} on {r.get('name')!r}"
            assert isinstance(r[field], str) and r[field], (
                f"{field!r} is empty on {r.get('name')!r}: {r[field]!r}"
            )

    # security_tool failure_kind should map to security_tool_or_permission
    sec_case = next(r for r in failing if r.get("name") == "go_sec_case")
    assert sec_case["failure_category"] == "security_tool_or_permission"
    assert sec_case["failure_category_confidence"] == "high"
    assert sec_case["failure_category_rule"] == "failure_kind_security_tool"


# ── Test 2: missing category fields is a warning, not a crash ─────────────────

def test_smoke_missing_category_fields_no_crash():
    """Old reports without failure_category fields do not crash any display layer."""
    old_report = _make_report(
        {"name": "old_fail", "success": False, "failure_kind": "code_unknown"},
        {"name": "old_fail2", "success": False},
        _passing("pass"),
    )

    # summarize_run_health must not raise
    from core.benchmarks_view import summarize_run_health
    health = summarize_run_health(old_report)
    assert isinstance(health, dict)
    assert health.get("failure_category_counts") == {}

    # write_markdown_report must not raise
    from benchmarks.run_benchmarks import write_markdown_report
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "old.md"
        write_markdown_report(old_report, out)
        md = out.read_text(encoding="utf-8")
    assert "# Benchmark Report" in md


# ── Test 3: web render smoke shows category row when data present ──────────────

def test_smoke_web_render_category_row_present():
    """summarize_run_health returns non-empty failure_category_counts for enriched report."""
    old_report = _make_report(
        _failing("sec_case", failure_kind="security_tool"),
        _failing("toolchain_case", failure_kind="toolchain"),
        _passing("pass_case"),
    )
    enriched = _enrich_report(old_report)

    from core.benchmarks_view import summarize_run_health
    health = summarize_run_health(enriched)

    cat_counts = health.get("failure_category_counts") or {}
    assert cat_counts, "expected non-empty failure_category_counts after enrichment"

    # Known mappings: security_tool → security_tool_or_permission,
    #                 toolchain → toolchain_environment
    assert cat_counts.get("security_tool_or_permission", 0) >= 1
    assert cat_counts.get("toolchain_environment", 0) >= 1

    # The template function must exist in index.html
    template = (PROJECT_ROOT / "web" / "templates" / "index.html").read_text(encoding="utf-8")
    assert "_benchFailureCategoryText" in template
    assert "failure_category_counts" in template


# ── Test 4: old report — no category row appears ──────────────────────────────

def test_smoke_old_report_no_category_row():
    """Old reports (no failure_category field) produce no 'Failure categories' output."""
    old_report = _make_report(
        {"name": "old_fail", "success": False, "failure_kind": "code_unknown"},
        {"name": "old_fail2", "success": False, "failure_kind": "environment"},
    )

    from core.benchmarks_view import summarize_run_health
    health = summarize_run_health(old_report)
    assert health.get("failure_category_counts") == {}, (
        "old report should have empty failure_category_counts"
    )

    from benchmarks.run_benchmarks import write_markdown_report
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "old_report.md"
        write_markdown_report(old_report, out)
        md = out.read_text(encoding="utf-8")

    assert "Failure categories" not in md, (
        "old report Markdown must not show a 'Failure categories' row"
    )


# ── Test 5: smoke script has no bad imports (AST) ─────────────────────────────

def test_smoke_script_no_bad_imports():
    """The smoke script does not import model clients, DB, subprocess, patch/apply, or lesson promotion."""
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")

    # Check for bad string patterns (catch references in any context)
    bad_strings = [
        "anthropic", "openai", "litellm", "ollama",
        "sqlalchemy", "psycopg", "pymongo", "motor",
        "apply_patch", "patch_apply", "run_patch",
        "promote_lesson", "save_active_lesson", "lesson_store",
    ]
    for bad in bad_strings:
        assert bad not in source, f"Found forbidden reference {bad!r} in smoke script"

    # AST check: subprocess must not be imported
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "subprocess", "subprocess must not be imported in smoke script"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "") != "subprocess", "subprocess must not be imported in smoke script"
