"""MODEL.N5 - Model Role Catalog Proposal Review (report-only).

Reviews the MODEL.N4 proposed model role catalog update before any
human-approved adoption phase. This module reads deterministic proposal and
registry artifacts and writes JSON/Markdown review artifacts only; it does not
replace MODEL.N1, mutate proposed registries, route tasks, call models, launch
workers, bind executable model IDs, run validation or benchmarks, apply patches,
invoke MCP tools, contact networks, write databases, or change runtime behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "model_role_catalog_proposal_review"
JSON_NAME = "model_role_catalog_proposal_review.json"
MD_NAME = "model_role_catalog_proposal_review.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "model_role_registry" / "model_role_catalog_proposal_review"

PROPOSAL_REPORT_KIND = "model_role_catalog_update_proposal"
PROPOSED_REGISTRY_REPORT_KIND = "proposed_model_role_registry"
SOURCE_REGISTRY_REPORT_KIND = "model_role_registry"

REVIEW_STATUSES: tuple[str, ...] = (
    "catalog_proposal_review_ready",
    "catalog_proposal_review_ready_with_warnings",
    "catalog_proposal_review_incomplete",
    "catalog_proposal_review_blocked",
)

PROPOSAL_READY_STATUSES: tuple[str, ...] = (
    "catalog_update_proposal_ready",
    "catalog_update_proposal_ready_with_warnings",
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

REQUIRED_REVIEW_ROLE_IDS: tuple[str, ...] = (
    "ui_reviewer",
    "test_designer",
    "documentation_reviewer",
)

DEFAULT_MODEL_N1_ROLE_IDS: tuple[str, ...] = (
    "fast_scout",
    "planner",
    "patch_implementer",
    "code_reviewer",
    "evidence_checker",
    "risk_auditor",
    "local_fallback",
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
    "automatic_registry_update_performed",
    "task_routing_performed",
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "review-only",
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
    "no mutation of source registry",
    "no mutation of proposed registry",
    "writes review artifacts only",
)

MODEL_ROLE_CATALOG_PROPOSAL_REVIEW_GUARDRAIL_NOTE = (
    "Model Role Catalog Proposal Review is report-only: it reviews the MODEL.N4 "
    "proposed catalog update before any human-approved adoption phase. It does "
    "not replace MODEL.N1, mutate the proposed registry, route tasks, call "
    "models, launch workers, bind executable model IDs, apply patches, run "
    "validation or benchmarks, invoke MCP tools, contact networks, write "
    "databases, or change runtime behavior."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "MODEL.N6",
    "title": "Model Role Catalog Adoption Plan",
    "reason": (
        "After the proposal review is safe, prepare a human-approved adoption "
        "plan for replacing or updating the MODEL.N1 registry artifact, still "
        "without runtime routing or model calls."
    ),
    "alternative_phase_id": "MODEL.CLOSE",
    "alternative_title": "Model Role Planning Checkpoint",
}

MANUAL_REVIEW_CHECKLIST: tuple[str, ...] = (
    "confirm new roles are advisory only",
    "confirm no executable model binding is introduced",
    "confirm model_ids remain metadata only",
    "confirm no routing authority is introduced",
    "confirm no worker-launch authority is introduced",
    "confirm no patch-apply authority is introduced",
    "confirm fallback roles are known",
    "confirm human review remains required for risky roles",
    "confirm source registry is not replaced automatically",
    "confirm adoption requires a separate explicit phase",
)

EXECUTABLE_WORKER_KEYS: tuple[str, ...] = (
    "executable_assignment",
    "executable_worker_id",
    "executable_worker",
    "worker_binding",
    "worker_id",
    "assigned_worker",
    "execution_worker",
    "real_worker_assignment",
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

AUTHORITY_BOUNDARY_FRAGMENTS: tuple[str, ...] = (
    "apply",
    "approval",
    "approve",
    "authority",
    "benchmark",
    "execution",
    "launch",
    "merge",
    "mutation",
    "patch",
    "route",
    "validation",
    "worker",
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


def _ordered_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


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


def _role_id(role: dict[str, Any]) -> str:
    return str(role.get("role_id") or role.get("model_role_id") or "").strip()


def _role_ids(roles: list[dict[str, Any]]) -> list[str]:
    return [_role_id(role) for role in roles if _role_id(role)]


def _role_counts(ids: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for role_id in ids:
        counts[role_id] = counts.get(role_id, 0) + 1
    return counts


def _is_meaningful(value: Any) -> bool:
    return value not in (False, None, "", [], {})


def _proposal_role_ids(proposal_data: dict[str, Any]) -> list[str]:
    return _role_ids(_list_of_dicts(proposal_data.get("proposed_new_roles")))


def _explained_dropped_roles(proposal_data: dict[str, Any]) -> set[str]:
    explained: set[str] = set()
    for key in ("dropped_roles", "proposed_role_removals", "role_removals", "removed_roles"):
        value = proposal_data.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    role_id = str(item.get("role_id") or item.get("affected_role") or "").strip()
                    reason = str(item.get("reason") or item.get("explanation") or "").strip()
                    if role_id and reason:
                        explained.add(role_id)
                elif str(item).strip():
                    explained.add(str(item).strip())
    return explained


def _source_roles(source_registry_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(source_registry_data, dict):
        return []
    return _list_of_dicts(source_registry_data.get("roles"))


def _proposed_roles(proposed_registry_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(proposed_registry_data, dict):
        return []
    return _list_of_dicts(proposed_registry_data.get("roles"))


def _authority_boundary_present(role: dict[str, Any]) -> bool:
    forbidden = [item.lower() for item in _strings(role.get("forbidden_task_types"))]
    return any(any(fragment in item for fragment in AUTHORITY_BOUNDARY_FRAGMENTS) for item in forbidden)


def _scan_role_safety(
    roles: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str], list[str]]:
    warnings: list[str] = []
    blockers: list[str] = []

    advisory_failures: list[str] = []
    executable_failures: list[str] = []
    human_review_failures: list[str] = []
    forbidden_authority_hits: list[str] = []
    executable_worker_hits: list[str] = []
    model_id_authority_hits: list[str] = []
    metadata_warnings: list[str] = []

    ids = _role_ids(roles)
    counts = _role_counts(ids)
    duplicate_ids = sorted(role_id for role_id, count in counts.items() if count > 1)
    unsafe_ids = sorted(role_id for role_id in ids if not _safe_identifier(role_id))
    for role_id in duplicate_ids:
        blockers.append(f"duplicate role_id: {role_id}")
    for role_id in unsafe_ids:
        blockers.append(f"role {role_id} has an unsafe or empty role_id")

    for index, role in enumerate(roles):
        role_id = _role_id(role) or f"#{index}"
        role_kind = str(role.get("role_kind") or "").strip()
        if role.get("advisory_only") is not True:
            reason = f"role {role_id} advisory_only must be true"
            advisory_failures.append(role_id)
            blockers.append(reason)
        if role.get("executable_binding_allowed") is True:
            reason = f"role {role_id} executable_binding_allowed must be false"
            executable_failures.append(role_id)
            blockers.append(reason)
        if (
            role_kind in {"implementer", "reviewer", "risk_auditor"}
            or role_id in REQUIRED_REVIEW_ROLE_IDS
            or any(token in role_id for token in ("ui", "test", "doc"))
        ) and role.get("human_review_required") is not True:
            reason = f"role {role_id} human_review_required must be true"
            human_review_failures.append(role_id)
            blockers.append(reason)
        for flag in FORBIDDEN_AUTHORITY_FLAGS:
            if flag in role:
                reason = f"role {role_id} includes forbidden authority flag: {flag}"
                forbidden_authority_hits.append(reason)
                blockers.append(reason)
        for key in EXECUTABLE_WORKER_KEYS:
            if key in role and _is_meaningful(role.get(key)):
                reason = f"role {role_id} defines executable worker binding via {key}"
                executable_worker_hits.append(reason)
                blockers.append(reason)
        for key in MODEL_ID_AUTHORITY_KEYS:
            if key in role and _is_meaningful(role.get(key)):
                reason = f"role {role_id} defines executable model authority via {key}"
                model_id_authority_hits.append(reason)
                blockers.append(reason)
        model_id_policy = str(role.get("model_id_policy") or "descriptive_metadata_only").strip()
        if model_id_policy != "descriptive_metadata_only":
            reason = f"role {role_id} model_id_policy must keep model_ids descriptive metadata only"
            model_id_authority_hits.append(reason)
            blockers.append(reason)
        for key, value in role.items():
            low = str(key).lower()
            if any(fragment in low for fragment in AUTHORITY_KEY_FRAGMENTS) and bool(value):
                reason = f"role {role_id} claims executable authority via {key}"
                forbidden_authority_hits.append(reason)
                blockers.append(reason)
        if (
            role_kind in {"implementer", "reviewer", "risk_auditor"}
            or role_id in REQUIRED_REVIEW_ROLE_IDS
        ) and not _authority_boundary_present(role):
            metadata_warnings.append(f"role {role_id} should explicitly forbid authority boundaries")
        if not _strings(role.get("forbidden_task_types")):
            metadata_warnings.append(f"role {role_id} has empty forbidden_task_types")
        if not _strings(role.get("best_for")):
            metadata_warnings.append(f"role {role_id} has empty best_for")
        if not str(role.get("evidence_expectation") or "").strip():
            metadata_warnings.append(f"role {role_id} has empty evidence_expectation")

    safety_review = {
        "advisory_only_failures": _unique(advisory_failures),
        "executable_binding_failures": _unique(executable_failures),
        "human_review_failures": _unique(human_review_failures),
        "passed": not (advisory_failures or executable_failures or human_review_failures),
    }
    authority_review = {
        "forbidden_flags": list(FORBIDDEN_AUTHORITY_FLAGS),
        "forbidden_authority_hits": _unique(forbidden_authority_hits),
        "executable_worker_binding_hits": _unique(executable_worker_hits),
        "model_id_authority_hits": _unique(model_id_authority_hits),
        "passed": not (forbidden_authority_hits or executable_worker_hits or model_id_authority_hits),
    }
    proposed_role_review = {
        "duplicate_role_ids": duplicate_ids,
        "unsafe_role_ids": unsafe_ids,
    }
    warnings += metadata_warnings
    return safety_review, authority_review, proposed_role_review, warnings, blockers


def _fallback_review(roles: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    known = set(_role_ids(roles))
    unknown_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    fallback_map: dict[str, list[str]] = {}
    for role in roles:
        role_id = _role_id(role)
        fallbacks = _strings(role.get("fallback_roles"))
        if role_id:
            fallback_map[role_id] = fallbacks
        for fallback in fallbacks:
            if fallback not in known:
                unknown_rows.append({"role_id": role_id, "fallback_role": fallback})
                blockers.append(f"role {role_id} references unknown fallback role: {fallback}")
    return {
        "fallback_map": {key: fallback_map[key] for key in sorted(fallback_map)},
        "unknown_fallback_roles": unknown_rows,
        "passed": not unknown_rows,
    }, blockers


def _review_status(
    *,
    blockers: list[str],
    incomplete: list[str],
    warnings: list[str],
) -> str:
    if blockers:
        return "catalog_proposal_review_blocked"
    if incomplete:
        return "catalog_proposal_review_incomplete"
    if warnings:
        return "catalog_proposal_review_ready_with_warnings"
    return "catalog_proposal_review_ready"


def _adoption_readiness(status: str) -> str:
    if status == "catalog_proposal_review_blocked":
        return "blocked_do_not_adopt"
    if status == "catalog_proposal_review_incomplete":
        return "not_ready_missing_evidence"
    if status == "catalog_proposal_review_ready_with_warnings":
        return "ready_with_manual_warnings"
    return "ready_for_human_adoption_review"


def build_model_role_catalog_proposal_review(
    *,
    proposal_path: str | Path | None,
    proposal_data: dict[str, Any] | None = None,
    proposed_registry_path: str | Path | None = None,
    proposed_registry_data: dict[str, Any] | None = None,
    source_registry_path: str | Path | None = None,
    source_registry_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic MODEL.N5 review from loaded artifacts."""
    blockers = list(input_blockers or [])
    blockers += _input_path_blockers(proposal_path, "proposal", required=True)
    blockers += _input_path_blockers(proposed_registry_path, "proposed registry", required=False)
    blockers += _input_path_blockers(source_registry_path, "source registry", required=False)
    warnings: list[str] = []
    incomplete: list[str] = []

    proposed_registry_missing = proposed_registry_data is None

    if proposal_data is None:
        proposal_data = {}
        blockers.append("proposal is missing or malformed")
    if not isinstance(proposal_data, dict):
        proposal_data = {}
        blockers.append("proposal must contain a JSON object")
    if proposed_registry_data is None:
        proposed_registry_data = {}
        incomplete.append("proposed registry is missing")
    if not isinstance(proposed_registry_data, dict):
        proposed_registry_data = {}
        blockers.append("proposed registry must contain a JSON object")
    if source_registry_data is not None and not isinstance(source_registry_data, dict):
        source_registry_data = {}
        blockers.append("source registry must contain a JSON object")

    if proposal_data.get("report_kind") != PROPOSAL_REPORT_KIND:
        blockers.append("proposal report_kind must be model_role_catalog_update_proposal")
    proposal_status = str(proposal_data.get("proposal_status") or "")
    if proposal_status not in PROPOSAL_READY_STATUSES:
        if proposal_status == "catalog_update_proposal_incomplete":
            incomplete.append("proposal status is catalog_update_proposal_incomplete")
        else:
            blockers.append(
                "proposal status must be catalog_update_proposal_ready or "
                "catalog_update_proposal_ready_with_warnings"
            )
    if proposal_status == "catalog_update_proposal_ready_with_warnings":
        warnings.append("source proposal status is catalog_update_proposal_ready_with_warnings")
    for reason in _strings(proposal_data.get("blocked_reasons")):
        blockers.append(f"proposal blocker: {reason}")

    if proposed_registry_data and proposed_registry_data.get("report_kind") != PROPOSED_REGISTRY_REPORT_KIND:
        blockers.append("proposed registry report_kind must be proposed_model_role_registry")
    if proposed_registry_data and not isinstance(proposed_registry_data.get("roles"), list):
        blockers.append("proposed registry roles must be a list")
    if source_registry_data is not None:
        if source_registry_data.get("report_kind") != SOURCE_REGISTRY_REPORT_KIND:
            blockers.append("source registry report_kind must be model_role_registry")
        if not isinstance(source_registry_data.get("roles"), list):
            blockers.append("source registry roles must be a list")
        source_status = str(source_registry_data.get("validation_status") or "")
        if source_status and source_status not in {"model_roles_ready", "model_roles_ready_with_warnings"}:
            warnings.append(f"source registry validation_status is {source_status}")

    proposed_roles = _proposed_roles(proposed_registry_data)
    source_roles = _source_roles(source_registry_data)
    proposed_role_ids = _role_ids(proposed_roles)
    source_role_ids = _role_ids(source_roles)
    proposed_new_role_ids = _proposal_role_ids(proposal_data)
    proposed_id_set = set(proposed_role_ids)
    source_id_set = set(source_role_ids)

    if proposed_registry_data and not proposed_roles:
        incomplete.append("proposed registry contains no roles")
    if not proposed_new_role_ids:
        incomplete.append("proposal lacks useful new roles")
    addressed_gap_roles = [role_id for role_id in REQUIRED_REVIEW_ROLE_IDS if role_id in proposed_new_role_ids]
    if proposed_new_role_ids and not addressed_gap_roles:
        incomplete.append("proposed roles do not address MODEL.N3 review-role gaps")

    missing_new_roles = (
        sorted(role_id for role_id in proposed_new_role_ids if role_id not in proposed_id_set)
        if not proposed_registry_missing
        else []
    )
    for role_id in missing_new_roles:
        blockers.append(f"proposed new role {role_id} is missing from proposed registry")

    source_drops = sorted(source_id_set - proposed_id_set) if not proposed_registry_missing else []
    explained_drops = _explained_dropped_roles(proposal_data)
    unexplained_drops = [role_id for role_id in source_drops if role_id not in explained_drops]
    for role_id in unexplained_drops:
        blockers.append(f"source role dropped without explanation: {role_id}")

    default_role_coverage = (
        {
            role_id: role_id in proposed_id_set
            for role_id in (source_role_ids or list(DEFAULT_MODEL_N1_ROLE_IDS))
        }
        if not proposed_registry_missing
        else {}
    )
    for role_id, covered in default_role_coverage.items():
        if not covered:
            blockers.append(f"proposed catalog does not cover existing MODEL.N1 role: {role_id}")

    declared_registry_count = proposed_registry_data.get("role_count") if proposed_registry_data else None
    proposal_count = proposal_data.get("proposed_role_count")
    diff = proposal_data.get("diff_summary") if isinstance(proposal_data.get("diff_summary"), dict) else {}
    diff_count = diff.get("proposed_role_count")
    actual_count = len(proposed_roles)
    count_pairs = [
        ("proposed registry role_count", declared_registry_count),
        ("proposal proposed_role_count", proposal_count),
        ("proposal diff_summary.proposed_role_count", diff_count),
    ]
    for label, value in count_pairs:
        if isinstance(value, int) and proposed_roles and value != actual_count:
            warnings.append(f"{label} role count {value} does not match proposed registry roles {actual_count}")

    safety_review, authority_review, duplicate_review, safety_warnings, safety_blockers = _scan_role_safety(
        proposed_roles
    )
    warnings += safety_warnings
    blockers += safety_blockers
    fallback_review, fallback_blockers = _fallback_review(proposed_roles)
    blockers += fallback_blockers

    proposed_role_review = {
        "expected_review_role_ids": list(REQUIRED_REVIEW_ROLE_IDS),
        "proposed_new_role_ids": _ordered_unique(proposed_new_role_ids),
        "registered_role_ids": _ordered_unique(proposed_role_ids),
        "missing_from_proposed_registry": missing_new_roles,
        "duplicate_role_ids": duplicate_review["duplicate_role_ids"],
        "unsafe_role_ids": duplicate_review["unsafe_role_ids"],
        "passed": not (
            missing_new_roles
            or duplicate_review["duplicate_role_ids"]
            or duplicate_review["unsafe_role_ids"]
        ),
    }
    coverage_review = {
        "source_role_ids": _ordered_unique(source_role_ids),
        "proposed_role_ids": _ordered_unique(proposed_role_ids),
        "source_roles_preserved": not unexplained_drops,
        "source_roles_dropped_without_explanation": unexplained_drops,
        "proposed_new_roles_registered": not missing_new_roles,
        "model_n3_gap_roles_addressed": addressed_gap_roles,
        "default_role_coverage": default_role_coverage,
        "passed": not unexplained_drops and not missing_new_roles and all(default_role_coverage.values()),
    }
    metadata_review = {
        "proposal_status": proposal_status,
        "proposal_warning_count": len(proposal_data.get("warnings") or []),
        "proposal_blocked_reason_count": len(proposal_data.get("blocked_reasons") or []),
        "proposed_registry_declared_role_count": declared_registry_count,
        "actual_proposed_registry_role_count": actual_count,
        "optional_metadata_warnings": _unique(safety_warnings),
        "passed": not safety_warnings,
    }
    proposal_summary = {
        "proposal_id": proposal_data.get("proposal_id", ""),
        "proposal_status": proposal_status,
        "source_role_count": len(source_roles),
        "proposal_current_role_count": proposal_data.get("current_role_count", len(source_roles)),
        "proposed_role_count": actual_count,
        "proposal_proposed_role_count": proposal_count,
        "proposed_new_role_count": len(proposed_new_role_ids),
        "proposed_role_update_count": len(proposal_data.get("proposed_role_updates") or []),
        "rejected_gap_item_count": len(proposal_data.get("rejected_gap_items") or []),
    }

    warnings = _unique(warnings)
    blockers = _unique(blockers)
    incomplete = _unique(incomplete)
    status = _review_status(blockers=blockers, incomplete=incomplete, warnings=warnings)

    return {
        "report_kind": REPORT_KIND,
        "review_id": "model-role-catalog-proposal-review",
        "guardrail_note": MODEL_ROLE_CATALOG_PROPOSAL_REVIEW_GUARDRAIL_NOTE,
        "source_proposal_path": str(proposal_path or ""),
        "source_registry_path": str(source_registry_path or proposal_data.get("source_model_registry_path") or ""),
        "proposed_registry_path": str(proposed_registry_path or ""),
        "review_status": status,
        "proposal_summary": proposal_summary,
        "proposed_role_review": proposed_role_review,
        "coverage_review": coverage_review,
        "safety_review": safety_review,
        "authority_review": authority_review,
        "fallback_review": fallback_review,
        "metadata_review": metadata_review,
        "adoption_readiness": _adoption_readiness(status),
        "manual_review_checklist": list(MANUAL_REVIEW_CHECKLIST),
        "warnings": warnings,
        "incomplete_reasons": incomplete,
        "blocked_reasons": blockers,
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
        "review_statuses": list(REVIEW_STATUSES),
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


def render_model_role_catalog_proposal_review_markdown(report: dict[str, Any]) -> str:
    """Render a MODEL.N5 proposal review as Markdown."""
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    proposal_summary = report.get("proposal_summary") if isinstance(report.get("proposal_summary"), dict) else {}
    role_review = report.get("proposed_role_review") if isinstance(report.get("proposed_role_review"), dict) else {}
    coverage = report.get("coverage_review") if isinstance(report.get("coverage_review"), dict) else {}
    safety = report.get("safety_review") if isinstance(report.get("safety_review"), dict) else {}
    authority = report.get("authority_review") if isinstance(report.get("authority_review"), dict) else {}
    fallback = report.get("fallback_review") if isinstance(report.get("fallback_review"), dict) else {}
    metadata = report.get("metadata_review") if isinstance(report.get("metadata_review"), dict) else {}

    lines: list[str] = [
        "# Model Role Catalog Proposal Review",
        "",
        f"> {report.get('guardrail_note', MODEL_ROLE_CATALOG_PROPOSAL_REVIEW_GUARDRAIL_NOTE)}",
        "",
        "_Report only: MODEL.N5 reviews the MODEL.N4 proposal and does not adopt or mutate any registry._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Review status:** `{_md(report.get('review_status', ''))}`",
        f"- **Adoption readiness:** `{_md(report.get('adoption_readiness', ''))}`",
        f"- **Warnings:** {len(report.get('warnings') or [])}",
        f"- **Incomplete reasons:** {len(report.get('incomplete_reasons') or [])}",
        f"- **Blocked reasons:** {len(report.get('blocked_reasons') or [])}",
        "",
        "## Proposal Summary",
        "",
    ]
    _render_dict(lines, proposal_summary)
    lines += ["## Proposed Role Review", ""]
    _render_dict(lines, role_review)
    lines += ["## Coverage Review", ""]
    _render_dict(lines, coverage)
    lines += ["## Safety Review", ""]
    _render_dict(lines, safety)
    lines += ["## Authority Review", ""]
    _render_dict(lines, authority)
    lines += ["## Fallback Review", ""]
    _render_dict(lines, fallback)
    lines += ["## Metadata Review", ""]
    _render_dict(lines, metadata)
    lines += ["## Adoption Readiness", ""]
    lines.append(f"- `{_md(report.get('adoption_readiness', ''))}`")
    lines.append("")
    lines += ["## Manual Review Checklist", ""]
    _render_list(lines, list(report.get("manual_review_checklist") or []))
    lines += ["## Warnings", ""]
    _render_list(lines, list(report.get("warnings") or []))
    lines += ["## Incomplete Reasons", ""]
    _render_list(lines, list(report.get("incomplete_reasons") or []))
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
        f"- **Alternative:** `{_md(next_phase.get('alternative_phase_id', ''))}` - {_md(next_phase.get('alternative_title', ''))}",
        "",
    ]
    return "\n".join(lines)


