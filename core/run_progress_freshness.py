"""UX.LIVE.8 advisory freshness classification for safe run-progress snapshots.

The classifier is deliberately pure: it accepts approved snapshot metadata and
an optional observation time, then returns derived display data.  It does not
read or write artifacts, inspect a runtime, or decide what a run should do.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping


DEFAULT_FRESH_SECONDS = 15
DEFAULT_RECENT_SECONDS = 60
DEFAULT_ABANDONED_SECONDS = 300
DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS = 5

FRESHNESS_STATUSES: tuple[str, ...] = (
    "fresh",
    "recent",
    "terminal",
    "stale",
    "possibly_abandoned",
    "unknown",
)


@dataclass(frozen=True)
class FreshnessThresholds:
    """Advisory age thresholds.  Resolution validates every instance."""

    fresh_seconds: float = DEFAULT_FRESH_SECONDS
    recent_seconds: float = DEFAULT_RECENT_SECONDS
    abandoned_seconds: float = DEFAULT_ABANDONED_SECONDS
    clock_skew_tolerance_seconds: float = DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS


DEFAULT_THRESHOLDS = FreshnessThresholds()

_NOTICES = {
    "fresh": "Progress was updated recently. This does not confirm that the run is healthy or complete.",
    "recent": "Progress was updated within the recent window.",
    "stale": "This nonterminal snapshot has not been updated recently.",
    "possibly_abandoned": (
        "This nonterminal snapshot has not been updated for an extended period. "
        "The run may have stopped, but no automatic action has been taken."
    ),
    "unknown": "Snapshot freshness could not be classified safely.",
}
_TERMINAL_NOTICES = {
    "success": "The run reported a terminal final-response state. This does not imply validation or approval.",
    "error": "The run reported a terminal error state.",
    "unknown": "The run reported a terminal state whose outcome could not be recognized safely.",
}


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(code for code in values if code))


def _as_finite_non_negative_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if isfinite(numeric) and numeric >= 0 else None


def validate_threshold_order(thresholds: FreshnessThresholds | Mapping[str, Any] | Any) -> bool:
    """Return whether four finite, non-negative, strictly ordered thresholds are safe."""
    if isinstance(thresholds, FreshnessThresholds):
        values = asdict(thresholds)
    elif isinstance(thresholds, Mapping):
        values = thresholds
    else:
        return False
    try:
        fresh = _as_finite_non_negative_number(values["fresh_seconds"])
        recent = _as_finite_non_negative_number(values["recent_seconds"])
        abandoned = _as_finite_non_negative_number(values["abandoned_seconds"])
        skew = _as_finite_non_negative_number(values["clock_skew_tolerance_seconds"])
    except (KeyError, TypeError):
        return False
    return None not in (fresh, recent, abandoned, skew) and bool(fresh < recent < abandoned)


def resolve_freshness_thresholds(
    thresholds: FreshnessThresholds | Mapping[str, Any] | None = None,
) -> tuple[FreshnessThresholds, list[str]]:
    """Resolve safe advisory thresholds, falling back without raising."""
    if thresholds is None:
        return DEFAULT_THRESHOLDS, []
    if isinstance(thresholds, FreshnessThresholds):
        raw_values: Mapping[str, Any] = asdict(thresholds)
    elif isinstance(thresholds, Mapping):
        raw_values = thresholds
    else:
        return DEFAULT_THRESHOLDS, ["threshold_configuration_invalid"]
    if not validate_threshold_order(raw_values):
        return DEFAULT_THRESHOLDS, ["threshold_configuration_invalid"]
    try:
        candidate = FreshnessThresholds(
            fresh_seconds=_as_finite_non_negative_number(raw_values.get("fresh_seconds", DEFAULT_FRESH_SECONDS)),
            recent_seconds=_as_finite_non_negative_number(raw_values.get("recent_seconds", DEFAULT_RECENT_SECONDS)),
            abandoned_seconds=_as_finite_non_negative_number(raw_values.get("abandoned_seconds", DEFAULT_ABANDONED_SECONDS)),
            clock_skew_tolerance_seconds=_as_finite_non_negative_number(
                raw_values.get("clock_skew_tolerance_seconds", DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS)
            ),
        )
    except (AttributeError, TypeError):
        return DEFAULT_THRESHOLDS, ["threshold_configuration_invalid"]
    return candidate, []


def parse_aware_utc_timestamp(value: datetime | str | None) -> datetime | None:
    """Parse a timezone-aware timestamp and normalize it to UTC.

    A naive timestamp intentionally returns ``None`` rather than being treated
    as local time.  ``Z`` suffices are accepted for interoperable ISO input.
    """
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        candidate = value.strip()
        if candidate.endswith(("Z", "z")):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def calculate_snapshot_age(observed_at: datetime, updated_at: datetime) -> float:
    """Return a non-negative age in seconds after callers check skew policy."""
    return max(0.0, (observed_at - updated_at).total_seconds())


def classify_terminal_outcome(snapshot: Mapping[str, Any]) -> tuple[str, str | None, list[str]]:
    """Derive a terminal outcome from approved stage metadata only."""
    current_stage_id = snapshot.get("current_stage_id")
    current = current_stage_id if isinstance(current_stage_id, str) else ""
    error_stage_ids = snapshot.get("error_stage_ids", [])
    observed_stage_ids = snapshot.get("observed_stage_ids", [])
    error_ids = set()
    if isinstance(error_stage_ids, list):
        error_ids.update(item for item in error_stage_ids if isinstance(item, str))
    if isinstance(observed_stage_ids, list):
        error_ids.update(item for item in observed_stage_ids if isinstance(item, str) and item == "error_reported")

    if current == "error_reported" or "error_reported" in error_ids:
        return "error", "error_reported", []
    if current == "final_response_ready":
        return "success", "final_response_ready", []
    return "unknown", None, ["terminal_state_unrecognized"]


def build_freshness_notice(status: str, terminal_outcome: str | None = None) -> str:
    """Return the concise, non-authoritative notice approved for display."""
    if status == "terminal":
        return _TERMINAL_NOTICES.get(terminal_outcome or "unknown", _TERMINAL_NOTICES["unknown"])
    return _NOTICES.get(status, _NOTICES["unknown"])


def _timestamp_warning(field: str, raw_value: Any) -> str:
    if raw_value is None or raw_value == "":
        return f"missing_{field}"
    if isinstance(raw_value, datetime):
        if raw_value.tzinfo is None or raw_value.utcoffset() is None:
            return "naive_timestamp"
    elif isinstance(raw_value, str):
        candidate = raw_value.strip()
        if candidate:
            try:
                parsed = datetime.fromisoformat(candidate[:-1] + "+00:00" if candidate.endswith(("Z", "z")) else candidate)
            except ValueError:
                return f"invalid_{field}"
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                return "naive_timestamp"
        else:
            return f"missing_{field}"
    else:
        return f"invalid_{field}"
    return f"invalid_{field}"


def _empty_result(
    *,
    thresholds: FreshnessThresholds,
    warnings: list[str],
    observed: datetime | None = None,
    created: datetime | None = None,
    updated: datetime | None = None,
    terminal: bool = False,
    terminal_outcome: str | None = None,
    terminal_stage_id: str | None = None,
    clock_skew_detected: bool = False,
    timestamp_parse_valid: bool = False,
    age_seconds: float | None = None,
    lifetime_seconds: float | None = None,
    status: str = "unknown",
) -> dict[str, Any]:
    return {
        "freshness_status": status,
        "observed_at": observed.isoformat() if observed else None,
        "created_at": created.isoformat() if created else None,
        "updated_at": updated.isoformat() if updated else None,
        "age_seconds": max(0.0, age_seconds) if age_seconds is not None else None,
        "lifetime_seconds": max(0.0, lifetime_seconds) if lifetime_seconds is not None else None,
        "terminal": terminal,
        "terminal_outcome": terminal_outcome,
        "terminal_stage_id": terminal_stage_id,
        "clock_skew_detected": clock_skew_detected,
        "timestamp_parse_valid": timestamp_parse_valid,
        "thresholds_used": asdict(thresholds),
        "warning_codes": _dedupe(warnings),
        "advisory_notice": build_freshness_notice(status, terminal_outcome),
        "runtime_authority": False,
        "action_triggered": False,
        "actions_available": [],
    }


def classify_run_progress_freshness(
    snapshot: Mapping[str, Any],
    *,
    observed_at: datetime | str | None = None,
    thresholds: FreshnessThresholds | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify one safely loaded snapshot without mutating it or taking action."""
    resolved_thresholds, warnings = resolve_freshness_thresholds(thresholds)
    try:
        if not isinstance(snapshot, Mapping):
            return _empty_result(
                thresholds=resolved_thresholds,
                warnings=warnings + ["snapshot_schema_inconsistent"],
            )

        terminal_value = snapshot.get("terminal")
        if not isinstance(terminal_value, bool):
            return _empty_result(
                thresholds=resolved_thresholds,
                warnings=warnings + ["snapshot_schema_inconsistent"],
            )

        raw_created = snapshot.get("created_at")
        raw_updated = snapshot.get("updated_at")
        created = parse_aware_utc_timestamp(raw_created)
        updated = parse_aware_utc_timestamp(raw_updated)
        observed = datetime.now(timezone.utc) if observed_at is None else parse_aware_utc_timestamp(observed_at)
        timestamp_warnings = list(warnings)
        if created is None:
            timestamp_warnings.append(_timestamp_warning("created_at", raw_created))
        if updated is None:
            timestamp_warnings.append(_timestamp_warning("updated_at", raw_updated))
        if observed is None:
            timestamp_warnings.append("freshness_classification_failed")
        if created is None or updated is None or observed is None:
            return _empty_result(
                thresholds=resolved_thresholds,
                warnings=timestamp_warnings,
                observed=observed,
                created=created,
                updated=updated,
                terminal=terminal_value,
            )

        if not isinstance(snapshot.get("sequence_number"), int) or isinstance(snapshot.get("sequence_number"), bool) or snapshot["sequence_number"] < 0:
            warnings.append("invalid_sequence_number")

        if updated < created:
            return _empty_result(
                thresholds=resolved_thresholds,
                warnings=warnings + ["updated_before_created", "snapshot_schema_inconsistent"],
                observed=observed,
                created=created,
                updated=updated,
                terminal=terminal_value,
                timestamp_parse_valid=True,
            )

        future_updated_seconds = (updated - observed).total_seconds()
        future_created_seconds = (created - observed).total_seconds()
        clock_skew = future_updated_seconds > 0 or future_created_seconds > 0
        if max(future_updated_seconds, future_created_seconds) > resolved_thresholds.clock_skew_tolerance_seconds:
            return _empty_result(
                thresholds=resolved_thresholds,
                warnings=warnings + ["clock_skew_detected"],
                observed=observed,
                created=created,
                updated=updated,
                terminal=terminal_value,
                clock_skew_detected=True,
                timestamp_parse_valid=True,
            )
        if clock_skew:
            warnings.append("clock_skew_detected")

        age_seconds = calculate_snapshot_age(observed, updated)
        lifetime_seconds = calculate_snapshot_age(observed, created)
        if terminal_value:
            terminal_outcome, terminal_stage_id, terminal_warnings = classify_terminal_outcome(snapshot)
            return _empty_result(
                thresholds=resolved_thresholds,
                warnings=warnings + terminal_warnings,
                observed=observed,
                created=created,
                updated=updated,
                terminal=True,
                terminal_outcome=terminal_outcome,
                terminal_stage_id=terminal_stage_id,
                clock_skew_detected=clock_skew,
                timestamp_parse_valid=True,
                age_seconds=age_seconds,
                lifetime_seconds=lifetime_seconds,
                status="terminal",
            )

        if age_seconds <= resolved_thresholds.fresh_seconds:
            status = "fresh"
        elif age_seconds <= resolved_thresholds.recent_seconds:
            status = "recent"
        elif age_seconds < resolved_thresholds.abandoned_seconds:
            status = "stale"
        else:
            status = "possibly_abandoned"
        return _empty_result(
            thresholds=resolved_thresholds,
            warnings=warnings,
            observed=observed,
            created=created,
            updated=updated,
            terminal=False,
            clock_skew_detected=clock_skew,
            timestamp_parse_valid=True,
            age_seconds=age_seconds,
            lifetime_seconds=lifetime_seconds,
            status=status,
        )
    except Exception:
        return _empty_result(
            thresholds=resolved_thresholds,
            warnings=warnings + ["freshness_classification_failed"],
        )
