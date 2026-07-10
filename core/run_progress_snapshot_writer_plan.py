"""UX.LIVE.2 - Run Progress Snapshot Writer Plan.

Defines a future, default-off shadow-mode snapshot writer.  This module is a
planning artifact generator only: it does not implement a snapshot writer,
attach a runtime hook, or observe a live run.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "run_progress_snapshot_writer_plan"
THIS_PHASE_ID = "UX.LIVE.2"

JSON_NAME = "run_progress_snapshot_writer_plan.json"
MD_NAME = "run_progress_snapshot_writer_plan.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "ux" / "run_progress_snapshot_writer_plan"
DEFAULT_REGISTRY_PATH = Path("docs") / "roadmap" / "phase_registry.json"
DEFAULT_INSTRUMENTATION_PLAN_PATH = (
    Path(".agent") / "ux" / "run_progress_instrumentation_plan" / "run_progress_instrumentation_plan.json"
)
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

ALLOWED_FUTURE_WRITE_ROOT = Path(".agent") / "ux" / "run_progress_snapshots"
ALLOWED_FUTURE_WRITE_TEMPLATE = ".agent/ux/run_progress_snapshots/<run_id>/"
CANONICAL_SNAPSHOT_JSON_NAME = "run_progress_snapshot.json"
CANONICAL_SNAPSHOT_MD_NAME = "run_progress_snapshot.md"
FUTURE_EVENTS_JSONL_NAME = "run_progress_events.jsonl"

READY = "run_progress_snapshot_writer_plan_ready"
READY_WITH_WARNINGS = "run_progress_snapshot_writer_plan_ready_with_warnings"
INCOMPLETE = "run_progress_snapshot_writer_plan_incomplete"
BLOCKED = "run_progress_snapshot_writer_plan_blocked"

SAFE_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")

REQUIRED_SNAPSHOT_FIELDS: tuple[str, ...] = (
    "snapshot_id",
    "run_id",
    "source_phase",
    "writer_mode",
    "writer_enabled",
    "snapshot_status",
    "current_stage_id",
    "completed_stage_ids",
    "pending_stage_ids",
    "warning_stage_ids",
    "error_stage_ids",
    "stages",
    "progress_notice",
    "created_at",
    "updated_at",
    "sequence_number",
    "simulated_only",
    "live_stream_enabled",
    "polling_enabled",
    "runtime_behavior_changed",
    "runtime_authority",
    "action_triggered",
    "actions_available",
    "artifact_refs",
    "warnings",
    "errors",
    "metadata",
)

REQUIRED_STAGE_FIELDS: tuple[str, ...] = (
    "stage_id",
    "status",
    "label",
    "message",
    "updated_at",
    "artifact_refs",
    "warnings",
    "errors",
)

REQUIRED_PREVIOUS_PHASES: tuple[str, ...] = (
    "UX.RUN.1",
    "UX.RUN.2",
    "UX.RUN.CLOSE",
    "UX.LIVE.1",
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "UX.LIVE.3",
    "title": "Run Progress Snapshot Writer Shadow Mode",
    "reason": (
        "Implement one minimal, default-off writer at one narrow safe boundary; "
        "keep it non-authoritative and do not add polling, streaming, actions, "
        "a database, or network delivery."
    ),
}

GUARDRAIL_NOTE = (
    "UX.LIVE.2 is report-only and plan-only. It defines how a later shadow-mode "
    "snapshot writer could be safe without implementing a writer, inserting hooks, "
    "or changing runtime behavior now."
)

GUARDRAILS: tuple[str, ...] = (
    "report-only",
    "plan only",
    "no runtime hook insertion",
    "no snapshot writing",
    "no polling",
    "no streaming",
    "no model call",
    "no model routing",
    "no worker launch",
    "no patch apply",
    "no validation run",
    "no benchmark run",
    "no MCP/tool invocation",
    "no approval enforcement",
    "no token issuance",
    "no token consumption",
    "no network",
    "no database write",
    "no auth behavior change",
    "no cleanup/deletion",
    "no automatic authority escalation",
)

_FORBIDDEN_NOW_FLAGS: dict[str, str] = {
    "writer_enabled_by_default": "the future writer is enabled by default",
    "runtime_hooks_inserted": "a runtime hook is inserted now",
    "writes_outside_allowed_root": "future writes are permitted outside the allowed root",
    "sensitive_data_permitted": "the plan permits sensitive data",
    "progress_events_trigger_actions": "progress events may trigger or block actions",
    "snapshots_as_runtime_authority": "snapshots are treated as runtime authority",
    "writer_failure_fails_main_run": "writer failure can fail the main run",
    "polling_enabled": "polling is enabled",
    "streaming_enabled": "streaming is enabled",
    "cleanup_or_deletion_enabled": "cleanup or deletion is enabled",
    "runtime_behavior_changed": "runtime behavior is changed now",
    "model_call_performed": "a model call is performed",
    "model_routing_changed": "model routing is changed",
    "worker_launch_performed": "a worker is launched",
    "patch_apply_performed": "a patch is applied",
    "validation_run_performed": "validation is run",
    "benchmark_run_performed": "a benchmark is run",
    "approval_enforcement_changed": "approval enforcement is changed",
    "network_used": "a network path is used",
    "database_written": "a database is written",
    "auth_behavior_changed": "auth behavior is changed",
}

_CONTEXT_ALIASES: dict[str, str] = {
    "writer_default_enabled": "writer_enabled_by_default",
    "live_writer_enabled": "writer_enabled_by_default",
    "live_instrumentation_added": "runtime_hooks_inserted",
    "snapshot_written": "runtime_hooks_inserted",
    "outside_allowed_root": "writes_outside_allowed_root",
    "sensitive_payload_allowed": "sensitive_data_permitted",
    "action_triggering_events_allowed": "progress_events_trigger_actions",
    "progress_treated_as_authority": "snapshots_as_runtime_authority",
    "writer_failure_changes_run_result": "writer_failure_fails_main_run",
    "polling_added": "polling_enabled",
    "streaming_added": "streaming_enabled",
    "cleanup_added": "cleanup_or_deletion_enabled",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _norm_path(value: str | Path | None) -> str:
    return str(value or "").replace("\\", "/")


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _bool(value: Any) -> str:
    return "true" if value is True else "false"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def _add_reason(reasons: list[dict[str, str]], reason: str, message: str) -> None:
    if not any(item.get("reason") == reason for item in reasons):
        reasons.append({"reason": reason, "message": message})


def _deep_update(base: dict[str, Any], overrides: dict[str, Any] | None) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in _dict(overrides).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_update(_dict(result[key]), value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _source_record(
    *, source_id: str, path: str | Path, value: Any, load_error: str, expected_kind: str
) -> dict[str, Any]:
    record = {
        "source_id": source_id,
        "path": _norm_path(path),
        "expected_kind": expected_kind,
        "provided": value is not None,
        "load_error": str(load_error or ""),
        "read_status": "loaded" if value is not None and not load_error else ("missing_or_unreadable" if load_error else "reference_only"),
    }
    if isinstance(value, dict):
        record["report_kind"] = str(value.get("report_kind", ""))
        record["status"] = str(value.get("status") or value.get("checkpoint_status") or "")
    return record


def _evaluate_sources(
    *,
    registry_path: str | Path,
    instrumentation_path: str | Path,
    visibility_path: str | Path,
    snapshot_loader_path: str | Path,
    branch_checkpoint_path: str | Path,
    registry_data: Any,
    registry_load_error: str,
    instrumentation_plan: Any,
    instrumentation_plan_load_error: str,
    visibility_report: Any,
    visibility_report_load_error: str,
    snapshot_loader_report: Any,
    snapshot_loader_report_load_error: str,
    branch_checkpoint: Any,
    branch_checkpoint_load_error: str,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]]]:
    records = [
        _source_record(source_id="phase_registry", path=registry_path, value=registry_data, load_error=registry_load_error, expected_kind="phase_registry"),
        _source_record(source_id="ux_live_1_instrumentation_plan", path=instrumentation_path, value=instrumentation_plan, load_error=instrumentation_plan_load_error, expected_kind="run_progress_instrumentation_plan"),
        _source_record(source_id="ux_run_1_visibility_report", path=visibility_path, value=visibility_report, load_error=visibility_report_load_error, expected_kind="run_progress_visibility"),
        _source_record(source_id="ux_run_2_snapshot_loader_report", path=snapshot_loader_path, value=snapshot_loader_report, load_error=snapshot_loader_report_load_error, expected_kind="run_progress_snapshot_loader"),
        _source_record(source_id="ux_run_close_checkpoint", path=branch_checkpoint_path, value=branch_checkpoint, load_error=branch_checkpoint_load_error, expected_kind="run_progress_visibility_branch_checkpoint"),
    ]
    incomplete: list[str] = []
    blocked: list[dict[str, str]] = []
    for record in records:
        if record["load_error"]:
            incomplete.append(f"Required source {record['source_id']} could not be loaded: {record['load_error']}")
        elif not record["provided"]:
            incomplete.append(f"Required source {record['source_id']} was not provided")

    registry = _dict(registry_data)
    if registry_data is not None:
        phases = {
            str(item.get("phase_id")): item
            for item in _list(registry.get("phases"))
            if isinstance(item, dict) and item.get("phase_id")
        }
        for phase_id in REQUIRED_PREVIOUS_PHASES:
            if _dict(phases.get(phase_id)).get("status") != "complete":
                incomplete.append(f"Required prior phase is not complete: {phase_id}")

    plan = _dict(instrumentation_plan)
    if instrumentation_plan is not None:
        if plan.get("report_kind") != "run_progress_instrumentation_plan":
            incomplete.append("UX.LIVE.1 source is not a run_progress_instrumentation_plan artifact")
        if plan.get("status") not in {"run_progress_instrumentation_plan_ready", "run_progress_instrumentation_plan_ready_with_warnings"}:
            incomplete.append("UX.LIVE.1 source is not ready to inform a future writer plan")
        if not _list(plan.get("attachment_points")):
            incomplete.append("UX.LIVE.1 source has no future attachment points")

    visibility = _dict(visibility_report)
    if visibility_report is not None:
        if visibility.get("report_kind") != "run_progress_visibility":
            incomplete.append("UX.RUN.1 source is not a run_progress_visibility artifact")
        if not _list(visibility.get("stage_contract")):
            incomplete.append("UX.RUN.1 source has no stage contract")

    loader = _dict(snapshot_loader_report)
    if snapshot_loader_report is not None:
        if loader.get("report_kind") != "run_progress_snapshot_loader":
            incomplete.append("UX.RUN.2 source is not a run_progress_snapshot_loader artifact")
        if loader.get("blocked_reasons"):
            _add_reason(blocked, "source_snapshot_loader_blocked", "UX.RUN.2 source already reports blocked reasons.")

    checkpoint = _dict(branch_checkpoint)
    if branch_checkpoint is not None:
        if checkpoint.get("report_kind") != "run_progress_visibility_branch_checkpoint":
            incomplete.append("UX.RUN.CLOSE source is not a branch checkpoint artifact")
        if checkpoint.get("checkpoint_status") not in {
            "run_progress_visibility_branch_frozen",
            "run_progress_visibility_branch_frozen_with_warnings",
        }:
            incomplete.append("UX.RUN.CLOSE source does not show a frozen read-only branch")
    return records, _dedupe(incomplete), blocked


def _default_configuration() -> dict[str, Any]:
    return {
        "environment_variable": "RUN_PROGRESS_SHADOW_WRITER_ENABLED",
        "default_value": False,
        "RUN_PROGRESS_SHADOW_WRITER_ENABLED": False,
        "missing_config_behaves_as_disabled": True,
        "no_implicit_enablement": True,
        "disabled_state_writes_nothing": True,
        "optional_per_run_opt_in": {
            "supported_now": False,
            "future_only": True,
            "requires_explicit_opt_in": True,
        },
        "writer_mode": "shadow_mode_default_off",
        "implementation_status": "planned_only",
    }


def _default_allowed_write_root() -> dict[str, Any]:
    return {
        "root": ALLOWED_FUTURE_WRITE_ROOT.as_posix(),
        "per_run_directory_template": ALLOWED_FUTURE_WRITE_TEMPLATE,
        "fixed_files": [CANONICAL_SNAPSHOT_JSON_NAME, CANONICAL_SNAPSHOT_MD_NAME],
        "future_only_file": FUTURE_EVENTS_JSONL_NAME,
        "future_events_jsonl_allowed_now": False,
        "writes_outside_root_allowed": False,
        "one_canonical_snapshot_per_run": True,
    }


def _default_snapshot_schema() -> dict[str, Any]:
    fields = {
        "snapshot_id": "safe slug uniquely identifying this snapshot record within a safe run directory",
        "run_id": "safe slug identifying one run; never an absolute or relative path",
        "source_phase": "phase or source boundary that supplied the observation, not an authority claim",
        "writer_mode": "shadow_mode_default_off for the future minimal writer",
        "writer_enabled": "records explicit future enablement; false when disabled",
        "snapshot_status": "descriptive snapshot lifecycle state; never a success or approval result",
        "current_stage_id": "current observed stage identifier, if known",
        "completed_stage_ids": "observed completed stages; completion is not validation or benchmark pass",
        "pending_stage_ids": "known stages not yet observed complete",
        "warning_stage_ids": "stages carrying visible warnings",
        "error_stage_ids": "stages carrying visible errors",
        "stages": "ordered descriptive stage records following stage_schema",
        "progress_notice": "operator-facing description of what the snapshot does and does not prove",
        "created_at": "UTC creation timestamp",
        "updated_at": "UTC update timestamp that cannot move backward",
        "sequence_number": "monotonically increasing integer per run",
        "simulated_only": "true unless a separately approved future phase changes this contract",
        "live_stream_enabled": "always false for this plan",
        "polling_enabled": "always false for this plan",
        "runtime_behavior_changed": "always false for this plan",
        "runtime_authority": "always false; snapshots are read-only evidence",
        "action_triggered": "always false",
        "actions_available": "always an empty list",
        "artifact_refs": "redacted, relative, safe evidence references only",
        "warnings": "visible non-fatal writer or stage warnings",
        "errors": "visible descriptive errors; they do not change run control",
        "metadata": "allow-listed, redacted descriptive metadata only",
    }
    return {
        "required_fields": list(REQUIRED_SNAPSHOT_FIELDS),
        "field_definitions": fields,
        "stage_schema": {
            "required_fields": list(REQUIRED_STAGE_FIELDS),
            "status_values": ["pending", "in_progress", "completed", "warning", "error"],
            "authority": False,
            "may_trigger_action": False,
            "may_block_action": False,
        },
        "planned_defaults": {
            "writer_mode": "shadow_mode_default_off",
            "writer_enabled": False,
            "snapshot_status": "planned_snapshot",
            "completed_stage_ids": [],
            "pending_stage_ids": [],
            "warning_stage_ids": [],
            "error_stage_ids": [],
            "stages": [],
            "simulated_only": True,
            "live_stream_enabled": False,
            "polling_enabled": False,
            "runtime_behavior_changed": False,
            "runtime_authority": False,
            "action_triggered": False,
            "actions_available": [],
            "artifact_refs": [],
            "warnings": [],
            "errors": [],
            "metadata": {},
        },
    }


def _default_stage_update_policy() -> dict[str, Any]:
    return {
        "progress_stage_is_not_success": True,
        "validation_finished_is_validation_passed": False,
        "benchmark_finished_is_benchmark_passed": False,
        "final_response_ready_is_terminal_only": True,
        "final_response_ready_implies_patch_approval": False,
        "final_response_ready_implies_validation_success": False,
        "sequence_number_must_increase_monotonically": True,
        "updated_at_must_not_move_backward": True,
        "completed_stages_do_not_silently_become_pending": True,
        "error_stages_remain_visible_unless_explicitly_resolved": True,
        "unknown_stage_behavior": "append_visible_warning_and_preserve_snapshot",
        "duplicate_update_behavior": "deterministic_idempotent_when_same_run_sequence_and_payload",
        "stage_status_is_descriptive_not_authoritative": True,
    }


def _default_atomic_write_strategy() -> dict[str, Any]:
    return {
        "planned_only": True,
        "temporary_file_location": "same_per_run_directory_as_canonical_target",
        "temporary_filename_strategy": "fixed-safe-prefix + safe snapshot_id + sequence_number + uuid4 hex + .tmp",
        "windows_safe_temporary_filenames": True,
        "write_order": [
            "serialize complete UTF-8 content to a unique temporary file",
            "flush and close temporary file before replacement",
            "atomically replace canonical target where supported",
            "write Markdown only as a projection of the canonical JSON snapshot",
        ],
        "canonical_json_never_partially_written": True,
        "replacement_method": "future implementation should use same-directory atomic replacement where supported",
        "transient_permission_error_retry": {
            "allowed_only_if_project_convention_supports_it": True,
            "scope": "replacement only",
            "maximum_attempts": 2,
            "otherwise": "surface warning and leave main run unchanged",
        },
        "temporary_file_cleanup_on_failure": True,
    }


def _default_overwrite_update_policy() -> dict[str, Any]:
    return {
        "canonical_json_filename": CANONICAL_SNAPSHOT_JSON_NAME,
        "canonical_markdown_filename": CANONICAL_SNAPSHOT_MD_NAME,
        "one_canonical_snapshot_per_run": True,
        "sequence_based_last_update_logic": True,
        "stale_sequence_behavior": "reject_or_ignore_in_future_implementation",
        "malformed_prior_snapshot_behavior": "preserve_or_quarantine_inside_same_safe_run_directory_before_any_explicit_safe_replacement",
        "no_silent_malformed_overwrite": True,
        "markdown_is_noncanonical_projection": True,
        "future_events_jsonl_deferred": True,
    }


def _default_path_safety() -> dict[str, Any]:
    return {
        "run_id_must_be_safe_slug": True,
        "snapshot_id_must_be_safe_slug": True,
        "safe_slug_pattern": SAFE_SLUG_RE.pattern,
        "no_absolute_paths": True,
        "no_path_traversal": True,
        "no_path_separators_in_ids": True,
        "fixed_canonical_filenames_only": True,
        "resolve_and_verify_path_is_inside_allowed_root": True,
        "no_fallback_write_outside_allowed_root": True,
    }


def _default_redaction_policy() -> dict[str, Any]:
    return {
        "sensitive_data_forbidden": True,
        "forbidden_payload_categories": [
            ".env contents",
            "secrets",
            "credentials",
            "tokens",
            "raw prompts",
            "API keys",
            "sensitive payloads",
        ],
        "metadata_policy": "allow-list short descriptive fields; reject or redact unknown sensitive payloads",
        "artifact_refs_policy": "relative safe references only; no raw content or absolute paths",
        "redaction_happens_before_persistence": True,
        "redaction_failure_behavior": "do_not_write_sensitive_value; emit a non-fatal warning later",
    }


def _default_failure_isolation() -> dict[str, Any]:
    return {
        "writer_failure_fails_main_run": False,
        "writer_failure_changes_main_run_result": False,
        "writer_failure_visible_as_warning_or_debug_evidence_later": True,
        "no_hidden_silence": True,
        "no_fallback_write_outside_allowed_root": True,
        "database_fallback": False,
        "network_fallback": False,
        "future_error_boundary": "catch writer-local failures after the observed boundary without changing that boundary result",
    }


def _default_concurrency_strategy() -> dict[str, Any]:
    return {
        "one_canonical_snapshot_per_run": True,
        "no_global_shared_snapshot_file": True,
        "run_ids_must_not_mix": True,
        "sequence_based_last_update_logic": True,
        "stale_sequence_updates_rejected_or_ignored": True,
        "concurrent_updates_must_not_produce_malformed_json": True,
        "same_directory_atomic_replacement": True,
        "future_locking_decision": "use a narrowly scoped per-run coordination primitive only if one attachment point can emit concurrent updates",
    }


def _default_retention_boundary() -> dict[str, Any]:
    return {
        "deletion_performed_now": False,
        "automatic_janitor_enabled": False,
        "snapshots_are_read_only_evidence": True,
        "future_retention_options": ["count_based", "age_based"],
        "cleanup_requires_separate_explicit_phase": True,
        "no_cleanup_or_deletion_in_ux_live_2": True,
    }


def _default_authority_boundary() -> dict[str, Any]:
    return {
        "runtime_authority": False,
        "action_triggered": False,
        "actions_available": [],
        "progress_updates_may_trigger_actions": False,
        "progress_updates_may_block_actions": False,
        "progress_updates_may_enforce_approvals": False,
        "progress_is_not_success": True,
        "snapshot_is_read_only_evidence": True,
    }


def _default_future_attachment_points(instrumentation_plan: Any) -> list[dict[str, Any]]:
    selected = {
        "request_received",
        "input_normalized",
        "final_response_ready",
        "error_reported",
    }
    points: list[dict[str, Any]] = []
    for point in _list(_dict(instrumentation_plan).get("attachment_points")):
        source = _dict(point)
        stage_id = str(source.get("stage_id", ""))
        if stage_id in selected:
            points.append(
                {
                    "stage_id": stage_id,
                    "proposed_source_file": str(source.get("proposed_source_file", "")),
                    "proposed_function_or_boundary": str(source.get("proposed_function_or_boundary", "")),
                    "future_only": True,
                    "writer_must_observe_after_existing_boundary": True,
                    "must_not_trigger_or_block_action": True,
                    "implementation_not_before_phase": "UX.LIVE.3",
                }
            )
    if not points:
        points = [
            {
                "stage_id": "final_response_ready",
                "proposed_source_file": "web/runner.py",
                "proposed_function_or_boundary": "existing final result assembly boundary",
                "future_only": True,
                "writer_must_observe_after_existing_boundary": True,
                "must_not_trigger_or_block_action": True,
                "implementation_not_before_phase": "UX.LIVE.3",
            }
        ]
    return points


def _default_rollback_disable_behavior() -> dict[str, Any]:
    return {
        "disable_switch": "set RUN_PROGRESS_SHADOW_WRITER_ENABLED=false or omit it",
        "missing_config_is_disabled": True,
        "disabled_writer_writes_nothing": True,
        "disable_does_not_change_main_run_behavior": True,
        "disable_does_not_delete_existing_snapshots": True,
        "rollback_scope": "remove the one future hook and leave prior snapshots as read-only evidence",
    }


def _planning_boundary(safety_context: dict[str, Any] | None) -> dict[str, bool]:
    values = {key: False for key in _FORBIDDEN_NOW_FLAGS}
    for key, value in _dict(safety_context).items():
        target = _CONTEXT_ALIASES.get(key, key)
        if target in values:
            values[target] = bool(value)
    return values


def _evaluate_configuration(configuration: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    incomplete: list[str] = []
    blocked: list[dict[str, str]] = []
    for key in ("environment_variable", "default_value", "RUN_PROGRESS_SHADOW_WRITER_ENABLED", "missing_config_behaves_as_disabled", "no_implicit_enablement", "disabled_state_writes_nothing", "optional_per_run_opt_in", "writer_mode", "implementation_status"):
        if key not in configuration:
            incomplete.append(f"Default-off configuration is missing {key}")
    if configuration.get("environment_variable") != "RUN_PROGRESS_SHADOW_WRITER_ENABLED":
        incomplete.append("Default-off configuration must name RUN_PROGRESS_SHADOW_WRITER_ENABLED")
    if configuration.get("default_value") is not False or configuration.get("RUN_PROGRESS_SHADOW_WRITER_ENABLED") is not False:
        _add_reason(blocked, "writer_enabled_by_default", "RUN_PROGRESS_SHADOW_WRITER_ENABLED must default to false.")
    if configuration.get("missing_config_behaves_as_disabled") is not True:
        _add_reason(blocked, "missing_config_not_disabled", "Missing writer configuration must behave as disabled.")
    if configuration.get("no_implicit_enablement") is not True:
        _add_reason(blocked, "implicit_writer_enablement", "The future writer may not be implicitly enabled.")
    if configuration.get("disabled_state_writes_nothing") is not True:
        _add_reason(blocked, "disabled_writer_writes", "A disabled writer must write nothing.")
    opt_in = _dict(configuration.get("optional_per_run_opt_in"))
    if opt_in and (opt_in.get("supported_now") is True or opt_in.get("future_only") is not True or opt_in.get("requires_explicit_opt_in") is not True):
        _add_reason(blocked, "per_run_opt_in_not_future_explicit", "Per-run opt-in must remain future-only and explicit.")
    return _dedupe(incomplete), blocked


def _evaluate_write_root(root: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    incomplete: list[str] = []
    blocked: list[dict[str, str]] = []
    for key in ("root", "per_run_directory_template", "fixed_files", "writes_outside_root_allowed", "one_canonical_snapshot_per_run"):
        if key not in root:
            incomplete.append(f"Allowed write root is missing {key}")
    if root.get("root") != ALLOWED_FUTURE_WRITE_ROOT.as_posix() or root.get("per_run_directory_template") != ALLOWED_FUTURE_WRITE_TEMPLATE:
        _add_reason(blocked, "writes_outside_allowed_root", "Future snapshot paths must be restricted to .agent/ux/run_progress_snapshots/<run_id>/.")
    if root.get("writes_outside_root_allowed") is not False:
        _add_reason(blocked, "outside_root_permitted", "No fallback or direct write outside the allowed root is allowed.")
    if root.get("one_canonical_snapshot_per_run") is not True:
        incomplete.append("Write root must define one canonical snapshot per run")
    return _dedupe(incomplete), blocked


def _evaluate_schema(schema: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    incomplete: list[str] = []
    blocked: list[dict[str, str]] = []
    fields = _list(schema.get("required_fields"))
    missing = [field for field in REQUIRED_SNAPSHOT_FIELDS if field not in fields]
    if missing:
        incomplete.append("Snapshot schema is missing required fields: " + ", ".join(missing))
    stage = _dict(schema.get("stage_schema"))
    missing_stage = [field for field in REQUIRED_STAGE_FIELDS if field not in _list(stage.get("required_fields"))]
    if missing_stage:
        incomplete.append("Stage schema is missing required fields: " + ", ".join(missing_stage))
    defaults = _dict(schema.get("planned_defaults"))
    for key, required in {
        "runtime_authority": False,
        "action_triggered": False,
        "live_stream_enabled": False,
        "polling_enabled": False,
        "runtime_behavior_changed": False,
        "simulated_only": True,
    }.items():
        if defaults.get(key) is not required:
            _add_reason(blocked, f"schema:{key}", f"Snapshot schema default {key} must be {str(required).lower()}.")
    if defaults.get("actions_available") != []:
        _add_reason(blocked, "schema:actions_available", "Snapshot schema actions_available must be empty.")
    if stage.get("authority") is not False or stage.get("may_trigger_action") is not False or stage.get("may_block_action") is not False:
        _add_reason(blocked, "stage_schema_authority", "Stage records must remain non-authoritative and non-actionable.")
    return _dedupe(incomplete), blocked


def _evaluate_stage_update_policy(policy: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    required_true = ("progress_stage_is_not_success", "final_response_ready_is_terminal_only", "sequence_number_must_increase_monotonically", "updated_at_must_not_move_backward", "completed_stages_do_not_silently_become_pending", "error_stages_remain_visible_unless_explicitly_resolved")
    required_false = ("validation_finished_is_validation_passed", "benchmark_finished_is_benchmark_passed", "final_response_ready_implies_patch_approval", "final_response_ready_implies_validation_success")
    incomplete: list[str] = []
    blocked: list[dict[str, str]] = []
    for key in (*required_true, *required_false, "unknown_stage_behavior", "duplicate_update_behavior"):
        if key not in policy:
            incomplete.append(f"Stage update policy is missing {key}")
    for key in required_true:
        if policy.get(key) is not True:
            _add_reason(blocked, f"stage_update:{key}", f"Stage update policy must keep {key} true.")
    for key in required_false:
        if policy.get(key) is not False:
            _add_reason(blocked, f"stage_update:{key}", f"Stage update policy must keep {key} false.")
    return _dedupe(incomplete), blocked


def _evaluate_atomicity(strategy: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    required = ("temporary_file_location", "temporary_filename_strategy", "windows_safe_temporary_filenames", "write_order", "canonical_json_never_partially_written", "replacement_method", "transient_permission_error_retry", "temporary_file_cleanup_on_failure")
    incomplete = [f"Atomic write strategy is missing {key}" for key in required if key not in strategy]
    blocked: list[dict[str, str]] = []
    if strategy.get("temporary_file_location") != "same_per_run_directory_as_canonical_target":
        _add_reason(blocked, "atomicity:temporary_location", "Temporary files must be in the same per-run directory as the target.")
    if strategy.get("windows_safe_temporary_filenames") is not True:
        incomplete.append("Atomic write strategy must include Windows-safe temporary filenames")
    if strategy.get("canonical_json_never_partially_written") is not True:
        _add_reason(blocked, "atomicity:partial_canonical_json", "Canonical snapshot JSON must never be partially written.")
    if strategy.get("temporary_file_cleanup_on_failure") is not True:
        incomplete.append("Atomic write strategy must clean up temporary files on failure")
    retry = _dict(strategy.get("transient_permission_error_retry"))
    if retry and (retry.get("scope") != "replacement only" or not isinstance(retry.get("maximum_attempts"), int) or int(retry.get("maximum_attempts", 0)) > 2):
        _add_reason(blocked, "atomicity:retry_scope", "PermissionError retry must be narrow and capped at two replacement attempts.")
    return _dedupe(incomplete), blocked


def _evaluate_path_safety(policy: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    required_true = ("run_id_must_be_safe_slug", "snapshot_id_must_be_safe_slug", "no_absolute_paths", "no_path_traversal", "no_path_separators_in_ids", "resolve_and_verify_path_is_inside_allowed_root", "no_fallback_write_outside_allowed_root")
    incomplete = [f"Path safety policy is missing {key}" for key in (*required_true, "safe_slug_pattern") if key not in policy]
    blocked: list[dict[str, str]] = []
    for key in required_true:
        if policy.get(key) is not True:
            _add_reason(blocked, f"path_safety:{key}", f"Path safety policy must keep {key} true.")
    if policy.get("safe_slug_pattern") != SAFE_SLUG_RE.pattern:
        _add_reason(blocked, "path_safety:slug_pattern", "Run and snapshot IDs must use the defined safe slug pattern.")
    return _dedupe(incomplete), blocked


def _evaluate_redaction(policy: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    required = ("sensitive_data_forbidden", "forbidden_payload_categories", "metadata_policy", "artifact_refs_policy", "redaction_happens_before_persistence", "redaction_failure_behavior")
    incomplete = [f"Sensitive data redaction policy is missing {key}" for key in required if key not in policy]
    blocked: list[dict[str, str]] = []
    if policy.get("sensitive_data_forbidden") is not True:
        _add_reason(blocked, "sensitive_data_permitted", "Snapshots must not contain .env data, secrets, credentials, tokens, raw prompts, API keys, or sensitive payloads.")
    if policy.get("redaction_happens_before_persistence") is not True:
        _add_reason(blocked, "redaction_after_persistence", "Redaction must happen before any future persistence.")
    return _dedupe(incomplete), blocked


def _evaluate_failure_isolation(policy: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    required = ("writer_failure_fails_main_run", "writer_failure_changes_main_run_result", "writer_failure_visible_as_warning_or_debug_evidence_later", "no_hidden_silence", "no_fallback_write_outside_allowed_root", "database_fallback", "network_fallback")
    incomplete = [f"Failure isolation policy is missing {key}" for key in required if key not in policy]
    blocked: list[dict[str, str]] = []
    if policy.get("writer_failure_fails_main_run") is not False or policy.get("writer_failure_changes_main_run_result") is not False:
        _add_reason(blocked, "writer_failure_fails_main_run", "Writer failure must not fail or change the actual run result.")
    if policy.get("writer_failure_visible_as_warning_or_debug_evidence_later") is not True or policy.get("no_hidden_silence") is not True:
        incomplete.append("Writer failure must be visible through future warning or debug evidence")
    if policy.get("no_fallback_write_outside_allowed_root") is not True or policy.get("database_fallback") is not False or policy.get("network_fallback") is not False:
        _add_reason(blocked, "failure_fallback_unsafe", "Writer failures may not fall back to external paths, a database, or a network.")
    return _dedupe(incomplete), blocked


def _evaluate_concurrency(policy: dict[str, Any]) -> list[str]:
    required = ("one_canonical_snapshot_per_run", "no_global_shared_snapshot_file", "run_ids_must_not_mix", "sequence_based_last_update_logic", "stale_sequence_updates_rejected_or_ignored", "concurrent_updates_must_not_produce_malformed_json", "same_directory_atomic_replacement")
    return [f"Concurrency strategy is missing or weak for {key}" for key in required if policy.get(key) is not True]


def _evaluate_retention(policy: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    required = ("deletion_performed_now", "automatic_janitor_enabled", "snapshots_are_read_only_evidence", "future_retention_options", "cleanup_requires_separate_explicit_phase", "no_cleanup_or_deletion_in_ux_live_2")
    incomplete = [f"Retention boundary is missing {key}" for key in required if key not in policy]
    blocked: list[dict[str, str]] = []
    if policy.get("deletion_performed_now") is not False or policy.get("automatic_janitor_enabled") is not False or policy.get("no_cleanup_or_deletion_in_ux_live_2") is not True:
        _add_reason(blocked, "cleanup_or_deletion_enabled", "UX.LIVE.2 must not add cleanup, deletion, or an automatic janitor.")
    if policy.get("cleanup_requires_separate_explicit_phase") is not True:
        incomplete.append("Retention policy must defer cleanup to a separate explicit phase")
    return _dedupe(incomplete), blocked


def _evaluate_authority(policy: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    required = ("runtime_authority", "action_triggered", "actions_available", "progress_updates_may_trigger_actions", "progress_updates_may_block_actions", "progress_updates_may_enforce_approvals", "progress_is_not_success", "snapshot_is_read_only_evidence")
    incomplete = [f"Runtime authority boundary is missing {key}" for key in required if key not in policy]
    blocked: list[dict[str, str]] = []
    if policy.get("runtime_authority") is not False:
        _add_reason(blocked, "snapshots_as_runtime_authority", "Snapshots must never hold runtime authority.")
    if policy.get("action_triggered") is not False or policy.get("actions_available") != []:
        _add_reason(blocked, "snapshot_actions_available", "Snapshot actions must remain absent and untriggered.")
    for key in ("progress_updates_may_trigger_actions", "progress_updates_may_block_actions", "progress_updates_may_enforce_approvals"):
        if policy.get(key) is not False:
            _add_reason(blocked, f"authority:{key}", f"Runtime authority boundary must keep {key} false.")
    return _dedupe(incomplete), blocked


def _evaluate_attachment_points(points: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, str]]]:
    if not points:
        return ["Future attachment points are missing"], []
    incomplete: list[str] = []
    blocked: list[dict[str, str]] = []
    for point in points:
        stage_id = str(point.get("stage_id") or "(unknown)")
        for key in ("stage_id", "future_only", "writer_must_observe_after_existing_boundary", "must_not_trigger_or_block_action", "implementation_not_before_phase"):
            if key not in point:
                incomplete.append(f"Future attachment point {stage_id} is missing {key}")
        if point.get("future_only") is not True or point.get("implementation_not_before_phase") != "UX.LIVE.3":
            _add_reason(blocked, f"attachment:{stage_id}:implemented_now", "Attachment points must remain future-only until UX.LIVE.3.")
        if point.get("writer_must_observe_after_existing_boundary") is not True or point.get("must_not_trigger_or_block_action") is not True:
            _add_reason(blocked, f"attachment:{stage_id}:authority", "A future writer may observe only after an existing boundary and may not trigger or block action.")
    return _dedupe(incomplete), blocked


def _status(blocked: list[dict[str, str]], incomplete: list[str], warnings: list[str]) -> str:
    if blocked:
        return BLOCKED
    if incomplete:
        return INCOMPLETE
    return READY_WITH_WARNINGS if warnings else READY


def build_run_progress_snapshot_writer_plan(
    *,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    instrumentation_plan_path: str | Path = DEFAULT_INSTRUMENTATION_PLAN_PATH,
    visibility_report_path: str | Path = DEFAULT_VISIBILITY_REPORT_PATH,
    snapshot_loader_report_path: str | Path = DEFAULT_SNAPSHOT_LOADER_REPORT_PATH,
    branch_checkpoint_path: str | Path = DEFAULT_BRANCH_CHECKPOINT_PATH,
    registry_data: Any = None,
    registry_load_error: str = "",
    instrumentation_plan: Any = None,
    instrumentation_plan_load_error: str = "",
    visibility_report: Any = None,
    visibility_report_load_error: str = "",
    snapshot_loader_report: Any = None,
    snapshot_loader_report_load_error: str = "",
    branch_checkpoint: Any = None,
    branch_checkpoint_load_error: str = "",
    source_instrumentation_plan: Any = None,
    source_instrumentation_plan_load_error: str = "",
    source_visibility_contract: Any = None,
    source_visibility_contract_load_error: str = "",
    source_snapshot_loader_report: Any = None,
    source_snapshot_loader_report_load_error: str = "",
    source_branch_checkpoint: Any = None,
    source_branch_checkpoint_load_error: str = "",
    configuration_overrides: dict[str, Any] | None = None,
    writer_configuration_overrides: dict[str, Any] | None = None,
    allowed_write_root_overrides: dict[str, Any] | None = None,
    snapshot_schema_overrides: dict[str, Any] | None = None,
    stage_update_policy_overrides: dict[str, Any] | None = None,
    atomic_write_strategy_overrides: dict[str, Any] | None = None,
    overwrite_update_policy_overrides: dict[str, Any] | None = None,
    path_safety_overrides: dict[str, Any] | None = None,
    redaction_policy_overrides: dict[str, Any] | None = None,
    failure_isolation_overrides: dict[str, Any] | None = None,
    concurrency_strategy_overrides: dict[str, Any] | None = None,
    retention_policy_overrides: dict[str, Any] | None = None,
    runtime_authority_overrides: dict[str, Any] | None = None,
    future_attachment_points: list[dict[str, Any]] | None = None,
    rollback_disable_overrides: dict[str, Any] | None = None,
    plan_overrides: dict[str, Any] | None = None,
    safety_context: dict[str, Any] | None = None,
    policy_violation_markers: dict[str, Any] | None = None,
    plan_id: str = "",
    created_at: str = "",
    writer_is_intentionally_unimplemented: bool = True,
) -> dict[str, Any]:
    """Build a pure future-writer plan; it never writes a run snapshot."""
    if source_instrumentation_plan is not None:
        instrumentation_plan = source_instrumentation_plan
    if source_instrumentation_plan_load_error:
        instrumentation_plan_load_error = source_instrumentation_plan_load_error
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

    all_overrides = _dict(plan_overrides)
    configuration = _deep_update(_default_configuration(), _dict(configuration_overrides) or _dict(writer_configuration_overrides) or _dict(all_overrides.get("default_off_configuration")))
    write_root = _deep_update(_default_allowed_write_root(), _dict(allowed_write_root_overrides) or _dict(all_overrides.get("allowed_write_root")))
    schema = _deep_update(_default_snapshot_schema(), _dict(snapshot_schema_overrides) or _dict(all_overrides.get("snapshot_schema")))
    stage_policy = _deep_update(_default_stage_update_policy(), _dict(stage_update_policy_overrides) or _dict(all_overrides.get("stage_update_policy")))
    atomicity = _deep_update(_default_atomic_write_strategy(), _dict(atomic_write_strategy_overrides) or _dict(all_overrides.get("atomic_write_strategy")))
    overwrite = _deep_update(_default_overwrite_update_policy(), _dict(overwrite_update_policy_overrides) or _dict(all_overrides.get("overwrite_update_policy")))
    path_safety = _deep_update(_default_path_safety(), _dict(path_safety_overrides) or _dict(all_overrides.get("path_safety")))
    redaction = _deep_update(_default_redaction_policy(), _dict(redaction_policy_overrides) or _dict(all_overrides.get("sensitive_data_redaction")))
    failure = _deep_update(_default_failure_isolation(), _dict(failure_isolation_overrides) or _dict(all_overrides.get("failure_isolation")))
    concurrency = _deep_update(_default_concurrency_strategy(), _dict(concurrency_strategy_overrides) or _dict(all_overrides.get("concurrency_strategy")))
    retention = _deep_update(_default_retention_boundary(), _dict(retention_policy_overrides) or _dict(all_overrides.get("retention_boundary")))
    authority = _deep_update(_default_authority_boundary(), _dict(runtime_authority_overrides) or _dict(all_overrides.get("runtime_authority_boundary")))
    rollback = _deep_update(_default_rollback_disable_behavior(), _dict(rollback_disable_overrides) or _dict(all_overrides.get("rollback_disable_behavior")))
    attachment_points = copy.deepcopy(future_attachment_points) if future_attachment_points is not None else _default_future_attachment_points(instrumentation_plan)

    sources, source_incomplete, source_blocked = _evaluate_sources(
        registry_path=registry_path,
        instrumentation_path=instrumentation_plan_path,
        visibility_path=visibility_report_path,
        snapshot_loader_path=snapshot_loader_report_path,
        branch_checkpoint_path=branch_checkpoint_path,
        registry_data=registry_data,
        registry_load_error=registry_load_error,
        instrumentation_plan=instrumentation_plan,
        instrumentation_plan_load_error=instrumentation_plan_load_error,
        visibility_report=visibility_report,
        visibility_report_load_error=visibility_report_load_error,
        snapshot_loader_report=snapshot_loader_report,
        snapshot_loader_report_load_error=snapshot_loader_report_load_error,
        branch_checkpoint=branch_checkpoint,
        branch_checkpoint_load_error=branch_checkpoint_load_error,
    )
    evaluations = [
        _evaluate_configuration(configuration),
        _evaluate_write_root(write_root),
        _evaluate_schema(schema),
        _evaluate_stage_update_policy(stage_policy),
        _evaluate_atomicity(atomicity),
        _evaluate_path_safety(path_safety),
        _evaluate_redaction(redaction),
        _evaluate_failure_isolation(failure),
        _evaluate_retention(retention),
        _evaluate_authority(authority),
        _evaluate_attachment_points(attachment_points),
    ]
    incomplete = list(source_incomplete + _evaluate_concurrency(concurrency))
    blocked = list(source_blocked)
    for missing, reasons in evaluations:
        incomplete.extend(missing)
        blocked.extend(reasons)

    boundary_context = dict(_dict(safety_context))
    boundary_context.update(_dict(policy_violation_markers))
    planning_boundary = _planning_boundary(boundary_context)
    for flag, enabled in planning_boundary.items():
        if enabled:
            _add_reason(blocked, f"planning_boundary:{flag}", f"UX.LIVE.2 is blocked because {_FORBIDDEN_NOW_FLAGS[flag]}.")

    # Cross-section rules prevent a safe-looking individual section from weakening
    # the complete plan.
    if overwrite.get("one_canonical_snapshot_per_run") is not True or overwrite.get("sequence_based_last_update_logic") is not True:
        incomplete.append("Overwrite/update policy must preserve one canonical sequence-based snapshot per run")
    if overwrite.get("no_silent_malformed_overwrite") is not True:
        _add_reason(blocked, "overwrite:malformed_prior_snapshot", "Malformed prior snapshots must be preserved/quarantined or replaced only under explicit safe rules.")
    if rollback.get("missing_config_is_disabled") is not True or rollback.get("disabled_writer_writes_nothing") is not True or rollback.get("disable_does_not_change_main_run_behavior") is not True:
        _add_reason(blocked, "rollback:disable_behavior", "Rollback/disable behavior must keep the writer disabled without changing run behavior.")

    warnings: list[str] = []
    if writer_is_intentionally_unimplemented:
        warnings.append("The shadow-mode writer remains intentionally unimplemented; UX.LIVE.2 adds no hook and writes no live snapshots.")
    warnings = _dedupe(warnings)
    incomplete = _dedupe(incomplete)
    status = _status(blocked, incomplete, warnings)
    verdict_messages = {
        READY: "The future writer plan is complete, safe, explicit, and has no blockers.",
        READY_WITH_WARNINGS: "The future writer plan is complete and safe, while the writer intentionally remains unimplemented.",
        INCOMPLETE: "The future writer plan needs missing configuration, schema, atomicity, failure, path, concurrency, or retention boundaries.",
        BLOCKED: "The future writer plan crosses a default-off, containment, authority, failure-isolation, or no-live-delivery guardrail.",
    }
    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "plan_id": plan_id or "ux-live-2-run-progress-snapshot-writer-plan",
        "created_at": created_at or _utc_now(),
        "status": status,
        "guardrail_note": GUARDRAIL_NOTE,
        "source_artifacts": sources,
        "writer_purpose": {
            "purpose": "Define a future controlled, read-only evidence writer for run progress snapshots during an already-running execution.",
            "default_off_shadow_mode": True,
            "implemented_now": False,
            "changes_runtime_behavior_now": False,
        },
        "default_off_configuration": configuration,
        "allowed_write_root": write_root,
        "snapshot_directory_structure": {
            "per_run_directory": ALLOWED_FUTURE_WRITE_TEMPLATE,
            "canonical_files": [CANONICAL_SNAPSHOT_JSON_NAME, CANONICAL_SNAPSHOT_MD_NAME],
            "future_optional_file": FUTURE_EVENTS_JSONL_NAME,
            "future_optional_file_allowed_now": False,
        },
        "snapshot_schema": schema,
        "stage_update_policy": stage_policy,
        "atomic_write_strategy": atomicity,
        "overwrite_update_policy": overwrite,
        "path_safety": path_safety,
        "sensitive_data_redaction": redaction,
        "failure_isolation": failure,
        "concurrency_strategy": concurrency,
        "retention_boundary": retention,
        "runtime_authority_boundary": authority,
        "future_attachment_points": attachment_points,
        "rollback_disable_behavior": rollback,
        "planning_boundary": planning_boundary,
        "warnings": warnings,
        "blocked_reasons": blocked,
        "incomplete_reasons": incomplete,
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "guardrails": list(GUARDRAILS),
        "final_verdict": {
            "status": status,
            "safe_to_plan": status in {READY, READY_WITH_WARNINGS},
            "writer_implemented": False,
            "runtime_hooks_inserted": False,
            "live_snapshots_written": False,
            "message": verdict_messages[status],
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
        },
    }


def _list_lines(values: Any) -> list[str]:
    entries = _list(values)
    if not entries:
        return ["_None._"]
    return [f"- {_md(json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, dict) else item)}" for item in entries]


def _dict_lines(values: Any) -> list[str]:
    entries = _dict(values)
    if not entries:
        return ["_None._"]
    return [f"- `{_md(key)}`: {_md(json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value)}" for key, value in sorted(entries.items())]


def render_run_progress_snapshot_writer_plan_markdown(report: dict[str, Any]) -> str:
    """Render UX.LIVE.2 planning evidence without mutating its report."""
    lines = [
        "# Run Progress Snapshot Writer Plan",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Plan id:** `{_md(report.get('plan_id'))}`",
        f"- **Status:** `{_md(report.get('status'))}`",
        "- **Writer implemented now:** `false`",
        "",
        "## Source Artifacts",
        "",
        "| Source | Read status | Expected kind | Path |",
        "| --- | --- | --- | --- |",
    ]
    for source in _list(report.get("source_artifacts")):
        item = _dict(source)
        lines.append(f"| {_md(item.get('source_id'))} | {_md(item.get('read_status'))} | {_md(item.get('expected_kind'))} | `{_md(item.get('path'))}` |")
    section_keys = (
        ("Writer Philosophy", "writer_purpose"),
        ("Default-Off Configuration", "default_off_configuration"),
        ("Allowed Write Root", "allowed_write_root"),
        ("Snapshot Directory Structure", "snapshot_directory_structure"),
        ("Snapshot Schema", "snapshot_schema"),
        ("Stage Update Policy", "stage_update_policy"),
        ("Atomic Write Strategy", "atomic_write_strategy"),
        ("Overwrite / Update Policy", "overwrite_update_policy"),
        ("Path Safety", "path_safety"),
        ("Sensitive Data Redaction", "sensitive_data_redaction"),
        ("Failure Isolation", "failure_isolation"),
        ("Concurrency Strategy", "concurrency_strategy"),
        ("Retention Boundary", "retention_boundary"),
        ("Runtime Authority Boundary", "runtime_authority_boundary"),
        ("Future Attachment Points", "future_attachment_points"),
        ("Rollback / Disable Behavior", "rollback_disable_behavior"),
        ("Warnings", "warnings"),
        ("Blocked Reasons", "blocked_reasons"),
        ("Final Verdict", "final_verdict"),
    )
    for heading, key in section_keys:
        value = report.get(key)
        lines.extend(["", f"## {heading}", ""])
        lines.extend(_dict_lines(value) if isinstance(value, dict) else _list_lines(value))
    next_phase = _dict(report.get("recommended_next_phase"))
    lines.extend([
        "",
        "## Recommended Next Phase",
        "",
        f"- **Phase:** `{_md(next_phase.get('phase_id'))}`",
        f"- **Title:** {_md(next_phase.get('title'))}",
        f"- **Reason:** {_md(next_phase.get('reason'))}",
        "",
        "## Guardrails",
        "",
    ])
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


def write_run_progress_snapshot_writer_plan(
    *,
    repo_root: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    instrumentation_plan_path: str | Path = DEFAULT_INSTRUMENTATION_PLAN_PATH,
    visibility_report_path: str | Path = DEFAULT_VISIBILITY_REPORT_PATH,
    snapshot_loader_report_path: str | Path = DEFAULT_SNAPSHOT_LOADER_REPORT_PATH,
    branch_checkpoint_path: str | Path = DEFAULT_BRANCH_CHECKPOINT_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    plan_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Write only the UX.LIVE.2 plan artifacts, never a run snapshot artifact."""
    root = Path(repo_root or ".")
    registry, registry_error = _load_json_object(_resolve(root, registry_path))
    instrumentation, instrumentation_error = _load_json_object(_resolve(root, instrumentation_plan_path))
    visibility, visibility_error = _load_json_object(_resolve(root, visibility_report_path))
    loader, loader_error = _load_json_object(_resolve(root, snapshot_loader_report_path))
    checkpoint, checkpoint_error = _load_json_object(_resolve(root, branch_checkpoint_path))
    report = build_run_progress_snapshot_writer_plan(
        registry_path=registry_path,
        instrumentation_plan_path=instrumentation_plan_path,
        visibility_report_path=visibility_report_path,
        snapshot_loader_report_path=snapshot_loader_report_path,
        branch_checkpoint_path=branch_checkpoint_path,
        registry_data=registry,
        registry_load_error=registry_error,
        instrumentation_plan=instrumentation,
        instrumentation_plan_load_error=instrumentation_error,
        visibility_report=visibility,
        visibility_report_load_error=visibility_error,
        snapshot_loader_report=loader,
        snapshot_loader_report_load_error=loader_error,
        branch_checkpoint=checkpoint,
        branch_checkpoint_load_error=checkpoint_error,
        plan_id=plan_id,
        created_at=created_at,
    )
    out = _resolve(root, output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    md_path = out / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_run_progress_snapshot_writer_plan_markdown(report), encoding="utf-8")
    return {
        "ok": report["status"] in {READY, READY_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
