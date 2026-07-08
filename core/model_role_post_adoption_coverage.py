"""ADOPT.MODEL.2 - Post-Adoption Role Coverage Recheck.

Rechecks the adopted active advisory model-role catalog after ADOPT.MODEL.1.
This module reads deterministic JSON artifacts and writes JSON/Markdown
coverage artifacts only. It does not route tasks, call models, launch workers,
create executable model bindings, apply patches, run validation or benchmarks,
invoke MCP tools, contact networks, write databases, change route/auth
behavior, enforce approval tokens, or grant automatic authority.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "model_role_post_adoption_coverage"
JSON_NAME = "model_role_post_adoption_coverage.json"
MD_NAME = "model_role_post_adoption_coverage.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "model_role_registry" / "post_adoption_coverage"

MODEL_REGISTRY_REPORT_KIND = "model_role_registry"
ADOPTION_RECEIPT_REPORT_KIND = "model_role_catalog_adoption_receipt"
GAP_PLAN_REPORT_KIND = "model_role_gap_plan"
READINESS_REPORT_KIND = "model_role_catalog_adoption_readiness"

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

POST_ADOPTION_COVERAGE_STATUSES: tuple[str, ...] = (
    "model_role_post_adoption_coverage_ready",
    "model_role_post_adoption_coverage_ready_with_warnings",
    "model_role_post_adoption_coverage_incomplete",
    "model_role_post_adoption_coverage_blocked",
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
    "worker_launch_allowed",
    "model_calls_allowed",
    "model_routing_enabled",
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

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "coverage analysis only",
    "deterministic/artifact input only",
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
    "writes post-adoption coverage artifacts only",
)

MODEL_ROLE_POST_ADOPTION_COVERAGE_GUARDRAIL_NOTE = (
    "Model Role Post-Adoption Coverage is report-only: it verifies whether the "
    "active advisory model-role catalog now resolves the MODEL.N3 role gaps "
    "after ADOPT.MODEL.1. It does not route tasks, call models, launch workers, "
    "create executable model bindings, run validation or benchmarks, apply "
    "patches, invoke MCP tools, contact networks, write databases, change "
    "route/auth behavior, enforce approval tokens, or grant automatic authority."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "ADOPT.MODEL.CLOSE",
    "title": "Model Catalog Adoption Branch Checkpoint",
    "reason": (
        "After post-adoption coverage verifies the active advisory catalog, "
        "freeze the report-only adoption branch before any future execution work."
    ),
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
    """Read a JSON input file and return findings instead of raising."""
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


def _role_safety_findings(roles: list[dict[str, Any]], catalog_data: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    advisory_failures: list[str] = []
    executable_failures: list[str] = []
    model_id_authority_hits: list[str] = []
    model_routing_hits: list[str] = []
    model_call_hits: list[str] = []
    worker_launch_hits: list[str] = []
    forbidden_authority_hits: list[str] = []

    for reason in _truthy_key_hits(catalog_data, MODEL_ROUTING_KEYS, "active catalog"):
        model_routing_hits.append(reason)
        blockers.append(reason)
    for reason in _truthy_key_hits(catalog_data, MODEL_CALL_KEYS, "active catalog"):
        model_call_hits.append(reason)
        blockers.append(reason)
    for reason in _truthy_key_hits(catalog_data, WORKER_LAUNCH_KEYS, "active catalog"):
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

    findings = {
        "advisory_only_failures": _unique(advisory_failures),
        "executable_binding_failures": _unique(executable_failures),
        "model_id_authority_hits": _unique(model_id_authority_hits),
        "model_routing_hits": _unique(model_routing_hits),
        "model_call_hits": _unique(model_call_hits),
        "worker_launch_hits": _unique(worker_launch_hits),
        "forbidden_authority_hits": _unique(forbidden_authority_hits),
    }
    return blockers, findings


def _previous_roles_from_receipt(adoption_receipt_data: dict[str, Any] | None) -> list[str]:
    if not isinstance(adoption_receipt_data, dict):
        return list(PRESERVED_ROLE_IDS)
    values = _strings(adoption_receipt_data.get("preserved_roles"))
    return values or list(PRESERVED_ROLE_IDS)


def _gap_roles(gap_plan_data: dict[str, Any] | None) -> list[str]:
    roles: list[str] = []
    if not isinstance(gap_plan_data, dict):
        return roles
    for row in _list_of_dicts(gap_plan_data.get("missing_role_plans")):
        role_id = str(row.get("suggested_role_id") or row.get("affected_role") or "").strip()
        if role_id:
            roles.append(role_id)
    return _ordered_unique(roles)


def _status(*, blockers: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blockers:
        return "model_role_post_adoption_coverage_blocked"
    if incomplete:
        return "model_role_post_adoption_coverage_incomplete"
    if warnings:
        return "model_role_post_adoption_coverage_ready_with_warnings"
    return "model_role_post_adoption_coverage_ready"


def build_model_role_post_adoption_coverage(
    *,
    active_catalog_path: str | Path | None,
    active_catalog_data: dict[str, Any] | None,
    adoption_receipt_path: str | Path | None,
    adoption_receipt_data: dict[str, Any] | None,
    gap_plan_path: str | Path | None = None,
    gap_plan_data: dict[str, Any] | None = None,
    readiness_path: str | Path | None = None,
    readiness_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
    input_incomplete: list[str] | None = None,
    input_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic ADOPT.MODEL.2 coverage recheck report."""
    blockers = list(input_blockers or [])
    incomplete = list(input_incomplete or [])
    warnings = list(input_warnings or [])
    blockers += _input_path_blockers(active_catalog_path, "active catalog", required=True)
    incomplete += _input_path_blockers(adoption_receipt_path, "adoption receipt", required=True)
    incomplete += _input_path_blockers(gap_plan_path, "gap plan", required=True)
    warnings += _input_path_blockers(readiness_path, "readiness", required=False)

    if active_catalog_data is None:
        active_catalog_data = {}
        blockers.append("active catalog is missing or malformed")
    if not isinstance(active_catalog_data, dict):
        active_catalog_data = {}
        blockers.append("active catalog must contain a JSON object")
    if active_catalog_data.get("report_kind") != MODEL_REGISTRY_REPORT_KIND:
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
    if adoption_receipt_data and adoption_receipt_data.get("report_kind") != ADOPTION_RECEIPT_REPORT_KIND:
        incomplete.append("adoption receipt report_kind must be model_role_catalog_adoption_receipt")
    adoption_status = str(adoption_receipt_data.get("adoption_status") or "")
    if adoption_receipt_data and adoption_status not in {
        "model_role_catalog_adoption_complete",
        "model_role_catalog_adoption_complete_with_warnings",
    }:
        incomplete.append("adoption receipt must show a complete ADOPT.MODEL.1 adoption")
    for warning in _strings(adoption_receipt_data.get("warnings")):
        warnings.append(f"adoption receipt warning: {warning}")
    for reason in _strings(adoption_receipt_data.get("blocked_reasons")):
        blockers.append(f"adoption receipt blocker: {reason}")

    if gap_plan_data is None:
        gap_plan_data = {}
        incomplete.append("gap plan is missing or malformed")
    if not isinstance(gap_plan_data, dict):
        gap_plan_data = {}
        incomplete.append("gap plan must contain a JSON object")
    if gap_plan_data and gap_plan_data.get("report_kind") != GAP_PLAN_REPORT_KIND:
        incomplete.append("gap plan report_kind must be model_role_gap_plan")
    for reason in _strings(gap_plan_data.get("blocked_reasons")):
        blockers.append(f"gap plan blocker: {reason}")

    if readiness_data is None:
        warnings.append("readiness artifact is missing or unavailable")
    elif not isinstance(readiness_data, dict):
        warnings.append("readiness artifact must contain a JSON object")
    elif readiness_data.get("report_kind") != READINESS_REPORT_KIND:
        warnings.append("readiness report_kind is not model_role_catalog_adoption_readiness")
    else:
        for warning in _strings(readiness_data.get("warnings")):
            warnings.append(f"readiness warning: {warning}")
        for reason in _strings(readiness_data.get("blocked_reasons")):
            blockers.append(f"readiness blocker: {reason}")

    previous_role_ids = _previous_roles_from_receipt(adoption_receipt_data)
    missing_previous_roles = [role_id for role_id in previous_role_ids if role_id not in active_role_set]
    for role_id in missing_previous_roles:
        blockers.append(f"active catalog loses previous required role: {role_id}")

    gap_role_ids = _gap_roles(gap_plan_data)
    expected_gap_set = set(ADDED_ROLE_IDS)
    gap_role_set = set(gap_role_ids)
    if gap_plan_data and not expected_gap_set <= gap_role_set:
        missing_gap_evidence = [role_id for role_id in ADDED_ROLE_IDS if role_id not in gap_role_set]
        incomplete.append(
            "coverage report cannot verify resolved gaps from gap plan: "
            + ", ".join(missing_gap_evidence)
        )

    added_roles_verified = all(role_id in active_role_set for role_id in ADDED_ROLE_IDS)
    preserved_roles_verified = all(role_id in active_role_set for role_id in previous_role_ids)
    resolved_gaps = [
        role_id for role_id in ADDED_ROLE_IDS if role_id in active_role_set and role_id in gap_role_set
    ]
    unresolved_gaps = [
        role_id for role_id in ADDED_ROLE_IDS if role_id not in active_role_set or role_id not in gap_role_set
    ]
    if gap_plan_data and unresolved_gaps and active_role_count >= EXPECTED_ROLE_COUNT:
        incomplete.append("coverage report cannot verify resolved gaps: " + ", ".join(unresolved_gaps))

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

    blockers = _unique(blockers)
    incomplete = _unique(incomplete)
    warnings = _unique(warnings)
    status = _status(blockers=blockers, incomplete=incomplete, warnings=warnings)

    safety_checks = {
        **safety_findings,
        "expected_added_roles": list(ADDED_ROLE_IDS),
        "expected_added_roles_present": added_roles_verified,
        "previous_roles_expected": previous_role_ids,
        "previous_roles_missing": missing_previous_roles,
        "previous_roles_preserved": preserved_roles_verified,
        "active_role_ids": active_role_ids,
        "gap_plan_roles": gap_role_ids,
        "passed": not blockers,
    }

    return {
        "report_kind": REPORT_KIND,
        "report_id": "model-role-post-adoption-coverage",
        "source_active_catalog_path": str(active_catalog_path or ""),
        "source_adoption_receipt_path": str(adoption_receipt_path or ""),
        "source_gap_plan_path": str(gap_plan_path or ""),
        "source_readiness_path": str(readiness_path or ""),
        "post_adoption_coverage_status": status,
        "active_role_count": active_role_count,
        "expected_role_count": EXPECTED_ROLE_COUNT,
        "resolved_gaps": resolved_gaps,
        "unresolved_gaps": unresolved_gaps,
        "added_roles_verified": added_roles_verified,
        "preserved_roles_verified": preserved_roles_verified,
        "advisory_only_confirmed": advisory_only_confirmed,
        "executable_binding_allowed_confirmed_false": executable_binding_allowed_confirmed_false,
        "model_routing_enabled_confirmed_false": model_routing_enabled_confirmed_false,
        "model_calls_allowed_confirmed_false": model_calls_allowed_confirmed_false,
        "worker_launch_allowed_confirmed_false": worker_launch_allowed_confirmed_false,
        "model_ids_metadata_only_confirmed": model_ids_metadata_only_confirmed,
        "safety_findings": safety_checks,
        "warnings": warnings,
        "incomplete_reasons": incomplete,
        "blocked_reasons": blockers,
        "guardrail_note": MODEL_ROLE_POST_ADOPTION_COVERAGE_GUARDRAIL_NOTE,
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
        "post_adoption_coverage_statuses": list(POST_ADOPTION_COVERAGE_STATUSES),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_model_role_post_adoption_coverage_markdown(report: dict[str, Any]) -> str:
    """Render an ADOPT.MODEL.2 post-adoption coverage report as Markdown."""
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    safety = report.get("safety_findings") if isinstance(report.get("safety_findings"), dict) else {}
    lines: list[str] = [
        "# Model Role Post-Adoption Role Coverage",
        "",
        f"> {report.get('guardrail_note', MODEL_ROLE_POST_ADOPTION_COVERAGE_GUARDRAIL_NOTE)}",
        "",
        "_Report only: ADOPT.MODEL.2 verifies advisory catalog coverage after adoption. It routes nothing, calls no models, launches no workers, and creates no executable bindings._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Coverage status:** `{_md(report.get('post_adoption_coverage_status', ''))}`",
        f"- **Active role count:** {report.get('active_role_count', 0)}",
        f"- **Expected role count:** {report.get('expected_role_count', 0)}",
        f"- **Resolved gaps:** {len(report.get('resolved_gaps') or [])}",
        f"- **Unresolved gaps:** {len(report.get('unresolved_gaps') or [])}",
        f"- **Blocked reasons:** {len(report.get('blocked_reasons') or [])}",
        "",
        "## Source Artifacts",
        "",
        f"- **Active catalog:** `{_md(report.get('source_active_catalog_path', ''))}`",
        f"- **Adoption receipt:** `{_md(report.get('source_adoption_receipt_path', ''))}`",
        f"- **Gap plan:** `{_md(report.get('source_gap_plan_path', ''))}`",
        f"- **Readiness:** `{_md(report.get('source_readiness_path', ''))}`",
        "",
        "## Resolved Gaps",
        "",
    ]
    _render_list(lines, list(report.get("resolved_gaps") or []), code=True)
    lines += ["## Unresolved Gaps", ""]
    _render_list(lines, list(report.get("unresolved_gaps") or []), code=True)
    lines += [
        "## Role Verification",
        "",
        f"- `added_roles_verified`: {str(bool(report.get('added_roles_verified'))).lower()}",
        f"- `preserved_roles_verified`: {str(bool(report.get('preserved_roles_verified'))).lower()}",
        f"- `expected_added_roles_present`: {str(bool(safety.get('expected_added_roles_present'))).lower()}",
        f"- `previous_roles_preserved`: {str(bool(safety.get('previous_roles_preserved'))).lower()}",
        "",
        "## Safety Confirmations",
        "",
    ]
    for key in (
        "advisory_only_confirmed",
        "executable_binding_allowed_confirmed_false",
        "model_routing_enabled_confirmed_false",
        "model_calls_allowed_confirmed_false",
        "worker_launch_allowed_confirmed_false",
        "model_ids_metadata_only_confirmed",
    ):
        lines.append(f"- `{_md(key)}`: {str(bool(report.get(key))).lower()}")
    for key in sorted(safety):
        if key.endswith("_hits") and safety[key]:
            lines.append(f"- **{_md(key)}:** {_md(safety[key])}")
    lines += ["", "## Warnings", ""]
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
        "",
    ]
    return "\n".join(lines)


