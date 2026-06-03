"""Phase 14.4 — Failure taxonomy trend / dogfood report (read-only).

These tests cover comparing the Phase 14 failure taxonomy across *multiple*
already-existing benchmark reports. The trend report is analysis-only: it never
runs benchmarks, changes scoring, patches, validates, promotes lessons, calls a
model/API, writes a database, touches Docker, spawns subprocesses, makes network
calls, or mutates the source benchmark reports. The only writes performed are
the two explicit trend artifacts produced by the optional script.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core import failure_taxonomy_trends as trends
from scripts import create_failure_taxonomy_trend_report as trend_script


# --- fixtures ---------------------------------------------------------------


def _report(results: list[dict]) -> dict:
    passed = sum(1 for r in results if r.get("success") is True)
    skipped = sum(1 for r in results if r.get("skipped"))
    total = len(results)
    failed = max(0, total - passed - skipped)
    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total": total,
        "success_rate": (passed / total) if total else 0,
        "results": results,
    }


def _env_case(name: str) -> dict:
    return {
        "name": name,
        "success": False,
        "validation_output": "ModuleNotFoundError: No module named 'x'",
    }


def _forbidden_case(name: str) -> dict:
    return {
        "name": name,
        "success": False,
        "touched_forbidden_files": ["tests/test_a.py"],
        "changed_files": ["src/a.py"],
    }


def _timeout_case(name: str) -> dict:
    return {"name": name, "success": False, "timed_out": True}


def _baseline() -> dict:
    return _report(
        [
            _env_case("alpha"),
            _forbidden_case("beta"),
            {"name": "ok1", "success": True},
        ]
    )


def _latest() -> dict:
    return _report(
        [
            _timeout_case("alpha"),  # alpha changed env -> timeout
            _env_case("gamma"),  # gamma is new
            {"name": "ok2", "success": True},
        ]
    )


# --- core comparison --------------------------------------------------------


def test_trend_compares_two_reports():
    trend = trends.compare_failure_taxonomies(
        [_baseline(), _latest()], identifiers=["report_A", "report_B"]
    )
    assert trend["ok"] is True
    assert trend["report_count"] == 2
    assert [r["identifier"] for r in trend["reports"]] == ["report_A", "report_B"]
    assert [r["total_failing"] for r in trend["reports"]] == [2, 2]
    assert trend["baseline"] == "report_A"
    assert trend["latest"] == "report_B"
    assert trend["reports"][0]["counts_by_category"] == {
        "forbidden_file_temptation": 1,
        "environment_issue": 1,
    }
    assert trend["reports"][1]["counts_by_category"] == {
        "timeout_or_cost": 1,
        "environment_issue": 1,
    }


def test_trend_category_count_deltas():
    trend = trends.compare_failure_taxonomies(
        [_baseline(), _latest()], identifiers=["A", "B"]
    )
    deltas = trend["category_deltas"]
    assert deltas["environment_issue"] == 0
    assert deltas["forbidden_file_temptation"] == -1
    assert deltas["timeout_or_cost"] == 1


def test_trend_new_and_disappeared_categories():
    trend = trends.compare_failure_taxonomies(
        [_baseline(), _latest()], identifiers=["A", "B"]
    )
    assert trend["new_categories"] == ["timeout_or_cost"]
    assert trend["disappeared_categories"] == ["forbidden_file_temptation"]


def test_trend_changed_case_category():
    trend = trends.compare_failure_taxonomies(
        [_baseline(), _latest()], identifiers=["A", "B"]
    )
    changed = trend["changed_cases"]
    assert len(changed) == 1
    assert changed[0]["name"] == "alpha"
    assert changed[0]["from_category"] == "environment_issue"
    assert changed[0]["to_category"] == "timeout_or_cost"


def test_trend_next_action_notes_are_text_only():
    trend = trends.compare_failure_taxonomies(
        [_baseline(), _latest()], identifiers=["A", "B"]
    )
    notes = trend["next_action_notes"]
    assert isinstance(notes, list)
    assert all(isinstance(n, str) for n in notes)
    assert trend["guardrail_note"]


def test_trend_fewer_than_two_reports_graceful():
    one = trends.compare_failure_taxonomies([_baseline()], identifiers=["only"])
    assert one["ok"] is False
    assert one["report_count"] == 1
    assert "at least two" in one["error"].lower()

    none = trends.compare_failure_taxonomies([])
    assert none["ok"] is False
    assert none["report_count"] == 0


def test_trend_zero_failure_reports():
    a = _report([{"name": "ok", "success": True}])
    b = _report([{"name": "ok", "success": True}])
    trend = trends.compare_failure_taxonomies([a, b], identifiers=["A", "B"])
    assert trend["ok"] is True
    assert [r["total_failing"] for r in trend["reports"]] == [0, 0]
    assert trend["new_categories"] == []
    assert trend["disappeared_categories"] == []
    assert trend["changed_cases"] == []


def test_trend_old_report_shape_does_not_crash():
    trend = trends.compare_failure_taxonomies(
        [{"passed": 0, "failed": 0}, {"foo": "bar"}], identifiers=["old1", "old2"]
    )
    assert trend["ok"] is True
    assert [r["total_failing"] for r in trend["reports"]] == [0, 0]


def test_trend_does_not_mutate_source_reports():
    a, b = _baseline(), _latest()
    snap_a = json.dumps(a, sort_keys=True)
    snap_b = json.dumps(b, sort_keys=True)
    trends.compare_failure_taxonomies([a, b], identifiers=["A", "B"])
    assert json.dumps(a, sort_keys=True) == snap_a
    assert json.dumps(b, sort_keys=True) == snap_b


def test_trend_accepts_report_paths(tmp_path):
    p1 = tmp_path / "benchmark_report_1.json"
    p2 = tmp_path / "benchmark_report_2.json"
    p1.write_text(json.dumps(_baseline()), encoding="utf-8")
    p2.write_text(json.dumps(_latest()), encoding="utf-8")
    trend = trends.compare_failure_taxonomies([p1, p2])
    assert trend["ok"] is True
    assert trend["report_count"] == 2
    # Identifiers default to the file stems when paths are given.
    assert [r["identifier"] for r in trend["reports"]] == [
        "benchmark_report_1",
        "benchmark_report_2",
    ]


# --- markdown ---------------------------------------------------------------


def test_trend_markdown_contains_fields():
    trend = trends.compare_failure_taxonomies(
        [_baseline(), _latest()], identifiers=["report_A", "report_B"]
    )
    md = trends.format_trend_markdown(trend)
    assert "# Failure Taxonomy Trend" in md
    assert "report_A" in md
    assert "report_B" in md
    assert "timeout_or_cost" in md
    assert "forbidden_file_temptation" in md
    assert "alpha" in md
    assert trend["guardrail_note"] in md


def test_trend_markdown_friendly_when_too_few_reports():
    trend = trends.compare_failure_taxonomies([_baseline()], identifiers=["only"])
    md = trends.format_trend_markdown(trend)
    assert "# Failure Taxonomy Trend" in md
    assert "at least two" in md.lower()


# --- script -----------------------------------------------------------------


def test_script_writes_json_and_markdown(tmp_path):
    bench_dir = tmp_path / ".agent" / "benchmarks"
    bench_dir.mkdir(parents=True)
    (bench_dir / "benchmark_report_1.json").write_text(
        json.dumps(_baseline()), encoding="utf-8"
    )
    (bench_dir / "benchmark_report_2.json").write_text(
        json.dumps(_latest()), encoding="utf-8"
    )
    out_dir = tmp_path / ".agent" / "failure_taxonomy"

    result = trend_script.export_failure_taxonomy_trend_report(
        repo_path=str(tmp_path),
        output_dir=str(out_dir),
        generated_at=1700000000.0,
    )

    assert result["ok"] is True
    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])
    assert json_path.exists()
    assert md_path.exists()
    assert json_path.name == "1700000000_failure_taxonomy_trend.json"
    assert md_path.name == "1700000000_failure_taxonomy_trend.md"

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["report_count"] == 2
    assert data["new_categories"] == ["timeout_or_cost"]
    assert "# Failure Taxonomy Trend" in md_path.read_text(encoding="utf-8")

    # Source benchmark reports are untouched (no trend key written into them).
    stored = json.loads((bench_dir / "benchmark_report_1.json").read_text("utf-8"))
    assert "category_deltas" not in stored


def test_script_friendly_when_fewer_than_two_reports(tmp_path):
    bench_dir = tmp_path / ".agent" / "benchmarks"
    bench_dir.mkdir(parents=True)
    (bench_dir / "benchmark_report_1.json").write_text(
        json.dumps(_baseline()), encoding="utf-8"
    )
    result = trend_script.export_failure_taxonomy_trend_report(
        repo_path=str(tmp_path),
        output_dir=str(tmp_path / "out"),
        generated_at=1700000000.0,
    )
    assert result["ok"] is False
    assert "at least two" in result["error"].lower()
    assert result["json_path"] is None


def test_script_friendly_when_invalid_json(tmp_path):
    bench_dir = tmp_path / ".agent" / "benchmarks"
    bench_dir.mkdir(parents=True)
    (bench_dir / "benchmark_report_1.json").write_text(
        json.dumps(_baseline()), encoding="utf-8"
    )
    (bench_dir / "benchmark_report_2.json").write_text("{not json", encoding="utf-8")
    result = trend_script.export_failure_taxonomy_trend_report(
        repo_path=str(tmp_path),
        output_dir=str(tmp_path / "out"),
        generated_at=1700000000.0,
    )
    # Only one valid report remains -> friendly insufficient-reports failure.
    assert result["ok"] is False
    assert "at least two" in result["error"].lower()


# --- AST guards: analysis-only ----------------------------------------------


def _top_functions(tree: ast.AST) -> list[ast.FunctionDef]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]


def _called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                names.add(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                names.add(child.func.attr)
    return names


FORBIDDEN_CALLS = {
    "ChatCompletion",
    "Popen",
    "apply_patch_plan",
    "check_call",
    "check_output",
    "commit",
    "connect",
    "create_connection",
    "create_lesson",
    "create_lesson_candidate",
    "executemany",
    "from_env",
    "generate_content",
    "promote_lesson",
    "recv",
    "run_benchmark",
    "run_benchmarks",
    "run_deepseek_review",
    "run_gemini_request",
    "run_patch_plan_with_artifacts",
    "run_validation_command",
    "sendall",
    "socket",
    "start_overnight_async",
    "system",
    "urlopen",
    "urlretrieve",
}


def test_core_trends_module_is_analysis_only_ast_guard():
    tree = ast.parse(
        Path("core/failure_taxonomy_trends.py").read_text(encoding="utf-8")
    )
    calls: set[str] = set()
    for func in _top_functions(tree):
        calls |= _called_names(func)
    assert calls.isdisjoint(FORBIDDEN_CALLS)
    # The core module must never write files or create directories.
    assert "write_text" not in calls
    assert "mkdir" not in calls
    assert "open" not in calls


def test_script_is_analysis_only_ast_guard():
    tree = ast.parse(
        Path("scripts/create_failure_taxonomy_trend_report.py").read_text(
            encoding="utf-8"
        )
    )
    calls: set[str] = set()
    for func in _top_functions(tree):
        calls |= _called_names(func)
    # The script may write its two explicit artifacts (write_text/mkdir) but
    # must not run/patch/validate/score/train/network/subprocess anything.
    assert calls.isdisjoint(FORBIDDEN_CALLS)
