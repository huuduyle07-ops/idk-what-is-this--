"""HARDEN.N1 - Approval Enforcement Readiness Audit.

Maps dangerous runtime action categories to future HUMAN.N2 approval-token
requirements and candidate enforcement attachment points. This module is
report-only: it reads local JSON artifacts and writes audit artifacts only. It
does not add approval enforcement, validate tokens, add route blockers, change
auth policy, run validation or benchmarks, invoke tools, call models, launch
workers, apply patches, or approve/reject work.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "approval_enforcement_readiness_audit"
THIS_PHASE_ID = "HARDEN.N1"

STATUS_READY = "approval_enforcement_readiness_ready"
STATUS_READY_WITH_WARNINGS = "approval_enforcement_readiness_ready_with_warnings"
STATUS_INCOMPLETE = "approval_enforcement_readiness_incomplete"
STATUS_BLOCKED = "approval_enforcement_readiness_blocked"

JSON_NAME = "approval_enforcement_readiness_audit.json"
MD_NAME = "approval_enforcement_readiness_audit.md"

DEFAULT_OUTPUT_ROOT = Path(".agent") / "harden" / "approval_enforcement_readiness_audit"
DEFAULT_REGISTRY_PATH = Path("docs") / "roadmap" / "phase_registry.json"
DEFAULT_HUMAN_BOUNDARY_PATH = Path(".agent") / "human" / "review_boundary_map" / "human_review_boundary_map.json"
DEFAULT_APPROVAL_CONTRACT_PATH = (
    Path(".agent") / "human" / "approval_token_contract" / "human_approval_token_contract.json"
)
DEFAULT_HUMAN_CHECKPOINT_PATH = (
    Path(".agent") / "human" / "authority_branch_checkpoint" / "human_authority_branch_checkpoint.json"
)
DEFAULT_DRY_RUN_VALIDATOR_PATH = Path("core") / "human_approval_token_dry_run_validator.py"
DEFAULT_SAMPLE_CATALOG_PATH = (
    Path(".agent")
    / "human"
    / "approval_token_sample_catalog"
    / "human_approval_token_sample_catalog.json"
)
DEFAULT_MODEL_ADOPTION_CHECKPOINT_PATH = (
    Path(".agent")
    / "model_role_registry"
    / "adoption_checkpoint"
    / "model_role_catalog_adoption_checkpoint.json"
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
    "dream_execution",
    "replay_apply",
    "remote_execution",
    "automatic_approval",
    "automatic_rejection",
    "hidden_mutation",
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "HARDEN.N2",
    "title": "Approval Enforcement Design Plan",
    "reason": (
        "Use the HARDEN.N1 attachment map to design approval enforcement before "
        "any runtime token gate or route behavior changes are implemented."
    ),
}

GUARDRAIL_NOTE = (
    "HARDEN.N1 is report-only and audit-only. It maps where future approval "
    "enforcement could attach; it does not attach enforcement, validate tokens, "
    "block routes, change auth, or approve/reject work."
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "audit-only",
    "no approval enforcement",
    "no token validation gate",
    "no route blocker",
    "no auth policy change",
    "no route behavior change",
    "no model calls",
    "no model routing",
    "no worker launch",
    "no executable binding",
    "no patch apply",
    "no validation run",
    "no benchmark run",
    "no MCP/tool invocation",
    "no Dream execution",
    "no Replay janitor apply",
    "no Docker/subprocess execution",
    "no network",
    "no database write",
    "no automatic approval/rejection",
    "no automatic authority escalation",
    "writes audit artifacts only",
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

HUMAN_N1_CATEGORY_ALIASES: dict[str, str] = {
    "patch_apply": "patch_apply",
    "direct_file_mutation": "direct_file_mutation",
    "worker_launch": "worker_launch",
    "model_call": "model_calls",
    "model_routing": "model_routing",
    "validation_run": "validation_execution",
    "benchmark_run": "benchmark_execution",
    "mcp_tool_invocation": "mcp_tool_invocation",
    "network_access": "network_access",
    "subprocess_execution": "subprocess_docker_execution",
    "docker_execution": "subprocess_docker_execution",
    "database_write": "database_writes",
    "auth_policy_change": "web_route_auth_policy_changes",
    "route_behavior_change": "web_route_auth_policy_changes",
    "registry_mutation": "registry_adoption",
    "model_catalog_adoption": "model_role_catalog_adoption",
    "dream_execution": "dream_execution",
    "replay_apply": "replay_janitor_apply_actions",
    "remote_execution": "remote_execution",
    "automatic_approval": "automatic_approval_rejection",
    "automatic_rejection": "automatic_approval_rejection",
    "hidden_mutation": "hidden_mutation",
}

CURRENT_SURFACES: dict[str, list[str]] = {
    "patch_apply": ["web/app.py apply patch routes", "core/patch_safety.py", "core/project_evolution_patch_draft.py"],
    "direct_file_mutation": ["project-evolution patch writers", "artifact writers under scripts/ and core/"],
    "worker_launch": ["core/worker_runs.py", "core/commander_run_contract.py", "worker import/review routes"],
    "model_call": ["model provider call sites and router-adjacent code", "model role registry metadata"],
    "model_routing": ["core/model_role_registry.py", "ADOPT.MODEL advisory catalog artifacts"],
    "validation_run": ["core/validation_execution.py", "web proposal validation routes"],
    "benchmark_run": ["benchmarks/run_benchmarks.py", "benchmark report scripts"],
    "mcp_tool_invocation": ["mcp_server artifact/tool entry points", "core/tool_registry.py"],
    "network_access": ["remote PR safety contracts", "external queue/network-capable integrations"],
    "subprocess_execution": ["validation execution helpers", "sandbox runner utilities"],
    "docker_execution": ["sandbox/container execution planning surfaces"],
    "database_write": ["durable persistence adapters if introduced later"],
    "auth_policy_change": ["web/auth_gate.py", "web/app.py before-request gate wiring"],
    "route_behavior_change": ["web/app.py", "web/routes modules"],
    "registry_mutation": ["docs/roadmap/phase_registry.json", "phase registry update scripts"],
    "model_catalog_adoption": ["scripts/adopt_model_role_catalog.py", "model role adoption artifacts"],
    "dream_execution": ["core/dream_trials.py", "Dream route/action surfaces"],
    "replay_apply": ["core/replay_janitor.py", "Replay janitor/apply routes"],
    "remote_execution": ["remote PR/workflow safety contracts", "future remote command surfaces"],
    "automatic_approval": ["HUMAN.N1/HUMAN.N2 forbidden automatic authority boundary"],
    "automatic_rejection": ["HUMAN.N1/HUMAN.N2 forbidden automatic authority boundary"],
    "hidden_mutation": ["HUMAN.N1 hidden mutation forbidden boundary"],
}

ATTACHMENT_CANDIDATES: dict[str, str] = {
    "patch_apply": "patch-apply request builder before any source mutation",
    "direct_file_mutation": "file mutation service boundary before write dispatch",
    "worker_launch": "worker launch planner before worker task dispatch",
    "model_call": "model provider client boundary before cost/network call",
    "model_routing": "model routing/catalog resolver before executable routing",
    "validation_run": "validation plan runner before command execution",
    "benchmark_run": "benchmark plan runner before benchmark execution",
    "mcp_tool_invocation": "tool registry invocation boundary before tool call",
    "network_access": "network request adapter before external contact",
    "subprocess_execution": "process execution adapter before command spawn",
    "docker_execution": "container execution adapter before Docker/container launch",
    "database_write": "repository/database adapter before durable write",
    "auth_policy_change": "auth policy configuration review boundary",
    "route_behavior_change": "route registration/change review boundary",
    "registry_mutation": "phase/model registry writer before registry update",
    "model_catalog_adoption": "model catalog adoption receipt writer before adoption",
    "dream_execution": "Dream run dispatcher before execution",
    "replay_apply": "Replay janitor/apply dispatcher before mutation",
    "remote_execution": "remote command adapter before external execution",
    "automatic_approval": "no attachment candidate; automatic approval remains forbidden",
    "automatic_rejection": "no attachment candidate; automatic rejection remains forbidden",
    "hidden_mutation": "no attachment candidate; hidden mutation remains forbidden",
}

DEFAULT_APPROVAL_MAPPINGS: dict[str, dict[str, Any]] = {
    "patch_apply": {"approval_action": "approve_patch_apply", "target_type": "patch", "future_approval_required": True},
    "direct_file_mutation": {"approval_action": "approve_patch_apply", "target_type": "patch", "future_approval_required": True},
    "worker_launch": {"approval_action": "approve_worker_launch", "target_type": "worker_task", "future_approval_required": True},
    "model_call": {"approval_action": "approve_network_access", "target_type": "network_request", "future_approval_required": True},
    "model_routing": {"approval_action": "approve_model_catalog_adoption", "target_type": "model_catalog", "future_approval_required": True},
    "validation_run": {"approval_action": "approve_validation_run", "target_type": "validation_plan", "future_approval_required": True},
    "benchmark_run": {"approval_action": "approve_benchmark_run", "target_type": "benchmark_plan", "future_approval_required": True},
    "mcp_tool_invocation": {"approval_action": "approve_mcp_tool_invocation", "target_type": "mcp_tool", "future_approval_required": True},
    "network_access": {"approval_action": "approve_network_access", "target_type": "network_request", "future_approval_required": True},
    "subprocess_execution": {"approval_action": "approve_remote_execution", "target_type": "remote_command", "future_approval_required": True},
    "docker_execution": {"approval_action": "approve_remote_execution", "target_type": "remote_command", "future_approval_required": True},
    "database_write": {"approval_action": "approve_database_write", "target_type": "database_change", "future_approval_required": True},
    "auth_policy_change": {"approval_action": "approve_auth_policy_change", "target_type": "auth_policy", "future_approval_required": True},
    "route_behavior_change": {"approval_action": "approve_auth_policy_change", "target_type": "auth_policy", "future_approval_required": True},
    "registry_mutation": {"approval_action": "approve_registry_mutation", "target_type": "registry", "future_approval_required": True},
    "model_catalog_adoption": {
        "approval_action": "approve_model_catalog_adoption",
        "target_type": "model_catalog",
        "future_approval_required": True,
    },
    "dream_execution": {"approval_action": "approve_dream_execution", "target_type": "dream_run", "future_approval_required": True},
    "replay_apply": {"approval_action": "approve_replay_apply", "target_type": "replay_action", "future_approval_required": True},
    "remote_execution": {"approval_action": "approve_remote_execution", "target_type": "remote_command", "future_approval_required": True},
    "automatic_approval": {"approval_action": None, "target_type": None, "future_approval_required": False},
    "automatic_rejection": {"approval_action": None, "target_type": None, "future_approval_required": False},
    "hidden_mutation": {"approval_action": None, "target_type": None, "future_approval_required": False},
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


def _read_text_marker(repo: Path, path: str | Path, marker: str) -> tuple[bool, str]:
    source = _resolve(repo, path)
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        return False, str(exc)
    return marker in text, ""


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
    human_boundary_path: str | Path,
    approval_contract_path: str | Path,
    human_checkpoint_path: str | Path,
    dry_run_validator_path: str | Path,
    sample_catalog_path: str | Path,
    model_adoption_checkpoint_path: str | Path,
) -> tuple[dict[str, dict[str, Any] | None], list[dict[str, Any]], list[str]]:
    boundary, boundary_error = _read_json_object(repo, human_boundary_path, "HUMAN.N1 boundary map")
    contract, contract_error = _read_json_object(repo, approval_contract_path, "HUMAN.N2 approval contract")
    human_close, human_close_error = _read_json_object(repo, human_checkpoint_path, "HUMAN.CLOSE checkpoint")
    sample_catalog, sample_catalog_error = _read_json_object(repo, sample_catalog_path, "HUMAN.N4 sample catalog")
    model_close, model_close_error = _read_json_object(
        repo,
        model_adoption_checkpoint_path,
        "ADOPT.MODEL.CLOSE checkpoint",
    )
    dry_run_present, dry_run_error = _read_text_marker(repo, dry_run_validator_path, "human_approval_token_dry_run")

    artifacts = [
        _artifact_summary(
            phase_id="HUMAN.N1",
            path=human_boundary_path,
            data=boundary,
            error=boundary_error,
            expected_kind="human_review_boundary_map",
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
        {
            "phase_id": "HUMAN.N3",
            "path": _norm_path(dry_run_validator_path),
            "present": dry_run_present and not dry_run_error,
            "required": False,
            "report_kind": "source_marker",
            "expected_report_kind": "human_approval_token_dry_run source marker",
            "report_kind_ok": dry_run_present,
            "error": dry_run_error,
        },
        _artifact_summary(
            phase_id="HUMAN.N4",
            path=sample_catalog_path,
            data=sample_catalog,
            error=sample_catalog_error,
            expected_kind="human_approval_token_sample_catalog",
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
        _artifact_summary(
            phase_id="ADOPT.MODEL.CLOSE",
            path=model_adoption_checkpoint_path,
            data=model_close,
            error=model_close_error,
            expected_kind="model_role_catalog_adoption_checkpoint",
            required=True,
        ),
    ]

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
        "human_boundary": boundary,
        "approval_contract": contract,
        "human_checkpoint": human_close,
        "sample_catalog": sample_catalog,
        "model_adoption_checkpoint": model_close,
    }, artifacts, incomplete


def _human_boundary_ids(boundary: dict[str, Any] | None) -> set[str]:
    if not isinstance(boundary, dict):
        return set()
    matrix = boundary.get("boundary_matrix")
    if not isinstance(matrix, list):
        return set()
    return {
        str(item.get("action_id") or "").strip()
        for item in matrix
        if isinstance(item, dict) and str(item.get("action_id") or "").strip()
    }


def _allowed_approval_actions(contract: dict[str, Any] | None) -> set[str]:
    values = contract.get("allowed_approval_actions") if isinstance(contract, dict) else []
    return {str(value) for value in values} if isinstance(values, list) else set()


def _allowed_target_types(contract: dict[str, Any] | None) -> set[str]:
    values = contract.get("target_types") if isinstance(contract, dict) else []
    return {str(value) for value in values} if isinstance(values, list) else set()


def _authority_status(category: str) -> str:
    if category in {"automatic_approval", "automatic_rejection", "hidden_mutation"}:
        return "blocked_forbidden"
    if category == "model_routing":
        return "forbidden_without_separate_phase"
    return "explicit_human_approval_required"


def _risk_level(category: str) -> str:
    if category in {"automatic_approval", "automatic_rejection", "hidden_mutation"}:
        return "critical"
    if category in {
        "patch_apply",
        "direct_file_mutation",
        "worker_launch",
        "auth_policy_change",
        "route_behavior_change",
        "registry_mutation",
        "model_catalog_adoption",
        "remote_execution",
        "database_write",
    }:
        return "high"
    return "medium"


def _copy_mappings(value: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    source = DEFAULT_APPROVAL_MAPPINGS if value is None else value
    copied: dict[str, dict[str, Any]] = {}
    for category, mapping in source.items():
        if isinstance(mapping, dict):
            copied[str(category)] = dict(mapping)
    return copied


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
    data["audit_only"] = True
    data["writes_audit_artifacts_only"] = True
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


def _future_candidates(mappings: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for category in ACTION_CATEGORIES:
        mapping = dict(mappings.get(category) or {})
        out[category] = {
            "approval_action": mapping.get("approval_action"),
            "target_type": mapping.get("target_type"),
            "future_approval_required": bool(mapping.get("future_approval_required")),
            "enforcement_attachment_candidate": ATTACHMENT_CANDIDATES.get(category, ""),
        }
    return out


def _action_findings(
    *,
    mappings: dict[str, dict[str, Any]],
    boundary_ids: set[str],
    allowed_actions: set[str],
    target_types: set[str],
    incomplete: list[str],
    blockers: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    findings: list[dict[str, Any]] = []
    missing_mappings: list[str] = []
    for category in ACTION_CATEGORIES:
        alias = HUMAN_N1_CATEGORY_ALIASES[category]
        mapping = mappings.get(category)
        missing_boundary = alias not in boundary_ids if boundary_ids else False
        if missing_boundary:
            blockers.append(f"{category} lacks HUMAN.N1 human boundary reference ({alias})")

        if not mapping:
            missing_mappings.append(category)
            incomplete.append(f"{category} lacks future approval mapping")
            approval_action = None
            target_type = None
            future_required = True
        else:
            approval_action = mapping.get("approval_action")
            target_type = mapping.get("target_type")
            future_required = bool(mapping.get("future_approval_required"))
            if future_required and not approval_action:
                missing_mappings.append(category)
                incomplete.append(f"{category} lacks HUMAN.N2 approval action")
            if approval_action and allowed_actions and approval_action not in allowed_actions:
                blockers.append(
                    f"{category} mapping {approval_action} contradicts HUMAN.N2 allowed approval actions"
                )
            if target_type and target_types and target_type not in target_types:
                blockers.append(f"{category} target type {target_type} contradicts HUMAN.N2 target types")

        item_warnings: list[str] = []
        if category in {"automatic_approval", "automatic_rejection", "hidden_mutation"}:
            item_warnings.append(f"{category} is forbidden; no approval token may authorize it.")
        elif category == "model_routing":
            item_warnings.append("Model routing remains future separate-phase work; ADOPT catalog is advisory.")

        findings.append(
            {
                "action_category": category,
                "current_known_surface": list(CURRENT_SURFACES.get(category, [])),
                "current_authority_status": _authority_status(category),
                "future_approval_required": future_required,
                "required_approval_action_from_HUMAN_N2": approval_action,
                "required_target_type_from_HUMAN_N2": target_type,
                "risk_level": _risk_level(category),
                "existing_human_boundary_reference": f"HUMAN.N1:{alias}",
                "enforcement_attachment_candidate": ATTACHMENT_CANDIDATES.get(category, ""),
                "enforcement_not_implemented_confirmed": True,
                "warnings": item_warnings,
                "blockers": [],
            }
        )
    return findings, missing_mappings


def _status(blockers: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blockers:
        return STATUS_BLOCKED
    if incomplete:
        return STATUS_INCOMPLETE
    if warnings:
        return STATUS_READY_WITH_WARNINGS
    return STATUS_READY


def build_approval_enforcement_readiness_audit(
    *,
    repo_root: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    source_human_boundary_path: str | Path = DEFAULT_HUMAN_BOUNDARY_PATH,
    source_approval_contract_path: str | Path = DEFAULT_APPROVAL_CONTRACT_PATH,
    source_human_checkpoint_path: str | Path = DEFAULT_HUMAN_CHECKPOINT_PATH,
    source_dry_run_validator_path: str | Path = DEFAULT_DRY_RUN_VALIDATOR_PATH,
    source_sample_catalog_path: str | Path = DEFAULT_SAMPLE_CATALOG_PATH,
    source_model_adoption_checkpoint_path: str | Path = DEFAULT_MODEL_ADOPTION_CHECKPOINT_PATH,
    audit_id: str = "",
    created_at: str = "",
    approval_mappings: dict[str, Any] | None = None,
    runtime_change_markers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the HARDEN.N1 report-only approval enforcement readiness audit."""
    repo = Path(repo_root or ".").resolve()
    source_data, source_artifacts, incomplete = _source_artifacts(
        repo=repo,
        human_boundary_path=source_human_boundary_path,
        approval_contract_path=source_approval_contract_path,
        human_checkpoint_path=source_human_checkpoint_path,
        dry_run_validator_path=source_dry_run_validator_path,
        sample_catalog_path=source_sample_catalog_path,
        model_adoption_checkpoint_path=source_model_adoption_checkpoint_path,
    )
    blockers = _runtime_blockers(runtime_change_markers)

    mappings = _copy_mappings(approval_mappings)
    boundary_ids = _human_boundary_ids(source_data["human_boundary"])
    allowed_actions = _allowed_approval_actions(source_data["approval_contract"])
    target_types = _allowed_target_types(source_data["approval_contract"])
    findings, missing_mappings = _action_findings(
        mappings=mappings,
        boundary_ids=boundary_ids,
        allowed_actions=allowed_actions,
        target_types=target_types,
        incomplete=incomplete,
        blockers=blockers,
    )

    runtime_confirmation = _runtime_confirmation(runtime_change_markers)
    enforcement_not_implemented = all(runtime_confirmation.values())
    if not enforcement_not_implemented:
        blockers.append("runtime non-enforcement confirmation failed")

    warnings = [
        "Future enforcement is intentionally not implemented in HARDEN.N1.",
        "HARDEN.N2 should design enforcement before any token gate, route blocker, or auth behavior change.",
    ]
    human_checkpoint = source_data["human_checkpoint"] or {}
    model_checkpoint = source_data["model_adoption_checkpoint"] or {}
    for source, label in ((human_checkpoint, "HUMAN.CLOSE"), (model_checkpoint, "ADOPT.MODEL.CLOSE")):
        source_warnings = source.get("warnings") if isinstance(source, dict) else []
        if isinstance(source_warnings, list) and source_warnings:
            warnings.append(f"{label} has {len(source_warnings)} historical warning(s).")

    blockers = _dedupe(blockers)
    incomplete = _dedupe(incomplete)
    warnings = _dedupe(warnings)
    status = _status(blockers, incomplete, warnings)
    mapped_count = len(ACTION_CATEGORIES) - len(set(missing_mappings))
    candidates = _future_candidates(mappings)

    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "audit_id": str(audit_id or ""),
        "created_at": str(created_at or _utc_now()),
        "guardrail_note": GUARDRAIL_NOTE,
        "audit_status": status,
        "source_human_boundary_path": _norm_path(source_human_boundary_path),
        "source_approval_contract_path": _norm_path(source_approval_contract_path),
        "source_human_checkpoint_path": _norm_path(source_human_checkpoint_path),
        "source_model_adoption_checkpoint_path": _norm_path(source_model_adoption_checkpoint_path),
        "source_artifacts": source_artifacts,
        "action_surface_count": len(ACTION_CATEGORIES),
        "mapped_action_count": mapped_count,
        "unmapped_action_count": len(set(missing_mappings)),
        "enforcement_not_implemented_confirmed": enforcement_not_implemented,
        "action_surface_findings": findings,
        "future_enforcement_candidates": candidates,
        "missing_approval_mappings": sorted(set(missing_mappings)),
        "forbidden_runtime_changes_checked": sorted(RUNTIME_MARKER_LABELS),
        "runtime_non_enforcement_confirmation": runtime_confirmation,
        "human_authority_reference": {
            "human_n1_boundary_ids_detected": sorted(boundary_ids),
            "human_n2_allowed_approval_actions": sorted(allowed_actions),
            "human_n2_target_types": sorted(target_types),
            "human_close_ready_for_next_phase": bool(
                isinstance(human_checkpoint, dict)
                and (human_checkpoint.get("final_verdict") or {}).get("ready_for_next_phase") is True
            ),
        },
        "model_adoption_reference": {
            "adopt_model_close_status": str(model_checkpoint.get("checkpoint_status") or "")
            if isinstance(model_checkpoint, dict)
            else "",
            "active_catalog_advisory_only_confirmed": bool(
                isinstance(model_checkpoint, dict) and model_checkpoint.get("advisory_only_confirmed") is True
            ),
            "model_routing_enabled_confirmed_false": bool(
                isinstance(model_checkpoint, dict)
                and model_checkpoint.get("model_routing_enabled_confirmed_false") is True
            ),
        },
        "warnings": warnings,
        "blocked_reasons": blockers,
        "incomplete_reasons": incomplete,
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "final_verdict": {
            "status": status,
            "ready_for_design_phase": status in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
            "message": (
                "Approval enforcement readiness is mapped with warnings because runtime enforcement is intentionally absent."
                if status == STATUS_READY_WITH_WARNINGS
                else f"Approval enforcement readiness audit status is {status}."
            ),
        },
        "guardrails": _guardrails(runtime_change_markers),
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


