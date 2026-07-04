"""MODEL.N2 - Model Role Coverage Report (report-only).

Compares Commander advisory role labels from CMD.N5/CMD.N6 artifacts against
MODEL.N1 advisory tower cards. This module only reads deterministic JSON
artifacts and writes JSON/Markdown coverage reports; it does not route tasks,
call models, launch workers, bind executable model IDs, run validation, run
benchmarks, apply patches, invoke MCP tools, contact networks, or mutate source
artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "model_role_coverage_report"
JSON_NAME = "model_role_coverage_report.json"
MD_NAME = "model_role_coverage_report.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "model_role_registry" / "model_role_coverage_report"

MODEL_REGISTRY_REPORT_KIND = "model_role_registry"
ASSIGNMENT_REPORT_KIND = "commander_manual_assignment_plan"
REVIEW_PACK_REPORT_KIND = "commander_assignment_review_pack"

COVERAGE_STATUSES: tuple[str, ...] = (
    "role_coverage_ready",
    "role_coverage_ready_with_warnings",
    "role_coverage_incomplete",
    "role_coverage_blocked",
)

MODEL_REGISTRY_READY_STATUSES: tuple[str, ...] = (
    "model_roles_ready",
    "model_roles_ready_with_warnings",
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

OPTIONAL_ROLE_TARGETS: tuple[str, ...] = (
    "ui_reviewer",
    "test_designer",
    "documentation_reviewer",
)

IMPLEMENTER_LIKE_KINDS: tuple[str, ...] = ("implementer", "reviewer", "risk_auditor")

ROLE_ALIASES: dict[str, str] = {
    "risk": "risk_auditor",
    "audit": "risk_auditor",
    "reviewer": "code_reviewer",
    "evidence": "evidence_checker",
    "tester": "test_designer",
    "test": "test_designer",
    "docs": "documentation_reviewer",
    "documentation": "documentation_reviewer",
    "ui": "ui_reviewer",
}

MODEL_ID_KEYS: tuple[str, ...] = (
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

EXECUTABLE_SOURCE_KEYS: tuple[str, ...] = (
    "executable_assignment",
    "executable_worker_id",
    "executable_worker",
    "worker_binding",
    "worker_id",
    "assigned_worker",
    "execution_worker",
    "launch_worker",
    "real_worker_assignment",
    "route_tasks",
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

MODEL_ROLE_COVERAGE_GUARDRAIL_NOTE = (
    "Model Role Coverage Report is report-only: it compares Commander advisory "
    "role labels from CMD.N5/CMD.N6 with MODEL.N1 advisory tower cards. It does "
    "not route tasks, call models, launch workers, bind Commander roles to "
    "executable model IDs, run validation or benchmarks, apply patches, mutate "
    "source artifacts, invoke MCP tools, execute Dream actions, apply Replay "
    "janitor actions, use Docker/subprocess, contact networks, write databases, "
    "or change auth, route, or routing behavior."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "MODEL.N3",
    "title": "Model Role Gap Plan",
    "reason": (
        "After coverage is known, prepare a manual plan for adding missing or "
        "weak advisory tower cards without routing, model calls, worker launch, "
        "or executable model binding."
    ),
}

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "coverage analysis only",
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
    "writes coverage artifacts only",
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


def _safe_identifier(value: Any) -> bool:
    text = str(value or "").strip()
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if not text or text in {".", ".."} or ".." in text:
        return False
    if "/" in text or "\\" in text or text.startswith("."):
        return False
    return all(ch in allowed for ch in text)


def _role_detail(role: dict[str, Any]) -> dict[str, Any]:
    detail = {
        "role_id": str(role.get("role_id") or "").strip(),
        "display_name": str(role.get("display_name") or "").strip(),
        "role_kind": str(role.get("role_kind") or "").strip(),
        "risk_level": str(role.get("risk_level") or "unknown").strip(),
        "cost_tier": str(role.get("cost_tier") or "unknown").strip(),
        "latency_tier": str(role.get("latency_tier") or "unknown").strip(),
        "context_tier": str(role.get("context_tier") or "unknown").strip(),
        "reliability_tier": str(role.get("reliability_tier") or "unknown").strip(),
        "advisory_only": True if "advisory_only" not in role else bool(role.get("advisory_only")),
        "executable_binding_allowed": bool(role.get("executable_binding_allowed", False)),
        "model_ids": _strings(role.get("model_ids")),
        "model_id_policy": str(role.get("model_id_policy") or "descriptive_metadata_only"),
        "fallback_roles": _strings(role.get("fallback_roles")),
        "human_review_required": bool(role.get("human_review_required", False)),
        "allowed_task_types": _strings(role.get("allowed_task_types")),
        "forbidden_task_types": _strings(role.get("forbidden_task_types")),
    }
    return detail


def _authority_claim_blockers(role_id: str, raw: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for key, value in raw.items():
        low = str(key).lower()
        if any(fragment in low for fragment in AUTHORITY_KEY_FRAGMENTS) and bool(value):
            blockers.append(f"role {role_id} claims executable authority via {key}")
    return blockers


def _role_safety_findings(
    *,
    raw_roles: list[dict[str, Any]],
    details: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    warnings: list[str] = []
    blockers: list[str] = []
    overpowered: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    seen: set[str] = set()
    for index, detail in enumerate(details):
        raw = raw_roles[index]
        role_id = str(detail.get("role_id") or f"#{index}")
        role_kind = str(detail.get("role_kind") or "")
        if not _safe_identifier(role_id):
            blockers.append(f"role {role_id} has an unsafe or empty role_id")
        if role_id in seen:
            blockers.append(f"duplicate model role_id: {role_id}")
        seen.add(role_id)
        if detail["advisory_only"] is not True:
            reason = f"role {role_id} advisory_only must be true"
            blockers.append(reason)
            overpowered.append({"role_id": role_id, "reason": reason})
        if detail["executable_binding_allowed"] is True:
            reason = f"role {role_id} executable_binding_allowed must be false"
            blockers.append(reason)
            overpowered.append({"role_id": role_id, "reason": reason})
        for flag in FORBIDDEN_AUTHORITY_FLAGS:
            if bool(raw.get(flag, False)) is True:
                reason = f"role {role_id} includes forbidden authority flag: {flag}"
                blockers.append(reason)
                overpowered.append({"role_id": role_id, "reason": reason})
        for reason in _authority_claim_blockers(role_id, raw):
            blockers.append(reason)
            overpowered.append({"role_id": role_id, "reason": reason})
        if role_kind in IMPLEMENTER_LIKE_KINDS and detail["human_review_required"] is not True:
            reason = f"role {role_id} human_review_required must be true for {role_kind} roles"
            blockers.append(reason)
            overpowered.append({"role_id": role_id, "reason": reason})
        allowed = set(detail.get("allowed_task_types") or [])
        forbidden = set(detail.get("forbidden_task_types") or [])
        overlap = sorted(allowed & forbidden)
        if overlap:
            reason = f"role {role_id} allowed_task_types conflicts with forbidden_task_types"
            blockers.append(reason + ": " + ", ".join(overlap))
            conflicts.append({"role_id": role_id, "conflicting_task_types": overlap})
        unknown_tiers = [
            field
            for field in ("risk_level", "cost_tier", "latency_tier", "context_tier", "reliability_tier")
            if detail.get(field) == "unknown"
        ]
        if unknown_tiers:
            warnings.append(f"role {role_id} has unknown tier fields: {', '.join(unknown_tiers)}")
    return _unique(warnings), _unique(blockers), overpowered, conflicts


def _scan_source_bindings(value: Any, label: str, path: str = "") -> list[str]:
    blockers: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            current = f"{path}.{key_text}" if path else key_text
            low_key = key_text.lower()
            if low_key in EXECUTABLE_SOURCE_KEYS and bool(item):
                blockers.append(f"{label} defines executable worker/model binding at {current}")
            if low_key in MODEL_ID_KEYS and str(item or "").strip():
                blockers.append(f"{label} defines executable model binding at {current}")
            if low_key in FORBIDDEN_AUTHORITY_FLAGS and item is True:
                blockers.append(f"{label} enables forbidden authority flag at {current}")
            if low_key.endswith("_performed") and item is True:
                blockers.append(f"{label} reports forbidden guardrail action at {current}")
            blockers += _scan_source_bindings(item, label, current)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            current = f"{path}[{index}]" if path else f"[{index}]"
            blockers += _scan_source_bindings(item, label, current)
    return blockers


def _source_text(row: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "title",
        "warnings",
        "incomplete_reasons",
        "blocked_reasons",
        "unresolved_warnings",
        "source_evidence_required",
        "evidence_required",
    ):
        item = row.get(key)
        if isinstance(item, list):
            values += [str(value) for value in item]
        else:
            values.append(str(item or ""))
    return " ".join(values).lower()


def _missing_evidence(row: dict[str, Any]) -> bool:
    evidence = _strings(row.get("source_evidence_required")) or _strings(row.get("evidence_required"))
    if not evidence:
        return True
    text = _source_text(row)
    return "missing evidence" in text or "evidence_required must be non-empty" in text


def _role_labels_include(labels: list[str], expected: str) -> bool:
    low_labels = {label.strip().lower() for label in labels}
    if expected in low_labels:
        return True
    return any(ROLE_ALIASES.get(label) == expected for label in low_labels)


def _add_required_role(
    rows: list[dict[str, Any]],
    *,
    source: str,
    source_id: str,
    source_role: str,
    reason: str,
) -> None:
    row = {
        "source": source,
        "source_id": source_id,
        "source_role": source_role,
        "reason": reason,
    }
    if row not in rows:
        rows.append(row)


def _extract_assignment_roles(
    assignment_data: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[str], list[str], dict[str, Any], dict[str, Any]]:
    required: list[dict[str, Any]] = []
    warnings: list[str] = []
    blockers: list[str] = []
    risk_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []

    if assignment_data is None:
        return required, warnings, blockers, {"coverage": [], "high_or_unknown_without_risk_auditor": []}, {
            "coverage": [],
            "missing_evidence_without_evidence_checker": [],
        }
    if assignment_data.get("report_kind") != ASSIGNMENT_REPORT_KIND:
        blockers.append("assignment report_kind must be commander_manual_assignment_plan")
    status = str(assignment_data.get("assignment_status") or "")
    if status and status != "assignment_ready":
        warnings.append(f"assignment_status is {status}")
    blockers += _scan_source_bindings(assignment_data, "assignment")

    raw_rows = assignment_data.get("assignments")
    if raw_rows is None:
        raw_rows = []
    if not isinstance(raw_rows, list):
        blockers.append("assignment assignments must be a list")
        raw_rows = []

    for index, item in enumerate(raw_rows):
        if not isinstance(item, dict):
            blockers.append(f"assignment assignments[{index}] must be an object")
            continue
        source_id = str(item.get("sub_boss_id") or item.get("assignment_id") or f"assignment-{index}").strip()
        labels = _strings(item.get("advisory_roles"))
        for label in labels:
            _add_required_role(
                required,
                source="assignment",
                source_id=source_id,
                source_role=label,
                reason="CMD.N5 advisory assignment",
            )
        risk_level = str(item.get("risk_level") or "unknown").strip().lower()
        risk_required = risk_level in {"high", "unknown"}
        risk_assigned = _role_labels_include(labels, "risk_auditor")
        if risk_required and not risk_assigned:
            warnings.append(f"sub_boss {source_id} requires risk_auditor coverage")
            _add_required_role(
                required,
                source="assignment",
                source_id=source_id,
                source_role="risk_auditor",
                reason=f"{risk_level} risk coverage requirement",
            )
        risk_rows.append(
            {
                "source": "assignment",
                "sub_boss_id": source_id,
                "risk_level": risk_level,
                "coverage_required": risk_required,
                "risk_auditor_assigned": risk_assigned,
            }
        )
        missing = _missing_evidence(item)
        evidence_assigned = _role_labels_include(labels, "evidence_checker")
        if missing and not evidence_assigned:
            warnings.append(f"sub_boss {source_id} requires evidence_checker coverage")
            _add_required_role(
                required,
                source="assignment",
                source_id=source_id,
                source_role="evidence_checker",
                reason="missing evidence coverage requirement",
            )
        evidence_rows.append(
            {
                "source": "assignment",
                "sub_boss_id": source_id,
                "evidence_required_count": len(_strings(item.get("source_evidence_required")) or _strings(item.get("evidence_required"))),
                "missing_evidence": missing,
                "evidence_checker_assigned": evidence_assigned,
            }
        )

    return (
        required,
        _unique(warnings),
        _unique(blockers),
        {
            "coverage": risk_rows,
            "high_or_unknown_without_risk_auditor": [
                row["sub_boss_id"]
                for row in risk_rows
                if row.get("coverage_required") and not row.get("risk_auditor_assigned")
            ],
        },
        {
            "coverage": evidence_rows,
            "missing_evidence_without_evidence_checker": [
                row["sub_boss_id"]
                for row in evidence_rows
                if row.get("missing_evidence") and not row.get("evidence_checker_assigned")
            ],
        },
    )


def _extract_review_pack_roles(
    review_pack_data: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[str], list[str], dict[str, Any], dict[str, Any]]:
    required: list[dict[str, Any]] = []
    warnings: list[str] = []
    blockers: list[str] = []
    risk_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []

    if review_pack_data is None:
        return required, warnings, blockers, {"coverage": [], "high_or_unknown_without_risk_auditor": []}, {
            "coverage": [],
            "missing_evidence_without_evidence_checker": [],
        }
    if review_pack_data.get("report_kind") != REVIEW_PACK_REPORT_KIND:
        blockers.append("review pack report_kind must be commander_assignment_review_pack")
    status = str(review_pack_data.get("review_status") or "")
    if status and status != "review_pack_ready":
        warnings.append(f"review_status is {status}")
    blockers += _scan_source_bindings(review_pack_data, "review pack")

    raw_rows = review_pack_data.get("per_sub_boss_review")
    if raw_rows is None:
        raw_rows = []
    if not isinstance(raw_rows, list):
        blockers.append("review pack per_sub_boss_review must be a list")
        raw_rows = []

    for index, item in enumerate(raw_rows):
        if not isinstance(item, dict):
            blockers.append(f"review pack per_sub_boss_review[{index}] must be an object")
            continue
        source_id = str(item.get("sub_boss_id") or f"review-{index}").strip()
        labels = _strings(item.get("assigned_advisory_roles"))
        for label in labels:
            _add_required_role(
                required,
                source="review_pack",
                source_id=source_id,
                source_role=label,
                reason="CMD.N6 per-sub-boss advisory review",
            )
        risk_level = str(item.get("risk_level") or "unknown").strip().lower()
        risk_required = risk_level in {"high", "unknown"}
        risk_assigned = _role_labels_include(labels, "risk_auditor")
        if risk_required and not risk_assigned:
            warnings.append(f"sub_boss {source_id} requires risk_auditor coverage")
            _add_required_role(
                required,
                source="review_pack",
                source_id=source_id,
                source_role="risk_auditor",
                reason=f"{risk_level} risk coverage requirement",
            )
        risk_rows.append(
            {
                "source": "review_pack",
                "sub_boss_id": source_id,
                "risk_level": risk_level,
                "coverage_required": risk_required,
                "risk_auditor_assigned": risk_assigned,
            }
        )
        missing = _missing_evidence(item)
        evidence_assigned = _role_labels_include(labels, "evidence_checker")
        if missing and not evidence_assigned:
            warnings.append(f"sub_boss {source_id} requires evidence_checker coverage")
            _add_required_role(
                required,
                source="review_pack",
                source_id=source_id,
                source_role="evidence_checker",
                reason="missing evidence coverage requirement",
            )
        evidence_rows.append(
            {
                "source": "review_pack",
                "sub_boss_id": source_id,
                "evidence_required_count": len(_strings(item.get("evidence_required"))),
                "missing_evidence": missing,
                "evidence_checker_assigned": evidence_assigned,
            }
        )

    return (
        required,
        _unique(warnings),
        _unique(blockers),
        {
            "coverage": risk_rows,
            "high_or_unknown_without_risk_auditor": [
                row["sub_boss_id"]
                for row in risk_rows
                if row.get("coverage_required") and not row.get("risk_auditor_assigned")
            ],
        },
        {
            "coverage": evidence_rows,
            "missing_evidence_without_evidence_checker": [
                row["sub_boss_id"]
                for row in evidence_rows
                if row.get("missing_evidence") and not row.get("evidence_checker_assigned")
            ],
        },
    )


def _kind_index(details: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_kind: dict[str, list[str]] = {}
    for role in details:
        by_kind.setdefault(str(role.get("role_kind") or ""), []).append(str(role.get("role_id") or ""))
    return by_kind


def _resolve_role(
    source_role: str,
    *,
    role_ids: set[str],
    by_kind: dict[str, list[str]],
) -> tuple[str, str]:
    label = str(source_role or "").strip().lower()
    if label in role_ids:
        return label, "exact_role_id"
    alias_target = ROLE_ALIASES.get(label)
    if alias_target:
        if alias_target in role_ids:
            return alias_target, f"alias:{label}"
        return alias_target, f"missing_alias_target:{label}"
    if label in by_kind and len([role_id for role_id in by_kind[label] if role_id]) == 1:
        return by_kind[label][0], f"role_kind:{label}"
    return label, "unmatched"


def _combined_gap(left: dict[str, Any], right: dict[str, Any], key: str) -> list[str]:
    return _unique(list(left.get(key) or []) + list(right.get(key) or []))


def _status(*, blockers: list[str], missing_roles: list[str], warnings: list[str]) -> str:
    if blockers:
        return "role_coverage_blocked"
    if missing_roles:
        return "role_coverage_incomplete"
    if warnings:
        return "role_coverage_ready_with_warnings"
    return "role_coverage_ready"


def build_model_role_coverage_report(
    *,
    model_registry_path: str | Path,
    model_registry_data: dict[str, Any] | None = None,
    assignment_path: str | Path | None = None,
    assignment_data: dict[str, Any] | None = None,
    review_pack_path: str | Path | None = None,
    review_pack_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic MODEL.N2 coverage report from loaded artifacts."""
    blockers = list(input_blockers or [])
    blockers += _input_path_blockers(model_registry_path, "model registry", required=True)
    blockers += _input_path_blockers(assignment_path, "assignment", required=False)
    blockers += _input_path_blockers(review_pack_path, "review pack", required=False)
    warnings: list[str] = []

    if model_registry_data is None:
        model_registry_data = {}
        blockers.append("model registry is missing or malformed")
    if not isinstance(model_registry_data, dict):
        model_registry_data = {}
        blockers.append("model registry must contain a JSON object")
    if assignment_data is not None and not isinstance(assignment_data, dict):
        assignment_data = {}
        blockers.append("assignment must contain a JSON object")
    if review_pack_data is not None and not isinstance(review_pack_data, dict):
        review_pack_data = {}
        blockers.append("review pack must contain a JSON object")

    if model_registry_data.get("report_kind") != MODEL_REGISTRY_REPORT_KIND:
        blockers.append("model registry report_kind must be model_role_registry")
    registry_status = str(model_registry_data.get("validation_status") or "")
    if registry_status not in MODEL_REGISTRY_READY_STATUSES:
        blockers.append(
            "model registry validation_status must be model_roles_ready or model_roles_ready_with_warnings"
        )

    raw_roles = [role for role in model_registry_data.get("roles") or [] if isinstance(role, dict)]
    if not isinstance(model_registry_data.get("roles"), list):
        blockers.append("model registry roles must be a list")
    if not raw_roles:
        blockers.append("model registry contains no roles")

    details = [_role_detail(role) for role in raw_roles]
    role_warnings, role_blockers, overpowered_roles, role_conflicts = _role_safety_findings(
        raw_roles=raw_roles,
        details=details,
    )
    warnings += role_warnings
    blockers += role_blockers

    available_roles = [str(role.get("role_id") or "") for role in details if str(role.get("role_id") or "")]
    role_ids = set(available_roles)
    detail_by_id = {str(role.get("role_id") or ""): role for role in details}
    by_kind = _kind_index(details)

    optional_missing = [role for role in OPTIONAL_ROLE_TARGETS if role not in role_ids]
    for role in optional_missing:
        warnings.append(f"optional Commander role {role} is not present in MODEL.N1 tower cards")

    assignment_required, assignment_warnings, assignment_blockers, assignment_risk, assignment_evidence = (
        _extract_assignment_roles(assignment_data)
    )
    review_required, review_warnings, review_blockers, review_risk, review_evidence = _extract_review_pack_roles(
        review_pack_data
    )
    required_rows = assignment_required + review_required
    warnings += assignment_warnings + review_warnings
    blockers += assignment_blockers + review_blockers

    matched_roles: list[dict[str, Any]] = []
    missing_roles: list[str] = []
    seen_matches: set[tuple[str, str, str, str]] = set()
    for row in required_rows:
        source_role = str(row.get("source_role") or "").strip()
        model_role_id, method = _resolve_role(source_role, role_ids=role_ids, by_kind=by_kind)
        if model_role_id in role_ids:
            key = (
                str(row.get("source") or ""),
                str(row.get("source_id") or ""),
                source_role,
                model_role_id,
            )
            if key not in seen_matches:
                matched_roles.append(
                    {
                        "source": row.get("source", ""),
                        "source_id": row.get("source_id", ""),
                        "source_role": source_role,
                        "model_role_id": model_role_id,
                        "canonical_role_id": model_role_id,
                        "match_method": method,
                        "reason": row.get("reason", ""),
                    }
                )
                seen_matches.add(key)
        else:
            missing_roles.append(model_role_id)

    fallback_coverage: list[dict[str, Any]] = []
    required_model_role_ids = {row["model_role_id"] for row in matched_roles}
    for detail in details:
        role_id = str(detail.get("role_id") or "")
        fallbacks = list(detail.get("fallback_roles") or [])
        unknown = [fallback for fallback in fallbacks if fallback not in role_ids]
        status = "fallback_ready"
        if unknown:
            status = "unknown_fallback"
            reason = f"role {role_id} references unknown fallback role: {', '.join(unknown)}"
            if role_id in required_model_role_ids:
                blockers.append(reason)
            else:
                warnings.append(reason)
        elif role_id in required_model_role_ids and not fallbacks and role_id not in {"local_fallback"}:
            status = "weak_fallback"
            warnings.append(f"role {role_id} has weak fallback coverage")
        fallback_coverage.append(
            {
                "role_id": role_id,
                "fallback_roles": fallbacks,
                "unknown_fallback_roles": unknown,
                "coverage_status": status,
            }
        )

    risky_roles = [
        {
            "role_id": str(role.get("role_id") or ""),
            "risk_level": str(role.get("risk_level") or ""),
            "reason": "MODEL.N1 tower card has high or unknown risk tier",
        }
        for role in details
        if str(role.get("risk_level") or "") in {"high", "unknown"}
    ]

    risk_coverage = {
        "coverage": list(assignment_risk.get("coverage") or []) + list(review_risk.get("coverage") or []),
        "high_or_unknown_without_risk_auditor": _combined_gap(
            assignment_risk,
            review_risk,
            "high_or_unknown_without_risk_auditor",
        ),
    }
    evidence_coverage = {
        "coverage": list(assignment_evidence.get("coverage") or []) + list(review_evidence.get("coverage") or []),
        "missing_evidence_without_evidence_checker": _combined_gap(
            assignment_evidence,
            review_evidence,
            "missing_evidence_without_evidence_checker",
        ),
    }

    warnings = _unique(warnings)
    blockers = _unique(blockers)
    missing_roles = _unique(missing_roles)
    coverage_status = _status(blockers=blockers, missing_roles=missing_roles, warnings=warnings)
    forbidden_hits = [
        reason
        for reason in blockers
        if "forbidden authority flag" in reason
        or "claims executable authority" in reason
        or "executable" in reason
        or "model binding" in reason
    ]

    return {
        "report_kind": REPORT_KIND,
        "report_id": "model-role-coverage-report",
        "guardrail_note": MODEL_ROLE_COVERAGE_GUARDRAIL_NOTE,
        "source_model_registry_path": str(model_registry_path or ""),
        "source_assignment_path": str(assignment_path or ""),
        "source_review_pack_path": str(review_pack_path or ""),
        "source_artifacts": {
            "model_registry": {
                "path": str(model_registry_path or ""),
                "report_kind": model_registry_data.get("report_kind", ""),
                "status": registry_status,
                "loaded": bool(model_registry_data),
            },
            "assignment": {
                "path": str(assignment_path or ""),
                "report_kind": (assignment_data or {}).get("report_kind", "") if isinstance(assignment_data, dict) else "",
                "status": (assignment_data or {}).get("assignment_status", "") if isinstance(assignment_data, dict) else "",
                "loaded": bool(assignment_data),
            },
            "review_pack": {
                "path": str(review_pack_path or ""),
                "report_kind": (review_pack_data or {}).get("report_kind", "") if isinstance(review_pack_data, dict) else "",
                "status": (review_pack_data or {}).get("review_status", "") if isinstance(review_pack_data, dict) else "",
                "loaded": bool(review_pack_data),
            },
        },
        "coverage_status": coverage_status,
        "required_commander_roles": required_rows,
        "available_model_roles": available_roles,
        "available_model_role_details": details,
        "matched_roles": matched_roles,
        "missing_roles": missing_roles,
        "risky_roles": risky_roles,
        "overpowered_roles": overpowered_roles,
        "fallback_coverage": fallback_coverage,
        "role_conflicts": role_conflicts,
        "risk_coverage": risk_coverage,
        "evidence_coverage": evidence_coverage,
        "forbidden_authority_checks": {
            "forbidden_flags": list(FORBIDDEN_AUTHORITY_FLAGS),
            "blocked_hits": forbidden_hits,
            "passed": not forbidden_hits,
        },
        "warnings": warnings,
        "blocked_reasons": blockers,
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
        "coverage_statuses": list(COVERAGE_STATUSES),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_model_role_coverage_report_markdown(report: dict[str, Any]) -> str:
    """Render a MODEL.N2 model role coverage report as Markdown."""
    source = report.get("source_artifacts") if isinstance(report.get("source_artifacts"), dict) else {}
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    risk = report.get("risk_coverage") if isinstance(report.get("risk_coverage"), dict) else {}
    evidence = report.get("evidence_coverage") if isinstance(report.get("evidence_coverage"), dict) else {}
    checks = report.get("forbidden_authority_checks") if isinstance(report.get("forbidden_authority_checks"), dict) else {}

    lines: list[str] = [
        "# Model Role Coverage Report",
        "",
        f"> {report.get('guardrail_note', MODEL_ROLE_COVERAGE_GUARDRAIL_NOTE)}",
        "",
        "_Report only: MODEL.N2 compares advisory role labels to advisory tower cards. It routes nothing, calls no models, launches no workers, and creates no executable bindings._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Coverage status:** `{_md(report.get('coverage_status', ''))}`",
        f"- **Required Commander roles:** {len(report.get('required_commander_roles') or [])}",
        f"- **Matched roles:** {len(report.get('matched_roles') or [])}",
        f"- **Missing roles:** {len(report.get('missing_roles') or [])}",
        f"- **Blocked reasons:** {len(report.get('blocked_reasons') or [])}",
        "",
        "## Source Artifacts",
        "",
        "| Artifact | Path | Kind | Status | Loaded |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name in ("model_registry", "assignment", "review_pack"):
        row = source.get(name) if isinstance(source.get(name), dict) else {}
        lines.append(
            "| {name} | {path} | {kind} | {status} | {loaded} |".format(
                name=_md(name),
                path=_md(row.get("path", "")),
                kind=_md(row.get("report_kind", "")),
                status=_md(row.get("status", "")),
                loaded=str(bool(row.get("loaded"))).lower(),
            )
        )

    lines += ["", "## Required Commander Roles", ""]
    required = report.get("required_commander_roles") if isinstance(report.get("required_commander_roles"), list) else []
    if required:
        lines += ["| Source | Sub-boss | Role | Reason |", "| --- | --- | --- | --- |"]
        for row in required:
            lines.append(
                "| {source} | {sid} | {role} | {reason} |".format(
                    source=_md(row.get("source", "")),
                    sid=_md(row.get("source_id", "")),
                    role=_md(row.get("source_role", "")),
                    reason=_md(row.get("reason", "")),
                )
            )
    else:
        lines.append("_None._")
    lines += ["", "## Available Tower Cards", ""]
    details = report.get("available_model_role_details") if isinstance(report.get("available_model_role_details"), list) else []
    if details:
        lines += [
            "| Role | Kind | Risk | Human review | Model IDs | Fallbacks |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for role in details:
            lines.append(
                "| {role} | {kind} | {risk} | {review} | {models} | {fallbacks} |".format(
                    role=_md(role.get("role_id", "")),
                    kind=_md(role.get("role_kind", "")),
                    risk=_md(role.get("risk_level", "")),
                    review=str(bool(role.get("human_review_required"))).lower(),
                    models=_md(", ".join(role.get("model_ids") or [])),
                    fallbacks=_md(", ".join(role.get("fallback_roles") or [])),
                )
            )
    else:
        lines.append("_None._")

    lines += ["", "## Role Coverage Matrix", ""]
    matched = report.get("matched_roles") if isinstance(report.get("matched_roles"), list) else []
    if matched:
        lines += ["| Source role | Model role | Source | Sub-boss | Match |", "| --- | --- | --- | --- | --- |"]
        for row in matched:
            lines.append(
                "| {source_role} | {model_role} | {source} | {sid} | {match} |".format(
                    source_role=_md(row.get("source_role", "")),
                    model_role=_md(row.get("model_role_id", "")),
                    source=_md(row.get("source", "")),
                    sid=_md(row.get("source_id", "")),
                    match=_md(row.get("match_method", "")),
                )
            )
    else:
        lines.append("_None._")

    lines += ["", "## Missing Roles", ""]
    _render_list(lines, list(report.get("missing_roles") or []), code=True)

    lines += ["## Risk Coverage", ""]
    risk_rows = risk.get("coverage") if isinstance(risk.get("coverage"), list) else []
    if risk_rows:
        for row in risk_rows:
            lines.append(
                f"- `{_md(row.get('sub_boss_id', ''))}` risk=`{_md(row.get('risk_level', ''))}`, risk_auditor_assigned={str(bool(row.get('risk_auditor_assigned'))).lower()}"
            )
    else:
        lines.append("_None._")
    risk_gaps = risk.get("high_or_unknown_without_risk_auditor") or []
    if risk_gaps:
        lines.append(f"- Missing risk_auditor assignment coverage: `{_md(', '.join(risk_gaps))}`")
    lines.append("")

    lines += ["## Evidence Coverage", ""]
    evidence_rows = evidence.get("coverage") if isinstance(evidence.get("coverage"), list) else []
    if evidence_rows:
        for row in evidence_rows:
            lines.append(
                f"- `{_md(row.get('sub_boss_id', ''))}` evidence_required_count={row.get('evidence_required_count', 0)}, missing_evidence={str(bool(row.get('missing_evidence'))).lower()}, evidence_checker_assigned={str(bool(row.get('evidence_checker_assigned'))).lower()}"
            )
    else:
        lines.append("_None._")
    evidence_gaps = evidence.get("missing_evidence_without_evidence_checker") or []
    if evidence_gaps:
        lines.append(f"- Missing evidence_checker assignment coverage: `{_md(', '.join(evidence_gaps))}`")
    lines.append("")

    lines += ["## Fallback Coverage", ""]
    fallback = report.get("fallback_coverage") if isinstance(report.get("fallback_coverage"), list) else []
    if fallback:
        lines += ["| Role | Fallbacks | Unknown | Status |", "| --- | --- | --- | --- |"]
        for row in fallback:
            lines.append(
                "| {role} | {fallbacks} | {unknown} | {status} |".format(
                    role=_md(row.get("role_id", "")),
                    fallbacks=_md(", ".join(row.get("fallback_roles") or [])),
                    unknown=_md(", ".join(row.get("unknown_fallback_roles") or [])),
                    status=_md(row.get("coverage_status", "")),
                )
            )
    else:
        lines.append("_None._")
    lines += [
        "",
        "## Forbidden Authority Checks",
        "",
        f"- **Passed:** {str(bool(checks.get('passed'))).lower()}",
        f"- **Forbidden flags:** `{_md(', '.join(checks.get('forbidden_flags') or []))}`",
        "",
        "## Warnings",
        "",
    ]
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


def write_model_role_coverage_report(
    *,
    model_registry_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    assignment_path: str | Path | None = None,
    review_pack_path: str | Path | None = None,
    model_registry_data: dict[str, Any] | None = None,
    assignment_data: dict[str, Any] | None = None,
    review_pack_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build and write MODEL.N2 JSON + Markdown coverage artifacts."""
    blockers = list(input_blockers or [])
    if model_registry_data is None and not blockers:
        model_registry_data, read_blockers = read_json_input(model_registry_path, "model registry", required=True)
        blockers += read_blockers
    if assignment_path is not None and assignment_data is None and not blockers:
        assignment_data, read_blockers = read_json_input(assignment_path, "assignment")
        blockers += read_blockers
    if review_pack_path is not None and review_pack_data is None and not blockers:
        review_pack_data, read_blockers = read_json_input(review_pack_path, "review pack")
        blockers += read_blockers
    report = build_model_role_coverage_report(
        model_registry_path=model_registry_path,
        model_registry_data=model_registry_data,
        assignment_path=assignment_path,
        assignment_data=assignment_data,
        review_pack_path=review_pack_path,
        review_pack_data=review_pack_data,
        input_blockers=blockers,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_model_role_coverage_report_markdown(report), encoding="utf-8")
    return {
        "ok": report.get("coverage_status") != "role_coverage_blocked",
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
