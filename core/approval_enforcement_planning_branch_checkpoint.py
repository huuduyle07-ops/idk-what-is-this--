"""HARDEN.CLOSE - Approval Enforcement Planning Branch Checkpoint.

Freezes HARDEN.N1-HARDEN.N4 as a completed, non-enforcing approval-enforcement
planning branch. This module is report-only: it reads local registry/artifact
evidence and writes checkpoint artifacts only. It does not enforce approvals,
validate live tokens, issue or consume tokens, approve or reject real actions,
change routes/auth/runtime behavior, call models, launch workers, invoke tools,
apply patches, run validation, run benchmarks, contact networks, or write a
database.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "approval_enforcement_planning_branch_checkpoint"
THIS_PHASE_ID = "HARDEN.CLOSE"
REQUIRED_HARDEN_PHASE_IDS: tuple[str, ...] = ("HARDEN.N1", "HARDEN.N2", "HARDEN.N3", "HARDEN.N4")

STATUS_FROZEN = "approval_enforcement_planning_branch_frozen"
STATUS_FROZEN_WITH_WARNINGS = "approval_enforcement_planning_branch_frozen_with_warnings"
STATUS_INCOMPLETE = "approval_enforcement_planning_branch_incomplete"
STATUS_BLOCKED = "approval_enforcement_planning_branch_blocked"

JSON_NAME = "approval_enforcement_planning_branch_checkpoint.json"
MD_NAME = "approval_enforcement_planning_branch_checkpoint.md"

DEFAULT_REGISTRY_PATH = Path("docs") / "roadmap" / "phase_registry.json"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "harden" / "approval_enforcement_planning_branch_checkpoint"
DEFAULT_READINESS_AUDIT_PATH = (
    Path(".agent") / "harden" / "approval_enforcement_readiness_audit" / "approval_enforcement_readiness_audit.json"
)
DEFAULT_ATTACHMENT_PLAN_PATH = (
    Path(".agent") / "harden" / "approval_enforcement_attachment_plan" / "approval_enforcement_attachment_plan.json"
)
DEFAULT_DRY_RUN_SIMULATOR_PATH = (
    Path(".agent")
    / "harden"
    / "approval_enforcement_dry_run_gate_simulator"
    / "approval_enforcement_dry_run_gate_simulator.json"
)
DEFAULT_OPERATOR_REPORT_PATH = (
    Path(".agent") / "harden" / "approval_enforcement_operator_report" / "approval_enforcement_operator_report.json"
)
DEFAULT_HUMAN_AUTHORITY_CHECKPOINT_PATH = (
    Path(".agent") / "human" / "authority_branch_checkpoint" / "human_authority_branch_checkpoint.json"
)
DEFAULT_TOKEN_CONTRACT_PATH = (
    Path(".agent") / "human" / "approval_token_contract" / "human_approval_token_contract.json"
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "OPS.TEST.1",
    "title": "Full Suite Runtime / Slow Test Audit",
    "reason": (
        "The approval-enforcement planning branch is frozen. The next biggest "
        "project pain is full pytest timing out around 304 seconds, so the next "
        "safe step is a report-only audit and suite-splitting plan before adding "
        "more runtime features."
    ),
    "alternatives": [
        {
            "phase_id": "UX.RUN.1",
            "title": "Run Progress / Operator Visibility",
            "reason": "Use this if operator visibility is more urgent than test-suite runtime.",
        }
    ],
}

GUARDRAIL_NOTE = (
    "HARDEN.CLOSE is report-only and checkpoint-only. It verifies that "
    "HARDEN.N1-N4 completed the approval-enforcement planning branch without "
    "installing runtime enforcement, token gates, token issuance/consumption, "
    "approval/rejection authority, or route/auth behavior changes."
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "checkpoint only",
    "no runtime enforcement",
    "no token validation gate",
    "no approval/rejection of real actions",
    "no token issuance",
    "no token consumption",
    "no model call",
    "no model routing",
    "no worker launch",
    "no patch apply",
    "no validation run",
    "no benchmark run",
    "no MCP/tool invocation",
    "no Dream execution",
    "no Replay janitor apply",
    "no Docker/subprocess execution except normal CLI script execution",
    "no network",
    "no database write",
    "no route behavior change",
    "no auth policy change",
    "no automatic authority escalation",
)

PHASE_GUARDRAIL_FIELDS: tuple[str, ...] = (
    "model_calls_allowed",
    "network_allowed",
    "merge_allowed",
    "writes_real_repo",
)

REQUIRED_ARTIFACTS: tuple[tuple[str, str, str, Path], ...] = (
    ("readiness_audit", "HARDEN.N1", "approval_enforcement_readiness_audit", DEFAULT_READINESS_AUDIT_PATH),
    ("attachment_plan", "HARDEN.N2", "approval_enforcement_attachment_plan", DEFAULT_ATTACHMENT_PLAN_PATH),
    (
        "dry_run_simulator",
        "HARDEN.N3",
        "approval_enforcement_dry_run_gate_simulator",
        DEFAULT_DRY_RUN_SIMULATOR_PATH,
    ),
    ("operator_report", "HARDEN.N4", "approval_enforcement_operator_report", DEFAULT_OPERATOR_REPORT_PATH),
)

OPTIONAL_ARTIFACTS: tuple[tuple[str, str, str, Path], ...] = (
    (
        "human_authority_checkpoint",
        "HUMAN.CLOSE",
        "human_authority_branch_checkpoint",
        DEFAULT_HUMAN_AUTHORITY_CHECKPOINT_PATH,
    ),
    ("token_contract", "HUMAN.N2", "human_approval_token_contract", DEFAULT_TOKEN_CONTRACT_PATH),
)

FORBIDDEN_MARKER_REASONS: dict[str, str] = {
    "approval_enforcement_added": "runtime_enforcement_added",
    "runtime_enforcement_added": "runtime_enforcement_added",
    "runtime_check_added": "runtime_enforcement_added",
    "enforcement_was_applied": "runtime_enforcement_added",
    "approval_gate_enforced": "runtime_enforcement_added",
    "approval_gate_added": "runtime_enforcement_added",
    "route_blocker_added": "runtime_enforcement_added",
    "token_validation_gate_added": "token_validation_gate_added",
    "approval_token_issuance_performed": "token_issuance_added",
    "token_issuance_performed": "token_issuance_added",
    "token_was_issued": "token_issuance_added",
    "token_issued": "token_issuance_added",
    "approval_token_consumption_performed": "token_consumption_added",
    "token_consumption_performed": "token_consumption_added",
    "token_was_consumed": "token_consumption_added",
    "token_consumed": "token_consumption_added",
    "route_behavior_changed": "route_behavior_changed",
    "auth_policy_changed": "auth_policy_changed",
    "route_or_auth_changed": "route_behavior_changed",
    "automatic_approval_allowed": "auto_approval_allowed",
    "auto_approval_allowed": "auto_approval_allowed",
    "auto_approve_allowed": "auto_approval_allowed",
    "automatic_rejection_allowed": "auto_rejection_allowed",
    "auto_rejection_allowed": "auto_rejection_allowed",
    "auto_reject_allowed": "auto_rejection_allowed",
    "hidden_mutation_allowed": "hidden_mutation_allowed",
    "simulated_allow_treated_as_real_authority": "simulated_allow_treated_as_real_authority",
    "sample_token_treated_as_real_authority": "simulated_allow_treated_as_real_authority",
    "sample_tokens_treated_as_real_authority": "simulated_allow_treated_as_real_authority",
    "approval_tokens_treated_as_real_authority": "simulated_allow_treated_as_real_authority",
    "authorizes_real_action": "simulated_allow_treated_as_real_authority",
    "real_dispatch_allowed": "simulated_allow_treated_as_real_authority",
}

FORBIDDEN_RUNTIME_KEYS: tuple[str, ...] = (
    "runtime_enforcement_added",
    "token_validation_gate_added",
    "token_issuance_added",
    "token_consumption_added",
    "route_behavior_changed",
    "auth_policy_changed",
    "auto_approval_allowed",
    "auto_rejection_allowed",
    "hidden_mutation_allowed",
    "simulated_allow_treated_as_real_authority",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm_path(value: str | Path | None) -> str:
    return str(value or "").replace("\\", "/")


def _resolve(repo: Path, path: str | Path) -> Path:
    raw = Path(path)
    return raw if raw.is_absolute() else repo / raw


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _bool(value: Any) -> str:
    return "true" if bool(value) else "false"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _read_json_object(repo: Path, path: str | Path, label: str) -> tuple[dict[str, Any] | None, str]:
    resolved = _resolve(repo, path)
    if not resolved.is_file():
        return None, f"{label} missing at {_norm_path(path)}"
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{label} unreadable at {_norm_path(path)}: {exc}"
    if not isinstance(data, dict):
        return None, f"{label} is not a JSON object at {_norm_path(path)}"
    return data, ""


def _artifact_summary(
    key: str,
    phase_id: str,
    path: str | Path,
    expected_kind: str,
    data: dict[str, Any] | None,
    error: str,
    required: bool,
) -> dict[str, Any]:
    return {
        "artifact_key": key,
        "phase_id": phase_id,
        "path": _norm_path(path),
        "required": required,
        "present": data is not None and not error,
        "expected_report_kind": expected_kind,
        "report_kind": data.get("report_kind") if isinstance(data, dict) else "",
        "report_kind_ok": bool(isinstance(data, dict) and data.get("report_kind") == expected_kind),
        "error": error,
    }


def _phase_map(registry_data: Any) -> dict[str, dict[str, Any]]:
    root = registry_data if isinstance(registry_data, dict) else {}
    phases = root.get("phases") if isinstance(root.get("phases"), list) else []
    return {
        str(phase["phase_id"]): phase
        for phase in phases
        if isinstance(phase, dict) and str(phase.get("phase_id", "")).strip()
    }


def _phase_guardrail_violations(phase: dict[str, Any]) -> list[str]:
    violations = [field for field in PHASE_GUARDRAIL_FIELDS if phase.get(field) is True]
    automation = str(phase.get("automation_level", ""))
    if automation not in {"LOCAL_0_OBSERVE", "LOCAL_1_PREPARE"}:
        violations.append(f"automation_level={automation or '(missing)'}")
    if phase.get("human_approval_required") is not True:
        violations.append("human_approval_required")
    return violations


def _phase_completion(registry_data: Any, registry_error: str, incomplete: list[str], blocked: list[str]) -> dict[str, Any]:
    if registry_error:
        incomplete.append(f"phase registry missing or unreadable: {registry_error}")
    phases = _phase_map(registry_data)
    checks: list[dict[str, Any]] = []
    for phase_id in REQUIRED_HARDEN_PHASE_IDS:
        phase = phases.get(phase_id)
        present = phase is not None
        complete = present and phase.get("status") == "complete"
        violations = _phase_guardrail_violations(phase) if present else []
        if not present:
            incomplete.append(f"{phase_id} phase is missing")
        elif not complete:
            incomplete.append(f"{phase_id} is not registered complete")
        for violation in violations:
            blocked.append(f"{phase_id} unsafe registry guardrail: {violation}")
        checks.append(
            {
                "phase_id": phase_id,
                "present": present,
                "status": str(phase.get("status", "(missing)")) if present else "(missing)",
                "complete": complete,
                "guardrails_ok": present and not violations,
                "guardrail_violations": violations,
            }
        )

    this_phase = phases.get(THIS_PHASE_ID)
    this_present = this_phase is not None
    this_complete = this_present and this_phase.get("status") == "complete"
    this_violations = _phase_guardrail_violations(this_phase) if this_present else []
    if not this_present:
        incomplete.append(f"{THIS_PHASE_ID} phase is missing")
    elif not this_complete:
        incomplete.append(f"{THIS_PHASE_ID} is not registered complete")
    for violation in this_violations:
        blocked.append(f"{THIS_PHASE_ID} unsafe registry guardrail: {violation}")

    return {
        "required_phase_ids": list(REQUIRED_HARDEN_PHASE_IDS),
        "phase_checks": checks,
        "all_required_harden_phases_complete": all(check["complete"] for check in checks),
        "all_required_harden_phase_guardrails_ok": all(check["guardrails_ok"] for check in checks),
        "this_phase_id": THIS_PHASE_ID,
        "this_phase_registered": this_present,
        "this_phase_complete": this_complete,
        "this_phase_guardrails_ok": this_present and not this_violations,
        "this_phase_guardrail_violations": this_violations,
    }


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "allowed", "enabled"}
    return bool(value)


def _scan_forbidden_markers(value: Any, source: str) -> tuple[dict[str, bool], list[str]]:
    flags = {key: False for key in FORBIDDEN_RUNTIME_KEYS}
    reasons: list[str] = []

    def mark(reason: str, path: str) -> None:
        flags[reason] = True
        reasons.append(f"{reason} marker is enabled at {source}:{path or '(root)'}")

    def walk(item: Any, trail: str) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                key_text = str(key)
                key_low = key_text.lower()
                child_path = f"{trail}.{key_text}" if trail else key_text
                reason = FORBIDDEN_MARKER_REASONS.get(key_low)
                if reason and _truthy(child):
                    mark(reason, child_path)
                walk(child, child_path)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{trail}[{index}]")

    walk(value, "")
    return flags, reasons


def _combine_flags(*flag_sets: dict[str, bool]) -> dict[str, bool]:
    combined = {key: False for key in FORBIDDEN_RUNTIME_KEYS}
    for flags in flag_sets:
        for key in combined:
            combined[key] = combined[key] or bool(flags.get(key))
    return combined


def _artifact_warnings(*artifacts: dict[str, Any] | None) -> list[str]:
    warnings: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        raw = artifact.get("warnings")
        if isinstance(raw, list):
            warnings.extend(str(item) for item in raw)
    return _dedupe(warnings)


def _artifact_blockers(*artifacts: dict[str, Any] | None) -> list[str]:
    blockers: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        raw = artifact.get("blocked_reasons")
        if isinstance(raw, list):
            blockers.extend(str(item) for item in raw)
    return _dedupe(blockers)


def _artifact_incomplete(*artifacts: dict[str, Any] | None) -> list[str]:
    reasons: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        raw = artifact.get("incomplete_reasons")
        if isinstance(raw, list):
            reasons.extend(str(item) for item in raw)
    return _dedupe(reasons)


def _dangerous_action_coverage(readiness: dict[str, Any] | None, incomplete: list[str]) -> dict[str, Any]:
    data = readiness if isinstance(readiness, dict) else {}
    findings = data.get("action_surface_findings") if isinstance(data.get("action_surface_findings"), list) else []
    categories = sorted(
        {
            str(item.get("action_category"))
            for item in findings
            if isinstance(item, dict) and str(item.get("action_category", "")).strip()
        }
    )
    mapped = int(data.get("mapped_action_count") or len(categories) or 0)
    unmapped = int(data.get("unmapped_action_count") or 0)
    maps_surfaces = bool(categories) and mapped > 0 and unmapped == 0
    if not maps_surfaces:
        incomplete.append("dangerous action surface coverage cannot be verified from HARDEN.N1")
    return {
        "source_phase_id": "HARDEN.N1",
        "action_surface_count": int(data.get("action_surface_count") or len(categories) or 0),
        "mapped_action_count": mapped,
        "unmapped_action_count": unmapped,
        "action_categories": categories,
        "maps_dangerous_action_surfaces": maps_surfaces,
    }


def _attachment_plan_coverage(attachment: dict[str, Any] | None, incomplete: list[str]) -> dict[str, Any]:
    data = attachment if isinstance(attachment, dict) else {}
    items = data.get("attachment_items") if isinstance(data.get("attachment_items"), list) else []
    matrix = data.get("dangerous_action_attachment_matrix")
    matrix_items = matrix if isinstance(matrix, list) else []
    categories = sorted(
        {
            str(item.get("action_category"))
            for item in items
            if isinstance(item, dict) and str(item.get("action_category", "")).strip()
        }
    )
    attachment_points = sum(
        len(item.get("proposed_attachment_points") or item.get("attachment_points") or [])
        for item in items
        if isinstance(item, dict)
    )
    missing_count = int(data.get("missing_action_count") or 0)
    enforcement_allowed = [
        str(item.get("action_category", "(unknown)"))
        for item in items
        if isinstance(item, dict) and item.get("enforcement_allowed_now") is True
    ]
    plans_points = bool(categories) and (attachment_points > 0 or bool(matrix_items)) and missing_count == 0
    if enforcement_allowed:
        incomplete.append("attachment plan permits enforcement before a future phase")
    if not plans_points:
        incomplete.append("attachment plan coverage cannot be verified from HARDEN.N2")
    return {
        "source_phase_id": "HARDEN.N2",
        "attachment_item_count": int(data.get("attachment_item_count") or len(items) or 0),
        "planned_action_count": int(data.get("planned_action_count") or len(categories) or 0),
        "missing_action_count": missing_count,
        "action_categories": categories,
        "attachment_point_count": attachment_points,
        "matrix_item_count": len(matrix_items),
        "enforcement_allowed_now_categories": enforcement_allowed,
        "plans_future_attachment_points": plans_points and not enforcement_allowed,
    }


def _simulation_summary(simulator: dict[str, Any] | None, flags: dict[str, bool], incomplete: list[str]) -> dict[str, Any]:
    data = simulator if isinstance(simulator, dict) else {}
    results = data.get("simulation_results") if isinstance(data.get("simulation_results"), list) else []
    decisions: dict[str, int] = {}
    all_simulated_only = bool(results)
    for result in results:
        if not isinstance(result, dict):
            all_simulated_only = False
            continue
        decision = str(result.get("simulated_decision") or "simulation_incomplete")
        decisions[decision] = decisions.get(decision, 0) + 1
        boundary = result.get("boundary_result") if isinstance(result.get("boundary_result"), dict) else {}
        all_simulated_only = all_simulated_only and (
            result.get("enforcement_was_applied") is not True
            and boundary.get("runtime_enforcement_added") is not True
            and boundary.get("simulation_only", True) is True
        )
    if not results:
        incomplete.append("dry-run simulator has no simulation results")
    if not all_simulated_only:
        incomplete.append("dry-run simulator results are not all simulation-only")
    return {
        "source_phase_id": "HARDEN.N3",
        "simulator_status": str(data.get("simulator_status") or data.get("simulation_status") or ""),
        "scenario_count": int(data.get("sample_scenario_count") or len(results) or 0),
        "decision_summary": data.get("decision_counts") if isinstance(data.get("decision_counts"), dict) else decisions,
        "allow_count": decisions.get("would_allow_with_valid_token", 0),
        "deny_count": sum(count for decision, count in decisions.items() if decision.startswith("would_deny")),
        "block_count": sum(count for decision, count in decisions.items() if decision.startswith("would_block")),
        "simulates_approval_decisions_only": all_simulated_only and not flags["runtime_enforcement_added"],
        "simulated_allow_is_not_real_authority": not flags["simulated_allow_treated_as_real_authority"],
    }


def _operator_report_summary(operator: dict[str, Any] | None, flags: dict[str, bool], incomplete: list[str]) -> dict[str, Any]:
    data = operator if isinstance(operator, dict) else {}
    items = data.get("operator_review_items") if isinstance(data.get("operator_review_items"), list) else []
    all_simulated_only = bool(items) and all(isinstance(item, dict) and item.get("simulated_only") is True for item in items)
    if not items:
        incomplete.append("operator report has no operator review items")
    if not all_simulated_only:
        incomplete.append("operator report items are not all simulated-only")
    decision_summary = data.get("decision_summary") if isinstance(data.get("decision_summary"), dict) else {}
    return {
        "source_phase_id": "HARDEN.N4",
        "report_status": str(data.get("report_status") or ""),
        "scenario_count": int(data.get("scenario_count") or len(items) or 0),
        "decision_summary": decision_summary,
        "allow_count": len(data.get("allow_simulations") or []),
        "deny_count": len(data.get("deny_simulations") or []),
        "block_count": len(data.get("block_simulations") or []),
        "warning_count": len(data.get("warning_simulations") or []),
        "operator_review_item_count": len(items),
        "summarizes_simulated_outcomes_only": all_simulated_only and not flags["runtime_enforcement_added"],
        "runtime_behavior_changed": bool(data.get("runtime_behavior_changed")),
    }


def _non_enforcement_verification(flags: dict[str, bool]) -> dict[str, bool]:
    return {
        "no_runtime_enforcement_added": not flags["runtime_enforcement_added"],
        "no_token_validation_gate": not flags["token_validation_gate_added"],
        "no_token_issuance_added": not flags["token_issuance_added"],
        "no_token_consumption_added": not flags["token_consumption_added"],
        "no_route_behavior_change": not flags["route_behavior_changed"],
        "no_auth_policy_change": not flags["auth_policy_changed"],
        "no_approval_rejection_of_real_actions": True,
        "auto_approval_blocked": not flags["auto_approval_allowed"],
        "auto_rejection_blocked": not flags["auto_rejection_allowed"],
        "hidden_mutation_blocked": not flags["hidden_mutation_allowed"],
        "simulated_allow_is_not_real_authority": not flags["simulated_allow_treated_as_real_authority"],
        "planning_only": True,
        "future_enforcement_requires_separate_phase": True,
    }


def _guardrails(flags: dict[str, bool]) -> dict[str, bool]:
    return {
        "report_only": True,
        "checkpoint_only": True,
        "writes_checkpoint_artifacts_only": True,
        "no_runtime_enforcement": not flags["runtime_enforcement_added"],
        "no_token_validation_gate": not flags["token_validation_gate_added"],
        "no_approval_rejection_of_real_actions": True,
        "no_token_issuance": not flags["token_issuance_added"],
        "no_token_consumption": not flags["token_consumption_added"],
        "no_model_call": True,
        "no_model_routing": True,
        "no_worker_launch": True,
        "no_patch_apply": True,
        "no_validation_run": True,
        "no_benchmark_run": True,
        "no_mcp_tool_invocation": True,
        "no_dream_execution": True,
        "no_replay_janitor_apply": True,
        "no_docker_subprocess_execution_except_cli": True,
        "no_network": True,
        "no_database_write": True,
        "no_route_behavior_change": not flags["route_behavior_changed"],
        "no_auth_policy_change": not flags["auth_policy_changed"],
        "no_automatic_authority_escalation": (
            not flags["auto_approval_allowed"]
            and not flags["auto_rejection_allowed"]
            and not flags["hidden_mutation_allowed"]
            and not flags["simulated_allow_treated_as_real_authority"]
        ),
    }


def _status(blocked: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blocked:
        return STATUS_BLOCKED
    if incomplete:
        return STATUS_INCOMPLETE
    if warnings:
        return STATUS_FROZEN_WITH_WARNINGS
    return STATUS_FROZEN


def _final_verdict(status: str) -> dict[str, Any]:
    return {
        "status": status,
        "branch_frozen": status == STATUS_FROZEN,
        "branch_frozen_with_warnings": status == STATUS_FROZEN_WITH_WARNINGS,
        "ready_for_next_phase": status in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS},
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
        "message": {
            STATUS_BLOCKED: "Approval-enforcement planning branch is blocked by forbidden runtime or authority markers.",
            STATUS_INCOMPLETE: "Approval-enforcement planning branch is missing required phases or artifact coverage.",
            STATUS_FROZEN_WITH_WARNINGS: (
                "Approval-enforcement planning branch is complete and safe to freeze, with warnings because runtime "
                "enforcement remains intentionally unimplemented."
            ),
            STATUS_FROZEN: "Approval-enforcement planning branch is frozen as planning-only evidence.",
        }[status],
    }


def build_approval_enforcement_planning_branch_checkpoint(
    *,
    repo_root: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    source_readiness_audit_path: str | Path = DEFAULT_READINESS_AUDIT_PATH,
    source_attachment_plan_path: str | Path = DEFAULT_ATTACHMENT_PLAN_PATH,
    source_dry_run_simulator_path: str | Path = DEFAULT_DRY_RUN_SIMULATOR_PATH,
    source_operator_report_path: str | Path = DEFAULT_OPERATOR_REPORT_PATH,
    source_human_authority_checkpoint_path: str | Path = DEFAULT_HUMAN_AUTHORITY_CHECKPOINT_PATH,
    source_token_contract_path: str | Path = DEFAULT_TOKEN_CONTRACT_PATH,
    checkpoint_id: str = "",
    created_at: str = "",
    runtime_change_markers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a report-only HARDEN.CLOSE checkpoint from registry/artifact evidence."""
    repo = Path(repo_root or ".").resolve()

    registry_data, registry_error = _read_json_object(repo, registry_path, "phase registry")
    readiness, readiness_error = _read_json_object(repo, source_readiness_audit_path, "HARDEN.N1 readiness audit")
    attachment, attachment_error = _read_json_object(repo, source_attachment_plan_path, "HARDEN.N2 attachment plan")
    simulator, simulator_error = _read_json_object(repo, source_dry_run_simulator_path, "HARDEN.N3 dry-run simulator")
    operator, operator_error = _read_json_object(repo, source_operator_report_path, "HARDEN.N4 operator report")
    human_close, human_close_error = _read_json_object(
        repo, source_human_authority_checkpoint_path, "HUMAN.CLOSE checkpoint"
    )
    token_contract, token_contract_error = _read_json_object(repo, source_token_contract_path, "HUMAN.N2 token contract")

    incomplete: list[str] = []
    blocked: list[str] = []
    phase_completion = _phase_completion(registry_data, registry_error, incomplete, blocked)

    artifact_rows: list[dict[str, Any]] = []
    for key, phase_id, expected_kind, path, data, error in (
        (
            "readiness_audit",
            "HARDEN.N1",
            "approval_enforcement_readiness_audit",
            source_readiness_audit_path,
            readiness,
            readiness_error,
        ),
        (
            "attachment_plan",
            "HARDEN.N2",
            "approval_enforcement_attachment_plan",
            source_attachment_plan_path,
            attachment,
            attachment_error,
        ),
        (
            "dry_run_simulator",
            "HARDEN.N3",
            "approval_enforcement_dry_run_gate_simulator",
            source_dry_run_simulator_path,
            simulator,
            simulator_error,
        ),
        (
            "operator_report",
            "HARDEN.N4",
            "approval_enforcement_operator_report",
            source_operator_report_path,
            operator,
            operator_error,
        ),
    ):
        row = _artifact_summary(key, phase_id, path, expected_kind, data, error, True)
        artifact_rows.append(row)
        if not row["present"]:
            incomplete.append(f"{key.replace('_', ' ')} artifact is missing or unreadable: {error}")
        elif not row["report_kind_ok"]:
            incomplete.append(f"{key.replace('_', ' ')} artifact has unexpected report_kind")

    for key, phase_id, expected_kind, path, data, error in (
        (
            "human_authority_checkpoint",
            "HUMAN.CLOSE",
            "human_authority_branch_checkpoint",
            source_human_authority_checkpoint_path,
            human_close,
            human_close_error,
        ),
        ("token_contract", "HUMAN.N2", "human_approval_token_contract", source_token_contract_path, token_contract, token_contract_error),
    ):
        artifact_rows.append(_artifact_summary(key, phase_id, path, expected_kind, data, error, False))

    scan_sets: list[dict[str, bool]] = []
    scan_reasons: list[str] = []
    for source, artifact in (
        ("readiness_audit", readiness),
        ("attachment_plan", attachment),
        ("dry_run_simulator", simulator),
        ("operator_report", operator),
        ("human_authority_checkpoint", human_close),
        ("token_contract", token_contract),
        ("runtime_change_markers", runtime_change_markers or {}),
    ):
        flags, reasons = _scan_forbidden_markers(artifact, source)
        scan_sets.append(flags)
        scan_reasons.extend(reasons)
    flags = _combine_flags(*scan_sets)

    dangerous_action_coverage = _dangerous_action_coverage(readiness, incomplete)
    attachment_plan_coverage = _attachment_plan_coverage(attachment, incomplete)
    simulation_summary = _simulation_summary(simulator, flags, incomplete)
    operator_report_summary = _operator_report_summary(operator, flags, incomplete)
    non_enforcement = _non_enforcement_verification(flags)
    forbidden_runtime_changes = dict(flags)
    forbidden_runtime_changes["all_clear"] = not any(flags.values())
    blocked.extend(scan_reasons)
    blocked.extend(_artifact_blockers(readiness, attachment, simulator, operator))
    incomplete.extend(_artifact_incomplete(readiness, attachment, simulator, operator))

    warnings = _artifact_warnings(readiness, attachment, simulator, operator, human_close, token_contract)
    if not warnings:
        warnings.append("Runtime approval enforcement remains intentionally unimplemented by HARDEN.CLOSE.")
    if human_close_error:
        warnings.append(f"optional HUMAN.CLOSE checkpoint unavailable: {human_close_error}")
    if token_contract_error:
        warnings.append(f"optional HUMAN.N2 token contract unavailable: {token_contract_error}")

    blocked = _dedupe(blocked)
    incomplete = _dedupe(incomplete)
    warnings = _dedupe(warnings)
    status = _status(blocked, incomplete, warnings)

    artifact_coverage = {
        "artifact_checks": artifact_rows,
        "required_artifacts_present": all(row["present"] and row["report_kind_ok"] for row in artifact_rows if row["required"]),
        "optional_artifacts_present": all(row["present"] and row["report_kind_ok"] for row in artifact_rows if not row["required"]),
        "required_artifact_count": sum(1 for row in artifact_rows if row["required"]),
        "optional_artifact_count": sum(1 for row in artifact_rows if not row["required"]),
    }

    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "checkpoint_id": str(checkpoint_id or "harden-close-approval-enforcement-planning-branch-checkpoint"),
        "created_at": str(created_at or _utc_now()),
        "guardrail_note": GUARDRAIL_NOTE,
        "checkpoint_status": status,
        "repo_root": _norm_path(repo),
        "registry_path": _norm_path(registry_path),
        "source_readiness_audit_path": _norm_path(source_readiness_audit_path),
        "source_attachment_plan_path": _norm_path(source_attachment_plan_path),
        "source_dry_run_simulator_path": _norm_path(source_dry_run_simulator_path),
        "source_operator_report_path": _norm_path(source_operator_report_path),
        "source_human_authority_checkpoint_path": _norm_path(source_human_authority_checkpoint_path),
        "source_token_contract_path": _norm_path(source_token_contract_path),
        "phase_completion_summary": phase_completion,
        "artifact_coverage": artifact_coverage,
        "dangerous_action_coverage": dangerous_action_coverage,
        "attachment_plan_coverage": attachment_plan_coverage,
        "simulation_summary": simulation_summary,
        "operator_report_summary": operator_report_summary,
        "non_enforcement_verification": non_enforcement,
        "forbidden_runtime_changes": forbidden_runtime_changes,
        "warnings": warnings,
        "blocked_reasons": blocked,
        "incomplete_reasons": incomplete,
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "final_verdict": _final_verdict(status),
        "guardrails": _guardrails(flags),
        "boundaries": list(BOUNDARIES),
    }