def render_approval_enforcement_readiness_audit_markdown(report: dict[str, Any]) -> str:
    """Render the HARDEN.N1 readiness audit as Markdown."""
    lines: list[str] = [
        "# Approval Enforcement Readiness Audit",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Audit status:** `{_md(report.get('audit_status', ''))}`",
        f"- **Action surfaces:** {report.get('action_surface_count', 0)}",
        f"- **Mapped actions:** {report.get('mapped_action_count', 0)}",
        f"- **Unmapped actions:** {report.get('unmapped_action_count', 0)}",
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

    lines.extend(["", "## Human Authority Reference", ""])
    lines.extend(_dict_lines(report.get("human_authority_reference")))
    lines.extend(["", "## Model Adoption Reference", ""])
    lines.extend(_dict_lines(report.get("model_adoption_reference")))

    lines.extend(["", "## Dangerous Action Surface Map", ""])
    findings = report.get("action_surface_findings") if isinstance(report.get("action_surface_findings"), list) else []
    if findings:
        lines.extend(
            [
                "| Category | Authority | Approval action | Target type | Risk | Attachment candidate |",
                "|---|---|---|---|---|---|",
            ]
        )
        for item in findings:
            lines.append(
                "| {cat} | `{status}` | `{action}` | `{target}` | `{risk}` | {candidate} |".format(
                    cat=_md(item.get("action_category")),
                    status=_md(item.get("current_authority_status")),
                    action=_md(item.get("required_approval_action_from_HUMAN_N2")),
                    target=_md(item.get("required_target_type_from_HUMAN_N2")),
                    risk=_md(item.get("risk_level")),
                    candidate=_md(item.get("enforcement_attachment_candidate")),
                )
            )
    else:
        lines.append("_None._")

    lines.extend(["", "## Future Approval Mapping", ""])
    lines.extend(_dict_lines(report.get("future_enforcement_candidates")))
    lines.extend(["", "## Enforcement Attachment Candidates", ""])
    for item in findings:
        lines.append(f"- `{_md(item.get('action_category'))}`: {_md(item.get('enforcement_attachment_candidate'))}")
    if not findings:
        lines.append("_None._")

    lines.extend(["", "## Runtime Non-Enforcement Confirmation", ""])
    lines.extend(_dict_lines(report.get("runtime_non_enforcement_confirmation")))
    lines.extend(["", "## Missing Mappings", ""])
    lines.extend(_list_lines(report.get("missing_approval_mappings")))
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


def write_approval_enforcement_readiness_audit(
    *,
    repo_root: str | Path = ".",
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    source_human_boundary_path: str | Path = DEFAULT_HUMAN_BOUNDARY_PATH,
    source_approval_contract_path: str | Path = DEFAULT_APPROVAL_CONTRACT_PATH,
    source_human_checkpoint_path: str | Path = DEFAULT_HUMAN_CHECKPOINT_PATH,
    source_dry_run_validator_path: str | Path = DEFAULT_DRY_RUN_VALIDATOR_PATH,
    source_sample_catalog_path: str | Path = DEFAULT_SAMPLE_CATALOG_PATH,
    source_model_adoption_checkpoint_path: str | Path = DEFAULT_MODEL_ADOPTION_CHECKPOINT_PATH,
    audit_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build and write HARDEN.N1 JSON/Markdown audit artifacts."""
    report = build_approval_enforcement_readiness_audit(
        repo_root=repo_root,
        registry_path=registry_path,
        source_human_boundary_path=source_human_boundary_path,
        source_approval_contract_path=source_approval_contract_path,
        source_human_checkpoint_path=source_human_checkpoint_path,
        source_dry_run_validator_path=source_dry_run_validator_path,
        source_sample_catalog_path=source_sample_catalog_path,
        source_model_adoption_checkpoint_path=source_model_adoption_checkpoint_path,
        audit_id=audit_id,
        created_at=created_at,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_approval_enforcement_readiness_audit_markdown(report), encoding="utf-8")
    return {
        "ok": report["audit_status"] in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
