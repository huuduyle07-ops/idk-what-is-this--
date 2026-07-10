"""UX.RUN.CLOSE - Run Progress Visibility Branch Checkpoint.

Creates a report-only checkpoint for UX.RUN.1 through UX.RUN.3.  It reads the
existing visibility-contract and snapshot-loader artifacts plus static UI-panel
markers.  It never starts live instrumentation, changes a route, polls, or
performs any runtime action.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "run_progress_visibility_branch_checkpoint"
THIS_PHASE_ID = "UX.RUN.CLOSE"
REQUIRED_PHASE_IDS: tuple[str, ...] = ("UX.RUN.1", "UX.RUN.2", "UX.RUN.3")

STATUS_FROZEN = "run_progress_visibility_branch_frozen"
STATUS_FROZEN_WITH_WARNINGS = "run_progress_visibility_branch_frozen_with_warnings"
STATUS_INCOMPLETE = "run_progress_visibility_branch_incomplete"
STATUS_BLOCKED = "run_progress_visibility_branch_blocked"

JSON_NAME = "run_progress_visibility_branch_checkpoint.json"
MD_NAME = "run_progress_visibility_branch_checkpoint.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "ux" / "run_progress_visibility_branch_checkpoint"
DEFAULT_REGISTRY_PATH = Path("docs") / "roadmap" / "phase_registry.json"
DEFAULT_VISIBILITY_CONTRACT_PATH = (
    Path(".agent") / "ux" / "run_progress_visibility" / "run_progress_visibility_report.json"
)
DEFAULT_SNAPSHOT_LOADER_REPORT_PATH = (
    Path(".agent") / "ux" / "run_progress_snapshot_loader" / "run_progress_snapshot_loader_report.json"
)
DEFAULT_UI_PANEL_MARKER_PATH = Path("web") / "templates" / "index.html"

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "UX.LIVE.1",
    "title": "Run Progress Instrumentation Plan",
    "reason": (
        "Plan future live progress instrumentation without implementing polling, "
        "runtime hooks, or execution behavior."
    ),
}
ALTERNATIVE_NEXT_PHASE = {
    "phase_id": "OPS.TEST.4",
    "title": "Executable Suite Manifest Design",
    "reason": "Use only when executable test-suite manifest planning is the explicit priority.",
}

GUARDRAIL_NOTE = (
    "UX.RUN.CLOSE is report-only and checkpoint-only. It verifies that progress "
    "visibility remains readable, non-live, and non-authoritative; it does not "
    "add instrumentation, polling, POST actions, runtime hooks, model calls, "
    "worker launches, patch application, validation, benchmarks, approval "
    "enforcement, or action-triggering controls."
)
GUARDRAILS: tuple[str, ...] = (
    "report-only",
    "checkpoint only",
    "no live instrumentation",
    "no polling",
    "no POST route",
    "no action-triggering UI controls",
    "no runtime behavior change",
    "no model call or routing",
    "no worker launch",
    "no patch apply",
    "no validation or benchmark run",
    "no MCP/tool invocation",
    "no approval enforcement",
    "no token issuance or consumption",
    "no network beyond the existing same-app GET route",
    "no database write",
    "no auth behavior change",
    "no automatic authority escalation",
)

POLICY_VIOLATION_LABELS: dict[str, str] = {
    "live_instrumentation_added": "live progress instrumentation was added",
    "polling_added": "progress polling was added",
    "post_action_added": "POST progress action was added",
    "action_controls_added": "action-triggering progress UI control was added",
    "runtime_behavior_changed": "runtime execution behavior was changed",
    "patch_apply_controls_added": "patch-apply progress control was added",
    "validation_controls_added": "validation progress control was added",
    "benchmark_controls_added": "benchmark progress control was added",
    "worker_controls_added": "worker progress control was added",
    "model_controls_added": "model progress control was added",
    "approval_enforcement_added": "approval enforcement was added",
    "progress_treated_as_authority": "progress was treated as authority",
    "progress_treated_as_success": "progress was treated as proof of success",
}
PHASE_GUARDRAIL_FIELDS: tuple[str, ...] = (
    "merge_allowed",
    "network_allowed",
    "model_calls_allowed",
    "writes_real_repo",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _norm_path(value: str | Path | None) -> str:
    return str(value or "").replace("\\", "/")


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _bool(value: Any) -> str:
    return "true" if bool(value) else "false"


def _phase_map(registry_data: Any) -> dict[str, dict[str, Any]]:
    return {
        str(phase["phase_id"]): phase
        for phase in _as_list(_as_dict(registry_data).get("phases"))
        if isinstance(phase, dict) and phase.get("phase_id")
    }


def _phase_completion_summary(registry_data: Any, load_error: str) -> tuple[dict[str, Any], list[str], list[str]]:
    incomplete: list[str] = []
    blocked: list[str] = []
    if load_error:
        incomplete.append(f"phase registry could not be loaded: {load_error}")
    phases = _phase_map(registry_data)
    checks: list[dict[str, Any]] = []
    for phase_id in REQUIRED_PHASE_IDS:
        phase = phases.get(phase_id)
        present = phase is not None
        status = str(phase.get("status", "")) if phase else "(missing)"
        violations = [field for field in PHASE_GUARDRAIL_FIELDS if phase and phase.get(field) is True]
        complete = bool(phase and status == "complete")
        if not present:
            incomplete.append(f"{phase_id} is missing from the phase registry")
        elif not complete:
            incomplete.append(f"{phase_id} is {status}, expected complete")
        if violations:
            blocked.append(f"{phase_id} has guardrail violation(s): {', '.join(violations)}")
        checks.append(
            {
                "phase_id": phase_id,
                "present": present,
                "status": status,
                "complete": complete,
                "guardrails_ok": present and not violations,
                "guardrail_violations": violations,
            }
        )
    checkpoint = phases.get(THIS_PHASE_ID)
    return (
        {
            "required_phase_ids": list(REQUIRED_PHASE_IDS),
            "phase_checks": checks,
            "all_required_phases_complete": all(item["complete"] for item in checks),
            "all_required_phase_guardrails_ok": all(item["guardrails_ok"] for item in checks),
            "checkpoint_phase_registered": checkpoint is not None,
            "checkpoint_phase_status": str(checkpoint.get("status", "")) if checkpoint else "(missing)",
            "checkpoint_phase_complete": bool(checkpoint and checkpoint.get("status") == "complete"),
        },
        incomplete,
        blocked,
    )


def _artifact_coverage(
    *,
    visibility_contract_path: str | Path,
    visibility_contract: Any,
    visibility_contract_error: str,
    snapshot_loader_path: str | Path,
    snapshot_loader: Any,
    snapshot_loader_error: str,
) -> tuple[dict[str, Any], list[str], list[str]]:
    incomplete: list[str] = []
    blocked: list[str] = []
    contract = _as_dict(visibility_contract)
    loader = _as_dict(snapshot_loader)
    checks: list[dict[str, Any]] = []

    contract_present = bool(contract) and not visibility_contract_error
    contract_ok = contract_present and contract.get("report_kind") == "run_progress_visibility"
    if not contract_present:
        incomplete.append("progress visibility report is missing or unreadable: " + (visibility_contract_error or _norm_path(visibility_contract_path)))
    elif not contract_ok:
        incomplete.append("progress visibility report has an unexpected report_kind")
    elif not _as_list(contract.get("stage_contract")):
        incomplete.append("progress visibility report has no progress stage contract")
    checks.append({
        "artifact_id": "progress_visibility_contract",
        "path": _norm_path(visibility_contract_path),
        "present": contract_present,
        "report_kind": str(contract.get("report_kind", "")),
        "status": str(contract.get("status", "")),
        "ready": contract_ok and bool(_as_list(contract.get("stage_contract"))),
    })

    loader_result = _as_dict(loader.get("loader_result"))
    snapshot = _as_dict(loader_result.get("snapshot"))
    loader_present = bool(loader) and not snapshot_loader_error
    loader_ok = loader_present and loader.get("report_kind") == "run_progress_snapshot_loader"
    if not loader_present:
        incomplete.append("snapshot loader report is missing or unreadable: " + (snapshot_loader_error or _norm_path(snapshot_loader_path)))
    elif not loader_ok:
        incomplete.append("snapshot loader report has an unexpected report_kind")
    elif not snapshot:
        incomplete.append("snapshot loader report has no loaded snapshot summary")
    checks.append({
        "artifact_id": "snapshot_loader_report",
        "path": _norm_path(snapshot_loader_path),
        "present": loader_present,
        "report_kind": str(loader.get("report_kind", "")),
        "status": str(loader.get("status", "")),
        "ready": loader_ok and bool(snapshot),
    })

    for source_name, source in (("progress visibility", contract), ("snapshot loader", loader)):
        for reason in _as_list(source.get("blocked_reasons")):
            blocked.append(f"{source_name} source is blocked: {reason}")
        for reason in _as_list(source.get("incomplete_reasons")):
            incomplete.append(f"{source_name} source is incomplete: {reason}")
    return (
        {
            "checks": checks,
            "all_required_artifacts_present": all(item["present"] for item in checks),
            "all_required_artifacts_ready": all(item["ready"] for item in checks),
        },
        incomplete,
        blocked,
    )


def _progress_contract_summary(contract: Any) -> tuple[dict[str, Any], list[str]]:
    data = _as_dict(contract)
    semantics = _as_dict(data.get("progress_semantics"))
    stages = _as_list(data.get("stage_contract"))
    stage_ids = [str(stage.get("stage_id", "")) for stage in stages if isinstance(stage, dict)]
    incomplete: list[str] = []
    if data and not semantics.get("progress_is_descriptive_only"):
        incomplete.append("progress contract does not verify descriptive-only semantics")
    if data and semantics.get("progress_implies_success") is not False:
        incomplete.append("progress contract does not verify that progress is distinct from success")
    return (
        {
            "contract_exists": bool(data),
            "contract_status": str(data.get("status", "")),
            "stage_count": len(stages),
            "stage_ids": stage_ids,
            "progress_is_descriptive_only": semantics.get("progress_is_descriptive_only") is True,
            "progress_implies_success": semantics.get("progress_implies_success"),
            "validation_not_run_distinct": "validation_not_run" in stage_ids and "validation_reported" in stage_ids,
            "benchmark_not_run_distinct": "benchmark_not_run" in stage_ids and "benchmark_reported" in stage_ids,
            "errors_visible": bool(_as_dict(data.get("error_visibility")).get("errors_must_be_visible")),
        },
        incomplete,
    )


def _snapshot_loader_summary(loader: Any) -> tuple[dict[str, Any], list[str], list[str]]:
    data = _as_dict(loader)
    result = _as_dict(data.get("loader_result"))
    snapshot = _as_dict(result.get("snapshot"))
    boundaries = [str(item) for item in _as_list(data.get("read_only_boundaries"))]
    incomplete: list[str] = []
    blocked: list[str] = []
    if data and not result:
        incomplete.append("snapshot loader report lacks loader_result")
    if result and not snapshot:
        incomplete.append("snapshot loader report lacks snapshot data")
    if snapshot.get("live_stream_enabled") is True:
        blocked.append("snapshot loader reports live streaming enabled")
    if snapshot.get("polling_enabled") is True:
        blocked.append("snapshot loader reports polling enabled")
    if snapshot.get("runtime_behavior_changed") is True:
        blocked.append("snapshot loader reports runtime behavior changed")
    if _as_list(snapshot.get("actions_available")):
        blocked.append("snapshot loader reports available actions")
    if result and str(result.get("loader_status", "")).endswith("_blocked"):
        blocked.append("snapshot loader result is blocked")
    return (
        {
            "loader_exists": bool(data),
            "loader_status": str(result.get("loader_status", data.get("status", ""))),
            "snapshot_id": str(snapshot.get("snapshot_id", "")),
            "snapshot_status": str(snapshot.get("snapshot_status", "")),
            "loader_is_read_only": any("Loads existing JSON only." == item for item in boundaries),
            "live_stream_enabled": snapshot.get("live_stream_enabled"),
            "polling_enabled": snapshot.get("polling_enabled"),
            "runtime_behavior_changed": snapshot.get("runtime_behavior_changed"),
            "actions_available": _as_list(snapshot.get("actions_available")),
        },
        incomplete,
        blocked,
    )


def _between(text: str, start: str, end: str) -> str:
    try:
        start_index = text.index(start)
        end_index = text.index(end, start_index)
    except ValueError:
        return ""
    return text[start_index:end_index]


def _ui_panel_summary(marker: str, load_error: str, path: str | Path) -> tuple[dict[str, Any], list[str], list[str]]:
    incomplete: list[str] = []
    blocked: list[str] = []
    panel_html = _between(marker, "<!-- UX.RUN.3 run-progress-panel", "<!-- /UX.RUN.3 run-progress-panel -->")
    panel_js = _between(marker, "// UX.RUN.3 run-progress-panel", "// /UX.RUN.3 run-progress-panel")
    required_html = ("id=\"runProgressPanel\"", "data-run-progress-readonly=\"true\"", "Not run / unavailable is not a passed result.")
    required_js = ('fetch("/ux/run-progress/snapshot/" + safeId, { method: "GET" })', "loadRunProgressSnapshot")
    if load_error:
        incomplete.append("UI panel marker is missing or unreadable: " + load_error)
    elif not panel_html or not panel_js:
        incomplete.append("UI panel marker is missing")
    elif any(item not in panel_html for item in required_html) or any(item not in panel_js for item in required_js):
        incomplete.append("UI panel does not contain all required read-only markers")
    forbidden = {
        "polling": "setInterval",
        "POST action": 'method: "POST"',
        "patch control": "applyPatch(",
        "validation control": "runValidation",
        "benchmark control": "runBenchmark",
        "worker control": "launchWorker",
        "model control": "routeModel",
    }
    for label, token in forbidden.items():
        if token in panel_js:
            blocked.append(f"UI panel contains forbidden {label} marker: {token}")
    return (
        {
            "source_ui_panel_marker": _norm_path(path),
            "panel_exists": bool(panel_html and panel_js),
            "panel_is_read_only": "data-run-progress-readonly=\"true\"" in panel_html,
            "uses_get_only_loader": required_js[0] in panel_js,
            "not_run_is_distinct_from_passed": "Not run / unavailable is not a passed result." in panel_html,
            "no_polling_marker": "setInterval" not in panel_js,
            "no_post_marker": 'method: "POST"' not in panel_js,
            "no_action_control_marker": not blocked,
        },
        incomplete,
        blocked,
    )


def _artifact_runtime_blockers(contract: Any) -> list[str]:
    guardrails = _as_dict(_as_dict(contract).get("guardrails"))
    labels = {
        "polling_route_added": "progress contract reports polling route added",
        "runtime_execution_changed": "progress contract reports runtime execution changed",
        "action_triggering_controls_added": "progress contract reports action controls added",
        "patch_apply_performed": "progress contract reports patch application",
        "validation_run_performed": "progress contract reports validation run",
        "benchmark_run_performed": "progress contract reports benchmark run",
        "worker_launch_performed": "progress contract reports worker launch",
        "model_call_performed": "progress contract reports model call",
        "model_routing_changed": "progress contract reports model routing changed",
        "approval_enforcement_changed": "progress contract reports approval enforcement changed",
        "progress_treated_as_success": "progress contract treats progress as success",
    }
    return [label for key, label in labels.items() if guardrails.get(key) is True]


def _verification(
    contract_summary: dict[str, Any],
    loader_summary: dict[str, Any],
    ui_summary: dict[str, Any],
    markers: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    read_only = {
        "progress_is_descriptive_only": contract_summary.get("progress_is_descriptive_only") is True,
        "progress_does_not_imply_success": contract_summary.get("progress_implies_success") is False,
        "snapshot_loader_is_read_only": loader_summary.get("loader_is_read_only") is True,
        "ui_panel_uses_get_only_loader": ui_summary.get("uses_get_only_loader") is True,
        "ui_panel_has_no_action_controls": ui_summary.get("no_action_control_marker") is True,
        "not_run_is_distinct_from_passed": ui_summary.get("not_run_is_distinct_from_passed") is True,
    }
    non_live = {
        "live_streaming_not_implemented": loader_summary.get("live_stream_enabled") is False,
        "polling_not_enabled": loader_summary.get("polling_enabled") is False,
        "runtime_behavior_unchanged": loader_summary.get("runtime_behavior_changed") is False,
        "no_live_instrumentation_marker": not bool(markers.get("live_instrumentation_added")),
        "no_polling_marker": not bool(markers.get("polling_added")),
    }
    blockers = [label for key, label in POLICY_VIOLATION_LABELS.items() if markers.get(key)]
    return read_only, non_live, blockers


def _checkpoint_status(blocked: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blocked:
        return STATUS_BLOCKED
    if incomplete:
        return STATUS_INCOMPLETE
    return STATUS_FROZEN_WITH_WARNINGS if warnings else STATUS_FROZEN


def build_run_progress_visibility_branch_checkpoint(
    *,
    registry_data: Any = None,
    registry_load_error: str = "",
    source_visibility_contract_path: str | Path = DEFAULT_VISIBILITY_CONTRACT_PATH,
    source_visibility_contract: Any = None,
    source_visibility_contract_load_error: str = "",
    source_snapshot_loader_report_path: str | Path = DEFAULT_SNAPSHOT_LOADER_REPORT_PATH,
    source_snapshot_loader_report: Any = None,
    source_snapshot_loader_report_load_error: str = "",
    source_ui_panel_marker_path: str | Path = DEFAULT_UI_PANEL_MARKER_PATH,
    source_ui_panel_marker: str = "",
    source_ui_panel_marker_load_error: str = "",
    checkpoint_id: str = "",
    created_at: str = "",
    policy_violation_markers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the pure, report-only UX.RUN.CLOSE checkpoint record."""
    markers = dict(policy_violation_markers or {})
    phase_summary, phase_incomplete, phase_blocked = _phase_completion_summary(registry_data, registry_load_error)
    artifact_coverage, artifact_incomplete, artifact_blocked = _artifact_coverage(
        visibility_contract_path=source_visibility_contract_path,
        visibility_contract=source_visibility_contract,
        visibility_contract_error=source_visibility_contract_load_error,
        snapshot_loader_path=source_snapshot_loader_report_path,
        snapshot_loader=source_snapshot_loader_report,
        snapshot_loader_error=source_snapshot_loader_report_load_error,
    )
    contract_summary, contract_incomplete = _progress_contract_summary(source_visibility_contract)
    loader_summary, loader_incomplete, loader_blocked = _snapshot_loader_summary(source_snapshot_loader_report)
    ui_summary, ui_incomplete, ui_blocked = _ui_panel_summary(
        source_ui_panel_marker, source_ui_panel_marker_load_error, source_ui_panel_marker_path
    )
    read_only, non_live, marker_blocked = _verification(contract_summary, loader_summary, ui_summary, markers)
    verification_incomplete = [
        "read-only boundary verification is incomplete"
        for verified in (all(read_only.values()), all(non_live.values()))
        if not verified
    ]
    warnings = [
        str(item)
        for source in (source_visibility_contract, source_snapshot_loader_report)
        for item in _as_list(_as_dict(source).get("warnings"))
        if str(item)
    ]
    if all(non_live.values()):
        warnings.append("Live progress streaming and instrumentation remain intentionally unimplemented.")
    incomplete = _dedupe(phase_incomplete + artifact_incomplete + contract_incomplete + loader_incomplete + ui_incomplete + verification_incomplete)
    blocked = _dedupe(phase_blocked + artifact_blocked + loader_blocked + ui_blocked + marker_blocked + _artifact_runtime_blockers(source_visibility_contract))
    warnings = _dedupe(warnings)
    status = _checkpoint_status(blocked, incomplete, warnings)
    forbidden_runtime_changes = {
        "policy_violation_markers": {key: bool(markers.get(key)) for key in POLICY_VIOLATION_LABELS},
        "artifact_runtime_blockers": _artifact_runtime_blockers(source_visibility_contract),
        "all_forbidden_runtime_changes_absent": not blocked,
    }
    guardrails = {
        "report_only": True,
        "checkpoint_only": True,
        "runtime_behavior_changed": False,
        "model_call_performed": False,
        "worker_launch_performed": False,
        "patch_apply_performed": False,
        "validation_run_performed": False,
        "benchmark_run_performed": False,
        "approval_enforcement_changed": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "auth_behavior_changed": False,
        "automatic_authority_escalation": False,
    }
    verdicts = {
        STATUS_FROZEN: "UX.RUN.1-UX.RUN.3 are complete, safe, read-only, and frozen.",
        STATUS_FROZEN_WITH_WARNINGS: "UX.RUN.1-UX.RUN.3 are safely frozen; live streaming and instrumentation remain future work.",
        STATUS_INCOMPLETE: "UX.RUN.CLOSE cannot freeze the branch until incomplete evidence is resolved.",
        STATUS_BLOCKED: "UX.RUN.CLOSE is blocked by a forbidden runtime, authority, or action-control change.",
    }
    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "checkpoint_id": checkpoint_id or "ux-run-close-run-progress-visibility-branch-checkpoint",
        "created_at": created_at or _utc_now(),
        "guardrail_note": GUARDRAIL_NOTE,
        "checkpoint_status": status,
        "source_visibility_contract_path": _norm_path(source_visibility_contract_path),
        "source_snapshot_loader_report_path": _norm_path(source_snapshot_loader_report_path),
        "source_ui_panel_marker": _norm_path(source_ui_panel_marker_path),
        "phase_completion_summary": phase_summary,
        "artifact_coverage": artifact_coverage,
        "progress_stage_contract_summary": contract_summary,
        "snapshot_loader_summary": loader_summary,
        "ui_panel_summary": ui_summary,
        "read_only_boundary_verification": read_only,
        "non_live_instrumentation_verification": non_live,
        "forbidden_runtime_changes": forbidden_runtime_changes,
        "warnings": warnings,
        "blocked_reasons": blocked,
        "incomplete_reasons": incomplete,
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "alternative_next_phase": dict(ALTERNATIVE_NEXT_PHASE),
        "guardrails": guardrails,
        "boundaries": list(GUARDRAILS),
        "final_verdict": {
            "status": status,
            "ready_to_freeze": status in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS},
            "message": verdicts[status],
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
        },
    }