def _dict_lines(values: Any) -> list[str]:
    if not isinstance(values, dict) or not values:
        return ["_None._"]
    lines: list[str] = []
    for key in sorted(values):
        value = values[key]
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f"- `{_md(key)}`: {_md(value)}")
    return lines


def _list_lines(values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        return ["_None._"]
    lines: list[str] = []
    for value in values:
        if isinstance(value, dict):
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            text = str(value)
        lines.append(f"- {_md(text)}")
    return lines


def render_approval_enforcement_planning_branch_checkpoint_markdown(report: dict[str, Any]) -> str:
    """Render a HARDEN.CLOSE checkpoint report as Markdown."""
    lines: list[str] = [
        "# Approval Enforcement Planning Branch Checkpoint",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Checkpoint id:** `{_md(report.get('checkpoint_id'))}`",
        f"- **Created at:** `{_md(report.get('created_at'))}`",
        f"- **Checkpoint status:** `{_md(report.get('checkpoint_status'))}`",
        "",
        "## Phase Completion",
        "",
    ]
    phase = report.get("phase_completion_summary") if isinstance(report.get("phase_completion_summary"), dict) else {}
    lines.extend(_dict_lines({key: value for key, value in phase.items() if key != "phase_checks"}))
    checks = phase.get("phase_checks") if isinstance(phase.get("phase_checks"), list) else []
    if checks:
        lines.extend(["", "| Phase | Present | Status | Complete | Guardrails OK |", "|---|---|---|---|---|"])
        for check in checks:
            lines.append(
                f"| {_md(check.get('phase_id'))} | {_bool(check.get('present'))} | "
                f"{_md(check.get('status'))} | {_bool(check.get('complete'))} | "
                f"{_bool(check.get('guardrails_ok'))} |"
            )

    lines.extend(["", "## Artifact Coverage", ""])
    coverage = report.get("artifact_coverage") if isinstance(report.get("artifact_coverage"), dict) else {}
    artifact_checks = coverage.get("artifact_checks") if isinstance(coverage.get("artifact_checks"), list) else []
    if artifact_checks:
        lines.extend(["| Artifact | Phase | Required | Present | Kind OK | Path |", "|---|---|---|---|---|---|"])
        for check in artifact_checks:
            lines.append(
                f"| {_md(check.get('artifact_key'))} | {_md(check.get('phase_id'))} | "
                f"{_bool(check.get('required'))} | {_bool(check.get('present'))} | "
                f"{_bool(check.get('report_kind_ok'))} | `{_md(check.get('path'))}` |"
            )
    else:
        lines.append("_None._")

    for title, key in (
        ("Dangerous Action Coverage", "dangerous_action_coverage"),
        ("Attachment Plan Coverage", "attachment_plan_coverage"),
        ("Dry-Run Simulation Summary", "simulation_summary"),
        ("Operator Report Summary", "operator_report_summary"),
        ("Non-Enforcement Verification", "non_enforcement_verification"),
        ("Forbidden Runtime Changes", "forbidden_runtime_changes"),
    ):
        lines.extend(["", f"## {title}", ""])
        lines.extend(_dict_lines(report.get(key)))

    lines.extend(["", "## Warnings", ""])
    lines.extend(_list_lines(report.get("warnings")))
    lines.extend(["", "## Blocked Reasons", ""])
    lines.extend(_list_lines(report.get("blocked_reasons")))
    lines.extend(["", "## Incomplete Reasons", ""])
    lines.extend(_list_lines(report.get("incomplete_reasons")))
    lines.extend(["", "## Final Verdict", ""])
    lines.extend(_dict_lines(report.get("final_verdict")))

    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    lines.extend(
        [
            "",
            "## Recommended Next Phase",
            "",
            f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
            f"- **Title:** {_md(next_phase.get('title', ''))}",
            f"- **Reason:** {_md(next_phase.get('reason', ''))}",
        ]
    )
    alternatives = next_phase.get("alternatives") if isinstance(next_phase.get("alternatives"), list) else []
    for alternative in alternatives:
        if isinstance(alternative, dict):
            lines.append(
                f"- **Alternative:** `{_md(alternative.get('phase_id', ''))}` - {_md(alternative.get('title', ''))}"
            )

    lines.extend(["", "## Guardrails", ""])
    lines.extend(_list_lines(report.get("boundaries")))
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: `{str(bool(guardrails[key])).lower()}`")
    lines.append("")
    return "\n".join(lines)


def write_approval_enforcement_planning_branch_checkpoint(
    *,
    repo_root: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    source_readiness_audit_path: str | Path = DEFAULT_READINESS_AUDIT_PATH,
    source_attachment_plan_path: str | Path = DEFAULT_ATTACHMENT_PLAN_PATH,
    source_dry_run_simulator_path: str | Path = DEFAULT_DRY_RUN_SIMULATOR_PATH,
    source_operator_report_path: str | Path = DEFAULT_OPERATOR_REPORT_PATH,
    source_human_authority_checkpoint_path: str | Path = DEFAULT_HUMAN_AUTHORITY_CHECKPOINT_PATH,
    source_token_contract_path: str | Path = DEFAULT_TOKEN_CONTRACT_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    checkpoint_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build and write HARDEN.CLOSE JSON/Markdown checkpoint artifacts."""
    report = build_approval_enforcement_planning_branch_checkpoint(
        repo_root=repo_root,
        registry_path=registry_path,
        source_readiness_audit_path=source_readiness_audit_path,
        source_attachment_plan_path=source_attachment_plan_path,
        source_dry_run_simulator_path=source_dry_run_simulator_path,
        source_operator_report_path=source_operator_report_path,
        source_human_authority_checkpoint_path=source_human_authority_checkpoint_path,
        source_token_contract_path=source_token_contract_path,
        checkpoint_id=checkpoint_id,
        created_at=created_at,
    )
    out = Path(output_dir)
    if not out.is_absolute():
        out = Path(repo_root or ".") / out
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    md_path = out / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_approval_enforcement_planning_branch_checkpoint_markdown(report), encoding="utf-8")
    return {
        "ok": report["checkpoint_status"] in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
