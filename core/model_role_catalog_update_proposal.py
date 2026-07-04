"""MODEL.N4 - Model Role Catalog Update Proposal (report-only).

Reads a MODEL.N3 gap plan and optionally the current MODEL.N1 registry, then
writes a human-reviewable proposed catalog update. This module never modifies
the real MODEL.N1 registry artifact, changes runtime model selection, routes
tasks, calls models, launches workers, binds executable model IDs, applies
patches, runs validation or benchmarks, invokes MCP tools, contacts networks,
writes databases, or mutates source artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "model_role_catalog_update_proposal"
JSON_NAME = "model_role_catalog_update_proposal.json"
MD_NAME = "model_role_catalog_update_proposal.md"
PROPOSED_REGISTRY_NAME = "proposed_model_role_registry.json"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "model_role_registry" / "model_role_catalog_update_proposal"

GAP_PLAN_REPORT_KIND = "model_role_gap_plan"
MODEL_REGISTRY_REPORT_KIND = "model_role_registry"
PROPOSED_REGISTRY_REPORT_KIND = "proposed_model_role_registry"

PROPOSAL_STATUSES: tuple[str, ...] = (
    "catalog_update_proposal_ready",
    "catalog_update_proposal_ready_with_warnings",
    "catalog_update_proposal_incomplete",
    "catalog_update_proposal_blocked",
)

GAP_PLAN_STATUSES: tuple[str, ...] = (
    "gap_plan_ready",
    "gap_plan_ready_with_warnings",
    "gap_plan_incomplete",
    "gap_plan_blocked",
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
    "source_artifacts_mutated",
    "model_n1_registry_artifact_mutated",
    "automatic_registry_update_performed",
)

FORBIDDEN_CHANGES: tuple[str, ...] = (
    "do not enable executable_binding_allowed",
    "do not set advisory_only false",
    "do not add route_tasks",
    "do not add launch_worker",
    "do not add auto_run",
    "do not add auto_apply",
    "do not add auto_merge",
    "do not allow model IDs to become authority",
    "do not mutate MODEL.N1 registry artifact",
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "proposal-only",
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
    "no automatic registry update",
    "no mutation of MODEL.N1 registry artifact",
    "writes proposal artifacts only",
)

MODEL_ROLE_CATALOG_UPDATE_PROPOSAL_GUARDRAIL_NOTE = (
    "Model Role Catalog Update Proposal is report-only: it reads MODEL.N3 gap "
    "plan evidence and drafts a separate proposed MODEL.N1 catalog update for "
    "human review. It does not modify the existing MODEL.N1 registry artifact, "
    "change runtime model selection, route tasks, call models, launch workers, "
    "bind executable model IDs, apply patches, run validation or benchmarks, "
    "invoke MCP tools, contact networks, write databases, or perform automatic "
    "assignment."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "MODEL.N5",
    "title": "Model Role Catalog Proposal Review",
    "reason": (
        "Review the proposed catalog update against MODEL.N1, MODEL.N2, and "
        "MODEL.N3 safety expectations before any human-approved adoption phase."
    ),
}

REQUIRED_REVIEW_ROLE_IDS: tuple[str, ...] = (
    "ui_reviewer",
    "test_designer",
    "documentation_reviewer",
)

DANGEROUS_BOUNDARY_TASKS: tuple[str, ...] = (
    "patch_apply",
    "approval_authority",
    "auto_apply",
    "auto_merge",
    "route_change",
    "worker_launch",
)

ROLE_TEMPLATES: dict[str, dict[str, Any]] = {
    "ui_reviewer": {
        "display_name": "UI Reviewer",
        "role_kind": "reviewer",
        "description": "Reviews user-facing UI behavior, copy, and visual workflow consistency without mutating templates.",
        "strengths": ["UI behavior review", "user-facing copy review", "visual workflow consistency"],
        "weaknesses": ["does not mutate templates", "does not approve patch application"],
        "best_for": ["UI behavior review", "user-facing copy", "visual workflow consistency"],
        "not_for": ["direct template mutation", "apply approval", "runtime behavior changes"],
        "risk_level": "medium",
        "cost_tier": "medium",
        "latency_tier": "medium",
        "context_tier": "large",
        "reliability_tier": "normal",
        "evidence_expectation": "cite visible UI behavior, copy, and workflow consistency evidence",
        "allowed_task_types": ["ui_review", "copy_review", "workflow_consistency_review"],
        "forbidden_task_types": ["patch_apply", "approval_authority", "hidden_ui_mutation", "route_change"],
        "fallback_roles": ["code_reviewer", "planner"],
        "human_review_required": True,
    },
    "test_designer": {
        "display_name": "Test Designer",
        "role_kind": "evidence_checker",
        "description": "Designs test plans, edge cases, and regression coverage without running validation automatically.",
        "strengths": ["test plan design", "edge case discovery", "regression coverage planning"],
        "weaknesses": ["does not run tests automatically", "does not approve final patches"],
        "best_for": ["test plan design", "edge case discovery", "regression coverage planning"],
        "not_for": ["running tests automatically", "changing benchmark gates", "approving final patch"],
        "risk_level": "medium",
        "cost_tier": "medium",
        "latency_tier": "medium",
        "context_tier": "large",
        "reliability_tier": "strong",
        "evidence_expectation": "name test intent, edge cases, regression risks, and required human validation",
        "allowed_task_types": ["test_plan_design", "edge_case_review", "regression_coverage_planning"],
        "forbidden_task_types": ["run_validation", "run_benchmark", "patch_apply", "approval_authority"],
        "fallback_roles": ["evidence_checker", "code_reviewer"],
        "human_review_required": True,
    },
    "documentation_reviewer": {
        "display_name": "Documentation Reviewer",
        "role_kind": "reviewer",
        "description": "Reviews roadmap consistency, registry narrative consistency, and artifact explanation clarity.",
        "strengths": ["roadmap consistency", "registry narrative consistency", "artifact explanation clarity"],
        "weaknesses": ["does not mutate registries", "does not approve phases"],
        "best_for": ["roadmap consistency", "registry narrative consistency", "artifact explanation clarity"],
        "not_for": ["registry mutation authority", "phase approval authority", "hidden roadmap edits"],
        "risk_level": "low",
        "cost_tier": "low",
        "latency_tier": "fast",
        "context_tier": "medium",
        "reliability_tier": "strong",
        "evidence_expectation": "cite roadmap, registry, and artifact explanation consistency evidence",
        "allowed_task_types": ["documentation_review", "roadmap_consistency_review", "artifact_explanation_review"],
        "forbidden_task_types": ["auto_registry_update", "approval_authority", "route_change"],
        "fallback_roles": ["code_reviewer", "planner"],
        "human_review_required": True,
    },
}


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


def _safe_identifier(value: Any) -> bool:
    text = str(value or "").strip()
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if not text or text in {".", ".."} or ".." in text:
        return False
    if "/" in text or "\\" in text or text.startswith("."):
        return False
    return all(ch in allowed for ch in text)


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _role_id(value: dict[str, Any]) -> str:
    return str(value.get("role_id") or value.get("suggested_role_id") or value.get("affected_role") or "").strip()


def _title_from_id(role_id: str) -> str:
    return " ".join(piece.capitalize() for piece in role_id.split("_") if piece) or "Unnamed Role"


def _role_template(role_id: str) -> dict[str, Any]:
    template = dict(ROLE_TEMPLATES.get(role_id) or {})
    if template:
        return template
    role_kind = "reviewer"
    return {
        "display_name": _title_from_id(role_id),
        "role_kind": role_kind,
        "description": f"Advisory tower card proposed for {role_id}.",
        "strengths": ["manual advisory review"],
        "weaknesses": ["does not execute", "does not approve changes"],
        "best_for": ["manual advisory review"],
        "not_for": ["execution authority", "automatic mutation", "final approval"],
        "risk_level": "medium",
        "cost_tier": "medium",
        "latency_tier": "medium",
        "context_tier": "medium",
        "reliability_tier": "normal",
        "evidence_expectation": "state assumptions, evidence, and required human review",
        "allowed_task_types": ["manual_advisory_review"],
        "forbidden_task_types": list(DANGEROUS_BOUNDARY_TASKS),
        "fallback_roles": ["code_reviewer", "planner"],
        "human_review_required": True,
    }


def _card_from_gap_item(item: dict[str, Any]) -> dict[str, Any]:
    role_id = str(item.get("suggested_role_id") or item.get("affected_role") or "").strip()
    template = _role_template(role_id)
    role_kind = str(template.get("role_kind") or item.get("suggested_role_kind") or "reviewer")
    if role_id not in ROLE_TEMPLATES and item.get("suggested_role_kind"):
        role_kind = str(item.get("suggested_role_kind") or role_kind)
    best_for = list(template.get("best_for") or _strings(item.get("suggested_best_for")) or ["manual advisory review"])
    not_for = list(template.get("not_for") or _strings(item.get("suggested_not_for")) or ["execution authority"])
    forbidden = list(template.get("forbidden_task_types") or []) or _strings(item.get("suggested_forbidden_task_types"))
    fallbacks = _strings(item.get("suggested_fallback_roles")) or list(template.get("fallback_roles") or [])
    human_review = bool(template.get("human_review_required", item.get("human_review_required", True)))
    if role_kind in {"implementer", "reviewer", "risk_auditor"} or role_id in REQUIRED_REVIEW_ROLE_IDS:
        human_review = True
    return {
        "role_id": role_id,
        "display_name": str(template.get("display_name") or item.get("suggested_display_name") or _title_from_id(role_id)),
        "role_kind": role_kind,
        "description": str(template.get("description") or f"Advisory tower card proposed for {role_id}."),
        "strengths": list(template.get("strengths") or best_for),
        "weaknesses": list(template.get("weaknesses") or ["does not execute", "does not approve changes"]),
        "best_for": best_for,
        "not_for": not_for,
        "risk_level": str(template.get("risk_level") or "medium"),
        "cost_tier": str(template.get("cost_tier") or "medium"),
        "latency_tier": str(template.get("latency_tier") or "medium"),
        "context_tier": str(template.get("context_tier") or "medium"),
        "reliability_tier": str(template.get("reliability_tier") or "normal"),
        "evidence_expectation": str(template.get("evidence_expectation") or "state evidence and required human review"),
        "allowed_task_types": list(template.get("allowed_task_types") or ["manual_advisory_review"]),
        "forbidden_task_types": forbidden,
        "advisory_only": True,
        "executable_binding_allowed": False,
        "model_ids": _strings(item.get("model_ids")),
        "model_id_policy": "descriptive_metadata_only",
        "fallback_roles": fallbacks,
        "human_review_required": human_review,
        "notes": [
            "Proposed by MODEL.N4 for human review only.",
            "Advisory card only; no executable model binding, routing, worker launch, or patch authority.",
        ],
    }


def _gap_item_blockers(item: dict[str, Any]) -> list[str]:
    role_id = str(item.get("suggested_role_id") or item.get("affected_role") or "unknown_role")
    blockers: list[str] = []
    if item.get("executable_binding_allowed") is True:
        blockers.append(f"gap item {role_id} requests executable_binding_allowed true")
    if item.get("advisory_only") is False:
        blockers.append(f"gap item {role_id} requests advisory_only false")
    for flag in FORBIDDEN_AUTHORITY_FLAGS:
        if item.get(flag) is True:
            blockers.append(f"gap item {role_id} includes forbidden authority flag: {flag}")
    return blockers


def _current_roles(model_registry_data: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[str]]:
    blockers: list[str] = []
    if model_registry_data is None:
        return [], []
    if model_registry_data.get("report_kind") != MODEL_REGISTRY_REPORT_KIND:
        blockers.append("model registry report_kind must be model_role_registry")
    raw = model_registry_data.get("roles")
    if not isinstance(raw, list):
        blockers.append("model registry roles must be a list")
        return [], blockers
    return [dict(role) for role in raw if isinstance(role, dict)], blockers


def _gap_rows(gap_plan_data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in (
        "missing_role_plans",
        "weak_role_plans",
        "risky_role_plans",
        "fallback_improvement_plans",
        "metadata_improvement_plans",
    ):
        for item in _list_of_dicts(gap_plan_data.get(group)):
            row = dict(item)
            row["source_gap_group"] = group
            rows.append(row)
    return rows


def _missing_rows(gap_plan_data: dict[str, Any]) -> list[dict[str, Any]]:
    return _list_of_dicts(gap_plan_data.get("missing_role_plans"))


def _role_update(row: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    role_id = str(existing.get("role_id") or row.get("affected_role") or row.get("suggested_role_id") or "")
    updates: dict[str, Any] = {
        "role_id": role_id,
        "category": row.get("category", ""),
        "reason": row.get("reason", ""),
        "proposed_changes": {},
        "advisory_only": True,
        "executable_binding_allowed": False,
    }
    category = str(row.get("category") or "")
    if category == "weak_fallback":
        updates["proposed_changes"]["fallback_roles"] = _strings(row.get("suggested_fallback_roles"))
    elif category.startswith("unknown_"):
        field = category.replace("unknown_", "")
        updates["proposed_changes"][field] = "manual_review_required"
    elif category == "weak_forbidden_task_types":
        merged = _unique(_strings(existing.get("forbidden_task_types")) + _strings(row.get("suggested_forbidden_task_types")))
        updates["proposed_changes"]["forbidden_task_types"] = merged
    elif category == "weak_evidence_expectation":
        updates["proposed_changes"]["evidence_expectation"] = "state evidence, assumptions, and required human review"
    else:
        updates["proposed_changes"]["review_note"] = "manual review required"
    return updates


def _known_role_ids(current_roles: list[dict[str, Any]], proposed_new_roles: list[dict[str, Any]]) -> set[str]:
    ids = {str(role.get("role_id") or "") for role in current_roles if str(role.get("role_id") or "")}
    ids.update(str(role.get("role_id") or "") for role in proposed_new_roles if str(role.get("role_id") or ""))
    return ids


def _role_safety_blockers(role: dict[str, Any], known_ids: set[str]) -> list[str]:
    role_id = str(role.get("role_id") or "unknown_role")
    blockers: list[str] = []
    if not _safe_identifier(role_id):
        blockers.append(f"role {role_id} has an unsafe or empty role_id")
    if role.get("advisory_only") is not True:
        blockers.append(f"role {role_id} advisory_only must be true")
    if role.get("executable_binding_allowed") is True:
        blockers.append(f"role {role_id} executable_binding_allowed must be false")
    for flag in FORBIDDEN_AUTHORITY_FLAGS:
        if role.get(flag) is True:
            blockers.append(f"role {role_id} includes forbidden authority flag: {flag}")
    role_kind = str(role.get("role_kind") or "")
    if role_kind in {"implementer", "reviewer", "risk_auditor"} and role.get("human_review_required") is not True:
        blockers.append(f"role {role_id} human_review_required must be true for {role_kind} roles")
    if role_id in REQUIRED_REVIEW_ROLE_IDS and role.get("human_review_required") is not True:
        blockers.append(f"role {role_id} human_review_required must be true")
    forbidden = set(_strings(role.get("forbidden_task_types")))
    if not forbidden:
        blockers.append(f"role {role_id} forbidden_task_types must be non-empty")
    if role_id in REQUIRED_REVIEW_ROLE_IDS and not forbidden.intersection(DANGEROUS_BOUNDARY_TASKS):
        blockers.append(f"role {role_id} forbidden_task_types must block dangerous authority")
    for fallback in _strings(role.get("fallback_roles")):
        if fallback not in known_ids:
            blockers.append(f"role {role_id} references unknown fallback role: {fallback}")
    return blockers


def _duplicate_role_blockers(current_roles: list[dict[str, Any]], proposed_new_roles: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    current_ids = [str(role.get("role_id") or "") for role in current_roles if str(role.get("role_id") or "")]
    proposed_ids = [str(role.get("role_id") or "") for role in proposed_new_roles if str(role.get("role_id") or "")]
    for role_id in sorted({role_id for role_id in proposed_ids if proposed_ids.count(role_id) > 1}):
        blockers.append(f"duplicate proposed role_id: {role_id}")
    for role_id in sorted({role_id for role_id in proposed_ids if role_id in current_ids}):
        blockers.append(f"proposed role_id already exists in current registry: {role_id}")
    for role_id in sorted({role_id for role_id in current_ids if current_ids.count(role_id) > 1}):
        blockers.append(f"duplicate current registry role_id: {role_id}")
    return blockers


def _proposal_status(
    *,
    blockers: list[str],
    warnings: list[str],
    has_changes: bool,
    rejected_gap_items: list[dict[str, Any]],
    gap_status: str,
) -> str:
    if blockers:
        return "catalog_update_proposal_blocked"
    if gap_status == "gap_plan_incomplete" and not has_changes:
        return "catalog_update_proposal_incomplete"
    if warnings or rejected_gap_items:
        return "catalog_update_proposal_ready_with_warnings"
    return "catalog_update_proposal_ready"


def _proposed_registry(
    *,
    proposal_id: str,
    source_registry_path: str,
    current_roles: list[dict[str, Any]],
    proposed_new_roles: list[dict[str, Any]],
) -> dict[str, Any]:
    roles = [dict(role) for role in current_roles] + [dict(role) for role in proposed_new_roles]
    return {
        "report_kind": PROPOSED_REGISTRY_REPORT_KIND,
        "proposal_id": proposal_id,
        "source_model_registry_path": source_registry_path,
        "role_count": len(roles),
        "roles": roles,
        "guardrail_note": (
            "Proposed registry only. This artifact is not the active MODEL.N1 "
            "registry and grants no routing, execution, worker launch, patch, "
            "or model binding authority."
        ),
        "boundaries": list(BOUNDARIES),
    }


def build_model_role_catalog_update_proposal(
    *,
    gap_plan_path: str | Path | None,
    gap_plan_data: dict[str, Any] | None = None,
    model_registry_path: str | Path | None = None,
    model_registry_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic MODEL.N4 catalog update proposal."""
    blockers = list(input_blockers or [])
    blockers += _input_path_blockers(gap_plan_path, "gap plan", required=True)
    blockers += _input_path_blockers(model_registry_path, "model registry", required=False)
    warnings: list[str] = []

    if gap_plan_data is None:
        gap_plan_data = {}
        blockers.append("gap plan is missing or malformed")
    if not isinstance(gap_plan_data, dict):
        gap_plan_data = {}
        blockers.append("gap plan must contain a JSON object")
    if model_registry_data is not None and not isinstance(model_registry_data, dict):
        model_registry_data = {}
        blockers.append("model registry must contain a JSON object")

    if gap_plan_data.get("report_kind") != GAP_PLAN_REPORT_KIND:
        blockers.append("gap plan report_kind must be model_role_gap_plan")
    gap_status = str(gap_plan_data.get("gap_plan_status") or "")
    if gap_status not in GAP_PLAN_STATUSES:
        blockers.append("gap_plan_status must be a MODEL.N3 gap plan status")
    if gap_status == "gap_plan_blocked":
        blockers.append("gap plan is blocked; resolve MODEL.N3 blockers before proposing catalog updates")
    for reason in _strings(gap_plan_data.get("blocked_reasons")):
        if gap_status == "gap_plan_blocked":
            blockers.append(f"gap plan blocker: {reason}")

    current_roles, registry_blockers = _current_roles(model_registry_data)
    blockers += registry_blockers
    current_by_id = {str(role.get("role_id") or ""): dict(role) for role in current_roles if str(role.get("role_id") or "")}
    current_ids = set(current_by_id)

    proposed_new_roles: list[dict[str, Any]] = []
    proposed_role_updates: list[dict[str, Any]] = []
    rejected_gap_items: list[dict[str, Any]] = []

    for row in _missing_rows(gap_plan_data):
        blockers += _gap_item_blockers(row)
        role_id = str(row.get("suggested_role_id") or row.get("affected_role") or "").strip()
        if not role_id:
            rejected_gap_items.append({"gap_id": row.get("gap_id", ""), "reason": "missing suggested_role_id"})
            continue
        if role_id in current_ids:
            rejected_gap_items.append(
                {
                    "gap_id": row.get("gap_id", ""),
                    "affected_role": role_id,
                    "reason": "role already exists in current MODEL.N1 registry",
                }
            )
            continue
        proposed_new_roles.append(_card_from_gap_item(row))

    for row in _gap_rows(gap_plan_data):
        group = str(row.get("source_gap_group") or "")
        if group == "missing_role_plans":
            continue
        blockers += _gap_item_blockers(row)
        if str(row.get("severity") or "") == "blocker" or group == "risky_role_plans":
            rejected_gap_items.append(
                {
                    "gap_id": row.get("gap_id", ""),
                    "affected_role": row.get("affected_role", ""),
                    "reason": "risky or blocker gap item requires separate human review",
                }
            )
            continue
        role_id = str(row.get("suggested_role_id") or row.get("affected_role") or "").strip()
        if role_id in current_by_id:
            proposed_role_updates.append(_role_update(row, current_by_id[role_id]))
        else:
            rejected_gap_items.append(
                {
                    "gap_id": row.get("gap_id", ""),
                    "affected_role": role_id,
                    "reason": "cannot update a role that is not present in the current registry",
                }
            )

    known_ids = _known_role_ids(current_roles, proposed_new_roles)
    blockers += _duplicate_role_blockers(current_roles, proposed_new_roles)
    for role in proposed_new_roles:
        blockers += _role_safety_blockers(role, known_ids)

    warnings += _strings(gap_plan_data.get("warnings"))
    if rejected_gap_items:
        warnings.append("some MODEL.N3 gap items were rejected from automatic proposal and require manual review")
    if model_registry_data is None:
        warnings.append("model registry was not supplied; proposed registry starts from an empty current catalog")

    blockers = _unique(blockers)
    warnings = _unique(warnings)
    has_changes = bool(proposed_new_roles or proposed_role_updates)
    status = _proposal_status(
        blockers=blockers,
        warnings=warnings,
        has_changes=has_changes,
        rejected_gap_items=rejected_gap_items,
        gap_status=gap_status,
    )
    unchanged_roles = [str(role.get("role_id") or "") for role in current_roles if str(role.get("role_id") or "")]
    current_role_count = len(current_roles)
    proposed_role_count = current_role_count + len(proposed_new_roles)
    safety_checks = {
        "advisory_only_preserved": not any(role.get("advisory_only") is not True for role in proposed_new_roles),
        "executable_binding_disallowed": not any(role.get("executable_binding_allowed") is True for role in proposed_new_roles),
        "forbidden_authority_flags_absent": not any(
            role.get(flag) is True for role in proposed_new_roles for flag in FORBIDDEN_AUTHORITY_FLAGS
        ),
        "fallback_roles_known": not any(
            fallback not in known_ids for role in proposed_new_roles for fallback in _strings(role.get("fallback_roles"))
        ),
        "role_ids_unique": not _duplicate_role_blockers(current_roles, proposed_new_roles),
        "passed": not blockers,
    }
    diff_summary = {
        "current_role_count": current_role_count,
        "proposed_role_count": proposed_role_count,
        "new_role_count": len(proposed_new_roles),
        "updated_role_count": len(proposed_role_updates),
        "unchanged_role_count": len(unchanged_roles),
        "rejected_gap_item_count": len(rejected_gap_items),
    }
    checklist = [
        "confirm proposed roles are advisory labels only",
        "confirm executable_binding_allowed remains false",
        "confirm advisory_only remains true",
        "confirm model_ids are metadata only",
        "confirm no routing/launch/apply authority is introduced",
        "confirm fallback roles reference known roles",
        "confirm forbidden_task_types clearly block dangerous authority",
        "confirm humans still approve model/worker use separately",
    ]
    proposal_id = "model-role-catalog-update-proposal"
    source_registry_path = str(model_registry_path or gap_plan_data.get("source_model_registry_path") or "")
    return {
        "report_kind": REPORT_KIND,
        "proposal_id": proposal_id,
        "guardrail_note": MODEL_ROLE_CATALOG_UPDATE_PROPOSAL_GUARDRAIL_NOTE,
        "source_gap_plan_path": str(gap_plan_path or ""),
        "source_model_registry_path": source_registry_path,
        "source_gap_plan": {
            "path": str(gap_plan_path or ""),
            "report_kind": gap_plan_data.get("report_kind", ""),
            "gap_plan_status": gap_status,
            "loaded": bool(gap_plan_data),
        },
        "source_registry": {
            "path": source_registry_path,
            "report_kind": (model_registry_data or {}).get("report_kind", "") if isinstance(model_registry_data, dict) else "",
            "validation_status": (model_registry_data or {}).get("validation_status", "") if isinstance(model_registry_data, dict) else "",
            "loaded": bool(model_registry_data),
        },
        "proposal_status": status,
        "current_role_count": current_role_count,
        "proposed_role_count": proposed_role_count,
        "proposed_new_roles": proposed_new_roles,
        "proposed_role_updates": proposed_role_updates,
        "unchanged_roles": unchanged_roles,
        "rejected_gap_items": rejected_gap_items,
        "diff_summary": diff_summary,
        "safety_checks": safety_checks,
        "manual_review_checklist": checklist,
        "forbidden_changes": list(FORBIDDEN_CHANGES),
        "warnings": warnings,
        "blocked_reasons": blockers,
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
        "proposal_statuses": list(PROPOSAL_STATUSES),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "proposed_registry": _proposed_registry(
            proposal_id=proposal_id,
            source_registry_path=source_registry_path,
            current_roles=current_roles,
            proposed_new_roles=proposed_new_roles,
        ),
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def _render_role_table(lines: list[str], rows: list[dict[str, Any]]) -> None:
    if not rows:
        lines.append("_None._")
        lines.append("")
        return
    lines += ["| Role | Kind | Human review | Fallbacks | Forbidden task types |", "| --- | --- | --- | --- | --- |"]
    for row in rows:
        lines.append(
            "| {role} | {kind} | {review} | {fallbacks} | {forbidden} |".format(
                role=_md(row.get("role_id", "")),
                kind=_md(row.get("role_kind", "")),
                review=str(bool(row.get("human_review_required"))).lower(),
                fallbacks=_md(", ".join(row.get("fallback_roles") or [])),
                forbidden=_md(", ".join(row.get("forbidden_task_types") or [])),
            )
        )
    lines.append("")


def render_model_role_catalog_update_proposal_markdown(report: dict[str, Any]) -> str:
    """Render a MODEL.N4 catalog update proposal as Markdown."""
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    gap = report.get("source_gap_plan") if isinstance(report.get("source_gap_plan"), dict) else {}
    registry = report.get("source_registry") if isinstance(report.get("source_registry"), dict) else {}
    diff = report.get("diff_summary") if isinstance(report.get("diff_summary"), dict) else {}
    safety = report.get("safety_checks") if isinstance(report.get("safety_checks"), dict) else {}
    lines: list[str] = [
        "# Model Role Catalog Update Proposal",
        "",
        f"> {report.get('guardrail_note', MODEL_ROLE_CATALOG_UPDATE_PROPOSAL_GUARDRAIL_NOTE)}",
        "",
        "_Report only: MODEL.N4 writes a proposed catalog update for human review and does not mutate MODEL.N1._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Proposal status:** `{_md(report.get('proposal_status', ''))}`",
        f"- **Current role count:** {report.get('current_role_count', 0)}",
        f"- **Proposed role count:** {report.get('proposed_role_count', 0)}",
        f"- **New roles:** {len(report.get('proposed_new_roles') or [])}",
        f"- **Role updates:** {len(report.get('proposed_role_updates') or [])}",
        f"- **Rejected gap items:** {len(report.get('rejected_gap_items') or [])}",
        "",
        "## Source Gap Plan",
        "",
        f"- **Path:** `{_md(gap.get('path', report.get('source_gap_plan_path', '')))}`",
        f"- **Kind:** `{_md(gap.get('report_kind', ''))}`",
        f"- **Status:** `{_md(gap.get('gap_plan_status', ''))}`",
        "",
        "## Source Registry",
        "",
        f"- **Path:** `{_md(registry.get('path', report.get('source_model_registry_path', '')))}`",
        f"- **Kind:** `{_md(registry.get('report_kind', ''))}`",
        f"- **Status:** `{_md(registry.get('validation_status', ''))}`",
        "",
        "## Proposed New Roles",
        "",
    ]
    _render_role_table(lines, list(report.get("proposed_new_roles") or []))
    lines += ["## Proposed Role Updates", ""]
    updates = report.get("proposed_role_updates") if isinstance(report.get("proposed_role_updates"), list) else []
    if updates:
        lines += ["| Role | Category | Proposed changes | Reason |", "| --- | --- | --- | --- |"]
        for row in updates:
            lines.append(
                "| {role} | {category} | {changes} | {reason} |".format(
                    role=_md(row.get("role_id", "")),
                    category=_md(row.get("category", "")),
                    changes=_md(row.get("proposed_changes", {})),
                    reason=_md(row.get("reason", "")),
                )
            )
        lines.append("")
    else:
        lines.append("_None._")
        lines.append("")
    lines += ["## Diff Summary", ""]
    for key in sorted(diff):
        lines.append(f"- **{_md(key)}:** {_md(diff[key])}")
    lines.append("")
    lines += ["## Rejected Gap Items", ""]
    rejected = report.get("rejected_gap_items") if isinstance(report.get("rejected_gap_items"), list) else []
    if rejected:
        for row in rejected:
            lines.append(f"- `{_md(row.get('gap_id', ''))}`: {_md(row.get('reason', ''))}")
    else:
        lines.append("_None._")
    lines.append("")
    lines += ["## Safety Checks", ""]
    for key in sorted(safety):
        lines.append(f"- `{_md(key)}`: {str(bool(safety[key])).lower()}")
    lines.append("")
    lines += ["## Manual Review Checklist", ""]
    _render_list(lines, list(report.get("manual_review_checklist") or []))
    lines += ["## Forbidden Changes", ""]
    _render_list(lines, list(report.get("forbidden_changes") or []))
    lines += ["## Warnings", ""]
    _render_list(lines, list(report.get("warnings") or []))
    lines += ["## Blocked Reasons", ""]
    _render_list(lines, list(report.get("blocked_reasons") or []))
    lines += ["## Boundaries / Guardrails", ""]
    for boundary in report.get("boundaries") or []:
        lines.append(f"- {_md(boundary)}")
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


def write_model_role_catalog_update_proposal(
    *,
    gap_plan_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    model_registry_path: str | Path | None = None,
    gap_plan_data: dict[str, Any] | None = None,
    model_registry_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build and write MODEL.N4 proposal JSON, Markdown, and proposed registry."""
    blockers = list(input_blockers or [])
    if gap_plan_data is None and not blockers:
        gap_plan_data, read_blockers = read_json_input(gap_plan_path, "gap plan", required=True)
        blockers += read_blockers
    if model_registry_path is not None and model_registry_data is None and not blockers:
        model_registry_data, read_blockers = read_json_input(model_registry_path, "model registry")
        blockers += read_blockers
    report = build_model_role_catalog_update_proposal(
        gap_plan_path=gap_plan_path,
        gap_plan_data=gap_plan_data,
        model_registry_path=model_registry_path,
        model_registry_data=model_registry_data,
        input_blockers=blockers,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    proposed_path = out_dir / PROPOSED_REGISTRY_NAME
    json_path.write_text(
        json.dumps({key: value for key, value in report.items() if key != "proposed_registry"}, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    md_path.write_text(render_model_role_catalog_update_proposal_markdown(report), encoding="utf-8")
    proposed_path.write_text(json.dumps(report["proposed_registry"], indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return {
        "ok": report.get("proposal_status") != "catalog_update_proposal_blocked",
        "json_path": str(json_path),
        "md_path": str(md_path),
        "proposed_registry_path": str(proposed_path),
        "report": report,
    }