def _list_lines(values: Any) -> list[str]:
    items = _as_list(values)
    return [f"- {_md(json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, dict) else item)}" for item in items] or ["_None._"]


def _dict_lines(values: Any) -> list[str]:
    data = _as_dict(values)
    return [f"- `{_md(key)}`: {_md(json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value)}" for key, value in sorted(data.items())] or ["_None._"]


def render_run_progress_visibility_branch_checkpoint_markdown(report: dict[str, Any]) -> str:
    """Render the UX.RUN.CLOSE report without mutating it."""
    lines = [
        "# Run Progress Visibility Branch Checkpoint", "", f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}", "",
        "## Summary", "", f"- **Checkpoint id:** `{_md(report.get('checkpoint_id'))}`", f"- **Checkpoint status:** `{_md(report.get('checkpoint_status'))}`", "",
        "## Phase Completion", "",
    ]
    phase = _as_dict(report.get("phase_completion_summary"))
    lines.extend(_dict_lines({key: value for key, value in phase.items() if key != "phase_checks"}))
    if _as_list(phase.get("phase_checks")):
        lines.extend(["", "| Phase | Present | Status | Complete | Guardrails OK |", "|---|---|---|---|---|"])
        for check in _as_list(phase.get("phase_checks")):
            row = _as_dict(check)
            lines.append(f"| {_md(row.get('phase_id'))} | {_bool(row.get('present'))} | {_md(row.get('status'))} | {_bool(row.get('complete'))} | {_bool(row.get('guardrails_ok'))} |")
    sections = (
        ("Artifact Coverage", "artifact_coverage"),
        ("Progress Contract Summary", "progress_stage_contract_summary"),
        ("Snapshot Loader Summary", "snapshot_loader_summary"),
        ("UI Panel Summary", "ui_panel_summary"),
        ("Read-Only Boundary Verification", "read_only_boundary_verification"),
        ("Non-Live Instrumentation Verification", "non_live_instrumentation_verification"),
        ("Forbidden Runtime Changes", "forbidden_runtime_changes"),
    )
    for heading, key in sections:
        lines.extend(["", f"## {heading}", ""])
        lines.extend(_dict_lines(report.get(key)))
    for heading, key in (("Warnings", "warnings"), ("Blocked Reasons", "blocked_reasons"), ("Incomplete Reasons", "incomplete_reasons")):
        lines.extend(["", f"## {heading}", ""])
        lines.extend(_list_lines(report.get(key)))
    lines.extend(["", "## Final Verdict", ""])
    lines.extend(_dict_lines(report.get("final_verdict")))
    next_phase = _as_dict(report.get("recommended_next_phase"))
    lines.extend(["", "## Recommended Next Phase", "", f"- **Phase:** `{_md(next_phase.get('phase_id'))}`", f"- **Title:** {_md(next_phase.get('title'))}", f"- **Reason:** {_md(next_phase.get('reason'))}", "", "## Guardrails", ""])
    lines.extend(_list_lines(report.get("boundaries")))
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


