"""ADOPT.MODEL.CLOSE - Model Catalog Adoption Branch Checkpoint.

Freezes the report-only ADOPT.MODEL.1 and ADOPT.MODEL.2 branch after the active
10-role advisory model catalog has been adopted and rechecked. This module reads
local JSON artifacts and writes checkpoint JSON/Markdown only. It does not route
models, call models, launch workers, create executable bindings, enforce
approvals, apply patches, run validation or benchmarks, invoke MCP tools,
contact networks, write databases, or change route/auth behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "model_role_catalog_adoption_checkpoint"
CHECKPOINT_ID = "model-role-catalog-adoption-checkpoint"
THIS_PHASE_ID = "ADOPT.MODEL.CLOSE"
REQUIRED_ADOPTION_PHASE_IDS: tuple[str, ...] = ("ADOPT.MODEL.1", "ADOPT.MODEL.2", THIS_PHASE_ID)

JSON_NAME = "model_role_catalog_adoption_checkpoint.json"
MD_NAME = "model_role_catalog_adoption_checkpoint.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "model_role_registry" / "adoption_checkpoint"

EXPECTED_ROLE_COUNT = 10
ADDED_ROLE_IDS: tuple[str, ...] = (
    "ui_reviewer",
    "test_designer",
    "documentation_reviewer",
)
PRESERVED_ROLE_IDS: tuple[str, ...] = (
    "fast_scout",
    "planner",
    "patch_implementer",
    "code_reviewer",
    "evidence_checker",
    "risk_auditor",
    "local_fallback",
)

STATUS_FROZEN = "model_catalog_adoption_branch_frozen"
STATUS_FROZEN_WITH_WARNINGS = "model_catalog_adoption_branch_frozen_with_warnings"
STATUS_INCOMPLETE = "model_catalog_adoption_branch_incomplete"
STATUS_BLOCKED = "model_catalog_adoption_branch_blocked"
CHECKPOINT_STATUSES: tuple[str, ...] = (
    STATUS_FROZEN,
    STATUS_FROZEN_WITH_WARNINGS,
    STATUS_INCOMPLETE,
    STATUS_BLOCKED,
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "HARDEN.N1",
    "title": "Approval Enforcement Readiness Audit",
    "reason": (
        "After HUMAN authority and model catalog adoption are frozen, audit where "
        "approval enforcement could safely attach before any enforcement work."
    ),
}

GUARDRAIL_NOTE = (
    "ADOPT.MODEL.CLOSE is report-only and checkpoint-only. It freezes the "
    "human-approved advisory model-role catalog adoption branch after "
    "ADOPT.MODEL.1 and ADOPT.MODEL.2. It routes no models, calls no models, "
    "launches no workers, creates no executable model bindings, enforces no "
    "approvals, applies no patches, runs no validation or benchmarks, invokes no "
    "MCP tools, contacts no network services, writes no database rows, and "
    "changes no route or auth behavior."
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "checkpoint only",
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
    "no Docker/subprocess",
    "no network",
    "no database write",
    "no route behavior change",
    "no auth policy change",
    "no approval-token enforcement",
    "no automatic authority escalation",
    "writes adoption checkpoint artifacts only",
)

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "model_call_performed",
    "model_routing_performed",
    "worker_launch_performed",
    "executable_model_binding_created",
    "automatic_assignment_performed",
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
    "routing_changed",
    "auth_policy_changed",
    "approval_token_enforcement_changed",
    "approval_enforcement_added",
    "model_calls_allowed",
    "model_routing_enabled",
    "worker_launch_allowed",
)

PHASE_GUARDRAIL_FIELDS: tuple[str, ...] = (
    "model_calls_allowed",
    "network_allowed",
    "merge_allowed",
    "writes_real_repo",
)

FORBIDDEN_AUTHORITY_FLAGS: tuple[str, ...] = (
    "auto_run",
    "auto_apply",
    "auto_merge",
    "route_tasks",
    "launch_worker",
    "run_validation",
    "run_benchmark",
    "run_tools",
    "mutate_files",
    "approve_patch",
    "apply_patch",
)

MODEL_ROUTING_KEYS: tuple[str, ...] = (
    "model_routing_enabled",
    "model_routing_performed",
    "routing_changed",
    "route_tasks",
    "routing_enabled",
    "task_routing_performed",
    "route_behavior_changed",
)
MODEL_CALL_KEYS: tuple[str, ...] = (
    "model_calls_allowed",
    "model_call_enabled",
    "model_call_performed",
)
WORKER_LAUNCH_KEYS: tuple[str, ...] = (
    "worker_launch_allowed",
    "worker_launch_enabled",
    "worker_launch_performed",
    "launch_worker",
)
MODEL_ID_AUTHORITY_KEYS: tuple[str, ...] = (
    "model",
    "model_id",
    "model_name",
    "llm",
    "authority_model",
    "authoritative_model",
    "model_authority",
    "model_binding",
    "executable_model_id",
    "execution_authority",
)
AUTHORITY_KEY_FRAGMENTS: tuple[str, ...] = (
    "can_execute",
    "can_route",
    "can_approve",
    "execute_tasks",
    "route_authority",
    "routing_authority",
    "approval_authority",
    "execution_authority",
    "final_authority",
)


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _norm_path(value: str | Path | None) -> str:
    return str(value or "").replace("\\", "/")


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _split_segments(value: str) -> list[str]:
    return [segment for segment in value.replace("\\", "/").split("/") if segment]


def _path_has_traversal(value: str) -> bool:
    return any(segment == ".." for segment in _split_segments(value))


def _input_path_findings(path: str | Path | None, label: str, *, required: bool) -> list[str]:
    if path is None or str(path).strip() == "":
        return [f"{label} path is required"] if required else []
    if _path_has_traversal(str(path).strip()):
        return [f"{label} path must not contain traversal segments"]
    return []


def read_json_input(
    path: str | Path | None,
    label: str,
    *,
    required: bool = False,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Read a JSON input and return findings instead of raising."""
    findings = _input_path_findings(path, label, required=required)
    if findings:
        return None, findings
    if path is None or str(path).strip() == "":
        return None, []
    source = Path(str(path))
    try:
        raw = source.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [f"{label} could not be read: {exc}"]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"{label} must contain valid JSON: {exc.msg}"]
    if not isinstance(data, dict):
        return None, [f"{label} must contain a JSON object"]
    return data, []


