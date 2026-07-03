"""CMD.N6 - Commander Assignment Review Pack (report-only).

Combines CMD.N3 fracture tree, CMD.N4 preflight contract, and CMD.N5 manual
assignment plan artifacts into one deterministic human review pack. CMD.N6
writes review-pack artifacts only. It does not launch workers, bind executable
workers or real model IDs, call models, run validation, run benchmarks, apply
patches, mutate source artifacts, route tasks, invoke MCP tools, execute Dream
actions, apply Replay janitor actions, use Docker/subprocess, contact networks,
write databases, or change auth policy.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "commander_assignment_review_pack"
JSON_NAME = "commander_assignment_review_pack.json"
MD_NAME = "commander_assignment_review_pack.md"

DEFAULT_OUTPUT_ROOT = Path(".agent") / "commander" / "assignment_review_pack"
INVALID_TREE_ID_DIR = "invalid_tree_id"

TREE_REPORT_KIND = "commander_fracture_tree_registry"
PREFLIGHT_REPORT_KIND = "commander_preflight_contract"
ASSIGNMENT_REPORT_KIND = "commander_manual_assignment_plan"

ELIGIBLE_SUB_BOSS_STATUSES: tuple[str, ...] = ("ready_for_preflight", "proposed")
REVIEW_STATUSES: tuple[str, ...] = (
    "review_pack_ready",
    "review_pack_ready_with_warnings",
    "review_pack_incomplete",
    "review_pack_blocked",
)

EXECUTABLE_WORKER_KEYS: tuple[str, ...] = (
    "worker_binding",
    "worker_id",
    "worker",
    "assigned_worker",
    "executable_worker",
    "execution_worker",
    "launch_worker",
    "executable_assignment",
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
    "routing_change_performed",
    "source_artifact_mutation_performed",
    "automatic_decomposition_performed",
    "auto_run_performed",
    "auto_apply_performed",
    "auto_merge_performed",
)

HUMAN_REVIEW_CHECKLIST: tuple[str, ...] = (
    "confirm boss goal is still valid",
    "confirm fracture tree matches intended scope",
    "confirm file scope is bounded",
    "confirm forbidden files are respected",
    "confirm evidence requirements are clear",
    "confirm rollback boundaries are clear",
    "confirm advisory roles are labels only",
    "confirm no worker/model is authorized to execute",
    "confirm validation/benchmark runs remain human-triggered",
    "confirm patch apply remains human-triggered",
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "CMD.CLOSE",
    "title": "Commander Planning Branch Checkpoint",
    "reason": (
        "After CMD.N1-CMD.N6, Commander has the half-life stagnation model, "
        "manual fracture report, fracture tree registry, preflight contract, "
        "manual assignment plan, and combined review pack. That is enough to "
        "freeze the planning branch before any execution-related Commander work."
    ),
}

COMMANDER_ASSIGNMENT_REVIEW_PACK_GUARDRAIL_NOTE = (
    "Commander Assignment Review Pack is report-only: it reads deterministic "
    "CMD.N3, CMD.N4, and CMD.N5 artifacts and writes JSON plus Markdown review "
    "artifacts only. It does not launch workers, call models, run tools, run "
    "validation or benchmarks, apply patches, mutate source artifacts, route "
    "tasks, invoke MCP tools, execute Dream actions, apply Replay janitor "
    "actions, use Docker/subprocess, contact networks, write databases, or "
    "change auth policy."
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "review-pack only",
    "deterministic/artifact input only",
    "no model call",
    "no executable worker binding",
    "no real model binding",
    "no automatic decomposition",
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
    "no routing change",
    "no mutation of source artifacts",
    "writes review-pack artifacts only",
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
            if key_text.endswith("_performed") and item is True:
                blockers.append(f"{label} reports forbidden guardrail action at {current}")
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


def _identity(data: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(data.get("tree_id") or "").strip(),
        str(data.get("boss_id") or "").strip(),
        str(data.get("title") or "").strip(),
    )


def _dict_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _row_by_sub_boss(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("sub_boss_id") or "").strip(): row for row in rows if str(row.get("sub_boss_id") or "").strip()}


def _assignment_rows_by_sub_boss(assignment_data: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    assignments = _dict_rows(assignment_data.get("assignments"))
    unassigned = _dict_rows(assignment_data.get("unassigned_sub_bosses"))
    return _row_by_sub_boss(assignments), _row_by_sub_boss(unassigned)


def _context_text(
    sub: dict[str, Any],
    finding: dict[str, Any] | None,
    assignment: dict[str, Any] | None,
) -> str:
    values: list[str] = [
        str(sub.get("title") or ""),
        str(sub.get("scope") or ""),
        " ".join(_strings(sub.get("allowed_files"))),
        " ".join(_strings(sub.get("evidence_required"))),
    ]
    if finding:
        values += [
            str(finding.get("title") or ""),
            " ".join(_strings(finding.get("allowed_files"))),
            " ".join(_strings(finding.get("evidence_required"))),
            " ".join(_strings(finding.get("warnings"))),
            " ".join(_strings(finding.get("incomplete_reasons"))),
            " ".join(_strings(finding.get("blocked_reasons"))),
        ]
    if assignment:
        values += [
            " ".join(_strings(assignment.get("source_allowed_files"))),
            " ".join(_strings(assignment.get("source_evidence_required"))),
            " ".join(_strings(assignment.get("warnings"))),
            " ".join(_strings(assignment.get("incomplete_reasons"))),
            " ".join(_strings(assignment.get("blocked_reasons"))),
        ]
    return " ".join(values).lower()


def _is_ui_scope(text: str) -> bool:
    return any(token in text for token in ("ui", "web/", "frontend", "template", ".html", ".css", "copy review"))


def _is_test_scope(text: str) -> bool:
    return "tests/" in text or "test_" in text or "test plan" in text or "edge cases" in text


def _is_docs_scope(text: str) -> bool:
    return "docs/" in text or "roadmap" in text or "phase_registry" in text or "documentation" in text


def _missing_evidence(finding: dict[str, Any] | None, evidence_required: list[str]) -> bool:
    if not evidence_required:
        return True
    if not finding:
        return False
    text = " ".join(
        _strings(finding.get("warnings"))
        + _strings(finding.get("incomplete_reasons"))
        + _strings(finding.get("blocked_reasons"))
    ).lower()
    return "missing evidence" in text or "evidence_required must be non-empty" in text


def _unique(values: list[str]) -> list[str]:
    return sorted(dict.fromkeys(value for value in values if value))


def _coverage_warning(
    *,
    sub_boss_id: str,
    roles: list[str],
    role: str,
    reason: str,
) -> str:
    if role in roles:
        return ""
    return f"sub_boss {sub_boss_id} requires {role} coverage: {reason}"


def _source_artifact_summary(
    *,
    tree_path: str | Path,
    preflight_path: str | Path,
    assignment_path: str | Path,
    tree_data: dict[str, Any],
    preflight_data: dict[str, Any],
    assignment_data: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        "tree": {
            "path": str(tree_path or ""),
            "report_kind": tree_data.get("report_kind", ""),
            "status": tree_data.get("validation_status", ""),
        },
        "preflight": {
            "path": str(preflight_path or ""),
            "report_kind": preflight_data.get("report_kind", ""),
            "status": preflight_data.get("preflight_status", ""),
        },
        "assignment": {
            "path": str(assignment_path or ""),
            "report_kind": assignment_data.get("report_kind", ""),
            "status": assignment_data.get("assignment_status", ""),
        },
    }


def _review_status(*, blockers: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blockers:
        return "review_pack_blocked"
    if incomplete:
        return "review_pack_incomplete"
    if warnings:
        return "review_pack_ready_with_warnings"
    return "review_pack_ready"


def _summaries(
    *,
    tree_data: dict[str, Any],
    preflight_data: dict[str, Any],
    assignment_data: dict[str, Any],
    sub_bosses: list[dict[str, Any]],
    preflight_findings: list[dict[str, Any]],
    assignments_by_id: dict[str, dict[str, Any]],
    unassigned_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = tree_data.get("root_boss") if isinstance(tree_data.get("root_boss"), dict) else {}
    boss_summary = {
        "boss_id": tree_data.get("boss_id", ""),
        "title": tree_data.get("title", ""),
        "root_title": root.get("title", ""),
        "commander_decision": root.get("commander_decision", ""),
        "fracture_pressure": root.get("fracture_pressure"),
        "actual_remaining": root.get("actual_remaining"),
    }
    fracture_tree_summary = {
        "validation_status": tree_data.get("validation_status", ""),
        "sub_boss_count": len(sub_bosses),
        "eligible_sub_boss_count": sum(
            1 for sub in sub_bosses if str(sub.get("status") or "") in ELIGIBLE_SUB_BOSS_STATUSES
        ),
        "total_expected_complexity": tree_data.get("total_expected_complexity"),
        "total_attempt_budget": tree_data.get("total_attempt_budget"),
        "dependency_edge_count": len(_dict_rows(tree_data.get("dependency_edges"))),
    }
    preflight_summary = {
        "preflight_status": preflight_data.get("preflight_status", ""),
        "evaluated_sub_boss_count": len(preflight_findings),
        "warning_count": len(_strings(preflight_data.get("warnings"))),
        "incomplete_reason_count": len(_strings(preflight_data.get("incomplete_reasons"))),
        "blocked_reason_count": len(_strings(preflight_data.get("blocked_reasons"))),
    }
    assignment_summary = {
        "assignment_status": assignment_data.get("assignment_status", ""),
        "assignment_count": len(assignments_by_id),
        "unassigned_sub_boss_count": len(unassigned_by_id),
        "warning_count": len(_strings(assignment_data.get("warnings"))),
        "blocked_reason_count": len(_strings(assignment_data.get("blocked_reasons"))),
    }
    return boss_summary, fracture_tree_summary, preflight_summary, assignment_summary


def build_commander_assignment_review_pack(
    *,
    tree_path: str | Path,
    preflight_path: str | Path,
    assignment_path: str | Path,
    tree_data: dict[str, Any] | None = None,
    preflight_data: dict[str, Any] | None = None,
    assignment_data: dict[str, Any] | None = None,
    input_blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic CMD.N6 review pack from already-loaded artifacts."""
    blockers = list(input_blockers or [])
    blockers += _input_path_blockers(tree_path, "tree")
    blockers += _input_path_blockers(preflight_path, "preflight")
    blockers += _input_path_blockers(assignment_path, "assignment")

    if tree_data is None:
        tree_data = {}
        blockers.append("tree is missing or malformed")
    if preflight_data is None:
        preflight_data = {}
        blockers.append("preflight is missing or malformed")
    if assignment_data is None:
        assignment_data = {}
        blockers.append("assignment is missing or malformed")
    if not isinstance(tree_data, dict):
        tree_data = {}
        blockers.append("tree must contain a JSON object")
    if not isinstance(preflight_data, dict):
        preflight_data = {}
        blockers.append("preflight must contain a JSON object")
    if not isinstance(assignment_data, dict):
        assignment_data = {}
        blockers.append("assignment must contain a JSON object")

    tree_id, tree_boss_id, tree_title = _identity(tree_data)
    preflight_tree_id, preflight_boss_id, _ = _identity(preflight_data)
    assignment_tree_id, assignment_boss_id, _ = _identity(assignment_data)
    safe_tree_id, tree_id_blockers = _safe_identifier(tree_id, "tree_id")
    safe_boss_id, boss_id_blockers = _safe_identifier(tree_boss_id, "boss_id")
    blockers += tree_id_blockers + boss_id_blockers

    if tree_data.get("report_kind") != TREE_REPORT_KIND:
        blockers.append("tree report_kind must be commander_fracture_tree_registry")
    if preflight_data.get("report_kind") != PREFLIGHT_REPORT_KIND:
        blockers.append("preflight report_kind must be commander_preflight_contract")
    if assignment_data.get("report_kind") != ASSIGNMENT_REPORT_KIND:
        blockers.append("assignment report_kind must be commander_manual_assignment_plan")

    tree_ids = [value for value in (tree_id, preflight_tree_id, assignment_tree_id) if value]
    if len(set(tree_ids)) > 1:
        blockers.append(
            "tree_id mismatch across source artifacts: "
            + ", ".join(f"{label}={value or '(missing)'}" for label, value in (
                ("tree", tree_id),
                ("preflight", preflight_tree_id),
                ("assignment", assignment_tree_id),
            ))
        )
    boss_ids = [value for value in (tree_boss_id, preflight_boss_id, assignment_boss_id) if value]
    if len(set(boss_ids)) > 1:
        blockers.append(
            "boss_id mismatch across source artifacts: "
            + ", ".join(f"{label}={value or '(missing)'}" for label, value in (
                ("tree", tree_boss_id),
                ("preflight", preflight_boss_id),
                ("assignment", assignment_boss_id),
            ))
        )

    blockers += _scan_forbidden_bindings(tree_data, "tree")
    blockers += _scan_forbidden_bindings(preflight_data, "preflight")
    blockers += _scan_forbidden_bindings(assignment_data, "assignment")

    if tree_data.get("validation_status") == "blocked":
        blockers.append("tree validation_status is blocked")
    if preflight_data.get("preflight_status") == "preflight_blocked":
        blockers.append("preflight_status is preflight_blocked")
    if assignment_data.get("assignment_status") == "assignment_blocked":
        blockers.append("assignment_status is assignment_blocked")

    sub_bosses = _dict_rows(tree_data.get("sub_bosses"))
    preflight_findings = _dict_rows(preflight_data.get("per_sub_boss_findings"))
    preflight_by_id = _row_by_sub_boss(preflight_findings)
    assignments_by_id, unassigned_by_id = _assignment_rows_by_sub_boss(assignment_data)
    assignment_coverage_ids = set(assignments_by_id) | set(unassigned_by_id)

    tree_sub_ids = {str(sub.get("sub_boss_id") or "").strip() for sub in sub_bosses if str(sub.get("sub_boss_id") or "").strip()}
    eligible_sub_ids = {
        str(sub.get("sub_boss_id") or "").strip()
        for sub in sub_bosses
        if str(sub.get("sub_boss_id") or "").strip()
        and str(sub.get("status") or "") in ELIGIBLE_SUB_BOSS_STATUSES
    }

    warnings: list[str] = []
    incomplete: list[str] = []
    warnings += _strings(tree_data.get("warnings"))
    warnings += _strings(preflight_data.get("warnings"))
    warnings += _strings(assignment_data.get("warnings"))

    extra_preflight_ids = sorted(set(preflight_by_id) - tree_sub_ids)
    for sub_id in extra_preflight_ids:
        blockers.append(f"preflight contains unknown sub_boss_id not present in tree: {sub_id}")
    extra_assignment_ids = sorted(assignment_coverage_ids - tree_sub_ids)
    for sub_id in extra_assignment_ids:
        blockers.append(f"assignment contains unknown sub_boss_id not present in tree: {sub_id}")

    missing_preflight = sorted(eligible_sub_ids - set(preflight_by_id))
    for sub_id in missing_preflight:
        message = f"sub_boss {sub_id} missing preflight coverage"
        warnings.append(message)
        incomplete.append(message)

    missing_assignment = sorted(eligible_sub_ids - assignment_coverage_ids)
    for sub_id in missing_assignment:
        message = f"sub_boss {sub_id} missing assignment coverage"
        warnings.append(message)
        incomplete.append(message)

    per_sub_boss_review: list[dict[str, Any]] = []
    risk_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []

    for sub in sub_bosses:
        sub_id = str(sub.get("sub_boss_id") or "").strip()
        finding = preflight_by_id.get(sub_id)
        assignment = assignments_by_id.get(sub_id)
        unassigned = unassigned_by_id.get(sub_id)
        roles = _strings(assignment.get("advisory_roles")) if assignment else []
        preflight_status = str((finding or {}).get("preflight_status") or "not_evaluated")
        risk_level = str(
            (finding or {}).get("risk_level")
            or (assignment or {}).get("risk_level")
            or sub.get("risk_level")
            or "unknown"
        ).strip().lower()
        if risk_level not in {"low", "medium", "high", "unknown"}:
            warnings.append(f"sub_boss {sub_id} risk_level {risk_level} is not recognized; defaulted to unknown")
            risk_level = "unknown"
        evidence_required = _strings((finding or {}).get("evidence_required")) or _strings(sub.get("evidence_required"))
        rollback_boundary = str((finding or {}).get("rollback_boundary") or sub.get("rollback_boundary") or "").strip()
        dependencies = _strings(sub.get("dependencies"))

        sub_warnings: list[str] = []
        sub_blockers: list[str] = []
        sub_warnings += _strings((finding or {}).get("warnings"))
        sub_warnings += _strings((finding or {}).get("incomplete_reasons"))
        sub_warnings += _strings((assignment or {}).get("warnings"))
        sub_warnings += _strings((assignment or {}).get("incomplete_reasons"))
        sub_blockers += _strings((finding or {}).get("blocked_reasons"))
        sub_blockers += _strings((assignment or {}).get("blocked_reasons"))
        if unassigned and str(unassigned.get("reason") or "").strip():
            sub_warnings.append(str(unassigned.get("reason") or "").strip())

        status = str(sub.get("status") or "")
        if status == "blocked" and roles:
            message = f"blocked sub_boss {sub_id} has advisory assignment coverage instead of unassigned representation"
            blockers.append(message)
            sub_blockers.append(message)

        context = _context_text(sub, finding, assignment)
        missing_evidence = _missing_evidence(finding, evidence_required)
        if risk_level in {"high", "unknown"}:
            sub_warnings.append(f"sub_boss {sub_id} risk_level {risk_level} requires human review")
            warning = _coverage_warning(
                sub_boss_id=sub_id,
                roles=roles,
                role="risk_auditor",
                reason=f"{risk_level} risk",
            )
            if warning:
                sub_warnings.append(warning)
                warnings.append(warning)
        if missing_evidence:
            sub_warnings.append(f"sub_boss {sub_id} has missing evidence requirements")
            warning = _coverage_warning(
                sub_boss_id=sub_id,
                roles=roles,
                role="evidence_checker",
                reason="missing evidence",
            )
            if warning:
                sub_warnings.append(warning)
                warnings.append(warning)
        if _is_ui_scope(context):
            warning = _coverage_warning(sub_boss_id=sub_id, roles=roles, role="ui_reviewer", reason="UI scope")
            if warning:
                sub_warnings.append(warning)
                warnings.append(warning)
        if _is_test_scope(context):
            warning = _coverage_warning(sub_boss_id=sub_id, roles=roles, role="test_designer", reason="test scope")
            if warning:
                sub_warnings.append(warning)
                warnings.append(warning)
        if _is_docs_scope(context):
            warning = _coverage_warning(
                sub_boss_id=sub_id,
                roles=roles,
                role="documentation_reviewer",
                reason="docs/roadmap scope",
            )
            if warning:
                sub_warnings.append(warning)
                warnings.append(warning)
        if preflight_status == "preflight_incomplete":
            sub_warnings.append(f"sub_boss {sub_id} is preflight_incomplete")
        if preflight_status == "preflight_ready_with_warnings":
            sub_warnings.append(f"sub_boss {sub_id} is preflight_ready_with_warnings")

        human_review_required = bool(
            sub_warnings
            or sub_blockers
            or risk_level in {"high", "unknown"}
            or missing_evidence
            or preflight_status != "preflight_ready"
        )
        per_sub_boss_review.append(
            {
                "sub_boss_id": sub_id,
                "title": str(sub.get("title") or (finding or {}).get("title") or ""),
                "status": status,
                "commander_decision_context": {
                    "root_commander_decision": (
                        tree_data.get("root_boss", {}).get("commander_decision", "")
                        if isinstance(tree_data.get("root_boss"), dict)
                        else ""
                    ),
                    "tree_validation_status": tree_data.get("validation_status", ""),
                    "assignment_status": assignment_data.get("assignment_status", ""),
                },
                "preflight_status": preflight_status,
                "assigned_advisory_roles": roles,
                "risk_level": risk_level,
                "evidence_required": evidence_required,
                "rollback_boundary": rollback_boundary,
                "dependencies": dependencies,
                "unresolved_warnings": _unique(sub_warnings),
                "blocked_reasons": _unique(sub_blockers),
                "human_review_required": human_review_required,
            }
        )
        risk_rows.append(
            {
                "sub_boss_id": sub_id,
                "risk_level": risk_level,
                "risk_auditor_assigned": "risk_auditor" in roles,
                "coverage_required": risk_level in {"high", "unknown"},
            }
        )
        evidence_rows.append(
            {
                "sub_boss_id": sub_id,
                "evidence_required_count": len(evidence_required),
                "missing_evidence": missing_evidence,
                "evidence_checker_assigned": "evidence_checker" in roles,
            }
        )

    if any(row.get("preflight_status") in {"preflight_incomplete", "preflight_ready_with_warnings"} for row in per_sub_boss_review):
        warnings.append("one or more sub-bosses carry incomplete or warning preflight status")
    if any(row.get("risk_level") in {"high", "unknown"} for row in per_sub_boss_review):
        warnings.append("one or more sub-bosses require high/unknown risk review")
    if any(row.get("unresolved_warnings") for row in per_sub_boss_review):
        warnings.append("one or more sub-bosses have unresolved warnings")

    risk_summary = {
        "coverage": risk_rows,
        "high_or_unknown_without_risk_auditor": [
            row["sub_boss_id"]
            for row in risk_rows
            if row.get("coverage_required") and not row.get("risk_auditor_assigned")
        ],
    }
    evidence_summary = {
        "coverage": evidence_rows,
        "missing_evidence_without_evidence_checker": [
            row["sub_boss_id"]
            for row in evidence_rows
            if row.get("missing_evidence") and not row.get("evidence_checker_assigned")
        ],
    }

    boss_summary, fracture_tree_summary, preflight_summary, assignment_summary = _summaries(
        tree_data=tree_data,
        preflight_data=preflight_data,
        assignment_data=assignment_data,
        sub_bosses=sub_bosses,
        preflight_findings=preflight_findings,
        assignments_by_id=assignments_by_id,
        unassigned_by_id=unassigned_by_id,
    )

    blockers = _unique(blockers)
    incomplete = _unique(incomplete)
    warnings = _unique(warnings)
    review_status = _review_status(blockers=blockers, incomplete=incomplete, warnings=warnings)
    review_tree_id = safe_tree_id if not tree_id_blockers else tree_id

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": COMMANDER_ASSIGNMENT_REVIEW_PACK_GUARDRAIL_NOTE,
        "review_id": f"cmd-n6-{review_tree_id or INVALID_TREE_ID_DIR}-assignment-review-pack",
        "tree_id": review_tree_id,
        "boss_id": safe_boss_id if not boss_id_blockers else tree_boss_id,
        "source_artifacts": _source_artifact_summary(
            tree_path=tree_path,
            preflight_path=preflight_path,
            assignment_path=assignment_path,
            tree_data=tree_data,
            preflight_data=preflight_data,
            assignment_data=assignment_data,
        ),
        "review_status": review_status,
        "boss_summary": boss_summary,
        "fracture_tree_summary": fracture_tree_summary,
        "preflight_summary": preflight_summary,
        "assignment_summary": assignment_summary,
        "per_sub_boss_review": per_sub_boss_review,
        "risk_summary": risk_summary,
        "evidence_summary": evidence_summary,
        "human_review_checklist": list(HUMAN_REVIEW_CHECKLIST),
        "warnings": warnings,
        "blocked_reasons": blockers,
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
        "review_statuses": list(REVIEW_STATUSES),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "title": tree_title,
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_commander_assignment_review_pack_markdown(report: dict[str, Any]) -> str:
    """Render a CMD.N6 review pack as Markdown."""
    source = report.get("source_artifacts") if isinstance(report.get("source_artifacts"), dict) else {}
    boss = report.get("boss_summary") if isinstance(report.get("boss_summary"), dict) else {}
    tree = report.get("fracture_tree_summary") if isinstance(report.get("fracture_tree_summary"), dict) else {}
    preflight = report.get("preflight_summary") if isinstance(report.get("preflight_summary"), dict) else {}
    assignment = report.get("assignment_summary") if isinstance(report.get("assignment_summary"), dict) else {}
    risk = report.get("risk_summary") if isinstance(report.get("risk_summary"), dict) else {}
    evidence = report.get("evidence_summary") if isinstance(report.get("evidence_summary"), dict) else {}
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}

    lines: list[str] = [
        "# Commander Assignment Review Pack",
        "",
        f"> {report.get('guardrail_note', COMMANDER_ASSIGNMENT_REVIEW_PACK_GUARDRAIL_NOTE)}",
        "",
        "_Report only: CMD.N6 combines CMD.N3, CMD.N4, and CMD.N5 artifacts for human review. It runs nothing and changes no source, routing, worker, model, validation, benchmark, or patch behavior._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Review id:** `{_md(report.get('review_id', ''))}`",
        f"- **Tree id:** `{_md(report.get('tree_id', ''))}`",
        f"- **Boss id:** `{_md(report.get('boss_id', ''))}`",
        f"- **Review status:** `{_md(report.get('review_status', ''))}`",
        "",
        "## Source Artifacts",
        "",
        "| Artifact | Path | Kind | Status |",
        "| --- | --- | --- | --- |",
    ]
    for name in ("tree", "preflight", "assignment"):
        row = source.get(name) if isinstance(source.get(name), dict) else {}
        lines.append(
            "| {name} | {path} | {kind} | {status} |".format(
                name=_md(name),
                path=_md(row.get("path", "")),
                kind=_md(row.get("report_kind", "")),
                status=_md(row.get("status", "")),
            )
        )

    lines += [
        "",
        "## Boss Overview",
        "",
        f"- **Title:** {_md(boss.get('title', ''))}",
        f"- **Root title:** {_md(boss.get('root_title', ''))}",
        f"- **Commander decision:** `{_md(boss.get('commander_decision', ''))}`",
        f"- **Fracture pressure:** `{_md(boss.get('fracture_pressure', ''))}`",
        f"- **Actual remaining:** `{_md(boss.get('actual_remaining', ''))}`",
        "",
        "## Fracture Tree Overview",
        "",
        f"- **Validation status:** `{_md(tree.get('validation_status', ''))}`",
        f"- **Sub-bosses:** {tree.get('sub_boss_count', 0)}",
        f"- **Eligible sub-bosses:** {tree.get('eligible_sub_boss_count', 0)}",
        f"- **Total expected complexity:** `{_md(tree.get('total_expected_complexity', ''))}`",
        f"- **Total attempt budget:** `{_md(tree.get('total_attempt_budget', ''))}`",
        f"- **Dependency edges:** {tree.get('dependency_edge_count', 0)}",
        "",
        "## Preflight Overview",
        "",
        f"- **Preflight status:** `{_md(preflight.get('preflight_status', ''))}`",
        f"- **Evaluated sub-bosses:** {preflight.get('evaluated_sub_boss_count', 0)}",
        f"- **Warnings:** {preflight.get('warning_count', 0)}",
        f"- **Incomplete reasons:** {preflight.get('incomplete_reason_count', 0)}",
        f"- **Blocked reasons:** {preflight.get('blocked_reason_count', 0)}",
        "",
        "## Assignment Overview",
        "",
        f"- **Assignment status:** `{_md(assignment.get('assignment_status', ''))}`",
        f"- **Assignments:** {assignment.get('assignment_count', 0)}",
        f"- **Unassigned sub-bosses:** {assignment.get('unassigned_sub_boss_count', 0)}",
        f"- **Warnings:** {assignment.get('warning_count', 0)}",
        f"- **Blocked reasons:** {assignment.get('blocked_reason_count', 0)}",
        "",
        "## Per-Sub-Boss Review",
        "",
    ]
    rows = report.get("per_sub_boss_review") if isinstance(report.get("per_sub_boss_review"), list) else []
    if rows:
        lines += [
            "| Sub-boss | Status | Preflight | Risk | Roles | Human review | Warnings | Blocked |",
            "| --- | --- | --- | --- | --- | --- | ---: | ---: |",
        ]
        for row in rows:
            lines.append(
                "| {sid} | {status} | {preflight} | {risk} | {roles} | {human} | {warnings} | {blocked} |".format(
                    sid=_md(row.get("sub_boss_id", "")),
                    status=_md(row.get("status", "")),
                    preflight=_md(row.get("preflight_status", "")),
                    risk=_md(row.get("risk_level", "")),
                    roles=_md(", ".join(row.get("assigned_advisory_roles") or [])),
                    human=str(bool(row.get("human_review_required"))).lower(),
                    warnings=len(row.get("unresolved_warnings") or []),
                    blocked=len(row.get("blocked_reasons") or []),
                )
            )
    else:
        lines.append("_None._")
    lines += [
        "",
        "## Risk Coverage",
        "",
    ]
    risk_rows = risk.get("coverage") if isinstance(risk.get("coverage"), list) else []
    if risk_rows:
        for row in risk_rows:
            lines.append(
                f"- `{_md(row.get('sub_boss_id', ''))}` risk=`{_md(row.get('risk_level', ''))}`, risk_auditor_assigned={str(bool(row.get('risk_auditor_assigned'))).lower()}"
            )
    else:
        lines.append("_None._")
    gaps = risk.get("high_or_unknown_without_risk_auditor") or []
    if gaps:
        lines.append(f"- Missing risk_auditor coverage: `{_md(', '.join(gaps))}`")
    lines += [
        "",
        "## Evidence Coverage",
        "",
    ]
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
        lines.append(f"- Missing evidence_checker coverage: `{_md(', '.join(evidence_gaps))}`")
    lines += [
        "",
        "## Human Review Checklist",
        "",
    ]
    _render_list(lines, list(report.get("human_review_checklist") or []))

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


def write_commander_assignment_review_pack(
    *,
    tree_path: str | Path,
    preflight_path: str | Path,
    assignment_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    """Build and write CMD.N6 JSON + Markdown review-pack artifacts."""
    tree_data, tree_blockers = read_json_input(tree_path, "tree")
    preflight_data, preflight_blockers = read_json_input(preflight_path, "preflight")
    assignment_data, assignment_blockers = read_json_input(assignment_path, "assignment")
    report = build_commander_assignment_review_pack(
        tree_path=tree_path,
        preflight_path=preflight_path,
        assignment_path=assignment_path,
        tree_data=tree_data,
        preflight_data=preflight_data,
        assignment_data=assignment_data,
        input_blockers=tree_blockers + preflight_blockers + assignment_blockers,
    )
    safe_tree_id, tree_id_blockers = _safe_identifier(report.get("tree_id"), "tree_id")
    target_id = safe_tree_id if not tree_id_blockers else INVALID_TREE_ID_DIR
    out_dir = Path(output_dir) / target_id
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_commander_assignment_review_pack_markdown(report), encoding="utf-8")
    return {
        "ok": report.get("review_status") != "review_pack_blocked",
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