def write_model_role_post_adoption_coverage(
    *,
    active_catalog_path: str | Path,
    adoption_receipt_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    gap_plan_path: str | Path | None = None,
    readiness_path: str | Path | None = None,
    active_catalog_data: dict[str, Any] | None = None,
    adoption_receipt_data: dict[str, Any] | None = None,
    gap_plan_data: dict[str, Any] | None = None,
    readiness_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
    input_incomplete: list[str] | None = None,
    input_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build and write ADOPT.MODEL.2 JSON plus Markdown artifacts."""
    blockers = list(input_blockers or [])
    incomplete = list(input_incomplete or [])
    warnings = list(input_warnings or [])
    if active_catalog_data is None:
        active_catalog_data, read_findings = read_json_input(active_catalog_path, "active catalog", required=True)
        blockers += read_findings
    if adoption_receipt_data is None:
        adoption_receipt_data, read_findings = read_json_input(adoption_receipt_path, "adoption receipt", required=True)
        incomplete += read_findings
    if gap_plan_path is not None and gap_plan_data is None:
        gap_plan_data, read_findings = read_json_input(gap_plan_path, "gap plan", required=True)
        incomplete += read_findings
    if readiness_path is not None and readiness_data is None:
        readiness_data, read_findings = read_json_input(readiness_path, "readiness", required=False)
        warnings += read_findings

    report = build_model_role_post_adoption_coverage(
        active_catalog_path=active_catalog_path,
        active_catalog_data=active_catalog_data,
        adoption_receipt_path=adoption_receipt_path,
        adoption_receipt_data=adoption_receipt_data,
        gap_plan_path=gap_plan_path,
        gap_plan_data=gap_plan_data,
        readiness_path=readiness_path,
        readiness_data=readiness_data,
        input_blockers=blockers,
        input_incomplete=incomplete,
        input_warnings=warnings,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_model_role_post_adoption_coverage_markdown(report), encoding="utf-8")
    return {
        "ok": report.get("post_adoption_coverage_status")
        in {
            "model_role_post_adoption_coverage_ready",
            "model_role_post_adoption_coverage_ready_with_warnings",
        },
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
