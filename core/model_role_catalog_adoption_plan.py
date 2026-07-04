"""MODEL.N6 - Model Role Catalog Adoption Plan (report-only).

Reads a MODEL.N5 proposal review plus MODEL.N1/MODEL.N4 registry artifacts and
writes a human-reviewable adoption plan. MODEL.N6 never replaces the active
MODEL.N1 registry, mutates the proposed registry, changes runtime model
selection, routes tasks, calls models, launches workers, binds executable model
IDs, applies patches, runs validation or benchmarks, invokes MCP tools, contacts
networks, writes databases, or changes runtime behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "model_role_catalog_adoption_plan"
JSON_NAME = "model_role_catalog_adoption_plan.json"
MD_NAME = "model_role_catalog_adoption_plan.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "model_role_registry" / "model_role_catalog_adoption_plan"

REVIEW_REPORT_KIND = "model_role_catalog_proposal_review"
SOURCE_REGISTRY_REPORT_KIND = "model_role_registry"
PROPOSED_REGISTRY_REPORT_KIND = "proposed_model_role_registry"

ADOPTION_PLAN_STATUSES: tuple[str, ...] = (
    "adoption_plan_ready",
    "adoption_plan_ready_with_warnings",
    "adoption_plan_incomplete",
    "adoption_plan_blocked",
)

REVIEW_READY_STATUSES: tuple[str, ...] = (
    "catalog_proposal_review_ready",
    "catalog_proposal_review_ready_with_warnings",
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
    "adoption planning only",
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
    "writes adoption plan artifacts only",
)

MODEL_ROLE_CATALOG_ADOPTION_PLAN_GUARDRAIL_NOTE = (
    "Model Role Catalog Adoption Plan is report-only: it explains how a human "
    "could safely adopt the reviewed MODEL.N4 proposed catalog in a later "
    "explicit phase. It does not replace MODEL.N1, mutate proposed registries, "
    "change runtime model selection, route tasks, call models, launch workers, "
    "bind executable model IDs, apply patches, run validation or benchmarks, "
    "invoke MCP tools, contact networks, write databases, or perform automatic "
    "adoption."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "MODEL.N7",
    "title": "Model Role Catalog Adoption Readiness Check",
    "reason": (
        "Run one final report-only readiness gate before any human-approved "
        "catalog adoption writes to the active MODEL.N1 artifact."
    ),
    "alternative_phase_id": "MODEL.CLOSE",
    "alternative_title": "Model Role Planning Checkpoint",
}

ACTIVE_REGISTRY_JSON = ".agent/model_role_registry/model_role_registry.json"
ACTIVE_REGISTRY_MD = ".agent/model_role_registry/model_role_registry.md"
PROPOSED_REGISTRY_JSON = (
    ".agent/model_role_registry/model_role_catalog_update_proposal/proposed_model_role_registry.json"
)

FILES_THAT_WOULD_CHANGE: tuple[str, ...] = (
    ACTIVE_REGISTRY_JSON,
    ACTIVE_REGISTRY_MD,
    "docs/roadmap/phase_registry.json",
)

FILES_THAT_MUST_NOT_CHANGE: tuple[str, ...] = (
    ACTIVE_REGISTRY_JSON,
    ACTIVE_REGISTRY_MD,
    PROPOSED_REGISTRY_JSON,
    ".agent/commander/",
    "core/router.py",
    "core/driver_model_routing.py",
    "web/routes/",
    "agents/",
)

HUMAN_APPROVAL_CHECKLIST: tuple[str, ...] = (
    "human reviewed MODEL.N5 review",
    "human reviewed proposed registry",
    "human confirmed advisory_only remains true",
    "human confirmed executable_binding_allowed remains false",
    "human confirmed model_ids are metadata only",
    "human confirmed no routing authority is introduced",
    "human confirmed no worker launch authority is introduced",
    "human confirmed no patch apply authority is introduced",
    "human confirmed rollback path is clear",
    "human confirmed adoption will happen only in a separate explicit phase",
)

FORBIDDEN_ACTIONS: tuple[str, ...] = (
    "do not replace source registry in MODEL.N6",
    "do not mutate proposed registry in MODEL.N6",
    "do not update runtime routing",
    "do not bind model IDs to executable workers",
    "do not authorize model calls",
    "do not add worker launch",
    "do not add auto_run",
    "do not add auto_apply",
    "do not add auto_merge",
    "do not treat proposal review as adoption approval",
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


def _review_proposed_new_ids(review_data: dict[str, Any]) -> list[str]:
    role_review = review_data.get("proposed_role_review")
    if not isinstance(role_review, dict):
        return []
    return _strings(role_review.get("proposed_new_role_ids"))


def _source_roles(source_registry_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(source_registry_data, dict):
        return []
    return _list_of_dicts(source_registry_data.get("roles"))


def _proposed_roles(proposed_registry_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(proposed_registry_data, dict):
        return []
    return _list_of_dicts(proposed_registry_data.get("roles"))


def _adoption_steps() -> list[dict[str, Any]]:
    actions = [
        "Review MODEL.N5 proposal review.",
        "Review proposed_model_role_registry.json manually.",
        "Confirm no executable model binding exists.",
        "Confirm no routing or worker-launch authority exists.",
        "Confirm new roles are advisory labels only.",
        "Backup the current MODEL.N1 model_role_registry artifact.",
        "Replace/update the catalog only in a separate human-approved adoption phase.",
        "Re-run MODEL.N1 validation after adoption.",
        "Re-run MODEL.N2 coverage after adoption.",
        "Re-run benchmark check.",
        "Roll back to the previous registry if validation fails.",
    ]
    return [
        {
            "step": index + 1,
            "action": action,
            "requires_human_approval": index in {0, 1, 5, 6, 10},
        }
        for index, action in enumerate(actions)
    ]


def _rollback_plan() -> dict[str, Any]:
    return {
        "preserve_current_registry_artifact_path": ACTIVE_REGISTRY_JSON,
        "backup_before_adoption": "copy current registry JSON and Markdown to a timestamped backup before adoption",
        "restore_backup_if_validation_fails": True,
        "never_roll_forward_automatically_after_failed_validation": True,
        "human_confirmation_required_before_retry": True,
        "rollback_steps": [
            "Stop the adoption attempt if MODEL.N1, MODEL.N2, or benchmark checks fail.",
            "Restore the timestamped MODEL.N1 registry JSON and Markdown backup.",
            "Re-run MODEL.N1 and MODEL.N2 reports against the restored registry.",
            "Require explicit human confirmation before any retry.",
        ],
    }


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
        return "adoption_plan_blocked"
    if incomplete:
        return "adoption_plan_incomplete"
    if warnings:
        return "adoption_plan_ready_with_warnings"
    return "adoption_plan_ready"


def build_model_role_catalog_adoption_plan(
    *,
    review_path: str | Path | None,
    review_data: dict[str, Any] | None = None,
    source_registry_path: str | Path | None = None,
    source_registry_data: dict[str, Any] | None = None,
    proposed_registry_path: str | Path | None = None,
    proposed_registry_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic MODEL.N6 adoption plan from loaded artifacts."""
    blockers = list(input_blockers or [])
    blockers += _input_path_blockers(review_path, "review", required=True)
    blockers += _input_path_blockers(source_registry_path, "source registry", required=True)
    blockers += _input_path_blockers(proposed_registry_path, "proposed registry", required=True)
    warnings: list[str] = []
    incomplete: list[str] = []

    if review_data is None:
        review_data = {}
        blockers.append("review is missing or malformed")
    if not isinstance(review_data, dict):
        review_data = {}
        blockers.append("review must contain a JSON object")
    if source_registry_data is None:
        source_registry_data = {}
        blockers.append("source registry is missing or malformed")
    if not isinstance(source_registry_data, dict):
        source_registry_data = {}
        blockers.append("source registry must contain a JSON object")
    if proposed_registry_data is None:
        proposed_registry_data = {}
        blockers.append("proposed registry is missing")
    if not isinstance(proposed_registry_data, dict):
        proposed_registry_data = {}
        blockers.append("proposed registry must contain a JSON object")

    if review_data.get("report_kind") != REVIEW_REPORT_KIND:
        blockers.append("review report_kind must be model_role_catalog_proposal_review")
    review_status = str(review_data.get("review_status") or "")
    if review_status not in REVIEW_READY_STATUSES:
        if review_status == "catalog_proposal_review_incomplete":
            incomplete.append("review status is catalog_proposal_review_incomplete")
        else:
            blockers.append(
                "review status must be catalog_proposal_review_ready or "
                "catalog_proposal_review_ready_with_warnings"
            )
    if review_status == "catalog_proposal_review_ready_with_warnings":
        warnings.append("review status is catalog_proposal_review_ready_with_warnings")
    for reason in _strings(review_data.get("blocked_reasons")):
        blockers.append(f"review blocker: {reason}")
    warnings += [f"review warning: {item}" for item in _strings(review_data.get("warnings"))]

    if source_registry_data.get("report_kind") != SOURCE_REGISTRY_REPORT_KIND:
        blockers.append("source registry report_kind must be model_role_registry")
    if not isinstance(source_registry_data.get("roles"), list):
        blockers.append("source registry roles must be a list")
    if proposed_registry_data.get("report_kind") != PROPOSED_REGISTRY_REPORT_KIND:
        blockers.append("proposed registry report_kind must be proposed_model_role_registry")
    if not isinstance(proposed_registry_data.get("roles"), list):
        blockers.append("proposed registry roles must be a list")

    source_roles = _source_roles(source_registry_data)
    proposed_roles = _proposed_roles(proposed_registry_data)
    source_ids = _role_ids(source_roles)
    proposed_ids = _role_ids(proposed_roles)
    source_id_set = set(source_ids)
    proposed_id_set = set(proposed_ids)

    if not source_roles:
        blockers.append("source registry contains no roles")
    if not proposed_roles:
        blockers.append("proposed registry contains no roles")

    dropped = sorted(source_id_set - proposed_id_set)
    for role_id in dropped:
        blockers.append(f"source role dropped in proposed registry: {role_id}")

    review_expected_count = None
    proposal_summary = review_data.get("proposal_summary")
    if isinstance(proposal_summary, dict) and isinstance(proposal_summary.get("proposed_role_count"), int):
        review_expected_count = int(proposal_summary["proposed_role_count"])
    declared_proposed_count = proposed_registry_data.get("role_count")
    actual_proposed_count = len(proposed_roles)
    if isinstance(declared_proposed_count, int) and declared_proposed_count != actual_proposed_count:
        warnings.append(
            f"proposed registry role_count {declared_proposed_count} does not match roles {actual_proposed_count}"
        )
    if isinstance(review_expected_count, int) and review_expected_count != actual_proposed_count:
        blockers.append(
            f"proposed registry role count {actual_proposed_count} does not match review expected {review_expected_count}"
        )

    review_new_ids = _review_proposed_new_ids(review_data)
    new_ids = [role_id for role_id in proposed_ids if role_id not in source_id_set]
    missing_new = sorted(role_id for role_id in review_new_ids if role_id not in proposed_id_set)
    for role_id in missing_new:
        blockers.append(f"expected new role missing from proposed registry: {role_id}")
    if not new_ids and not review_new_ids:
        incomplete.append("proposed changes are unclear")

    safety_checks, safety_warnings, safety_blockers = _role_safety(proposed_roles)
    warnings += safety_warnings
    blockers += safety_blockers

    adoption_steps = _adoption_steps()
    rollback_plan = _rollback_plan()
    rollback_defined = bool(rollback_plan.get("restore_backup_if_validation_fails")) and bool(
        rollback_plan.get("human_confirmation_required_before_retry")
    )
    safety_checks.update(
        {
            "review_status_acceptable": review_status in REVIEW_READY_STATUSES,
            "review_blockers_absent": not _strings(review_data.get("blocked_reasons")),
            "role_count_matches_review": not (
                isinstance(review_expected_count, int) and review_expected_count != actual_proposed_count
            ),
            "source_roles_preserved": not dropped,
            "expected_new_roles_present": not missing_new,
            "rollback_defined": rollback_defined,
            "human_approval_required_for_later_adoption": True,
            "passed": not blockers,
        }
    )

    warnings = _unique(warnings)
    blockers = _unique(blockers)
    incomplete = _unique(incomplete)
    plan_status = _status(blockers=blockers, incomplete=incomplete, warnings=warnings)

    proposed_new_roles = [dict(role) for role in proposed_roles if _role_id(role) in set(new_ids)]
    return {
        "report_kind": REPORT_KIND,
        "plan_id": "model-role-catalog-adoption-plan",
        "guardrail_note": MODEL_ROLE_CATALOG_ADOPTION_PLAN_GUARDRAIL_NOTE,
        "source_review_path": str(review_path or ""),
        "source_registry_path": str(source_registry_path or ""),
        "proposed_registry_path": str(proposed_registry_path or ""),
        "adoption_plan_status": plan_status,
        "source_review": {
            "path": str(review_path or ""),
            "report_kind": review_data.get("report_kind", ""),
            "review_status": review_status,
            "blocked_reason_count": len(review_data.get("blocked_reasons") or []),
            "warning_count": len(review_data.get("warnings") or []),
            "loaded": bool(review_data),
        },
        "source_registry": {
            "path": str(source_registry_path or ""),
            "report_kind": source_registry_data.get("report_kind", ""),
            "validation_status": source_registry_data.get("validation_status", ""),
            "role_count": len(source_roles),
            "loaded": bool(source_registry_data),
        },
        "proposed_registry": {
            "path": str(proposed_registry_path or ""),
            "report_kind": proposed_registry_data.get("report_kind", ""),
            "declared_role_count": declared_proposed_count,
            "role_count": actual_proposed_count,
            "loaded": bool(proposed_registry_data),
        },
        "current_role_count": len(source_roles),
        "proposed_role_count": actual_proposed_count,
        "proposed_new_roles": proposed_new_roles,
        "proposed_updated_roles": [],
        "adoption_steps": adoption_steps,
        "rollback_plan": rollback_plan,
        "files_that_would_change": list(FILES_THAT_WOULD_CHANGE),
        "files_that_must_not_change": list(FILES_THAT_MUST_NOT_CHANGE),
        "human_approval_checklist": list(HUMAN_APPROVAL_CHECKLIST),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "safety_checks": safety_checks,
        "warnings": warnings,
        "incomplete_reasons": incomplete,
        "blocked_reasons": blockers,
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
        "adoption_plan_statuses": list(ADOPTION_PLAN_STATUSES),
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


def render_model_role_catalog_adoption_plan_markdown(report: dict[str, Any]) -> str:
    """Render a MODEL.N6 adoption plan as Markdown."""
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    source_review = report.get("source_review") if isinstance(report.get("source_review"), dict) else {}
    source_registry = report.get("source_registry") if isinstance(report.get("source_registry"), dict) else {}
    proposed_registry = report.get("proposed_registry") if isinstance(report.get("proposed_registry"), dict) else {}
    rollback = report.get("rollback_plan") if isinstance(report.get("rollback_plan"), dict) else {}
    safety = report.get("safety_checks") if isinstance(report.get("safety_checks"), dict) else {}

    lines: list[str] = [
        "# Model Role Catalog Adoption Plan",
        "",
        f"> {report.get('guardrail_note', MODEL_ROLE_CATALOG_ADOPTION_PLAN_GUARDRAIL_NOTE)}",
        "",
        "_Report only: MODEL.N6 explains a later human-approved adoption path and does not adopt the catalog._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Adoption plan status:** `{_md(report.get('adoption_plan_status', ''))}`",
        f"- **Current role count:** {report.get('current_role_count', 0)}",
        f"- **Proposed role count:** {report.get('proposed_role_count', 0)}",
        f"- **Proposed new roles:** {len(report.get('proposed_new_roles') or [])}",
        f"- **Warnings:** {len(report.get('warnings') or [])}",
        f"- **Blocked reasons:** {len(report.get('blocked_reasons') or [])}",
        "",
        "## Source Review",
        "",
    ]
    _render_dict(lines, source_review)
    lines += ["## Source Registry", ""]
    _render_dict(lines, source_registry)
    lines += ["## Proposed Registry", ""]
    _render_dict(lines, proposed_registry)
    lines += ["## Adoption Plan", ""]
    steps = report.get("adoption_steps") if isinstance(report.get("adoption_steps"), list) else []
    if steps:
        for step in steps:
            lines.append(
                f"{step.get('step', '')}. {_md(step.get('action', ''))} "
                f"(human approval: {str(bool(step.get('requires_human_approval'))).lower()})"
            )
    else:
        lines.append("_None._")
    lines.append("")
    lines += ["## Rollback Plan", ""]
    _render_dict(lines, rollback)
    lines += ["## Files That Would Change Later", ""]
    _render_list(lines, list(report.get("files_that_would_change") or []), code=True)
    lines += ["## Files That Must Not Change Now", ""]
    _render_list(lines, list(report.get("files_that_must_not_change") or []), code=True)
    lines += ["## Human Approval Checklist", ""]
    _render_list(lines, list(report.get("human_approval_checklist") or []))
    lines += ["## Safety Checks", ""]
    _render_dict(lines, safety)
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
        f"- **Alternative:** `{_md(next_phase.get('alternative_phase_id', ''))}` - {_md(next_phase.get('alternative_title', ''))}",
        "",
    ]
    return "\n".join(lines)


