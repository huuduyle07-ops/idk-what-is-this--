"""UX.LIVE.CLOSE - report-only live run-progress branch checkpoint.

This module records what UX.LIVE.1 through UX.LIVE.10 already provide.  It
does not inspect a run, load or write a progress snapshot, start polling, or
alter any runtime, browser, configuration, or execution behaviour.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "run_progress_live_branch_checkpoint"
THIS_PHASE_ID = "UX.LIVE.CLOSE"
JSON_NAME = "run_progress_live_branch_checkpoint.json"
MD_NAME = "run_progress_live_branch_checkpoint.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "ux" / "run_progress_live_branch_checkpoint"

FROZEN = "live_run_progress_branch_frozen"
FROZEN_WITH_WARNINGS = "live_run_progress_branch_frozen_with_warnings"
INCOMPLETE = "live_run_progress_branch_incomplete"
BLOCKED = "live_run_progress_branch_blocked"

REQUIRED_PHASE_IDS: tuple[str, ...] = tuple(f"UX.LIVE.{index}" for index in range(1, 11))
OBSERVED_STAGES: tuple[str, ...] = (
    "request_received",
    "model_response_received",
    "final_response_ready",
    "error_reported",
)
UNOBSERVED_STAGES: tuple[str, ...] = (
    "prompt_built",
    "model_call_pending",
    "input_normalized",
    "goal_brief_checked",
    "mode_selected",
    "context_prepared",
    "patch_candidate_detected",
    "evidence_collected",
    "validation_stages",
    "benchmark_stages",
    "approval_stages",
)
RECOMMENDED_NEXT_PHASE = {
    "phase_id": "DOGFOOD.1",
    "title": "Real Operator Run Evaluation",
    "status": "proposed",
    "report_only_initially": True,
    "reason": "The frozen branch needs sustained real-use evidence before another automation branch.",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _phase_inventory() -> list[dict[str, Any]]:
    """Return static evidence inventory, not a runtime or filesystem audit."""
    rows = (
        ("UX.LIVE.1", "Run Progress Instrumentation Plan", "plan_only", ["core/run_progress_instrumentation_plan.py"], "tests/test_run_progress_visibility.py", False, False, True, ["plan_only", "partial_stage_coverage"]),
        ("UX.LIVE.2", "Snapshot Writer Plan", "plan_only", ["core/run_progress_snapshot_writer_plan.py"], "tests/test_run_progress_snapshot_writer_plan.py", False, False, True, ["plan_only", "writer_default_off"]),
        ("UX.LIVE.3", "Default-Off Terminal Shadow Writer", "implementation", ["core/run_progress_snapshot_shadow_writer.py", "web/runner.py"], "tests/test_run_progress_snapshot_shadow_writer.py", True, False, True, ["terminal_boundary_only", "partial_stage_coverage"]),
        ("UX.LIVE.4", "Truthful Multi-Stage Shadow Instrumentation", "implementation", ["core/run_progress_snapshot_shadow_writer.py", "web/runner.py"], "tests/test_run_progress_multistage_shadow_instrumentation.py", True, False, True, ["observed_stage_coverage_is_deliberately_narrow"]),
        ("UX.LIVE.5", "Current Run Snapshot Association", "implementation", ["web/runner.py", "web/templates/index.html"], "tests/test_current_run_snapshot_association.py", False, True, True, ["association_available_after_result_boundary"]),
        ("UX.LIVE.6", "Manual Progress Refresh", "implementation", ["web/templates/index.html", "web/static/style.css"], "tests/test_manual_run_progress_refresh.py", False, True, True, ["manual_refresh_only"]),
        ("UX.LIVE.7", "Freshness/Staleness Plan", "plan_only", ["core/run_progress_freshness_plan.py"], "tests/test_run_progress_freshness_plan.py", False, False, True, ["plan_only"]),
        ("UX.LIVE.8", "Freshness Classification", "implementation", ["core/run_progress_freshness.py", "core/run_progress_snapshot_loader.py", "web/templates/index.html"], "tests/test_run_progress_freshness.py", False, True, True, ["freshness_evaluated_at_load_time"]),
        ("UX.LIVE.9", "Bounded Polling Plan", "plan_only", ["core/run_progress_polling_plan.py"], "tests/test_run_progress_polling_plan.py", False, False, True, ["plan_only", "polling_not_implemented_in_phase"]),
        ("UX.LIVE.10", "Optional Default-Off Bounded Progress Polling", "implementation", ["web/app.py", "web/templates/index.html", "web/static/style.css"], "tests/test_bounded_run_progress_polling.py", False, True, True, ["polling_default_off", "experimental_polling_ui", "operator_dogfood_pending"]),
    )
    inventory: list[dict[str, Any]] = []
    for phase_id, title, category, files, test_file, runtime_changed, ui_changed, default_off, warnings in rows:
        inventory.append({
            "phase_id": phase_id,
            "title": title,
            "completion_status": "complete",
            "category": category,
            "primary_files": files,
            "runtime_behavior_changed": runtime_changed,
            "ui_behavior_changed": ui_changed,
            "default_off": default_off,
            "authority": {"runtime_authority": False, "action_triggered": False, "actions_available": []},
            "known_warnings": warnings,
            "evidence_references": [f"docs/roadmap/phase_registry.json#{phase_id}", test_file],
        })
    return inventory


def _all_true(section: Any, keys: tuple[str, ...]) -> bool:
    values = _as_dict(section)
    return all(values.get(key) is True for key in keys)


def _blockers(report: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if report.get("report_only") is not True:
        blockers.append("report_only_boundary_missing")
    if report.get("branch_frozen") is not True:
        blockers.append("branch_not_frozen")
    authority = _as_dict(report.get("authority_audit"))
    for key in (
        "runtime_authority", "action_triggered", "progress_controls_execution",
        "progress_alters_main_run_behavior",
        "progress_controls_model_selection", "progress_controls_worker_launch",
        "progress_controls_patch_apply", "progress_controls_validation",
        "progress_controls_benchmarks", "progress_controls_approval",
    ):
        if authority.get(key) is not False:
            blockers.append(f"authority_or_action_enabled:{key}")
    if _as_list(authority.get("actions_available")):
        blockers.append("progress_actions_available")
    configuration = _as_dict(report.get("configuration_audit"))
    for key in ("writer_enabled_by_default", "polling_enabled_by_default", "polling_started_by_default"):
        if configuration.get(key) is not False:
            blockers.append(f"unsafe_default:{key}")
    writer = _as_dict(report.get("writer_safety_audit"))
    for key in ("failure_isolated", "no_main_result_mutation", "no_sensitive_raw_content", "no_filesystem_path_exposure"):
        if writer.get(key) is not True:
            blockers.append(f"writer_safety_missing:{key}")
    polling = _as_dict(report.get("polling_audit"))
    for key in ("one_request_in_flight", "finite_duration", "finite_request_budget", "finite_consecutive_error_budget", "terminal_stop", "association_change_stop", "stale_callback_rejection"):
        if polling.get(key) is not True:
            blockers.append(f"polling_safety_missing:{key}")
    for key in ("set_interval", "automatic_polling", "websocket", "sse", "long_polling"):
        if polling.get(key) is not False:
            blockers.append(f"polling_forbidden_behavior:{key}")
    return list(dict.fromkeys(blockers))


def _incomplete_reasons(report: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    inventory = _as_list(report.get("phase_inventory"))
    by_id = {str(item.get("phase_id")): item for item in inventory if isinstance(item, dict)}
    if set(by_id) != set(REQUIRED_PHASE_IDS):
        reasons.append("phase_inventory_incomplete")
    else:
        for phase_id in REQUIRED_PHASE_IDS:
            phase = _as_dict(by_id[phase_id])
            if phase.get("completion_status") != "complete":
                reasons.append("phase_inventory_not_complete")
                break
            if (
                not isinstance(phase.get("title"), str)
                or phase.get("category") not in {"implementation", "plan_only"}
                or not _as_list(phase.get("primary_files"))
                or not isinstance(phase.get("runtime_behavior_changed"), bool)
                or not isinstance(phase.get("ui_behavior_changed"), bool)
                or not isinstance(phase.get("default_off"), bool)
                or not _as_list(phase.get("known_warnings"))
                or not _as_list(phase.get("evidence_references"))
            ):
                reasons.append(f"phase_inventory_evidence_incomplete:{phase_id}")
                break
            phase_authority = _as_dict(phase.get("authority"))
            if (
                phase_authority.get("runtime_authority") is not False
                or phase_authority.get("action_triggered") is not False
                or _as_list(phase_authority.get("actions_available"))
            ):
                reasons.append(f"phase_inventory_authority_incomplete:{phase_id}")
                break
    if set(_as_list(report.get("truthful_observed_stages"))) != set(OBSERVED_STAGES):
        reasons.append("truthful_observed_stages_incomplete")
    if not set(UNOBSERVED_STAGES) <= set(_as_list(report.get("intentionally_unobserved_stages"))):
        reasons.append("intentionally_unobserved_stages_incomplete")
    required_audits = {
        "configuration_audit": ("missing_flags_disabled", "writer_permission_does_not_enable_polling", "polling_requires_explicit_operator_activation", "disabled_writer_creates_no_snapshot_root", "no_writer_enable_ui", "no_automatic_polling"),
        "writer_safety_audit": ("safe_slug_run_ids", "allowed_root_enforced", "atomic_same_directory_writes", "temporary_file_cleanup", "failure_isolated", "no_database_fallback", "no_network_fallback", "no_main_result_mutation", "sensitive_metadata_filtered", "no_sensitive_raw_content", "no_raw_prompt_response_patch_storage"),
        "loader_safety_audit": ("get_only", "traversal_protected", "approved_schema_only", "no_filesystem_path_exposure", "bad_artifact_visible", "does_not_mutate_snapshot", "freshness_derived_separately"),
        "freshness_audit": ("deterministic", "injectable_observation_time", "timezone_aware_utc", "terminal_precedence", "safe_unknown_fallback", "stale_is_not_failure", "possibly_abandoned_no_action", "load_or_refresh_only", "no_canonical_snapshot_mutation"),
        "polling_audit": ("default_off", "explicit_start_stop", "existing_get_only", "one_request_in_flight", "no_set_interval", "finite_duration", "finite_request_budget", "finite_consecutive_error_budget", "hidden_tab_pause", "no_catch_up_burst", "terminal_stop", "association_change_stop", "stale_callback_rejection", "possibly_abandoned_stop_no_action", "page_local_only", "no_persistent_or_push_transport", "no_local_storage", "no_cookies", "no_database", "no_service_worker", "no_websocket", "no_sse", "no_long_polling"),
    }
    for field, keys in required_audits.items():
        if not _all_true(report.get(field), keys):
            reasons.append(f"{field}_incomplete")
    if not _as_list(report.get("known_limitations")):
        reasons.append("known_limitations_missing")
    if not _as_dict(report.get("validation_summary")):
        reasons.append("validation_summary_missing")
    next_phase = _as_dict(report.get("recommended_next_phase"))
    if next_phase.get("phase_id") != "DOGFOOD.1" or next_phase.get("status") != "proposed":
        reasons.append("recommended_next_phase_missing")
    return reasons


def _status(report: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    blockers = _blockers(report)
    incomplete = _incomplete_reasons(report)
    if blockers:
        return BLOCKED, incomplete, blockers
    if incomplete:
        return INCOMPLETE, incomplete, blockers
    return (FROZEN_WITH_WARNINGS if _as_list(report.get("warnings")) else FROZEN), incomplete, blockers


def build_run_progress_live_branch_checkpoint(*, created_at: str = "", checkpoint_overrides: Any = None) -> dict[str, Any]:
    """Build a static branch checkpoint without reading or changing live state."""
    report: dict[str, Any] = {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "created_at": created_at or _utc_now(),
        "report_only": True,
        "checkpoint_status": FROZEN_WITH_WARNINGS,
        "branch_frozen": True,
        "phase_inventory": _phase_inventory(),
        "delivered_capabilities": [
            "Default-off progress artifact writing.", "One stable safe run ID per enabled execution.",
            "Truthful observed stages: request_received, model_response_received, final_response_ready, and error_reported.",
            "Atomic canonical snapshot updates and safe loader-compatible JSON.",
            "Current-run snapshot association and manual GET-only refresh.",
            "Derived advisory freshness classification.",
            "Explicit optional bounded polling with terminal, association-change, hidden-tab, duration, request, and error stops.",
        ],
        "truthfulness_statement": "The branch provides truthful partial progress visibility, not complete runtime tracing.",
        "truthful_observed_stages": list(OBSERVED_STAGES),
        "intentionally_unobserved_stages": list(UNOBSERVED_STAGES),
        "configuration_audit": {
            "RUN_PROGRESS_SHADOW_WRITER_ENABLED": False, "RUN_PROGRESS_POLLING_ENABLED": False,
            "writer_enabled_by_default": False, "polling_enabled_by_default": False, "polling_started_by_default": False,
            "missing_flags_disabled": True, "writer_permission_does_not_enable_polling": True,
            "polling_permission_does_not_start_polling": True, "polling_requires_explicit_operator_activation": True,
            "disabled_writer_creates_no_snapshot_root": True, "no_writer_enable_ui": True,
            "no_automatic_polling": True, "no_page_load_polling": True,
            "no_run_start_polling": True, "no_association_polling": True,
            "no_completion_polling": True,
        },
        "writer_safety_audit": {
            "safe_slug_run_ids": True, "allowed_root_enforced": True, "no_arbitrary_output_path": True,
            "atomic_same_directory_writes": True, "temporary_file_cleanup": True, "failure_isolated": True,
            "no_database_fallback": True, "no_network_fallback": True, "no_main_result_mutation": True,
            "sensitive_metadata_filtered": True, "no_sensitive_raw_content": True,
            "no_raw_prompt_response_patch_storage": True, "no_filesystem_path_exposure": True,
        },
        "loader_safety_audit": {
            "get_only": True, "traversal_protected": True, "approved_schema_only": True,
            "no_filesystem_path_exposure": True, "bad_artifact_visible": True,
            "does_not_mutate_snapshot": True, "freshness_derived_separately": True,
        },
        "freshness_audit": {
            "deterministic": True, "injectable_observation_time": True, "timezone_aware_utc": True,
            "terminal_precedence": True, "safe_unknown_fallback": True, "stale_is_not_failure": True,
            "possibly_abandoned_no_action": True, "load_or_refresh_only": True,
            "no_canonical_snapshot_mutation": True,
        },
        "polling_audit": {
            "default_off": True, "explicit_start_stop": True, "existing_get_only": True,
            "one_request_in_flight": True, "no_set_interval": True, "finite_duration": True,
            "finite_request_budget": True, "finite_consecutive_error_budget": True, "hidden_tab_pause": True,
            "no_catch_up_burst": True, "terminal_stop": True, "association_change_stop": True,
            "stale_callback_rejection": True, "possibly_abandoned_stop_no_action": True,
            "page_local_only": True, "no_persistent_or_push_transport": True,
            "no_local_storage": True, "no_cookies": True, "no_database": True,
            "no_service_worker": True, "no_websocket": True, "no_sse": True,
            "no_long_polling": True,
            "set_interval": False, "automatic_polling": False, "websocket": False, "sse": False, "long_polling": False,
        },
        "authority_audit": {
            "runtime_authority": False, "action_triggered": False, "actions_available": [],
            "progress_alters_main_run_behavior": False,
            "progress_controls_execution": False, "progress_controls_model_selection": False,
            "progress_controls_worker_launch": False, "progress_controls_patch_apply": False,
            "progress_controls_validation": False, "progress_controls_benchmarks": False,
            "progress_controls_approval": False,
        },
        "known_limitations": [
            "Progress writing remains disabled by default.", "Polling remains disabled by default.",
            "Progress stage coverage is partial.", "Association normally becomes available through the existing web result path.",
            "No durable browser polling session survives page reload and no cross-tab association exists.",
            "No background or server-side monitoring, WebSocket/SSE, process-health inspection, or database job state exists.",
            "No automatic repair, retry, restart, or cancellation exists.", "Freshness age is derived at load time.",
            "Real multi-minute operator dogfooding is limited; repeated-run performance and usability remain unproven.",
        ],
        "warnings": [
            "progress_writer_default_off", "polling_default_off", "partial_stage_coverage", "operator_dogfood_pending",
            "no_server_push", "no_durable_polling_session", "association_available_after_result_boundary",
            "freshness_evaluated_at_load_time", "experimental_polling_ui", "full_suite_not_required_for_checkpoint",
        ],
        "blockers": [],
        "validation_summary": {
            "report_only": True,
            "scoped_checks": ["checkpoint unit test", "polling and plan tests", "freshness tests", "association and refresh tests", "writer and instrumentation tests", "loader and UI tests", "registry and picker tests", "registry validator", "phase picker", "benchmark check"],
            "full_pytest_required": False,
        },
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }
    report.update(copy.deepcopy(_as_dict(checkpoint_overrides)))
    checkpoint_status, incomplete, blockers = _status(report)
    report["checkpoint_status"] = checkpoint_status
    report["incomplete_reasons"] = incomplete
    report["blockers"] = blockers
    return report


def render_run_progress_live_branch_checkpoint_markdown(checkpoint: Any) -> str:
    """Render the checkpoint as a static Markdown artifact."""
    report = _as_dict(checkpoint)
    lines = [
        "# Live Run Progress Branch Checkpoint", "",
        f"- Phase: `{_md(report.get('phase_id'))}`", f"- Status: `{_md(report.get('checkpoint_status'))}`",
        f"- Branch frozen: `{str(report.get('branch_frozen')).lower()}`", "",
        "## Truthfulness Boundary", "", _md(report.get("truthfulness_statement")), "",
        "Observed stages:", *[f"- `{_md(stage)}`" for stage in _as_list(report.get("truthful_observed_stages"))], "",
        "Not claimed unless genuinely observed:", *[f"- `{_md(stage)}`" for stage in _as_list(report.get("intentionally_unobserved_stages"))], "",
        "## Phase Inventory", "", "| Phase | Status | Category | Runtime changed | UI changed | Default off |", "|---|---|---|---:|---:|---:|",
    ]
    for item in _as_list(report.get("phase_inventory")):
        phase = _as_dict(item)
        lines.append("| `{}` | `{}` | `{}` | `{}` | `{}` | `{}` |".format(
            _md(phase.get("phase_id")), _md(phase.get("completion_status")), _md(phase.get("category")),
            str(phase.get("runtime_behavior_changed")).lower(), str(phase.get("ui_behavior_changed")).lower(), str(phase.get("default_off")).lower(),
        ))
    lines += ["", "## Configuration and Authority", ""]
    for name in ("RUN_PROGRESS_SHADOW_WRITER_ENABLED", "RUN_PROGRESS_POLLING_ENABLED"):
        lines.append(f"- `{name}=false`: `{str(_as_dict(report.get('configuration_audit')).get(name) is False).lower()}`")
    authority = _as_dict(report.get("authority_audit"))
    lines += [
        f"- Runtime authority: `{str(authority.get('runtime_authority')).lower()}`",
        f"- Action triggered: `{str(authority.get('action_triggered')).lower()}`",
        f"- Actions available: `{_md(authority.get('actions_available'))}`", "",
        "## Delivered Capability", "",
        *[f"- {_md(item)}" for item in _as_list(report.get("delivered_capabilities"))], "",
        "## Known Limitations and Warnings", "",
        *[f"- {_md(item)}" for item in _as_list(report.get("known_limitations"))], "",
        *[f"- Warning: `{_md(item)}`" for item in _as_list(report.get("warnings"))], "",
        "## Next Phase", "",
        f"`{_md(_as_dict(report.get('recommended_next_phase')).get('phase_id'))}` — {_md(_as_dict(report.get('recommended_next_phase')).get('title'))}", "",
    ]
    return "\n".join(lines)


def write_run_progress_live_branch_checkpoint(checkpoint: Any, output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    """Write only the explicit checkpoint artifacts."""
    report = copy.deepcopy(_as_dict(checkpoint))
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_NAME
    markdown_path = root / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_run_progress_live_branch_checkpoint_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "markdown_path": str(markdown_path), "report": report}