def write_model_role_catalog_proposal_review(
    *,
    proposal_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    proposed_registry_path: str | Path | None = None,
    source_registry_path: str | Path | None = None,
    proposal_data: dict[str, Any] | None = None,
    proposed_registry_data: dict[str, Any] | None = None,
    source_registry_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build and write MODEL.N5 JSON + Markdown review artifacts."""
    blockers = list(input_blockers or [])
    if proposal_data is None and not blockers:
        proposal_data, read_blockers = read_json_input(proposal_path, "proposal", required=True)
        blockers += read_blockers
    if proposed_registry_path is not None and proposed_registry_data is None and not blockers:
        proposed_registry_data, read_blockers = read_json_input(proposed_registry_path, "proposed registry")
        blockers += read_blockers
    if source_registry_path is not None and source_registry_data is None and not blockers:
        source_registry_data, read_blockers = read_json_input(source_registry_path, "source registry")
        blockers += read_blockers
    report = build_model_role_catalog_proposal_review(
        proposal_path=proposal_path,
        proposal_data=proposal_data,
        proposed_registry_path=proposed_registry_path,
        proposed_registry_data=proposed_registry_data,
        source_registry_path=source_registry_path,
        source_registry_data=source_registry_data,
        input_blockers=blockers,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_model_role_catalog_proposal_review_markdown(report), encoding="utf-8")
    ok = report.get("review_status") in {
        "catalog_proposal_review_ready",
        "catalog_proposal_review_ready_with_warnings",
    }
    return {
        "ok": ok,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
