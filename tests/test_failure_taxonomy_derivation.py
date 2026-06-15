"""Tests for Phase 14.5 failure taxonomy data-derivation report.

Covers:
1. Report builds JSON and Markdown.
2. Known benchmark failure signals map to expected categories.
3. Security/tool failures map to security_tool_or_permission.
4. Wrong-file/decoy cases map to wrong_file_or_decoy.
5. Forbidden-file cases map to forbidden_file_or_scope_violation.
6. False-positive no-patch cases map to false_positive_no_patch.
7. Unknown/invalid artifacts are tolerated.
8. Unmapped cases are preserved, not forced.
9. Category enum is small and deterministic.
10. Import/side-effect guard: no model clients, no Flask, no DB,
    no subprocess, no patch apply, no lesson promotion.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.failure_taxonomy_derivation import (
    DERIVATION_CATEGORIES,
    DERIVATION_GUARDRAIL_NOTE,
    classify_benchmark_case,
    collect_signal_inventory,
    derive_taxonomy_report,
    render_derivation_markdown,
)
import scripts.create_failure_taxonomy_derivation_report as script


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_case(name: str = "test_case", passed: bool | None = None, **kwargs) -> dict:
    case: dict = {"name": name}
    if passed is not None:
        case["success"] = passed
    case.update(kwargs)
    return case


def _bench_report(results: list[dict]) -> dict:
    return {
        "passed": sum(1 for r in results if r.get("success") is True),
        "failed": sum(1 for r in results if r.get("success") is False),
        "total": len(results),
        "results": results,
    }


def _write_bench(path: Path, results: list[dict]) -> None:
    path.write_text(json.dumps(_bench_report(results)), encoding="utf-8")


def _repo_with_bench(tmp_path: Path, results: list[dict]) -> Path:
    bench_dir = tmp_path / ".agent" / "benchmarks"
    bench_dir.mkdir(parents=True)
    _write_bench(bench_dir / "benchmark_report_1.json", results)
    return tmp_path


# ── Test 1: report builds JSON and Markdown ───────────────────────────────────

def test_report_builds_json_and_markdown(tmp_path):
    repo = _repo_with_bench(tmp_path, [
        {"name": "passing_case", "success": True, "language": "go"},
        {"name": "failing_case", "success": False, "language": "go", "category": "async_error"},
    ])
    out_dir = tmp_path / "out"
    result = script.run_derivation(
        repo_path=str(repo),
        output_dir=str(out_dir),
        generated_at=1700000000.0,
    )

    assert result["ok"] is True
    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])
    assert json_path.is_file()
    assert md_path.is_file()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["report_kind"] == "failure_taxonomy_derivation"
    assert "summary" in data
    assert "signal_inventory" in data
    assert "candidate_taxonomy" in data
    assert "mapping_rules" in data
    assert "classified_cases" in data
    assert "unmapped_cases" in data
    assert "recommendations" in data
    assert "generated_at" in data

    md = md_path.read_text(encoding="utf-8")
    assert "Phase 14.5" in md
    assert "read-only" in md.lower() or "guardrail" in md.lower()
    assert "## 1. Summary" in md
    assert "## 7. Recommendations" in md


def test_report_json_filename_contains_timestamp(tmp_path):
    repo = _repo_with_bench(tmp_path, [])
    out_dir = tmp_path / "out"
    result = script.run_derivation(
        repo_path=str(repo),
        output_dir=str(out_dir),
        generated_at=1700000000.0,
    )
    assert "failure-taxonomy-derivation.json" in result["json_path"]
    assert "failure-taxonomy-derivation.md" in result["md_path"]


# ── Test 2: known benchmark failure signals map correctly ─────────────────────

def test_async_error_category_maps_to_async_or_lifecycle():
    case = _make_case("async_test", passed=False, category="async_error")
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "async_or_lifecycle_bug"
    assert det is True
    assert conf == "high"


def test_side_effect_category_maps_correctly():
    case = _make_case("side_effect_test", passed=False, category="side_effect")
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "state_mutation_or_side_effect"
    assert det is True


def test_missing_import_category_maps_correctly():
    case = _make_case("import_test", passed=False, category="missing_import")
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "missing_import_or_dependency"
    assert det is True


def test_logic_validation_category_maps_to_data_validation():
    case = _make_case("logic_val_test", passed=False, category="logic_validation")
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "data_validation_or_boundary"
    assert det is True


def test_boundary_logic_category_maps_to_data_validation():
    case = _make_case("boundary_test", passed=False, category="boundary_logic")
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "data_validation_or_boundary"
    assert det is True


def test_multi_file_root_cause_maps_correctly():
    case = _make_case("multi_test", passed=False, category="multi_file_root_cause")
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "root_cause_multifile"
    assert det is True


# ── Test 3: security/tool failures map to security_tool_or_permission ─────────

def test_access_denied_in_validation_maps_to_security():
    case = _make_case(
        "go_blocked",
        passed=False,
        validation_output="fork/exec go.exe: Access is denied.",
    )
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "security_tool_or_permission"
    assert det is True
    assert conf == "high"


def test_failure_kind_security_tool_maps_to_security():
    case = _make_case("sec_case", passed=False, failure_kind="security_tool")
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "security_tool_or_permission"
    assert det is True


def test_antivirus_marker_maps_to_security():
    case = _make_case(
        "av_case",
        passed=False,
        validation_output="antivirus blocked the execution",
    )
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "security_tool_or_permission"


def test_agent_validation_tail_access_denied_maps_to_security(tmp_path):
    """Security signal from nested validation_summary is detected."""
    case = _make_case(
        "nested_sec",
        passed=False,
        validation_summary={"agent_validation_tail": "Access is denied."},
    )
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "security_tool_or_permission"


# ── Test 4: wrong-file/decoy cases map to wrong_file_or_decoy ────────────────

def test_changed_files_disjoint_from_expected_maps_to_wrong_file():
    case = _make_case(
        "decoy_case",
        passed=False,
        changed_files=["decoy.go"],
        expected_changed_files=["target.go"],
    )
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "wrong_file_or_decoy"
    assert det is True
    assert conf == "high"


def test_overlapping_expected_and_changed_does_not_map_to_wrong_file():
    case = _make_case(
        "ok_file",
        passed=False,
        changed_files=["target.go"],
        expected_changed_files=["target.go"],
        category="correctness",
    )
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat != "wrong_file_or_decoy"


# ── Test 5: forbidden-file cases map to forbidden_file_or_scope_violation ─────

def test_forbidden_file_touch_maps_to_scope_violation():
    case = _make_case(
        "forbidden_case",
        passed=False,
        touched_forbidden_files=["tests/test_fixture.py"],
    )
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "forbidden_file_or_scope_violation"
    assert det is True
    assert conf == "high"


def test_multiple_forbidden_files_still_maps_correctly():
    case = _make_case(
        "multi_forbidden",
        passed=False,
        touched_forbidden_files=["tests/a.py", "tests/b.py"],
    )
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "forbidden_file_or_scope_violation"


# ── Test 6: false-positive no-patch cases map to false_positive_no_patch ─────

def test_expects_patch_false_maps_to_no_patch():
    case = _make_case("no_patch_case", passed=False, expects_patch=False)
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "false_positive_no_patch"
    assert det is True
    assert conf == "high"


def test_no_patch_expected_true_maps_to_no_patch():
    case = _make_case("no_patch_case2", passed=False, no_patch_expected=True)
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat == "false_positive_no_patch"
    assert det is True


# ── Test 7: unknown/invalid artifacts are tolerated ───────────────────────────

def test_empty_repo_produces_valid_report(tmp_path):
    report = derive_taxonomy_report(repo_path=tmp_path)
    assert report["report_kind"] == "failure_taxonomy_derivation"
    assert report["summary"]["total_benchmark_reports_scanned"] == 0
    assert report["summary"]["total_failing_cases_classified"] == 0
    assert isinstance(report["classified_cases"], list)
    assert isinstance(report["unmapped_cases"], list)
    assert isinstance(report["recommendations"], list)


def test_invalid_json_benchmark_artifact_is_tolerated(tmp_path):
    bench_dir = tmp_path / ".agent" / "benchmarks"
    bench_dir.mkdir(parents=True)
    (bench_dir / "benchmark_report_bad.json").write_text("NOT JSON {{{", encoding="utf-8")
    report = derive_taxonomy_report(repo_path=tmp_path)
    assert report["summary"]["total_benchmark_reports_scanned"] == 0


def test_non_dict_json_benchmark_artifact_is_tolerated(tmp_path):
    bench_dir = tmp_path / ".agent" / "benchmarks"
    bench_dir.mkdir(parents=True)
    (bench_dir / "benchmark_report_list.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    report = derive_taxonomy_report(repo_path=tmp_path)
    assert report["summary"]["total_benchmark_reports_scanned"] == 0


def test_missing_agent_dir_is_tolerated(tmp_path):
    """A repo with no .agent/ at all should not raise."""
    report = derive_taxonomy_report(repo_path=tmp_path)
    assert report["report_kind"] == "failure_taxonomy_derivation"


def test_partial_case_with_no_signals_is_tolerated():
    """A case with no recognizable signals falls through to unknown/insufficient."""
    case = _make_case("bare_case", passed=False)
    cat, rule, conf, evidence, det = classify_benchmark_case(case)
    assert cat in {"unknown", "insufficient_evidence"}


# ── Test 8: unmapped cases are preserved, not forced ─────────────────────────

def test_unmapped_cases_preserved_not_forced(tmp_path):
    repo = _repo_with_bench(tmp_path, [
        {"name": "mystery_case", "success": False},
    ])
    report = derive_taxonomy_report(repo_path=repo)
    unmapped = report["unmapped_cases"]
    assert len(unmapped) >= 1
    assert any(u["name"] == "mystery_case" for u in unmapped)


def test_clearly_passed_cases_not_classified(tmp_path):
    repo = _repo_with_bench(tmp_path, [
        {"name": "pass_case", "success": True, "language": "go"},
    ])
    report = derive_taxonomy_report(repo_path=repo)
    assert report["summary"]["total_failing_cases_classified"] == 0
    assert len(report["classified_cases"]) == 0


def test_unmapped_entries_contain_reason_field(tmp_path):
    repo = _repo_with_bench(tmp_path, [
        {"name": "bare", "success": False},
    ])
    report = derive_taxonomy_report(repo_path=repo)
    for u in report["unmapped_cases"]:
        assert "reason" in u
        assert "name" in u


# ── Test 9: category enum is small and deterministic ─────────────────────────

def test_derivation_categories_is_fixed_tuple():
    assert isinstance(DERIVATION_CATEGORIES, tuple)
    assert len(DERIVATION_CATEGORIES) == 13


def test_derivation_categories_exact_members():
    expected = (
        "toolchain_environment",
        "security_tool_or_permission",
        "validation_command_gap",
        "wrong_file_or_decoy",
        "forbidden_file_or_scope_violation",
        "missing_import_or_dependency",
        "async_or_lifecycle_bug",
        "state_mutation_or_side_effect",
        "data_validation_or_boundary",
        "root_cause_multifile",
        "false_positive_no_patch",
        "insufficient_evidence",
        "unknown",
    )
    assert DERIVATION_CATEGORIES == expected


def test_derivation_categories_ends_with_unknown():
    assert DERIVATION_CATEGORIES[-1] == "unknown"


def test_candidate_taxonomy_in_report_matches_enum(tmp_path):
    report = derive_taxonomy_report(repo_path=tmp_path)
    assert report["candidate_taxonomy"] == list(DERIVATION_CATEGORIES)


def test_counts_by_category_only_contains_known_categories(tmp_path):
    repo = _repo_with_bench(tmp_path, [
        {"name": "case1", "success": False, "category": "async_error"},
    ])
    report = derive_taxonomy_report(repo_path=repo)
    for cat in report["counts_by_category"]:
        assert cat in DERIVATION_CATEGORIES


# ── Test 10: import / side-effect guard ───────────────────────────────────────

_DERIVATION_MODULE = (
    Path(__file__).parent.parent / "core" / "failure_taxonomy_derivation.py"
)
_DERIVATION_SOURCE = _DERIVATION_MODULE.read_text(encoding="utf-8")


def test_no_flask_import_in_derivation_module():
    tree = ast.parse(_DERIVATION_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "flask" not in alias.name.lower(), alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "flask" not in module.lower(), module


def test_no_subprocess_in_derivation_module():
    tree = ast.parse(_DERIVATION_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "subprocess", "subprocess must not be imported"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "") != "subprocess", "subprocess must not be imported"


def test_no_model_client_in_derivation_module():
    for bad in ("anthropic", "openai", "litellm", "ollama", "bedrock"):
        assert bad not in _DERIVATION_SOURCE, f"Found {bad!r} in derivation module"


def test_no_db_client_in_derivation_module():
    for bad in ("sqlalchemy", "psycopg", "pymongo", "motor", "sqlite3"):
        assert bad not in _DERIVATION_SOURCE, f"Found {bad!r} in derivation module"


def test_no_lesson_promotion_in_derivation_module():
    for bad in ("promote_lesson", "save_active_lesson", "lesson_store"):
        assert bad not in _DERIVATION_SOURCE, f"Found {bad!r} in derivation module"


def test_no_patch_apply_in_derivation_module():
    for bad in ("apply_patch", "patch_apply", "run_patch", "exec_patch"):
        assert bad not in _DERIVATION_SOURCE, f"Found {bad!r} in derivation module"


def test_no_dream_runner_in_derivation_module():
    for bad in ("sleeping_consultant", "run_dream", "dream_runner"):
        assert bad not in _DERIVATION_SOURCE, f"Found {bad!r} in derivation module"


def test_derivation_module_only_imports_stdlib():
    """The core derivation module must import only stdlib modules."""
    stdlib_ok = {"__future__", "json", "pathlib", "typing"}
    tree = ast.parse(_DERIVATION_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in stdlib_ok, (
                f"Unexpected import in failure_taxonomy_derivation: {module!r}"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in stdlib_ok, (
                    f"Unexpected import in failure_taxonomy_derivation: {alias.name!r}"
                )
