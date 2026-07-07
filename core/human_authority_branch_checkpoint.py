"""HUMAN.CLOSE - Human Authority Branch Checkpoint.

Freezes HUMAN.N1-HUMAN.N4 as a complete human-authority planning branch before
any runtime approval enforcement, route integration, token validation gate,
token issuance/consumption, worker launch, validation run, benchmark run, model
routing, or patch apply behavior is added.

This module is report-only. It reads the phase registry, existing HUMAN branch
artifacts, and local dry-run validator source markers, then writes checkpoint
artifacts only.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "human_authority_branch_checkpoint"
THIS_PHASE_ID = "HUMAN.CLOSE"
REQUIRED_HUMAN_PHASE_IDS: tuple[str, ...] = ("HUMAN.N1", "HUMAN.N2", "HUMAN.N3", "HUMAN.N4")

STATUS_FROZEN = "human_authority_branch_frozen"
STATUS_FROZEN_WITH_WARNINGS = "human_authority_branch_frozen_with_warnings"
STATUS_INCOMPLETE = "human_authority_branch_incomplete"
STATUS_BLOCKED = "human_authority_branch_blocked"

JSON_NAME = "human_authority_branch_checkpoint.json"
MD_NAME = "human_authority_branch_checkpoint.md"

DEFAULT_REGISTRY_PATH = Path("docs") / "roadmap" / "phase_registry.json"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "human" / "authority_branch_checkpoint"
DEFAULT_BOUNDARY_MAP_PATH = Path(".agent") / "human" / "review_boundary_map" / "human_review_boundary_map.json"
DEFAULT_TOKEN_CONTRACT_PATH = (
    Path(".agent") / "human" / "approval_token_contract" / "human_approval_token_contract.json"
)
DEFAULT_DRY_RUN_VALIDATOR_PATH = Path("core") / "human_approval_token_dry_run_validator.py"
DEFAULT_SAMPLE_CATALOG_PATH = (
    Path(".agent")
    / "human"
    / "approval_token_sample_catalog"
    / "human_approval_token_sample_catalog.json"
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "ADOPT.MODEL.1",
    "title": "Human-Approved Model Role Catalog Adoption",
    "reason": (
        "HUMAN.N1-N4 are frozen as advisory authority planning. The next safe "
        "step is to adopt the proposed model-role catalog only through an "
        "explicit human-approved, report-first phase."
    ),
    "alternatives": [
        {
            "phase_id": "HARDEN.N1",
            "title": "Approval Enforcement Readiness Audit",
            "reason": "Use this before enforcement if adoption is deferred.",
        },
        {
            "phase_id": "EVAL.DEMO.1",
            "title": "Evidence Quality Loaded Report Demo",
            "reason": "Use this if demo evidence quality is the next operator priority.",
        },
    ],
}

GUARDRAIL_NOTE = (
    "HUMAN.CLOSE is report-only and checkpoint-only. It reads existing HUMAN "
    "branch artifacts/code markers and writes checkpoint JSON/Markdown only. It "
    "does not enforce approvals, approve or reject work, issue or consume tokens, "
    "apply patches, run validation, run benchmarks, launch workers, route models, "
    "invoke MCP tools, execute Dream or Replay janitor actions, use Docker or "
    "subprocess, contact networks, write databases, change routes, change auth "
    "policy, or mutate the phase registry."
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "checkpoint only",
    "no runtime enforcement",
    "no approval/rejection",
    "no token issuance",
    "no token consumption",
    "no model call",
    "no model routing",
    "no worker launch",
    "no patch apply",
    "no validation run",
    "no benchmark run",
    "no MCP invocation",
    "no Dream execution",
    "no Replay janitor apply",
    "no Docker/subprocess",
    "no network",
    "no database write",
    "no route behavior change",
    "no auth policy change",
    "no registry mutation",
    "writes checkpoint artifacts only",
)

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "approval_or_rejection_performed",
    "real_approval_issued",
    "token_issuance_performed",
    "token_consumption_performed",
    "runtime_enforcement_added",
    "route_approval_enforcement_added",
    "approval_gate_added",
    "model_call_performed",
    "model_routing_performed",
    "worker_launch_performed",
    "patch_apply_performed",
    "validation_run_performed",
    "benchmark_run_performed",
    "mcp_invocation_performed",
    "dream_execution_performed",
    "replay_janitor_apply_performed",
    "docker_or_subprocess_used",
    "network_contacted",
    "database_write_performed",
    "route_behavior_changed",
    "auth_policy_changed",
    "registry_mutation_performed",
)

BLOCK_TRUE_KEYS: dict[str, str] = {
    "auto_approve": "auto_approve_allowed",
    "auto_approve_allowed": "auto_approve_allowed",
    "automatic_approval_allowed": "auto_approve_allowed",
    "auto_reject": "auto_reject_allowed",
    "auto_reject_allowed": "auto_reject_allowed",
    "automatic_rejection_allowed": "auto_reject_allowed",
    "hidden_mutation_allowed": "hidden_mutation_allowed",
    "token_issuance_path": "token_issuance_path",
    "token_consumption_path": "token_consumption_path",
    "token_issuance_performed": "token_issuance_path",
    "token_consumption_performed": "token_consumption_path",
    "issue_token_path": "token_issuance_path",
    "consume_token_path": "token_consumption_path",
    "runtime_enforcement_added": "runtime_enforcement_added",
    "route_approval_enforcement_added": "runtime_enforcement_added",
    "approval_gate_added": "approval_gate_added",
    "route_behavior_changed": "route_behavior_changed",
    "route_behavior_change_performed": "route_behavior_changed",
    "auth_policy_changed": "auth_policy_changed",
    "auth_policy_change_performed": "auth_policy_changed",
    "patch_apply_path_changed": "patch_apply_path_changed",
    "patch_apply_performed": "patch_apply_path_changed",
    "validation_execution_path_changed": "validation_execution_path_changed",
    "validation_run_performed": "validation_execution_path_changed",
    "benchmark_execution_path_changed": "benchmark_execution_path_changed",
    "benchmark_run_performed": "benchmark_execution_path_changed",
    "worker_launch_path_changed": "worker_launch_path_changed",
    "worker_launch_performed": "worker_launch_path_changed",
    "model_routing_performed": "model_routing_changed",
    "model_routing_changed": "model_routing_changed",
    "approval_or_rejection_performed": "approval_or_rejection_performed",
}

REAL_AUTHORITY_TRUE_KEYS: tuple[str, ...] = (
    "safe_to_use_as_real_approval",
    "authorizes_action",
    "real_approval_issued",
    "approval_tokens_authorize_runtime_action",
    "sample_presence_implies_user_consent",
    "dry_run_valid_tokens_authorize_real_actions",
)

DOCUMENTATION_ONLY_FALSE_KEYS: tuple[str, ...] = (
    "approval_tokens_are_documentation_or_dry_run_only",
    "approval_tokens_documentation_only",
    "documentation_only",
    "dry_run_only",
)

PHASE_GUARDRAIL_FIELDS: tuple[str, ...] = (
    "model_calls_allowed",
    "network_allowed",
    "merge_allowed",
    "writes_real_repo",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _bool(value: Any) -> str:
    return str(bool(value)).lower()


def _norm_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


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
    raw = Path(path)
    return raw if raw.is_absolute() else repo / raw


def _read_text(path: Path) -> tuple[str, str]:
    try:
        return path.read_text(encoding="utf-8"), ""
    except OSError as exc:
        return "", f"could not read {_norm_path(path)}: {exc}"


def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, str]:
    text, read_error = _read_text(path)
    if read_error:
        return None, read_error
    try:
        data = json.loads(text)
    except ValueError as exc:
        return None, f"could not parse {_norm_path(path)}: {exc}"
    if not isinstance(data, dict):
        return None, f"{_norm_path(path)} is not a JSON object"
    return data, ""


def _guardrails() -> dict[str, bool]:
    data = {key: False for key in GUARDRAIL_FALSE_FLAGS}
    data["report_only"] = True
    data["checkpoint_only"] = True
    data["writes_checkpoint_artifacts_only"] = True
    return data


def _block(blocked: list[dict[str, str]], reason: str, message: str) -> None:
    if not any(item.get("reason") == reason for item in blocked):
        blocked.append({"reason": reason, "message": message})


def _phase_map(registry_data: Any) -> dict[str, dict[str, Any]]:
    root = registry_data if isinstance(registry_data, dict) else {}
    phases = root.get("phases") if isinstance(root.get("phases"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for phase in phases:
        if isinstance(phase, dict) and phase.get("phase_id"):
            out[str(phase["phase_id"])] = phase
    return out


def _phase_guardrail_violations(phase: dict[str, Any]) -> list[str]:
    violations = [field for field in PHASE_GUARDRAIL_FIELDS if phase.get(field) is True]
    automation = str(phase.get("automation_level", ""))
    if automation not in {"LOCAL_0_OBSERVE", "LOCAL_1_PREPARE"}:
        violations.append(f"automation_level={automation or '(missing)'}")
    if phase.get("human_approval_required") is not True:
        violations.append("human_approval_required")
    return violations


def _phase_completion(registry_data: Any, registry_error: str, blocked: list[dict[str, str]], incomplete: list[str]) -> dict[str, Any]:
    if registry_error:
        incomplete.append(f"phase registry missing or unreadable: {registry_error}")
    phases = _phase_map(registry_data)
    checks: list[dict[str, Any]] = []
    for phase_id in REQUIRED_HUMAN_PHASE_IDS:
        phase = phases.get(phase_id)
        present = phase is not None
        complete = present and phase.get("status") == "complete"
        violations = _phase_guardrail_violations(phase) if present else []
        if not present:
            incomplete.append(f"{phase_id} phase is missing")
        elif not complete:
            incomplete.append(f"{phase_id} is not registered complete")
        if violations:
            _block(
                blocked,
                f"{phase_id}_guardrail_violation",
                f"{phase_id} has unsafe registry guardrails: {', '.join(violations)}",
            )
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
    if this_violations:
        _block(
            blocked,
            f"{THIS_PHASE_ID}_guardrail_violation",
            f"{THIS_PHASE_ID} has unsafe registry guardrails: {', '.join(this_violations)}",
        )

    return {
        "required_phase_ids": list(REQUIRED_HUMAN_PHASE_IDS),
        "phase_checks": checks,
        "all_required_human_phases_complete": all(check["complete"] for check in checks),
        "all_required_human_phase_guardrails_ok": all(check["guardrails_ok"] for check in checks),
        "this_phase_id": THIS_PHASE_ID,
        "this_phase_registered": this_present,
        "this_phase_complete": this_complete,
        "this_phase_guardrails_ok": this_present and not this_violations,
        "this_phase_guardrail_violations": this_violations,
    }


def _truthy_marker(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() not in {"", "false", "no", "none", "0", "not allowed", "blocked"}
    return value is not None


def _scan_forbidden_markers(value: Any, blocked: list[dict[str, str]], path: str = "") -> dict[str, bool]:
    flags = {
        "auto_approve_allowed": False,
        "auto_reject_allowed": False,
        "hidden_mutation_allowed": False,
        "approval_token_treated_as_real_authority": False,
        "token_issuance_path": False,
        "token_consumption_path": False,
        "runtime_enforcement_added": False,
        "approval_gate_added": False,
        "route_behavior_changed": False,
        "auth_policy_changed": False,
        "patch_apply_path_changed": False,
        "validation_execution_path_changed": False,
        "benchmark_execution_path_changed": False,
        "worker_launch_path_changed": False,
        "model_routing_changed": False,
        "approval_or_rejection_performed": False,
    }

    def mark(reason: str, message: str) -> None:
        flags[reason] = True
        _block(blocked, reason, message)

    def walk(item: Any, trail: str) -> None:
        if isinstance(item, dict):
            action_id = str(item.get("action_id", item.get("action", ""))).lower()
            if action_id in {"auto_approve", "automatic_approval"} and item.get("automatic_allowed") is True:
                mark("auto_approve_allowed", f"auto-approve allowed at {trail or '(root)'}")
            if action_id in {"auto_reject", "automatic_rejection"} and item.get("automatic_allowed") is True:
                mark("auto_reject_allowed", f"auto-reject allowed at {trail or '(root)'}")
            if action_id == "hidden_mutation" and item.get("automatic_allowed") is True:
                mark("hidden_mutation_allowed", f"hidden mutation allowed at {trail or '(root)'}")

            for key, child in item.items():
                key_text = str(key)
                key_low = key_text.lower()
                child_path = f"{trail}.{key_text}" if trail else key_text
                if key_low in BLOCK_TRUE_KEYS and _truthy_marker(child):
                    reason = BLOCK_TRUE_KEYS[key_low]
                    mark(reason, f"{key_text} marker is enabled at {child_path}")
                if key_low in REAL_AUTHORITY_TRUE_KEYS and _truthy_marker(child):
                    mark(
                        "approval_token_treated_as_real_authority",
                        f"{key_text} treats approval-token documentation as real authority at {child_path}",
                    )
                if key_low in DOCUMENTATION_ONLY_FALSE_KEYS and child is False:
                    mark(
                        "approval_token_treated_as_real_authority",
                        f"{key_text} is false at {child_path}; approval tokens must remain documentation/dry-run only",
                    )
                if key_low == "hidden_mutation_path" and _truthy_marker(child):
                    mark("hidden_mutation_allowed", f"{key_text} marker is enabled at {child_path}")
                walk(child, child_path)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{trail}[{index}]")

    walk(value, path)
    return flags


def _text_blob(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    except TypeError:
        return str(value).lower()


def _has_terms(value: Any, *terms: str) -> bool:
    text = _text_blob(value)
    return all(term.lower() in text for term in terms)


def _artifact_coverage(
    *,
    repo: Path,
    boundary_map: dict[str, Any] | None,
    boundary_error: str,
    boundary_path: Path,
    contract: dict[str, Any] | None,
    contract_error: str,
    contract_path: Path,
    validator_text: str,
    validator_error: str,
    validator_path: Path,
    catalog: dict[str, Any] | None,
    catalog_error: str,
    catalog_path: Path,
    incomplete: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact_checks = [
        {
            "artifact_key": "human_review_boundary_map",
            "phase_id": "HUMAN.N1",
            "path": _norm_path(boundary_path),
            "present": boundary_map is not None and not boundary_error,
            "kind_ok": bool(boundary_map and boundary_map.get("report_kind") == "human_review_boundary_map"),
            "load_error": boundary_error,
        },
        {
            "artifact_key": "human_approval_token_contract",
            "phase_id": "HUMAN.N2",
            "path": _norm_path(contract_path),
            "present": contract is not None and not contract_error,
            "kind_ok": bool(contract and contract.get("report_kind") == "human_approval_token_contract"),
            "load_error": contract_error,
        },
        {
            "artifact_key": "human_approval_token_dry_run_validator",
            "phase_id": "HUMAN.N3",
            "path": _norm_path(validator_path),
            "present": bool(validator_text) and not validator_error,
            "kind_ok": "human_approval_token_dry_run" in validator_text,
            "load_error": validator_error,
        },
        {
            "artifact_key": "human_approval_token_sample_catalog",
            "phase_id": "HUMAN.N4",
            "path": _norm_path(catalog_path),
            "present": catalog is not None and not catalog_error,
            "kind_ok": bool(catalog and catalog.get("report_kind") == "human_approval_token_sample_catalog"),
            "load_error": catalog_error,
        },
    ]

    display_names = {
        "human_review_boundary_map": "human review boundary map",
        "human_approval_token_contract": "human approval token contract",
        "human_approval_token_dry_run_validator": "human approval token dry-run validator",
        "human_approval_token_sample_catalog": "human approval token sample catalog",
    }
    for row in artifact_checks:
        name = display_names.get(str(row["artifact_key"]), str(row["artifact_key"]))
        if not row["present"]:
            incomplete.append(f"{name} artifact is missing or unreadable: {row['load_error']}")
        elif not row["kind_ok"]:
            incomplete.append(f"{name} artifact has unexpected report_kind")

    sample_checks: list[dict[str, Any]] = []
    catalog_samples = catalog.get("sample_tokens") if isinstance(catalog, dict) and isinstance(catalog.get("sample_tokens"), list) else []
    for sample in catalog_samples:
        if not isinstance(sample, dict):
            continue
        raw_path = str(sample.get("sample_artifact_path", ""))
        present = bool(raw_path) and _resolve(repo, raw_path).is_file()
        sample_checks.append(
            {
                "sample_id": str(sample.get("sample_id", "")),
                "path": raw_path,
                "present": present,
                "documentation_only": sample.get("documentation_only") is True,
                "safe_to_use_as_real_approval": sample.get("safe_to_use_as_real_approval") is True,
            }
        )
        if not present:
            incomplete.append(f"sample token file missing: {raw_path or '(missing path)'}")
    if catalog is not None and not catalog_samples:
        incomplete.append("sample catalog has no sample_tokens")

    sample_coverage = {
        "sample_checks": sample_checks,
        "sample_count": len(catalog_samples),
        "sample_files_exist": bool(sample_checks) and all(row["present"] for row in sample_checks),
    }
    coverage = {
        "artifact_checks": artifact_checks,
        "required_artifacts_present": all(row["present"] and row["kind_ok"] for row in artifact_checks),
        "sample_token_files_present": sample_coverage["sample_files_exist"],
    }
    return coverage, sample_coverage


def _authority_boundary_summary(boundary_map: dict[str, Any] | None, incomplete: list[str]) -> dict[str, bool]:
    data = boundary_map or {}
    patch = _has_terms(data, "patch", "approval")
    worker = _has_terms(data, "worker", "approval")
    model_catalog = _has_terms(data, "model", "catalog", "approval")
    validation_benchmark = _has_terms(data, "validation", "benchmark", "approval")
    model_routing_not_auto = _has_terms(data, "route models automatically") or _has_terms(data, "model", "not", "automatic")
    auto_approve_blocked = _has_terms(data, "auto", "approve", "blocked") or _has_terms(data, "auto_approve")
    auto_reject_blocked = _has_terms(data, "auto", "reject", "blocked") or _has_terms(data, "auto_reject")
    hidden_mutation_blocked = _has_terms(data, "hidden", "mutation", "blocked") or _has_terms(data, "hidden_mutation")
    summary = {
        "patch_apply_requires_explicit_human_approval": patch,
        "worker_launch_requires_explicit_human_approval": worker,
        "model_routing_is_not_automatic": model_routing_not_auto,
        "validation_benchmark_execution_is_not_automatic": validation_benchmark,
        "model_catalog_adoption_requires_explicit_human_approval": model_catalog,
        "auto_approve_blocked": auto_approve_blocked,
        "auto_reject_blocked": auto_reject_blocked,
        "hidden_mutation_blocked": hidden_mutation_blocked,
        "critical_authority_boundaries_present": all(
            [
                patch,
                worker,
                model_routing_not_auto,
                validation_benchmark,
                model_catalog,
                auto_approve_blocked,
                auto_reject_blocked,
                hidden_mutation_blocked,
            ]
        ),
        "human_authority_branch_remains_planning_only": True,
    }
    if boundary_map is not None and not summary["critical_authority_boundaries_present"]:
        incomplete.append("missing critical human authority boundary")
    return summary


def _approval_token_contract_summary(contract: dict[str, Any] | None) -> dict[str, bool]:
    data = contract or {}
    text = _text_blob(data)
    future = data.get("future_enforcement_boundary") if isinstance(data.get("future_enforcement_boundary"), dict) else {}
    guardrails = data.get("guardrails") if isinstance(data.get("guardrails"), dict) else {}
    no_runtime_enforcement = (
        "no runtime enforcement" in text
        or future.get("runtime_enforcement_added") is False
        or guardrails.get("runtime_enforcement_added") is False
    )
    no_token_issuance = (
        future.get("token_issuance_added") is False
        or guardrails.get("token_issuance_performed") is False
        or guardrails.get("token_issuance_added") is False
    )
    contract_only = data.get("contract_status") is not None or guardrails.get("contract_only") is True
    return {
        "contract_present": contract is not None,
        "approval_tokens_are_documentation_or_dry_run_only": (
            "documentation" in text and "dry-run" in text and "authorize real" in text
        )
        or (contract_only and no_runtime_enforcement and no_token_issuance),
        "dry_run_valid_tokens_do_not_authorize_real_actions": "valid tokens do not authorize real actions" in text
        or "valid dry-run" in text
        or "dry-run valid" in text,
        "no_token_issuance_path": "token_issuance_path" not in text and "issue_token_path" not in text,
        "no_token_consumption_path": "token_consumption_path" not in text and "consume_token_path" not in text,
        "future_enforcement_requires_explicit_human_approval": _has_terms(data, "explicit", "human", "approval"),
    }


def _dry_run_validator_summary(validator_text: str, validator_error: str, validator_path: Path) -> dict[str, Any]:
    return {
        "path": _norm_path(validator_path),
        "validator_exists": bool(validator_text) and not validator_error,
        "validator_read_error": validator_error,
        "report_kind_marker_detected": "human_approval_token_dry_run" in validator_text,
        "dry_run_only": True,
        "authorizes_real_actions": False,
    }


def _sample_catalog_summary(catalog: dict[str, Any] | None, sample_coverage: dict[str, Any]) -> dict[str, Any]:
    samples = catalog.get("sample_tokens") if isinstance(catalog, dict) and isinstance(catalog.get("sample_tokens"), list) else []
    sample_doc_only = bool(samples) and all(isinstance(sample, dict) and sample.get("documentation_only") is True for sample in samples)
    sample_not_real = bool(samples) and all(
        isinstance(sample, dict) and sample.get("safe_to_use_as_real_approval") is not True for sample in samples
    )
    text = _text_blob(catalog or {})
    return {
        "sample_catalog_present": catalog is not None,
        "sample_count": len(samples),
        "sample_files_exist": bool(sample_coverage.get("sample_files_exist")),
        "sample_tokens_are_documentation_only": sample_doc_only,
        "sample_tokens_are_not_real_approvals": sample_not_real,
        "dry_run_valid_tokens_do_not_authorize_real_actions": "authorize no" in text
        or "not authorize" in text
        or "must not authorize" in text,
    }


def _runtime_non_enforcement(flags: dict[str, bool]) -> dict[str, bool]:
    return {
        "no_runtime_enforcement_route_added": not flags["runtime_enforcement_added"],
        "no_approval_gate_added": not flags["approval_gate_added"],
        "no_token_issuance_or_consumption_path": not flags["token_issuance_path"] and not flags["token_consumption_path"],
        "no_patch_apply_path_changed": not flags["patch_apply_path_changed"],
        "no_validation_benchmark_execution_path_changed": (
            not flags["validation_execution_path_changed"] and not flags["benchmark_execution_path_changed"]
        ),
        "no_worker_launch_path_changed": not flags["worker_launch_path_changed"],
        "no_auth_policy_changed": not flags["auth_policy_changed"],
        "no_route_behavior_changed": not flags["route_behavior_changed"],
        "no_model_routing_changed": not flags["model_routing_changed"],
    }


def _forbidden_authority_checks(
    *,
    flags: dict[str, bool],
    contract_summary: dict[str, bool],
    sample_summary: dict[str, Any],
) -> dict[str, bool]:
    return {
        "auto_approve_and_auto_reject_blocked": not flags["auto_approve_allowed"] and not flags["auto_reject_allowed"],
        "hidden_mutation_blocked": not flags["hidden_mutation_allowed"],
        "approval_tokens_documentation_dry_run_only": bool(
            contract_summary["approval_tokens_are_documentation_or_dry_run_only"]
        ),
        "sample_tokens_not_real_approvals": bool(sample_summary["sample_tokens_are_not_real_approvals"]),
        "dry_run_valid_tokens_do_not_authorize_real_actions": bool(
            contract_summary["dry_run_valid_tokens_do_not_authorize_real_actions"]
            or sample_summary["dry_run_valid_tokens_do_not_authorize_real_actions"]
        ),
        "no_approval_token_real_authority": not flags["approval_token_treated_as_real_authority"],
        "no_approval_rejection_performed": not flags["approval_or_rejection_performed"],
    }


def _human_approval_boundary(authority_summary: dict[str, bool]) -> dict[str, Any]:
    return {
        "planning_only": True,
        "patch_apply_requires_explicit_human_approval": authority_summary["patch_apply_requires_explicit_human_approval"],
        "worker_launch_requires_explicit_human_approval": authority_summary["worker_launch_requires_explicit_human_approval"],
        "model_catalog_adoption_requires_explicit_human_approval": authority_summary[
            "model_catalog_adoption_requires_explicit_human_approval"
        ],
        "approval_rejection_authority": "human_only",
        "runtime_enforcement_authority": "future_phase_only_with_explicit_human_approval",
        "approval_tokens_authorize_runtime_actions": False,
    }


def _artifact_warnings(*artifacts: dict[str, Any] | None) -> list[str]:
    warnings: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        value = artifact.get("warnings")
        if isinstance(value, list):
            warnings.extend(str(item) for item in value)
    return _dedupe(warnings)


def _future_enforcement_boundary_explicit(contract: dict[str, Any] | None) -> bool:
    if not isinstance(contract, dict):
        return False
    text = _text_blob(contract)
    return "future_enforcement_boundary" in text and "explicit" in text


def _status(blocked: list[dict[str, str]], incomplete: list[str], warnings: list[str]) -> str:
    if blocked:
        return STATUS_BLOCKED
    if incomplete:
        return STATUS_INCOMPLETE
    if warnings:
        return STATUS_FROZEN_WITH_WARNINGS
    return STATUS_FROZEN


def _final_verdict(status: str) -> str:
    if status == STATUS_BLOCKED:
        return "Human authority branch cannot be frozen until authority blockers are resolved."
    if status == STATUS_INCOMPLETE:
        return "Human authority branch is missing required phase or artifact coverage."
    if status == STATUS_FROZEN_WITH_WARNINGS:
        return "Human authority branch is complete and safe to freeze, with future enforcement warnings."
    return "Human authority branch is frozen as planning-only human authority evidence."


def build_human_authority_branch_checkpoint(
    *,
    repo_root: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    boundary_map_path: str | Path = DEFAULT_BOUNDARY_MAP_PATH,
    token_contract_path: str | Path = DEFAULT_TOKEN_CONTRACT_PATH,
    dry_run_validator_path: str | Path = DEFAULT_DRY_RUN_VALIDATOR_PATH,
    sample_catalog_path: str | Path = DEFAULT_SAMPLE_CATALOG_PATH,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build a report-only HUMAN.CLOSE checkpoint from local artifacts/source."""
    repo = Path(repo_root or ".").resolve()
    registry_abs = _resolve(repo, registry_path)
    boundary_abs = _resolve(repo, boundary_map_path)
    contract_abs = _resolve(repo, token_contract_path)
    validator_abs = _resolve(repo, dry_run_validator_path)
    catalog_abs = _resolve(repo, sample_catalog_path)

    registry_data, registry_error = _load_json_object(registry_abs)
    boundary_map, boundary_error = _load_json_object(boundary_abs)
    contract, contract_error = _load_json_object(contract_abs)
    validator_text, validator_error = _read_text(validator_abs)
    catalog, catalog_error = _load_json_object(catalog_abs)

    blocked: list[dict[str, str]] = []
    incomplete: list[str] = []

    phase_completion = _phase_completion(registry_data, registry_error, blocked, incomplete)
    artifact_coverage, sample_coverage = _artifact_coverage(
        repo=repo,
        boundary_map=boundary_map,
        boundary_error=boundary_error,
        boundary_path=boundary_abs,
        contract=contract,
        contract_error=contract_error,
        contract_path=contract_abs,
        validator_text=validator_text,
        validator_error=validator_error,
        validator_path=validator_abs,
        catalog=catalog,
        catalog_error=catalog_error,
        catalog_path=catalog_abs,
        incomplete=incomplete,
    )

    flags = {
        "auto_approve_allowed": False,
        "auto_reject_allowed": False,
        "hidden_mutation_allowed": False,
        "approval_token_treated_as_real_authority": False,
        "token_issuance_path": False,
        "token_consumption_path": False,
        "runtime_enforcement_added": False,
        "approval_gate_added": False,
        "route_behavior_changed": False,
        "auth_policy_changed": False,
        "patch_apply_path_changed": False,
        "validation_execution_path_changed": False,
        "benchmark_execution_path_changed": False,
        "worker_launch_path_changed": False,
        "model_routing_changed": False,
        "approval_or_rejection_performed": False,
    }
    for source, label in (
        (boundary_map, "boundary_map"),
        (contract, "token_contract"),
        (catalog, "sample_catalog"),
    ):
        scan = _scan_forbidden_markers(source, blocked, label)
        for key, value in scan.items():
            flags[key] = flags[key] or value

    authority_summary = _authority_boundary_summary(boundary_map, incomplete)
    contract_summary = _approval_token_contract_summary(contract)
    dry_run_summary = _dry_run_validator_summary(validator_text, validator_error, validator_abs)
    sample_summary = _sample_catalog_summary(catalog, sample_coverage)
    runtime_checks = _runtime_non_enforcement(flags)
    forbidden_checks = _forbidden_authority_checks(
        flags=flags,
        contract_summary=contract_summary,
        sample_summary=sample_summary,
    )
    human_boundary = _human_approval_boundary(authority_summary)

    warnings = _artifact_warnings(boundary_map, contract, catalog)
    if not _future_enforcement_boundary_explicit(contract):
        warnings.append("Approval enforcement remains future work; approval tokens are documentation/dry-run only.")
    warnings = _dedupe(warnings)
    incomplete = _dedupe(incomplete)

    status = _status(blocked, incomplete, warnings)
    summary = {
        "checkpoint_status": status,
        "all_required_human_phases_complete": bool(phase_completion["all_required_human_phases_complete"]),
        "required_artifacts_present": bool(artifact_coverage["required_artifacts_present"]),
        "sample_token_files_present": bool(artifact_coverage["sample_token_files_present"]),
        "blocked_reason_count": len(blocked),
        "incomplete_reason_count": len(incomplete),
        "warning_count": len(warnings),
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
    }

    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "guardrail_note": GUARDRAIL_NOTE,
        "report_id": str(report_id or ""),
        "created_at": str(created_at or _utc_now()),
        "repo_root": _norm_path(repo),
        "registry_path": _norm_path(registry_path),
        "checkpoint_status": status,
        "summary": summary,
        "phase_completion": phase_completion,
        "artifact_coverage": artifact_coverage,
        "authority_boundary_summary": authority_summary,
        "approval_token_contract_summary": contract_summary,
        "dry_run_validator_summary": dry_run_summary,
        "sample_catalog_summary": sample_summary,
        "sample_token_file_coverage": sample_coverage,
        "runtime_non_enforcement_verification": runtime_checks,
        "forbidden_authority_checks": forbidden_checks,
        "human_approval_boundary": human_boundary,
        "warnings": warnings,
        "blocked_reasons": blocked,
        "incomplete_reasons": incomplete,
        "final_verdict": {
            "status": status,
            "branch_frozen": status == STATUS_FROZEN,
            "branch_frozen_with_warnings": status == STATUS_FROZEN_WITH_WARNINGS,
            "ready_for_next_phase": status in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS},
            "message": _final_verdict(status),
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
        },
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "boundaries_guardrails": list(BOUNDARIES),
        "guardrails": _guardrails(),
    }


