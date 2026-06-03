"""Tests for Phase 14.2 failure taxonomy report exporter."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.failure_taxonomy import GUARDRAIL_NOTE
from scripts import create_failure_taxonomy_report as exporter


FIXED_NOW = 1700000000.0


def _write_report(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _benchmark_report(results: list[dict]) -> dict:
    return {
        "passed": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if r.get("success") is False),
        "total": len(results),
        "results": results,
    }


# --- explicit report path ---------------------------------------------------


def test_explicit_report_path_writes_json_and_md(tmp_path):
    report = _benchmark_report(
        [
            {"name": "ok_case", "success": True},
            {
                "name": "broken_env",
                "success": False,
                "validation_output": "ModuleNotFoundError: No module named 'foo'",
            },
        ]
    )
    report_path = _write_report(tmp_path / "benchmark_report_42.json", report)
    out_dir = tmp_path / "out"

    result = exporter.export_failure_taxonomy_report(
        benchmark_report=str(report_path),
        output_dir=str(out_dir),
        generated_at=FIXED_NOW,
    )

    assert result["ok"] is True
    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])
    assert json_path.is_file()
    assert md_path.is_file()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["total_cases"] == 2
    assert data["total_classified"] == 1
    assert data["counts_by_category"] == {"environment_issue": 1}
    assert data["source_benchmark_report"].endswith("benchmark_report_42.json")
    assert data["guardrail_note"] == GUARDRAIL_NOTE
    assert len(data["classifications"]) == 1
    assert data["classifications"][0]["name"] == "broken_env"
    assert data["classifications"][0]["category"] == "environment_issue"


def test_output_filenames_use_timestamp(tmp_path):
    report_path = _write_report(
        tmp_path / "benchmark_report_42.json",
        _benchmark_report([{"name": "a", "success": True}]),
    )
    result = exporter.export_failure_taxonomy_report(
        benchmark_report=str(report_path),
        output_dir=str(tmp_path / "out"),
        generated_at=FIXED_NOW,
    )
    assert Path(result["json_path"]).name == "1700000000_failure_taxonomy.json"
    assert Path(result["md_path"]).name == "1700000000_failure_taxonomy.md"


# --- --latest ---------------------------------------------------------------


def test_latest_chooses_newest_report(tmp_path):
    bench_dir = tmp_path / ".agent" / "benchmarks"
    bench_dir.mkdir(parents=True)
    _write_report(
        bench_dir / "benchmark_report_1000.json",
        _benchmark_report(
            [{"name": "old", "success": False, "fallback_count": 2}]
        ),
    )
    _write_report(
        bench_dir / "benchmark_report_2000.json",
        _benchmark_report(
            [
                {
                    "name": "new",
                    "success": False,
                    "touched_forbidden_files": ["tests/test_x.py"],
                    "changed_files": ["src/x.py"],
                }
            ]
        ),
    )

    result = exporter.export_failure_taxonomy_report(
        benchmark_report=None,
        output_dir=str(tmp_path / "out"),
        repo_path=str(tmp_path),
        use_latest=True,
        generated_at=FIXED_NOW,
    )

    assert result["ok"] is True
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["source_benchmark_report"].endswith("benchmark_report_2000.json")
    assert data["counts_by_category"] == {"forbidden_file_temptation": 1}


def test_find_latest_benchmark_report_returns_none_when_empty(tmp_path):
    assert exporter.find_latest_benchmark_report(tmp_path) is None


# --- error handling ---------------------------------------------------------


def test_missing_report_path_returns_friendly_failure(tmp_path):
    result = exporter.export_failure_taxonomy_report(
        benchmark_report=str(tmp_path / "does_not_exist.json"),
        output_dir=str(tmp_path / "out"),
        generated_at=FIXED_NOW,
    )
    assert result["ok"] is False
    assert "error" in result
    assert result.get("json_path") is None


def test_invalid_json_returns_friendly_failure(tmp_path):
    bad = tmp_path / "benchmark_report_bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    result = exporter.export_failure_taxonomy_report(
        benchmark_report=str(bad),
        output_dir=str(tmp_path / "out"),
        generated_at=FIXED_NOW,
    )
    assert result["ok"] is False
    assert "json" in result["error"].lower()
    assert result.get("json_path") is None


def test_no_report_selected_with_latest_returns_friendly_failure(tmp_path):
    result = exporter.export_failure_taxonomy_report(
        benchmark_report=None,
        output_dir=str(tmp_path / "out"),
        repo_path=str(tmp_path),
        use_latest=True,
        generated_at=FIXED_NOW,
    )
    assert result["ok"] is False
    assert "error" in result


# --- zero-case and old-shape reports ----------------------------------------


def test_zero_case_report_writes_valid_empty_report(tmp_path):
    report_path = _write_report(
        tmp_path / "benchmark_report_empty.json", _benchmark_report([])
    )
    result = exporter.export_failure_taxonomy_report(
        benchmark_report=str(report_path),
        output_dir=str(tmp_path / "out"),
        generated_at=FIXED_NOW,
    )
    assert result["ok"] is True
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["total_cases"] == 0
    assert data["total_classified"] == 0
    assert data["counts_by_category"] == {}
    assert data["classifications"] == []
    assert Path(result["md_path"]).is_file()


def test_old_report_shape_without_results_is_graceful(tmp_path):
    report_path = _write_report(
        tmp_path / "benchmark_report_old.json", {"passed": 0, "failed": 0}
    )
    result = exporter.export_failure_taxonomy_report(
        benchmark_report=str(report_path),
        output_dir=str(tmp_path / "out"),
        generated_at=FIXED_NOW,
    )
    assert result["ok"] is True
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["total_cases"] == 0
    assert data["total_classified"] == 0


def test_missing_fields_classify_as_unknown_not_crash(tmp_path):
    report_path = _write_report(
        tmp_path / "benchmark_report_partial.json",
        _benchmark_report([{"name": "mystery", "success": False}]),
    )
    result = exporter.export_failure_taxonomy_report(
        benchmark_report=str(report_path),
        output_dir=str(tmp_path / "out"),
        generated_at=FIXED_NOW,
    )
    assert result["ok"] is True
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["total_classified"] == 1
    assert data["counts_by_category"] == {"unknown": 1}


def test_passing_cases_are_not_classified(tmp_path):
    report_path = _write_report(
        tmp_path / "benchmark_report_allpass.json",
        _benchmark_report(
            [
                {"name": "a", "success": True},
                {"name": "b", "success": True},
            ]
        ),
    )
    result = exporter.export_failure_taxonomy_report(
        benchmark_report=str(report_path),
        output_dir=str(tmp_path / "out"),
        generated_at=FIXED_NOW,
    )
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["total_cases"] == 2
    assert data["total_classified"] == 0
    assert data["counts_by_category"] == {}


# --- non-mutation -----------------------------------------------------------


def test_source_report_is_not_mutated(tmp_path):
    report = _benchmark_report(
        [
            {
                "name": "broken_env",
                "success": False,
                "validation_output": "ModuleNotFoundError: x",
            }
        ]
    )
    report_path = _write_report(tmp_path / "benchmark_report_42.json", report)
    before = report_path.read_text(encoding="utf-8")

    exporter.export_failure_taxonomy_report(
        benchmark_report=str(report_path),
        output_dir=str(tmp_path / "out"),
        generated_at=FIXED_NOW,
    )

    after = report_path.read_text(encoding="utf-8")
    assert before == after


def test_build_does_not_mutate_loaded_report():
    report = _benchmark_report(
        [{"name": "x", "success": False, "fallback_count": 3}]
    )
    snapshot = json.dumps(report, sort_keys=True)
    exporter.build_failure_taxonomy(
        report, source_path="benchmark_report_42.json", generated_at=FIXED_NOW
    )
    assert json.dumps(report, sort_keys=True) == snapshot


# --- markdown ---------------------------------------------------------------


def test_markdown_contains_counts_and_guardrail(tmp_path):
    report = _benchmark_report(
        [
            {"name": "a", "success": False, "fallback_count": 1},
            {"name": "b", "success": False, "fallback_count": 1},
            {
                "name": "c",
                "success": False,
                "validation_output": "Process timed out after 60s",
            },
        ]
    )
    taxonomy = exporter.build_failure_taxonomy(
        report, source_path="benchmark_report_42.json", generated_at=FIXED_NOW
    )
    markdown = exporter.render_markdown(taxonomy)

    assert "# Failure Taxonomy Report" in markdown
    assert "model_fallback_instability" in markdown
    assert "timeout_or_cost" in markdown
    assert "benchmark_report_42.json" in markdown
    assert GUARDRAIL_NOTE in markdown
    assert "## Summary counts" in markdown


def test_markdown_handles_zero_classified():
    report = _benchmark_report([{"name": "a", "success": True}])
    taxonomy = exporter.build_failure_taxonomy(
        report, source_path="r.json", generated_at=FIXED_NOW
    )
    markdown = exporter.render_markdown(taxonomy)
    assert "# Failure Taxonomy Report" in markdown
    assert GUARDRAIL_NOTE in markdown


# --- read-only guard --------------------------------------------------------


def test_exporter_ast_guard_no_dangerous_behavior():
    source = Path("scripts/create_failure_taxonomy_report.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imports = _imported_modules(tree)
    calls = _called_names(tree)

    forbidden_import_roots = {
        "agents",
        "anthropic",
        "benchmarks",
        "database",
        "docker",
        "google",
        "httpx",
        "openai",
        "psycopg",
        "psycopg2",
        "requests",
        "sqlite3",
        "subprocess",
    }
    forbidden_calls = {
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

    assert {name.split(".", 1)[0] for name in imports}.isdisjoint(
        forbidden_import_roots
    )
    assert calls.isdisjoint(forbidden_calls)


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names
