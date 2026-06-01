"""Phase 13.7 - Memory Temperature Shadow Retrieval tests.

Shadow retrieval is report/debug-only: it computes a temperature-adjusted
ordering over already-loaded lessons without changing live lesson retrieval,
CONTROL prompt injection, ranking, storage, patching, validation, or benchmark
behavior.
"""
from __future__ import annotations

import ast
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _days_ago(days: int) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def _lesson(
    lesson_id: str,
    *,
    title: str | None = None,
    status: str = "active",
    source_type: str = "manual",
    trusted: bool = False,
    updated_days_ago: int = 1,
    **overrides,
) -> dict:
    record = {
        "id": lesson_id,
        "title": title or lesson_id,
        "status": status,
        "source_type": source_type,
        "trusted": trusted,
        "updated_at": _days_ago(updated_days_ago),
        "active_knowledge_allowed": True,
    }
    record.update(overrides)
    return record


def _shadow_sample() -> list[dict]:
    return [
        _lesson("cold-first", title="Cold first", updated_days_ago=60),
        _lesson(
            "hot-second",
            title="Hot second",
            source_type="lesson",
            trusted=True,
            updated_days_ago=1,
        ),
        _lesson(
            "warm-third",
            title="Warm third",
            updated_days_ago=20,
            human_approved=True,
        ),
    ]


def test_original_lesson_order_is_preserved_in_report():
    from core.memory_temperature_shadow import build_shadow_retrieval_report

    lessons = _shadow_sample()
    before = copy.deepcopy(lessons)

    report = build_shadow_retrieval_report(lessons, now=NOW)

    assert report["original_order"] == ["cold-first", "hot-second", "warm-third"]
    assert [item["item_id"] for item in report["items"]] == report["original_order"]
    assert [item["original_rank"] for item in report["items"]] == [1, 2, 3]
    assert lessons == before


def test_shadow_order_is_computed_separately_from_original_order():
    from core.memory_temperature_shadow import (
        apply_shadow_temperature_order,
        build_shadow_retrieval_report,
    )

    lessons = _shadow_sample()

    report = build_shadow_retrieval_report(lessons, now=NOW)
    ordered = apply_shadow_temperature_order(lessons, now=NOW)

    assert report["original_order"] == ["cold-first", "hot-second", "warm-third"]
    assert report["shadow_order"] == ["hot-second", "warm-third", "cold-first"]
    assert report["shadow_order"] != report["original_order"]
    assert [item["item_id"] for item in ordered] == report["shadow_order"]


def test_hot_lesson_can_move_up_in_shadow_order():
    from core.memory_temperature_shadow import build_shadow_retrieval_report

    report = build_shadow_retrieval_report(_shadow_sample(), now=NOW)
    hot = next(item for item in report["items"] if item["item_id"] == "hot-second")

    assert hot["temperature_band"] == "hot"
    assert hot["original_rank"] == 2
    assert hot["shadow_rank"] == 1
    assert hot["rank_delta"] == 1


def test_cold_lesson_can_move_down_but_is_not_removed_from_shadow_report():
    from core.memory_temperature_shadow import build_shadow_retrieval_report

    report = build_shadow_retrieval_report(_shadow_sample(), now=NOW)
    cold = next(item for item in report["items"] if item["item_id"] == "cold-first")

    assert cold["temperature_band"] == "cold"
    assert cold["original_rank"] == 1
    assert cold["shadow_rank"] == 3
    assert cold["rank_delta"] == -2
    assert "cold-first" in report["shadow_order"]
    assert "cold-first" in [item["item_id"] for item in report["items"]]


def test_frozen_audit_only_lesson_is_marked_excluded_and_blocked_in_report():
    from core.memory_temperature_shadow import build_shadow_retrieval_report

    lessons = [
        _lesson("hot", source_type="lesson", trusted=True, updated_days_ago=1),
        _lesson("audit", status="audit-only", updated_days_ago=0),
    ]

    report = build_shadow_retrieval_report(lessons, now=NOW)
    audit = next(item for item in report["items"] if item["item_id"] == "audit")

    assert audit["temperature_band"] == "frozen"
    assert audit["excluded"] is True
    assert audit["blocked"] is True
    assert audit["shadow_rank"] is None
    assert audit["rank_delta"] is None
    assert "audit" in report["excluded_order"]
    assert "audit" not in report["shadow_order"]
    assert "audit-only" in audit["reason"]


def test_markdown_report_includes_shadow_retrieval_rank_fields_and_reason():
    from core.memory_temperature_shadow import (
        build_shadow_retrieval_report,
        format_shadow_retrieval_markdown,
    )

    report = build_shadow_retrieval_report(_shadow_sample(), now=NOW)
    md = format_shadow_retrieval_markdown(report)

    assert "Memory Temperature Shadow Retrieval" in md
    for header in (
        "original_rank",
        "shadow_rank",
        "rank_delta",
        "temperature_band",
        "reason",
    ):
        assert header in md
    assert "hot-second" in md
    assert "trusted/useful source base temperature" in md


def test_empty_lesson_list_produces_safe_empty_report_and_markdown():
    from core.memory_temperature_shadow import (
        build_shadow_retrieval_report,
        format_shadow_retrieval_markdown,
    )

    report = build_shadow_retrieval_report([], now=NOW)
    md = format_shadow_retrieval_markdown(report)

    assert report["original_order"] == []
    assert report["shadow_order"] == []
    assert report["items"] == []
    assert report["count"] == 0
    assert "_(no lessons)_" in md


def test_shadow_helper_has_no_lesson_store_import_or_query():
    source = (PROJECT_ROOT / "core" / "memory_temperature_shadow.py").read_text(
        encoding="utf-8"
    )
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

    forbidden_imports = {
        "core.lesson_store",
        "lesson_store",
        "core.lesson_retrieval",
        "lesson_retrieval",
    }
    assert forbidden_imports.isdisjoint(imported_modules)

    forbidden_calls = {
        "list_lessons",
        "list_active_lessons",
        "find_active_lessons",
        "format_lessons_for_prompt",
    }
    assert forbidden_calls.isdisjoint(call_names)


def test_control_prompt_and_live_retrieval_do_not_import_shadow_helper():
    control_source = (PROJECT_ROOT / "core" / "control_engine.py").read_text(
        encoding="utf-8"
    )
    retrieval_source = (PROJECT_ROOT / "core" / "lesson_retrieval.py").read_text(
        encoding="utf-8"
    )

    assert "memory_temperature_shadow" not in control_source
    assert "Memory Temperature Shadow Retrieval" not in control_source
    assert "memory_temperature_shadow" not in retrieval_source
    assert "classify_memory_temperature" not in retrieval_source


def test_ast_guard_shadow_helper_has_no_forbidden_side_effects_or_sink_calls():
    source = (PROJECT_ROOT / "core" / "memory_temperature_shadow.py").read_text(
        encoding="utf-8"
    )
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
        "control_engine",
        "lesson_retrieval",
        "lesson_store",
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
