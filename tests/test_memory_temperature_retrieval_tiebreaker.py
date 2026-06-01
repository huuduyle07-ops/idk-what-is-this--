"""Phase 13.9 - Memory Temperature Tie-breaker Retrieval (default off) tests.

The tie-breaker is the first *behavior* hook for Memory Temperature, but it is
disabled by default and very conservative when enabled:

  * default-off => candidates are returned in their exact original order and
    inputs are never mutated;
  * enabled + tiebreak_only => Memory Temperature may only reorder lessons
    *within* near-equal relevance groups; it must never let a weak hot/cold
    signal override a clearly higher relevance score;
  * frozen / audit-only / blocked lessons are never revived or surfaced;
  * cold lessons are never hard-filtered, only de-prioritized inside a group.

It performs no model/API calls, no DB writes, no patching, no validation /
benchmark execution, no subprocess / Docker lifecycle, and no lesson_store
writes. As of Phase 13.11a the helper is wired into the lesson-retrieval
ordering boundary behind a default-off flag (see
``test_memory_temperature_retrieval_wiring``); ``control_engine`` does not
import it.
"""
from __future__ import annotations

import ast
import copy
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

METADATA_KEY = "memory_temperature_tiebreak"


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
        item_id,
        score,
        source_type="lesson",
        trusted=True,
        updated_at=_days_ago(1),
    )


def _warm(item_id: str, score: float) -> dict:
    return _candidate(item_id, score, source_type="manual", updated_at=_days_ago(5))


def _cold(item_id: str, score: float) -> dict:
    return _candidate(item_id, score, source_type="manual", updated_at=_days_ago(80))


def _blocked(item_id: str, score: float) -> dict:
    return _candidate(item_id, score, status="blocked", updated_at=_days_ago(1))


def _ids(candidates) -> list[str]:
    return [c["id"] for c in candidates]


# ---------------------------------------------------------------------------
# 1 & 2 - default disabled mode
# ---------------------------------------------------------------------------
def test_default_disabled_mode_returns_candidates_in_exact_original_order():
    from core.memory_temperature_retrieval import apply_memory_temperature_tiebreaker

    # All near-equal score; would reorder to hot, warm, cold if enabled.
    candidates = [_cold("c1", 0.5), _hot("c2", 0.5), _warm("c3", 0.5)]

    result = apply_memory_temperature_tiebreaker(candidates, now=NOW)

    assert _ids(result) == ["c1", "c2", "c3"]
    assert all(METADATA_KEY not in c for c in result)


def test_default_disabled_mode_does_not_mutate_input_candidates():
    from core.memory_temperature_retrieval import apply_memory_temperature_tiebreaker

    candidates = [_cold("c1", 0.5), _hot("c2", 0.5), _warm("c3", 0.5)]
    before = copy.deepcopy(candidates)

    apply_memory_temperature_tiebreaker(candidates, now=NOW)

    assert candidates == before


# ---------------------------------------------------------------------------
# 3 - enabled tie-breaker reorders near-equal candidates
# ---------------------------------------------------------------------------
def test_enabled_tiebreaker_reorders_near_equal_candidates():
    from core.memory_temperature_retrieval import apply_memory_temperature_tiebreaker

    candidates = [_cold("c1", 0.5), _hot("c2", 0.5), _warm("c3", 0.5)]
    before = copy.deepcopy(candidates)

    result = apply_memory_temperature_tiebreaker(candidates, enabled=True, now=NOW)

    assert _ids(result) == ["c2", "c3", "c1"]
    # original retrieval score preserved on every candidate
    assert all(c["score"] == 0.5 for c in result)
    # input candidates are not mutated (annotation happens on copies)
    assert candidates == before


# ---------------------------------------------------------------------------
# 4 - clearly different scores are never reordered
# ---------------------------------------------------------------------------
def test_enabled_tiebreaker_cannot_reorder_clearly_different_scores():
    from core.memory_temperature_retrieval import apply_memory_temperature_tiebreaker

    # Cold but clearly higher relevance vs hot but clearly lower relevance.
    candidates = [_cold("hi", 0.90), _hot("lo", 0.50)]

    result = apply_memory_temperature_tiebreaker(candidates, enabled=True, now=NOW)

    assert _ids(result) == ["hi", "lo"]
    meta_hi = result[0][METADATA_KEY]
    meta_lo = result[1][METADATA_KEY]
    assert meta_hi["tie_break_applied"] is False
    assert meta_lo["tie_break_applied"] is False


# ---------------------------------------------------------------------------
# 5 - hot/warm lesson can rise only inside a near-equal group
# ---------------------------------------------------------------------------
def test_hot_lesson_rises_only_inside_near_equal_group():
    from core.memory_temperature_retrieval import apply_memory_temperature_tiebreaker

    candidates = [_cold("top_cold", 0.90), _cold("g_cold", 0.50), _hot("g_hot", 0.50)]

    result = apply_memory_temperature_tiebreaker(candidates, enabled=True, now=NOW)
    order = _ids(result)

    # Rose above its near-equal cold peer ...
    assert order.index("g_hot") < order.index("g_cold")
    # ... but never above the clearly-higher-scored cold candidate.
    assert order.index("top_cold") < order.index("g_hot")
    assert order[0] == "top_cold"


