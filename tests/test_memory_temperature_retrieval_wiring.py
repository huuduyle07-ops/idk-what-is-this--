"""Phase 13.11a - Wire the Memory Temperature tie-breaker behind a disabled flag.

The Phase 13.9 tie-breaker is wired into the final lesson-candidate ordering
boundary (`core.lesson_retrieval.find_active_lessons`), but it is *disabled by
default* so live behavior is exactly unchanged:

  * default flags (``MEMORY_TEMPERATURE_RETRIEVAL_ENABLED=false``,
    ``MEMORY_TEMPERATURE_TIEBREAK_ONLY=true``) → exact pass-through: same order,
    no tie-break metadata, no input mutation, CONTROL prompt unchanged;
  * enabled → only near-equal candidates may be reordered, original scores are
    preserved, tie-break metadata is attached for debugging, cold lessons are
    never hard-filtered, and frozen / audit-only / blocked lessons are never
    surfaced.

The wiring reads its flags from config (env-backed) only; it performs no
model/API calls, no DB writes, no patching, no validation/benchmark execution,
and no subprocess/Docker lifecycle, and it never rewrites the CONTROL prompt.
"""
from __future__ import annotations

import ast
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config
from core import control_engine
from core import lesson_retrieval as lr
from core.memory_temperature_retrieval import TIEBREAK_METADATA_KEY

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# A single fixed reference time so two records built with the same `_ts(...)`
# get byte-identical timestamps (otherwise per-call `datetime.now()` drift would
# make one record microseconds "newer" and silently break recency ties).
_NOW = datetime.now(timezone.utc)


def _ts(days_ago: int) -> str:
    return (_NOW - timedelta(days=days_ago)).isoformat()


def _lesson(lesson_id: str, **overrides) -> dict:
    record = {
        "id": lesson_id,
        "title": lesson_id,
        "status": "active",
        "active_knowledge_allowed": True,
        "summary": "general note",
        "source_type": "manual",
        "updated_at": _ts(1),
        "created_at": _ts(1),
    }
    record.update(overrides)
    return record


def _hot(lesson_id: str, **overrides) -> dict:
    base = {"source_type": "lesson", "trusted": True, "human_approved": True}
    base.update(overrides)
    return _lesson(lesson_id, **base)


def _enable(monkeypatch, *, enabled: bool = True, tiebreak_only: bool = True) -> None:
    monkeypatch.setattr(config, "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED", enabled, raising=False)
    monkeypatch.setattr(config, "MEMORY_TEMPERATURE_TIEBREAK_ONLY", tiebreak_only, raising=False)


def _feed(monkeypatch, lessons: list[dict]) -> None:
    monkeypatch.setattr(lr, "list_active_lessons", lambda repo_path=None: lessons)


# ---------------------------------------------------------------------------
# 1 - default flag false preserves exact lesson order
# ---------------------------------------------------------------------------
def test_default_flag_false_preserves_exact_order(monkeypatch):
    # A (manual) and B (trusted lesson) are equal-score (no query) and equally
    # recent, so retrieval order is the input order [A, B]. When enabled the
    # tie-breaker would raise the hotter B; with the default-off flag it must not.
    a = _lesson("A", source_type="manual")
    b = _hot("B")
    _feed(monkeypatch, [a, b])
    _enable(monkeypatch, enabled=False)

    out = lr.find_active_lessons(query=None, limit=5)

    assert [r["id"] for r in out] == ["A", "B"]


# ---------------------------------------------------------------------------
# 2 - default flag false does not add tie-break metadata
# ---------------------------------------------------------------------------
def test_default_flag_false_adds_no_metadata(monkeypatch):
    _feed(monkeypatch, [_lesson("A", source_type="manual"), _hot("B")])
    _enable(monkeypatch, enabled=False)

    out = lr.find_active_lessons(query=None, limit=5)

    assert all(TIEBREAK_METADATA_KEY not in record for record in out)


# ---------------------------------------------------------------------------
# 3 - default flag false does not mutate candidates
# ---------------------------------------------------------------------------
def test_default_flag_false_does_not_mutate_candidates(monkeypatch):
    a = _lesson("A", source_type="manual")
    b = _hot("B")
    snapshot = copy.deepcopy([a, b])
    _feed(monkeypatch, [a, b])
    _enable(monkeypatch, enabled=False)

    lr.find_active_lessons(query=None, limit=5)

    assert [a, b] == snapshot


