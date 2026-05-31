"""Phase 12.14a - Exponential Memory Temperature explain-only MVP."""
from __future__ import annotations

import ast
import copy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

NOW = datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc)


def _days_ago(days: int) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def test_recent_trusted_active_item_becomes_hot():
    from core.memory_temperature import classify_memory_temperature

    item = classify_memory_temperature(
        {
            "item_id": "recent",
            "status": "active",
            "source_type": "lesson",
            "trusted": True,
            "updated_at": _days_ago(1),
        },
        now=NOW,
    )

    assert item.band == "hot"
    assert item.temperature >= 0.75
    assert item.should_surface is True
    assert any("trusted" in reason.lower() for reason in item.reasons)


def test_old_valid_item_cools_to_cold():
    from core.memory_temperature import classify_memory_temperature

    item = classify_memory_temperature(
        {
            "item_id": "old",
            "status": "active",
            "source_type": "manual",
            "updated_at": _days_ago(45),
        },
        now=NOW,
    )

    assert item.band == "cold"
    assert 0.10 <= item.temperature < 0.40
    assert item.should_surface is False
    assert any("cool" in reason.lower() or "age" in reason.lower() for reason in item.reasons)


def test_human_approved_item_reheats():
    from core.memory_temperature import classify_memory_temperature

    plain = classify_memory_temperature(
        {"item_id": "plain", "updated_at": _days_ago(30)},
        now=NOW,
    )
    approved = classify_memory_temperature(
        {
            "item_id": "approved",
            "updated_at": _days_ago(30),
            "human_approved": True,
        },
        now=NOW,
    )

    assert approved.reheating_boost > plain.reheating_boost
    assert approved.temperature > plain.temperature
    assert any("human" in reason.lower() for reason in approved.reasons)


def test_repeated_use_item_reheats():
    from core.memory_temperature import classify_memory_temperature

    plain = classify_memory_temperature(
        {"item_id": "plain", "updated_at": _days_ago(30)},
        now=NOW,
    )
    reused = classify_memory_temperature(
        {"item_id": "reused", "updated_at": _days_ago(30), "use_count": 4},
        now=NOW,
    )

    assert reused.reheating_boost > plain.reheating_boost
    assert reused.temperature > plain.temperature
    assert any("use" in reason.lower() for reason in reused.reasons)


def test_blocked_item_freezes_even_if_recent():
    from core.memory_temperature import classify_memory_temperature

    item = classify_memory_temperature(
        {
            "item_id": "blocked",
            "status": "blocked",
            "human_approved": True,
            "use_count": 99,
            "updated_at": _days_ago(0),
        },
        now=NOW,
    )

    assert item.band == "frozen"
    assert item.temperature == 0.0
    assert item.should_surface is False
    assert any("blocked" in reason.lower() for reason in item.reasons)


def test_failed_validation_item_freezes():
    from core.memory_temperature import classify_memory_temperature

    item = classify_memory_temperature(
        {
            "item_id": "failed",
            "validation_ok": False,
            "updated_at": _days_ago(0),
        },
        now=NOW,
    )

    assert item.band == "frozen"
    assert item.temperature == 0.0
    assert any("validation" in reason.lower() for reason in item.reasons)


def test_missing_timestamp_does_not_crash_and_emits_warning():
    from core.memory_temperature import classify_memory_temperature

    item = classify_memory_temperature({"item_id": "missing-time"}, now=NOW)

    assert item.item_id == "missing-time"
    assert item.age_days == 0.0
    assert item.warnings
    assert any("timestamp" in warning.lower() for warning in item.warnings)


def test_input_dict_is_not_mutated():
    from core.memory_temperature import classify_memory_temperature

    record = {
        "item_id": "immutable-input",
        "updated_at": _days_ago(3),
        "metadata": {"nested": ["x"]},
    }
    before = copy.deepcopy(record)

    classify_memory_temperature(record, now=NOW)

    assert record == before


def test_batch_output_sorts_hot_warm_cold_before_frozen():
    from core.memory_temperature import classify_memory_batch

    items = classify_memory_batch(
        [
            {"item_id": "frozen", "status": "blocked", "updated_at": _days_ago(0)},
            {"item_id": "cold", "updated_at": _days_ago(45)},
            {"item_id": "hot", "trusted": True, "updated_at": _days_ago(1)},
            {"item_id": "warm", "human_approved": True, "updated_at": _days_ago(25)},
        ],
        now=NOW,
    )

    assert [item.band for item in items] == ["hot", "warm", "cold", "frozen"]
    assert [item.item_id for item in classify_memory_batch([], now=NOW)] == []
    assert len(classify_memory_batch(items, now=NOW, limit=2)) == 2


def test_markdown_groups_hot_warm_cold_frozen():
    from core.memory_temperature import (
        classify_memory_batch,
        format_memory_temperature_markdown,
    )

    items = classify_memory_batch(
        [
            {"item_id": "hot", "trusted": True, "updated_at": _days_ago(1)},
            {"item_id": "warm", "human_approved": True, "updated_at": _days_ago(25)},
            {"item_id": "cold", "updated_at": _days_ago(45)},
            {"item_id": "frozen", "status": "blocked", "updated_at": _days_ago(0)},
        ],
        now=NOW,
    )
    md = format_memory_temperature_markdown(items)

    for heading in ("## Hot", "## Warm", "## Cold", "## Frozen"):
        assert heading in md
    assert md.index("## Hot") < md.index("## Warm") < md.index("## Cold") < md.index("## Frozen")


def test_guardrail_appears():
    from core.memory_temperature import (
        MEMORY_TEMPERATURE_GUARDRAIL,
        classify_memory_batch,
        format_memory_temperature_markdown,
    )

    md = format_memory_temperature_markdown(
        classify_memory_batch([{"item_id": "hot", "trusted": True, "updated_at": _days_ago(1)}], now=NOW)
    )

    assert MEMORY_TEMPERATURE_GUARDRAIL in md
    for token in (
        "lesson retrieval",
        "CONTROL prompts",
        "ranking",
        "patch generation",
        "validation",
        "benchmark scoring",
        "storage behavior",
    ):
        assert token in md


def test_forbidden_imports_absent():
    import core.memory_temperature as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    forbidden_import_areas = (
        "patching",
        "model",
        "api",
        "database",
        "db",
        "benchmark_runner",
        "run_benchmarks",
    )
    for imported in imported_modules:
        parts = imported.split(".")
        for forbidden in forbidden_import_areas:
            assert not any(part == forbidden for part in parts), imported
