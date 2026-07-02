"""CMD.N5 - Commander Manual Assignment Plan (report-only).

Creates a deterministic advisory assignment plan from a CMD.N4 Commander
Preflight Contract artifact. CMD.N5 writes planning artifacts only. It does not
launch workers, bind executable worker IDs, call models, run validation, run
benchmarks, apply patches, mutate the source preflight/tree, change routing,
invoke MCP tools, execute Dream actions, apply Replay janitor actions, use
Docker/subprocess, contact networks, write databases, or change auth policy.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "commander_manual_assignment_plan"
JSON_NAME = "commander_manual_assignment_plan.json"
MD_NAME = "commander_manual_assignment_plan.md"

DEFAULT_OUTPUT_ROOT = Path(".agent") / "commander" / "manual_assignment_plan"
INVALID_TREE_ID_DIR = "invalid_tree_id"

PREFLIGHT_REPORT_KIND = "commander_preflight_contract"

ASSIGNMENT_STATUSES: tuple[str, ...] = (
    "assignment_ready",
    "assignment_ready_with_warnings",
    "assignment_incomplete",
    "assignment_blocked",
)

PREFLIGHT_STATUSES: tuple[str, ...] = (
    "preflight_ready",
    "preflight_ready_with_warnings",
    "preflight_incomplete",
    "preflight_blocked",
)

DEFAULT_ROLE_CATALOG: dict[str, dict[str, list[str]]] = {
    "planner": {
        "best_for": ["scope clarification", "decomposition", "dependency reasoning"],
        "not_allowed_to": ["mutate files", "approve patches", "run tools"],
    },
    "implementer": {
        "best_for": ["patch proposal preparation"],
        "not_allowed_to": ["apply patches", "bypass approval", "run validation"],
    },
    "reviewer": {
        "best_for": ["code review", "contradiction detection"],
        "not_allowed_to": ["approve final apply", "mutate files"],
    },
    "evidence_checker": {
        "best_for": ["evidence completeness", "validation claim matching"],
        "not_allowed_to": ["run benchmarks", "mutate evidence"],
    },
    "risk_auditor": {
        "best_for": ["safety", "path scope", "hidden mutation risk"],
        "not_allowed_to": ["execute tasks", "approve risky action"],
    },
    "ui_reviewer": {
        "best_for": ["UI behavior and copy review"],
        "not_allowed_to": ["change templates directly"],
    },
    "test_designer": {
        "best_for": ["test plan and edge cases"],
        "not_allowed_to": ["run tests automatically"],
    },
    "documentation_reviewer": {
        "best_for": ["roadmap/artifact consistency"],
        "not_allowed_to": ["change registry automatically"],
    },
}

ASSIGNMENT_RULES: tuple[str, ...] = (
    "preflight_blocked sub-bosses are left unassigned and never receive executable assignment.",
    "preflight_incomplete sub-bosses may receive planner, risk_auditor, and evidence_checker only.",
    "preflight_ready_with_warnings sub-bosses receive reviewer and risk_auditor coverage.",
    "preflight_ready sub-bosses receive planner, implementer, reviewer, and evidence_checker coverage.",
    "high or unknown risk requires risk_auditor coverage.",
    "missing evidence requires evidence_checker coverage.",
    "UI-scope sub-bosses receive ui_reviewer coverage.",
    "test-heavy sub-bosses receive test_designer coverage.",
    "docs or roadmap-scope sub-bosses receive documentation_reviewer coverage.",
    "All role names are advisory labels only, not model names or executable worker IDs.",
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "CMD.N6",
    "title": "Commander Assignment Review Pack",
    "reason": (
        "Before any execution design, combine the fracture tree, CMD.N4 "
        "preflight contract, and CMD.N5 assignment plan into a human-readable "
        "review pack."
    ),
    "alternative": "CMD.N6 - Commander Readiness Checkpoint",
}

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "model_call_performed",
    "worker_launch_performed",
    "real_worker_assignment_performed",
    "executable_worker_binding_performed",
    "patch_apply_performed",
    "validation_run_performed",
    "benchmark_run_performed",
    "mcp_invocation_performed",
    "dream_execution_performed",
    "replay_janitor_apply_performed",
    "docker_subprocess_performed",
    "network_call_performed",
    "database_write_performed",
    "route_behavior_change_performed",
    "auth_policy_change_performed",
    "source_preflight_mutation_performed",
    "fracture_tree_mutation_performed",
    "auto_decomposition_performed",
)

COMMANDER_MANUAL_ASSIGNMENT_PLAN_GUARDRAIL_NOTE = (
    "Commander Manual Assignment Plan is report-only: it maps CMD.N4 "
    "preflighted sub-bosses to advisory role labels for human review and "
    "preparation only. It does not launch workers, bind executable worker IDs, "
    "call models, change routing, mutate source preflight or fracture tree "
    "artifacts, apply patches, run validation, run benchmarks, invoke MCP "
    "tools, execute Dream actions, apply Replay janitor actions, use "
    "Docker/subprocess, contact networks, write databases, or change auth "
    "policy."
)

EXECUTABLE_WORKER_KEYS: tuple[str, ...] = (
    "worker_binding",
    "worker_id",
    "worker",
    "assigned_worker",
    "executable_worker",
    "execution_worker",
    "launch_worker",
)

AUTO_FLAG_KEYS: tuple[str, ...] = (
    "auto_apply",
    "auto_run",
    "auto_merge",
    "automatic_apply",
    "automatic_run",
    "automatic_merge",
)

MODEL_AUTHORITY_KEYS: tuple[str, ...] = (
    "model_authority",
    "authority_model",
    "authoritative_model",
    "model_name_as_authority",
)

MODEL_ID_KEYS: tuple[str, ...] = (
    "model",
    "model_id",
    "model_name",
    "llm",
    "authority",
    "execution_authority",
)

MODEL_ID_TOKENS: tuple[str, ...] = (
    "gpt-",
    "gpt_",
    "claude",
    "gemini",
    "llama",
    "mistral",
    "mixtral",
    "deepseek",
    "o1",
    "o3",
    "o4",
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


def _split_segments(value: str) -> list[str]:
    return [segment for segment in value.replace("\\", "/").split("/") if segment]


def _path_has_traversal(value: str) -> bool:
    return any(segment == ".." for segment in _split_segments(value))


def _input_path_blockers(path: str | Path | None, label: str) -> list[str]:
    if path is None or str(path).strip() == "":
        return [f"{label} path is required"]
    text = str(path).strip()
    if _path_has_traversal(text):
        return [f"{label} path must not contain traversal segments"]
    return []


def _safe_identifier(value: Any, field: str) -> tuple[str, list[str]]:
    text = str(value or "").strip()
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    blockers: list[str] = []
    if not text:
        blockers.append(f"{field} must be a non-empty path-safe identifier")
    if text in {".", ".."} or ".." in text:
        blockers.append(f"{field} must not contain path traversal segments")
    if "/" in text or "\\" in text:
        blockers.append(f"{field} must not contain path separators")
    if text.startswith("."):
        blockers.append(f"{field} must not start with a dot")
    if any(ch not in allowed for ch in text):
        blockers.append(f"{field} may contain only letters, numbers, dot, dash, and underscore")
    return text, sorted(set(blockers))


def _looks_like_model_id(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    return any(text == token or text.startswith(token) or f"/{token}" in text for token in MODEL_ID_TOKENS)


def _scan_forbidden_bindings(value: Any, label: str, path: str = "") -> list[str]:
    blockers: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            current = f"{path}.{key_text}" if path else key_text
            if key_text in EXECUTABLE_WORKER_KEYS and bool(item):
                blockers.append(f"{label} defines executable worker binding at {current}")
            if key_text in AUTO_FLAG_KEYS and item is True:
                blockers.append(f"{label} enables hidden auto flag at {current}")
            if key_text in MODEL_AUTHORITY_KEYS and str(item or "").strip():
                blockers.append(f"{label} treats a model name as authority at {current}")
            if key_text in MODEL_ID_KEYS and _looks_like_model_id(item):
                blockers.append(f"{label} binds model ID as authority at {current}")
            blockers += _scan_forbidden_bindings(item, label, current)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            current = f"{path}[{index}]" if path else f"[{index}]"
            blockers += _scan_forbidden_bindings(item, label, current)
    return blockers


def read_json_input(path: str | Path | None, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Read JSON input and return blockers instead of raising."""
    blockers = _input_path_blockers(path, label)
    if blockers:
        return None, blockers
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


