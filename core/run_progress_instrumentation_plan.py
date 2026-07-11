"""UX.LIVE.1 - Run Progress Instrumentation Plan.

This module only describes where a later, explicitly approved progress writer
*could* observe an existing run.  It deliberately does not insert a hook,
start polling or streaming, mutate runtime state, or call any execution path.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "run_progress_instrumentation_plan"
THIS_PHASE_ID = "UX.LIVE.1"

JSON_NAME = "run_progress_instrumentation_plan.json"
MD_NAME = "run_progress_instrumentation_plan.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "ux" / "run_progress_instrumentation_plan"
DEFAULT_REGISTRY_PATH = Path("docs") / "roadmap" / "phase_registry.json"
DEFAULT_VISIBILITY_REPORT_PATH = (
    Path(".agent") / "ux" / "run_progress_visibility" / "run_progress_visibility_report.json"
)
DEFAULT_SNAPSHOT_LOADER_REPORT_PATH = (
    Path(".agent") / "ux" / "run_progress_snapshot_loader" / "run_progress_snapshot_loader_report.json"
)
DEFAULT_BRANCH_CHECKPOINT_PATH = (
    Path(".agent")
    / "ux"
    / "run_progress_visibility_branch_checkpoint"
    / "run_progress_visibility_branch_checkpoint.json"
)
DEFAULT_RUNNER_SOURCE_PATH = Path("web") / "runner.py"
DEFAULT_APP_SOURCE_PATH = Path("web") / "app.py"

READY = "run_progress_instrumentation_plan_ready"
READY_WITH_WARNINGS = "run_progress_instrumentation_plan_ready_with_warnings"
INCOMPLETE = "run_progress_instrumentation_plan_incomplete"
BLOCKED = "run_progress_instrumentation_plan_blocked"

REQUIRED_STAGE_IDS: tuple[str, ...] = (
    "request_received",
    "input_normalized",
    "goal_brief_checked",
    "mode_selected",
    "context_prepared",
    "prompt_built",
    "model_call_pending",
    "model_response_received",
    "patch_candidate_detected",
    "evidence_collected",
    "validation_not_run",
    "validation_started",
    "validation_finished",
    "benchmark_not_run",
    "benchmark_started",
    "benchmark_finished",
    "approval_boundary_checked",
    "final_response_ready",
    "error_reported",
)

REQUIRED_ATTACHMENT_POINT_FIELDS: tuple[str, ...] = (
    "stage_id",
    "label",
    "proposed_source_file",
    "proposed_function_or_boundary",
    "event_payload_fields",
    "event_storage_target",
    "operator_visibility",
    "live_stream_candidate",
    "polling_candidate",
    "snapshot_candidate",
    "risk_level",
    "implementation_not_before_phase",
    "enforcement_allowed_now",
    "emits_runtime_authority",
    "may_trigger_action",
    "may_block_action",
    "notes",
)
# Kept as a concise alias for consumers that mirror the UX.RUN contract names.
REQUIRED_ATTACHMENT_FIELDS = REQUIRED_ATTACHMENT_POINT_FIELDS

EVENT_PAYLOAD_FIELDS: tuple[str, ...] = (
    "run_id",
    "stage_id",
    "stage_status",
    "message",
    "timestamp",
    "source_component",
    "artifact_refs",
    "warnings",
    "errors",
    "simulated_only",
    "runtime_authority",
    "action_triggered",
)

STORAGE_OPTION_IDS: tuple[str, ...] = (
    "snapshot_file",
    "in_memory_session_state",
    "event_log_file",
    "database_event_table",
    "websocket_stream",
)

REQUIRED_PREVIOUS_PHASES: tuple[str, ...] = (
    "UX.RUN.1",
    "UX.RUN.2",
    "UX.RUN.3",
    "UX.RUN.CLOSE",
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "UX.LIVE.2",
    "title": "Run Progress Snapshot Writer Plan",
    "reason": (
        "Plan a future shadow-mode snapshot writer before any runtime hook, "
        "automatic refresh, polling, or streaming is considered."
    ),
}

GUARDRAIL_NOTE = (
    "UX.LIVE.1 is report-only and plan-only. It identifies future observation "
    "boundaries without inserting hooks, making progress live, changing runtime "
    "behavior, or granting authority."
)

GUARDRAILS: tuple[str, ...] = (
    "report-only",
    "plan only",
    "no live instrumentation",
    "no polling",
    "no streaming",
    "no runtime hook insertion",
    "no model call or routing",
    "no worker launch",
    "no patch apply",
    "no validation run",
    "no benchmark run",
    "no MCP/tool invocation",
    "no approval enforcement",
    "no token issuance or consumption",
    "no database write",
    "no network",
    "no auth behavior change",
    "no automatic authority escalation",
    "no action-triggering UI controls",
)

_FORBIDDEN_NOW_FLAGS: dict[str, str] = {
    "live_hooks_allowed_now": "live hooks are allowed now",
    "polling_allowed_now": "polling is allowed now",
    "streaming_allowed_now": "streaming is allowed now",
    "runtime_mutation_allowed_now": "runtime mutation is allowed now",
    "model_call_allowed_now": "a progress event may call a model",
    "worker_launch_allowed_now": "a progress event may launch a worker",
    "patch_apply_allowed_now": "a progress event may apply a patch",
    "validation_execution_allowed_now": "a progress event may run validation",
    "benchmark_execution_allowed_now": "a progress event may run a benchmark",
    "approval_enforcement_allowed_now": "a progress event may enforce approval",
    "action_triggering_events_allowed_now": "a progress event may trigger an action",
    "progress_as_authority_allowed_now": "progress is treated as runtime authority",
}

_CONTEXT_ALIASES: dict[str, str] = {
    "live_instrumentation_added": "live_hooks_allowed_now",
    "polling_added": "polling_allowed_now",
    "streaming_added": "streaming_allowed_now",
    "runtime_behavior_changed": "runtime_mutation_allowed_now",
    "model_call_performed": "model_call_allowed_now",
    "worker_launch_performed": "worker_launch_allowed_now",
    "patch_apply_performed": "patch_apply_allowed_now",
    "validation_run_performed": "validation_execution_allowed_now",
    "benchmark_run_performed": "benchmark_execution_allowed_now",
    "approval_enforcement_changed": "approval_enforcement_allowed_now",
    "action_triggering_controls_added": "action_triggering_events_allowed_now",
    "progress_treated_as_authority": "progress_as_authority_allowed_now",
}

_ATTACHMENT_BLUEPRINTS: tuple[dict[str, str], ...] = (
    {"stage_id": "request_received", "label": "Request received", "source": "web/app.py", "boundary": "existing request route to web.runner.run_agent_web handoff", "risk": "low", "notes": "Observe only after the existing request path has accepted input; do not add a route or alter request handling."},
    {"stage_id": "input_normalized", "label": "Input normalized", "source": "web/runner.py", "boundary": "run_agent_web input-mode, language, and task-info preparation", "risk": "low", "notes": "Describe normalized input only; no input rewrite or execution decision is authorized."},
    {"stage_id": "goal_brief_checked", "label": "Goal brief checked", "source": "web/app.py", "boundary": "existing goal-brief/request-state handoff", "risk": "low", "notes": "The signal means available brief context was inspected, not that a goal is approved."},
    {"stage_id": "mode_selected", "label": "Mode selected", "source": "web/runner.py", "boundary": "run_agent_web agent_mode normalization", "risk": "low", "notes": "Observe the existing selected mode; the event must not select or reroute a mode."},
    {"stage_id": "context_prepared", "label": "Context prepared", "source": "web/runner.py", "boundary": "run_agent_web existing control/context preparation boundary", "risk": "medium", "notes": "Context availability is descriptive and must not imply grounding, approval, or success."},
    {"stage_id": "prompt_built", "label": "Prompt built", "source": "web/runner.py", "boundary": "run_draft_pipeline preparation boundary", "risk": "medium", "notes": "A future hook may observe that an existing prompt/work packet is ready; it must not construct or send one."},
    {"stage_id": "model_call_pending", "label": "Model call pending", "source": "web/runner.py", "boundary": "run_draft_pipeline model-call boundary", "risk": "high", "notes": "This planned event must not trigger, retry, route, or authorize a model call."},
    {"stage_id": "model_response_received", "label": "Model response received", "source": "web/runner.py", "boundary": "run_draft_pipeline return before review processing", "risk": "high", "notes": "A response is not proof of correctness, validation, or patch safety."},
    {"stage_id": "patch_candidate_detected", "label": "Patch candidate detected", "source": "web/runner.py", "boundary": "state.json_block candidate/result boundary", "risk": "high", "notes": "A candidate remains subject to the existing human and harness boundaries; no apply action is implied."},
    {"stage_id": "evidence_collected", "label": "Evidence collected", "source": "web/runner.py", "boundary": "result/evidence assembly boundary", "risk": "medium", "notes": "Surface artifact references only; do not validate, rank, or convert evidence into authority."},
    {"stage_id": "validation_not_run", "label": "Validation not run", "source": "web/runner.py", "boundary": "existing validation-output absence boundary", "risk": "low", "notes": "Explicitly preserve not-run as distinct from started, finished, or passed."},
    {"stage_id": "validation_started", "label": "Validation started", "source": "web/runner.py", "boundary": "future observation point around an already-authorized validation boundary", "risk": "high", "notes": "This planned event must never start validation and must remain distinct from validation_passed."},
    {"stage_id": "validation_finished", "label": "Validation finished", "source": "web/runner.py", "boundary": "future observation point after an already-completed validation boundary", "risk": "high", "notes": "Finished records completion only; it is distinct from validation_passed and carries errors visibly."},
    {"stage_id": "benchmark_not_run", "label": "Benchmark not run", "source": "web/runner.py", "boundary": "existing benchmark-artifact absence boundary", "risk": "low", "notes": "Explicitly preserve not-run as distinct from started, finished, or passed."},
    {"stage_id": "benchmark_started", "label": "Benchmark started", "source": "web/runner.py", "boundary": "future observation point around an already-authorized benchmark boundary", "risk": "high", "notes": "This planned event must never start a benchmark and must remain distinct from benchmark_passed."},
    {"stage_id": "benchmark_finished", "label": "Benchmark finished", "source": "web/runner.py", "boundary": "future observation point after an already-completed benchmark boundary", "risk": "high", "notes": "Finished records completion only; it is distinct from benchmark_passed and carries errors visibly."},
    {"stage_id": "approval_boundary_checked", "label": "Approval boundary checked", "source": "web/runner.py", "boundary": "existing harness/human review decision boundary", "risk": "high", "notes": "Observation must not enforce approval, issue or consume a token, approve an action, or block an action."},
    {"stage_id": "final_response_ready", "label": "Final response ready", "source": "web/runner.py", "boundary": "run_agent_web final result assembly", "risk": "medium", "notes": "A final response is ready for review only; it does not imply success or operator acceptance."},
    {"stage_id": "error_reported", "label": "Error reported", "source": "web/runner.py", "boundary": "run_agent_web error return boundaries", "risk": "medium", "notes": "Errors must remain visible in a future snapshot and must not be replaced by a generic progress state."},
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _norm_path(value: str | Path | None) -> str:
    return str(value or "").replace("\\", "/")


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _bool(value: Any) -> str:
    return "true" if bool(value) else "false"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def _add_reason(reasons: list[dict[str, str]], reason: str, message: str) -> None:
    if not any(item.get("reason") == reason for item in reasons):
        reasons.append({"reason": reason, "message": message})


def _default_attachment_points() -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for blueprint in _ATTACHMENT_BLUEPRINTS:
        points.append(
            {
                "stage_id": blueprint["stage_id"],
                "label": blueprint["label"],
                "proposed_source_file": blueprint["source"],
                "proposed_function_or_boundary": blueprint["boundary"],
                "event_payload_fields": list(EVENT_PAYLOAD_FIELDS),
                "event_storage_target": "snapshot_file (future controlled writer only)",
                "operator_visibility": "Existing UX.RUN.3 read-only snapshot panel after an operator-selected GET.",
                "live_stream_candidate": "future_only:websocket_stream; not authorized by UX.LIVE.1",
                "polling_candidate": "future_only:manual read-only refresh before any automatic polling",
                "snapshot_candidate": "future_only:controlled snapshot_file writer in shadow mode",
                "risk_level": blueprint["risk"],
                "implementation_not_before_phase": "UX.LIVE.2",
                "enforcement_allowed_now": False,
                "emits_runtime_authority": False,
                "may_trigger_action": False,
                "may_block_action": False,
                "notes": blueprint["notes"],
            }
        )
    return points


def _apply_attachment_overrides(
    points: list[dict[str, Any]], overrides: dict[str, dict[str, Any]] | None
) -> list[dict[str, Any]]:
    if not overrides:
        return points
    updated: list[dict[str, Any]] = []
    known: set[str] = set()
    for point in points:
        next_point = dict(point)
        stage_id = str(point.get("stage_id", ""))
        known.add(stage_id)
        if isinstance(overrides.get(stage_id), dict):
            next_point.update(overrides[stage_id])
        updated.append(next_point)
    for stage_id, override in overrides.items():
        if stage_id not in known and isinstance(override, dict):
            next_point = {"stage_id": str(stage_id)}
            next_point.update(override)
            updated.append(next_point)
    return updated


def _planning_boundary(safety_context: dict[str, Any] | None) -> dict[str, bool]:
    values = {key: False for key in _FORBIDDEN_NOW_FLAGS}
    for key, value in _as_dict(safety_context).items():
        target = _CONTEXT_ALIASES.get(key, key)
        if target in values:
            values[target] = bool(value)
    return values


def _source_record(
    *,
    source_id: str,
    path: str | Path,
    value: Any,
    load_error: str,
    expected_kind: str,
) -> dict[str, Any]:
    provided = value is not None
    record = {
        "source_id": source_id,
        "path": _norm_path(path),
        "expected_kind": expected_kind,
        "provided": provided,
        "load_error": str(load_error or ""),
        "read_status": "loaded" if provided and not load_error else ("missing_or_unreadable" if load_error else "reference_only"),
    }
    if isinstance(value, dict):
        record["report_kind"] = str(value.get("report_kind", ""))
        record["status"] = str(value.get("status") or value.get("checkpoint_status") or "")
    return record


def _evaluate_sources(
    *,
    registry_path: str | Path,
    visibility_path: str | Path,
    snapshot_loader_path: str | Path,
    branch_checkpoint_path: str | Path,
    registry_data: Any,
    registry_load_error: str,
    visibility_report: Any,
    visibility_load_error: str,
    snapshot_loader_report: Any,
    snapshot_loader_load_error: str,
    branch_checkpoint: Any,
    branch_checkpoint_load_error: str,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]]]:
    records = [
        _source_record(source_id="phase_registry", path=registry_path, value=registry_data, load_error=registry_load_error, expected_kind="phase_registry"),
        _source_record(source_id="ux_run_1_visibility_report", path=visibility_path, value=visibility_report, load_error=visibility_load_error, expected_kind="run_progress_visibility"),
        _source_record(source_id="ux_run_2_snapshot_loader_report", path=snapshot_loader_path, value=snapshot_loader_report, load_error=snapshot_loader_load_error, expected_kind="run_progress_snapshot_loader"),
        _source_record(source_id="ux_run_close_checkpoint", path=branch_checkpoint_path, value=branch_checkpoint, load_error=branch_checkpoint_load_error, expected_kind="run_progress_visibility_branch_checkpoint"),
    ]
    incomplete: list[str] = []
    blocked: list[dict[str, str]] = []
    for record in records:
        if record["load_error"]:
            incomplete.append(f"Required source {record['source_id']} could not be loaded: {record['load_error']}")

    if registry_data is not None:
        phases = {
            str(item.get("phase_id")): item
            for item in _as_list(_as_dict(registry_data).get("phases"))
            if isinstance(item, dict) and item.get("phase_id")
        }
        for phase_id in REQUIRED_PREVIOUS_PHASES:
            if str(_as_dict(phases.get(phase_id)).get("status", "")) != "complete":
                incomplete.append(f"Required prior phase is not complete: {phase_id}")
    if visibility_report is not None:
        report = _as_dict(visibility_report)
        if report.get("report_kind") != "run_progress_visibility":
            incomplete.append("UX.RUN.1 source is not a run_progress_visibility report")
        if not _as_list(report.get("stage_contract")):
            incomplete.append("UX.RUN.1 source has no progress stage contract")
    if snapshot_loader_report is not None:
        report = _as_dict(snapshot_loader_report)
        if report.get("report_kind") != "run_progress_snapshot_loader":
            incomplete.append("UX.RUN.2 source is not a run_progress_snapshot_loader report")
        if report.get("blocked_reasons"):
            _add_reason(blocked, "source_snapshot_loader_blocked", "UX.RUN.2 source already reports blocked reasons.")
    if branch_checkpoint is not None:
        report = _as_dict(branch_checkpoint)
        if report.get("report_kind") != "run_progress_visibility_branch_checkpoint":
            incomplete.append("UX.RUN.CLOSE source is not a branch checkpoint report")
        if report.get("checkpoint_status") not in {
            "run_progress_visibility_branch_frozen",
            "run_progress_visibility_branch_frozen_with_warnings",
        }:
            incomplete.append("UX.RUN.CLOSE source does not show a frozen read-only branch")
    return records, _dedupe(incomplete), blocked


def _static_source_summary(
    *, runner_source: str | None, runner_load_error: str, app_source: str | None, app_load_error: str
) -> tuple[dict[str, Any], list[str]]:
    runner_text = str(runner_source or "")
    app_text = str(app_source or "")
    summary = {
        "optional_static_inspection_only": True,
        "runner_source_loaded": bool(runner_text) and not bool(runner_load_error),
        "app_source_loaded": bool(app_text) and not bool(app_load_error),
        "run_agent_web_marker_found": "def run_agent_web" in runner_text,
        "draft_pipeline_marker_found": "run_draft_pipeline(" in runner_text,
        "review_pipeline_marker_found": "run_review_pipeline(" in runner_text,
        "result_assembly_marker_found": '"answer": state.final_answer' in runner_text,
        "request_route_marker_found": "run_agent_web" in app_text,
        "runtime_files_changed": False,
    }
    warnings: list[str] = []
    if runner_load_error:
        warnings.append("Optional web/runner.py static inspection was unavailable; proposed boundaries remain planning-only.")
    if app_load_error:
        warnings.append("Optional web/app.py static inspection was unavailable; proposed request boundary remains planning-only.")
    return summary, warnings


def _evaluate_attachment_points(points: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, str]]]:
    incomplete: list[str] = []
    blocked: list[dict[str, str]] = []
    ids = [str(point.get("stage_id", "")) for point in points]
    missing = [stage_id for stage_id in REQUIRED_STAGE_IDS if stage_id not in ids]
    if missing:
        incomplete.append("Missing required planned stages: " + ", ".join(missing))
    for point in points:
        stage_id = str(point.get("stage_id") or "(unknown)")
        missing_fields = [field for field in REQUIRED_ATTACHMENT_POINT_FIELDS if field not in point]
        if missing_fields:
            incomplete.append(f"Attachment point {stage_id} missing fields: " + ", ".join(missing_fields))
        payload_fields = point.get("event_payload_fields")
        missing_payload = [field for field in EVENT_PAYLOAD_FIELDS if field not in _as_list(payload_fields)]
        if missing_payload:
            incomplete.append(f"Attachment point {stage_id} missing payload fields: " + ", ".join(missing_payload))
        for field in ("enforcement_allowed_now", "emits_runtime_authority", "may_trigger_action", "may_block_action"):
            if point.get(field) is not False:
                _add_reason(blocked, f"attachment:{stage_id}:{field}", f"Attachment point {stage_id} must keep {field} false.")
        if "future_only" not in str(point.get("live_stream_candidate", "")):
            incomplete.append(f"Attachment point {stage_id} does not explicitly defer live streaming")
        if "future_only" not in str(point.get("polling_candidate", "")):
            incomplete.append(f"Attachment point {stage_id} does not explicitly defer polling")
    return _dedupe(incomplete), blocked


def _default_storage_options() -> list[dict[str, Any]]:
    return [
        {"option_id": "snapshot_file", "description": "Safest first implementation: a controlled future hook writes existing run-progress snapshot artifacts.", "risk_level": "low", "allowed_now": False, "future_only": True, "recommended_order": 1},
        {"option_id": "in_memory_session_state", "description": "Could support a live UI later, but requires future runtime-state design and lifecycle controls.", "risk_level": "medium", "allowed_now": False, "future_only": True, "recommended_order": 2},
        {"option_id": "event_log_file", "description": "Could support replay and debugging later, with retention and redaction design required first.", "risk_level": "medium", "allowed_now": False, "future_only": True, "recommended_order": 3},
        {"option_id": "database_event_table", "description": "Higher-risk future option; it requires explicit schema, retention, auth, and migration decisions.", "risk_level": "high", "allowed_now": False, "future_only": True, "recommended_order": 4},
        {"option_id": "websocket_stream", "description": "Highest live-complexity option; do not pursue before snapshot writer and read-only refresh work are closed.", "risk_level": "high", "allowed_now": False, "future_only": True, "recommended_order": 5},
    ]


def _evaluate_storage_options(options: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, str]]]:
    incomplete: list[str] = []
    blocked: list[dict[str, str]] = []
    ids = [str(item.get("option_id", "")) for item in options]
    missing = [option for option in STORAGE_OPTION_IDS if option not in ids]
    if missing:
        incomplete.append("Missing storage options: " + ", ".join(missing))
    for option in options:
        option_id = str(option.get("option_id") or "(unknown)")
        if option.get("allowed_now") is not False:
            _add_reason(blocked, f"storage:{option_id}:allowed_now", f"Storage option {option_id} must remain future work.")
        if option.get("future_only") is not True:
            incomplete.append(f"Storage option {option_id} is not explicitly marked future_only")
    return _dedupe(incomplete), blocked


def _payload_contract(overrides: dict[str, Any] | None) -> dict[str, Any]:
    contract = {
        "fields": list(EVENT_PAYLOAD_FIELDS),
        "planned_defaults": {
            "stage_status": "planned_only",
            "artifact_refs": [],
            "warnings": [],
            "errors": [],
            "simulated_only": True,
            "runtime_authority": False,
            "action_triggered": False,
        },
        "semantics": {
            "progress_implies_success": False,
            "validation_started_is_validation_passed": False,
            "validation_finished_is_validation_passed": False,
            "benchmark_started_is_benchmark_passed": False,
            "benchmark_finished_is_benchmark_passed": False,
            "model_call_pending_triggers_model_call": False,
            "validation_started_triggers_validation": False,
            "benchmark_started_triggers_benchmark": False,
            "approval_boundary_checked_enforces_approval": False,
            "error_reported_remains_visible": True,
        },
    }
    if overrides:
        for key, value in overrides.items():
            if key in {"planned_defaults", "semantics"} and isinstance(value, dict):
                contract[key].update(value)
            else:
                contract[key] = value
    return contract


def _evaluate_payload_contract(contract: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    incomplete: list[str] = []
    blocked: list[dict[str, str]] = []
    fields = _as_list(contract.get("fields"))
    missing = [field for field in EVENT_PAYLOAD_FIELDS if field not in fields]
    if missing:
        incomplete.append("Event payload contract is missing fields: " + ", ".join(missing))
    defaults = _as_dict(contract.get("planned_defaults"))
    semantics = _as_dict(contract.get("semantics"))
    if defaults.get("action_triggered") is not False:
        _add_reason(blocked, "payload:action_triggered", "Planned payload action_triggered must always be false.")
    if defaults.get("runtime_authority") is not False:
        _add_reason(blocked, "payload:runtime_authority", "Planned payload runtime_authority must always be false.")
    for key, message in {
        "progress_implies_success": "Progress events must not imply success.",
        "validation_started_is_validation_passed": "validation_started must remain distinct from validation_passed.",
        "validation_finished_is_validation_passed": "validation_finished must remain distinct from validation_passed.",
        "benchmark_started_is_benchmark_passed": "benchmark_started must remain distinct from benchmark_passed.",
        "benchmark_finished_is_benchmark_passed": "benchmark_finished must remain distinct from benchmark_passed.",
        "model_call_pending_triggers_model_call": "model_call_pending must not trigger a model call.",
        "validation_started_triggers_validation": "validation_started must not trigger validation.",
        "benchmark_started_triggers_benchmark": "benchmark_started must not trigger a benchmark.",
        "approval_boundary_checked_enforces_approval": "approval_boundary_checked must not enforce approval.",
    }.items():
        if semantics.get(key) is not False:
            _add_reason(blocked, f"payload:{key}", message)
    if semantics.get("error_reported_remains_visible") is not True:
        _add_reason(blocked, "payload:error_reported_remains_visible", "error_reported must remain visible.")
    return incomplete, blocked


def _status(blocked: list[dict[str, str]], incomplete: list[str], warnings: list[str]) -> str:
    if blocked:
        return BLOCKED
    if incomplete:
        return INCOMPLETE
    return READY_WITH_WARNINGS if warnings else READY


def build_run_progress_instrumentation_plan(
    *,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    visibility_report_path: str | Path = DEFAULT_VISIBILITY_REPORT_PATH,
    snapshot_loader_report_path: str | Path = DEFAULT_SNAPSHOT_LOADER_REPORT_PATH,
    branch_checkpoint_path: str | Path = DEFAULT_BRANCH_CHECKPOINT_PATH,
    registry_data: Any = None,
    registry_load_error: str = "",
    visibility_report: Any = None,
    visibility_report_load_error: str = "",
    snapshot_loader_report: Any = None,
    snapshot_loader_report_load_error: str = "",
    branch_checkpoint: Any = None,
    branch_checkpoint_load_error: str = "",
    source_visibility_contract: Any = None,
    source_visibility_contract_load_error: str = "",
    source_snapshot_loader_report: Any = None,
    source_snapshot_loader_report_load_error: str = "",
    source_branch_checkpoint: Any = None,
    source_branch_checkpoint_load_error: str = "",
    runner_source: str | None = None,
    runner_source_load_error: str = "",
    app_source: str | None = None,
    app_source_load_error: str = "",
    attachment_points: list[dict[str, Any]] | None = None,
    attachment_overrides: dict[str, dict[str, Any]] | None = None,
    payload_contract_overrides: dict[str, Any] | None = None,
    storage_options: list[dict[str, Any]] | None = None,
    safety_context: dict[str, Any] | None = None,
    policy_violation_markers: dict[str, Any] | None = None,
    plan_id: str = "",
    created_at: str = "",
    live_instrumentation_is_future_work: bool = True,
) -> dict[str, Any]:
    """Build a pure UX.LIVE.1 plan.  It does not inspect or alter a live run."""
    # Accept source names used by the preceding UX.RUN builders while keeping the
    # shorter internal names convenient for direct callers.
    if source_visibility_contract is not None:
        visibility_report = source_visibility_contract
    if source_visibility_contract_load_error:
        visibility_report_load_error = source_visibility_contract_load_error
    if source_snapshot_loader_report is not None:
        snapshot_loader_report = source_snapshot_loader_report
    if source_snapshot_loader_report_load_error:
        snapshot_loader_report_load_error = source_snapshot_loader_report_load_error
    if source_branch_checkpoint is not None:
        branch_checkpoint = source_branch_checkpoint
    if source_branch_checkpoint_load_error:
        branch_checkpoint_load_error = source_branch_checkpoint_load_error

    points = copy.deepcopy(attachment_points) if attachment_points is not None else _default_attachment_points()
    points = _apply_attachment_overrides(points, attachment_overrides)
    options = copy.deepcopy(storage_options) if storage_options is not None else _default_storage_options()
    contract = _payload_contract(payload_contract_overrides)
    boundary_context = dict(_as_dict(safety_context))
    boundary_context.update(_as_dict(policy_violation_markers))
    boundary = _planning_boundary(boundary_context)

    source_artifacts, source_incomplete, source_blocked = _evaluate_sources(
        registry_path=registry_path,
        visibility_path=visibility_report_path,
        snapshot_loader_path=snapshot_loader_report_path,
        branch_checkpoint_path=branch_checkpoint_path,
        registry_data=registry_data,
        registry_load_error=registry_load_error,
        visibility_report=visibility_report,
        visibility_load_error=visibility_report_load_error,
        snapshot_loader_report=snapshot_loader_report,
        snapshot_loader_load_error=snapshot_loader_report_load_error,
        branch_checkpoint=branch_checkpoint,
        branch_checkpoint_load_error=branch_checkpoint_load_error,
    )
    attachment_incomplete, attachment_blocked = _evaluate_attachment_points(points)
    storage_incomplete, storage_blocked = _evaluate_storage_options(options)
    payload_incomplete, payload_blocked = _evaluate_payload_contract(contract)
    static_inspection, static_warnings = _static_source_summary(
        runner_source=runner_source,
        runner_load_error=runner_source_load_error,
        app_source=app_source,
        app_load_error=app_source_load_error,
    )

    blocked = list(source_blocked + attachment_blocked + storage_blocked + payload_blocked)
    for flag, message in boundary.items():
        if message:
            _add_reason(blocked, f"planning_boundary:{flag}", f"UX.LIVE.1 is blocked because { _FORBIDDEN_NOW_FLAGS[flag] }.")
    incomplete = _dedupe(source_incomplete + attachment_incomplete + storage_incomplete + payload_incomplete)
    warnings = list(static_warnings)
    if live_instrumentation_is_future_work:
        warnings.append("Live instrumentation remains future work; this plan inserts no hook, polling loop, or stream.")
    warnings = _dedupe(warnings)
    status = _status(blocked, incomplete, warnings)

    live_polling_boundary = {
        "live_hooks_allowed_now": False,
        "polling_allowed_now": False,
        "streaming_allowed_now": False,
        "websocket_allowed_now": False,
        "automatic_refresh_allowed_now": False,
        "manual_read_only_refresh_not_before_phase": "UX.LIVE.4",
        "websocket_not_before": "A later separately approved phase after UX.LIVE.CLOSE",
        "do_not_jump_directly_to_websocket_or_polling": True,
    }
    authority_boundary = {
        "enforcement_allowed_now": False,
        "runtime_authority_emitted": False,
        "event_can_trigger_action": False,
        "event_can_block_action": False,
        "event_can_approve_action": False,
        "progress_is_not_success": True,
        "approval_boundary_observation_is_not_enforcement": True,
    }
    future_path = [
        {"phase_id": "UX.LIVE.2", "title": "Run Progress Snapshot Writer Plan", "purpose": "Plan a shadow-mode snapshot writer without implementing it."},
        {"phase_id": "UX.LIVE.3", "title": "Run Progress Snapshot Writer Shadow Mode", "purpose": "Future controlled writer work, still without polling, streaming, or action controls."},
        {"phase_id": "UX.LIVE.4", "title": "Read-only UI Refresh Button", "purpose": "Future explicit refresh only after snapshot-writer safety is closed."},
        {"phase_id": "UX.LIVE.CLOSE", "title": "Live Progress Planning Checkpoint", "purpose": "Freeze the planning branch before considering higher-risk live delivery."},
    ]
    risks = [
        {"risk": "Progress may be mistaken for success.", "mitigation": "Keep success semantics false and show validation/benchmark states separately from passed."},
        {"risk": "A planned event could become execution authority.", "mitigation": "Keep every attachment non-enforcing, non-authoritative, non-triggering, and non-blocking."},
        {"risk": "Live delivery could create load, stale state, or hidden errors.", "mitigation": "Start with a controlled snapshot_file plan; defer polling and websocket work."},
        {"risk": "Error events could be hidden by a generic spinner.", "mitigation": "Require error_reported to remain visible with warnings and errors payload fields."},
    ]
    verdicts = {
        READY: "The plan is complete and safe; all future boundaries are explicit.",
        READY_WITH_WARNINGS: "The plan is complete and safe, but live instrumentation intentionally remains future work.",
        INCOMPLETE: "The plan is missing required stages, payload rules, storage options, or future boundaries.",
        BLOCKED: "The plan permits a live runtime, authority, enforcement, or action-triggering behavior now.",
    }
    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "plan_id": plan_id or "ux-live-1-run-progress-instrumentation-plan",
        "created_at": created_at or _utc_now(),
        "status": status,
        "guardrail_note": GUARDRAIL_NOTE,
        "source_artifacts": source_artifacts,
        "static_inspection": static_inspection,
        "instrumentation_philosophy": {
            "plan_only": True,
            "events_observe_existing_boundaries_only": True,
            "progress_events_are_not_success": True,
            "planned_payloads_are_simulated_only": True,
            "runtime_authority": False,
            "action_triggered": False,
        },
        "attachment_points": points,
        "event_payload_contract": contract,
        "storage_options": options,
        "live_streaming_polling_boundary": live_polling_boundary,
        "runtime_authority_boundary": authority_boundary,
        "planning_boundary": boundary,
        "risks_and_mitigations": risks,
        "future_implementation_path": future_path,
        "warnings": warnings,
        "blocked_reasons": blocked,
        "incomplete_reasons": incomplete,
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "guardrails": list(GUARDRAILS),
        "final_verdict": {
            "status": status,
            "safe_to_plan": status in {READY, READY_WITH_WARNINGS},
            "live_instrumentation_implemented": False,
            "message": verdicts[status],
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
        },
    }


def _list_lines(values: Any) -> list[str]:
    return [f"- {_md(json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, dict) else item)}" for item in _as_list(values)] or ["_None._"]


def _dict_lines(values: Any) -> list[str]:
    return [f"- `{_md(key)}`: {_md(json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value)}" for key, value in sorted(_as_dict(values).items())] or ["_None._"]


def render_run_progress_instrumentation_plan_markdown(report: dict[str, Any]) -> str:
    """Render the plan in Markdown without mutating the report."""
    lines = [
        "# Run Progress Instrumentation Plan", "", f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}", "",
        "## Summary", "", f"- **Plan id:** `{_md(report.get('plan_id'))}`", f"- **Status:** `{_md(report.get('status'))}`", f"- **Attachment point count:** {len(_as_list(report.get('attachment_points')))}", "",
        "## Source Artifacts", "",
        "| Source | Read status | Expected kind | Path |", "| --- | --- | --- | --- |",
    ]
    for source in _as_list(report.get("source_artifacts")):
        item = _as_dict(source)
        lines.append(f"| {_md(item.get('source_id'))} | {_md(item.get('read_status'))} | {_md(item.get('expected_kind'))} | `{_md(item.get('path'))}` |")
    lines.extend(["", "## Instrumentation Philosophy", ""])
    lines.extend(_dict_lines(report.get("instrumentation_philosophy")))
    lines.extend(["", "## Proposed Stage Attachment Points", "", "| Stage | Proposed source | Boundary | Risk | Enforces now | Authority | Triggers | Blocks |", "| --- | --- | --- | --- | --- | --- | --- | --- |"])
    for point in _as_list(report.get("attachment_points")):
        item = _as_dict(point)
        lines.append(
            f"| {_md(item.get('stage_id'))} | `{_md(item.get('proposed_source_file'))}` | {_md(item.get('proposed_function_or_boundary'))} | {_md(item.get('risk_level'))} | {_bool(item.get('enforcement_allowed_now'))} | {_bool(item.get('emits_runtime_authority'))} | {_bool(item.get('may_trigger_action'))} | {_bool(item.get('may_block_action'))} |"
        )
    lines.extend(["", "## Event Payload Contract", ""])
    lines.extend(_dict_lines(report.get("event_payload_contract")))
    lines.extend(["", "## Storage Options", "", "| Option | Risk | Allowed now | Future only | Description |", "| --- | --- | --- | --- | --- |"])
    for option in _as_list(report.get("storage_options")):
        item = _as_dict(option)
        lines.append(f"| {_md(item.get('option_id'))} | {_md(item.get('risk_level'))} | {_bool(item.get('allowed_now'))} | {_bool(item.get('future_only'))} | {_md(item.get('description'))} |")
    for heading, key in (
        ("Live Streaming / Polling Boundary", "live_streaming_polling_boundary"),
        ("Runtime Authority Boundary", "runtime_authority_boundary"),
        ("Risks and Mitigations", "risks_and_mitigations"),
        ("Future Implementation Path", "future_implementation_path"),
        ("Warnings", "warnings"),
        ("Blocked Reasons", "blocked_reasons"),
        ("Incomplete Reasons", "incomplete_reasons"),
        ("Final Verdict", "final_verdict"),
    ):
        lines.extend(["", f"## {heading}", ""])
        lines.extend(_dict_lines(report.get(key)) if isinstance(report.get(key), dict) else _list_lines(report.get(key)))
    next_phase = _as_dict(report.get("recommended_next_phase"))
    lines.extend(["", "## Recommended Next Phase", "", f"- **Phase:** `{_md(next_phase.get('phase_id'))}`", f"- **Title:** {_md(next_phase.get('title'))}", f"- **Reason:** {_md(next_phase.get('reason'))}", "", "## Guardrails", ""])
    lines.extend(_list_lines(report.get("guardrails")))
    lines.append("")
    return "\n".join(lines)


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{_norm_path(path)}: {exc}"
    return (data, "") if isinstance(data, dict) else (None, f"{_norm_path(path)} is not a JSON object")


def _load_text(path: Path) -> tuple[str | None, str]:
    try:
        return path.read_text(encoding="utf-8"), ""
    except OSError as exc:
        return None, f"{_norm_path(path)}: {exc}"


def write_run_progress_instrumentation_plan(
    *,
    repo_root: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    visibility_report_path: str | Path = DEFAULT_VISIBILITY_REPORT_PATH,
    snapshot_loader_report_path: str | Path = DEFAULT_SNAPSHOT_LOADER_REPORT_PATH,
    branch_checkpoint_path: str | Path = DEFAULT_BRANCH_CHECKPOINT_PATH,
    runner_source_path: str | Path = DEFAULT_RUNNER_SOURCE_PATH,
    app_source_path: str | Path = DEFAULT_APP_SOURCE_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    plan_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Read static source artifacts and write UX.LIVE.1 planning artifacts only."""
    root = Path(repo_root or ".")
    registry, registry_error = _load_json_object(_resolve(root, registry_path))
    visibility, visibility_error = _load_json_object(_resolve(root, visibility_report_path))
    loader, loader_error = _load_json_object(_resolve(root, snapshot_loader_report_path))
    checkpoint, checkpoint_error = _load_json_object(_resolve(root, branch_checkpoint_path))
    runner_source, runner_error = _load_text(_resolve(root, runner_source_path))
    app_source, app_error = _load_text(_resolve(root, app_source_path))
    report = build_run_progress_instrumentation_plan(
        registry_path=registry_path,
        visibility_report_path=visibility_report_path,
        snapshot_loader_report_path=snapshot_loader_report_path,
        branch_checkpoint_path=branch_checkpoint_path,
        registry_data=registry,
        registry_load_error=registry_error,
        visibility_report=visibility,
        visibility_report_load_error=visibility_error,
        snapshot_loader_report=loader,
        snapshot_loader_report_load_error=loader_error,
        branch_checkpoint=checkpoint,
        branch_checkpoint_load_error=checkpoint_error,
        runner_source=runner_source,
        runner_source_load_error=runner_error,
        app_source=app_source,
        app_source_load_error=app_error,
        plan_id=plan_id,
        created_at=created_at,
    )
    out = _resolve(root, output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    md_path = out / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_run_progress_instrumentation_plan_markdown(report), encoding="utf-8")
    return {
        "ok": report["status"] in {READY, READY_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