def _guardrails() -> dict[str, bool]:
    data = {key: False for key in GUARDRAIL_FALSE_FLAGS}
    data["report_only"] = True
    data["checkpoint_only"] = True
    data["writes_checkpoint_artifacts_only"] = True
    return data


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _role_id(role: dict[str, Any]) -> str:
    return str(role.get("role_id") or "").strip()


def _is_meaningful(value: Any) -> bool:
    return value not in (False, None, "", [], {})


def _truthy_key_hits(data: dict[str, Any], keys: tuple[str, ...], label: str) -> list[str]:
    hits: list[str] = []
    for key in keys:
        if data.get(key) is True:
            phrase = key.replace("_", " ")
            if key in MODEL_ROUTING_KEYS:
                phrase = "model routing"
            elif key in MODEL_CALL_KEYS:
                phrase = "model calls"
            elif key in WORKER_LAUNCH_KEYS:
                phrase = "worker launch"
            hits.append(f"{label} {phrase} enabled by {key}")
    guardrails = data.get("guardrails")
    if isinstance(guardrails, dict):
        for key in keys:
            if guardrails.get(key) is True:
                phrase = key.replace("_", " ")
                if key in MODEL_ROUTING_KEYS:
                    phrase = "model routing"
                elif key in MODEL_CALL_KEYS:
                    phrase = "model calls"
                elif key in WORKER_LAUNCH_KEYS:
                    phrase = "worker launch"
                hits.append(f"{label} {phrase} guardrail unexpectedly true: {key}")
    return hits