# ---------------------------------------------------------------------------
# 4 - existing CONTROL prompt output is unchanged with default flags
# ---------------------------------------------------------------------------
def test_control_prompt_unchanged_with_default_flags(monkeypatch):
    a = _lesson("A", summary="alpha note", source_type="manual")
    b = _hot("B", summary="beta note")
    _feed(monkeypatch, [a, b])
    monkeypatch.setattr(config, "LESSON_RETRIEVAL_ENABLED", True, raising=False)
    _enable(monkeypatch, enabled=False)

    # Spy: prove the prompt path never consults the tie-breaker when off.
    calls: list = []
    real = lr.apply_memory_temperature_tiebreaker

    def spy(candidates, **kwargs):
        calls.append(kwargs)
        return real(candidates, **kwargs)

    monkeypatch.setattr(lr, "apply_memory_temperature_tiebreaker", spy)

    block = control_engine._lessons_prompt_block(repo_path=None, user_query="alpha beta")

    assert calls == []  # tie-breaker not invoked under default-off flag
    assert "Lesson 1: A" in block
    assert "Lesson 2: B" in block
    assert "memory_temperature_tiebreak" not in block


# ---------------------------------------------------------------------------
# 5 - enabled flag invokes the tie-breaker at the final ordering boundary
# ---------------------------------------------------------------------------
def test_enabled_invokes_tiebreaker_at_ordering_boundary(monkeypatch):
    _feed(monkeypatch, [_lesson("A", source_type="manual")])
    _enable(monkeypatch, enabled=True)

    calls: list = []
    real = lr.apply_memory_temperature_tiebreaker

    def spy(candidates, **kwargs):
        calls.append(kwargs)
        return real(candidates, **kwargs)

    monkeypatch.setattr(lr, "apply_memory_temperature_tiebreaker", spy)

    lr.find_active_lessons(query=None, limit=5)

    assert len(calls) == 1
    assert calls[0].get("enabled") is True
    assert calls[0].get("tiebreak_only") is True


# ---------------------------------------------------------------------------
# 6 - enabled flag can reorder near-equal candidates
# ---------------------------------------------------------------------------
def test_enabled_can_reorder_near_equal_candidates(monkeypatch):
    a = _lesson("A", source_type="manual")  # hot-ish (~0.78)
    b = _hot("B")  # hotter (clamped 1.0)
    _feed(monkeypatch, [a, b])
    _enable(monkeypatch, enabled=True)

    out = lr.find_active_lessons(query=None, limit=5)

    # Equal score + equal recency → retrieval order [A, B]; the hotter trusted
    # lesson B rises within the near-equal group.
    assert [r["id"] for r in out] == ["B", "A"]


# ---------------------------------------------------------------------------
# 7 - enabled flag cannot reorder clearly different scores
# ---------------------------------------------------------------------------
def test_enabled_cannot_reorder_clearly_different_scores(monkeypatch):
    # HI matches the case_name (+100) but is cold; LO only matches the query
    # (+5) but is hot. Their scores are far apart, so they are in different
    # near-equal groups and the hot LO can never overtake the cold HI.
    hi = _lesson(
        "HI",
        case_name="py_demo",
        summary="retry helper",
        source_type="manual",
        updated_at=_ts(90),
        created_at=_ts(90),
    )
    lo = _hot("LO", case_name="py_other", summary="retry helper")
    _feed(monkeypatch, [hi, lo])
    _enable(monkeypatch, enabled=True)

    out = lr.find_active_lessons(case_name="py_demo", query="retry", limit=5)

    assert [r["id"] for r in out] == ["HI", "LO"]


# ---------------------------------------------------------------------------
# 8 - cold candidate is not removed
# ---------------------------------------------------------------------------
def test_enabled_does_not_remove_cold_candidate(monkeypatch):
    cold = _lesson("COLD", source_type="manual", updated_at=_ts(120), created_at=_ts(120))
    hot = _hot("HOT")
    _feed(monkeypatch, [hot, cold])
    _enable(monkeypatch, enabled=True)

    out = lr.find_active_lessons(query=None, limit=5)
    ids = [r["id"] for r in out]

    assert "COLD" in ids
    assert set(ids) == {"HOT", "COLD"}


