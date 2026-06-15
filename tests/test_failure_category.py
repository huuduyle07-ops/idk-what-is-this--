"""Tests for Phase 14.6 failure_category mapper and benchmark wiring.

Covers:
1. Mapper rules (10) — each priority-ordered classification path.
2. Report integration (7) — with_failure_category_fields behavior and view compat.
3. Guardrails (7) — import/side-effect guard (AST-based).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.failure_category import (
    FAILURE_CATEGORIES,
    FAILURE_CATEGORY_GUARDRAIL_NOTE,
    derive_failure_category,
)
from core.benchmarks_view import failure_category_display
from benchmarks.run_benchmarks import with_failure_category_fields

# ── helpers ───────────────────────────────────────────────────────────────────

def _case(**kwargs) -> dict:
    base = {"success": False}
    base.update(kwargs)
    return base


# ── Test group 1: mapper rules (10) ──────────────────────────────────────────

def test_failure_kind_security_tool_maps_to_security():
    result = derive_failure_category(_case(failure_kind="security_tool"))
    assert result["failure_category"] == "security_tool_or_permission"
    assert result["failure_category_confidence"] == "high"
    assert result["failure_category_rule"] == "failure_kind_security_tool"


def test_access_denied_in_validation_output_maps_to_security():
    result = derive_failure_category(_case(
        validation_output="fork/exec go.exe: Access is denied."
    ))
    assert result["failure_category"] == "security_tool_or_permission"
    assert result["failure_category_confidence"] == "high"
    assert result["failure_category_rule"] == "access_denied_or_antivirus_signal"


def test_antivirus_in_validation_output_maps_to_security():
    result = derive_failure_category(_case(
        validation_output="antivirus blocked the execution"
    ))
    assert result["failure_category"] == "security_tool_or_permission"
    assert result["failure_category_confidence"] == "high"


def test_nested_agent_validation_tail_access_denied_maps_to_security():
    result = derive_failure_category(_case(
        validation_summary={"agent_validation_tail": "Access is denied."}
    ))
    assert result["failure_category"] == "security_tool_or_permission"
    assert result["failure_category_confidence"] == "high"


def test_failure_kind_toolchain_maps_to_toolchain_environment():
    result = derive_failure_category(_case(failure_kind="toolchain"))
    assert result["failure_category"] == "toolchain_environment"
    assert result["failure_category_confidence"] == "medium"
    assert result["failure_category_rule"] == "failure_kind_toolchain_or_environment"


def test_failure_kind_environment_maps_to_toolchain_environment():
    result = derive_failure_category(_case(failure_kind="environment"))
    assert result["failure_category"] == "toolchain_environment"
    assert result["failure_category_confidence"] == "medium"


def test_expects_patch_false_maps_to_false_positive():
    result = derive_failure_category(_case(expects_patch=False))
    assert result["failure_category"] == "false_positive_no_patch"
    assert result["failure_category_confidence"] == "high"
    assert result["failure_category_rule"] == "no_patch_expected_flag"


def test_touched_forbidden_files_maps_to_scope_violation():
    result = derive_failure_category(_case(
        touched_forbidden_files=["tests/fixture.py"]
    ))
    assert result["failure_category"] == "forbidden_file_or_scope_violation"
    assert result["failure_category_confidence"] == "high"
    assert result["failure_category_rule"] == "touched_forbidden_files"


def test_disjoint_changed_files_maps_to_wrong_file():
    result = derive_failure_category(_case(
        changed_files=["decoy.go"],
        expected_changed_files=["target.go"],
    ))
    assert result["failure_category"] == "wrong_file_or_decoy"
    assert result["failure_category_confidence"] == "high"
    assert result["failure_category_rule"] == "changed_files_disjoint_from_expected"


def test_bench_category_async_error_maps_to_async_lifecycle():
    result = derive_failure_category(_case(category="async_error"))
    assert result["failure_category"] == "async_or_lifecycle_bug"
    assert result["failure_category_confidence"] == "high"
    assert result["failure_category_rule"] == "benchmark_category_mapping"


# Extra mapper coverage — additional bench_cat mappings and fallthrough

def test_bench_category_side_effect_maps_correctly():
    result = derive_failure_category(_case(category="side_effect"))
    assert result["failure_category"] == "state_mutation_or_side_effect"


def test_bench_category_missing_import_maps_correctly():
    result = derive_failure_category(_case(category="missing_import"))
    assert result["failure_category"] == "missing_import_or_dependency"


def test_bench_category_boundary_logic_maps_to_data_validation():
    result = derive_failure_category(_case(category="boundary_logic"))
    assert result["failure_category"] == "data_validation_or_boundary"


def test_no_signals_falls_through_to_unknown():
    result = derive_failure_category({"success": False})
    assert result["failure_category"] == "unknown"
    assert result["failure_category_confidence"] == "none"
    assert result["failure_category_rule"] == "no_rule_matched"


def test_overlapping_changed_files_does_not_map_to_wrong_file():
    result = derive_failure_category(_case(
        changed_files=["target.go"],
        expected_changed_files=["target.go"],
    ))
    assert result["failure_category"] != "wrong_file_or_decoy"


# ── Test group 2: report integration (7) ─────────────────────────────────────

def test_with_failure_category_fields_passes_through_success():
    enriched = with_failure_category_fields({"success": True, "name": "pass_case"})
    assert "failure_category" not in enriched


def test_with_failure_category_fields_adds_four_fields():
    enriched = with_failure_category_fields({"success": False, "name": "fail_case"})
    assert "failure_category" in enriched
    assert "failure_category_confidence" in enriched
    assert "failure_category_rule" in enriched
    assert "failure_category_reason" in enriched


def test_with_failure_category_fields_does_not_mutate_input():
    original = {"success": False, "name": "fail_case"}
    original_keys = set(original.keys())
    with_failure_category_fields(original)
    assert set(original.keys()) == original_keys


def test_failure_category_always_in_valid_set():
    for case in [
        {},
        {"failure_kind": "security_tool"},
        {"category": "async_error"},
        {"touched_forbidden_files": ["x"]},
        {"failure_kind": "environment"},
    ]:
        result = derive_failure_category({"success": False, **case})
        assert result["failure_category"] in FAILURE_CATEGORIES


def test_failure_categories_constant_is_correct_size():
    assert isinstance(FAILURE_CATEGORIES, tuple)
    assert len(FAILURE_CATEGORIES) == 13
    assert FAILURE_CATEGORIES[-1] == "unknown"


def test_failure_categories_exact_members():
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
    assert FAILURE_CATEGORIES == expected


def test_old_report_without_failure_category_tolerated_by_view():
    result = {"success": False, "failure_kind": "code_unknown"}
    display = failure_category_display(result)
    assert isinstance(display, str)
    # empty string is valid — absence of field should not raise


def test_failure_category_display_returns_formatted_string():
    result = {"success": False, "failure_category": "security_tool_or_permission"}
    display = failure_category_display(result)
    assert display == "SECURITY TOOL OR PERMISSION"


# ── Test group 3: guardrails (7, AST-based) ───────────────────────────────────

_FC_PATH = Path(__file__).parent.parent / "core" / "failure_category.py"
_FC_SOURCE = _FC_PATH.read_text(encoding="utf-8")


def test_no_flask_in_failure_category_module():
    tree = ast.parse(_FC_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "flask" not in alias.name.lower(), alias.name
        elif isinstance(node, ast.ImportFrom):
            assert "flask" not in (node.module or "").lower(), node.module


def test_no_subprocess_in_failure_category_module():
    tree = ast.parse(_FC_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "subprocess", "subprocess must not be imported"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "") != "subprocess", "subprocess must not be imported"


def test_no_model_client_in_failure_category_module():
    for bad in ("anthropic", "openai", "litellm", "ollama", "bedrock"):
        assert bad not in _FC_SOURCE, f"Found {bad!r} in failure_category module"


def test_no_db_client_in_failure_category_module():
    for bad in ("sqlalchemy", "psycopg", "pymongo", "motor", "sqlite3"):
        assert bad not in _FC_SOURCE, f"Found {bad!r} in failure_category module"


def test_no_lesson_promotion_in_failure_category_module():
    for bad in ("promote_lesson", "save_active_lesson", "lesson_store"):
        assert bad not in _FC_SOURCE, f"Found {bad!r} in failure_category module"


def test_no_patch_apply_in_failure_category_module():
    for bad in ("apply_patch", "patch_apply", "run_patch", "exec_patch"):
        assert bad not in _FC_SOURCE, f"Found {bad!r} in failure_category module"


def test_failure_category_module_only_imports_stdlib():
    stdlib_ok = {"__future__", "typing"}
    tree = ast.parse(_FC_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in stdlib_ok, (
                f"Unexpected import in failure_category: {module!r}"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in stdlib_ok, (
                    f"Unexpected import in failure_category: {alias.name!r}"
                )
