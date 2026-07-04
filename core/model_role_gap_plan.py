"""MODEL.N3 - Model Role Gap Plan (report-only).

Reads a MODEL.N2 model role coverage report and produces a deterministic manual
plan for improving the MODEL.N1 tower card catalog. This module writes JSON and
Markdown artifacts only; it does not edit the registry, route tasks, call
models, launch workers, bind executable model IDs, run validation, run
benchmarks, apply patches, invoke MCP tools, contact networks, write databases,
or mutate source artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "model_role_gap_plan"
JSON_NAME = "model_role_gap_plan.json"
MD_NAME = "model_role_gap_plan.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "model_role_registry" / "model_role_gap_plan"

COVERAGE_REPORT_KIND = "model_role_coverage_report"
MODEL_REGISTRY_REPORT_KIND = "model_role_registry"

GAP_PLAN_STATUSES: tuple[str, ...] = (
    "gap_plan_ready",
    "gap_plan_ready_with_warnings",
    "gap_plan_incomplete",
    "gap_plan_blocked",
)

COVERAGE_STATUSES: tuple[str, ...] = (
    "role_coverage_ready",
    "role_coverage_ready_with_warnings",
    "role_coverage_incomplete",
    "role_coverage_blocked",
)

OPTIONAL_ROLE_TARGETS: tuple[str, ...] = (
    "ui_reviewer",
    "test_designer",
    "documentation_reviewer",
)

TIER_CATEGORIES: dict[str, str] = {
    "risk_level": "unknown_risk_level",
    "cost_tier": "unknown_cost_tier",
    "latency_tier": "unknown_latency_tier",
    "context_tier": "unknown_context_tier",
    "reliability_tier": "unknown_reliability_tier",
}

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

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "model_call_performed",
    "model_routing_performed",
    "worker_launch_performed",
    "executable_model_binding_created",
    "commander_role_binding_created",
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
    "model_registry_mutated",
    "commander_artifacts_mutated",
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
    "do not mutate Commander assignments automatically",
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "gap planning only",
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
    "no mutation of source artifacts",
    "no automatic registry update",
    "writes gap plan artifacts only",
)

MODEL_ROLE_GAP_PLAN_GUARDRAIL_NOTE = (
    "Model Role Gap Plan is report-only: it reads MODEL.N2 coverage evidence "
    "and recommends manual MODEL.N1 tower card improvements. It does not edit "
    "the registry, route tasks, call models, launch workers, bind executable "
    "model IDs, run validation or benchmarks, apply patches, invoke MCP tools, "
    "contact networks, write databases, mutate Commander artifacts, or perform "
    "automatic assignment."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "MODEL.N4",
    "title": "Model Role Catalog Update Proposal",
    "reason": (
        "After a manual gap plan exists, prepare a proposed MODEL.N1 catalog "
        "update artifact without applying it automatically."
    ),
}

ROLE_SUGGESTIONS: dict[str, dict[str, Any]] = {
    "fast_scout": {
        "display_name": "Fast Scout",
        "role_kind": "scout",
        "best_for": ["quick triage", "broad summary", "shallow planning"],
        "not_for": ["final patch authority", "risky refactors"],
        "fallback_roles": ["local_fallback"],
        "human_review_required": False,
    },
    "planner": {
        "display_name": "Planner",
        "role_kind": "planner",
        "best_for": ["decomposition", "scope shaping", "preflight reasoning"],
        "not_for": ["direct code mutation", "worker launch"],
        "fallback_roles": ["fast_scout"],
        "human_review_required": False,
    },
    "implementer": {
        "display_name": "Patch Implementer",
        "role_kind": "implementer",
        "best_for": ["patch proposal preparation"],
        "not_for": ["patch apply", "final approval", "hidden mutation"],
        "fallback_roles": ["planner"],
        "human_review_required": True,
    },
    "patch_implementer": {
        "display_name": "Patch Implementer",
        "role_kind": "implementer",
        "best_for": ["patch proposal preparation"],
        "not_for": ["patch apply", "final approval", "hidden mutation"],
        "fallback_roles": ["planner"],
        "human_review_required": True,
    },
    "reviewer": {
        "display_name": "Code Reviewer",
        "role_kind": "reviewer",
        "best_for": ["critique", "bug finding", "consistency review"],
        "not_for": ["final apply authority", "automatic merge"],
        "fallback_roles": ["evidence_checker"],
        "human_review_required": True,
    },
    "code_reviewer": {
        "display_name": "Code Reviewer",
        "role_kind": "reviewer",
        "best_for": ["critique", "bug finding", "consistency review"],
        "not_for": ["final apply authority", "automatic merge"],
        "fallback_roles": ["evidence_checker"],
        "human_review_required": True,
    },
    "evidence_checker": {
        "display_name": "Evidence Checker",
        "role_kind": "evidence_checker",
        "best_for": ["validation claim matching", "missing evidence detection"],
        "not_for": ["running validation automatically", "benchmark execution"],
        "fallback_roles": ["fast_scout"],
        "human_review_required": False,
    },
    "risk_auditor": {
        "display_name": "Risk Auditor",
        "role_kind": "risk_auditor",
        "best_for": ["file scope safety", "mutation risk", "approval boundaries"],
        "not_for": ["execution", "approval authority"],
        "fallback_roles": ["code_reviewer", "planner"],
        "human_review_required": True,
    },
    "ui_reviewer": {
        "display_name": "UI Reviewer",
        "role_kind": "reviewer",
        "best_for": ["layout review", "visual affordance review", "responsive UI critique"],
        "not_for": ["patch apply", "final approval", "automatic UI mutation"],
        "fallback_roles": ["code_reviewer", "planner"],
        "human_review_required": True,
    },
    "test_designer": {
        "display_name": "Test Designer",
        "role_kind": "reviewer",
        "best_for": ["test strategy", "coverage gap review", "fixture design"],
        "not_for": ["running validation automatically", "final approval", "patch apply"],
        "fallback_roles": ["evidence_checker", "code_reviewer"],
        "human_review_required": True,
    },
    "documentation_reviewer": {
        "display_name": "Documentation Reviewer",
        "role_kind": "reviewer",
        "best_for": ["docs clarity review", "release note review", "operator guidance"],
        "not_for": ["source mutation", "automatic publishing", "final approval"],
        "fallback_roles": ["code_reviewer", "planner"],
        "human_review_required": True,
    },
    "local_fallback": {
        "display_name": "Local Fallback",
        "role_kind": "local_offline",
        "best_for": ["small offline summaries", "cheap fallback", "no-network mode"],
        "not_for": ["large context", "final authority"],
        "fallback_roles": [],
        "human_review_required": False,
    },
}

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

IMPLEMENTER_FORBIDDEN_TASK_TYPES: tuple[str, ...] = (
    "patch_apply",
    "final_approval",
    "direct_mutation",
    "hidden_writes",
)

DEFAULT_FORBIDDEN_TASK_TYPES: tuple[str, ...] = (
    "model_call",
    "model_routing",
    "worker_launch",
    "patch_apply",
    "auto_apply",
    "auto_merge",
    "final_authority",
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


def _role_id(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("role_id") or value.get("model_role_id") or value.get("affected_role") or "").strip()
    return ""


def _display_name(role_id: str) -> str:
    suggestion = ROLE_SUGGESTIONS.get(role_id, {})
    if suggestion.get("display_name"):
        return str(suggestion["display_name"])
    return " ".join(piece.capitalize() for piece in role_id.split("_") if piece) or "Unnamed Role"


def _role_kind(role_id: str, existing: dict[str, Any] | None = None) -> str:
    if existing and str(existing.get("role_kind") or "").strip():
        return str(existing.get("role_kind") or "").strip()
    return str(ROLE_SUGGESTIONS.get(role_id, {}).get("role_kind") or "reviewer")


def _suggested_best_for(role_id: str, existing: dict[str, Any] | None = None) -> list[str]:
    values = _strings((existing or {}).get("best_for"))
    if values:
        return values
    return list(ROLE_SUGGESTIONS.get(role_id, {}).get("best_for") or ["manual advisory review"])


def _suggested_not_for(role_id: str, existing: dict[str, Any] | None = None) -> list[str]:
    values = _strings((existing or {}).get("not_for"))
    if values:
        return values
    return list(ROLE_SUGGESTIONS.get(role_id, {}).get("not_for") or ["execution authority", "automatic mutation"])


def _suggested_fallbacks(role_id: str, existing: dict[str, Any] | None = None) -> list[str]:
    values = _strings((existing or {}).get("fallback_roles"))
    if values:
        return values
    return list(ROLE_SUGGESTIONS.get(role_id, {}).get("fallback_roles") or [])


def _suggested_forbidden_task_types(role_id: str, existing: dict[str, Any] | None = None) -> list[str]:
    values = _strings((existing or {}).get("forbidden_task_types"))
    if values:
        return values
    if _role_kind(role_id, existing) == "implementer":
        return list(IMPLEMENTER_FORBIDDEN_TASK_TYPES)
    return list(DEFAULT_FORBIDDEN_TASK_TYPES)


def _human_review_required(role_id: str, existing: dict[str, Any] | None = None) -> bool:
    if existing and "human_review_required" in existing:
        return bool(existing.get("human_review_required"))
    suggestion = ROLE_SUGGESTIONS.get(role_id, {})
    if "human_review_required" in suggestion:
        return bool(suggestion["human_review_required"])
    return _role_kind(role_id, existing) in {"implementer", "reviewer", "risk_auditor"}


def _plan_item(
    *,
    category: str,
    severity: str,
    affected_role: str,
    reason: str,
    existing: dict[str, Any] | None = None,
    suggested_role_id: str | None = None,
    suggested_fallback_roles: list[str] | None = None,
    expected_status_after_fix: str = "model_roles_ready_with_warnings",
) -> dict[str, Any]:
    role_id = str(suggested_role_id or affected_role).strip()
    fallbacks = list(suggested_fallback_roles) if suggested_fallback_roles is not None else _suggested_fallbacks(role_id, existing)
    return {
        "gap_id": f"{category}:{affected_role}",
        "category": category,
        "severity": severity,
        "affected_role": affected_role,
        "suggested_role_id": role_id,
        "suggested_display_name": str((existing or {}).get("display_name") or _display_name(role_id)),
        "suggested_role_kind": _role_kind(role_id, existing),
        "reason": reason,
        "suggested_best_for": _suggested_best_for(role_id, existing),
        "suggested_not_for": _suggested_not_for(role_id, existing),
        "suggested_forbidden_task_types": _suggested_forbidden_task_types(role_id, existing),
        "suggested_fallback_roles": fallbacks,
        "human_review_required": _human_review_required(role_id, existing),
        "advisory_only": True,
        "executable_binding_allowed": False,
        "expected_status_after_fix": expected_status_after_fix,
    }


def _append_unique(rows: list[dict[str, Any]], item: dict[str, Any]) -> None:
    key = (
        item.get("gap_id"),
        item.get("category"),
        item.get("affected_role"),
        item.get("reason"),
    )
    for row in rows:
        if (row.get("gap_id"), row.get("category"), row.get("affected_role"), row.get("reason")) == key:
            return
    rows.append(item)


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _role_details(
    coverage_data: dict[str, Any],
    model_registry_data: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    if isinstance(model_registry_data, dict):
        for role in _list_of_dicts(model_registry_data.get("roles")):
            rid = _role_id(role)
            if rid:
                by_id[rid] = dict(role)
    for role in _list_of_dicts(coverage_data.get("available_model_role_details")):
        rid = _role_id(role)
        if not rid:
            continue
        merged = dict(by_id.get(rid, {}))
        merged.update(role)
        by_id[rid] = merged
    return [by_id[key] for key in sorted(by_id)]


def _available_role_ids(coverage_data: dict[str, Any], role_details: list[dict[str, Any]]) -> set[str]:
    values = set(_strings(coverage_data.get("available_model_roles")))
    values.update(_role_id(role) for role in role_details if _role_id(role))
    return values


def _required_roles(coverage_data: dict[str, Any]) -> set[str]:
    required: set[str] = set()
    for row in _list_of_dicts(coverage_data.get("required_commander_roles")):
        role = str(row.get("source_role") or row.get("canonical_role_id") or row.get("model_role_id") or "").strip()
        if role:
            required.add(role)
    for row in _list_of_dicts(coverage_data.get("matched_roles")):
        role = str(row.get("canonical_role_id") or row.get("model_role_id") or "").strip()
        if role:
            required.add(role)
    required.update(_strings(coverage_data.get("missing_roles")))
    return required


def _scan_forbidden_claims(value: Any, label: str, path: str = "") -> list[str]:
    blockers: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            current = f"{path}.{key_text}" if path else key_text
            low_key = key_text.lower()
            if low_key == "executable_binding_allowed" and item is True:
                blockers.append(f"{label} enables executable_binding_allowed at {current}")
            if low_key == "advisory_only" and item is False:
                blockers.append(f"{label} sets advisory_only false at {current}")
            if low_key in FORBIDDEN_AUTHORITY_FLAGS and item is True:
                blockers.append(f"{label} enables forbidden authority flag at {current}: {low_key}")
            if low_key.endswith("_performed") and item is True:
                blockers.append(f"{label} reports forbidden guardrail action at {current}")
            if any(fragment in low_key for fragment in AUTHORITY_KEY_FRAGMENTS) and item is True:
                blockers.append(f"{label} claims executable authority at {current}")
            if low_key in MODEL_ID_AUTHORITY_KEYS and str(item or "").strip():
                blockers.append(f"{label} defines model ID authority at {current}")
            blockers += _scan_forbidden_claims(item, label, current)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            current = f"{path}[{index}]" if path else f"[{index}]"
            blockers += _scan_forbidden_claims(item, label, current)
    return blockers


def _blocked_hits(coverage_data: dict[str, Any]) -> list[str]:
    checks = coverage_data.get("forbidden_authority_checks")
    if not isinstance(checks, dict):
        return []
    return _strings(checks.get("blocked_hits"))


def _fallback_suggestion(role_id: str) -> list[str]:
    if role_id == "risk_auditor":
        return ["code_reviewer", "planner"]
    if role_id == "patch_implementer":
        return ["planner", "code_reviewer"]
    if role_id == "code_reviewer":
        return ["evidence_checker", "planner"]
    if role_id == "evidence_checker":
        return ["fast_scout", "code_reviewer"]
    if role_id == "planner":
        return ["fast_scout"]
    return _suggested_fallbacks(role_id)


def _is_weak_evidence(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return not text or text in {"unknown", "none", "n/a", "tbd"}


def _forbidden_task_types_are_weak(role: dict[str, Any]) -> bool:
    forbidden = {item.lower() for item in _strings(role.get("forbidden_task_types"))}
    if not forbidden:
        return True
    role_kind = str(role.get("role_kind") or "").strip()
    if role_kind == "implementer":
        needed = {"patch_apply", "final_approval", "direct_mutation", "hidden_writes"}
        return not needed.intersection(forbidden)
    return False


def _model_id_metadata_rows(role_details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role in role_details:
        role_id = _role_id(role)
        model_ids = _strings(role.get("model_ids"))
        if not role_id or not model_ids:
            continue
        _append_unique(
            rows,
            _plan_item(
                category="model_id_authority_risk",
                severity="info",
                affected_role=role_id,
                existing=role,
                reason=(
                    "MODEL.N1 model_ids are descriptive metadata only; keep them out of "
                    "routing, execution, approval, and authority decisions."
                ),
                expected_status_after_fix="model_roles_ready",
            ),
        )
    return rows


def _has_useful_data(coverage_data: dict[str, Any], role_details: list[dict[str, Any]]) -> bool:
    return any(
        [
            _strings(coverage_data.get("missing_roles")),
            _list_of_dicts(coverage_data.get("required_commander_roles")),
            role_details,
            _list_of_dicts(coverage_data.get("fallback_coverage")),
            _strings(coverage_data.get("warnings")),
        ]
    )


def _status(
    *,
    blockers: list[str],
    warnings: list[str],
    has_plans: bool,
    coverage_status: str,
    useful_data: bool,
) -> str:
    if blockers:
        return "gap_plan_blocked"
    if coverage_status == "role_coverage_incomplete" and not useful_data:
        return "gap_plan_incomplete"
    if warnings or has_plans:
        return "gap_plan_ready_with_warnings"
    return "gap_plan_ready"


def build_model_role_gap_plan(
    *,
    coverage_path: str | Path | None,
    coverage_data: dict[str, Any] | None = None,
    model_registry_path: str | Path | None = None,
    model_registry_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic MODEL.N3 gap plan from loaded artifacts."""
    blockers = list(input_blockers or [])
    blockers += _input_path_blockers(coverage_path, "coverage", required=True)
    blockers += _input_path_blockers(model_registry_path, "model registry", required=False)
    warnings: list[str] = []

    if coverage_data is None:
        coverage_data = {}
        blockers.append("coverage report is missing or malformed")
    if not isinstance(coverage_data, dict):
        coverage_data = {}
        blockers.append("coverage report must contain a JSON object")
    if model_registry_data is not None and not isinstance(model_registry_data, dict):
        model_registry_data = {}
        blockers.append("model registry must contain a JSON object")

    if coverage_data.get("report_kind") != COVERAGE_REPORT_KIND:
        blockers.append("coverage report_kind must be model_role_coverage_report")
    coverage_status = str(coverage_data.get("coverage_status") or "")
    if coverage_status not in COVERAGE_STATUSES:
        blockers.append("coverage_status must be a MODEL.N2 role coverage status")
    if coverage_status == "role_coverage_blocked":
        blockers.append("coverage report is blocked; resolve MODEL.N2 blockers before planning catalog updates")
    for reason in _strings(coverage_data.get("blocked_reasons")):
        if coverage_status == "role_coverage_blocked":
            blockers.append(f"coverage blocker: {reason}")

    if model_registry_data is not None and model_registry_data.get("report_kind") != MODEL_REGISTRY_REPORT_KIND:
        blockers.append("model registry report_kind must be model_role_registry")

    role_details = _role_details(coverage_data, model_registry_data)
    available_roles = _available_role_ids(coverage_data, role_details)
    required_roles = _required_roles(coverage_data)

    blockers += _scan_forbidden_claims(coverage_data, "coverage")
    if model_registry_data is not None:
        blockers += _scan_forbidden_claims(model_registry_data, "model registry")
    for hit in _blocked_hits(coverage_data):
        blockers.append(f"coverage forbidden authority hit: {hit}")

    missing_role_plans: list[dict[str, Any]] = []
    weak_role_plans: list[dict[str, Any]] = []
    risky_role_plans: list[dict[str, Any]] = []
    fallback_improvement_plans: list[dict[str, Any]] = []
    metadata_improvement_plans: list[dict[str, Any]] = []

    for role_id in _strings(coverage_data.get("missing_roles")):
        _append_unique(
            missing_role_plans,
            _plan_item(
                category="missing_required_role",
                severity="important",
                affected_role=role_id,
                suggested_role_id=role_id,
                reason=f"MODEL.N2 found required Commander advisory role {role_id} without a MODEL.N1 tower card.",
            ),
        )

    for role_id in OPTIONAL_ROLE_TARGETS:
        if role_id not in available_roles and role_id not in _strings(coverage_data.get("missing_roles")):
            warnings.append(f"optional Commander role {role_id} is not present in MODEL.N1 tower cards")
            _append_unique(
                missing_role_plans,
                _plan_item(
                    category="missing_optional_role",
                    severity="warning",
                    affected_role=role_id,
                    suggested_role_id=role_id,
                    reason=(
                        f"MODEL.N2 treats {role_id} as an optional advisory coverage target; "
                        "add it manually if Commander work needs that review lane."
                    ),
                ),
            )

    role_by_id = {_role_id(role): role for role in role_details if _role_id(role)}
    for row in _list_of_dicts(coverage_data.get("fallback_coverage")):
        role_id = str(row.get("role_id") or "").strip()
        status = str(row.get("coverage_status") or "").strip()
        unknown = _strings(row.get("unknown_fallback_roles"))
        if not role_id:
            continue
        if status in {"weak_fallback", "unknown_fallback"} or unknown:
            reason = (
                f"MODEL.N2 reports {status or 'fallback gap'} for {role_id}."
                if not unknown
                else f"MODEL.N2 reports unknown fallback roles for {role_id}: {', '.join(unknown)}."
            )
            _append_unique(
                fallback_improvement_plans,
                _plan_item(
                    category="weak_fallback",
                    severity="warning",
                    affected_role=role_id,
                    existing=role_by_id.get(role_id),
                    suggested_fallback_roles=_fallback_suggestion(role_id),
                    reason=reason,
                ),
            )

    for role in role_details:
        role_id = _role_id(role)
        if not role_id:
            continue
        for field, category in TIER_CATEGORIES.items():
            if str(role.get(field) or "unknown").strip() == "unknown":
                _append_unique(
                    metadata_improvement_plans,
                    _plan_item(
                        category=category,
                        severity="important" if field == "risk_level" else "warning",
                        affected_role=role_id,
                        existing=role,
                        reason=f"MODEL.N1 tower card {role_id} has unknown {field}; assign a concrete tier manually.",
                    ),
                )
        if _is_weak_evidence(role.get("evidence_expectation")):
            _append_unique(
                weak_role_plans,
                _plan_item(
                    category="weak_evidence_expectation",
                    severity="warning",
                    affected_role=role_id,
                    existing=role,
                    reason=f"MODEL.N1 tower card {role_id} lacks a concrete evidence expectation.",
                ),
            )
        if _forbidden_task_types_are_weak(role):
            _append_unique(
                weak_role_plans,
                _plan_item(
                    category="weak_forbidden_task_types",
                    severity="important" if str(role.get("role_kind") or "") == "implementer" else "warning",
                    affected_role=role_id,
                    existing=role,
                    suggested_fallback_roles=_suggested_fallbacks(role_id, role),
                    reason=(
                        f"MODEL.N1 tower card {role_id} should explicitly forbid patch apply, "
                        "approval, direct mutation, and hidden writes where applicable."
                    ),
                ),
            )

    for row in _list_of_dicts(coverage_data.get("overpowered_roles")):
        role_id = str(row.get("role_id") or row.get("affected_role") or "unknown_role").strip()
        reason = str(row.get("reason") or "MODEL.N2 reported this role as overpowered.").strip()
        blockers.append(f"overpowered role {role_id}: {reason}")
        _append_unique(
            risky_role_plans,
            _plan_item(
                category="overpowered_role",
                severity="blocker",
                affected_role=role_id,
                existing=role_by_id.get(role_id),
                reason=reason,
                expected_status_after_fix="model_roles_ready",
            ),
        )

    for reason in blockers:
        if "claims executable authority" in reason or "authority" in reason:
            role_id = "unknown_role"
            for known in role_by_id:
                if known and known in reason:
                    role_id = known
                    break
            _append_unique(
                risky_role_plans,
                _plan_item(
                    category="unsafe_authority_claim",
                    severity="blocker",
                    affected_role=role_id,
                    existing=role_by_id.get(role_id),
                    reason=reason,
                    expected_status_after_fix="model_roles_ready",
                ),
            )

    for item in _model_id_metadata_rows(role_details):
        _append_unique(metadata_improvement_plans, item)

    for row in _list_of_dicts(coverage_data.get("matched_roles")):
        method = str(row.get("match_method") or "")
        source_role = str(row.get("source_role") or "")
        model_role = str(row.get("model_role_id") or row.get("canonical_role_id") or "")
        if method == "unmatched" or method.startswith("missing_"):
            _append_unique(
                weak_role_plans,
                _plan_item(
                    category="commander_role_unmapped",
                    severity="important",
                    affected_role=source_role or model_role or "unknown_role",
                    suggested_role_id=model_role or source_role,
                    reason=f"Commander role {source_role or model_role} did not map cleanly to a MODEL.N1 tower card.",
                ),
            )

    warnings += _strings(coverage_data.get("warnings"))
    warnings = _unique(warnings)
    blockers = _unique(blockers)
    useful_data = _has_useful_data(coverage_data, role_details)
    has_plans = any(
        [
            missing_role_plans,
            weak_role_plans,
            risky_role_plans,
            fallback_improvement_plans,
            metadata_improvement_plans,
        ]
    )
    gap_status = _status(
        blockers=blockers,
        warnings=warnings,
        has_plans=has_plans,
        coverage_status=coverage_status,
        useful_data=useful_data,
    )

    checklist: list[str] = []
    for group in (
        missing_role_plans,
        weak_role_plans,
        risky_role_plans,
        fallback_improvement_plans,
        metadata_improvement_plans,
    ):
        for item in group:
            role_id = str(item.get("suggested_role_id") or item.get("affected_role") or "")
            category = str(item.get("category") or "")
            checklist.append(f"Review {category} for {role_id}; update MODEL.N1 manually and keep advisory_only true.")
    if not checklist:
        checklist.append("No manual MODEL.N1 catalog changes are required from the supplied coverage evidence.")
    checklist.append("Confirm all model_ids remain descriptive metadata only and never become routing or execution authority.")
    checklist.append("Re-run MODEL.N1 and MODEL.N2 reports after any manual catalog proposal is reviewed.")

    source_registry_path = str(model_registry_path or coverage_data.get("source_model_registry_path") or "")
    return {
        "report_kind": REPORT_KIND,
        "plan_id": "model-role-gap-plan",
        "guardrail_note": MODEL_ROLE_GAP_PLAN_GUARDRAIL_NOTE,
        "source_coverage_path": str(coverage_path or ""),
        "source_model_registry_path": source_registry_path,
        "source_coverage": {
            "path": str(coverage_path or ""),
            "report_kind": coverage_data.get("report_kind", ""),
            "coverage_status": coverage_status,
            "loaded": bool(coverage_data),
        },
        "source_model_registry": {
            "path": source_registry_path,
            "report_kind": (model_registry_data or {}).get("report_kind", "") if isinstance(model_registry_data, dict) else "",
            "validation_status": (model_registry_data or {}).get("validation_status", "") if isinstance(model_registry_data, dict) else "",
            "loaded": bool(model_registry_data),
        },
        "gap_plan_status": gap_status,
        "missing_role_plans": missing_role_plans,
        "weak_role_plans": weak_role_plans,
        "risky_role_plans": risky_role_plans,
        "fallback_improvement_plans": fallback_improvement_plans,
        "metadata_improvement_plans": metadata_improvement_plans,
        "forbidden_changes": list(FORBIDDEN_CHANGES),
        "manual_update_checklist": _unique(checklist),
        "warnings": warnings,
        "blocked_reasons": blockers,
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
        "gap_plan_statuses": list(GAP_PLAN_STATUSES),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def _render_plan_table(lines: list[str], rows: list[dict[str, Any]]) -> None:
    if not rows:
        lines.append("_None._")
        lines.append("")
        return
    lines += [
        "| Gap | Category | Severity | Suggested role | Reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {gap} | {category} | {severity} | {role} | {reason} |".format(
                gap=_md(row.get("gap_id", "")),
                category=_md(row.get("category", "")),
                severity=_md(row.get("severity", "")),
                role=_md(row.get("suggested_role_id", "")),
                reason=_md(row.get("reason", "")),
            )
        )
    lines.append("")


def render_model_role_gap_plan_markdown(report: dict[str, Any]) -> str:
    """Render a MODEL.N3 model role gap plan as Markdown."""
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    source = report.get("source_coverage") if isinstance(report.get("source_coverage"), dict) else {}
    source_registry = report.get("source_model_registry") if isinstance(report.get("source_model_registry"), dict) else {}
    lines: list[str] = [
        "# Model Role Gap Plan",
        "",
        f"> {report.get('guardrail_note', MODEL_ROLE_GAP_PLAN_GUARDRAIL_NOTE)}",
        "",
        "_Report only: MODEL.N3 recommends manual tower-card improvements. It does not update MODEL.N1 automatically._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Gap plan status:** `{_md(report.get('gap_plan_status', ''))}`",
        f"- **Missing role plans:** {len(report.get('missing_role_plans') or [])}",
        f"- **Weak role plans:** {len(report.get('weak_role_plans') or [])}",
        f"- **Risky role plans:** {len(report.get('risky_role_plans') or [])}",
        f"- **Fallback improvements:** {len(report.get('fallback_improvement_plans') or [])}",
        f"- **Metadata improvements:** {len(report.get('metadata_improvement_plans') or [])}",
        f"- **Blocked reasons:** {len(report.get('blocked_reasons') or [])}",
        "",
        "## Source Coverage",
        "",
        f"- **Coverage path:** `{_md(source.get('path', report.get('source_coverage_path', '')))}`",
        f"- **Coverage kind:** `{_md(source.get('report_kind', ''))}`",
        f"- **Coverage status:** `{_md(source.get('coverage_status', ''))}`",
        f"- **Model registry path:** `{_md(source_registry.get('path', report.get('source_model_registry_path', '')))}`",
        "",
        "## Missing Role Plans",
        "",
    ]
    _render_plan_table(lines, list(report.get("missing_role_plans") or []))
    lines += ["## Weak Role Plans", ""]
    _render_plan_table(lines, list(report.get("weak_role_plans") or []))
    lines += ["## Risky Role Plans", ""]
    _render_plan_table(lines, list(report.get("risky_role_plans") or []))
    lines += ["## Fallback Improvements", ""]
    _render_plan_table(lines, list(report.get("fallback_improvement_plans") or []))
    lines += ["## Metadata Improvements", ""]
    _render_plan_table(lines, list(report.get("metadata_improvement_plans") or []))
    lines += ["## Forbidden Changes", ""]
    _render_list(lines, list(report.get("forbidden_changes") or []))
    lines += ["## Manual Update Checklist", ""]
    _render_list(lines, list(report.get("manual_update_checklist") or []))
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


def write_model_role_gap_plan(
    *,
    coverage_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    model_registry_path: str | Path | None = None,
    coverage_data: dict[str, Any] | None = None,
    model_registry_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build and write MODEL.N3 JSON + Markdown gap plan artifacts."""
    blockers = list(input_blockers or [])
    if coverage_data is None and not blockers:
        coverage_data, read_blockers = read_json_input(coverage_path, "coverage", required=True)
        blockers += read_blockers
    if model_registry_path is not None and model_registry_data is None and not blockers:
        model_registry_data, read_blockers = read_json_input(model_registry_path, "model registry")
        blockers += read_blockers
    report = build_model_role_gap_plan(
        coverage_path=coverage_path,
        coverage_data=coverage_data,
        model_registry_path=model_registry_path,
        model_registry_data=model_registry_data,
        input_blockers=blockers,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_model_role_gap_plan_markdown(report), encoding="utf-8")
    return {
        "ok": report.get("gap_plan_status") != "gap_plan_blocked",
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