def _dict_lines(values: Any) -> list[str]:
    if not isinstance(values, dict) or not values:
        return ["_None._"]
    lines: list[str] = []
    for key in sorted(values):
        value = values[key]
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            rendered = str(value)
        lines.append(f"- `{_md(key)}`: {_md(rendered)}")
    return lines


def _list_lines(values: Any, *, key: str = "") -> list[str]:
    if not isinstance(values, list) or not values:
        return ["_None._"]
    lines: list[str] = []
    for item in values:
        if isinstance(item, dict) and key:
            lines.append(f"- {_md(item.get(key, item))}")
        elif isinstance(item, dict):
            lines.append(f"- {_md(json.dumps(item, ensure_ascii=False, sort_keys=True))}")
        else:
            lines.append(f"- {_md(item)}")
    return lines


def render_human_authority_branch_checkpoint_markdown(report: dict[str, Any]) -> str:
    """Render a HUMAN.CLOSE checkpoint report as Markdown."""
    lines: list[str] = [
        "# Human Authority Branch Checkpoint",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
    ]
    lines.extend(_dict_lines(report.get("summary")))

    lines.extend(["", "## Phase Completion", ""])
    phase = report.get("phase_completion") if isinstance(report.get("phase_completion"), dict) else {}
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
        lines.extend(["| Artifact | Phase | Present | Kind OK | Path |", "|---|---|---|---|---|"])
        for check in artifact_checks:
            lines.append(
                f"| {_md(check.get('artifact_key'))} | {_md(check.get('phase_id'))} | "
                f"{_bool(check.get('present'))} | {_bool(check.get('kind_ok'))} | "
                f"`{_md(check.get('path'))}` |"
            )
    else:
        lines.append("_None._")

    for title, key in (
        ("Authority Boundary Summary", "authority_boundary_summary"),
        ("Approval Token Contract Summary", "approval_token_contract_summary"),
        ("Dry-Run Validator Summary", "dry_run_validator_summary"),
        ("Sample Catalog Summary", "sample_catalog_summary"),
        ("Runtime Non-Enforcement Verification", "runtime_non_enforcement_verification"),
        ("Forbidden Authority Checks", "forbidden_authority_checks"),
        ("Human Approval Boundary", "human_approval_boundary"),
    ):
        lines.extend(["", f"## {title}", ""])
        lines.extend(_dict_lines(report.get(key)))

    lines.extend(["", "## Warnings", ""])
    lines.extend(_list_lines(report.get("warnings")))
    lines.extend(["", "## Blocked Reasons", ""])
    lines.extend(_list_lines(report.get("blocked_reasons"), key="reason"))
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
    for alt in alternatives:
        if isinstance(alt, dict):
            lines.append(f"- **Alternative:** `{_md(alt.get('phase_id', ''))}` - {_md(alt.get('title', ''))}")

    lines.extend(["", "## Boundaries / Guardrails", ""])
    lines.extend(_list_lines(report.get("boundaries_guardrails")))
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: `{str(bool(guardrails[key])).lower()}`")
    lines.append("")
    return "\n".join(lines)


def write_human_authority_branch_checkpoint(
    *,
    repo_root: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    boundary_map_path: str | Path = DEFAULT_BOUNDARY_MAP_PATH,
    token_contract_path: str | Path = DEFAULT_TOKEN_CONTRACT_PATH,
    dry_run_validator_path: str | Path = DEFAULT_DRY_RUN_VALIDATOR_PATH,
    sample_catalog_path: str | Path = DEFAULT_SAMPLE_CATALOG_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build and write HUMAN.CLOSE JSON/Markdown checkpoint artifacts."""
    report = build_human_authority_branch_checkpoint(
        repo_root=repo_root,
        registry_path=registry_path,
        boundary_map_path=boundary_map_path,
        token_contract_path=token_contract_path,
        dry_run_validator_path=dry_run_validator_path,
        sample_catalog_path=sample_catalog_path,
        report_id=report_id,
        created_at=created_at,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_human_authority_branch_checkpoint_markdown(report), encoding="utf-8")
    return {
        "ok": report["checkpoint_status"] in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