def _role_safety_findings(roles: list[dict[str, Any]], catalog: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    advisory_failures: list[str] = []
    executable_failures: list[str] = []
    model_id_authority_hits: list[str] = []
    model_routing_hits: list[str] = []
    model_call_hits: list[str] = []
    worker_launch_hits: list[str] = []
    forbidden_authority_hits: list[str] = []

    for reason in _truthy_key_hits(catalog, MODEL_ROUTING_KEYS, "active catalog"):
        model_routing_hits.append(reason)
        blockers.append(reason)
    for reason in _truthy_key_hits(catalog, MODEL_CALL_KEYS, "active catalog"):
        model_call_hits.append(reason)
        blockers.append(reason)
    for reason in _truthy_key_hits(catalog, WORKER_LAUNCH_KEYS, "active catalog"):
        worker_launch_hits.append(reason)
        blockers.append(reason)

    ids = [_role_id(role) for role in roles if _role_id(role)]
    for role_id in sorted({role_id for role_id in ids if ids.count(role_id) > 1}):
        blockers.append(f"duplicate role_id: {role_id}")

    for index, role in enumerate(roles):
        role_id = _role_id(role) or f"#{index}"
        if role.get("advisory_only") is not True:
            advisory_failures.append(role_id)
            blockers.append(f"role {role_id} advisory_only must be true")
        if role.get("executable_binding_allowed") is True:
            executable_failures.append(role_id)
            blockers.append(f"role {role_id} executable binding enabled by executable_binding_allowed")
        for flag in FORBIDDEN_AUTHORITY_FLAGS:
            if role.get(flag) is True:
                reason = f"role {role_id} includes forbidden authority flag: {flag}"
                forbidden_authority_hits.append(reason)
                blockers.append(reason)
        for reason in _truthy_key_hits(role, MODEL_ROUTING_KEYS, f"role {role_id}"):
            model_routing_hits.append(reason)
            blockers.append(reason)
        for reason in _truthy_key_hits(role, MODEL_CALL_KEYS, f"role {role_id}"):
            model_call_hits.append(reason)
            blockers.append(reason)
        for reason in _truthy_key_hits(role, WORKER_LAUNCH_KEYS, f"role {role_id}"):
            worker_launch_hits.append(reason)
            blockers.append(reason)

        model_id_policy = str(role.get("model_id_policy") or "descriptive_metadata_only").strip()
        if model_id_policy != "descriptive_metadata_only":
            reason = f"role {role_id} model_id_policy must keep model_ids descriptive metadata only"
            model_id_authority_hits.append(reason)
            blockers.append(reason)
        if "model_ids" in role and not isinstance(role.get("model_ids"), list):
            reason = f"role {role_id} model_ids must be a descriptive metadata list"
            model_id_authority_hits.append(reason)
            blockers.append(reason)
        for key in MODEL_ID_AUTHORITY_KEYS:
            if key in role and _is_meaningful(role.get(key)):
                reason = f"role {role_id} defines executable model authority via {key}"
                model_id_authority_hits.append(reason)
                blockers.append(reason)
        for key, value in role.items():
            low = str(key).lower()
            if any(fragment in low for fragment in AUTHORITY_KEY_FRAGMENTS) and bool(value):
                reason = f"role {role_id} claims executable authority via {key}"
                forbidden_authority_hits.append(reason)
                blockers.append(reason)

    return blockers, {
        "advisory_only_failures": sorted(set(advisory_failures)),
        "executable_binding_failures": sorted(set(executable_failures)),
        "model_id_authority_hits": sorted(set(model_id_authority_hits)),
        "model_routing_hits": sorted(set(model_routing_hits)),
        "model_call_hits": sorted(set(model_call_hits)),
        "worker_launch_hits": sorted(set(worker_launch_hits)),
        "forbidden_authority_hits": sorted(set(forbidden_authority_hits)),
    }


def _phase_map(registry_data: Any) -> dict[str, dict[str, Any]]:
    root = registry_data if isinstance(registry_data, dict) else {}
    phases = root.get("phases") if isinstance(root.get("phases"), list) else []
    return {
        str(phase["phase_id"]): phase
        for phase in phases
        if isinstance(phase, dict) and str(phase.get("phase_id") or "").strip()
    }


def _phase_guardrail_violations(phase: dict[str, Any]) -> list[str]:
    violations = [field for field in PHASE_GUARDRAIL_FIELDS if phase.get(field) is True]
    automation = str(phase.get("automation_level", ""))
    if automation not in {"LOCAL_0_OBSERVE", "LOCAL_1_PREPARE"}:
        violations.append(f"automation_level={automation or '(missing)'}")
    if phase.get("human_approval_required") is not True:
        violations.append("human_approval_required")
    return violations


def _phase_completion(registry_data: Any, incomplete: list[str], blockers: list[str]) -> dict[str, Any]:
    if not isinstance(registry_data, dict):
        incomplete.append("phase registry is missing or malformed")
    phases = _phase_map(registry_data)
    checks: list[dict[str, Any]] = []
    for phase_id in REQUIRED_ADOPTION_PHASE_IDS:
        phase = phases.get(phase_id)
        present = phase is not None
        complete = present and phase.get("status") == "complete"
        violations = _phase_guardrail_violations(phase) if present else []
        if not present:
            incomplete.append(f"{phase_id} phase is missing")
        elif not complete:
            incomplete.append(f"{phase_id} is not registered complete")
        for violation in violations:
            blockers.append(f"{phase_id} has unsafe registry guardrail: {violation}")
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
    harden_n1 = phases.get("HARDEN.N1")
    return {
        "required_phase_ids": list(REQUIRED_ADOPTION_PHASE_IDS),
        "phase_checks": checks,
        "all_required_adoption_phases_complete": all(check["complete"] for check in checks),
        "all_required_adoption_phase_guardrails_ok": all(check["guardrails_ok"] for check in checks),
        "next_phase_registered": harden_n1 is not None,
        "next_phase_status": str(harden_n1.get("status", "(missing)")) if harden_n1 else "(missing)",
    }


def _human_boundary_reference(
    human_close_data: dict[str, Any] | None,
    warnings: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    if human_close_data is None:
        warnings.append("HUMAN.CLOSE checkpoint artifact is missing or unavailable")
        return {
            "referenced": False,
            "report_kind_ok": False,
            "explicit_human_approval_required": False,
            "model_routing_not_automatic": False,
            "approval_tokens_do_not_authorize_runtime": False,
        }
    report_kind_ok = human_close_data.get("report_kind") == "human_authority_branch_checkpoint"
    if not report_kind_ok:
        warnings.append("HUMAN.CLOSE checkpoint report_kind is not human_authority_branch_checkpoint")
    for warning in _strings(human_close_data.get("warnings")):
        warnings.append(f"HUMAN.CLOSE warning: {warning}")
    for reason in _strings(human_close_data.get("blocked_reasons")):
        blockers.append(f"HUMAN.CLOSE blocker: {reason}")

    authority = human_close_data.get("authority_boundary_summary")
    authority = authority if isinstance(authority, dict) else {}
    human_boundary = human_close_data.get("human_approval_boundary")
    human_boundary = human_boundary if isinstance(human_boundary, dict) else {}
    runtime = human_close_data.get("runtime_non_enforcement_verification")
    runtime = runtime if isinstance(runtime, dict) else {}

    explicit = (
        authority.get("model_catalog_adoption_requires_explicit_human_approval") is True
        or human_boundary.get("model_catalog_adoption_requires_explicit_human_approval") is True
    )
    routing_not_auto = (
        authority.get("model_routing_is_not_automatic") is True
        or runtime.get("no_model_routing_changed") is True
    )
    tokens_not_runtime = human_boundary.get("approval_tokens_authorize_runtime_actions") is not True

    if authority.get("model_catalog_adoption_requires_explicit_human_approval") is False:
        blockers.append("HUMAN authority boundary contradicts explicit model catalog adoption approval")
    if authority.get("model_routing_is_not_automatic") is False:
        blockers.append("HUMAN authority boundary contradicts non-automatic model routing")
    if human_boundary.get("approval_tokens_authorize_runtime_actions") is True:
        blockers.append("HUMAN authority boundary treats approval tokens as runtime authority")

    return {
        "referenced": report_kind_ok,
        "report_kind_ok": report_kind_ok,
        "explicit_human_approval_required": explicit,
        "model_routing_not_automatic": routing_not_auto,
        "approval_tokens_do_not_authorize_runtime": tokens_not_runtime,
    }


def _artifact_summary(name: str, data: dict[str, Any] | None, expected_kind: str) -> dict[str, Any]:
    return {
        "artifact": name,
        "present": data is not None,
        "report_kind": str(data.get("report_kind") or "") if isinstance(data, dict) else "",
        "expected_report_kind": expected_kind,
        "report_kind_ok": bool(isinstance(data, dict) and data.get("report_kind") == expected_kind),
    }


def _status(blockers: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blockers:
        return STATUS_BLOCKED
    if incomplete:
        return STATUS_INCOMPLETE
    if warnings:
        return STATUS_FROZEN_WITH_WARNINGS
    return STATUS_FROZEN


def build_model_role_catalog_adoption_checkpoint(
    *,
    registry_path: str | Path | None,
    registry_data: dict[str, Any] | None,
    active_catalog_path: str | Path | None,
    active_catalog_data: dict[str, Any] | None,
    adoption_receipt_path: str | Path | None,
    adoption_receipt_data: dict[str, Any] | None,
    post_adoption_coverage_path: str | Path | None,
    post_adoption_coverage_data: dict[str, Any] | None,
    model_close_path: str | Path | None = None,
    model_close_data: dict[str, Any] | None = None,
    human_close_path: str | Path | None = None,
    human_close_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
    input_incomplete: list[str] | None = None,
    input_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build the deterministic ADOPT.MODEL.CLOSE checkpoint report."""
    blockers = list(input_blockers or [])
    incomplete = list(input_incomplete or [])
    warnings = list(input_warnings or [])

    blockers += _input_path_findings(active_catalog_path, "active catalog", required=True)
    incomplete += _input_path_findings(registry_path, "phase registry", required=True)
    incomplete += _input_path_findings(adoption_receipt_path, "adoption receipt", required=True)
    incomplete += _input_path_findings(post_adoption_coverage_path, "post-adoption coverage", required=True)
    warnings += _input_path_findings(model_close_path, "MODEL.CLOSE checkpoint", required=False)
    warnings += _input_path_findings(human_close_path, "HUMAN.CLOSE checkpoint", required=False)

    phase_completion = _phase_completion(registry_data, incomplete, blockers)

    if active_catalog_data is None:
        active_catalog_data = {}
        blockers.append("active catalog is missing or malformed")
    if not isinstance(active_catalog_data, dict):
        active_catalog_data = {}
        blockers.append("active catalog must contain a JSON object")
    if active_catalog_data.get("report_kind") != "model_role_registry":
        blockers.append("active catalog report_kind must be model_role_registry")
    if not isinstance(active_catalog_data.get("roles"), list):
        blockers.append("active catalog roles must be a list")
    active_roles = _list_of_dicts(active_catalog_data.get("roles"))
    active_role_ids = [_role_id(role) for role in active_roles if _role_id(role)]
    active_role_set = set(active_role_ids)
    active_role_count = len(active_roles)
    declared_role_count = active_catalog_data.get("role_count")
    if isinstance(declared_role_count, int) and declared_role_count != active_role_count:
        blockers.append(f"active catalog role_count {declared_role_count} does not match roles {active_role_count}")
    if active_role_count < EXPECTED_ROLE_COUNT:
        blockers.append(f"active catalog has fewer than 10 roles: {active_role_count}")
    elif active_role_count > EXPECTED_ROLE_COUNT:
        warnings.append(f"active catalog has more than expected 10 roles: {active_role_count}")

    if adoption_receipt_data is None:
        adoption_receipt_data = {}
        incomplete.append("adoption receipt is missing or malformed")
    if not isinstance(adoption_receipt_data, dict):
        adoption_receipt_data = {}
        incomplete.append("adoption receipt must contain a JSON object")
    if adoption_receipt_data and adoption_receipt_data.get("report_kind") != "model_role_catalog_adoption_receipt":
        incomplete.append("adoption receipt report_kind must be model_role_catalog_adoption_receipt")
    adoption_status = str(adoption_receipt_data.get("adoption_status") or "")
    if adoption_receipt_data and adoption_status not in {
        "model_role_catalog_adoption_complete",
        "model_role_catalog_adoption_complete_with_warnings",
    }:
        incomplete.append("adoption receipt must show complete ADOPT.MODEL.1 adoption")
    for warning in _strings(adoption_receipt_data.get("warnings")):
        warnings.append(f"adoption receipt warning: {warning}")
    for reason in _strings(adoption_receipt_data.get("blocked_reasons")):
        blockers.append(f"adoption receipt blocker: {reason}")

    if post_adoption_coverage_data is None:
        post_adoption_coverage_data = {}
        incomplete.append("post-adoption coverage report is missing or malformed")
    if not isinstance(post_adoption_coverage_data, dict):
        post_adoption_coverage_data = {}
        incomplete.append("post-adoption coverage report must contain a JSON object")
    if (
        post_adoption_coverage_data
        and post_adoption_coverage_data.get("report_kind") != "model_role_post_adoption_coverage"
    ):
        incomplete.append("post-adoption coverage report_kind must be model_role_post_adoption_coverage")
    coverage_status = str(post_adoption_coverage_data.get("post_adoption_coverage_status") or "")
    if post_adoption_coverage_data and coverage_status not in {
        "model_role_post_adoption_coverage_ready",
        "model_role_post_adoption_coverage_ready_with_warnings",
    }:
        incomplete.append("post-adoption coverage must be ready before ADOPT.MODEL.CLOSE")
    for warning in _strings(post_adoption_coverage_data.get("warnings")):
        warnings.append(f"post-adoption coverage warning: {warning}")
    for reason in _strings(post_adoption_coverage_data.get("incomplete_reasons")):
        incomplete.append(f"post-adoption coverage incomplete: {reason}")
    for reason in _strings(post_adoption_coverage_data.get("blocked_reasons")):
        blockers.append(f"post-adoption coverage blocker: {reason}")

    previous_role_ids = _strings(adoption_receipt_data.get("preserved_roles")) or list(PRESERVED_ROLE_IDS)
    missing_previous_roles = [role_id for role_id in previous_role_ids if role_id not in active_role_set]
    for role_id in missing_previous_roles:
        blockers.append(f"active catalog loses previous required role: {role_id}")

    added_roles = list(ADDED_ROLE_IDS)
    receipt_added = set(_strings(adoption_receipt_data.get("added_roles")))
    if adoption_receipt_data and not set(ADDED_ROLE_IDS) <= receipt_added:
        missing = [role_id for role_id in ADDED_ROLE_IDS if role_id not in receipt_added]
        incomplete.append("adoption receipt cannot verify added roles: " + ", ".join(missing))

    added_roles_verified = all(role_id in active_role_set for role_id in ADDED_ROLE_IDS)
    preserved_roles_verified = all(role_id in active_role_set for role_id in previous_role_ids)
    if not added_roles_verified and active_role_count >= EXPECTED_ROLE_COUNT:
        incomplete.append("active catalog cannot verify added roles: " + ", ".join(ADDED_ROLE_IDS))
    if not preserved_roles_verified:
        blockers.append("active catalog does not preserve all previous roles")

    coverage_resolved = _strings(post_adoption_coverage_data.get("resolved_gaps"))
    coverage_unresolved = _strings(post_adoption_coverage_data.get("unresolved_gaps"))
    resolved_gaps = [role_id for role_id in ADDED_ROLE_IDS if role_id in active_role_set and role_id in coverage_resolved]
    unresolved_gaps = [
        role_id for role_id in ADDED_ROLE_IDS if role_id not in active_role_set or role_id not in coverage_resolved
    ]
    if post_adoption_coverage_data and set(ADDED_ROLE_IDS) - set(coverage_resolved):
        incomplete.append("post-adoption coverage cannot verify resolved gaps: " + ", ".join(unresolved_gaps))
    if coverage_unresolved:
        incomplete.append("post-adoption coverage still reports unresolved gaps: " + ", ".join(coverage_unresolved))
    if post_adoption_coverage_data.get("added_roles_verified") is not True:
        incomplete.append("post-adoption coverage did not verify added roles")
    if post_adoption_coverage_data.get("preserved_roles_verified") is not True:
        incomplete.append("post-adoption coverage did not verify preserved roles")

    role_blockers, safety_findings = _role_safety_findings(active_roles, active_catalog_data)
    blockers += role_blockers

    advisory_only_confirmed = bool(active_roles) and not safety_findings["advisory_only_failures"] and all(
        role.get("advisory_only") is True for role in active_roles
    )
    executable_binding_allowed_confirmed_false = bool(active_roles) and not safety_findings[
        "executable_binding_failures"
    ] and all(role.get("executable_binding_allowed") is False for role in active_roles)
    model_routing_enabled_confirmed_false = not safety_findings["model_routing_hits"]
    model_calls_allowed_confirmed_false = not safety_findings["model_call_hits"]
    worker_launch_allowed_confirmed_false = not safety_findings["worker_launch_hits"]
    model_ids_metadata_only_confirmed = not safety_findings["model_id_authority_hits"]

    if model_close_data is None:
        warnings.append("MODEL.CLOSE checkpoint artifact is missing or unavailable")
    elif not isinstance(model_close_data, dict):
        warnings.append("MODEL.CLOSE checkpoint artifact must contain a JSON object")
    else:
        if model_close_data.get("report_kind") != "model_role_planning_checkpoint":
            warnings.append("MODEL.CLOSE checkpoint report_kind is not model_role_planning_checkpoint")
        model_close_warnings = _strings(model_close_data.get("warnings"))
        if model_close_warnings:
            warnings.append(
                f"MODEL.CLOSE checkpoint has {len(model_close_warnings)} historical planning warning(s)"
            )
        for reason in _strings(model_close_data.get("blocked_reasons")):
            blockers.append(f"MODEL.CLOSE blocker: {reason}")
        for reason in _strings(model_close_data.get("incomplete_reasons")):
            incomplete.append(f"MODEL.CLOSE incomplete: {reason}")

    human_boundary = _human_boundary_reference(human_close_data, warnings, blockers)
    human_authority_boundary_referenced = bool(human_boundary["referenced"])

    warnings.append(
        "Future model routing, model execution, and approval enforcement remain intentionally not implemented."
    )

    blockers = _unique(blockers)
    incomplete = _unique(incomplete)
    warnings = _unique(warnings)
    status = _status(blockers, incomplete, warnings)

    safety_boundary = {
        **safety_findings,
        "active_role_ids": active_role_ids,
        "expected_added_roles": list(ADDED_ROLE_IDS),
        "previous_roles_expected": previous_role_ids,
        "previous_roles_missing": missing_previous_roles,
        "added_roles_verified": added_roles_verified,
        "preserved_roles_verified": preserved_roles_verified,
        "passed": not blockers,
    }
    runtime_non_execution = {
        "no_model_calls": model_calls_allowed_confirmed_false,
        "no_model_routing": model_routing_enabled_confirmed_false,
        "no_worker_launch": worker_launch_allowed_confirmed_false,
        "no_executable_binding": executable_binding_allowed_confirmed_false,
        "no_patch_apply": True,
        "no_validation_run": True,
        "no_benchmark_run": True,
        "no_route_behavior_change": True,
        "no_auth_policy_change": True,
        "no_approval_token_enforcement": True,
    }

    return {
        "report_kind": REPORT_KIND,
        "checkpoint_id": CHECKPOINT_ID,
        "phase_id": THIS_PHASE_ID,
        "guardrail_note": GUARDRAIL_NOTE,
        "checkpoint_status": status,
        "checkpoint_statuses": list(CHECKPOINT_STATUSES),
        "active_catalog_path": _norm_path(active_catalog_path),
        "adoption_receipt_path": _norm_path(adoption_receipt_path),
        "post_adoption_coverage_path": _norm_path(post_adoption_coverage_path),
        "model_close_path": _norm_path(model_close_path),
        "human_close_path": _norm_path(human_close_path),
        "registry_path": _norm_path(registry_path),
        "active_role_count": active_role_count,
        "expected_role_count": EXPECTED_ROLE_COUNT,
        "added_roles": added_roles,
        "resolved_gaps": resolved_gaps,
        "unresolved_gaps": unresolved_gaps,
        "preserved_roles_verified": preserved_roles_verified,
        "advisory_only_confirmed": advisory_only_confirmed,
        "executable_binding_allowed_confirmed_false": executable_binding_allowed_confirmed_false,
        "model_routing_enabled_confirmed_false": model_routing_enabled_confirmed_false,
        "model_calls_allowed_confirmed_false": model_calls_allowed_confirmed_false,
        "worker_launch_allowed_confirmed_false": worker_launch_allowed_confirmed_false,
        "model_ids_metadata_only_confirmed": model_ids_metadata_only_confirmed,
        "human_authority_boundary_referenced": human_authority_boundary_referenced,
        "adoption_branch_summary": {
            "adopt_model_1_complete": adoption_status
            in {"model_role_catalog_adoption_complete", "model_role_catalog_adoption_complete_with_warnings"},
            "adopt_model_2_complete": coverage_status
            in {"model_role_post_adoption_coverage_ready", "model_role_post_adoption_coverage_ready_with_warnings"},
            "active_catalog_is_10_role_advisory_catalog": active_role_count == EXPECTED_ROLE_COUNT
            and advisory_only_confirmed,
            "branch_can_freeze": status in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS},
        },
        "phase_completion": phase_completion,
        "artifact_coverage": {
            "artifacts": [
                _artifact_summary("active_catalog", active_catalog_data, "model_role_registry"),
                _artifact_summary("adoption_receipt", adoption_receipt_data, "model_role_catalog_adoption_receipt"),
                _artifact_summary(
                    "post_adoption_coverage",
                    post_adoption_coverage_data,
                    "model_role_post_adoption_coverage",
                ),
                _artifact_summary("model_close", model_close_data, "model_role_planning_checkpoint"),
                _artifact_summary("human_close", human_close_data, "human_authority_branch_checkpoint"),
            ],
            "required_artifacts_present": bool(active_catalog_data and adoption_receipt_data and post_adoption_coverage_data),
        },
        "active_catalog_verification": {
            "active_role_ids": active_role_ids,
            "role_count_matches_expected": active_role_count == EXPECTED_ROLE_COUNT,
            "declared_role_count": declared_role_count,
        },
        "added_role_verification": {
            "expected_added_roles": list(ADDED_ROLE_IDS),
            "added_roles_verified": added_roles_verified,
        },
        "gap_resolution_summary": {
            "resolved_gaps": resolved_gaps,
            "unresolved_gaps": unresolved_gaps,
            "coverage_resolved_gaps": coverage_resolved,
        },
        "safety_boundary_verification": safety_boundary,
        "human_authority_boundary_reference": human_boundary,
        "runtime_non_execution_verification": runtime_non_execution,
        "warnings": warnings,
        "blocked_reasons": blockers,
        "incomplete_reasons": incomplete,
        "final_verdict": {
            "status": status,
            "branch_frozen": status == STATUS_FROZEN,
            "branch_frozen_with_warnings": status == STATUS_FROZEN_WITH_WARNINGS,
            "ready_for_next_phase": status in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS},
            "message": (
                "Model catalog adoption branch is frozen with explicit future-work warnings."
                if status == STATUS_FROZEN_WITH_WARNINGS
                else "Model catalog adoption branch checkpoint status is " + status
            ),
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
        },
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
    }


def _bool(value: Any) -> str:
    return str(bool(value)).lower()


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


def _list_lines(values: Any, *, code: bool = False) -> list[str]:
    if not isinstance(values, list) or not values:
        return ["_None._"]
    lines: list[str] = []
    for value in values:
        if isinstance(value, dict):
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            text = str(value)
        lines.append(f"- `{_md(text)}`" if code else f"- {_md(text)}")
    return lines


def render_model_role_catalog_adoption_checkpoint_markdown(report: dict[str, Any]) -> str:
    """Render the ADOPT.MODEL.CLOSE checkpoint as Markdown."""
    lines: list[str] = [
        "# Model Catalog Adoption Branch Checkpoint",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Checkpoint status:** `{_md(report.get('checkpoint_status', ''))}`",
        f"- **Active role count:** {report.get('active_role_count', 0)}",
        f"- **Expected role count:** {report.get('expected_role_count', 0)}",
        f"- **Resolved gaps:** {len(report.get('resolved_gaps') or [])}",
        f"- **Unresolved gaps:** {len(report.get('unresolved_gaps') or [])}",
        f"- **Blocked reasons:** {len(report.get('blocked_reasons') or [])}",
        f"- **Incomplete reasons:** {len(report.get('incomplete_reasons') or [])}",
        "",
        "## Phase Completion",
        "",
    ]
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
    artifacts = (report.get("artifact_coverage") or {}).get("artifacts") if isinstance(report.get("artifact_coverage"), dict) else []
    if artifacts:
        lines.extend(["| Artifact | Present | Kind OK | Report kind |", "|---|---|---|---|"])
        for artifact in artifacts:
            lines.append(
                f"| {_md(artifact.get('artifact'))} | {_bool(artifact.get('present'))} | "
                f"{_bool(artifact.get('report_kind_ok'))} | {_md(artifact.get('report_kind'))} |"
            )
    else:
        lines.append("_None._")

    for title, key in (
        ("Active Catalog Verification", "active_catalog_verification"),
        ("Added Role Verification", "added_role_verification"),
        ("Gap Resolution Summary", "gap_resolution_summary"),
        ("Safety Boundary Verification", "safety_boundary_verification"),
        ("Human Authority Boundary Reference", "human_authority_boundary_reference"),
        ("Runtime Non-Execution Verification", "runtime_non_execution_verification"),
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


def write_model_role_catalog_adoption_checkpoint(
    *,
    registry_path: str | Path,
    active_catalog_path: str | Path,
    adoption_receipt_path: str | Path,
    post_adoption_coverage_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    model_close_path: str | Path | None = None,
    human_close_path: str | Path | None = None,
    registry_data: dict[str, Any] | None = None,
    active_catalog_data: dict[str, Any] | None = None,
    adoption_receipt_data: dict[str, Any] | None = None,
    post_adoption_coverage_data: dict[str, Any] | None = None,
    model_close_data: dict[str, Any] | None = None,
    human_close_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
    input_incomplete: list[str] | None = None,
    input_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build and write ADOPT.MODEL.CLOSE JSON and Markdown artifacts."""
    blockers = list(input_blockers or [])
    incomplete = list(input_incomplete or [])
    warnings = list(input_warnings or [])
    if registry_data is None:
        registry_data, findings = read_json_input(registry_path, "phase registry", required=True)
        incomplete += findings
    if active_catalog_data is None:
        active_catalog_data, findings = read_json_input(active_catalog_path, "active catalog", required=True)
        blockers += findings
    if adoption_receipt_data is None:
        adoption_receipt_data, findings = read_json_input(adoption_receipt_path, "adoption receipt", required=True)
        incomplete += findings
    if post_adoption_coverage_data is None:
        post_adoption_coverage_data, findings = read_json_input(
            post_adoption_coverage_path,
            "post-adoption coverage",
            required=True,
        )
        incomplete += findings
    if model_close_path is not None and model_close_data is None:
        model_close_data, findings = read_json_input(model_close_path, "MODEL.CLOSE checkpoint", required=False)
        warnings += findings
    if human_close_path is not None and human_close_data is None:
        human_close_data, findings = read_json_input(human_close_path, "HUMAN.CLOSE checkpoint", required=False)
        warnings += findings

    report = build_model_role_catalog_adoption_checkpoint(
        registry_path=registry_path,
        registry_data=registry_data,
        active_catalog_path=active_catalog_path,
        active_catalog_data=active_catalog_data,
        adoption_receipt_path=adoption_receipt_path,
        adoption_receipt_data=adoption_receipt_data,
        post_adoption_coverage_path=post_adoption_coverage_path,
        post_adoption_coverage_data=post_adoption_coverage_data,
        model_close_path=model_close_path,
        model_close_data=model_close_data,
        human_close_path=human_close_path,
        human_close_data=human_close_data,
        input_blockers=blockers,
        input_incomplete=incomplete,
        input_warnings=warnings,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_model_role_catalog_adoption_checkpoint_markdown(report), encoding="utf-8")
    return {
        "ok": report["checkpoint_status"] in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
