"""MODEL.CLOSE - Model Role Planning Checkpoint (report-only).

Reads the MODEL.N1-MODEL.N7 artifact chain and writes a deterministic checkpoint
report that freezes the advisory model-role planning branch. MODEL.CLOSE never
adopts the proposed catalog, replaces MODEL.N1, routes tasks, calls models,
launches workers, binds executable model IDs, applies patches, runs validation
or benchmarks, invokes MCP tools, contacts networks, writes databases, or changes
runtime behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "model_role_planning_checkpoint"
JSON_NAME = "model_role_planning_checkpoint.json"
MD_NAME = "model_role_planning_checkpoint.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "model_role_registry" / "model_role_planning_checkpoint"

MODEL_REGISTRY_REPORT_KIND = "model_role_registry"
COVERAGE_REPORT_KIND = "model_role_coverage_report"
GAP_PLAN_REPORT_KIND = "model_role_gap_plan"
PROPOSAL_REPORT_KIND = "model_role_catalog_update_proposal"
PROPOSED_REGISTRY_REPORT_KIND = "proposed_model_role_registry"
REVIEW_REPORT_KIND = "model_role_catalog_proposal_review"
ADOPTION_PLAN_REPORT_KIND = "model_role_catalog_adoption_plan"
ADOPTION_READINESS_REPORT_KIND = "model_role_catalog_adoption_readiness"

CHECKPOINT_STATUSES: tuple[str, ...] = (
    "model_role_planning_frozen",
    "model_role_planning_frozen_with_adoption_ready_warnings",
    "model_role_planning_incomplete",
    "model_role_planning_blocked",
)

REQUIRED_MODEL_PHASE_IDS: tuple[str, ...] = (
    "MODEL.N1",
    "MODEL.N2",
    "MODEL.N3",
    "MODEL.N4",
    "MODEL.N5",
    "MODEL.N6",
    "MODEL.N7",
)

READY_STATUS_SUFFIXES: tuple[str, ...] = ("ready", "ready_with_warnings", "frozen", "frozen_with_adoption_ready_warnings")

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
    "active_registry_mutated",
    "proposed_registry_mutated",
    "automatic_adoption_performed",
    "automatic_registry_update_performed",
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "checkpoint only",
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
    "no active registry mutation",
    "no proposed registry mutation",
    "no automatic adoption",
    "writes checkpoint artifacts only",
)

MODEL_ROLE_PLANNING_CHECKPOINT_GUARDRAIL_NOTE = (
    "Model Role Planning Checkpoint is report-only: it verifies the completed "
    "MODEL.N1-MODEL.N7 advisory planning and catalog-adoption-readiness branch "
    "before any separate human-approved adoption or routing phase. It does not "
    "adopt the proposed catalog, replace MODEL.N1, route tasks, call models, "
    "launch workers, bind executable model IDs, apply patches, run validation "
    "or benchmarks, invoke MCP tools, contact networks, write databases, or "
    "change runtime behavior."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "EVAL.N1",
    "title": "Evidence Quality / Coverage Planning",
    "reason": (
        "Pause after the safe MODEL planning branch and improve evidence quality "
        "before any future adoption, routing, or execution design."
    ),
    "alternative_phase_id": "ADOPT.MODEL.1",
    "alternative_title": "Human-Approved Model Role Catalog Adoption",
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


def _roles(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    return _list_of_dicts(data.get("roles"))


def _role_ids_from_role_list(value: Any) -> list[str]:
    return _role_ids(_list_of_dicts(value))


def _expected_new_role_ids(
    proposal_data: dict[str, Any],
    review_data: dict[str, Any],
    adoption_plan_data: dict[str, Any],
    adoption_readiness_data: dict[str, Any],
) -> list[str]:
    values: list[str] = []
    values += _role_ids_from_role_list(proposal_data.get("proposed_new_roles"))
    role_review = review_data.get("proposed_role_review")
    if isinstance(role_review, dict):
        values += _strings(role_review.get("proposed_new_role_ids"))
    values += _role_ids_from_role_list(adoption_plan_data.get("proposed_new_roles"))
    safety = adoption_readiness_data.get("proposed_registry_safety_check")
    if isinstance(safety, dict):
        values += _strings(safety.get("expected_new_role_ids"))
    return _unique(values)


def _count_candidates(
    proposal_data: dict[str, Any],
    review_data: dict[str, Any],
    adoption_plan_data: dict[str, Any],
    adoption_readiness_data: dict[str, Any],
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
    safety = adoption_readiness_data.get("proposed_registry_safety_check")
    if isinstance(safety, dict) and isinstance(safety.get("proposed_role_count"), int):
        candidates["adoption readiness proposed_role_count"] = int(safety["proposed_role_count"])
    return candidates


def _readyish_status(value: str) -> bool:
    status = str(value or "")
    return any(status.endswith(suffix) for suffix in READY_STATUS_SUFFIXES) or status in {
        "role_coverage_ready",
        "role_coverage_ready_with_warnings",
        "gap_plan_ready",
        "gap_plan_ready_with_warnings",
        "catalog_update_proposal_ready",
        "catalog_update_proposal_ready_with_warnings",
        "catalog_proposal_review_ready",
        "catalog_proposal_review_ready_with_warnings",
        "adoption_plan_ready",
        "adoption_plan_ready_with_warnings",
        "adoption_readiness_ready",
        "adoption_readiness_ready_with_warnings",
    }


def _artifact_guardrail_blockers(data: dict[str, Any], label: str) -> list[str]:
    guardrails = data.get("guardrails")
    if not isinstance(guardrails, dict):
        return []
    return [f"{label} guardrail unexpectedly true: {key}" for key, value in guardrails.items() if value is True]


def _phase_completion(phase_registry_data: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    blockers: list[str] = []
    incomplete: list[str] = []
    phases = phase_registry_data.get("phases")
    phase_list = [phase for phase in phases if isinstance(phase, dict)] if isinstance(phases, list) else []
    phase_map = {str(phase.get("phase_id") or ""): phase for phase in phase_list}

    required_statuses: dict[str, str] = {}
    missing: list[str] = []
    not_complete: list[str] = []
    for phase_id in REQUIRED_MODEL_PHASE_IDS:
        phase = phase_map.get(phase_id)
        if not phase:
            missing.append(phase_id)
            incomplete.append(f"required phase missing: {phase_id}")
            continue
        status = str(phase.get("status") or "")
        required_statuses[phase_id] = status
        if status != "complete":
            not_complete.append(phase_id)
            blockers.append(f"required phase is not complete: {phase_id}")

    close_status = str((phase_map.get("MODEL.CLOSE") or {}).get("status") or "")
    if close_status and close_status != "complete":
        blockers.append("MODEL.CLOSE must be registered complete before checkpoint artifacts are final")

    next_status = str((phase_map.get("EVAL.N1") or {}).get("status") or "")
    return (
        {
            "required_phase_ids": list(REQUIRED_MODEL_PHASE_IDS),
            "required_phase_statuses": required_statuses,
            "missing_required_phases": missing,
            "not_complete_required_phases": not_complete,
            "model_close_status": close_status,
            "eval_n1_status": next_status,
            "all_model_phases_complete": not missing and not not_complete,
            "passed": not missing and not not_complete and close_status == "complete",
        },
        blockers,
        incomplete,
    )


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

    return (
        {
            "advisory_only_preserved": not advisory_failures,
            "advisory_only_failures": _unique(advisory_failures),
            "executable_binding_disallowed": not executable_failures,
            "executable_binding_failures": _unique(executable_failures),
            "model_ids_metadata_only": not model_id_authority_hits,
            "model_id_authority_hits": _unique(model_id_authority_hits),
            "forbidden_authority_absent": not forbidden_hits,
            "forbidden_authority_hits": _unique(forbidden_hits),
            "duplicate_role_ids": duplicate_ids,
            "passed": not advisory_failures and not executable_failures and not forbidden_hits and not model_id_authority_hits,
        },
        warnings,
        blockers,
    )


def _artifact_status(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(data.get(key) or "")
        if value:
            return value
    return ""


def _status(*, blockers: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blockers:
        return "model_role_planning_blocked"
    if incomplete:
        return "model_role_planning_incomplete"
    if warnings:
        return "model_role_planning_frozen_with_adoption_ready_warnings"
    return "model_role_planning_frozen"


def _missing_data(
    value: Any,
    label: str,
    *,
    active_registry: bool = False,
) -> tuple[dict[str, Any], list[str], list[str]]:
    if isinstance(value, dict) and value:
        return {"loaded": True, "label": label}, [], []
    if active_registry:
        return {"loaded": False, "label": label}, [f"{label} is missing or malformed"], []
    return {"loaded": False, "label": label}, [], [f"{label} is missing or malformed"]


def build_model_role_planning_checkpoint(
    *,
    phase_registry_path: str | Path | None,
    phase_registry_data: dict[str, Any] | None = None,
    model_registry_path: str | Path | None = None,
    model_registry_data: dict[str, Any] | None = None,
    coverage_report_path: str | Path | None = None,
    coverage_report_data: dict[str, Any] | None = None,
    gap_plan_path: str | Path | None = None,
    gap_plan_data: dict[str, Any] | None = None,
    proposal_path: str | Path | None = None,
    proposal_data: dict[str, Any] | None = None,
    proposed_registry_path: str | Path | None = None,
    proposed_registry_data: dict[str, Any] | None = None,
    review_path: str | Path | None = None,
    review_data: dict[str, Any] | None = None,
    adoption_plan_path: str | Path | None = None,
    adoption_plan_data: dict[str, Any] | None = None,
    adoption_readiness_path: str | Path | None = None,
    adoption_readiness_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic MODEL.CLOSE checkpoint report from loaded artifacts."""
    blockers = list(input_blockers or [])
    incomplete: list[str] = []
    warnings: list[str] = []

    path_specs = (
        (phase_registry_path, "phase registry"),
        (model_registry_path, "active registry"),
        (coverage_report_path, "coverage report"),
        (gap_plan_path, "gap plan"),
        (proposal_path, "proposal"),
        (proposed_registry_path, "proposed registry"),
        (review_path, "proposal review"),
        (adoption_plan_path, "adoption plan"),
        (adoption_readiness_path, "adoption readiness"),
    )
    for path, label in path_specs:
        blockers += _input_path_blockers(path, label, required=True)

    artifact_coverage: dict[str, Any] = {}
    checks = (
        ("phase_registry", phase_registry_data, "phase registry", False),
        ("model_registry", model_registry_data, "active registry", True),
        ("coverage_report", coverage_report_data, "coverage report", False),
        ("gap_plan", gap_plan_data, "gap plan", False),
        ("proposal", proposal_data, "proposal", False),
        ("proposed_registry", proposed_registry_data, "proposed registry", False),
        ("review", review_data, "proposal review", False),
        ("adoption_plan", adoption_plan_data, "adoption plan", False),
        ("adoption_readiness", adoption_readiness_data, "adoption readiness", False),
    )
    loaded_flags: dict[str, bool] = {}
    for key, data, label, active_registry in checks:
        loaded, missing_blockers, missing_incomplete = _missing_data(data, label, active_registry=active_registry)
        artifact_coverage[key] = loaded
        loaded_flags[key] = bool(loaded["loaded"])
        blockers += missing_blockers
        incomplete += missing_incomplete

    phase_registry_data = phase_registry_data if isinstance(phase_registry_data, dict) else {}
    model_registry_data = model_registry_data if isinstance(model_registry_data, dict) else {}
    coverage_report_data = coverage_report_data if isinstance(coverage_report_data, dict) else {}
    gap_plan_data = gap_plan_data if isinstance(gap_plan_data, dict) else {}
    proposal_data = proposal_data if isinstance(proposal_data, dict) else {}
    proposed_registry_data = proposed_registry_data if isinstance(proposed_registry_data, dict) else {}
    review_data = review_data if isinstance(review_data, dict) else {}
    adoption_plan_data = adoption_plan_data if isinstance(adoption_plan_data, dict) else {}
    adoption_readiness_data = adoption_readiness_data if isinstance(adoption_readiness_data, dict) else {}

    if model_registry_data.get("report_kind") != MODEL_REGISTRY_REPORT_KIND:
        blockers.append("active registry report_kind must be model_role_registry")
    if coverage_report_data.get("report_kind") != COVERAGE_REPORT_KIND:
        incomplete.append("coverage report report_kind must be model_role_coverage_report")
    if gap_plan_data.get("report_kind") != GAP_PLAN_REPORT_KIND:
        incomplete.append("gap plan report_kind must be model_role_gap_plan")
    if proposal_data.get("report_kind") != PROPOSAL_REPORT_KIND:
        incomplete.append("proposal report_kind must be model_role_catalog_update_proposal")
    if proposed_registry_data.get("report_kind") != PROPOSED_REGISTRY_REPORT_KIND:
        incomplete.append("proposed registry report_kind must be proposed_model_role_registry")
    if review_data.get("report_kind") != REVIEW_REPORT_KIND:
        incomplete.append("proposal review report_kind must be model_role_catalog_proposal_review")
    if adoption_plan_data.get("report_kind") != ADOPTION_PLAN_REPORT_KIND:
        incomplete.append("adoption plan report_kind must be model_role_catalog_adoption_plan")
    if adoption_readiness_data.get("report_kind") != ADOPTION_READINESS_REPORT_KIND:
        incomplete.append("adoption readiness report_kind must be model_role_catalog_adoption_readiness")

    phase_completion, phase_blockers, phase_incomplete = _phase_completion(phase_registry_data)
    blockers += phase_blockers
    incomplete += phase_incomplete

    artifact_coverage.update(
        {
            "all_required_artifacts_present": all(loaded_flags.values()),
            "loaded_artifact_count": sum(1 for value in loaded_flags.values() if value),
            "required_artifact_count": len(loaded_flags),
            "paths": {
                "phase_registry": str(phase_registry_path or ""),
                "model_registry": str(model_registry_path or ""),
                "coverage_report": str(coverage_report_path or ""),
                "gap_plan": str(gap_plan_path or ""),
                "proposal": str(proposal_path or ""),
                "proposed_registry": str(proposed_registry_path or ""),
                "review": str(review_path or ""),
                "adoption_plan": str(adoption_plan_path or ""),
                "adoption_readiness": str(adoption_readiness_path or ""),
            },
            "passed": all(loaded_flags.values()),
        }
    )

    artifacts = (
        ("coverage report", coverage_report_data, ("coverage_status",)),
        ("gap plan", gap_plan_data, ("gap_plan_status",)),
        ("proposal", proposal_data, ("proposal_status",)),
        ("proposal review", review_data, ("review_status",)),
        ("adoption plan", adoption_plan_data, ("adoption_plan_status",)),
        ("adoption readiness", adoption_readiness_data, ("readiness_status",)),
    )
    chain_statuses: dict[str, str] = {}
    chain_warning_counts: dict[str, int] = {}
    for label, data, keys in artifacts:
        status = _artifact_status(data, keys)
        chain_statuses[label] = status
        chain_warning_counts[label] = len(data.get("warnings") or [])
        if status and not _readyish_status(status):
            blockers.append(f"{label} status is not ready: {status}")
        for reason in _strings(data.get("blocked_reasons")):
            blockers.append(f"{label} blocker: {reason}")
        for warning in _strings(data.get("warnings")):
            warnings.append(f"{label} warning: {warning}")
        blockers += _artifact_guardrail_blockers(data, label)

    readiness_status = str(adoption_readiness_data.get("readiness_status") or "")
    if readiness_status == "adoption_readiness_ready_with_warnings":
        warnings.append("adoption readiness warning status is adoption_readiness_ready_with_warnings")

    active_roles = _roles(model_registry_data)
    proposed_roles = _roles(proposed_registry_data)
    active_ids = _role_ids(active_roles)
    proposed_ids = _role_ids(proposed_roles)
    active_id_set = set(active_ids)
    proposed_id_set = set(proposed_ids)
    expected_new_ids = _expected_new_role_ids(proposal_data, review_data, adoption_plan_data, adoption_readiness_data)
    actual_new_ids = [role_id for role_id in proposed_ids if role_id not in active_id_set]
    missing_new = sorted(role_id for role_id in expected_new_ids if role_id not in proposed_id_set)
    dropped = sorted(active_id_set - proposed_id_set)
    adopted_expected_roles = sorted(role_id for role_id in expected_new_ids if role_id in active_id_set)
    proposed_catalog_adopted = bool(expected_new_ids) and set(expected_new_ids).issubset(active_id_set)

    if not active_roles:
        blockers.append("active registry contains no roles")
    if not proposed_roles:
        incomplete.append("proposed registry contains no roles")
    for role_id in dropped:
        blockers.append(f"source role dropped in proposed registry: {role_id}")
    for role_id in missing_new:
        blockers.append(f"expected new role missing from proposed registry: {role_id}")
    if proposed_catalog_adopted or active_id_set == proposed_id_set:
        blockers.append("active registry appears to have been replaced by the proposed catalog")
    else:
        warnings.append("proposed catalog has not been adopted into the active registry")

    count_candidates = _count_candidates(proposal_data, review_data, adoption_plan_data, adoption_readiness_data)
    proposed_count = len(proposed_roles)
    declared_proposed_count = proposed_registry_data.get("role_count")
    if isinstance(declared_proposed_count, int) and declared_proposed_count != proposed_count:
        blockers.append(f"proposed registry role_count {declared_proposed_count} does not match roles {proposed_count}")
    for label, expected_count in count_candidates.items():
        if expected_count != proposed_count:
            blockers.append(f"{label} {expected_count} does not match proposed registry roles {proposed_count}")

    role_safety, role_warnings, role_blockers = _role_safety(proposed_roles)
    warnings += role_warnings
    blockers += role_blockers

    readiness_human = adoption_readiness_data.get("human_approval_readiness")
    readiness_boundary = adoption_readiness_data.get("adoption_boundary_check")
    plan_rollback = adoption_plan_data.get("rollback_plan")
    plan_checklist = _strings(adoption_plan_data.get("human_approval_checklist"))
    separate_from_plan = any(
        "separate" in item.lower() and "adoption" in item.lower() and "phase" in item.lower()
        for item in plan_checklist
    )
    separate_from_readiness = (
        isinstance(readiness_human, dict)
        and readiness_human.get("separate_adoption_phase_required") is True
    )
    rollback_explicit = (
        isinstance(plan_rollback, dict)
        and plan_rollback.get("restore_backup_if_validation_fails") is True
        and plan_rollback.get("human_confirmation_required_before_retry") is True
    )
    if not separate_from_plan or not separate_from_readiness:
        blockers.append("human approval boundary must require a separate adoption phase")
    if not rollback_explicit:
        blockers.append("rollback boundary must be explicit before branch freeze")
    if isinstance(readiness_boundary, dict) and readiness_boundary.get("active_registry_protected") is not True:
        blockers.append("readiness boundary must protect active registry")

    active_registry_status = {
        "path": str(model_registry_path or ""),
        "report_kind": model_registry_data.get("report_kind", ""),
        "validation_status": model_registry_data.get("validation_status", ""),
        "active_role_count": len(active_roles),
        "active_role_ids": active_ids,
        "adopted_expected_new_role_ids": adopted_expected_roles,
        "proposed_catalog_adopted": proposed_catalog_adopted,
        "passed": bool(active_roles) and not proposed_catalog_adopted,
    }
    proposed_registry_status = {
        "path": str(proposed_registry_path or ""),
        "report_kind": proposed_registry_data.get("report_kind", ""),
        "declared_role_count": declared_proposed_count,
        "proposed_role_count": proposed_count,
        "proposed_role_ids": proposed_ids,
        "expected_new_role_ids": expected_new_ids,
        "actual_new_role_ids": actual_new_ids,
        "source_roles_preserved": not dropped,
        "expected_new_roles_present": not missing_new,
        "proposed_catalog_adopted": proposed_catalog_adopted,
        "count_candidates": count_candidates,
        "passed": bool(proposed_roles) and not dropped and not missing_new and not role_blockers,
    }
    chain_status = {
        "artifact_statuses": chain_statuses,
        "warning_counts": chain_warning_counts,
        "passed": not any(str(status).endswith("blocked") for status in chain_statuses.values()),
    }
    safety_boundary_verification = {
        "active_registry_not_mutated": not proposed_catalog_adopted,
        "proposed_registry_separate": active_id_set != proposed_id_set,
        "source_roles_preserved": not dropped,
        "expected_new_roles_present": not missing_new,
        "no_model_routing": True,
        "no_model_call": True,
        "no_worker_launch": True,
        "no_patch_apply": True,
        "passed": not proposed_catalog_adopted and not dropped and not missing_new,
    }
    forbidden_authority_checks = {
        **role_safety,
        "artifact_guardrails_false": not [
            reason for reason in blockers if "guardrail unexpectedly true" in reason
        ],
    }
    human_approval_and_rollback_boundary = {
        "separate_adoption_phase_required_by_plan": separate_from_plan,
        "separate_adoption_phase_required_by_readiness": separate_from_readiness,
        "rollback_explicit": rollback_explicit,
        "active_registry_protected_by_readiness": (
            isinstance(readiness_boundary, dict)
            and readiness_boundary.get("active_registry_protected") is True
        ),
        "passed": separate_from_plan and separate_from_readiness and rollback_explicit,
    }

    warnings = _unique(warnings)
    blockers = _unique(blockers)
    incomplete = _unique(incomplete)
    checkpoint_status = _status(blockers=blockers, incomplete=incomplete, warnings=warnings)

    return {
        "report_kind": REPORT_KIND,
        "checkpoint_id": "model-role-planning-checkpoint",
        "guardrail_note": MODEL_ROLE_PLANNING_CHECKPOINT_GUARDRAIL_NOTE,
        "phase_registry_path": str(phase_registry_path or ""),
        "model_registry_path": str(model_registry_path or ""),
        "coverage_report_path": str(coverage_report_path or ""),
        "gap_plan_path": str(gap_plan_path or ""),
        "proposal_path": str(proposal_path or ""),
        "proposed_registry_path": str(proposed_registry_path or ""),
        "review_path": str(review_path or ""),
        "adoption_plan_path": str(adoption_plan_path or ""),
        "adoption_readiness_path": str(adoption_readiness_path or ""),
        "checkpoint_status": checkpoint_status,
        "phase_completion": phase_completion,
        "artifact_coverage": artifact_coverage,
        "active_registry_status": active_registry_status,
        "proposed_registry_status": proposed_registry_status,
        "chain_status": chain_status,
        "safety_boundary_verification": safety_boundary_verification,
        "forbidden_authority_checks": forbidden_authority_checks,
        "human_approval_and_rollback_boundary": human_approval_and_rollback_boundary,
        "files_that_must_not_change": list(FILES_THAT_MUST_NOT_CHANGE),
        "warnings": warnings,
        "incomplete_reasons": incomplete,
        "blocked_reasons": blockers,
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
        "checkpoint_statuses": list(CHECKPOINT_STATUSES),
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


def render_model_role_planning_checkpoint_markdown(report: dict[str, Any]) -> str:
    """Render a MODEL.CLOSE checkpoint report as Markdown."""
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    lines: list[str] = [
        "# Model Role Planning Checkpoint",
        "",
        f"> {report.get('guardrail_note', MODEL_ROLE_PLANNING_CHECKPOINT_GUARDRAIL_NOTE)}",
        "",
        "_Report only: MODEL.CLOSE freezes the advisory MODEL planning branch and does not adopt or route anything._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Checkpoint status:** `{_md(report.get('checkpoint_status', ''))}`",
        f"- **Warnings:** {len(report.get('warnings') or [])}",
        f"- **Blocked reasons:** {len(report.get('blocked_reasons') or [])}",
        "",
        "## Phase Completion",
        "",
    ]
    _render_dict(lines, report.get("phase_completion") if isinstance(report.get("phase_completion"), dict) else {})
    lines += ["## Artifact Coverage", ""]
    _render_dict(lines, report.get("artifact_coverage") if isinstance(report.get("artifact_coverage"), dict) else {})
    lines += ["## Active Registry Status", ""]
    _render_dict(lines, report.get("active_registry_status") if isinstance(report.get("active_registry_status"), dict) else {})
    lines += ["## Proposed Registry Status", ""]
    _render_dict(lines, report.get("proposed_registry_status") if isinstance(report.get("proposed_registry_status"), dict) else {})
    lines += ["## Coverage / Gap / Proposal / Review / Adoption Chain", ""]
    _render_dict(lines, report.get("chain_status") if isinstance(report.get("chain_status"), dict) else {})
    lines += ["## Safety Boundary Verification", ""]
    _render_dict(
        lines,
        report.get("safety_boundary_verification")
        if isinstance(report.get("safety_boundary_verification"), dict)
        else {},
    )
    lines += ["## Forbidden Authority Checks", ""]
    _render_dict(
        lines,
        report.get("forbidden_authority_checks")
        if isinstance(report.get("forbidden_authority_checks"), dict)
        else {},
    )
    lines += ["## Human Approval and Rollback Boundary", ""]
    _render_dict(
        lines,
        report.get("human_approval_and_rollback_boundary")
        if isinstance(report.get("human_approval_and_rollback_boundary"), dict)
        else {},
    )
    lines += ["## Warnings", ""]
    _render_list(lines, list(report.get("warnings") or []))
    lines += ["## Blocked Reasons", ""]
    _render_list(lines, list(report.get("blocked_reasons") or []))
    lines += ["## Final Verdict", ""]
    lines.append(f"- **Status:** `{_md(report.get('checkpoint_status', ''))}`")
    if report.get("blocked_reasons"):
        lines.append("- **Verdict:** Blocked until the listed reasons are resolved.")
    elif report.get("incomplete_reasons"):
        lines.append("- **Verdict:** Incomplete until missing evidence is supplied.")
    elif report.get("warnings"):
        lines.append("- **Verdict:** MODEL branch is frozen with warnings carried forward.")
    else:
        lines.append("- **Verdict:** MODEL branch is frozen with no warnings.")
    lines.append("")
    lines += ["## Recommended Next Phase", ""]
    lines += [
        f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
        f"- **Title:** {_md(next_phase.get('title', ''))}",
        f"- **Reason:** {_md(next_phase.get('reason', ''))}",
        f"- **Alternative:** `{_md(next_phase.get('alternative_phase_id', ''))}` - {_md(next_phase.get('alternative_title', ''))}",
        "",
        "## Boundaries / Guardrails",
        "",
    ]
    for boundary in report.get("boundaries") or []:
        lines.append(f"- {_md(boundary)}")
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: {str(bool(guardrails[key])).lower()}")
    lines.append("")
    return "\n".join(lines)


def write_model_role_planning_checkpoint(
    *,
    phase_registry_path: str | Path,
    model_registry_path: str | Path,
    coverage_report_path: str | Path,
    gap_plan_path: str | Path,
    proposal_path: str | Path,
    proposed_registry_path: str | Path,
    review_path: str | Path,
    adoption_plan_path: str | Path,
    adoption_readiness_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    phase_registry_data: dict[str, Any] | None = None,
    model_registry_data: dict[str, Any] | None = None,
    coverage_report_data: dict[str, Any] | None = None,
    gap_plan_data: dict[str, Any] | None = None,
    proposal_data: dict[str, Any] | None = None,
    proposed_registry_data: dict[str, Any] | None = None,
    review_data: dict[str, Any] | None = None,
    adoption_plan_data: dict[str, Any] | None = None,
    adoption_readiness_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build and write MODEL.CLOSE JSON + Markdown checkpoint artifacts."""
    blockers = list(input_blockers or [])
    if phase_registry_data is None and not blockers:
        phase_registry_data, read_blockers = read_json_input(phase_registry_path, "phase registry", required=True)
        blockers += read_blockers
    if model_registry_data is None and not blockers:
        model_registry_data, read_blockers = read_json_input(model_registry_path, "active registry", required=True)
        blockers += read_blockers
    if coverage_report_data is None and not blockers:
        coverage_report_data, read_blockers = read_json_input(coverage_report_path, "coverage report", required=True)
        blockers += read_blockers
    if gap_plan_data is None and not blockers:
        gap_plan_data, read_blockers = read_json_input(gap_plan_path, "gap plan", required=True)
        blockers += read_blockers
    if proposal_data is None and not blockers:
        proposal_data, read_blockers = read_json_input(proposal_path, "proposal", required=True)
        blockers += read_blockers
    if proposed_registry_data is None and not blockers:
        proposed_registry_data, read_blockers = read_json_input(proposed_registry_path, "proposed registry", required=True)
        blockers += read_blockers
    if review_data is None and not blockers:
        review_data, read_blockers = read_json_input(review_path, "proposal review", required=True)
        blockers += read_blockers
    if adoption_plan_data is None and not blockers:
        adoption_plan_data, read_blockers = read_json_input(adoption_plan_path, "adoption plan", required=True)
        blockers += read_blockers
    if adoption_readiness_data is None and not blockers:
        adoption_readiness_data, read_blockers = read_json_input(
            adoption_readiness_path, "adoption readiness", required=True
        )
        blockers += read_blockers
    report = build_model_role_planning_checkpoint(
        phase_registry_path=phase_registry_path,
        phase_registry_data=phase_registry_data,
        model_registry_path=model_registry_path,
        model_registry_data=model_registry_data,
        coverage_report_path=coverage_report_path,
        coverage_report_data=coverage_report_data,
        gap_plan_path=gap_plan_path,
        gap_plan_data=gap_plan_data,
        proposal_path=proposal_path,
        proposal_data=proposal_data,
        proposed_registry_path=proposed_registry_path,
        proposed_registry_data=proposed_registry_data,
        review_path=review_path,
        review_data=review_data,
        adoption_plan_path=adoption_plan_path,
        adoption_plan_data=adoption_plan_data,
        adoption_readiness_path=adoption_readiness_path,
        adoption_readiness_data=adoption_readiness_data,
        input_blockers=blockers,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_model_role_planning_checkpoint_markdown(report), encoding="utf-8")
    ok = report.get("checkpoint_status") in {
        "model_role_planning_frozen",
        "model_role_planning_frozen_with_adoption_ready_warnings",
    }
    return {"ok": ok, "json_path": str(json_path), "md_path": str(md_path), "report": report}