def _catalog_copy() -> dict[str, dict[str, list[str]]]:
    return {
        role: {
            "best_for": list(meta.get("best_for") or []),
            "not_allowed_to": list(meta.get("not_allowed_to") or []),
        }
        for role, meta in DEFAULT_ROLE_CATALOG.items()
    }


def _normalize_role_catalog(
    role_catalog_data: dict[str, Any] | None,
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    warnings: list[str] = []
    blockers: list[str] = []
    catalog = _catalog_copy()

    if role_catalog_data is not None:
        source: Any = role_catalog_data.get("advisory_roles") if isinstance(role_catalog_data, dict) else None
        if source is None:
            source = role_catalog_data
        if not isinstance(source, dict):
            blockers.append("role catalog must contain a JSON object")
            source = {}
        blockers += _scan_forbidden_bindings(source, "role catalog")
        for role_name, raw_meta in source.items():
            role = str(role_name or "").strip()
            safe_role, role_blockers = _safe_identifier(role, f"role {role}")
            blockers += role_blockers
            if _looks_like_model_id(role):
                blockers.append(f"role catalog role {role} looks like a model ID, not an advisory label")
            if not isinstance(raw_meta, dict):
                blockers.append(f"role catalog role {role} must be an object")
                continue
            base = catalog.get(safe_role, {"best_for": [], "not_allowed_to": []})
            best_for = _strings(raw_meta.get("best_for")) or list(base.get("best_for") or [])
            not_allowed_to = _strings(raw_meta.get("not_allowed_to")) or list(base.get("not_allowed_to") or [])
            if not best_for:
                warnings.append(f"role catalog role {safe_role} has no best_for entries")
            if not not_allowed_to:
                warnings.append(f"role catalog role {safe_role} has no not_allowed_to entries")
            catalog[safe_role] = {
                "best_for": best_for,
                "not_allowed_to": not_allowed_to,
            }

    decorated: dict[str, dict[str, Any]] = {}
    for role in sorted(catalog):
        decorated[role] = {
            "best_for": list(catalog[role].get("best_for") or []),
            "not_allowed_to": list(catalog[role].get("not_allowed_to") or []),
            "role_binding": "advisory_label_only",
            "executable_worker_id": "",
            "model_id": "",
        }
    return decorated, sorted(set(warnings)), sorted(set(blockers))


def _preflight_identity(preflight_data: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(preflight_data.get("tree_id") or "").strip(),
        str(preflight_data.get("boss_id") or "").strip(),
        str(preflight_data.get("title") or "").strip(),
    )


def _normalized_findings(preflight_data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    warnings: list[str] = []
    blockers: list[str] = []
    raw_findings = preflight_data.get("per_sub_boss_findings")
    if not isinstance(raw_findings, list):
        return [], warnings, ["preflight per_sub_boss_findings must be a list"]

    findings: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_findings):
        if not isinstance(raw, dict):
            blockers.append(f"preflight per_sub_boss_findings[{index}] must be an object")
            continue
        raw_id = str(raw.get("sub_boss_id") or "").strip()
        sub_boss_id, id_blockers = _safe_identifier(raw_id, f"sub_boss_id {raw_id}")
        blockers += id_blockers
        status = str(raw.get("preflight_status") or "").strip()
        if status not in PREFLIGHT_STATUSES:
            warnings.append(
                f"sub_boss {sub_boss_id} preflight_status {status or '(missing)'} is not recognized"
            )
            status = "preflight_incomplete"
        risk_level = str(raw.get("risk_level") or "unknown").strip().lower()
        if risk_level not in {"low", "medium", "high", "unknown"}:
            warnings.append(f"sub_boss {sub_boss_id} risk_level {risk_level} is not recognized; defaulted to unknown")
            risk_level = "unknown"
        findings.append(
            {
                "sub_boss_id": sub_boss_id,
                "title": str(raw.get("title") or ""),
                "status": str(raw.get("status") or ""),
                "preflight_status": status,
                "risk_level": risk_level,
                "allowed_files": _strings(raw.get("allowed_files")),
                "forbidden_files": _strings(raw.get("forbidden_files")),
                "evidence_required": _strings(raw.get("evidence_required")),
                "warnings": _strings(raw.get("warnings")),
                "incomplete_reasons": _strings(raw.get("incomplete_reasons")),
                "blocked_reasons": _strings(raw.get("blocked_reasons")),
            }
        )
    return findings, sorted(set(warnings)), sorted(set(blockers))


def _add_role(roles: list[str], reasons: list[str], role: str, reason: str) -> None:
    if role not in roles:
        roles.append(role)
    if reason not in reasons:
        reasons.append(reason)


def _context_text(finding: dict[str, Any]) -> str:
    values: list[str] = [
        str(finding.get("title") or ""),
        " ".join(finding.get("allowed_files") or []),
        " ".join(finding.get("evidence_required") or []),
        " ".join(finding.get("warnings") or []),
        " ".join(finding.get("incomplete_reasons") or []),
        " ".join(finding.get("blocked_reasons") or []),
    ]
    return " ".join(values).lower()


def _missing_evidence(finding: dict[str, Any]) -> bool:
    if not finding.get("evidence_required"):
        return True
    text = _context_text(finding)
    return "missing evidence" in text or "evidence_required must be non-empty" in text


def _is_ui_scope(finding: dict[str, Any]) -> bool:
    text = _context_text(finding)
    return any(token in text for token in ("ui", "web/", "frontend", "template", ".html", ".css", "copy review"))


def _is_test_scope(finding: dict[str, Any]) -> bool:
    text = _context_text(finding)
    return "tests/" in text or "test_" in text or "test plan" in text or "edge cases" in text


def _is_docs_scope(finding: dict[str, Any]) -> bool:
    text = _context_text(finding)
    return "docs/" in text or "roadmap" in text or "phase_registry" in text or "documentation" in text


def _roles_for_finding(
    finding: dict[str, Any],
    advisory_roles: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    roles: list[str] = []
    reasons: list[str] = []
    warnings: list[str] = []
    status = str(finding.get("preflight_status") or "")
    sub_boss_id = str(finding.get("sub_boss_id") or "")

    if status == "preflight_blocked":
        return [], [f"sub_boss {sub_boss_id} is preflight_blocked and receives no assignment"], []
    if status == "preflight_incomplete":
        _add_role(roles, reasons, "planner", "preflight_incomplete requires scope/readiness planning")
        _add_role(roles, reasons, "risk_auditor", "preflight_incomplete requires guardrail review")
        _add_role(roles, reasons, "evidence_checker", "preflight_incomplete requires evidence review")
    elif status == "preflight_ready_with_warnings":
        _add_role(roles, reasons, "reviewer", "preflight_ready_with_warnings requires reviewer coverage")
        _add_role(roles, reasons, "risk_auditor", "preflight_ready_with_warnings requires risk coverage")
    else:
        _add_role(roles, reasons, "planner", "preflight_ready may receive planning coverage")
        _add_role(roles, reasons, "implementer", "preflight_ready may receive patch proposal preparation")
        _add_role(roles, reasons, "reviewer", "preflight_ready may receive review coverage")
        _add_role(roles, reasons, "evidence_checker", "preflight_ready may receive evidence coverage")

    risk_level = str(finding.get("risk_level") or "unknown")
    if risk_level in {"high", "unknown"}:
        _add_role(roles, reasons, "risk_auditor", f"{risk_level} risk requires risk_auditor coverage")
    if _missing_evidence(finding):
        _add_role(roles, reasons, "evidence_checker", "missing evidence requires evidence_checker coverage")
    if _is_ui_scope(finding):
        _add_role(roles, reasons, "ui_reviewer", "UI scope requires ui_reviewer coverage")
    if _is_test_scope(finding):
        _add_role(roles, reasons, "test_designer", "test-heavy scope requires test_designer coverage")
    if _is_docs_scope(finding):
        _add_role(roles, reasons, "documentation_reviewer", "docs/roadmap scope requires documentation_reviewer coverage")

    available_roles: list[str] = []
    for role in roles:
        if role in advisory_roles:
            available_roles.append(role)
        else:
            warnings.append(f"sub_boss {sub_boss_id} advisory role {role} is missing from role catalog")
    return available_roles, reasons, warnings


def _assignment_status(
    *,
    blockers: list[str],
    warnings: list[str],
    findings: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    unassigned: list[dict[str, Any]],
) -> str:
    if blockers:
        return "assignment_blocked"
    if not findings:
        return "assignment_blocked"
    if not assignments:
        return "assignment_incomplete"
    if all(finding.get("preflight_status") in {"preflight_blocked", "preflight_incomplete"} for finding in findings):
        return "assignment_incomplete"
    if warnings or unassigned:
        return "assignment_ready_with_warnings"
    return "assignment_ready"


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def build_commander_manual_assignment_plan(
    *,
    preflight_path: str | Path,
    preflight_data: dict[str, Any] | None = None,
    role_catalog_path: str | Path | None = None,
    role_catalog_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
    role_catalog_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic CMD.N5 advisory assignment plan report."""
    blockers = list(input_blockers or [])
    blockers += _input_path_blockers(preflight_path, "preflight")
    if role_catalog_path is not None:
        blockers += _input_path_blockers(role_catalog_path, "role catalog")
    blockers += list(role_catalog_blockers or [])

    if preflight_data is None:
        preflight_data = {}
        blockers.append("preflight is missing or malformed")

    if not isinstance(preflight_data, dict):
        preflight_data = {}
        blockers.append("preflight must contain a JSON object")

    tree_id, boss_id, title = _preflight_identity(preflight_data)
    safe_tree_id, tree_id_blockers = _safe_identifier(tree_id, "tree_id")
    safe_boss_id, boss_id_blockers = _safe_identifier(boss_id, "boss_id")
    blockers += tree_id_blockers + boss_id_blockers

    if preflight_data.get("report_kind") != PREFLIGHT_REPORT_KIND:
        blockers.append("preflight report_kind must be commander_preflight_contract")

    blockers += _scan_forbidden_bindings(preflight_data, "preflight")

    advisory_roles, role_warnings, role_blockers = _normalize_role_catalog(role_catalog_data)
    warnings = list(role_warnings)
    blockers += role_blockers

    findings, finding_warnings, finding_blockers = _normalized_findings(preflight_data)
    warnings += finding_warnings
    blockers += finding_blockers
    if not findings:
        blockers.append("no evaluable sub-bosses")

    assignments: list[dict[str, Any]] = []
    unassigned: list[dict[str, Any]] = []
    risk_coverage: list[dict[str, Any]] = []
    evidence_coverage: list[dict[str, Any]] = []

    plan_level_blocked = bool(blockers)
    for finding in findings:
        sub_boss_id = str(finding.get("sub_boss_id") or "")
        status = str(finding.get("preflight_status") or "")
        risk_level = str(finding.get("risk_level") or "unknown")

        if plan_level_blocked:
            roles: list[str] = []
            assignment_reasons = ["plan-level blocker prevents advisory assignment"]
            role_warnings: list[str] = []
        else:
            roles, assignment_reasons, role_warnings = _roles_for_finding(finding, advisory_roles)
            warnings += role_warnings

        if status == "preflight_blocked" or not roles:
            reason = (
                "preflight_blocked sub-boss is not eligible for advisory assignment"
                if status == "preflight_blocked"
                else "no assignable advisory roles were available"
            )
            unassigned.append(
                {
                    "sub_boss_id": sub_boss_id,
                    "title": finding.get("title", ""),
                    "preflight_status": status,
                    "risk_level": risk_level,
                    "reason": reason,
                    "advisory_roles": [],
                    "executable_assignment": False,
                    "executable_worker_id": "",
                    "model_id": "",
                }
            )
        else:
            assignments.append(
                {
                    "assignment_id": f"{sub_boss_id}-advisory-assignment",
                    "sub_boss_id": sub_boss_id,
                    "title": finding.get("title", ""),
                    "preflight_status": status,
                    "risk_level": risk_level,
                    "advisory_roles": roles,
                    "role_binding": "advisory_labels_only",
                    "executable_assignment": False,
                    "executable_worker_id": "",
                    "model_id": "",
                    "assignment_reasons": assignment_reasons,
                    "source_evidence_required": list(finding.get("evidence_required") or []),
                    "source_allowed_files": list(finding.get("allowed_files") or []),
                    "warnings": list(finding.get("warnings") or []),
                    "incomplete_reasons": list(finding.get("incomplete_reasons") or []),
                    "blocked_reasons": list(finding.get("blocked_reasons") or []),
                }
            )

        if status in {"preflight_incomplete", "preflight_ready_with_warnings"}:
            warnings.append(f"sub_boss {sub_boss_id} assignment carries preflight status {status}")
        if status == "preflight_blocked":
            warnings.append(f"sub_boss {sub_boss_id} is unassigned because preflight is blocked")
        if risk_level in {"high", "unknown"}:
            warnings.append(f"sub_boss {sub_boss_id} risk_level {risk_level} requires risk_auditor coverage")

        risk_coverage.append(
            {
                "sub_boss_id": sub_boss_id,
                "risk_level": risk_level,
                "risk_auditor_assigned": "risk_auditor" in roles,
                "coverage_required": risk_level in {"high", "unknown"},
            }
        )
        evidence_coverage.append(
            {
                "sub_boss_id": sub_boss_id,
                "evidence_required_count": len(finding.get("evidence_required") or []),
                "missing_evidence": _missing_evidence(finding),
                "evidence_checker_assigned": "evidence_checker" in roles,
            }
        )

    warnings = sorted(set(warnings))
    blockers = sorted(set(blockers))
    assignment_status = _assignment_status(
        blockers=blockers,
        warnings=warnings,
        findings=findings,
        assignments=assignments,
        unassigned=unassigned,
    )
    plan_tree_id = safe_tree_id if not tree_id_blockers else tree_id

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": COMMANDER_MANUAL_ASSIGNMENT_PLAN_GUARDRAIL_NOTE,
        "plan_id": f"cmd-n5-{plan_tree_id or INVALID_TREE_ID_DIR}-manual-assignment-plan",
        "tree_id": plan_tree_id,
        "boss_id": safe_boss_id if not boss_id_blockers else boss_id,
        "title": title,
        "source_preflight_path": str(preflight_path or ""),
        "source_preflight": {
            "report_kind": preflight_data.get("report_kind", ""),
            "preflight_status": preflight_data.get("preflight_status", ""),
            "evaluated_sub_boss_count": len(findings),
            "source_tree_path": preflight_data.get("source_tree_path", ""),
        },
        "assignment_status": assignment_status,
        "advisory_roles": advisory_roles,
        "assignment_rules": list(ASSIGNMENT_RULES),
        "assignments": assignments,
        "unassigned_sub_bosses": unassigned,
        "risk_coverage": risk_coverage,
        "evidence_coverage": evidence_coverage,
        "human_approval_boundary": {
            "required_before_patch_apply": True,
            "required_before_worker_launch": True,
            "required_before_file_mutation": True,
            "assignment_authority": "human_only",
        },
        "warnings": warnings,
        "blocked_reasons": blockers,
        "guardrails": _guardrails(),
        "assignment_statuses": list(ASSIGNMENT_STATUSES),
        "boundaries": [
            "CMD.N5 is report-only.",
            "CMD.N5 uses advisory assignment labels only.",
            "CMD.N5 does not launch workers.",
            "CMD.N5 does not bind executable worker IDs.",
            "CMD.N5 does not bind real model IDs as authority.",
            "CMD.N5 does not call models.",
            "CMD.N5 does not run validation or benchmarks.",
            "CMD.N5 does not apply patches.",
            "CMD.N5 does not mutate the source preflight or fracture tree.",
            "CMD.N5 does not change routing, auth policy, or route behavior.",
            "CMD.N5 writes assignment artifacts only.",
        ],
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def render_commander_manual_assignment_plan_markdown(report: dict[str, Any]) -> str:
    """Render a CMD.N5 assignment plan report as Markdown."""
    source = report.get("source_preflight") if isinstance(report.get("source_preflight"), dict) else {}
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    lines: list[str] = [
        "# Commander Manual Assignment Plan",
        "",
        f"> {report.get('guardrail_note', COMMANDER_MANUAL_ASSIGNMENT_PLAN_GUARDRAIL_NOTE)}",
        "",
        "_Report only: CMD.N5 assigns advisory role labels for human review/preparation. It runs nothing and changes no routing, source artifact, worker, model, validation, benchmark, or patch behavior._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Plan id:** `{_md(report.get('plan_id', ''))}`",
        f"- **Tree id:** `{_md(report.get('tree_id', ''))}`",
        f"- **Boss id:** `{_md(report.get('boss_id', ''))}`",
        f"- **Title:** {_md(report.get('title', ''))}",
        f"- **Assignment status:** `{_md(report.get('assignment_status', ''))}`",
        f"- **Assignments:** {len(report.get('assignments') or [])}",
        f"- **Unassigned sub-bosses:** {len(report.get('unassigned_sub_bosses') or [])}",
        "",
        "## Source Preflight",
        "",
        f"- **Preflight path:** `{_md(report.get('source_preflight_path', ''))}`",
        f"- **Report kind:** `{_md(source.get('report_kind', ''))}`",
        f"- **Preflight status:** `{_md(source.get('preflight_status', ''))}`",
        f"- **Evaluated sub-bosses:** {source.get('evaluated_sub_boss_count', 0)}",
        f"- **Source tree path:** `{_md(source.get('source_tree_path', ''))}`",
        "",
        "## Advisory Role Catalog",
        "",
        "| Role | Best for | Not allowed to | Binding |",
        "| --- | --- | --- | --- |",
    ]
    roles = report.get("advisory_roles") if isinstance(report.get("advisory_roles"), dict) else {}
    for role_name in sorted(roles):
        role = roles[role_name] if isinstance(roles[role_name], dict) else {}
        lines.append(
            "| {role} | {best_for} | {not_allowed} | {binding} |".format(
                role=_md(role_name),
                best_for=_md(", ".join(role.get("best_for") or [])),
                not_allowed=_md(", ".join(role.get("not_allowed_to") or [])),
                binding=_md(role.get("role_binding", "")),
            )
        )

    lines += [
        "",
        "## Assignment Rules",
        "",
    ]
    _render_list(lines, list(report.get("assignment_rules") or []))

    lines += [
        "## Per-Sub-Boss Assignments",
        "",
    ]
    assignments = report.get("assignments") if isinstance(report.get("assignments"), list) else []
    if assignments:
        lines += [
            "| Sub-boss | Preflight | Risk | Advisory roles | Executable assignment |",
            "| --- | --- | --- | --- | --- |",
        ]
        for assignment in assignments:
            lines.append(
                "| {sid} | {preflight} | {risk} | {roles} | {executable} |".format(
                    sid=_md(assignment.get("sub_boss_id", "")),
                    preflight=_md(assignment.get("preflight_status", "")),
                    risk=_md(assignment.get("risk_level", "")),
                    roles=_md(", ".join(assignment.get("advisory_roles") or [])),
                    executable=str(bool(assignment.get("executable_assignment"))).lower(),
                )
            )
    else:
        lines.append("_None._")
    lines.append("")

    lines += [
        "## Unassigned Sub-Bosses",
        "",
    ]
    unassigned = report.get("unassigned_sub_bosses") if isinstance(report.get("unassigned_sub_bosses"), list) else []
    if unassigned:
        lines += [
            "| Sub-boss | Preflight | Risk | Reason | Executable assignment |",
            "| --- | --- | --- | --- | --- |",
        ]
        for row in unassigned:
            lines.append(
                "| {sid} | {preflight} | {risk} | {reason} | {executable} |".format(
                    sid=_md(row.get("sub_boss_id", "")),
                    preflight=_md(row.get("preflight_status", "")),
                    risk=_md(row.get("risk_level", "")),
                    reason=_md(row.get("reason", "")),
                    executable=str(bool(row.get("executable_assignment"))).lower(),
                )
            )
    else:
        lines.append("_None._")
    lines.append("")

    lines += [
        "## Risk Coverage",
        "",
    ]
    risk_rows = report.get("risk_coverage") if isinstance(report.get("risk_coverage"), list) else []
    if risk_rows:
        for row in risk_rows:
            lines.append(
                f"- `{_md(row.get('sub_boss_id', ''))}` risk=`{_md(row.get('risk_level', ''))}`, risk_auditor_assigned={str(bool(row.get('risk_auditor_assigned'))).lower()}"
            )
    else:
        lines.append("_None._")
    lines.append("")

    lines += [
        "## Evidence Coverage",
        "",
    ]
    evidence_rows = report.get("evidence_coverage") if isinstance(report.get("evidence_coverage"), list) else []
    if evidence_rows:
        for row in evidence_rows:
            lines.append(
                f"- `{_md(row.get('sub_boss_id', ''))}` evidence_required_count={row.get('evidence_required_count', 0)}, missing_evidence={str(bool(row.get('missing_evidence'))).lower()}, evidence_checker_assigned={str(bool(row.get('evidence_checker_assigned'))).lower()}"
            )
    else:
        lines.append("_None._")
    lines.append("")

    human = report.get("human_approval_boundary") if isinstance(report.get("human_approval_boundary"), dict) else {}
    lines += [
        "## Human Approval Boundary",
        "",
        f"- `{_md(json.dumps(human, sort_keys=True))}`",
        "",
        "## Warnings",
        "",
    ]
    _render_list(lines, list(report.get("warnings") or []))

    lines += ["## Blocked Reasons", ""]
    _render_list(lines, list(report.get("blocked_reasons") or []))

    lines += ["## Boundaries / Guardrails", ""]
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: {str(bool(guardrails[key])).lower()}")
    for boundary in report.get("boundaries") or []:
        lines.append(f"- {_md(boundary)}")

    lines += [
        "",
        "## Recommended Next Phase",
        "",
        f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
        f"- **Title:** {_md(next_phase.get('title', ''))}",
        f"- **Reason:** {_md(next_phase.get('reason', ''))}",
        f"- **Alternative:** {_md(next_phase.get('alternative', ''))}",
        "",
    ]
    return "\n".join(lines)


def write_commander_manual_assignment_plan(
    *,
    preflight_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    role_catalog_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build and write CMD.N5 JSON + Markdown assignment artifacts."""
    preflight_data, read_blockers = read_json_input(preflight_path, "preflight")
    role_catalog_data: dict[str, Any] | None = None
    role_read_blockers: list[str] = []
    if role_catalog_path is not None:
        role_catalog_data, role_read_blockers = read_json_input(role_catalog_path, "role catalog")
    report = build_commander_manual_assignment_plan(
        preflight_path=preflight_path,
        preflight_data=preflight_data,
        role_catalog_path=role_catalog_path,
        role_catalog_data=role_catalog_data,
        input_blockers=read_blockers,
        role_catalog_blockers=role_read_blockers,
    )
    safe_tree_id, tree_id_blockers = _safe_identifier(report.get("tree_id"), "tree_id")
    target_id = safe_tree_id if not tree_id_blockers else INVALID_TREE_ID_DIR
    out_dir = Path(output_dir) / target_id
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_commander_manual_assignment_plan_markdown(report), encoding="utf-8")
    return {
        "ok": report.get("assignment_status") != "assignment_blocked",
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
