"""HARDEN.N2 - Approval Enforcement Attachment Plan.

Plans where future approval-token checks could attach to dangerous action
surfaces found by HARDEN.N1. This module is report-only and plan-only: it reads
local artifacts and writes plan artifacts only. It does not validate approval
tokens, issue or consume tokens, block routes, change auth policy, call models,
route models, launch workers, apply patches, run validation or benchmarks,
invoke tools, contact networks, write databases, or approve/reject work.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "approval_enforcement_attachment_plan"
THIS_PHASE_ID = "HARDEN.N2"

STATUS_READY = "approval_enforcement_attachment_plan_ready"
STATUS_READY_WITH_WARNINGS = "approval_enforcement_attachment_plan_ready_with_warnings"
STATUS_INCOMPLETE = "approval_enforcement_attachment_plan_incomplete"
STATUS_BLOCKED = "approval_enforcement_attachment_plan_blocked"

JSON_NAME = "approval_enforcement_attachment_plan.json"
MD_NAME = "approval_enforcement_attachment_plan.md"

DEFAULT_OUTPUT_ROOT = Path(".agent") / "harden" / "approval_enforcement_attachment_plan"
DEFAULT_REGISTRY_PATH = Path("docs") / "roadmap" / "phase_registry.json"
DEFAULT_READINESS_AUDIT_PATH = (
    Path(".agent")
    / "harden"
    / "approval_enforcement_readiness_audit"
    / "approval_enforcement_readiness_audit.json"
)
DEFAULT_APPROVAL_CONTRACT_PATH = (
    Path(".agent") / "human" / "approval_token_contract" / "human_approval_token_contract.json"
)
DEFAULT_HUMAN_CHECKPOINT_PATH = (
    Path(".agent") / "human" / "authority_branch_checkpoint" / "human_authority_branch_checkpoint.json"
)

ACTION_CATEGORIES: tuple[str, ...] = (
    "patch_apply",
    "direct_file_mutation",
    "worker_launch",
    "model_call",
    "model_routing",
    "validation_run",
    "benchmark_run",
    "mcp_tool_invocation",
    "network_access",
    "subprocess_execution",
    "docker_execution",
    "database_write",
    "auth_policy_change",
    "route_behavior_change",
    "registry_mutation",
    "model_catalog_adoption",
    "replay_apply",
    "dream_execution",
    "remote_execution",
    "approval_token_issuance",
    "approval_token_consumption",
    "automatic_approval",
    "automatic_rejection",
    "hidden_mutation",
)

PREFERRED_ATTACHMENT_LAYERS: tuple[str, ...] = (
    "ui_confirmation_surface",
    "route_precheck",
    "service_layer_precheck",
    "command_dispatch_precheck",
    "file_write_precheck",
    "worker_dispatch_precheck",
    "model_dispatch_precheck",
    "tool_dispatch_precheck",
    "validation_dispatch_precheck",
    "benchmark_dispatch_precheck",
    "registry_write_precheck",
    "auth_policy_precheck",
    "blocked_forever",
    "not_applicable",
)

REQUIRED_TOKEN_FIELDS: tuple[str, ...] = (
    "token_id",
    "approval_action",
    "target_type",
    "target_id",
    "risk_level",
    "confirmation_text",
    "confirmation_scope",
    "created_at",
    "single_use",
)

COMMON_CONTEXT_FIELDS: tuple[str, ...] = (
    "action_category",
    "approval_action",
    "target_type",
    "target_id",
    "risk_level",
    "requested_by",
    "source_phase",
    "boundary_refs",
    "evidence_refs",
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "HARDEN.N3",
    "title": "Approval Enforcement Dry-Run Gate Simulator",
    "reason": (
        "Simulate future approval-gate pass/fail behavior with sample action "
        "requests and sample tokens before any runtime gate is installed."
    ),
}

ALTERNATIVE_NEXT_PHASE = {
    "phase_id": "HARDEN.CLOSE",
    "title": "Hardening Branch Freeze Checkpoint",
    "reason": "Freeze hardening after N2 if the operator wants no further approval-gate planning.",
}

GUARDRAIL_NOTE = (
    "HARDEN.N2 is report-only and plan-only. It maps where future approval "
    "checks could attach; it does not install gates, validate tokens, issue or "
    "consume tokens, block routes, change auth, or enforce approvals."
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "plan-only",
    "no runtime enforcement",
    "no token validation gate",
    "no approval/rejection",
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
    "writes plan artifacts only",
)

RUNTIME_MARKER_LABELS: dict[str, str] = {
    "approval_enforcement_added": "approval enforcement was added unexpectedly",
    "token_validation_gate_added": "token validation gate was added unexpectedly",
    "route_blocker_added": "route blocker was added unexpectedly",
    "runtime_check_added": "runtime approval check was added unexpectedly",
    "auth_policy_changed": "auth policy changed unexpectedly",
    "route_behavior_changed": "route behavior changed unexpectedly",
    "automatic_approval_allowed": "automatic approval is allowed",
    "automatic_rejection_allowed": "automatic rejection is allowed",
    "hidden_mutation_allowed": "hidden mutation is allowed",
    "approval_tokens_treated_as_real_authority": "approval tokens are treated as real authority",
    "approval_token_issuance_performed": "approval token issuance was performed",
    "approval_token_consumption_performed": "approval token consumption was performed",
    "model_call_performed": "model call was performed",
    "model_routing_performed": "model routing was performed",
    "worker_launch_performed": "worker launch was performed",
    "patch_apply_performed": "patch apply was performed",
    "validation_run_performed": "validation run was performed",
    "benchmark_run_performed": "benchmark run was performed",
    "mcp_invocation_performed": "MCP/tool invocation was performed",
    "network_contacted": "network access was performed",
    "database_write_performed": "database write was performed",
    "dream_execution_performed": "Dream execution was performed",
    "replay_apply_performed": "Replay apply was performed",
    "docker_or_subprocess_used": "Docker/subprocess execution was performed",
    "approval_or_rejection_performed": "approval or rejection was performed",
}

APPROVAL_ACTIONS: dict[str, str | None] = {
    "patch_apply": "approve_patch_apply",
    "direct_file_mutation": "approve_patch_apply",
    "worker_launch": "approve_worker_launch",
    "model_call": "approve_network_access",
    "model_routing": "approve_model_catalog_adoption",
    "validation_run": "approve_validation_run",
    "benchmark_run": "approve_benchmark_run",
    "mcp_tool_invocation": "approve_mcp_tool_invocation",
    "network_access": "approve_network_access",
    "subprocess_execution": "approve_remote_execution",
    "docker_execution": "approve_remote_execution",
    "database_write": "approve_database_write",
    "auth_policy_change": "approve_auth_policy_change",
    "route_behavior_change": "approve_auth_policy_change",
    "registry_mutation": "approve_registry_mutation",
    "model_catalog_adoption": "approve_model_catalog_adoption",
    "replay_apply": "approve_replay_apply",
    "dream_execution": "approve_dream_execution",
    "remote_execution": "approve_remote_execution",
    "approval_token_issuance": None,
    "approval_token_consumption": None,
    "automatic_approval": None,
    "automatic_rejection": None,
    "hidden_mutation": None,
}

PREFERRED_LAYER_BY_CATEGORY: dict[str, str] = {
    "patch_apply": "route_precheck",
    "direct_file_mutation": "file_write_precheck",
    "worker_launch": "worker_dispatch_precheck",
    "model_call": "model_dispatch_precheck",
    "model_routing": "model_dispatch_precheck",
    "validation_run": "validation_dispatch_precheck",
    "benchmark_run": "benchmark_dispatch_precheck",
    "mcp_tool_invocation": "tool_dispatch_precheck",
    "network_access": "tool_dispatch_precheck",
    "subprocess_execution": "command_dispatch_precheck",
    "docker_execution": "command_dispatch_precheck",
    "database_write": "service_layer_precheck",
    "auth_policy_change": "auth_policy_precheck",
    "route_behavior_change": "route_precheck",
    "registry_mutation": "registry_write_precheck",
    "model_catalog_adoption": "registry_write_precheck",
    "replay_apply": "command_dispatch_precheck",
    "dream_execution": "command_dispatch_precheck",
    "remote_execution": "command_dispatch_precheck",
    "approval_token_issuance": "not_applicable",
    "approval_token_consumption": "not_applicable",
    "automatic_approval": "blocked_forever",
    "automatic_rejection": "blocked_forever",
    "hidden_mutation": "blocked_forever",
}

ATTACHMENT_POINTS: dict[str, list[str]] = {
    "patch_apply": ["patch review route before source write", "patch application service boundary"],
    "direct_file_mutation": ["file mutation adapter before write dispatch", "artifact writer boundary"],
    "worker_launch": ["worker task planner before enqueue", "worker dispatch service boundary"],
    "model_call": ["model provider adapter before outbound call", "model request builder boundary"],
    "model_routing": ["model role resolver before executable routing", "model catalog adoption boundary"],
    "validation_run": ["validation plan runner before command execution", "safe validation dispatch boundary"],
    "benchmark_run": ["benchmark runner before suite execution", "benchmark report creation boundary"],
    "mcp_tool_invocation": ["tool registry invocation boundary", "MCP dispatch adapter"],
    "network_access": ["network request adapter", "remote integration dispatch boundary"],
    "subprocess_execution": ["process execution adapter", "command runner boundary"],
    "docker_execution": ["container execution adapter", "Docker launch boundary"],
    "database_write": ["repository write adapter", "durable persistence boundary"],
    "auth_policy_change": ["auth policy configuration boundary", "security review route before auth edit"],
    "route_behavior_change": ["route registration review boundary", "web route mutation planning boundary"],
    "registry_mutation": ["phase registry writer", "registry update script boundary"],
    "model_catalog_adoption": ["model catalog adoption receipt writer", "model role registry writer"],
    "replay_apply": ["Replay janitor apply dispatcher", "replay mutation service boundary"],
    "dream_execution": ["Dream run dispatcher", "dream trial execution boundary"],
    "remote_execution": ["remote command adapter", "remote workflow dispatch boundary"],
    "approval_token_issuance": ["future approval-token issuance phase, not HARDEN.N2"],
    "approval_token_consumption": ["future approval-token consumption phase, not HARDEN.N2"],
    "automatic_approval": ["No attachment point; blocked forever."],
    "automatic_rejection": ["No attachment point; blocked forever."],
    "hidden_mutation": ["No attachment point; blocked forever."],
}

CONFIRMATION_SURFACES: dict[str, str] = {
    "patch_apply": "Patch review UI showing diff, target files, risk, and explicit apply wording.",
    "direct_file_mutation": "File-write confirmation surface listing exact paths and artifact evidence.",
    "worker_launch": "Worker launch confirmation surface listing task, branch/worktree, and allowed files.",
    "model_call": "Model/network confirmation surface listing provider, purpose, cost/risk, and evidence refs.",
    "model_routing": "Model catalog confirmation surface listing routing intent and advisory-only evidence.",
    "validation_run": "Validation confirmation surface listing commands, sandbox posture, and expected outputs.",
    "benchmark_run": "Benchmark confirmation surface listing benchmark scope and runtime risk.",
    "mcp_tool_invocation": "Tool confirmation surface listing tool name, arguments, and side-effect class.",
    "network_access": "Network confirmation surface listing endpoint class, data sent, and purpose.",
    "subprocess_execution": "Command confirmation surface listing executable, arguments, cwd, and sandbox.",
    "docker_execution": "Container confirmation surface listing image/context, mounts, and command.",
    "database_write": "Database confirmation surface listing target store, mutation kind, and rollback notes.",
    "auth_policy_change": "Security confirmation surface listing auth policy delta and operator impact.",
    "route_behavior_change": "Route confirmation surface listing route/method behavior and regression risk.",
    "registry_mutation": "Registry confirmation surface listing phase ids, statuses, and validation evidence.",
    "model_catalog_adoption": "Model catalog confirmation surface listing catalog version and advisory boundary.",
    "replay_apply": "Replay confirmation surface listing target actions and mutation evidence.",
    "dream_execution": "Dream confirmation surface listing run intent, sandbox, and mutation boundary.",
    "remote_execution": "Remote execution confirmation surface listing remote target and command class.",
    "approval_token_issuance": "Not planned here; future issuance phase must design this surface separately.",
    "approval_token_consumption": "Not planned here; future consumption phase must design this surface separately.",
    "automatic_approval": "No confirmation surface; behavior remains forbidden.",
    "automatic_rejection": "No confirmation surface; behavior remains forbidden.",
    "hidden_mutation": "No confirmation surface; behavior remains forbidden.",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm_path(value: str | Path | None) -> str:
    return str(value or "").replace("\\", "/")


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _bool(value: Any) -> str:
    return str(bool(value)).lower()


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _resolve(repo: Path, path: str | Path) -> Path:
    source = Path(path)
    return source if source.is_absolute() else repo / source


def _read_json_object(repo: Path, path: str | Path, label: str) -> tuple[dict[str, Any] | None, str]:
    source = _resolve(repo, path)
    try:
        raw = source.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"{label} could not be read: {exc}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"{label} must contain valid JSON: {exc.msg}"
    if not isinstance(data, dict):
        return None, f"{label} must contain a JSON object"
    return data, ""


def _artifact_summary(
    *,
    phase_id: str,
    path: str | Path,
    data: dict[str, Any] | None,
    error: str,
    expected_kind: str,
    required: bool,
) -> dict[str, Any]:
    report_kind = str(data.get("report_kind") or "") if isinstance(data, dict) else ""
    return {
        "phase_id": phase_id,
        "path": _norm_path(path),
        "present": data is not None and not error,
        "required": required,
        "report_kind": report_kind,
        "expected_report_kind": expected_kind,
        "report_kind_ok": bool(data is not None and report_kind == expected_kind),
        "error": error,
    }


def _source_artifacts(
    *,
    repo: Path,
    readiness_audit_path: str | Path,
    approval_contract_path: str | Path,
    human_checkpoint_path: str | Path,
    route_inventory_path: str | Path | None,
    audit_inventory_path: str | Path | None,
) -> tuple[dict[str, dict[str, Any] | None], list[dict[str, Any]], list[str]]:
    readiness, readiness_error = _read_json_object(repo, readiness_audit_path, "HARDEN.N1 readiness audit")
    contract, contract_error = _read_json_object(repo, approval_contract_path, "HUMAN.N2 approval contract")
    human_close, human_close_error = _read_json_object(repo, human_checkpoint_path, "HUMAN.CLOSE checkpoint")

    route_inventory = None
    route_inventory_error = ""
    if route_inventory_path:
        route_inventory, route_inventory_error = _read_json_object(repo, route_inventory_path, "optional route inventory")

    audit_inventory = None
    audit_inventory_error = ""
    if audit_inventory_path:
        audit_inventory, audit_inventory_error = _read_json_object(repo, audit_inventory_path, "optional audit inventory")

    artifacts = [
        _artifact_summary(
            phase_id="HARDEN.N1",
            path=readiness_audit_path,
            data=readiness,
            error=readiness_error,
            expected_kind="approval_enforcement_readiness_audit",
            required=True,
        ),
        _artifact_summary(
            phase_id="HUMAN.N2",
            path=approval_contract_path,
            data=contract,
            error=contract_error,
            expected_kind="human_approval_token_contract",
            required=True,
        ),
        _artifact_summary(
            phase_id="HUMAN.CLOSE",
            path=human_checkpoint_path,
            data=human_close,
            error=human_close_error,
            expected_kind="human_authority_branch_checkpoint",
            required=True,
        ),
    ]
    if route_inventory_path:
        artifacts.append(
            _artifact_summary(
                phase_id="OPTIONAL.ROUTE_INVENTORY",
                path=route_inventory_path,
                data=route_inventory,
                error=route_inventory_error,
                expected_kind="route_inventory",
                required=False,
            )
        )
    if audit_inventory_path:
        artifacts.append(
            _artifact_summary(
                phase_id="OPTIONAL.AUDIT_INVENTORY",
                path=audit_inventory_path,
                data=audit_inventory,
                error=audit_inventory_error,
                expected_kind="audit_inventory",
                required=False,
            )
        )

    incomplete: list[str] = []
    for artifact in artifacts:
        if not artifact["required"]:
            continue
        if not artifact["present"]:
            incomplete.append(f"{artifact['phase_id']} source artifact missing or unreadable: {artifact['error']}")
        elif not artifact["report_kind_ok"]:
            incomplete.append(
                f"{artifact['phase_id']} source artifact report_kind is {artifact['report_kind']!r}, "
                f"expected {artifact['expected_report_kind']!r}"
            )

    return {
        "readiness_audit": readiness,
        "approval_contract": contract,
        "human_checkpoint": human_close,
        "route_inventory": route_inventory,
        "audit_inventory": audit_inventory,
    }, artifacts, incomplete


def _token_required_fields(contract: dict[str, Any] | None) -> list[str]:
    if isinstance(contract, dict):
        schema = contract.get("token_schema")
        if isinstance(schema, dict):
            fields = schema.get("required_fields")
            if isinstance(fields, list) and all(isinstance(field, str) for field in fields):
                return list(fields)
        fields = contract.get("required_fields")
        if isinstance(fields, list) and all(isinstance(field, str) for field in fields):
            return list(fields)
    return list(REQUIRED_TOKEN_FIELDS)


def _allowed_approval_actions(contract: dict[str, Any] | None) -> set[str]:
    values = contract.get("allowed_approval_actions") if isinstance(contract, dict) else []
    return {str(value) for value in values} if isinstance(values, list) else set()


def _status_for_category(category: str) -> str:
    if category in {"automatic_approval", "automatic_rejection", "hidden_mutation"}:
        return "forbidden_boundary"
    if category in {"approval_token_issuance", "approval_token_consumption"}:
        return "future_separate_phase"
    return "existing_dangerous_surface"


def _human_boundary_level(category: str) -> str:
    if category in {"automatic_approval", "automatic_rejection", "hidden_mutation"}:
        return "blocked_forever"
    if category in {"approval_token_issuance", "approval_token_consumption"}:
        return "future_separate_phase"
    return "future_human_approval_required"


def _not_before_phase(category: str) -> str:
    if category == "approval_token_issuance":
        return "future separate approval-token issuance phase"
    if category == "approval_token_consumption":
        return "future separate approval-token consumption phase"
    if category in {"automatic_approval", "automatic_rejection", "hidden_mutation"}:
        return "never"
    return "HARDEN.N3 or later dry-run/simulation phase"


def _required_token_fields_for_category(category: str, token_fields: list[str]) -> list[str]:
    if category in {
        "approval_token_issuance",
        "approval_token_consumption",
        "automatic_approval",
        "automatic_rejection",
        "hidden_mutation",
    }:
        return []
    return list(token_fields)


def _precheck_sequence(category: str) -> list[str]:
    if category in {"automatic_approval", "automatic_rejection", "hidden_mutation"}:
        return [
            "Keep behavior forbidden.",
            "Do not create an approval token path.",
            "Record any attempted design as blocked before implementation.",
        ]
    if category in {"approval_token_issuance", "approval_token_consumption"}:
        return [
            "Defer to a future approval-token authority phase.",
            "Require separate design for issuance or consumption semantics.",
            "Do not implement token authority in HARDEN.N2.",
        ]
    return [
        "Construct a complete action request context.",
        "Display human confirmation evidence before dispatch.",
        "In a future phase, check token fields and context fields before the dangerous action.",
        "In a future phase, write an audit-log decision before any runtime dispatch.",
    ]


def _failure_mode_later(category: str) -> str:
    if category in {"automatic_approval", "automatic_rejection", "hidden_mutation"}:
        return "Future systems must fail closed by refusing to create any authorization path."
    if category in {"approval_token_issuance", "approval_token_consumption"}:
        return "Future token authority work must fail closed until a separate contract exists."
    return "A future gate would fail closed before dispatch and leave runtime state unchanged."


def _bypass_risks(category: str) -> list[str]:
    if category in {"automatic_approval", "automatic_rejection", "hidden_mutation"}:
        return [
            "Accidentally granting implicit authority would bypass the human boundary.",
            "Hidden state changes could avoid review evidence.",
        ]
    if category in {"approval_token_issuance", "approval_token_consumption"}:
        return [
            "Conflating token planning with authority could create a real gate too early.",
            "Issuance or consumption rules require separate replay and audit semantics.",
        ]
    return [
        "Alternate code path could dispatch without the future precheck.",
        "Incomplete context could make a future token appear broader than intended.",
        "Audit evidence could be written after the action instead of before it.",
    ]


def _rollback_considerations(category: str) -> list[str]:
    if category in {"automatic_approval", "automatic_rejection", "hidden_mutation"}:
        return ["Rollback means removing any attempted authority path and preserving a blocked record."]
    if category in {"approval_token_issuance", "approval_token_consumption"}:
        return ["Rollback belongs to the future token authority phase, not HARDEN.N2."]
    return [
        "Future enforcement should be removable by disabling the precheck layer.",
        "Dangerous action inputs should remain inspectable after a denied future precheck.",
    ]


def _audit_log_requirements(category: str) -> list[str]:
    base = [
        "action_category",
        "approval_action",
        "target_type",
        "target_id",
        "decision",
        "evidence_refs",
        "boundary_refs",
    ]
    if category in {"automatic_approval", "automatic_rejection", "hidden_mutation"}:
        return ["action_category", "blocked_reason", "boundary_refs", "evidence_refs"]
    if category in {"approval_token_issuance", "approval_token_consumption"}:
        return ["action_category", "deferred_reason", "future_phase", "boundary_refs"]
    return base


def _notes_for_category(category: str) -> str:
    if category in {"automatic_approval", "automatic_rejection", "hidden_mutation"}:
        return "No future approval token may authorize this behavior."
    if category in {"approval_token_issuance", "approval_token_consumption"}:
        return "Token authority is not implemented in HARDEN.N2 and must remain a future separate phase."
    return "Attachment point is a future design candidate only; no runtime gate is installed by HARDEN.N2."


def _default_item(category: str, token_fields: list[str]) -> dict[str, Any]:
    return {
        "action_category": category,
        "approval_action": APPROVAL_ACTIONS[category],
        "current_runtime_status": _status_for_category(category),
        "human_boundary_level": _human_boundary_level(category),
        "proposed_attachment_points": list(ATTACHMENT_POINTS[category]),
        "preferred_attachment_layer": PREFERRED_LAYER_BY_CATEGORY[category],
        "required_token_fields": _required_token_fields_for_category(category, token_fields),
        "required_context_fields": list(COMMON_CONTEXT_FIELDS),
        "precheck_sequence": _precheck_sequence(category),
        "failure_mode_later": _failure_mode_later(category),
        "bypass_risks": _bypass_risks(category),
        "rollback_considerations": _rollback_considerations(category),
        "user_confirmation_surface": CONFIRMATION_SURFACES[category],
        "audit_log_requirements": _audit_log_requirements(category),
        "not_before_phase": _not_before_phase(category),
        "enforcement_allowed_now": False,
        "notes": _notes_for_category(category),
    }


def _copy_items(
    *,
    token_fields: list[str],
    attachment_items: dict[str, Any] | None,
    attachment_overrides: dict[str, dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    source_categories = set(ACTION_CATEGORIES) if attachment_items is None else {str(key) for key in attachment_items}
    missing = [category for category in ACTION_CATEGORIES if category not in source_categories]
    overrides = dict(attachment_overrides or {})
    out: list[dict[str, Any]] = []
    for category in ACTION_CATEGORIES:
        if category in missing:
            continue
        item = _default_item(category, token_fields)
        if attachment_items is not None:
            raw = attachment_items.get(category)
            if isinstance(raw, dict):
                item.update(raw)
        override = overrides.get(category)
        if isinstance(override, dict):
            item.update(override)
        out.append(item)
    return out, missing


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "none"}
    return bool(value)


def _runtime_blockers(runtime_change_markers: dict[str, Any] | None) -> list[str]:
    markers = dict(runtime_change_markers or {})
    blockers: list[str] = []
    for key, message in RUNTIME_MARKER_LABELS.items():
        if _truthy(markers.get(key, False)):
            blockers.append(message)
    return blockers


def _guardrails(runtime_change_markers: dict[str, Any] | None = None) -> dict[str, bool]:
    markers = dict(runtime_change_markers or {})
    data = {key: False for key in RUNTIME_MARKER_LABELS}
    for key in data:
        data[key] = _truthy(markers.get(key, False))
    data["report_only"] = True
    data["plan_only"] = True
    data["writes_plan_artifacts_only"] = True
    return data


def _runtime_confirmation(runtime_change_markers: dict[str, Any] | None = None) -> dict[str, bool]:
    guardrails = _guardrails(runtime_change_markers)
    return {
        "no_approval_enforcement_added": not guardrails["approval_enforcement_added"],
        "no_token_validation_gate_added": not guardrails["token_validation_gate_added"],
        "no_route_blocker_added": not guardrails["route_blocker_added"],
        "no_runtime_check_added": not guardrails["runtime_check_added"],
        "no_auth_policy_change": not guardrails["auth_policy_changed"],
        "no_route_behavior_change": not guardrails["route_behavior_changed"],
        "no_token_issuance": not guardrails["approval_token_issuance_performed"],
        "no_token_consumption": not guardrails["approval_token_consumption_performed"],
        "no_model_calls": not guardrails["model_call_performed"],
        "no_model_routing": not guardrails["model_routing_performed"],
        "no_worker_launch": not guardrails["worker_launch_performed"],
        "no_patch_apply": not guardrails["patch_apply_performed"],
        "no_validation_run": not guardrails["validation_run_performed"],
        "no_benchmark_run": not guardrails["benchmark_run_performed"],
        "no_mcp_invocation": not guardrails["mcp_invocation_performed"],
        "no_network": not guardrails["network_contacted"],
        "no_database_write": not guardrails["database_write_performed"],
        "no_automatic_approval": not guardrails["automatic_approval_allowed"],
        "no_automatic_rejection": not guardrails["automatic_rejection_allowed"],
        "no_hidden_mutation": not guardrails["hidden_mutation_allowed"],
    }


def _item_blockers(items: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    for item in items:
        category = str(item.get("action_category") or "")
        if _truthy(item.get("enforcement_allowed_now")):
            blockers.append(f"{category} has enforcement_allowed_now true")
        if category in {"automatic_approval", "automatic_rejection", "hidden_mutation"}:
            if item.get("preferred_attachment_layer") != "blocked_forever":
                blockers.append(f"{category} must use blocked_forever attachment layer")
            if item.get("approval_action") is not None:
                blockers.append(f"{category} must not have an approval action")
        if category in {"approval_token_issuance", "approval_token_consumption"}:
            if item.get("preferred_attachment_layer") != "not_applicable":
                blockers.append(f"{category} must remain not_applicable in HARDEN.N2")
    return blockers


def _item_incomplete(items: list[dict[str, Any]]) -> list[str]:
    incomplete: list[str] = []
    for item in items:
        category = str(item.get("action_category") or "")
        for key in (
            "approval_action",
            "current_runtime_status",
            "human_boundary_level",
            "proposed_attachment_points",
            "preferred_attachment_layer",
            "required_token_fields",
            "required_context_fields",
            "precheck_sequence",
            "failure_mode_later",
            "bypass_risks",
            "rollback_considerations",
            "user_confirmation_surface",
            "audit_log_requirements",
            "not_before_phase",
            "enforcement_allowed_now",
            "notes",
        ):
            if key not in item:
                incomplete.append(f"{category} missing {key}")
        if item.get("preferred_attachment_layer") not in PREFERRED_ATTACHMENT_LAYERS:
            incomplete.append(f"{category} has unknown preferred attachment layer")
        if not item.get("proposed_attachment_points"):
            incomplete.append(f"{category} lacks proposed attachment points")
    return incomplete


def _status(blockers: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blockers:
        return STATUS_BLOCKED
    if incomplete:
        return STATUS_INCOMPLETE
    if warnings:
        return STATUS_READY_WITH_WARNINGS
    return STATUS_READY


def _matrix(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "action_category": item.get("action_category"),
            "approval_action": item.get("approval_action"),
            "preferred_attachment_layer": item.get("preferred_attachment_layer"),
            "attachment_points": item.get("proposed_attachment_points"),
            "enforcement_allowed_now": item.get("enforcement_allowed_now"),
            "not_before_phase": item.get("not_before_phase"),
        }
        for item in items
    ]


def _blocked_forever_actions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "action_category": item.get("action_category"),
            "reason": item.get("notes"),
            "preferred_attachment_layer": item.get("preferred_attachment_layer"),
        }
        for item in items
        if item.get("preferred_attachment_layer") == "blocked_forever"
    ]


def build_approval_enforcement_attachment_plan(
    *,
    repo_root: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    source_readiness_audit_path: str | Path = DEFAULT_READINESS_AUDIT_PATH,
    source_approval_contract_path: str | Path = DEFAULT_APPROVAL_CONTRACT_PATH,
    source_human_checkpoint_path: str | Path = DEFAULT_HUMAN_CHECKPOINT_PATH,
    optional_route_inventory_path: str | Path | None = None,
    optional_audit_inventory_path: str | Path | None = None,
    plan_id: str = "",
    created_at: str = "",
    attachment_items: dict[str, Any] | None = None,
    attachment_overrides: dict[str, dict[str, Any]] | None = None,
    runtime_change_markers: dict[str, Any] | None = None,
    approval_tokens_treated_as_real_authority: bool = False,
) -> dict[str, Any]:
    """Build the HARDEN.N2 report-only approval enforcement attachment plan."""
    repo = Path(repo_root or ".").resolve()
    source_data, source_artifacts, incomplete = _source_artifacts(
        repo=repo,
        readiness_audit_path=source_readiness_audit_path,
        approval_contract_path=source_approval_contract_path,
        human_checkpoint_path=source_human_checkpoint_path,
        route_inventory_path=optional_route_inventory_path,
        audit_inventory_path=optional_audit_inventory_path,
    )
    contract = source_data["approval_contract"]
    token_fields = _token_required_fields(contract)
    allowed_actions = _allowed_approval_actions(contract)
    items, missing = _copy_items(
        token_fields=token_fields,
        attachment_items=attachment_items,
        attachment_overrides=attachment_overrides,
    )

    blockers = _runtime_blockers(runtime_change_markers)
    if approval_tokens_treated_as_real_authority:
        blockers.append("approval tokens are treated as real authority in HARDEN.N2")

    for category in missing:
        incomplete.append(f"{category} required dangerous action category is missing")

    for item in items:
        action = item.get("approval_action")
        category = str(item.get("action_category") or "")
        if action and allowed_actions and action not in allowed_actions:
            blockers.append(f"{category} approval action {action} contradicts HUMAN.N2")

    blockers.extend(_item_blockers(items))
    incomplete.extend(_item_incomplete(items))

    runtime_confirmation = _runtime_confirmation(runtime_change_markers)
    enforcement_not_implemented = all(runtime_confirmation.values()) and not approval_tokens_treated_as_real_authority
    if not enforcement_not_implemented:
        blockers.append("runtime non-enforcement confirmation failed")

    warnings = [
        "Future enforcement remains intentionally unimplemented in HARDEN.N2.",
        "HARDEN.N3 should simulate future gates before any route, auth, or token-validation behavior changes.",
    ]
    readiness = source_data["readiness_audit"] or {}
    readiness_warnings = readiness.get("warnings") if isinstance(readiness, dict) else []
    if isinstance(readiness_warnings, list) and readiness_warnings:
        warnings.append(f"HARDEN.N1 has {len(readiness_warnings)} readiness warning(s).")

    blockers = _dedupe(blockers)
    incomplete = _dedupe(incomplete)
    warnings = _dedupe(warnings)
    status = _status(blockers, incomplete, warnings)

    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "plan_id": str(plan_id or ""),
        "created_at": str(created_at or _utc_now()),
        "guardrail_note": GUARDRAIL_NOTE,
        "plan_status": status,
        "source_readiness_audit_path": _norm_path(source_readiness_audit_path),
        "source_approval_contract_path": _norm_path(source_approval_contract_path),
        "source_human_checkpoint_path": _norm_path(source_human_checkpoint_path),
        "source_artifacts": source_artifacts,
        "attachment_item_count": len(items),
        "planned_action_count": len(items),
        "missing_action_count": len(missing),
        "missing_action_categories": missing,
        "enforcement_not_implemented_confirmed": enforcement_not_implemented,
        "approval_tokens_treated_as_real_authority": bool(approval_tokens_treated_as_real_authority),
        "attachment_philosophy": {
            "summary": (
                "Attach future gates at the narrowest dispatch boundary before a dangerous side effect, "
                "after evidence is shown to a human, and before any runtime mutation or external call."
            ),
            "boundary": "HARDEN.N2 only plans attachment points; it does not attach them.",
            "preferred_sequence": [
                "collect action context",
                "show confirmation surface",
                "future token precheck",
                "future audit-log decision",
                "future dispatch only if allowed",
            ],
        },
        "attachment_items": items,
        "dangerous_action_attachment_matrix": _matrix(items),
        "token_field_requirements": {
            "required_fields": token_fields,
            "validation_gate_implemented": False,
            "issuance_implemented": False,
            "consumption_implemented": False,
            "source": "HUMAN.N2 approval token contract",
        },
        "confirmation_surface_plan": {
            str(item.get("action_category")): item.get("user_confirmation_surface")
            for item in items
        },
        "audit_log_plan": {
            str(item.get("action_category")): item.get("audit_log_requirements")
            for item in items
        },
        "bypass_risk_analysis": {
            str(item.get("action_category")): item.get("bypass_risks")
            for item in items
        },
        "rollback_considerations": {
            str(item.get("action_category")): item.get("rollback_considerations")
            for item in items
        },
        "blocked_forever_actions": _blocked_forever_actions(items),
        "future_enforcement_boundary": {
            "enforcement_allowed_now": False,
            "not_before_phase": "HARDEN.N3 dry-run simulator or later explicit implementation phase",
            "forbidden_now": list(BOUNDARIES),
        },
        "runtime_non_enforcement_confirmation": runtime_confirmation,
        "warnings": warnings,
        "blocked_reasons": blockers,
        "incomplete_reasons": incomplete,
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "alternative_next_phase": dict(ALTERNATIVE_NEXT_PHASE),
        "final_verdict": {
            "status": status,
            "ready_for_dry_run_simulator_phase": status in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
            "message": (
                "Approval enforcement attachment points are planned with warnings because future enforcement is absent."
                if status == STATUS_READY_WITH_WARNINGS
                else f"Approval enforcement attachment plan status is {status}."
            ),
        },
        "guardrails": _guardrails(runtime_change_markers),
        "boundaries": list(BOUNDARIES),
        "registry_path": _norm_path(registry_path),
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


def render_approval_enforcement_attachment_plan_markdown(report: dict[str, Any]) -> str:
    """Render the HARDEN.N2 attachment plan as Markdown."""
    lines: list[str] = [
        "# Approval Enforcement Attachment Plan",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Plan status:** `{_md(report.get('plan_status', ''))}`",
        f"- **Attachment items:** {report.get('attachment_item_count', 0)}",
        f"- **Missing actions:** {report.get('missing_action_count', 0)}",
        f"- **Runtime enforcement implemented:** `{str(not bool(report.get('enforcement_not_implemented_confirmed'))).lower()}`",
        "",
        "## Source Artifacts",
        "",
    ]
    artifacts = report.get("source_artifacts") if isinstance(report.get("source_artifacts"), list) else []
    if artifacts:
        lines.extend(["| Phase | Present | Kind OK | Path |", "|---|---|---|---|"])
        for artifact in artifacts:
            lines.append(
                f"| {_md(artifact.get('phase_id'))} | {_bool(artifact.get('present'))} | "
                f"{_bool(artifact.get('report_kind_ok'))} | `{_md(artifact.get('path'))}` |"
            )
    else:
        lines.append("_None._")

    lines.extend(["", "## Attachment Philosophy", ""])
    lines.extend(_dict_lines(report.get("attachment_philosophy")))

    lines.extend(["", "## Dangerous Action Attachment Matrix", ""])
    items = report.get("attachment_items") if isinstance(report.get("attachment_items"), list) else []
    if items:
        lines.extend(
            [
                "| Category | Approval action | Layer | Enforce now | Not before |",
                "|---|---|---|---|---|",
            ]
        )
        for item in items:
            lines.append(
                "| {cat} | `{action}` | `{layer}` | `{enforce}` | {phase} |".format(
                    cat=_md(item.get("action_category")),
                    action=_md(item.get("approval_action")),
                    layer=_md(item.get("preferred_attachment_layer")),
                    enforce=_bool(item.get("enforcement_allowed_now")),
                    phase=_md(item.get("not_before_phase")),
                )
            )
    else:
        lines.append("_None._")

    lines.extend(["", "## Token Field Requirements", ""])
    lines.extend(_dict_lines(report.get("token_field_requirements")))
    lines.extend(["", "## Confirmation Surface Plan", ""])
    lines.extend(_dict_lines(report.get("confirmation_surface_plan")))
    lines.extend(["", "## Audit Log Plan", ""])
    lines.extend(_dict_lines(report.get("audit_log_plan")))
    lines.extend(["", "## Bypass Risk Analysis", ""])
    lines.extend(_dict_lines(report.get("bypass_risk_analysis")))
    lines.extend(["", "## Rollback Considerations", ""])
    lines.extend(_dict_lines(report.get("rollback_considerations")))
    lines.extend(["", "## Blocked-Forever Actions", ""])
    lines.extend(_list_lines(report.get("blocked_forever_actions")))
    lines.extend(["", "## Future Enforcement Boundary", ""])
    lines.extend(_dict_lines(report.get("future_enforcement_boundary")))
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
            "",
            "## Guardrails",
            "",
        ]
    )
    lines.extend(_list_lines(report.get("boundaries")))
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: `{str(bool(guardrails[key])).lower()}`")
    lines.append("")
    return "\n".join(lines)


def write_approval_enforcement_attachment_plan(
    *,
    repo_root: str | Path = ".",
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    source_readiness_audit_path: str | Path = DEFAULT_READINESS_AUDIT_PATH,
    source_approval_contract_path: str | Path = DEFAULT_APPROVAL_CONTRACT_PATH,
    source_human_checkpoint_path: str | Path = DEFAULT_HUMAN_CHECKPOINT_PATH,
    optional_route_inventory_path: str | Path | None = None,
    optional_audit_inventory_path: str | Path | None = None,
    plan_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build and write HARDEN.N2 JSON/Markdown plan artifacts."""
    report = build_approval_enforcement_attachment_plan(
        repo_root=repo_root,
        registry_path=registry_path,
        source_readiness_audit_path=source_readiness_audit_path,
        source_approval_contract_path=source_approval_contract_path,
        source_human_checkpoint_path=source_human_checkpoint_path,
        optional_route_inventory_path=optional_route_inventory_path,
        optional_audit_inventory_path=optional_audit_inventory_path,
        plan_id=plan_id,
        created_at=created_at,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_approval_enforcement_attachment_plan_markdown(report), encoding="utf-8")
    return {
        "ok": report["plan_status"] in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
