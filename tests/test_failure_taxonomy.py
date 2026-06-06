"""Tests for Phase 14.1 read-only failure taxonomy classifier."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.failure_taxonomy import (
    CATEGORIES,
    GUARDRAIL_NOTE,
    FailureClassification,
    classify_benchmark_failure_kind,
    classify_failure,
    format_failure_taxonomy_markdown,
    format_failure_taxonomy_report,
)


def _assert_basic(result: FailureClassification, category: str):
    assert isinstance(result, FailureClassification)
    assert result.category == category
    assert category in CATEGORIES
    assert 0.0 < result.confidence <= 1.0
    assert isinstance(result.evidence, list)
    assert result.explanation
    assert result.recommended_next_action


# --- one synthetic input per category --------------------------------------


def test_environment_issue_from_validation_output():
    result = classify_failure(
        {"name": "c", "passed": False},
        validation_output="ModuleNotFoundError: No module named 'foo'",
    )
    _assert_basic(result, "environment_issue")


def test_timeout_or_cost_from_validation_output():
    result = classify_failure(
        {"name": "c", "passed": False},
        validation_output="Process timed out after 60s",
    )
    _assert_basic(result, "timeout_or_cost")


def test_validation_command_failure_from_flag():
    result = classify_failure(
        {"name": "c", "passed": False, "validation_command_ok": False}
    )
    _assert_basic(result, "validation_command_failure")


def test_forbidden_file_temptation():
    result = classify_failure(
        {
            "name": "c",
            "passed": False,
            "changed_files": ["src/a.py"],
            "touched_forbidden_files": ["tests/test_a.py"],
        }
    )
    _assert_basic(result, "forbidden_file_temptation")


def test_no_patch_expected_but_patch_produced():
    result = classify_failure(
        {
            "name": "c",
            "passed": False,
            "expects_patch": False,
            "changed_files": ["src/a.py"],
            "total_changed_lines": 12,
        }
    )
    _assert_basic(result, "no_patch_expected")


def test_retrieval_miss_from_replay_summary():
    result = classify_failure(
        {"name": "c", "passed": False},
        replay_summary={"retrieved_count": 0},
    )
    _assert_basic(result, "retrieval_miss")


def test_wrong_file():
    result = classify_failure(
        {
            "name": "c",
            "passed": False,
            "expected_changed_files": ["src/target.py"],
            "changed_files": ["src/unrelated.py"],
            "total_changed_lines": 10,
        }
    )
    _assert_basic(result, "wrong_file")


def test_patch_too_large():
    result = classify_failure(
        {
            "name": "c",
            "passed": False,
            "expected_changed_files": ["src/a.py"],
            "changed_files": ["src/a.py"],
            "total_changed_lines": 999,
        }
    )
    _assert_basic(result, "patch_too_large")


def test_patch_too_small():
    result = classify_failure(
        {
            "name": "c",
            "passed": False,
            "expected_changed_files": ["src/a.py"],
            "changed_files": ["src/a.py"],
            "total_changed_lines": 1,
        }
    )
    _assert_basic(result, "patch_too_small")


def test_model_fallback_instability():
    result = classify_failure(
        {"name": "c", "passed": False, "fallback_count": 3}
    )
    _assert_basic(result, "model_fallback_instability")


def test_validation_gap_green_but_failed():
    result = classify_failure(
        {"name": "c", "passed": False, "validation_passed": True}
    )
    _assert_basic(result, "validation_gap")


def test_algorithm_reasoning_failure():
    result = classify_failure(
        {
            "name": "c",
            "passed": False,
            "validation_passed": False,
            "expected_changed_files": ["src/a.py"],
            "changed_files": ["src/a.py"],
            "total_changed_lines": 10,
        }
    )
    _assert_basic(result, "algorithm_reasoning_failure")


def test_unknown_when_no_signal():
    result = classify_failure({})
    _assert_basic(result, "unknown")


# --- benchmark failure kind display ----------------------------------------


def test_benchmark_failure_kind_security_tool_from_fork_exec_access_denied():
    result = classify_benchmark_failure_kind(
        {
            "name": "go_case",
            "success": False,
            "validation_output": (
                "fork/exec C:\\Users\\Admin\\AppData\\Local\\Temp\\"
                "go-build123\\b001\\exe\\main.exe: Access is denied."
            ),
        }
    )
    assert result["kind"] == "security_tool"
    assert result["display"] == "SECURITY TOOL"
    assert "Access is denied" in result["evidence"]


def test_benchmark_failure_kind_go_temp_executable_blocked_on_windows():
    result = classify_benchmark_failure_kind(
        {
            "name": "go_case",
            "success": False,
            "language": "go",
            "validation_output": (
                "go test: fork/exec C:\\Users\\Admin\\AppData\\Local\\Temp\\"
                "go-build456\\b001\\exe\\pkg.test.exe: Access is denied."
            ),
        }
    )
    assert result["kind"] == "security_tool"
    assert result["display"] == "SECURITY TOOL"
    assert "Go temp executable blocked on Windows" in result["cause"]


def test_benchmark_failure_kind_missing_compiler_maps_to_toolchain():
    result = classify_benchmark_failure_kind(
        {
            "name": "cpp_case",
            "success": False,
            "validation_output": "g++: command not found",
        }
    )
    assert result["kind"] == "toolchain"
    assert result["display"] == "TOOLCHAIN"
    assert "missing toolchain" in result["cause"]


def test_benchmark_failure_kind_assertion_failure_remains_code_unknown():
    result = classify_benchmark_failure_kind(
        {
            "name": "logic_case",
            "success": False,
            "validation_output": "AssertionError: expected 5, got 4",
        }
    )
    assert result["kind"] == "code_unknown"
    assert result["display"] == "CODE / UNKNOWN"
    assert result["cause"] == "no environment/toolchain signal detected"


# --- behaviour --------------------------------------------------------------


def test_classification_is_deterministic():
    case = {
        "name": "c",
        "passed": False,
        "expected_changed_files": ["src/a.py"],
        "changed_files": ["src/unrelated.py"],
        "total_changed_lines": 10,
    }
    first = classify_failure(case)
    second = classify_failure(case)
    assert first.to_dict() == second.to_dict()


def test_classify_does_not_mutate_input():
    case = {"name": "c", "passed": False, "changed_files": ["src/a.py"]}
    snapshot = dict(case)
    classify_failure(case)
    assert case == snapshot


def test_categories_set_is_complete():
    expected = {
        "retrieval_miss",
        "wrong_file",
        "patch_too_large",
        "patch_too_small",
        "validation_gap",
        "validation_command_failure",
        "model_fallback_instability",
        "forbidden_file_temptation",
        "no_patch_expected",
        "algorithm_reasoning_failure",
        "timeout_or_cost",
        "environment_issue",
        "unknown",
    }
    assert set(CATEGORIES) == expected


def test_single_markdown_report_contains_guardrail():
    result = classify_failure(
        {
            "name": "c",
            "passed": False,
            "expected_changed_files": ["src/a.py"],
            "changed_files": ["src/unrelated.py"],
            "total_changed_lines": 10,
        }
    )
    markdown = format_failure_taxonomy_markdown(result)
    assert "# Failure Taxonomy" in markdown
    assert "wrong_file" in markdown
    assert GUARDRAIL_NOTE in markdown


def test_aggregate_report_counts_categories():
    classifications = [
        classify_failure({"name": "a", "passed": False, "fallback_count": 1}),
        classify_failure({"name": "b", "passed": False, "fallback_count": 1}),
        classify_failure({}),
    ]
    markdown = format_failure_taxonomy_report(classifications)
    assert "# Failure Taxonomy Report" in markdown
    assert "model_fallback_instability" in markdown
    assert GUARDRAIL_NOTE in markdown


# --- read-only guard --------------------------------------------------------


def test_failure_taxonomy_ast_guard_read_only_scope():
    tree = ast.parse(
        Path("core/failure_taxonomy.py").read_text(encoding="utf-8")
    )
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
        "shutil",
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
        "execute",
        "executemany",
        "from_env",
        "generate_content",
        "mkdir",
        "open",
        "promote_lesson",
        "remove",
        "removedirs",
        "rmdir",
        "rmtree",
        "run_benchmark",
        "run_benchmarks",
        "run_deepseek_review",
        "run_gemini_request",
        "run_patch_plan_with_artifacts",
        "run_validation_command",
        "start_overnight_async",
        "system",
        "unlink",
        "write_bytes",
        "write_text",
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