# ---------------------------------------------------------------------------
# 6 & 7 - cold lesson can fall only inside group, and is never removed
# ---------------------------------------------------------------------------
def test_cold_lesson_falls_only_inside_group_and_is_not_removed():
    from core.memory_temperature_retrieval import apply_memory_temperature_tiebreaker

    candidates = [_cold("top_cold", 0.90), _cold("g_cold", 0.50), _hot("g_hot", 0.50)]

    result = apply_memory_temperature_tiebreaker(candidates, enabled=True, now=NOW)
    order = _ids(result)

    # The near-equal cold fell behind the hot peer in its group ...
    assert order.index("g_cold") > order.index("g_hot")
    # ... but the clearly-higher-scored cold did not fall.
    assert order[0] == "top_cold"
    # No cold candidate was hard-filtered out.
    assert len(result) == 3
    assert "g_cold" in order
    assert "top_cold" in order


# ---------------------------------------------------------------------------
# 8 - frozen / audit-only / blocked lessons are never revived or surfaced
# ---------------------------------------------------------------------------
def test_blocked_lesson_is_not_revived_by_temperature():
    from core.memory_temperature_retrieval import apply_memory_temperature_tiebreaker

    candidates = [_blocked("blk", 0.50), _hot("h", 0.50), _warm("w", 0.50)]

    result = apply_memory_temperature_tiebreaker(candidates, enabled=True, now=NOW)
    order = _ids(result)

    # Blocked lesson sinks below every eligible lesson; never surfaced higher.
    assert order[-1] == "blk"
    assert order.index("blk") > order.index("h")
    assert order.index("blk") > order.index("w")
    # Present (not hard-filtered) but its rank only worsened.
    blk = next(c for c in result if c["id"] == "blk")
    assert blk[METADATA_KEY]["temperature_band"] == "frozen"
    assert blk[METADATA_KEY]["adjusted_rank"] >= blk[METADATA_KEY]["original_rank"]


# ---------------------------------------------------------------------------
# 9 - metadata records the adjustment
# ---------------------------------------------------------------------------
def test_metadata_records_rank_band_score_and_tie_break_flag():
    from core.memory_temperature_retrieval import apply_memory_temperature_tiebreaker

    candidates = [_cold("c1", 0.5), _hot("c2", 0.5), _warm("c3", 0.5)]

    result = apply_memory_temperature_tiebreaker(candidates, enabled=True, now=NOW)
    hot = next(c for c in result if c["id"] == "c2")
    meta = hot[METADATA_KEY]

    assert meta["original_rank"] == 2
    assert meta["adjusted_rank"] == 1
    assert meta["temperature_band"] == "hot"
    assert meta["temperature_score"] > 0.0
    assert meta["tie_break_applied"] is True
    assert isinstance(meta["reason"], str) and meta["reason"]


# ---------------------------------------------------------------------------
# grouping helper
# ---------------------------------------------------------------------------
def test_group_near_equal_candidates_splits_clearly_different_scores():
    from core.memory_temperature_retrieval import group_near_equal_candidates

    candidates = [
        _candidate("a", 0.90),
        _candidate("b", 0.895),
        _candidate("c", 0.50),
        _candidate("d", 0.49),
    ]

    groups = group_near_equal_candidates(candidates, epsilon=0.02)

    assert [_ids(g) for g in groups] == [["a", "b"], ["c", "d"]]


# ---------------------------------------------------------------------------
# 10 - tie-breaker is wired only at the retrieval boundary, never in the prompt
# ---------------------------------------------------------------------------
def test_tiebreaker_wired_at_retrieval_boundary_only():
    # Phase 13.11a wires the tie-breaker into the lesson_retrieval ordering
    # boundary behind a default-off flag. The CONTROL prompt builder itself must
    # stay prompt-only — it consumes the boundary's output and never imports or
    # calls the tie-breaker directly.
    retrieval_source = (PROJECT_ROOT / "core" / "lesson_retrieval.py").read_text(
        encoding="utf-8"
    )
    control_source = (PROJECT_ROOT / "core" / "control_engine.py").read_text(
        encoding="utf-8"
    )

    # lesson_retrieval is now wired (default-off) ...
    assert "apply_memory_temperature_tiebreaker" in retrieval_source
    # ... but control_engine is not.
    assert "memory_temperature_retrieval" not in control_source
    assert "apply_memory_temperature_tiebreaker" not in control_source


# ---------------------------------------------------------------------------
# 11 - harness flag default remains false
# ---------------------------------------------------------------------------
def test_harness_flag_default_remains_false():
    from core.harness_controls import current_effective, get_control
    from core.memory_temperature_retrieval import apply_memory_temperature_tiebreaker

    sig = inspect.signature(apply_memory_temperature_tiebreaker)
    assert sig.parameters["enabled"].default is False
    assert sig.parameters["tiebreak_only"].default is True

    control = get_control("MEMORY_TEMPERATURE_RETRIEVAL_ENABLED")
    assert control is not None
    assert control.wired is False
    assert bool(control.config_default) is False
    assert current_effective(control) not in {"true", "on"}


# ---------------------------------------------------------------------------
# 12 - AST guard: no forbidden side effects / sinks
# ---------------------------------------------------------------------------
def test_ast_guard_tiebreaker_has_no_forbidden_side_effects_or_sinks():
    source = (PROJECT_ROOT / "core" / "memory_temperature_retrieval.py").read_text(
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
        "list_lessons",
        "save_lesson",
        "write_lesson",
        "promote_lesson",
        "block_lesson",
    }
    assert forbidden_calls.isdisjoint(call_names)

    # The module reads no environment / harness flags directly; the enable and
    # tie-break flags are passed in as parameters. (subprocess/docker are
    # covered by the import-area check above and may appear in prose docstrings.)
    for forbidden_text in (
        "os.environ",
        "getenv",
        "harness_controls",
        "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED",
    ):
        assert forbidden_text not in source
