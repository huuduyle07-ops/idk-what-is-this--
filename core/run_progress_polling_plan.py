"""UX.LIVE.9 - report-only bounded run-progress polling experiment plan.

This module records a deterministic contract for a later browser-only experiment.
It does not schedule work, retrieve snapshots, inspect a runtime, or change any
browser, server, writer, loader, freshness, or execution behavior.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any


REPORT_KIND = "run_progress_polling_plan"
THIS_PHASE_ID = "UX.LIVE.9"
JSON_NAME = "run_progress_polling_plan.json"
MD_NAME = "run_progress_polling_plan.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "ux" / "run_progress_polling_plan"

READY = "run_progress_polling_plan_ready"
READY_WITH_WARNINGS = "run_progress_polling_plan_ready_with_warnings"
INCOMPLETE = "run_progress_polling_plan_incomplete"
BLOCKED = "run_progress_polling_plan_blocked"

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "UX.LIVE.10",
    "title": "Optional Default-Off Bounded Progress Polling",
    "reason": "Implement only this reviewed, page-local, GET-only bounded contract after browser dogfooding is planned.",
}

DEFAULT_POLLING_CONFIGURATION: dict[str, Any] = {
    "enabled": False,
    "poll_interval_seconds": 3,
    "minimum_poll_interval_seconds": 2,
    "maximum_poll_interval_seconds": 60,
    "maximum_duration_seconds": 300,
    "maximum_requests": 100,
    "maximum_consecutive_errors": 3,
    "hidden_tab_behavior": "pause",
}

REQUIRED_STOP_CONDITIONS: tuple[str, ...] = (
    "operator_stop",
    "terminal_snapshot",
    "association_changed",
    "associated_snapshot_unavailable",
    "duration_limit",
    "request_limit",
    "consecutive_error_limit",
    "page_unload",
    "browser_state_destroyed",
    "snapshot_id_safety_rejected",
    "configuration_disabled",
)
REQUIRED_UI_STATUSES: tuple[str, ...] = (
    "disabled",
    "ready",
    "active",
    "paused_hidden",
    "stopped_by_operator",
    "stopped_terminal",
    "stopped_association_changed",
    "stopped_duration_limit",
    "stopped_request_limit",
    "stopped_error_limit",
    "stopped_possibly_abandoned",
    "blocked",
    "unavailable",
)

_SAFETY_TRUE_FIELDS: tuple[str, ...] = ("report_only",)
_SAFETY_FALSE_FIELDS: tuple[str, ...] = (
    "polling_implemented",
    "polling_enabled_by_default",
    "background_requests_enabled",
    "automatic_retry_enabled",
    "streaming_enabled",
    "runtime_behavior_changed",
    "snapshot_writer_changed",
    "runtime_authority",
    "action_triggered",
)
_SAFETY_CONTEXT_FIELDS: dict[str, str] = {
    "polling_added": "polling_implemented",
    "polling_implemented": "polling_implemented",
    "polling_enabled_by_default": "polling_enabled_by_default",
    "background_requests_added": "background_requests_enabled",
    "automatic_retry_added": "automatic_retry_enabled",
    "streaming_added": "streaming_enabled",
    "runtime_changed": "runtime_behavior_changed",
    "snapshot_writer_changed": "snapshot_writer_changed",
    "runtime_authority": "runtime_authority",
    "action_triggered": "action_triggered",
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


def _safety_flags(safety_context: Any) -> dict[str, bool]:
    flags = {key: True for key in _SAFETY_TRUE_FIELDS}
    flags.update({key: False for key in _SAFETY_FALSE_FIELDS})
    for key, value in _as_dict(safety_context).items():
        target = _SAFETY_CONTEXT_FIELDS.get(str(key), str(key))
        if target in flags:
            flags[target] = bool(value)
    return flags


def _is_finite_positive(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return isfinite(numeric) and numeric > 0


def _stop_conditions() -> list[dict[str, str]]:
    meanings = {
        "operator_stop": "The operator selects Stop progress updates; this cancels only the next scheduled browser refresh.",
        "terminal_snapshot": "Render the terminal response, then stop because no more reads are necessary for that snapshot.",
        "association_changed": "Stop the old session when the safe associated snapshot ID changes; never auto-start the new association.",
        "associated_snapshot_unavailable": "Stop when the current safe association can no longer be loaded.",
        "duration_limit": "Stop when the finite configured maximum duration is reached.",
        "request_limit": "Stop when the finite configured GET request budget is reached.",
        "consecutive_error_limit": "Stop after the finite configured count of consecutive read failures.",
        "page_unload": "Stop when the page unloads; no page-local session survives it.",
        "browser_state_destroyed": "Stop when required page-local association or control state is destroyed.",
        "snapshot_id_safety_rejected": "Stop if the existing loader safety validation rejects the snapshot ID.",
        "configuration_disabled": "Stop or refuse to start if the future configuration does not explicitly permit polling.",
    }
    return [{"id": item, "meaning": meanings[item]} for item in REQUIRED_STOP_CONDITIONS]


def _ui_statuses() -> list[dict[str, str]]:
    notices = {
        "disabled": "Temporary progress updates are unavailable because polling is disabled by configuration.",
        "ready": "Temporary read-only progress updates are ready but inactive.",
        "active": "Temporary read-only progress updates are active.",
        "paused_hidden": "Progress updates are paused while this tab is hidden.",
        "stopped_by_operator": "Progress updates were stopped by the operator.",
        "stopped_terminal": "Progress updates stopped because the snapshot reported a terminal state.",
        "stopped_association_changed": "Progress updates stopped because a different run became associated.",
        "stopped_duration_limit": "Progress updates stopped after reaching the configured time limit.",
        "stopped_request_limit": "Progress updates stopped after reaching the configured request limit.",
        "stopped_error_limit": "Progress updates stopped after repeated read failures. No execution action was taken.",
        "stopped_possibly_abandoned": "Progress updates stopped because the nonterminal snapshot has not changed for an extended period. No automatic action was taken.",
        "blocked": "Progress updates cannot start because the current snapshot association was not safe to use.",
        "unavailable": "Progress updates are unavailable because the associated snapshot cannot be loaded.",
    }
    return [{"status": item, "notice": notices[item]} for item in REQUIRED_UI_STATUSES]


def _plan_incomplete_reasons(plan: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    configuration = _as_dict(plan.get("configuration_contract"))
    defaults = _as_dict(configuration.get("proposed_defaults"))
    if plan.get("explicit_operator_activation_required") is not True:
        reasons.append("explicit_operator_activation_missing")
    if not _is_finite_positive(defaults.get("poll_interval_seconds")):
        reasons.append("interval_bound_missing")
    if not _is_finite_positive(defaults.get("maximum_duration_seconds")):
        reasons.append("duration_bound_missing")
    if not _is_finite_positive(defaults.get("maximum_requests")):
        reasons.append("request_bound_missing")
    if not _is_finite_positive(defaults.get("maximum_consecutive_errors")) and defaults.get("maximum_consecutive_errors") != 0:
        reasons.append("error_bound_missing")
    stop_ids = {str(item.get("id")) for item in _as_list(plan.get("stop_conditions")) if isinstance(item, dict)}
    if not set(REQUIRED_STOP_CONDITIONS) <= stop_ids:
        reasons.append("stop_conditions_incomplete")
    if _as_dict(plan.get("terminal_stop_policy")).get("stop_after_render") is not True:
        reasons.append("terminal_stop_missing")
    if _as_dict(plan.get("association_change_policy")).get("stop_old_session") is not True:
        reasons.append("association_change_policy_missing")
    if not _as_dict(plan.get("error_policy")):
        reasons.append("error_policy_missing")
    if not _as_dict(plan.get("hidden_tab_policy")):
        reasons.append("hidden_tab_policy_missing")
    if plan.get("one_request_at_a_time") is not True:
        reasons.append("one_request_at_a_time_missing")
    statuses = {str(item.get("status")) for item in _as_list(plan.get("ui_statuses")) if isinstance(item, dict)}
    if not set(REQUIRED_UI_STATUSES) <= statuses:
        reasons.append("ui_status_taxonomy_missing")
    if _as_dict(plan.get("implementation_boundaries")).get("next_implementation_phase") != "UX.LIVE.10":
        reasons.append("ux_live_10_boundary_missing")
    return reasons


def _plan_blockers(plan: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if plan.get("report_only") is not True:
        blockers.append("report_only_boundary_missing")
    for key in _SAFETY_FALSE_FIELDS:
        if plan.get(key) is not False:
            blockers.append(f"forbidden_behavior_enabled:{key}")
    if _as_list(plan.get("actions_available")):
        blockers.append("actions_available_in_report_only_plan")
    if plan.get("explicit_operator_activation_required") is not True:
        blockers.append("implicit_activation_permitted")
    configuration = _as_dict(plan.get("configuration_contract"))
    defaults = _as_dict(configuration.get("proposed_defaults"))
    for key in ("poll_interval_seconds", "maximum_duration_seconds", "maximum_requests"):
        if not _is_finite_positive(defaults.get(key)):
            blockers.append(f"unbounded_or_invalid:{key}")
    error_limit = defaults.get("maximum_consecutive_errors")
    if not (error_limit == 0 or _is_finite_positive(error_limit)):
        blockers.append("unbounded_or_invalid:maximum_consecutive_errors")
    if plan.get("one_request_at_a_time") is not True:
        blockers.append("overlapping_requests_permitted")
    route = _as_dict(plan.get("route_contract"))
    if route.get("method") != "GET" or route.get("path") != "/ux/run-progress/snapshot/<snapshot_id>":
        blockers.append("route_contract_not_existing_get_loader")
    if route.get("new_backend_route_required") is True:
        blockers.append("new_backend_route_proposed")
    forbidden_dependencies = _as_dict(plan.get("implementation_boundaries")).get("prohibited_future_behavior")
    if not _as_list(forbidden_dependencies):
        blockers.append("implementation_boundary_missing")
    freshness = _as_dict(plan.get("freshness_relationship"))
    if freshness.get("stale_increases_frequency") is True:
        blockers.append("stale_increases_polling_frequency")
    if freshness.get("possibly_abandoned_triggers_runtime_action") is True:
        blockers.append("possibly_abandoned_triggers_runtime_action")
    return _dedupe(blockers)


def _evaluate_plan_status(plan: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    blockers = _plan_blockers(plan)
    incomplete = _plan_incomplete_reasons(plan)
    if blockers:
        return BLOCKED, incomplete, blockers
    if incomplete:
        return INCOMPLETE, incomplete, blockers
    return (READY_WITH_WARNINGS if _as_list(plan.get("warnings")) else READY), incomplete, blockers


def build_run_progress_polling_plan(
    *,
    created_at: str = "",
    safety_context: Any = None,
    plan_overrides: Any = None,
) -> dict[str, Any]:
    """Build the static UX.LIVE.9 contract without starting or configuring polling.

    ``safety_context`` and ``plan_overrides`` are test seams for the plan-status
    evaluator. They do not read environment variables or affect runtime behavior.
    """
    plan: dict[str, Any] = {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "created_at": created_at or _utc_now(),
        **_safety_flags(safety_context),
        "actions_available": [],
        "explicit_operator_activation_required": True,
        "route_contract": {
            "method": "GET",
            "path": "/ux/run-progress/snapshot/<snapshot_id>",
            "reuse_existing_loader_only": True,
            "new_backend_route_required": False,
            "prohibited": [
                "POST polling endpoints", "filesystem path parameters", "long-polling endpoints",
                "SSE endpoints", "WebSockets", "database job-status APIs", "bypass routes", "direct static-file access",
            ],
        },
        "configuration_contract": {
            "names": {
                "enabled": "RUN_PROGRESS_POLLING_ENABLED",
                "poll_interval_seconds": "RUN_PROGRESS_POLL_INTERVAL_SECONDS",
                "maximum_duration_seconds": "RUN_PROGRESS_POLL_MAX_DURATION_SECONDS",
                "maximum_requests": "RUN_PROGRESS_POLL_MAX_REQUESTS",
                "maximum_consecutive_errors": "RUN_PROGRESS_POLL_MAX_CONSECUTIVE_ERRORS",
                "hidden_tab_behavior": "RUN_PROGRESS_POLL_HIDDEN_TAB_BEHAVIOR",
            },
            "proposed_defaults": dict(DEFAULT_POLLING_CONFIGURATION),
            "enabled_by_default": False,
            "operator_activation_still_required": True,
            "configuration_never_starts_polling": True,
            "safe_fallback": "Missing or malformed values fall back to the documented safe proposed defaults.",
            "interval_rules": {
                "finite_and_positive": True,
                "minimum_supported_seconds": 2,
                "maximum_supported_seconds": 60,
                "reject_or_normalize": ["zero", "negative", "non-numeric", "infinite", "below minimum", "above documented maximum"],
                "rapid_one_second_polling_prohibited": True,
            },
            "bounds_rules": {
                "maximum_duration_finite_and_positive": True,
                "maximum_requests_finite_and_positive": True,
                "maximum_consecutive_errors_finite_and_non_negative": True,
            },
            "scope": "Future configuration affects read frequency and stop bounds only; it cannot change execution behavior.",
        },
        "polling_model": {
            "future_sequence": [
                "operator explicitly starts polling",
                "browser validates the current safe snapshot association",
                "browser performs one GET",
                "browser waits for the configured interval",
                "browser performs the next GET only if all continuation conditions remain true",
                "browser stops after a terminal state, safety condition, or maximum duration",
            ],
            "rejected_implicit_triggers": [
                "page load -> automatic polling", "run start -> implicit polling", "snapshot association -> implicit polling",
                "stale result -> faster polling", "possibly abandoned -> automatic retry/restart", "error -> recursive retry loop",
            ],
        },
        "operator_activation": {
            "start_label": "Start bounded progress updates",
            "stop_label": "Stop progress updates",
            "start_requires_safe_associated_snapshot": True,
            "visually_secondary": True,
            "states_temporary_and_read_only": True,
            "prohibited_control_meanings": ["Run", "Apply", "Approve", "Validate", "Restart"],
            "never_enables_snapshot_writer": True,
            "never_creates_or_changes_run": True,
            "stop_only_cancels_scheduled_browser_refresh": True,
            "stop_does_not_cancel_underlying_run": True,
            "stop_does_not_delete_snapshots": True,
            "stop_does_not_change_runtime_or_signal_worker": True,
        },
        "one_request_at_a_time": True,
        "request_concurrency": {
            "maximum_concurrent_polling_requests": 1,
            "no_request_while_previous_in_flight": True,
            "no_request_queue": True,
            "slow_responses_do_not_accumulate": True,
            "next_interval_starts_after_settlement": True,
            "reuse_ux_live_6_request_guard": True,
        },
        "scheduling_model": {
            "kind": "chained_one_shot_timeout",
            "sequence": "request settles -> evaluate continuation conditions -> schedule one next request",
            "fixed_interval_prohibited": True,
            "reason": "A chained one-shot schedule prevents overlapping GET requests.",
            "implemented_now": False,
        },
        "hidden_tab_policy": {
            "configured_default": "pause",
            "on_hidden": "Pause scheduled polling without a catch-up request.",
            "on_visible": "Remain paused until explicit operator resume.",
            "acceptable_less_strict_variant": "Resume only if the original bounded session remains valid.",
            "prohibited": ["increasing request frequency", "catch-up request bursts", "multiple immediate requests", "polling through browser sleep without bounds"],
        },
        "terminal_stop_policy": {
            "terminal_true_stops_polling": True,
            "stop_after_render": True,
            "meaning": "Terminal means only that no more polling is necessary for that snapshot.",
            "does_not_imply": ["successful task completion", "validation success", "benchmark success", "patch approval", "patch application"],
        },
        "association_change_policy": {
            "capture_associated_snapshot_id_each_cycle": True,
            "validate_active_association_match": True,
            "never_render_old_association_as_current": True,
            "stop_old_session": True,
            "new_association_starts_automatically": False,
        },
        "error_policy": {
            "first_error": "Show an advisory warning.",
            "immediate_retry": False,
            "next_attempt": "Wait the normal interval before the next permitted attempt.",
            "increment_consecutive_errors": True,
            "successful_response_resets_consecutive_errors": True,
            "stop_at_configured_consecutive_error_limit": True,
            "new_session_requires_operator_action": True,
            "exponential_backoff_proposed": False,
            "no_retry_may": ["restart execution", "create a snapshot", "change run association", "call an alternate route", "bypass loader safety checks"],
        },
        "freshness_relationship": {
            "advisory_only": True,
            "terminal_stops_polling": True,
            "stale_and_possibly_abandoned_displayed": True,
            "unknown_displayed_with_warnings": True,
            "stale_increases_frequency": False,
            "possibly_abandoned_triggers_runtime_action": False,
            "unknown_triggers_alternate_inspection": False,
            "stale_deletes_snapshots": False,
            "freshness_changes_runtime_behavior": False,
        },
        "possibly_abandoned_policy": {
            "recommended_behavior": "Stop polling and ask the operator to decide.",
            "notice": "This nonterminal snapshot has not been updated for an extended period. Automatic progress updates were stopped. No execution action was taken.",
            "prohibited": ["restart", "cancel", "inspect processes", "launch a worker", "send alerts", "delete artifacts"],
        },
        "unknown_freshness_policy": {
            "unknown_alone_stops_polling": False,
            "display_warning": True,
            "loader_or_classifier_failure_counts_under_error_policy": True,
            "stop_after_error_threshold": True,
            "never_bypass_safety_checks": True,
        },
        "request_budget": {
            "duration_and_request_count_both_apply": True,
            "first_limit_reached_stops_session": True,
            "page_local_state": [
                "pollingStartedAt", "pollingRequestCount", "pollingConsecutiveErrorCount", "pollingInFlight",
                "pollingAssociatedSnapshotId", "pollingSessionToken", "pollingActive",
            ],
            "not_persisted_in": ["localStorage", "cookies", "database", "service workers", "browser notifications", "cross-tab synchronization", "background sync APIs"],
            "session_token": {
                "page_local_random_or_incrementing_only": True,
                "rejects_stale_callbacks_only": True,
                "not_runtime_authority": True,
                "not_persisted": True,
                "not_a_run_identifier": True,
                "does_not_replace_snapshot_association_id": True,
            },
        },
        "manual_refresh_coexistence": {
            "policy": "Starting manual refresh while polling is active stops bounded polling, then performs one manual GET.",
            "shared_get_loader": True,
            "shared_in_flight_guard": True,
            "manual_refresh_changes_duration_or_request_limits": False,
            "reason": "This keeps operator intent explicit and avoids competing request sources.",
        },
        "ui_statuses": _ui_statuses(),
        "stop_conditions": _stop_conditions(),
        "security_boundaries": {
            "server_provided_safe_snapshot_id_only": True,
            "preserve_loader_path_and_safe_slug_validation": True,
            "approved_schema_rendering_only": True,
            "no_filesystem_path_exposure": True,
            "no_raw_prompt_response_credentials_repository_or_temp_names": True,
            "no_arbitrary_user_entered_path": True,
        },
        "accessibility": {
            "real_buttons": True,
            "textual_active_paused_stopped_state": True,
            "accessible_status_region": True,
            "not_color_only": True,
            "keyboard_activation": True,
            "temporary_behavior_clear": True,
            "immediate_manual_stop": True,
        },
        "resource_boundaries": {
            "one_active_polling_session_per_page": True,
            "one_active_request_per_session": True,
            "no_concurrent_old_association_sessions": True,
            "finite_duration": True,
            "finite_request_count": True,
            "minimum_interval": True,
            "hidden_tab_pause": True,
            "terminal_stop": True,
            "error_stop": True,
            "no_unbounded_memory_growth": True,
            "no_accumulating_event_listeners": True,
        },
        "optional_future_metrics": {
            "page_local_only": ["requests attempted", "requests succeeded", "requests failed", "session duration", "stop reason"],
            "not_database_written": True,
            "not_runtime_correctness_evidence": True,
            "does_not_affect_execution": True,
            "not_persisted_after_reload": True,
        },
        "implementation_boundaries": {
            "next_implementation_phase": "UX.LIVE.10",
            "may": [
                "add default-off polling configuration", "add explicit Start/Stop controls", "use a chained bounded timeout",
                "issue GET-only snapshot requests", "reuse freshness rendering", "stop deterministically", "remain page-local and advisory",
            ],
            "may_not": [
                "start polling automatically", "enable the writer", "create snapshots", "alter runtime execution", "add a job system",
                "add WebSocket/SSE", "restart or cancel runs", "invoke models/workers/tools", "apply patches",
                "run validation or benchmarks", "enforce approval", "delete artifacts",
            ],
            "prohibited_future_behavior": [
                "No implicit activation or unbounded background monitoring.",
                "No filesystem paths, database jobs, long polling, SSE, WebSockets, or bypass routes.",
                "No execution, restart, cancellation, writer enablement, snapshot mutation, or runtime authority.",
            ],
        },
        "warnings": [
            "The bounded contract is complete, but no browser polling implementation exists in UX.LIVE.9.",
            "UX.LIVE.10 requires browser dogfooding of association changes, slow reads, hidden tabs, and stop-state accessibility.",
        ],
        "blockers": [],
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }
    plan.update(copy.deepcopy(_as_dict(plan_overrides)))
    status, incomplete, blockers = _evaluate_plan_status(plan)
    plan["plan_status"] = status
    plan["incomplete_reasons"] = incomplete
    plan["blockers"] = blockers
    return plan


def render_run_progress_polling_plan_markdown(plan: Any) -> str:
    """Render the plan artifact without implementing its future browser behavior."""
    report = _as_dict(plan)
    configuration = _as_dict(report.get("configuration_contract"))
    defaults = _as_dict(configuration.get("proposed_defaults"))
    lines = [
        "# Bounded Run Progress Polling Experiment Plan",
        "",
        f"- Phase: `{_md(report.get('phase_id'))}`",
        f"- Status: `{_md(report.get('plan_status'))}`",
        f"- Report only: `{str(report.get('report_only')).lower()}`",
        f"- Polling implemented: `{str(report.get('polling_implemented')).lower()}`",
        "",
        "## Safety Boundary",
        "",
        "This is a contract only. It adds no timer, browser request, background refresh, retry, stream, route, snapshot write, runtime change, or execution authority.",
        "",
        "## Future Activation and Loader Contract",
        "",
        f"- Explicit operator activation required: `{str(report.get('explicit_operator_activation_required')).lower()}`",
        f"- Existing loader only: `{_md(_as_dict(report.get('route_contract')).get('method'))} {_md(_as_dict(report.get('route_contract')).get('path'))}`",
        f"- Start control: `{_md(_as_dict(report.get('operator_activation')).get('start_label'))}`",
        f"- Stop control: `{_md(_as_dict(report.get('operator_activation')).get('stop_label'))}`",
        "",
        "## Proposed Configuration Defaults",
        "",
        "| Setting | Proposed default |",
        "|---|---:|",
    ]
    for key in (
        "enabled", "poll_interval_seconds", "minimum_poll_interval_seconds", "maximum_poll_interval_seconds",
        "maximum_duration_seconds", "maximum_requests", "maximum_consecutive_errors", "hidden_tab_behavior",
    ):
        lines.append(f"| `{_md(key)}` | `{_md(defaults.get(key))}` |")
    lines += ["", "## Scheduling, Budget, and Stop Conditions", ""]
    for key in ("kind", "sequence", "reason"):
        lines.append(f"- {_md(_as_dict(report.get('scheduling_model')).get(key))}")
    for item in _as_list(report.get("stop_conditions")):
        entry = _as_dict(item)
        lines.append(f"- `{_md(entry.get('id'))}`: {_md(entry.get('meaning'))}")
    lines += ["", "## Freshness, Errors, and Manual Refresh", ""]
    lines += [
        f"- {_md(_as_dict(report.get('possibly_abandoned_policy')).get('notice'))}",
        f"- {_md(_as_dict(report.get('manual_refresh_coexistence')).get('policy'))}",
        f"- {_md(_as_dict(report.get('error_policy')).get('next_attempt'))}",
        "",
        "## Future UI Statuses",
        "",
        "| Status | Advisory notice |",
        "|---|---|",
    ]
    for item in _as_list(report.get("ui_statuses")):
        entry = _as_dict(item)
        lines.append(f"| `{_md(entry.get('status'))}` | {_md(entry.get('notice'))} |")
    lines += ["", "## UX.LIVE.10 Boundary", ""]
    for item in _as_list(_as_dict(report.get("implementation_boundaries")).get("may_not")):
        lines.append(f"- Must not: {_md(item)}")
    lines += ["", "## Warnings", ""]
    for warning in _as_list(report.get("warnings")):
        lines.append(f"- {_md(warning)}")
    next_phase = _as_dict(report.get("recommended_next_phase"))
    lines += ["", "## Next Phase", "", f"`{_md(next_phase.get('phase_id'))}` — {_md(next_phase.get('title'))}", ""]
    return "\n".join(lines)


def write_run_progress_polling_plan(plan: Any, output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    """Write JSON and Markdown plan artifacts only when this explicit command is used."""
    report = copy.deepcopy(_as_dict(plan))
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_NAME
    markdown_path = root / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_run_progress_polling_plan_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "markdown_path": str(markdown_path), "report": report}
