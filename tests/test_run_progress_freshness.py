"""Focused UX.LIVE.8 tests for the pure run-progress freshness classifier."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.run_progress_freshness import (
    DEFAULT_ABANDONED_SECONDS,
    DEFAULT_FRESH_SECONDS,
    DEFAULT_RECENT_SECONDS,
    FreshnessThresholds,
    classify_run_progress_freshness,
    parse_aware_utc_timestamp,
    resolve_freshness_thresholds,
    validate_threshold_order,
)


OBSERVED = "2026-07-11T00:10:00+00:00"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_PATH = PROJECT_ROOT / "core" / "run_progress_freshness.py"


def _snapshot(**overrides: object) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "created_at": "2026-07-11T00:00:00Z",
        "updated_at": "2026-07-11T00:10:00Z",
        "terminal": False,
        "sequence_number": 1,
        "snapshot_status": "run_progress_snapshot_available",
        "current_stage_id": "request_received",
        "observed_stage_ids": ["request_received"],
        "warning_stage_ids": [],
        "error_stage_ids": [],
        "writer_enabled": True,
    }
    snapshot.update(overrides)
    return snapshot


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (0, "fresh"),
        (DEFAULT_FRESH_SECONDS, "fresh"),
        (DEFAULT_FRESH_SECONDS + 0.1, "recent"),
        (DEFAULT_RECENT_SECONDS, "recent"),
        (DEFAULT_RECENT_SECONDS + 0.1, "stale"),
        (DEFAULT_ABANDONED_SECONDS - 0.1, "stale"),
        (DEFAULT_ABANDONED_SECONDS, "possibly_abandoned"),
    ],
)
def test_age_boundaries_are_deterministic(age: float, expected: str):
    observed = datetime(2026, 7, 11, 0, 10, 0, tzinfo=timezone.utc)
    result = classify_run_progress_freshness(
        _snapshot(updated_at=(observed - timedelta(seconds=age)).isoformat()),
        observed_at=observed,
    )
    assert result["freshness_status"] == expected
    assert result["age_seconds"] == pytest.approx(age)


def test_classification_is_pure_and_deterministic_for_same_inputs():
    snapshot = _snapshot(updated_at="2026-07-11T00:09:56+00:00")
    before = copy.deepcopy(snapshot)

    first = classify_run_progress_freshness(snapshot, observed_at=OBSERVED)
    second = classify_run_progress_freshness(snapshot, observed_at=OBSERVED)

    assert first == second
    assert snapshot == before
    assert first["freshness_status"] == "fresh"
    assert first["runtime_authority"] is False
    assert first["action_triggered"] is False
    assert first["actions_available"] == []


def test_terminal_precedence_and_outcomes_ignore_old_age():
    success = classify_run_progress_freshness(
        _snapshot(
            updated_at="2026-07-11T00:00:00+00:00",
            terminal=True,
            current_stage_id="final_response_ready",
            observed_stage_ids=["request_received", "final_response_ready"],
        ),
        observed_at=OBSERVED,
    )
    error = classify_run_progress_freshness(
        _snapshot(
            terminal=True,
            current_stage_id="error_reported",
            error_stage_ids=["error_reported"],
        ),
        observed_at=OBSERVED,
    )
    unknown = classify_run_progress_freshness(
        _snapshot(terminal=True, current_stage_id="terminal_elsewhere"),
        observed_at=OBSERVED,
    )

    assert success["freshness_status"] == error["freshness_status"] == unknown["freshness_status"] == "terminal"
    assert success["terminal_outcome"] == "success"
    assert success["advisory_notice"] == "The run reported a terminal final-response state. This does not imply validation or approval."
    assert error["terminal_outcome"] == "error"
    assert unknown["terminal_outcome"] == "unknown"
    assert "terminal_state_unrecognized" in unknown["warning_codes"]


@pytest.mark.parametrize(
    ("changes", "warning"),
    [
        ({"created_at": ""}, "missing_created_at"),
        ({"updated_at": "not-a-time"}, "invalid_updated_at"),
        ({"updated_at": "2026-07-11T00:10:00"}, "naive_timestamp"),
        ({"terminal": "true"}, "snapshot_schema_inconsistent"),
    ],
)
def test_unsafe_or_unparseable_input_returns_unknown(changes: dict[str, object], warning: str):
    result = classify_run_progress_freshness(_snapshot(**changes), observed_at=OBSERVED)

    assert result["freshness_status"] == "unknown"
    assert warning in result["warning_codes"]
    assert result["age_seconds"] is None


def test_future_time_is_safe_and_never_produces_negative_age():
    within_tolerance = classify_run_progress_freshness(
        _snapshot(
            created_at="2026-07-11T00:09:00+00:00",
            updated_at="2026-07-11T00:10:03+00:00",
        ),
        observed_at=OBSERVED,
    )
    beyond_tolerance = classify_run_progress_freshness(
        _snapshot(updated_at="2026-07-11T00:10:06+00:00"), observed_at=OBSERVED
    )

    assert within_tolerance["freshness_status"] == "fresh"
    assert within_tolerance["age_seconds"] == 0
    assert within_tolerance["clock_skew_detected"] is True
    assert "clock_skew_detected" in within_tolerance["warning_codes"]
    assert beyond_tolerance["freshness_status"] == "unknown"
    assert beyond_tolerance["age_seconds"] is None
    assert beyond_tolerance["clock_skew_detected"] is True


def test_time_inconsistency_and_sequence_are_advisory_not_execution_signals():
    inconsistent = classify_run_progress_freshness(
        _snapshot(created_at="2026-07-11T00:09:00+00:00", updated_at="2026-07-11T00:08:00+00:00"),
        observed_at=OBSERVED,
    )
    stale_high_sequence = classify_run_progress_freshness(
        _snapshot(updated_at="2026-07-11T00:00:00+00:00", sequence_number=999), observed_at=OBSERVED
    )
    fresh_first_sequence = classify_run_progress_freshness(
        _snapshot(updated_at="2026-07-11T00:09:59+00:00", sequence_number=1), observed_at=OBSERVED
    )

    assert inconsistent["freshness_status"] == "unknown"
    assert {"updated_before_created", "snapshot_schema_inconsistent"} <= set(inconsistent["warning_codes"])
    assert stale_high_sequence["freshness_status"] == "possibly_abandoned"
    assert fresh_first_sequence["freshness_status"] == "fresh"


def test_invalid_thresholds_fall_back_to_documented_defaults_without_raising():
    result = classify_run_progress_freshness(
        _snapshot(updated_at="2026-07-11T00:09:44+00:00"),
        observed_at=OBSERVED,
        thresholds={"fresh_seconds": 70, "recent_seconds": 60, "abandoned_seconds": 30},
    )
    resolved, warnings = resolve_freshness_thresholds({"fresh_seconds": float("inf")})

    assert result["freshness_status"] == "recent"
    assert "threshold_configuration_invalid" in result["warning_codes"]
    assert result["thresholds_used"]["fresh_seconds"] == DEFAULT_FRESH_SECONDS
    assert warnings == ["threshold_configuration_invalid"]
    assert resolved.fresh_seconds == DEFAULT_FRESH_SECONDS
    assert validate_threshold_order(FreshnessThresholds()) is True
    assert validate_threshold_order({"fresh_seconds": 10, "recent_seconds": 10, "abandoned_seconds": 20, "clock_skew_tolerance_seconds": 0}) is False


def test_valid_numeric_threshold_configuration_is_normalized_before_classification():
    result = classify_run_progress_freshness(
        _snapshot(updated_at="2026-07-11T00:09:40+00:00"),
        observed_at=OBSERVED,
        thresholds={
            "fresh_seconds": "10",
            "recent_seconds": "30",
            "abandoned_seconds": "90",
            "clock_skew_tolerance_seconds": "2",
        },
    )

    assert result["freshness_status"] == "recent"
    assert result["thresholds_used"]["fresh_seconds"] == 10


def test_parser_normalizes_aware_utc_and_rejects_naive_times():
    assert parse_aware_utc_timestamp("2026-07-11T09:00:00+09:00") == datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc)
    assert parse_aware_utc_timestamp("2026-07-11T00:00:00Z") == datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc)
    assert parse_aware_utc_timestamp("2026-07-11T00:00:00") is None


def test_classifier_source_has_no_io_or_runtime_control_dependencies():
    source = CORE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "import subprocess",
        "import requests",
        "import httpx",
        "socket.",
        "Path(",
        "open(",
        "setInterval",
        "WebSocket",
        "EventSource",
    ):
        assert forbidden not in source