def _load_text(path: Path) -> tuple[str, str]:
    try:
        return path.read_text(encoding="utf-8"), ""
    except OSError as exc:
        return "", f"{_norm_path(path)}: {exc}"


def write_run_progress_visibility_branch_checkpoint(
    *,
    repo_root: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    source_visibility_contract_path: str | Path = DEFAULT_VISIBILITY_CONTRACT_PATH,
    source_snapshot_loader_report_path: str | Path = DEFAULT_SNAPSHOT_LOADER_REPORT_PATH,
    source_ui_panel_marker_path: str | Path = DEFAULT_UI_PANEL_MARKER_PATH,
    checkpoint_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Read existing evidence and write UX.RUN.CLOSE JSON/Markdown artifacts."""
    root = Path(repo_root or ".")
    registry, registry_error = _load_json_object(_resolve(root, registry_path))
    contract, contract_error = _load_json_object(_resolve(root, source_visibility_contract_path))
    loader, loader_error = _load_json_object(_resolve(root, source_snapshot_loader_report_path))
    ui_marker, ui_error = _load_text(_resolve(root, source_ui_panel_marker_path))
    report = build_run_progress_visibility_branch_checkpoint(
        registry_data=registry,
        registry_load_error=registry_error,
        source_visibility_contract_path=source_visibility_contract_path,
        source_visibility_contract=contract,
        source_visibility_contract_load_error=contract_error,
        source_snapshot_loader_report_path=source_snapshot_loader_report_path,
        source_snapshot_loader_report=loader,
        source_snapshot_loader_report_load_error=loader_error,
        source_ui_panel_marker_path=source_ui_panel_marker_path,
        source_ui_panel_marker=ui_marker,
        source_ui_panel_marker_load_error=ui_error,
        checkpoint_id=checkpoint_id,
        created_at=created_at,
    )
    out = _resolve(root, output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    md_path = out / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_run_progress_visibility_branch_checkpoint_markdown(report), encoding="utf-8")
    return {"ok": report["checkpoint_status"] in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS}, "json_path": str(json_path), "md_path": str(md_path), "report": report}