# ---------------------------------------------------------------------------
# 9 - frozen / audit-only / blocked candidate is not surfaced
# ---------------------------------------------------------------------------
def test_enabled_does_not_surface_frozen_audit_only(monkeypatch):
    # An audit-only record classifies as frozen even though its status is still
    # "active" and it carries hot signals. The tie-breaker must sink it to the
    # bottom of its group (never surfaced above a real lesson) without removing
    # or reviving it.
    frozen = _hot("FROZEN", audit_only=True)
    hot = _hot("HOT")
    _feed(monkeypatch, [frozen, hot])
    _enable(monkeypatch, enabled=True)

    out = lr.find_active_lessons(query=None, limit=5)
    ids = [r["id"] for r in out]

    assert ids[0] == "HOT"  # frozen record never surfaced at the top
    assert ids[-1] == "FROZEN"  # sunk last
    assert "FROZEN" in ids  # not hard-filtered / removed
    frozen_row = next(r for r in out if r["id"] == "FROZEN")
    assert frozen_row[TIEBREAK_METADATA_KEY]["temperature_band"] == "frozen"


# ---------------------------------------------------------------------------
# 10 - tie-break metadata appears only when enabled
# ---------------------------------------------------------------------------
def test_tiebreak_metadata_only_present_when_enabled(monkeypatch):
    lessons = [_lesson("A", source_type="manual"), _hot("B")]
    _feed(monkeypatch, lessons)

    _enable(monkeypatch, enabled=False)
    out_off = lr.find_active_lessons(query=None, limit=5)
    assert all(TIEBREAK_METADATA_KEY not in r for r in out_off)

    _enable(monkeypatch, enabled=True)
    out_on = lr.find_active_lessons(query=None, limit=5)
    assert all(TIEBREAK_METADATA_KEY in r for r in out_on)
    # Enabling must not mutate the caller-supplied source records.
    assert all(TIEBREAK_METADATA_KEY not in src for src in lessons)


# ---------------------------------------------------------------------------
# 11 - harness default remains false / unwired
# ---------------------------------------------------------------------------
def test_harness_default_remains_false_and_unwired():
    from core import harness_controls as hc

    assert config.MEMORY_TEMPERATURE_RETRIEVAL_ENABLED is False
    assert config.MEMORY_TEMPERATURE_TIEBREAK_ONLY is True

    for control_id in ("MEMORY_TEMPERATURE_RETRIEVAL_ENABLED", "MEMORY_TEMPERATURE_TIEBREAK_ONLY"):
        control = hc.get_control(control_id)
        assert control is not None
        assert control.control_type == hc.READ_ONLY_PLANNED
        assert control.wired is False


# ---------------------------------------------------------------------------
# 12 - AST guard: no forbidden side effects / sinks; no CONTROL prompt rewrite
# ---------------------------------------------------------------------------
def test_ast_guard_lesson_retrieval_wiring_has_no_forbidden_sinks():
    source = (PROJECT_ROOT / "core" / "lesson_retrieval.py").read_text(encoding="utf-8")
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

    forbidden_network = {"requests", "httpx", "urllib", "aiohttp", "socket", "subprocess", "openai"}
    assert forbidden_network.isdisjoint(part.split(".")[0] for part in imported_modules)

    forbidden_calls = {
        "call_model",
        "call_api",
        "run_gemini_request",
        "save_lesson",
        "write_lesson",
        "promote_lesson",
        "block_lesson",
        "save_candidate_lesson",
        "update_lesson",
        "delete_lesson",
        "apply_patch_plan",
        "generate_patch",
        "validate_patch",
        "run_validation",
        "run_validation_command",
        "run_benchmarks",
        "Popen",
        "check_call",
        "check_output",
    }
    assert forbidden_calls.isdisjoint(call_names)

    # No broad CONTROL prompt rewrite: the retrieval module must not reach into
    # the control-engine prompt builder.
    assert "control_engine" not in source
    assert "build_control_prompt" not in source

    # The CONTROL prompt builder still delegates to the retrieval boundary and
    # is itself never wired to the tie-breaker (the wiring lives one layer down).
    control_source = (PROJECT_ROOT / "core" / "control_engine.py").read_text(encoding="utf-8")
    assert "find_active_lessons" in control_source
    assert "apply_memory_temperature_tiebreaker" not in control_source
    assert "memory_temperature_retrieval" not in control_source
