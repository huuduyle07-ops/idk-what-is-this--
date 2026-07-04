"""MODEL.N7 - Model Role Catalog Adoption Readiness Check (report-only).

Reads MODEL.N4, MODEL.N5, MODEL.N6, MODEL.N1, and proposed registry artifacts
and writes a deterministic readiness report. MODEL.N7 never replaces the active
MODEL.N1 registry, mutates proposed registries, changes runtime model selection,
routes tasks, calls models, launches workers, binds executable model IDs,
applies patches, runs validation or benchmarks, invokes MCP tools, contacts
networks, writes databases, or changes runtime behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "model_role_catalog_adoption_readiness"
JSON_NAME = "model_role_catalog_adoption_readiness.json"
MD_NAME = "model_role_catalog_adoption_readiness.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "model_role_registry" / "model_role_catalog_adoption_readiness"

PROPOSAL_REPORT_KIND = "model_role_catalog_update_proposal"
REVIEW_REPORT_KIND = "model_role_catalog_proposal_review"
ADOPTION_PLAN_REPORT_KIND = "model_role_catalog_adoption_plan"
SOURCE_REGISTRY_REPORT_KIND = "model_role_registry"
PROPOSED_REGISTRY_REPORT_KIND = "proposed_model_role_registry"

READINESS_STATUSES: tuple[str, ...] = (
    "adoption_readiness_ready",
    "adoption_readiness_ready_with_warnings",
    "adoption_readiness_incomplete",
    "adoption_readiness_blocked",
)

PROPOSAL_READY_STATUSES: tuple[str, ...] = (
    "catalog_update_proposal_ready",
    "catalog_update_proposal_ready_with_warnings",
)

REVIEW_READY_STATUSES: tuple[str, ...] = (
    "catalog_proposal_review_ready",
    "catalog_proposal_review_ready_with_warnings",
)

ADOPTION_PLAN_READY_STATUSES: tuple[str, ...] = (
    "adoption_plan_ready",
    "adoption_plan_ready_with_warnings",
)

FORBIDDEN_AUTHORITY_FLAGS: tuple[str, ...] = (
    "auto_run",
    "auto_apply",
    "auto_merge",
    "route_tasks",
    "launch_worker",
    "run_validation",
    "run_benchmark",
    "mutate_files",
    "approve_patch",
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
    "source_registry_mutated",
    "proposed_registry_mutated",
    "automatic_adoption_performed",
    "automatic_registry_update_performed",
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "readiness check only",
    "deterministic/artifact input only",
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
    "no executable model binding",
    "no automatic assignment",
    "no source registry mutation",
    "no proposed registry mutation",
    "no automatic adoption",
    "writes readiness artifacts only",
)

MODEL_ROLE_CATALOG_ADOPTION_READINESS_GUARDRAIL_NOTE = (
    "Model Role Catalog Adoption Readiness Check is report-only: it verifies "
    "whether the MODEL.N4 proposal, MODEL.N5 review, MODEL.N6 adoption plan, "
    "MODEL.N1 source registry, and MODEL.N4 proposed registry are safe and "
    "complete enough for a future human-approved adoption phase. It does not "
    "replace MODEL.N1, mutate proposed registries, change runtime model "
    "selection, route tasks, call models, launch workers, bind executable model "
    "IDs, apply patches, run validation or benchmarks, invoke MCP tools, "
    "contact networks, write databases, or perform automatic adoption."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "MODEL.CLOSE",
    "title": "Model Role Planning Checkpoint",
    "reason": (
        "Freeze the report-only MODEL role-planning branch before any separate "
        "human-approved adoption writes to the active MODEL.N1 artifact."
    ),
}

ACTIVE_REGISTRY_JSON = ".agent/model_role_registry/model_role_registry.json"
ACTIVE_REGISTRY_MD = ".agent/model_role_registry/model_role_registry.md"
PROPOSED_REGISTRY_JSON = (
    ".agent/model_role_registry/model_role_catalog_update_proposal/proposed_model_role_registry.json"
)

FILES_THAT_MUST_NOT_CHANGE: tuple[str, ...] = (
    ACTIVE_REGISTRY_JSON,
    ACTIVE_REGISTRY_MD,
    PROPOSED_REGISTRY_JSON,
    ".agent/model_role_registry/model_role_catalog_update_proposal/model_role_catalog_update_proposal.json",
    ".agent/model_role_registry/model_role_catalog_proposal_review/model_role_catalog_proposal_review.json",
    ".agent/model_role_registry/model_role_catalog_adoption_plan/model_role_catalog_adoption_plan.json",
    "core/router.py",
    "core/driver_model_routing.py",
    "web/routes/",
    "agents/",
)


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _unique(values: list[str]) -> list[str]:
    return sorted(dict.fromkeys(str(value) for value in values if str(value)))


def _split_segments(value: str) -> list[str]:
    return [segment for segment in value.replace("\\", "/").split("/") if segment]


def _path_has_traversal(value: str) -> bool:
    return any(segment == ".." for segment in _split_segments(value))


def _input_path_blockers(path: str | Path | None, label: str, *, required: bool) -> list[str]:
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
    """Read a JSON input file and return blockers instead of raising."""
    blockers = _input_path_blockers(path, label, required=required)
    if blockers:
        return None, blockers
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


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _role_id(role: dict[str, Any]) -> str:
    return str(role.get("role_id") or "").strip()


def _role_ids(roles: list[dict[str, Any]]) -> list[str]:
    return [_role_id(role) for role in roles if _role_id(role)]


def _is_meaningful(value: Any) -> bool:
    return value not in (False, None, "", [], {})


def _source_roles(source_registry_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(source_registry_data, dict):
        return []
    return _list_of_dicts(source_registry_data.get("roles"))


def _proposed_roles(proposed_registry_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(proposed_registry_data, dict):
        return []
    return _list_of_dicts(proposed_registry_data.get("roles"))


def _role_ids_from_role_list(value: Any) -> list[str]:
    return _role_ids(_list_of_dicts(value))


def _expected_new_role_ids(
    proposal_data: dict[str, Any],
    review_data: dict[str, Any],
    adoption_plan_data: dict[str, Any],
) -> list[str]:
    values: list[str] = []
    values += _role_ids_from_role_list(proposal_data.get("proposed_new_roles"))
    role_review = review_data.get("proposed_role_review")
    if isinstance(role_review, dict):
        values += _strings(role_review.get("proposed_new_role_ids"))
    values += _role_ids_from_role_list(adoption_plan_data.get("proposed_new_roles"))
    return _unique(values)


def _count_candidates(
    proposal_data: dict[str, Any],
    review_data: dict[str, Any],
    adoption_plan_data: dict[str, Any],
) -> dict[str, int]:
    candidates: dict[str, int] = {}
    diff_summary = proposal_data.get("diff_summary")
    if isinstance(diff_summary, dict) and isinstance(diff_summary.get("proposed_role_count"), int):
        candidates["proposal diff_summary proposed_role_count"] = int(diff_summary["proposed_role_count"])
    if isinstance(proposal_data.get("proposed_role_count"), int):
        candidates["proposal proposed_role_count"] = int(proposal_data["proposed_role_count"])
    proposal_summary = review_data.get("proposal_summary")
    if isinstance(proposal_summary, dict) and isinstance(proposal_summary.get("proposed_role_count"), int):
        candidates["review proposal_summary proposed_role_count"] = int(proposal_summary["proposed_role_count"])
    if isinstance(adoption_plan_data.get("proposed_role_count"), int):
        candidates["adoption plan proposed_role_count"] = int(adoption_plan_data["proposed_role_count"])
    return candidates


def _artifact_guardrail_blockers(data: dict[str, Any], label: str) -> list[str]:
    guardrails = data.get("guardrails")
    if not isinstance(guardrails, dict):
        return []
    return [f"{label} guardrail unexpectedly true: {key}" for key, value in guardrails.items() if value is True]


def _role_safety(
    proposed_roles: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    advisory_failures: list[str] = []
    executable_failures: list[str] = []
    forbidden_hits: list[str] = []
    model_id_authority_hits: list[str] = []
    duplicate_ids: list[str] = []

    ids = _role_ids(proposed_roles)
    for role_id in sorted({role_id for role_id in ids if ids.count(role_id) > 1}):
        duplicate_ids.append(role_id)
        blockers.append(f"duplicate role_id: {role_id}")

    for index, role in enumerate(proposed_roles):
        role_id = _role_id(role) or f"#{index}"
        if role.get("advisory_only") is not True:
            advisory_failures.append(role_id)
            blockers.append(f"role {role_id} advisory_only must be true")
        if role.get("executable_binding_allowed") is True:
            executable_failures.append(role_id)
            blockers.append(f"role {role_id} executable_binding_allowed must be false")
        for flag in FORBIDDEN_AUTHORITY_FLAGS:
            if role.get(flag) is True:
                reason = f"role {role_id} includes forbidden authority flag: {flag}"
                forbidden_hits.append(reason)
                blockers.append(reason)
        model_id_policy = str(role.get("model_id_policy") or "descriptive_metadata_only").strip()
        if model_id_policy != "descriptive_metadata_only":
            reason = f"role {role_id} model_id_policy must keep model_ids descriptive metadata only"
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
                forbidden_hits.append(reason)
                blockers.append(reason)
        if not _strings(role.get("forbidden_task_types")):
            warnings.append(f"role {role_id} has empty forbidden_task_types")

    safety_checks = {
        "advisory_only_preserved": not advisory_failures,
        "advisory_only_failures": _unique(advisory_failures),
        "executable_binding_disallowed": not executable_failures,
        "executable_binding_failures": _unique(executable_failures),
        "model_ids_metadata_only": not model_id_authority_hits,
        "model_id_authority_hits": _unique(model_id_authority_hits),
        "forbidden_authority_absent": not forbidden_hits,
        "forbidden_authority_hits": _unique(forbidden_hits),
        "duplicate_role_ids": duplicate_ids,
    }
    return safety_checks, warnings, blockers


def _status(*, blockers: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blockers:
        return "adoption_readiness_blocked"
    if incomplete:
        return "adoption_readiness_incomplete"
    if warnings:
        return "adoption_readiness_ready_with_warnings"
    return "adoption_readiness_ready"


def _status_check(
    *,
    label: str,
    status: str,
    ready_statuses: tuple[str, ...],
    warning_status: str,
    incomplete_status: str,
    blockers: list[str],
    warnings: list[str],
    incomplete: list[str],
) -> None:
    if status not in ready_statuses:
        if status == incomplete_status:
            incomplete.append(f"{label} status is {status}")
        else:
            blockers.append(f"{label} status must be ready or ready_with_warnings")
    if status == warning_status:
        warnings.append(f"{label} status is {status}")


def _rollback_readiness(adoption_plan_data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    rollback = adoption_plan_data.get("rollback_plan")
    if not isinstance(rollback, dict) or not rollback:
        return {"present": False, "explicit": False, "passed": False}, ["rollback plan missing"]
    preserve_path = str(rollback.get("preserve_current_registry_artifact_path") or "").strip()
    restore_backup = rollback.get("restore_backup_if_validation_fails") is True
    human_retry = rollback.get("human_confirmation_required_before_retry") is True
    steps = rollback.get("rollback_steps")
    has_steps = isinstance(steps, list) and bool(steps)
    if not preserve_path:
        blockers.append("rollback plan must preserve current registry artifact path")
    if not restore_backup:
        blockers.append("rollback plan must restore backup if validation fails")
    if not human_retry:
        blockers.append("rollback plan must require human confirmation before retry")
    if not has_steps:
        blockers.append("rollback plan must include explicit rollback steps")
    check = {
        "present": True,
        "preserve_current_registry_artifact_path": preserve_path,
        "restore_backup_if_validation_fails": restore_backup,
        "human_confirmation_required_before_retry": human_retry,
        "rollback_steps_present": has_steps,
        "explicit": not blockers,
        "passed": not blockers,
    }
    return check, blockers


def _human_approval_readiness(adoption_plan_data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    checklist = _strings(adoption_plan_data.get("human_approval_checklist"))
    has_separate_phase = any(
        "separate" in item.lower() and "adoption" in item.lower() and "phase" in item.lower()
        for item in checklist
    )
    blockers = [] if has_separate_phase else ["human approval checklist must require separate adoption phase"]
    return {
        "checklist_item_count": len(checklist),
        "separate_adoption_phase_required": has_separate_phase,
        "passed": not blockers,
    }, blockers


def _adoption_boundary_check(adoption_plan_data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    boundaries = _strings(adoption_plan_data.get("boundaries"))
    files_that_must_not_change = _strings(adoption_plan_data.get("files_that_must_not_change"))
    has_no_automatic_adoption = "no automatic adoption" in boundaries
    active_registry_protected = ACTIVE_REGISTRY_JSON in files_that_must_not_change
    blockers: list[str] = []
    if not has_no_automatic_adoption:
        blockers.append("adoption boundary must include no automatic adoption")
    if not active_registry_protected:
        blockers.append("files_that_must_not_change must include active registry")
    return {
        "no_automatic_adoption_boundary_present": has_no_automatic_adoption,
        "active_registry_protected": active_registry_protected,
        "files_that_must_not_change": files_that_must_not_change,
        "passed": not blockers,
    }, blockers


def build_model_role_catalog_adoption_readiness(
    *,
    proposal_path: str | Path | None,
    proposal_data: dict[str, Any] | None = None,
    review_path: str | Path | None = None,
    review_data: dict[str, Any] | None = None,
    adoption_plan_path: str | Path | None = None,
    adoption_plan_data: dict[str, Any] | None = None,
    source_registry_path: str | Path | None = None,
    source_registry_data: dict[str, Any] | None = None,
    proposed_registry_path: str | Path | None = None,
    proposed_registry_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic MODEL.N7 readiness report from loaded artifacts."""
    blockers = list(input_blockers or [])
    blockers += _input_path_blockers(proposal_path, "proposal", required=True)
    blockers += _input_path_blockers(review_path, "review", required=True)
    blockers += _input_path_blockers(adoption_plan_path, "adoption plan", required=True)
    blockers += _input_path_blockers(source_registry_path, "source registry", required=True)
    blockers += _input_path_blockers(proposed_registry_path, "proposed registry", required=True)
    warnings: list[str] = []
    incomplete: list[str] = []

    if proposal_data is None:
        proposal_data = {}
        blockers.append("proposal is missing or malformed")
    if not isinstance(proposal_data, dict):
        proposal_data = {}
        blockers.append("proposal must contain a JSON object")
    if review_data is None:
        review_data = {}
        blockers.append("review is missing or malformed")
    if not isinstance(review_data, dict):
        review_data = {}
        blockers.append("review must contain a JSON object")
    if adoption_plan_data is None:
        adoption_plan_data = {}
        blockers.append("adoption plan is missing or malformed")
    if not isinstance(adoption_plan_data, dict):
        adoption_plan_data = {}
        blockers.append("adoption plan must contain a JSON object")
    if source_registry_data is None:
        source_registry_data = {}
        blockers.append("source registry is missing or malformed")
    if not isinstance(source_registry_data, dict):
        source_registry_data = {}
        blockers.append("source registry must contain a JSON object")
    if proposed_registry_data is None:
        proposed_registry_data = {}
        blockers.append("proposed registry is missing or malformed")
    if not isinstance(proposed_registry_data, dict):
        proposed_registry_data = {}
        blockers.append("proposed registry must contain a JSON object")

    if proposal_data.get("report_kind") != PROPOSAL_REPORT_KIND:
        blockers.append("proposal report_kind must be model_role_catalog_update_proposal")
    proposal_status = str(proposal_data.get("proposal_status") or "")
    _status_check(
        label="proposal",
        status=proposal_status,
        ready_statuses=PROPOSAL_READY_STATUSES,
        warning_status="catalog_update_proposal_ready_with_warnings",
        incomplete_status="catalog_update_proposal_incomplete",
        blockers=blockers,
        warnings=warnings,
        incomplete=incomplete,
    )
    for reason in _strings(proposal_data.get("blocked_reasons")):
        blockers.append(f"proposal blocker: {reason}")
    warnings += [f"proposal warning: {item}" for item in _strings(proposal_data.get("warnings"))]

    if review_data.get("report_kind") != REVIEW_REPORT_KIND:
        blockers.append("review report_kind must be model_role_catalog_proposal_review")
    review_status = str(review_data.get("review_status") or "")
    _status_check(
        label="review",
        status=review_status,
        ready_statuses=REVIEW_READY_STATUSES,
        warning_status="catalog_proposal_review_ready_with_warnings",
        incomplete_status="catalog_proposal_review_incomplete",
        blockers=blockers,
        warnings=warnings,
        incomplete=incomplete,
    )
    for reason in _strings(review_data.get("blocked_reasons")):
        blockers.append(f"review blocker: {reason}")
    warnings += [f"review warning: {item}" for item in _strings(review_data.get("warnings"))]

    if adoption_plan_data.get("report_kind") != ADOPTION_PLAN_REPORT_KIND:
        blockers.append("adoption plan report_kind must be model_role_catalog_adoption_plan")
    adoption_plan_status = str(adoption_plan_data.get("adoption_plan_status") or "")
    _status_check(
        label="adoption plan",
        status=adoption_plan_status,
        ready_statuses=ADOPTION_PLAN_READY_STATUSES,
        warning_status="adoption_plan_ready_with_warnings",
        incomplete_status="adoption_plan_incomplete",
        blockers=blockers,
        warnings=warnings,
        incomplete=incomplete,
    )
    for reason in _strings(adoption_plan_data.get("blocked_reasons")):
        blockers.append(f"adoption plan blocker: {reason}")
    warnings += [f"adoption plan warning: {item}" for item in _strings(adoption_plan_data.get("warnings"))]

    if source_registry_data.get("report_kind") != SOURCE_REGISTRY_REPORT_KIND:
        blockers.append("source registry report_kind must be model_role_registry")
    if not isinstance(source_registry_data.get("roles"), list):
        blockers.append("source registry roles must be a list")
    if proposed_registry_data.get("report_kind") != PROPOSED_REGISTRY_REPORT_KIND:
        blockers.append("proposed registry report_kind must be proposed_model_role_registry")
    if not isinstance(proposed_registry_data.get("roles"), list):
        blockers.append("proposed registry roles must be a list")

    blockers += _artifact_guardrail_blockers(proposal_data, "proposal")
    blockers += _artifact_guardrail_blockers(review_data, "review")
    blockers += _artifact_guardrail_blockers(adoption_plan_data, "adoption plan")

    source_roles = _source_roles(source_registry_data)
    proposed_roles = _proposed_roles(proposed_registry_data)
    source_ids = _role_ids(source_roles)
    proposed_ids = _role_ids(proposed_roles)
    source_id_set = set(source_ids)
    proposed_id_set = set(proposed_ids)
    actual_proposed_count = len(proposed_roles)
    declared_proposed_count = proposed_registry_data.get("role_count")

    if not source_roles:
        blockers.append("source registry contains no roles")
    if not proposed_roles:
        blockers.append("proposed registry contains no roles")

    dropped = sorted(source_id_set - proposed_id_set)
    for role_id in dropped:
        blockers.append(f"source role dropped in proposed registry: {role_id}")

    if isinstance(declared_proposed_count, int) and declared_proposed_count != actual_proposed_count:
        blockers.append(
            f"proposed registry role_count {declared_proposed_count} does not match roles {actual_proposed_count}"
        )
    count_candidates = _count_candidates(proposal_data, review_data, adoption_plan_data)
    for label, expected_count in count_candidates.items():
        if expected_count != actual_proposed_count:
            blockers.append(f"{label} {expected_count} does not match proposed registry roles {actual_proposed_count}")

    expected_new_ids = _expected_new_role_ids(proposal_data, review_data, adoption_plan_data)
    actual_new_ids = [role_id for role_id in proposed_ids if role_id not in source_id_set]
    missing_new = sorted(role_id for role_id in expected_new_ids if role_id not in proposed_id_set)
    for role_id in missing_new:
        blockers.append(f"expected new role missing from proposed registry: {role_id}")
    if not expected_new_ids and not actual_new_ids:
        incomplete.append("proposed registry lacks clear new-role evidence")

    safety_checks, safety_warnings, safety_blockers = _role_safety(proposed_roles)
    warnings += safety_warnings
    blockers += safety_blockers

    rollback_readiness, rollback_blockers = _rollback_readiness(adoption_plan_data)
    blockers += rollback_blockers
    human_approval_readiness, human_blockers = _human_approval_readiness(adoption_plan_data)
    blockers += human_blockers
    adoption_boundary_check, boundary_blockers = _adoption_boundary_check(adoption_plan_data)
    blockers += boundary_blockers

    source_validation_status = str(source_registry_data.get("validation_status") or "")
    if source_validation_status and source_validation_status not in {"model_roles_ready", "model_roles_ready_with_warnings"}:
        warnings.append(f"source registry validation_status is {source_validation_status}")

    proposal_check = {
        "path": str(proposal_path or ""),
        "loaded": bool(proposal_data),
        "report_kind": proposal_data.get("report_kind", ""),
        "proposal_status": proposal_status,
        "blocked_reason_count": len(proposal_data.get("blocked_reasons") or []),
        "warning_count": len(proposal_data.get("warnings") or []),
        "proposed_role_count": count_candidates.get("proposal diff_summary proposed_role_count"),
        "passed": proposal_status in PROPOSAL_READY_STATUSES and not _strings(proposal_data.get("blocked_reasons")),
    }
    review_check = {
        "path": str(review_path or ""),
        "loaded": bool(review_data),
        "report_kind": review_data.get("report_kind", ""),
        "review_status": review_status,
        "blocked_reason_count": len(review_data.get("blocked_reasons") or []),
        "warning_count": len(review_data.get("warnings") or []),
        "passed": review_status in REVIEW_READY_STATUSES and not _strings(review_data.get("blocked_reasons")),
    }
    adoption_plan_check = {
        "path": str(adoption_plan_path or ""),
        "loaded": bool(adoption_plan_data),
        "report_kind": adoption_plan_data.get("report_kind", ""),
        "adoption_plan_status": adoption_plan_status,
        "blocked_reason_count": len(adoption_plan_data.get("blocked_reasons") or []),
        "warning_count": len(adoption_plan_data.get("warnings") or []),
        "passed": adoption_plan_status in ADOPTION_PLAN_READY_STATUSES
        and not _strings(adoption_plan_data.get("blocked_reasons")),
    }
    registry_safety_check = {
        "path": str(source_registry_path or ""),
        "loaded": bool(source_registry_data),
        "report_kind": source_registry_data.get("report_kind", ""),
        "validation_status": source_validation_status,
        "source_role_count": len(source_roles),
        "source_role_ids": source_ids,
        "source_roles_preserved": not dropped,
        "passed": bool(source_roles) and not dropped,
    }
    proposed_registry_safety_check = {
        "path": str(proposed_registry_path or ""),
        "loaded": bool(proposed_registry_data),
        "report_kind": proposed_registry_data.get("report_kind", ""),
        "declared_role_count": declared_proposed_count,
        "proposed_role_count": actual_proposed_count,
        "proposed_role_ids": proposed_ids,
        "actual_new_role_ids": actual_new_ids,
        "expected_new_role_ids": expected_new_ids,
        "expected_new_roles_present": not missing_new,
        "count_candidates": count_candidates,
        **safety_checks,
        "passed": bool(proposed_roles) and not missing_new and not safety_blockers,
    }

    warnings = _unique(warnings)
    blockers = _unique(blockers)
    incomplete = _unique(incomplete)
    readiness_status = _status(blockers=blockers, incomplete=incomplete, warnings=warnings)

    return {
        "report_kind": REPORT_KIND,
        "readiness_id": "model-role-catalog-adoption-readiness",
        "guardrail_note": MODEL_ROLE_CATALOG_ADOPTION_READINESS_GUARDRAIL_NOTE,
        "source_proposal_path": str(proposal_path or ""),
        "source_review_path": str(review_path or ""),
        "source_adoption_plan_path": str(adoption_plan_path or ""),
        "source_registry_path": str(source_registry_path or ""),
        "proposed_registry_path": str(proposed_registry_path or ""),
        "readiness_status": readiness_status,
        "source_artifacts": {
            "proposal": str(proposal_path or ""),
            "review": str(review_path or ""),
            "adoption_plan": str(adoption_plan_path or ""),
            "source_registry": str(source_registry_path or ""),
            "proposed_registry": str(proposed_registry_path or ""),
        },
        "proposal_check": proposal_check,
        "review_check": review_check,
        "adoption_plan_check": adoption_plan_check,
        "registry_safety_check": registry_safety_check,
        "proposed_registry_safety_check": proposed_registry_safety_check,
        "rollback_readiness": rollback_readiness,
        "human_approval_readiness": human_approval_readiness,
        "adoption_boundary_check": adoption_boundary_check,
        "files_that_must_not_change": list(FILES_THAT_MUST_NOT_CHANGE),
        "warnings": warnings,
        "incomplete_reasons": incomplete,
        "blocked_reasons": blockers,
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
        "readiness_statuses": list(READINESS_STATUSES),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def _render_dict(lines: list[str], values: dict[str, Any]) -> None:
    if values:
        for key in sorted(values):
            lines.append(f"- **{_md(key)}:** {_md(values[key])}")
    else:
        lines.append("_None._")
    lines.append("")


def render_model_role_catalog_adoption_readiness_markdown(report: dict[str, Any]) -> str:
    """Render a MODEL.N7 readiness report as Markdown."""
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    source_artifacts = report.get("source_artifacts") if isinstance(report.get("source_artifacts"), dict) else {}
    proposal_check = report.get("proposal_check") if isinstance(report.get("proposal_check"), dict) else {}
    review_check = report.get("review_check") if isinstance(report.get("review_check"), dict) else {}
    adoption_plan_check = (
        report.get("adoption_plan_check") if isinstance(report.get("adoption_plan_check"), dict) else {}
    )
    registry_check = (
        report.get("registry_safety_check") if isinstance(report.get("registry_safety_check"), dict) else {}
    )
    proposed_check = (
        report.get("proposed_registry_safety_check")
        if isinstance(report.get("proposed_registry_safety_check"), dict)
        else {}
    )
    rollback = report.get("rollback_readiness") if isinstance(report.get("rollback_readiness"), dict) else {}
    human = report.get("human_approval_readiness") if isinstance(report.get("human_approval_readiness"), dict) else {}
    boundary = report.get("adoption_boundary_check") if isinstance(report.get("adoption_boundary_check"), dict) else {}

    lines: list[str] = [
        "# Model Role Catalog Adoption Readiness Check",
        "",
        f"> {report.get('guardrail_note', MODEL_ROLE_CATALOG_ADOPTION_READINESS_GUARDRAIL_NOTE)}",
        "",
        "_Report only: MODEL.N7 checks readiness for a later human-approved adoption phase and does not adopt the catalog._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Readiness status:** `{_md(report.get('readiness_status', ''))}`",
        f"- **Warnings:** {len(report.get('warnings') or [])}",
        f"- **Blocked reasons:** {len(report.get('blocked_reasons') or [])}",
        "",
        "## Source Artifacts",
        "",
    ]
    _render_dict(lines, source_artifacts)
    lines += ["## Proposal Readiness", ""]
    _render_dict(lines, proposal_check)
    lines += ["## Review Readiness", ""]
    _render_dict(lines, review_check)
    lines += ["## Adoption Plan Readiness", ""]
    _render_dict(lines, adoption_plan_check)
    lines += ["## Source Registry Safety", ""]
    _render_dict(lines, registry_check)
    lines += ["## Proposed Registry Safety", ""]
    _render_dict(lines, proposed_check)
    lines += ["## Rollback Readiness", ""]
    _render_dict(lines, rollback)
    lines += ["## Human Approval Boundary", ""]
    _render_dict(lines, human)
    _render_dict(lines, boundary)
    lines += ["## Files That Must Not Change", ""]
    _render_list(lines, list(report.get("files_that_must_not_change") or []), code=True)
    lines += ["## Warnings", ""]
    _render_list(lines, list(report.get("warnings") or []))
    lines += ["## Blocked Reasons", ""]
    _render_list(lines, list(report.get("blocked_reasons") or []))
    lines += ["## Final Verdict", ""]
    lines.append(f"- **Status:** `{_md(report.get('readiness_status', ''))}`")
    if report.get("blocked_reasons"):
        lines.append("- **Verdict:** Blocked until the listed reasons are resolved.")
    elif report.get("incomplete_reasons"):
        lines.append("- **Verdict:** Incomplete until missing evidence is supplied.")
    elif report.get("warnings"):
        lines.append("- **Verdict:** Safe for human review with warnings carried forward.")
    else:
        lines.append("- **Verdict:** Safe for human review with no warnings.")
    lines.append("")
    lines += ["## Boundaries / Guardrails", ""]
    for boundary_item in report.get("boundaries") or []:
        lines.append(f"- {_md(boundary_item)}")
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: {str(bool(guardrails[key])).lower()}")
    lines += [
        "",
        "## Recommended Next Phase",
        "",
        f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
        f"- **Title:** {_md(next_phase.get('title', ''))}",
        f"- **Reason:** {_md(next_phase.get('reason', ''))}",
        "",
    ]
    return "\n".join(lines)


def write_model_role_catalog_adoption_readiness(
    *,
    proposal_path: str | Path,
    review_path: str | Path,
    adoption_plan_path: str | Path,
    source_registry_path: str | Path,
    proposed_registry_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    proposal_data: dict[str, Any] | None = None,
    review_data: dict[str, Any] | None = None,
    adoption_plan_data: dict[str, Any] | None = None,
    source_registry_data: dict[str, Any] | None = None,
    proposed_registry_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build and write MODEL.N7 JSON + Markdown readiness artifacts."""
    blockers = list(input_blockers or [])
    if proposal_data is None and not blockers:
        proposal_data, read_blockers = read_json_input(proposal_path, "proposal", required=True)
        blockers += read_blockers
    if review_data is None and not blockers:
        review_data, read_blockers = read_json_input(review_path, "review", required=True)
        blockers += read_blockers
    if adoption_plan_data is None and not blockers:
        adoption_plan_data, read_blockers = read_json_input(adoption_plan_path, "adoption plan", required=True)
        blockers += read_blockers
    if source_registry_data is None and not blockers:
        source_registry_data, read_blockers = read_json_input(source_registry_path, "source registry", required=True)
        blockers += read_blockers
    if proposed_registry_data is None and not blockers:
        proposed_registry_data, read_blockers = read_json_input(proposed_registry_path, "proposed registry", required=True)
        blockers += read_blockers
    report = build_model_role_catalog_adoption_readiness(
        proposal_path=proposal_path,
        proposal_data=proposal_data,
        review_path=review_path,
        review_data=review_data,
        adoption_plan_path=adoption_plan_path,
        adoption_plan_data=adoption_plan_data,
        source_registry_path=source_registry_path,
        source_registry_data=source_registry_data,
        proposed_registry_path=proposed_registry_path,
        proposed_registry_data=proposed_registry_data,
        input_blockers=blockers,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_model_role_catalog_adoption_readiness_markdown(report), encoding="utf-8")
    ok = report.get("readiness_status") in {
        "adoption_readiness_ready",
        "adoption_readiness_ready_with_warnings",
    }
    return {"ok": ok, "json_path": str(json_path), "md_path": str(md_path), "report": report}
