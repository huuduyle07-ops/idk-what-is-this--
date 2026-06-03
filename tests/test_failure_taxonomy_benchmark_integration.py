"""Phase 14.3 — Failure taxonomy benchmark report integration (display-only).

These tests cover surfacing the Phase 14 failure taxonomy in:
  * the benchmark report Markdown (``run_benchmarks.write_markdown_report``)
  * the web benchmark report route (``/benchmarks/report``)
as read-only evidence that never changes scoring, pass/fail, patching,
validation, lessons, or model routing.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from benchmarks import run_benchmarks
from core import failure_taxonomy as ft
from scripts import create_failure_taxonomy_report as exporter


REQUIRED_GUARDRAIL = (
    "Failure taxonomy is read-only and does not affect benchmark scoring, "
    "patching, validation, or lesson promotion."
)


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


def _failing_env_case(name: str = "broken_env") -> dict:
    return {
        "name": name,
        "success": False,
        "validation_output": "ModuleNotFoundError: No module named 'foo'",
    }


def _failing_forbidden_case(name: str = "touched_forbidden") -> dict:
    return {
        "name": name,
        "success": False,
        "touched_forbidden_files": ["tests/test_x.py"],
        "changed_files": ["src/x.py"],
    }


# --- core display-only summary ----------------------------------------------


def test_guardrail_note_constant_matches_required_text():
    assert ft.BENCHMARK_DISPLAY_GUARDRAIL_NOTE == REQUIRED_GUARDRAIL


def test_summarize_classifies_only_failing_cases():
    report = _report(
        [
            {"name": "ok", "success": True},
            {"name": "skip", "success": False, "skipped": True},
            _failing_env_case(),
            _failing_forbidden_case(),
        ]
    )
    summary = ft.summarize_benchmark_failures(report)

    assert summary["total_cases"] == 4
    assert summary["total_failing"] == 2
    assert summary["counts_by_category"] == {
        "forbidden_file_temptation": 1,
        "environment_issue": 1,
    }
    names = {c["name"] for c in summary["classifications"]}
    assert names == {"broken_env", "touched_forbidden"}
    for item in summary["classifications"]:
        assert set(item) >= {
            "name",
            "category",
            "confidence",
            "explanation",
            "recommended_next_action",
        }
    assert summary["guardrail_note"] == REQUIRED_GUARDRAIL


def test_summarize_empty_when_no_failing_cases():
    report = _report([{"name": "ok", "success": True}])
    summary = ft.summarize_benchmark_failures(report)
    assert summary["total_failing"] == 0
    assert summary["counts_by_category"] == {}
    assert summary["classifications"] == []


def test_summarize_handles_old_report_shape_without_crash():
    summary = ft.summarize_benchmark_failures({"passed": 0, "failed": 0})
    assert summary["total_cases"] == 0
    assert summary["total_failing"] == 0
    summary_none = ft.summarize_benchmark_failures({})
    assert summary_none["total_failing"] == 0


def test_summarize_does_not_mutate_report():
    report = _report([_failing_env_case(), {"name": "ok", "success": True}])
    snapshot = json.dumps(report, sort_keys=True)
    ft.summarize_benchmark_failures(report)
    assert json.dumps(report, sort_keys=True) == snapshot


# --- markdown integration ---------------------------------------------------


def test_markdown_report_includes_taxonomy_section_for_failing_cases(tmp_path):
    report = _report([{"name": "ok", "success": True}, _failing_forbidden_case()])
    md_path = tmp_path / "benchmark_report_1.md"
    run_benchmarks.write_markdown_report(report, md_path)
    text = md_path.read_text(encoding="utf-8")

    assert "## Failure Taxonomy" in text
    assert "forbidden_file_temptation" in text
    assert "touched_forbidden" in text
    assert REQUIRED_GUARDRAIL in text


def test_markdown_report_friendly_empty_state(tmp_path):
    report = _report([{"name": "ok", "success": True}])
    md_path = tmp_path / "benchmark_report_2.md"
    run_benchmarks.write_markdown_report(report, md_path)
    text = md_path.read_text(encoding="utf-8")

    assert "## Failure Taxonomy" in text
    assert "No failing cases to classify" in text
    assert REQUIRED_GUARDRAIL in text


def test_markdown_report_old_shape_does_not_crash(tmp_path):
    md_path = tmp_path / "benchmark_report_3.md"
    run_benchmarks.write_markdown_report({"passed": 0, "failed": 0}, md_path)
    text = md_path.read_text(encoding="utf-8")
    assert "## Failure Taxonomy" in text
    assert "No failing cases to classify" in text


# --- display-only / scoring untouched ---------------------------------------


def test_scoring_fields_unchanged_by_markdown_and_summary(tmp_path):
    results = [
        {"name": "ok", "success": True},
        _failing_env_case(),
        {"name": "skip", "success": False, "skipped": True},
    ]
    report = _report(results)
    scoring_before = {
        k: report[k]
        for k in ("passed", "failed", "skipped", "total", "success_rate")
    }

    ft.summarize_benchmark_failures(report)
    run_benchmarks.write_markdown_report(report, tmp_path / "r.md")

    scoring_after = {
        k: report[k]
        for k in ("passed", "failed", "skipped", "total", "success_rate")
    }
    assert scoring_before == scoring_after
    # The per-case success flags must be untouched too.
    assert [r.get("success") for r in report["results"]] == [True, False, False]


# --- web route integration --------------------------------------------------


@pytest.fixture
def client():
    from web import app as web_app

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as test_client:
        yield test_client


def test_web_report_route_includes_taxonomy_counts(client, tmp_path):
    bench_dir = tmp_path / ".agent" / "benchmarks"
    bench_dir.mkdir(parents=True)
    report = _report([{"name": "ok", "success": True}, _failing_forbidden_case()])
    (bench_dir / "benchmark_report_123.json").write_text(
        json.dumps(report), encoding="utf-8"
    )

    resp = client.get(
        "/benchmarks/report",
        query_string={
            "repo_path": str(tmp_path),
            "filename": "benchmark_report_123.json",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()

    assert "failure_taxonomy" in body
    taxonomy = body["failure_taxonomy"]
    assert taxonomy["counts_by_category"] == {"forbidden_file_temptation": 1}
    assert taxonomy["total_failing"] == 1
    assert taxonomy["guardrail_note"] == REQUIRED_GUARDRAIL
    item = taxonomy["classifications"][0]
    assert item["name"] == "touched_forbidden"
    assert item["category"] == "forbidden_file_temptation"
    assert "confidence" in item
    assert "explanation" in item
    assert "recommended_next_action" in item
    # Scoring fields are still present and unchanged in the response.
    assert body["passed"] == 1
    assert body["failed"] == 1
    assert body["total"] == 2


def test_web_report_route_does_not_write_taxonomy_artifacts(client, tmp_path):
    bench_dir = tmp_path / ".agent" / "benchmarks"
    bench_dir.mkdir(parents=True)
    report = _report([_failing_env_case()])
    (bench_dir / "benchmark_report_5.json").write_text(
        json.dumps(report), encoding="utf-8"
    )

    client.get(
        "/benchmarks/report",
        query_string={
            "repo_path": str(tmp_path),
            "filename": "benchmark_report_5.json",
        },
    )

    # Viewing must not create new taxonomy artifacts on disk.
    assert sorted(p.name for p in bench_dir.iterdir()) == ["benchmark_report_5.json"]
    assert not (tmp_path / ".agent" / "failure_taxonomy").exists()
    # The stored report file is unchanged (no failure_taxonomy key written).
    stored = json.loads((bench_dir / "benchmark_report_5.json").read_text("utf-8"))
    assert "failure_taxonomy" not in stored


# --- exporter unchanged -----------------------------------------------------


def test_phase_142_exporter_still_works(tmp_path):
    report_path = tmp_path / "benchmark_report_99.json"
    report_path.write_text(
        json.dumps(_report([_failing_env_case()])), encoding="utf-8"
    )
    result = exporter.export_failure_taxonomy_report(
        benchmark_report=str(report_path),
        output_dir=str(tmp_path / "out"),
        generated_at=1700000000.0,
    )
    assert result["ok"] is True
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["counts_by_category"] == {"environment_issue": 1}


# --- AST guard: display-only, no scoring/patching/validation/etc. ------------


def _func_by_name(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found")


def _called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                names.add(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                names.add(child.func.attr)
    return names


def _subscript_assignment_keys(node: ast.AST) -> set[str]:
    keys: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, (ast.Assign, ast.AugAssign)):
            targets = child.targets if isinstance(child, ast.Assign) else [child.target]
            for target in targets:
                if isinstance(target, ast.Subscript) and isinstance(
                    target.slice, ast.Constant
                ):
                    keys.add(str(target.slice.value))
    return keys


FORBIDDEN_CALLS = {
    "ChatCompletion",
    "Popen",
    "apply_patch_plan",
    "check_call",
    "check_output",
    "commit",
    "create_lesson",
    "create_lesson_candidate",
    "executemany",
    "from_env",
    "generate_content",
    "promote_lesson",
    "run_benchmark",
    "run_benchmarks",
    "run_deepseek_review",
    "run_gemini_request",
    "run_patch_plan_with_artifacts",
    "run_validation_command",
    "start_overnight_async",
    "system",
}
SCORING_KEYS = {"passed", "failed", "total", "success", "success_rate", "score", "rank"}


def test_core_taxonomy_helpers_are_display_only_ast_guard():
    tree = ast.parse(
        Path("core/failure_taxonomy.py").read_text(encoding="utf-8")
    )
    for fname in ("summarize_benchmark_failures", "render_benchmark_taxonomy_lines"):
        func = _func_by_name(tree, fname)
        assert _called_names(func).isdisjoint(FORBIDDEN_CALLS)
        assert _subscript_assignment_keys(func).isdisjoint(SCORING_KEYS)


def test_web_report_route_is_display_only_ast_guard():
    tree = ast.parse(Path("web/app.py").read_text(encoding="utf-8"))
    func = _func_by_name(tree, "benchmarks_report_route")
    calls = _called_names(func)
    # The route must not write artifacts or run/patch/score anything.
    assert calls.isdisjoint(FORBIDDEN_CALLS)
    assert "write_text" not in calls
    assert "mkdir" not in calls
    assert _subscript_assignment_keys(func).isdisjoint(SCORING_KEYS)