def write_model_role_catalog_adoption_plan(
    *,
    review_path: str | Path,
    source_registry_path: str | Path,
    proposed_registry_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    review_data: dict[str, Any] | None = None,
    source_registry_data: dict[str, Any] | None = None,
    proposed_registry_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build and write MODEL.N6 JSON + Markdown adoption plan artifacts."""
    blockers = list(input_blockers or [])
    if review_data is None and not blockers:
        review_data, read_blockers = read_json_input(review_path, "review", required=True)
        blockers += read_blockers
    if source_registry_data is None and not blockers:
        source_registry_data, read_blockers = read_json_input(source_registry_path, "source registry", required=True)
        blockers += read_blockers
    if proposed_registry_data is None and not blockers:
        proposed_registry_data, read_blockers = read_json_input(proposed_registry_path, "proposed registry", required=True)
        blockers += read_blockers
    report = build_model_role_catalog_adoption_plan(
        review_path=review_path,
        review_data=review_data,
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
    md_path.write_text(render_model_role_catalog_adoption_plan_markdown(report), encoding="utf-8")
    ok = report.get("adoption_plan_status") in {
        "adoption_plan_ready",
        "adoption_plan_ready_with_warnings",
    }
    return {"ok": ok, "json_path": str(json_path), "md_path": str(md_path), "report": report}
