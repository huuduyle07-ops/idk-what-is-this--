"""Phase 13.10 - Memory Temperature Tie-breaker Dogfood Report tests.

The dogfood layer is *evidence-only*. Given a caller-supplied list of lesson
candidates, it shows what the (default-off) Memory Temperature tie-breaker
*would* do: original vs adjusted rank, rank delta, relevance score, thermal
band/score, whether a tie-break was applied, the reason, and how
frozen/audit-only/blocked lessons are handled. It must:

  * confirm default-off pass-through (live behavior unchanged);
  * never query lesson_store / DB, never wire into live retrieval or the
    CONTROL prompt, never enable the harness flag;
  * never hard-filter cold lessons or revive frozen/audit-only/blocked lessons;
  * never mutate the caller's candidates.
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


def _candidate(item_id: str, score: float, **overrides) -> dict:
    record = {
        "id": item_id,
        "title": item_id,
        "score": score,
        "status": "active",
        "source_type": "manual",
        "updated_at": _days_ago(1),
    }
    record.update(overrides)
    return record


def _hot(item_id: str, score: float) -> dict:
    return _candidate(
        item_id, score, source_type="lesson", trusted=True, updated_at=_days_ago(1)
    )


def _warm(item_id: str, score: float) -> dict:
    return _candidate(item_id, score, source_type="manual", updated_at=_days_ago(5))


def _cold(item_id: str, score: float) -> dict:
    return _candidate(item_id, score, source_type="manual", updated_at=_days_ago(80))


def _blocked(item_id: str, score: float) -> dict:
    return _candidate(item_id, score, status="blocked", updated_at=_days_ago(1))


def _audit_only(item_id: str, score: float) -> dict:
    return _candidate(
        item_id, score, source_type="lesson", status="audit-only", updated_at=_days_ago(1)
    )


def _row_for(report: dict, item_id: str) -> dict:
    return next(row for row in report["rows"] if row["item_id"] == item_id)


def _adjusted_order(report: dict) -> list[str]:
    rows = sorted(report["rows"], key=lambda r: r["adjusted_rank"])
    return [r["item_id"] for r in rows]


# ---------------------------------------------------------------------------
# 1 - report confirms default-off pass-through behavior
# ---------------------------------------------------------------------------
def test_report_confirms_default_off_passthrough_behavior():
    from core.memory_temperature_retrieval_dogfood import (
        build_memory_temperature_tiebreaker_dogfood,
    )

    candidates = [_cold("c1", 0.5), _hot("c2", 0.5), _warm("c3", 0.5)]

    report = build_memory_temperature_tiebreaker_dogfood(candidates, now=NOW)

    assert report["default_off_passthrough_unchanged"] is True
    assert report["default_off_order"] == ["c1", "c2", "c3"]
    assert report["live_retrieval_unchanged"] is True
    assert report["control_prompt_unchanged"] is True
    assert report["harness_flag_enabled"] is False
    # The harness flag is now a wired editable toggle, but still OFF by default.
    assert report["harness_flag_wired"] is True
    assert report["evidence_only"] is True
    assert report["candidate_count"] == 3


# ---------------------------------------------------------------------------
# 2 - report shows original and adjusted ranks
# ---------------------------------------------------------------------------
def test_report_shows_original_and_adjusted_ranks():
    from core.memory_temperature_retrieval_dogfood import (
        build_memory_temperature_tiebreaker_dogfood,
    )

    candidates = [_cold("c1", 0.5), _hot("c2", 0.5), _warm("c3", 0.5)]

    report = build_memory_temperature_tiebreaker_dogfood(candidates, now=NOW)

    c2 = _row_for(report, "c2")
    assert c2["original_rank"] == 2
    assert c2["adjusted_rank"] == 1
    c1 = _row_for(report, "c1")
    assert c1["original_rank"] == 1
    assert c1["adjusted_rank"] == 3


# ---------------------------------------------------------------------------
# 3 - report shows rank deltas
# ---------------------------------------------------------------------------
def test_report_shows_rank_deltas():
    from core.memory_temperature_retrieval_dogfood import (
        build_memory_temperature_tiebreaker_dogfood,
    )

    candidates = [_cold("c1", 0.5), _hot("c2", 0.5), _warm("c3", 0.5)]

    report = build_memory_temperature_tiebreaker_dogfood(candidates, now=NOW)

    # rank_delta = original_rank - adjusted_rank; positive == rose in priority.
    for row in report["rows"]:
        assert row["rank_delta"] == row["original_rank"] - row["adjusted_rank"]
    assert _row_for(report, "c2")["rank_delta"] == 1  # hot rose
    assert _row_for(report, "c1")["rank_delta"] == -2  # cold fell


# ---------------------------------------------------------------------------
# 4 - report shows temperature band and score
# ---------------------------------------------------------------------------
def test_report_shows_temperature_band_and_score():
    from core.memory_temperature_retrieval_dogfood import (
        build_memory_temperature_tiebreaker_dogfood,
    )

    candidates = [_cold("c1", 0.5), _hot("c2", 0.5), _warm("c3", 0.5)]

    report = build_memory_temperature_tiebreaker_dogfood(candidates, now=NOW)

    assert _row_for(report, "c2")["temperature_band"] == "hot"
    assert _row_for(report, "c1")["temperature_band"] == "cold"
    assert _row_for(report, "c3")["temperature_band"] == "warm"
    for row in report["rows"]:
        assert isinstance(row["temperature_score"], (int, float))
    assert _row_for(report, "c2")["temperature_score"] > 0.0
    # relevance score is preserved alongside the thermal score.
    assert _row_for(report, "c2")["score"] == 0.5


# ---------------------------------------------------------------------------
# 5 - report marks tie_break_applied correctly
# ---------------------------------------------------------------------------
def test_report_marks_tie_break_applied_correctly():
    from core.memory_temperature_retrieval_dogfood import (
        build_memory_temperature_tiebreaker_dogfood,
    )

    # Already hot-first within the near-equal group: hot does not move, but the
    # warm/cold pair swaps.
    candidates = [_hot("h", 0.5), _cold("c", 0.5), _warm("w", 0.5)]

    report = build_memory_temperature_tiebreaker_dogfood(candidates, now=NOW)

    assert _row_for(report, "h")["tie_break_applied"] is False
    assert _row_for(report, "w")["tie_break_applied"] is True
    assert _row_for(report, "c")["tie_break_applied"] is True


# ---------------------------------------------------------------------------
# 6 - near-equal candidates can be reordered in dogfood output
# ---------------------------------------------------------------------------
def test_near_equal_candidates_can_be_reordered_in_dogfood_output():
    from core.memory_temperature_retrieval_dogfood import (
        build_memory_temperature_tiebreaker_dogfood,
    )

    candidates = [_cold("c1", 0.5), _hot("c2", 0.5), _warm("c3", 0.5)]

    report = build_memory_temperature_tiebreaker_dogfood(candidates, now=NOW)

    assert _adjusted_order(report) == ["c2", "c3", "c1"]


# ---------------------------------------------------------------------------
# 7 - clearly different score candidates are not reordered
# ---------------------------------------------------------------------------
def test_clearly_different_score_candidates_are_not_reordered():
    from core.memory_temperature_retrieval_dogfood import (
        build_memory_temperature_tiebreaker_dogfood,
    )

    candidates = [_cold("hi", 0.90), _hot("lo", 0.50)]

    report = build_memory_temperature_tiebreaker_dogfood(candidates, now=NOW)

    assert _adjusted_order(report) == ["hi", "lo"]
    assert _row_for(report, "hi")["tie_break_applied"] is False
    assert _row_for(report, "lo")["tie_break_applied"] is False


# ---------------------------------------------------------------------------
# 8 - cold candidates are not removed
# ---------------------------------------------------------------------------
def test_cold_candidates_are_not_removed():
    from core.memory_temperature_retrieval_dogfood import (
        build_memory_temperature_tiebreaker_dogfood,
    )

    candidates = [_cold("top_cold", 0.90), _cold("g_cold", 0.50), _hot("g_hot", 0.50)]

    report = build_memory_temperature_tiebreaker_dogfood(candidates, now=NOW)

    assert report["candidate_count"] == 3
    assert len(report["rows"]) == 3
    ids = {row["item_id"] for row in report["rows"]}
    assert {"top_cold", "g_cold", "g_hot"} == ids
    # Cold lessons stay in the report and are never flagged as excluded/filtered.
    assert _row_for(report, "top_cold")["excluded_from_control"] is False
    assert _row_for(report, "g_cold")["excluded_from_control"] is False


# ---------------------------------------------------------------------------
# 9 - frozen / audit-only / blocked candidates are not revived
# ---------------------------------------------------------------------------
def test_frozen_audit_only_blocked_candidates_are_not_revived():
    from core.memory_temperature_retrieval_dogfood import (
        build_memory_temperature_tiebreaker_dogfood,
    )

    candidates = [
        _blocked("blk", 0.50),
        _audit_only("aud", 0.50),
        _hot("h", 0.50),
        _warm("w", 0.50),
    ]

    report = build_memory_temperature_tiebreaker_dogfood(candidates, now=NOW)
    order = _adjusted_order(report)

    # Frozen lessons sink below every eligible lesson; never raised in priority.
    assert order.index("h") < order.index("blk")
    assert order.index("w") < order.index("blk")
    assert order.index("h") < order.index("aud")
    assert order.index("w") < order.index("aud")

    blk = _row_for(report, "blk")
    aud = _row_for(report, "aud")
    assert blk["temperature_band"] == "frozen"
    assert aud["temperature_band"] == "frozen"
    assert blk["excluded_from_control"] is True
    assert aud["excluded_from_control"] is True
    # Not revived: their rank never improved.
    assert blk["adjusted_rank"] >= blk["original_rank"]
    assert aud["adjusted_rank"] >= aud["original_rank"]
    assert blk["rank_delta"] <= 0
    assert aud["rank_delta"] <= 0


# ---------------------------------------------------------------------------
# 10 - markdown contains guardrail text and explicit statements
# ---------------------------------------------------------------------------
def test_markdown_contains_guardrail_text_and_explicit_statements():
    from core.memory_temperature_retrieval_dogfood import (
        MEMORY_TEMPERATURE_TIEBREAKER_DOGFOOD_GUARDRAIL,
        build_memory_temperature_tiebreaker_dogfood,
        format_memory_temperature_tiebreaker_dogfood_markdown,
    )

    candidates = [_cold("c1", 0.5), _hot("c2", 0.5), _warm("c3", 0.5)]
    report = build_memory_temperature_tiebreaker_dogfood(candidates, now=NOW)

    md = format_memory_temperature_tiebreaker_dogfood_markdown(report)

    assert MEMORY_TEMPERATURE_TIEBREAKER_DOGFOOD_GUARDRAIL in md
    assert "live retrieval is unchanged" in md.lower()
    assert "control prompt is unchanged" in md.lower()
    assert "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED" in md
    assert "evidence-only" in md.lower()
    # The per-candidate table surfaces the key columns.
    for header in (
        "original_rank",
        "adjusted_rank",
        "rank_delta",
        "score",
        "temperature_band",
        "temperature_score",
        "tie_break_applied",
        "reason",
    ):
        assert header in md
    # Frozen handling is shown when present, and the cold lesson still appears.
    assert "c1" in md


# ---------------------------------------------------------------------------
# 11 - helper does not mutate input candidates
# ---------------------------------------------------------------------------
def test_helper_does_not_mutate_input_candidates():
    from core.memory_temperature_retrieval_dogfood import (
        build_memory_temperature_tiebreaker_dogfood,
        format_memory_temperature_tiebreaker_dogfood_markdown,
    )

    candidates = [
        _cold("c1", 0.5),
        _hot("c2", 0.5),
        _warm("c3", 0.5),
        _blocked("blk", 0.5),
    ]
    before = copy.deepcopy(candidates)

    report = build_memory_temperature_tiebreaker_dogfood(candidates, now=NOW)
    format_memory_temperature_tiebreaker_dogfood_markdown(report)

    assert candidates == before


# ---------------------------------------------------------------------------
# 12 - AST guard: no forbidden imports / sinks / live wiring
# ---------------------------------------------------------------------------
def test_ast_guard_dogfood_has_no_forbidden_imports_or_sinks():
    module_path = PROJECT_ROOT / "core" / "memory_temperature_retrieval_dogfood.py"
    source = module_path.read_text(encoding="utf-8")
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
        "lesson_store",
        "lesson_retrieval",
        "control_engine",
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
        "list_lessons",
        "list_active_lessons",
        "find_active_lessons",
        "save_lesson",
        "write_lesson",
        "promote_lesson",
        "block_lesson",
    }
    assert forbidden_calls.isdisjoint(call_names)

    # No direct env / harness-flag reads (the live flag is referenced only as
    # explanatory text, never enabled).
    for forbidden_text in ("os.environ", "getenv", "harness_controls"):
        assert forbidden_text not in source


def test_live_retrieval_and_control_prompt_do_not_import_dogfood():
    retrieval_source = (PROJECT_ROOT / "core" / "lesson_retrieval.py").read_text(
        encoding="utf-8"
    )
    control_source = (PROJECT_ROOT / "core" / "control_engine.py").read_text(
        encoding="utf-8"
    )

    assert "memory_temperature_retrieval_dogfood" not in retrieval_source
    assert "memory_temperature_retrieval_dogfood" not in control_source
