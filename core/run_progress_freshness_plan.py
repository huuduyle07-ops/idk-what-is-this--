"""UX.LIVE.7 - report-only Run Progress Snapshot Freshness Plan.

This module defines a future classifier contract.  It does not read snapshots,
inspect a runtime, or classify live data; it only emits the deterministic plan
that a later UX.LIVE.8 implementation must follow.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any


REPORT_KIND = "run_progress_freshness_plan"
THIS_PHASE_ID = "UX.LIVE.7"
JSON_NAME = "run_progress_freshness_plan.json"
MD_NAME = "run_progress_freshness_plan.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "ux" / "run_progress_freshness_plan"

READY = "run_progress_freshness_plan_ready"
READY_WITH_WARNINGS = "run_progress_freshness_plan_ready_with_warnings"
INCOMPLETE = "run_progress_freshness_plan_incomplete"
BLOCKED = "run_progress_freshness_plan_blocked"

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "UX.LIVE.8",
    "title": "Freshness Classification Implementation",
    "reason": "Implement the pure advisory classifier and narrow loader/UI display only after this contract is reviewed.",
}

REQUIRED_CLASSIFICATION_INPUTS: tuple[str, ...] = (
    "created_at",
    "updated_at",
    "terminal",
    "sequence_number",
    "snapshot_status",
    "current_stage_id",
    "observed_stage_ids",
    "warning_stage_ids",
    "error_stage_ids",
    "writer_enabled",
    "loader_retrieved_at_optional",
)
REQUIRED_FRESHNESS_STATUSES: tuple[str, ...] = (
    "fresh",
    "recent",
    "terminal",
    "stale",
    "possibly_abandoned",
    "unknown",
)
REQUIRED_WARNING_CODES: tuple[str, ...] = (
    "missing_created_at",
    "missing_updated_at",
    "invalid_created_at",
    "invalid_updated_at",
    "naive_timestamp",
    "clock_skew_detected",
    "updated_before_created",
    "invalid_sequence_number",
    "terminal_state_unrecognized",
    "threshold_configuration_invalid",
    "snapshot_schema_inconsistent",
)
REQUIRED_RESULT_FIELDS: tuple[str, ...] = (
    "freshness_status",
    "observed_at",
    "created_at",
    "updated_at",
    "age_seconds",
    "lifetime_seconds",
    "terminal",
    "terminal_outcome",
    "terminal_stage_id",
    "clock_skew_detected",
    "timestamp_parse_valid",
    "thresholds_used",
    "warning_codes",
    "advisory_notice",
    "runtime_authority",
    "action_triggered",
)

DEFAULT_THRESHOLDS: dict[str, int] = {
    "fresh_seconds": 15,
    "recent_seconds": 60,
    "abandoned_seconds": 300,
    "clock_skew_tolerance_seconds": 5,
}

_SAFETY_FALSE_FIELDS: tuple[str, ...] = (
    "report_only",
    "runtime_behavior_changed",
    "ui_behavior_changed",
    "polling_enabled",
    "streaming_enabled",
    "automatic_retry_enabled",
    "cleanup_enabled",
    "runtime_authority",
    "action_triggered",
)
_FORBIDDEN_NOW_CONTEXT: dict[str, str] = {
    "polling_added": "polling_enabled",
    "streaming_added": "streaming_enabled",
    "automatic_retry_added": "automatic_retry_enabled",
    "cleanup_added": "cleanup_enabled",
    "runtime_changed": "runtime_behavior_changed",
    "ui_changed": "ui_behavior_changed",
    "classification_is_authority": "runtime_authority",
    "classification_triggers_action": "action_triggered",
    "cancellation_added": "action_triggered",
    "restart_added": "action_triggered",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _normalize_thresholds(value: Any) -> tuple[dict[str, int], list[str]]:
    """Document the future safe configuration fallback without reading config."""
    supplied = _as_dict(value)
    if not supplied:
        return dict(DEFAULT_THRESHOLDS), []
    parsed: dict[str, int] = {}
    for key, default in DEFAULT_THRESHOLDS.items():
        candidate = supplied.get(key, default)
        if isinstance(candidate, bool):
            return dict(DEFAULT_THRESHOLDS), ["threshold_configuration_invalid"]
        try:
            numeric = float(candidate)
        except (TypeError, ValueError):
            return dict(DEFAULT_THRESHOLDS), ["threshold_configuration_invalid"]
        if not isfinite(numeric) or numeric < 0 or numeric != int(numeric):
            return dict(DEFAULT_THRESHOLDS), ["threshold_configuration_invalid"]
        parsed[key] = int(numeric)
    if not (parsed["fresh_seconds"] < parsed["recent_seconds"] < parsed["abandoned_seconds"]):
        return dict(DEFAULT_THRESHOLDS), ["threshold_configuration_invalid"]
    return parsed, []


def _safety_flags(safety_context: Any) -> dict[str, bool]:
    flags = {"report_only": True}
    flags.update({key: False for key in _SAFETY_FALSE_FIELDS if key != "report_only"})
    for key, value in _as_dict(safety_context).items():
        target = _FORBIDDEN_NOW_CONTEXT.get(str(key), str(key))
        if target in flags:
            flags[target] = bool(value)
    return flags


def _freshness_statuses() -> list[dict[str, Any]]:
    return [
        {
            "status": "fresh",
            "conditions": ["nonterminal", "valid timezone-aware timestamps", "age_seconds <= fresh_seconds"],
            "meaning": "Updated inside the narrow active window; this does not prove health, completion, or a future update.",
            "notice": "Progress was updated recently. This does not confirm that the run is healthy or complete.",
        },
        {
            "status": "recent",
            "conditions": ["nonterminal", "valid timezone-aware timestamps", "fresh_seconds < age_seconds <= recent_seconds"],
            "meaning": "May still be active; operator attention is not necessarily required.",
            "notice": "Progress was updated within the recent window.",
        },
        {
            "status": "terminal",
            "conditions": ["terminal is explicitly true", "valid and recognized terminal evidence when available"],
            "meaning": "Takes precedence over ordinary age classification and never implies validation, approval, or success.",
            "notice": "The run reported a terminal final-response state. This does not imply validation or approval.",
        },
        {
            "status": "stale",
            "conditions": ["nonterminal", "valid timezone-aware timestamps", "recent_seconds < age_seconds <= abandoned_seconds"],
            "meaning": "Not updated recently; it is not a failure declaration.",
            "notice": "This nonterminal snapshot has not been updated recently.",
        },
        {
            "status": "possibly_abandoned",
            "conditions": ["nonterminal", "valid timezone-aware timestamps", "age_seconds > abandoned_seconds", "no terminal evidence"],
            "meaning": "An advisory suspicion only; it must not cancel, restart, retry, clean up, or intervene with a worker.",
            "notice": "This nonterminal snapshot has not been updated for an extended period. The run may have stopped, but no automatic action has been taken.",
        },
        {
            "status": "unknown",
            "conditions": ["missing, malformed, naive, inconsistent, or skewed timestamp evidence", "insufficient safe evidence"],
            "meaning": "The classifier cannot calculate a trustworthy age.",
            "notice": "Snapshot freshness could not be classified safely.",
        },
        {
            "status": "invalid",
            "optional": True,
            "conditions": ["snapshot violates the approved schema or safety contract"],
            "meaning": "Separate from age classification; it is never a reason to act on the snapshot.",
            "notice": "Snapshot freshness could not be classified safely.",
        },
    ]


def _warning_catalog() -> list[dict[str, str]]:
    messages = {
        "missing_created_at": "created_at is absent.",
        "missing_updated_at": "updated_at is absent.",
        "invalid_created_at": "created_at is not a safely parseable UTC timestamp.",
        "invalid_updated_at": "updated_at is not a safely parseable UTC timestamp.",
        "naive_timestamp": "A timestamp lacks timezone information and local time must not be assumed.",
        "clock_skew_detected": "A timestamp is beyond the documented future-skew tolerance.",
        "updated_before_created": "updated_at precedes created_at.",
        "invalid_sequence_number": "sequence_number is absent, negative, or not an integer.",
        "terminal_state_unrecognized": "terminal is true but its outcome cannot be safely recognized.",
        "threshold_configuration_invalid": "Threshold configuration was malformed or unordered; documented safe defaults apply.",
        "snapshot_schema_inconsistent": "Required approved metadata is inconsistent.",
    }
    return [{"code": code, "meaning": messages[code]} for code in REQUIRED_WARNING_CODES]


def _plan_incomplete_reasons(plan: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    present_statuses = {str(item.get("status")) for item in _as_list(plan.get("freshness_statuses")) if isinstance(item, dict)}
    missing_statuses = set(REQUIRED_FRESHNESS_STATUSES) - present_statuses
    if missing_statuses:
        reasons.append("freshness_status_taxonomy_missing")
    thresholds = _as_dict(plan.get("default_thresholds"))
    if not {"fresh_seconds", "recent_seconds", "abandoned_seconds", "clock_skew_tolerance_seconds"} <= set(thresholds):
        reasons.append("default_thresholds_missing")
    if not _as_list(plan.get("status_precedence")):
        reasons.append("status_precedence_missing")
    if not _as_dict(plan.get("terminal_precedence")):
        reasons.append("terminal_precedence_missing")
    if not _as_dict(plan.get("malformed_timestamp_policy")):
        reasons.append("malformed_timestamp_policy_missing")
    if not _as_dict(plan.get("clock_skew_policy")):
        reasons.append("clock_skew_policy_missing")
    result_fields = set(_as_list(_as_dict(plan.get("proposed_classifier_output")).get("fields")))
    if not set(REQUIRED_RESULT_FIELDS) <= result_fields:
        reasons.append("proposed_classifier_output_missing")
    if _as_dict(plan.get("implementation_boundaries")).get("next_implementation_phase") != "UX.LIVE.8":
        reasons.append("ux_live_8_boundary_missing")
    return reasons


def _plan_blockers(plan: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if plan.get("report_only") is not True:
        blockers.append("report_only_boundary_missing")
    for key in _SAFETY_FALSE_FIELDS:
        if key == "report_only":
            continue
        if plan.get(key) is not False:
            blockers.append(f"forbidden_behavior_enabled:{key}")
    boundaries = _as_dict(plan.get("implementation_boundaries"))
    for key in ("process_inspection_required", "network_probe_required", "database_state_required", "raw_content_required"):
        if boundaries.get(key) is True:
            blockers.append(f"forbidden_input_or_dependency:{key}")
    if _as_dict(plan.get("terminal_precedence")).get("terminal_age_overrides_terminal") is True:
        blockers.append("terminal_age_overrides_terminal")
    if _as_dict(plan.get("configuration_contract")).get("configuration_changes_execution_behavior") is True:
        blockers.append("configuration_changes_execution_behavior")
    relationship = _as_dict(plan.get("future_polling_relationship"))
    if relationship.get("stale_starts_polling") is True:
        blockers.append("stale_starts_polling")
    if relationship.get("possibly_abandoned_triggers_retry_or_cancellation") is True:
        blockers.append("possibly_abandoned_triggers_action")
    return _dedupe(blockers)


def _evaluate_plan_status(plan: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    blockers = _plan_blockers(plan)
    incomplete = _plan_incomplete_reasons(plan)
    if blockers:
        return BLOCKED, incomplete, blockers
    if incomplete:
        return INCOMPLETE, incomplete, blockers
    warnings = _as_list(plan.get("warnings"))
    return (READY_WITH_WARNINGS if warnings else READY), incomplete, blockers


def build_run_progress_freshness_plan(
    *,
    created_at: str = "",
    threshold_overrides: Any = None,
    safety_context: Any = None,
    plan_overrides: Any = None,
) -> dict[str, Any]:
    """Return a data-only contract for a later freshness classifier.

    ``threshold_overrides`` exists only to test documented configuration fallback;
    this phase does not read environment variables or runtime configuration.
    ``plan_overrides`` is likewise a test seam for proving status logic.
    """
    thresholds, threshold_warnings = _normalize_thresholds(threshold_overrides)
    plan: dict[str, Any] = {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "created_at": created_at or _utc_now(),
        **_safety_flags(safety_context),
        "classification_inputs": {
            "approved_snapshot_metadata_only": list(REQUIRED_CLASSIFICATION_INPUTS),
            "optional_future_input": "loader_retrieved_at supplied to the future classifier only; it is not persisted or authoritative.",
            "excluded_inputs": [
                "raw prompts", "raw responses", "user messages", "repository paths", "model output contents",
                "worker process inspection", "database state", "operating-system process checks", "browser activity",
                "hidden heartbeats", "network probes",
            ],
        },
        "time_model": {
            "observed_at": "Timezone-aware UTC time at future classification.",
            "created_at": "Timezone-aware UTC snapshot creation time.",
            "updated_at": "Timezone-aware UTC latest successful snapshot update time.",
            "age_seconds": "null or max(0, observed_at - updated_at); large future skew is unknown, not silently clamped fresh.",
            "lifetime_seconds": "null or max(0, observed_at - created_at).",
            "timestamp_parse_valid": "True only when required timestamps are safely parseable and timezone-aware.",
            "naive_timestamp_policy": "Reject or classify unknown with naive_timestamp; never assume local time.",
        },
        "freshness_statuses": _freshness_statuses(),
        "status_precedence": [
            {"rank": 1, "rule": "invalid or unsafe snapshot -> invalid"},
            {"rank": 2, "rule": "unclassifiable timestamp or inconsistent required fields -> unknown"},
            {"rank": 3, "rule": "explicit terminal=true -> terminal before age classification"},
            {"rank": 4, "rule": "clock skew beyond tolerance -> unknown"},
            {"rank": 5, "rule": "age_seconds <= fresh_seconds -> fresh"},
            {"rank": 6, "rule": "age_seconds <= recent_seconds -> recent"},
            {"rank": 7, "rule": "age_seconds <= abandoned_seconds -> stale"},
            {"rank": 8, "rule": "age_seconds > abandoned_seconds -> possibly_abandoned"},
        ],
        "default_thresholds": thresholds,
        "configuration_contract": {
            "names": {
                "fresh_seconds": "RUN_PROGRESS_FRESH_SECONDS",
                "recent_seconds": "RUN_PROGRESS_RECENT_SECONDS",
                "abandoned_seconds": "RUN_PROGRESS_ABANDONED_SECONDS",
                "clock_skew_tolerance_seconds": "RUN_PROGRESS_CLOCK_SKEW_TOLERANCE_SECONDS",
            },
            "parsing": "Future code must safely parse finite non-negative numeric values and use documented defaults for missing or malformed values.",
            "ordering": "fresh_seconds < recent_seconds < abandoned_seconds.",
            "fallback": "Malformed, non-finite, negative, or unordered values produce threshold_configuration_invalid and fall back to DEFAULT_THRESHOLDS.",
            "boundary": "Configuration changes advisory classification only; it cannot enable polling, execution, retries, or runtime behavior.",
            "configuration_changes_execution_behavior": False,
        },
        "terminal_precedence": {
            "explicit_terminal_precedes_age": True,
            "terminal_age_overrides_terminal": False,
            "old_terminal_remains_terminal": True,
            "terminal_outcome": {
                "success": "current_stage_id is final_response_ready and no approved error terminal evidence exists; advisory only, not validation proof.",
                "error": "current_stage_id is error_reported or approved error-stage evidence exists.",
                "unknown": "terminal is true but the state is not safely recognized.",
            },
            "terminal_details": ["terminal_outcome", "terminal_stage_id", "terminal_age_seconds"],
            "not_success_proof": "terminal=true never means a patch was approved, validation passed, or execution succeeded.",
        },
        "clock_skew_policy": {
            "small_tolerance_seconds": thresholds["clock_skew_tolerance_seconds"],
            "beyond_tolerance": "freshness_status=unknown, clock_skew_detected=true, and warning code clock_skew_detected.",
            "negative_age_forbidden": True,
            "large_future_timestamp": "Do not silently clamp a large future timestamp and call it fresh.",
        },
        "malformed_timestamp_policy": {
            "missing_updated_at": "unknown with missing_updated_at.",
            "missing_created_at": "unknown with missing_created_at.",
            "malformed_or_unsupported": "unknown with invalid_created_at or invalid_updated_at; no exception escapes.",
            "naive_timestamp": "unknown with naive_timestamp unless a future implementation explicitly rejects it before result creation.",
            "updated_before_created": "unknown with updated_before_created and snapshot_schema_inconsistent.",
            "future_created_or_updated": "unknown beyond the documented clock-skew tolerance.",
        },
        "sequence_policy": {
            "supporting_evidence_only": True,
            "does_not_determine_freshness": True,
            "high_sequence_not_fresh": True,
            "sequence_one_may_be_fresh": True,
            "timestamps_required_for_age": True,
            "decreasing_sequence": "May add invalid_sequence_number or snapshot_schema_inconsistent; it does not trigger execution decisions.",
            "duplicate_sequence": "Not necessarily an error.",
        },
        "warning_codes": _warning_catalog(),
        "proposed_classifier_output": {
            "fields": list(REQUIRED_RESULT_FIELDS),
            "invariants": [
                "age_seconds is null or non-negative.",
                "Classification is deterministic for identical inputs and observed_at.",
                "Terminal state takes precedence over age-based stale classification.",
                "possibly_abandoned remains advisory and cannot trigger action.",
                "runtime_authority is always false.",
                "action_triggered is always false.",
                "Classification never changes execution or canonical snapshots.",
            ],
        },
        "implementation_boundaries": {
            "next_implementation_phase": "UX.LIVE.8",
            "recommended_files": [
                "core/run_progress_freshness.py",
                "tests/test_run_progress_freshness.py",
                "narrow loader integration",
                "narrow UI display integration",
            ],
            "allowed_future_behavior": [
                "Pure deterministic advisory classification when an existing snapshot is loaded or manually refreshed.",
                "Derived freshness data may be included in the existing GET loader response and displayed in the existing panel.",
            ],
            "prohibited_future_behavior": [
                "Do not write freshness back into the snapshot.",
                "Do not add polling, background requests, streaming, retries, runtime execution changes, or canonical snapshot mutation.",
                "Do not make freshness an approval, validation, or execution authority.",
            ],
            "process_inspection_required": False,
            "network_probe_required": False,
            "database_state_required": False,
            "raw_content_required": False,
        },
        "future_polling_relationship": {
            "implemented_now": False,
            "freshness_requires_polling": False,
            "stale_starts_polling": False,
            "possibly_abandoned_triggers_retry_or_cancellation": False,
            "later_sequence": [
                "UX.LIVE.8 - Freshness Classification Implementation",
                "UX.LIVE.9 - Bounded Polling Experiment Plan",
                "UX.LIVE.10 - Optional Default-Off Bounded Polling",
                "UX.LIVE.CLOSE - Branch Checkpoint",
            ],
            "boundary": "Any later polling may consume freshness only for display and bounded stop conditions; freshness remains non-authoritative.",
        },
        "warnings": [
            "Thresholds are planning defaults only; they need review against real snapshot cadence before implementation.",
            "The classifier and UI display are intentionally unimplemented until UX.LIVE.8.",
        ] + threshold_warnings,
        "blockers": [],
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }
    plan.update(copy.deepcopy(_as_dict(plan_overrides)))
    status, incomplete, blockers = _evaluate_plan_status(plan)
    plan["plan_status"] = status
    plan["incomplete_reasons"] = incomplete
    plan["blockers"] = blockers
    return plan


def render_run_progress_freshness_plan_markdown(plan: Any) -> str:
    """Render the contract without executing, inspecting, or classifying a run."""
    report = _as_dict(plan)
    lines = [
        "# Run Progress Snapshot Freshness and Staleness Plan",
        "",
        f"- Phase: `{_md(report.get('phase_id'))}`",
        f"- Status: `{_md(report.get('plan_status'))}`",
        f"- Report only: `{str(report.get('report_only')).lower()}`",
        "",
        "## Safety Boundary",
        "",
        "This is a planning artifact only. It does not classify a live snapshot, alter runtime or UI behavior, poll, stream, retry, clean up, cancel, restart, or trigger any action.",
        "",
        "## Classification Inputs",
        "",
        "| Input | Contract |",
        "|---|---|",
    ]
    for item in _as_list(_as_dict(report.get("classification_inputs")).get("approved_snapshot_metadata_only")):
        lines.append(f"| `{_md(item)}` | Already-approved snapshot metadata only |")
    lines += ["", "## Freshness Statuses", "", "| Status | Meaning |", "|---|---|"]
    for item in _as_list(report.get("freshness_statuses")):
        entry = _as_dict(item)
        lines.append(f"| `{_md(entry.get('status'))}` | {_md(entry.get('meaning'))} |")
    lines += ["", "## Deterministic Precedence", ""]
    for item in _as_list(report.get("status_precedence")):
        entry = _as_dict(item)
        lines.append(f"{_md(entry.get('rank'))}. {_md(entry.get('rule'))}")
    lines += ["", "## Threshold and Timestamp Policy", ""]
    thresholds = _as_dict(report.get("default_thresholds"))
    for key in ("fresh_seconds", "recent_seconds", "abandoned_seconds", "clock_skew_tolerance_seconds"):
        lines.append(f"- `{key}`: `{_md(thresholds.get(key))}`")
    lines += [
        "",
        _md(_as_dict(report.get("configuration_contract")).get("fallback")),
        "",
        "## Terminal, Sequence, and Clock-Skew Rules",
        "",
        f"- {_md(_as_dict(report.get('terminal_precedence')).get('not_success_proof'))}",
        f"- {_md(_as_dict(report.get('sequence_policy')).get('decreasing_sequence'))}",
        f"- {_md(_as_dict(report.get('clock_skew_policy')).get('beyond_tolerance'))}",
        "",
        "## Proposed Future Classifier Output",
        "",
    ]
    for field in _as_list(_as_dict(report.get("proposed_classifier_output")).get("fields")):
        lines.append(f"- `{_md(field)}`")
    lines += ["", "## UX.LIVE.8 Boundary", ""]
    for item in _as_list(_as_dict(report.get("implementation_boundaries")).get("prohibited_future_behavior")):
        lines.append(f"- {_md(item)}")
    lines += ["", "## Warnings", ""]
    for warning in _as_list(report.get("warnings")):
        lines.append(f"- {_md(warning)}")
    lines += ["", "## Next Phase", "", f"`{_md(_as_dict(report.get('recommended_next_phase')).get('phase_id'))}` — {_md(_as_dict(report.get('recommended_next_phase')).get('title'))}", ""]
    return "\n".join(lines)


def write_run_progress_freshness_plan(plan: Any, output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    """Write the JSON and Markdown plan artifacts only when explicitly called."""
    report = copy.deepcopy(_as_dict(plan))
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_NAME
    md_path = root / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_run_progress_freshness_plan_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "markdown_path": str(md_path), "report": report}
