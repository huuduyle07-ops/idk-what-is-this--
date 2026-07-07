"""HUMAN.N1 - Human Review Boundary Map.

Defines the report-only boundary between advisory C.A.T.T.U.S outputs and
human-only authority. HUMAN.N1 writes a JSON/Markdown map only. It does not add
approval enforcement, call models, route models, launch workers, run validation
or benchmarks, invoke tools, use network access, execute subprocesses, write to a
database, change auth/routes, apply patches, or approve/reject work.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "human_review_boundary_map"
THIS_PHASE_ID = "HUMAN.N1"

STATUS_READY = "human_boundary_map_ready"
STATUS_READY_WITH_WARNINGS = "human_boundary_map_ready_with_warnings"
STATUS_INCOMPLETE = "human_boundary_map_incomplete"
STATUS_BLOCKED = "human_boundary_map_blocked"

JSON_NAME = "human_review_boundary_map.json"
MD_NAME = "human_review_boundary_map.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "human" / "review_boundary_map"

AUTHORITY_LEVELS: tuple[str, ...] = (
    "advisory_only",
    "human_review_required",
    "explicit_human_approval_required",
    "forbidden_without_separate_phase",
    "blocked",
)

ACTION_CATEGORIES: tuple[str, ...] = (
    "advisory_reports",
    "patch_apply",
    "direct_file_mutation",
    "worker_launch",
    "model_routing",
    "model_calls",
    "validation_execution",
    "benchmark_execution",
    "mcp_tool_invocation",
    "network_access",
    "subprocess_docker_execution",
    "database_writes",
    "web_route_auth_policy_changes",
    "registry_adoption",
    "model_role_catalog_adoption",
    "evidence_quality_acceptance",
    "mirror_score_interpretation",
    "commander_fracture_assignment_interpretation",
    "final_answer_confidence",
    "remote_execution",
    "replay_janitor_apply_actions",
    "dream_execution",
    "automatic_approval_rejection",
    "hidden_mutation",
)

BRANCHES: tuple[str, ...] = ("MIRROR", "CMD", "MODEL", "EVAL", "HARDEN", "UX")

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "HUMAN.N2",
    "title": "Human Approval Token / Confirmation Contract",
    "reason": (
        "Define the explicit human confirmation signal shape before dangerous "
        "actions, still without enforcing runtime behavior."
    ),
}

ALTERNATIVE_NEXT_PHASE = {
    "phase_id": "ADOPT.MODEL.1",
    "title": "Human-Approved Model Role Catalog Adoption",
    "reason": (
        "Adopt the proposed model role catalog only after the human confirmation "
        "contract is clear."
    ),
}

GUARDRAIL_NOTE = (
    "HUMAN.N1 is report-only and boundary-map-only. It defines where AI advice "
    "stops and where human decision-making begins; it does not enforce approval "
    "gates or perform dangerous actions."
)

DEFAULT_WARNINGS: tuple[str, ...] = (
    "Future HUMAN.N2 should define explicit confirmation token shape before enforcement.",
    "This map intentionally does not enforce approval gates.",
)

ADVISORY_SYSTEMS_COVERED: tuple[str, ...] = (
    "MIRROR drift, derailment, score, and trace evidence",
    "CMD fracture, assignment, preflight, and review-pack planning artifacts",
    "MODEL tower cards, role coverage, gap, proposal, and adoption-readiness artifacts",
    "EVAL evidence quality plans, reports, loaders, readiness checks, and branch checkpoint",
)

HUMAN_ONLY_DECISIONS: tuple[str, ...] = (
    "approve or reject work",
    "apply patches or accept direct file mutation",
    "launch workers or execute Commander assignments",
    "route work to executable models or adopt model catalogs",
    "accept evidence quality as sufficient",
    "interpret Mirror scores as blocking or non-blocking decisions",
    "accept Commander fracture or assignment plans as executable work",
    "treat final-answer confidence as trustworthy enough to act on",
    "approve remote execution, network access, MCP/tool use, database writes, or auth changes",
)

HUMAN_REVIEW_CHECKLIST: tuple[str, ...] = (
    "Confirm the action category is present in the boundary matrix.",
    "Check whether the authority level is advisory, review-required, explicit-approval, forbidden, or blocked.",
    "Require explicit human approval before patch apply, mutation, worker launch, model call, tool use, remote execution, or auth changes.",
    "Reject any automatic approval, rejection, hidden mutation, or AI executable authority.",
    "Treat MIRROR, CMD, MODEL, and EVAL outputs as advisory evidence until a human decides otherwise.",
    "Use HUMAN.N2 to define the confirmation token shape before any enforcement phase.",
)

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "enforcement_change_performed",
    "model_call_performed",
    "model_routing_performed",
    "worker_launch_performed",
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
    "auth_policy_changed",
    "registry_mutation_performed",
    "approval_or_rejection_performed",
)

BOUNDARY_GUARDRAILS: tuple[str, ...] = (
    "report-only",
    "boundary mapping only",
    "no enforcement change",
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
    "no registry mutation",
    "no approval/rejection",
    "writes boundary artifacts only",
)

DEFAULT_ACTION_BOUNDARIES: tuple[dict[str, Any], ...] = (
    {
        "action_id": "advisory_reports",
        "action": "advisory reports",
        "authority_level": "advisory_only",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human decides whether advisory evidence is sufficient.",
        "rationale": "MIRROR, CMD, MODEL, and EVAL may produce evidence and planning artifacts only.",
    },
    {
        "action_id": "patch_apply",
        "action": "patch apply",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must explicitly approve any patch application.",
        "rationale": "Applying patches mutates source and crosses from advice into action.",
    },
    {
        "action_id": "direct_file_mutation",
        "action": "direct file mutation",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve direct mutation or an implementation phase must authorize it.",
        "rationale": "File writes are real-world state changes.",
    },
    {
        "action_id": "worker_launch",
        "action": "worker launch",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve launching workers or executable agents.",
        "rationale": "Planning artifacts may describe assignments but must not launch them.",
    },
    {
        "action_id": "model_routing",
        "action": "model routing",
        "authority_level": "forbidden_without_separate_phase",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human-approved later phase must authorize routing behavior.",
        "rationale": "Model IDs and tower cards are advisory until a separate adoption phase.",
    },
    {
        "action_id": "model_calls",
        "action": "model calls",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve calls that spend model budget or contact providers.",
        "rationale": "Model calls can spend budget and produce new advisory evidence.",
    },
    {
        "action_id": "validation_execution",
        "action": "validation execution",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve validation execution when it is a real action.",
        "rationale": "Validation commands are evidence-producing actions, not automatic gates.",
    },
    {
        "action_id": "benchmark_execution",
        "action": "benchmark execution",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve benchmark execution and interpret results.",
        "rationale": "Benchmarks can be slow, flaky, or environment-dependent.",
    },
    {
        "action_id": "mcp_tool_invocation",
        "action": "MCP/tool invocation",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve tool use that can affect external systems or local state.",
        "rationale": "Tools may mutate state, spend budget, or contact services.",
    },
    {
        "action_id": "network_access",
        "action": "network access",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve network access.",
        "rationale": "Network access crosses local-report-only boundaries.",
    },
    {
        "action_id": "subprocess_docker_execution",
        "action": "subprocess/Docker execution",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve process or container execution.",
        "rationale": "Process execution can mutate state or escape report-only scope.",
    },
    {
        "action_id": "database_writes",
        "action": "database writes",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve durable database writes.",
        "rationale": "Database writes are durable state changes.",
    },
    {
        "action_id": "web_route_auth_policy_changes",
        "action": "web route/auth policy changes",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve route behavior and auth policy changes.",
        "rationale": "Route and auth changes can alter user access and mutation surfaces.",
    },
    {
        "action_id": "registry_adoption",
        "action": "registry adoption",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve registry adoption or registry mutation.",
        "rationale": "Registry records shape future work selection.",
    },
    {
        "action_id": "model_role_catalog_adoption",
        "action": "model role catalog adoption",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve adopting a proposed model role catalog.",
        "rationale": "Catalog adoption must not convert advisory model IDs into executable authority.",
    },
    {
        "action_id": "evidence_quality_acceptance",
        "action": "evidence quality acceptance",
        "authority_level": "forbidden_without_separate_phase",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human decides whether evidence quality is acceptable.",
        "rationale": "Evidence scores must not become automatic approval gates in HUMAN.N1.",
    },
    {
        "action_id": "mirror_score_interpretation",
        "action": "Mirror score interpretation",
        "authority_level": "human_review_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human interprets Mirror drift/derailment scores.",
        "rationale": "Mirror reports may display risk but must not block or reject runs.",
    },
    {
        "action_id": "commander_fracture_assignment_interpretation",
        "action": "Commander fracture/assignment interpretation",
        "authority_level": "human_review_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human decides whether Commander plans become executable work.",
        "rationale": "Fracture and assignment artifacts are planning outputs only.",
    },
    {
        "action_id": "final_answer_confidence",
        "action": "final answer confidence",
        "authority_level": "human_review_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human decides whether final-answer confidence is sufficient.",
        "rationale": "Confidence is an advisory signal, not authority.",
    },
    {
        "action_id": "remote_execution",
        "action": "remote execution",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve remote execution.",
        "rationale": "Remote execution crosses local-only and external-system boundaries.",
    },
    {
        "action_id": "replay_janitor_apply_actions",
        "action": "replay janitor/apply actions",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve Replay janitor/apply actions.",
        "rationale": "Replay apply actions can mutate artifacts or source state.",
    },
    {
        "action_id": "dream_execution",
        "action": "Dream execution",
        "authority_level": "explicit_human_approval_required",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human must approve Dream execution.",
        "rationale": "Dream execution is outside advisory boundary mapping.",
    },
    {
        "action_id": "automatic_approval_rejection",
        "action": "automatic approval/rejection",
        "authority_level": "blocked",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Human approval or rejection is mandatory.",
        "rationale": "Automatic approval/rejection is explicitly blocked.",
    },
    {
        "action_id": "hidden_mutation",
        "action": "hidden mutation",
        "authority_level": "blocked",
        "automatic_allowed": False,
        "ai_may_execute": False,
        "human_decision": "Hidden mutation is never allowed.",
        "rationale": "All mutation must be visible and separately authorized.",
    },
)

FORBIDDEN_AUTOMATIC_ACTIONS: tuple[dict[str, Any], ...] = (
    {"action_id": "auto_apply_patch", "authority_level": "blocked", "automatic_allowed": False},
    {"action_id": "auto_reject_patch", "authority_level": "blocked", "automatic_allowed": False},
    {"action_id": "auto_approve_patch", "authority_level": "blocked", "automatic_allowed": False},
    {"action_id": "auto_launch_worker", "authority_level": "blocked", "automatic_allowed": False},
    {"action_id": "auto_route_model", "authority_level": "blocked", "automatic_allowed": False},
    {"action_id": "auto_run_validation", "authority_level": "blocked", "automatic_allowed": False},
    {"action_id": "auto_run_benchmark", "authority_level": "blocked", "automatic_allowed": False},
    {"action_id": "auto_mutate_registry", "authority_level": "blocked", "automatic_allowed": False},
    {"action_id": "auto_adopt_model_catalog", "authority_level": "blocked", "automatic_allowed": False},
    {"action_id": "auto_call_mcp_tool", "authority_level": "blocked", "automatic_allowed": False},
    {"action_id": "auto_write_database", "authority_level": "blocked", "automatic_allowed": False},
    {"action_id": "auto_change_auth_policy", "authority_level": "blocked", "automatic_allowed": False},
    {"action_id": "auto_execute_remote_command", "authority_level": "blocked", "automatic_allowed": False},
)

DEFAULT_BRANCH_BOUNDARIES: dict[str, dict[str, list[str]]] = {
    "MIRROR": {
        "may": ["may display drift/derailment evidence", "may show trace and score interpretation prompts"],
        "may_not": ["may not block Apply", "may not auto-reject a run", "may not change routing"],
        "human_only": ["decide whether drift evidence blocks action"],
    },
    "CMD": {
        "may": ["may fracture and plan tasks", "may prepare advisory assignments"],
        "may_not": [
            "may not launch workers",
            "may not mutate files",
            "may not convert advisory roles into executable agents",
        ],
        "human_only": ["approve executable assignment or worker launch"],
    },
    "MODEL": {
        "may": ["may define tower cards", "may propose model role catalogs"],
        "may_not": [
            "may not route to models",
            "may not treat model_ids as executable authority",
            "may not adopt proposed catalog without separate human-approved phase",
        ],
        "human_only": ["approve catalog adoption and model-routing authority"],
    },
    "EVAL": {
        "may": ["may report evidence quality", "may summarize missing or weak evidence"],
        "may_not": [
            "may not approve/reject patches",
            "may not run missing validation",
            "may not become a scoring gate without separate phase",
        ],
        "human_only": ["accept evidence quality or request more evidence"],
    },
    "HARDEN": {
        "may": ["may audit safety boundaries", "may report policy risks"],
        "may_not": ["may not silently loosen auth/mutation rules"],
        "human_only": ["approve safety-boundary or policy changes"],
    },
    "UX": {
        "may": ["may display advisory status", "may make human actions visible"],
        "may_not": ["may not hide critical human actions behind automation"],
        "human_only": ["approve UI flows that trigger dangerous actions"],
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _bool(value: Any) -> str:
    return str(bool(value)).lower()


def _guardrails() -> dict[str, bool]:
    data = {key: False for key in GUARDRAIL_FALSE_FLAGS}
    data["report_only"] = True
    data["boundary_mapping_only"] = True
    return data


def _copy_matrix(action_boundaries: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> list[dict[str, Any]]:
    source = DEFAULT_ACTION_BOUNDARIES if action_boundaries is None else action_boundaries
    matrix: list[dict[str, Any]] = []
    for item in source:
        entry = dict(item)
        entry.setdefault("action", entry.get("action_id", ""))
        entry.setdefault("authority_level", "human_review_required")
        entry.setdefault("automatic_allowed", False)
        entry.setdefault("ai_may_execute", False)
        entry.setdefault("human_decision", "")
        entry.setdefault("rationale", "")
        matrix.append(entry)
    return matrix


def _copy_branches(branch_boundaries: dict[str, Any] | None) -> dict[str, dict[str, list[str]]]:
    source = DEFAULT_BRANCH_BOUNDARIES if branch_boundaries is None else branch_boundaries
    copied: dict[str, dict[str, list[str]]] = {}
    for branch, rules in source.items():
        rule_map = rules if isinstance(rules, dict) else {}
        copied[str(branch)] = {
            "may": [str(item) for item in rule_map.get("may", [])],
            "may_not": [str(item) for item in rule_map.get("may_not", [])],
            "human_only": [str(item) for item in rule_map.get("human_only", [])],
        }
    return copied


def _block(blocked: list[dict[str, str]], reason: str, message: str) -> None:
    if not any(item.get("reason") == reason for item in blocked):
        blocked.append({"reason": reason, "message": message})


def _evaluate_boundary_map(
    matrix: list[dict[str, Any]],
    branches: dict[str, dict[str, list[str]]],
    warnings: list[str],
) -> tuple[str, list[str], list[dict[str, str]]]:
    action_ids = {str(item.get("action_id", "")) for item in matrix}
    missing = sorted(set(ACTION_CATEGORIES) - action_ids)
    missing.extend(sorted(set(BRANCHES) - set(branches)))

    blocked: list[dict[str, str]] = []
    for item in matrix:
        action_id = str(item.get("action_id", ""))
        authority_level = str(item.get("authority_level", ""))
        automatic_allowed = item.get("automatic_allowed") is True
        ai_may_execute = item.get("ai_may_execute") is True
        if authority_level not in AUTHORITY_LEVELS:
            missing.append(f"invalid_authority_level:{action_id}")
        if action_id == "automatic_approval_rejection" and (
            automatic_allowed or authority_level != "blocked"
        ):
            _block(
                blocked,
                "auto_approval_allowed",
                "Automatic approval/rejection must remain blocked.",
            )
        if action_id == "hidden_mutation" and (automatic_allowed or authority_level != "blocked"):
            _block(blocked, "hidden_mutation_allowed", "Hidden mutation must remain blocked.")
        if ai_may_execute and authority_level != "advisory_only":
            _block(
                blocked,
                "ai_executable_authority",
                f"{action_id} grants executable authority to AI.",
            )

    if blocked:
        return STATUS_BLOCKED, sorted(set(missing)), blocked
    if missing:
        return STATUS_INCOMPLETE, sorted(set(missing)), blocked
    if warnings:
        return STATUS_READY_WITH_WARNINGS, [], blocked
    return STATUS_READY, [], blocked


def _approval_actions(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in matrix
        if item.get("authority_level") == "explicit_human_approval_required"
    ]


def build_human_review_boundary_map(
    *,
    report_id: str = "",
    created_at: str = "",
    action_boundaries: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    branch_boundaries: dict[str, Any] | None = None,
    warnings: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Build the HUMAN.N1 report-only authority boundary map."""
    matrix = _copy_matrix(action_boundaries)
    branches = _copy_branches(branch_boundaries)
    warning_list = [str(item) for item in (DEFAULT_WARNINGS if warnings is None else warnings)]
    status, missing, blocked = _evaluate_boundary_map(matrix, branches, warning_list)
    approval_actions = _approval_actions(matrix)
    forbidden_actions = [dict(item) for item in FORBIDDEN_AUTOMATIC_ACTIONS]

    summary = {
        "boundary_status": status,
        "critical_action_category_count": len(ACTION_CATEGORIES),
        "mapped_action_category_count": len({str(item.get("action_id", "")) for item in matrix}),
        "missing_critical_action_categories": list(missing),
        "explicit_approval_action_count": len(approval_actions),
        "forbidden_automatic_action_count": len(forbidden_actions),
        "branch_boundary_count": len(branches),
        "blocked_reason_count": len(blocked),
        "warning_count": len(warning_list),
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
    }

    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "guardrail_note": GUARDRAIL_NOTE,
        "report_id": str(report_id or ""),
        "created_at": str(created_at or _utc_now()),
        "boundary_status": status,
        "summary": summary,
        "authority_levels": list(AUTHORITY_LEVELS),
        "authority_philosophy": [
            "AI systems may produce advisory evidence and plans.",
            "Humans retain authority over approval, rejection, mutation, routing, execution, and risk acceptance.",
            "Dangerous actions require explicit human approval before any later phase may enforce them.",
            "Automatic approval/rejection and hidden mutation remain blocked.",
        ],
        "advisory_systems_covered": list(ADVISORY_SYSTEMS_COVERED),
        "human_only_decisions": list(HUMAN_ONLY_DECISIONS),
        "explicit_approval_actions": approval_actions,
        "forbidden_automatic_actions": forbidden_actions,
        "boundary_matrix": matrix,
        "branch_specific_boundaries": branches,
        "human_review_checklist": list(HUMAN_REVIEW_CHECKLIST),
        "warnings": warning_list,
        "blocked_reasons": blocked,
        "incomplete_reasons": missing,
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "alternative_next_phase": dict(ALTERNATIVE_NEXT_PHASE),
        "final_verdict": {
            "status": status,
            "boundary_map_ready": status == STATUS_READY,
            "boundary_map_ready_with_warnings": status == STATUS_READY_WITH_WARNINGS,
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
        },
        "boundaries_guardrails": list(BOUNDARY_GUARDRAILS),
        "guardrails": _guardrails(),
    }


def _dict_lines(values: Any) -> list[str]:
    if not isinstance(values, dict) or not values:
        return ["_None._"]
    lines: list[str] = []
    for key in sorted(values):
        value = values[key]
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            rendered = str(value)
        lines.append(f"- `{_md(key)}`: {_md(rendered)}")
    return lines


def _list_lines(values: Any, *, key: str = "") -> list[str]:
    if not isinstance(values, list) or not values:
        return ["_None._"]
    lines: list[str] = []
    for item in values:
        if isinstance(item, dict) and key:
            lines.append(f"- {_md(item.get(key, item))}")
        elif isinstance(item, dict):
            lines.append(f"- {_md(json.dumps(item, ensure_ascii=False, sort_keys=True))}")
        else:
            lines.append(f"- {_md(item)}")
    return lines


def render_human_review_boundary_map_markdown(report: dict[str, Any]) -> str:
    """Render the HUMAN.N1 boundary map as operator-readable Markdown."""
    lines: list[str] = [
        "# Human Review Boundary Map",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
    ]
    lines.extend(_dict_lines(report.get("summary")))
    lines.extend(["", "## Authority Philosophy", ""])
    lines.extend(_list_lines(report.get("authority_philosophy")))
    lines.extend(["", "## Advisory Systems Covered", ""])
    lines.extend(_list_lines(report.get("advisory_systems_covered")))
    lines.extend(["", "## Human-Only Decisions", ""])
    lines.extend(_list_lines(report.get("human_only_decisions")))
    lines.extend(["", "## Explicit Approval Actions", ""])
    approval = report.get("explicit_approval_actions") if isinstance(report.get("explicit_approval_actions"), list) else []
    if approval:
        lines.extend(["| Action | Human decision | Rationale |", "|---|---|---|"])
        for item in approval:
            lines.append(
                f"| {_md(item.get('action'))} | {_md(item.get('human_decision'))} | {_md(item.get('rationale'))} |"
            )
    else:
        lines.append("_None._")
    lines.extend(["", "## Forbidden Automatic Actions", ""])
    forbidden = report.get("forbidden_automatic_actions") if isinstance(report.get("forbidden_automatic_actions"), list) else []
    if forbidden:
        lines.extend(["| Action | Authority | Automatic allowed |", "|---|---|---|"])
        for item in forbidden:
            lines.append(
                f"| {_md(item.get('action_id'))} | {_md(item.get('authority_level'))} | {_bool(item.get('automatic_allowed'))} |"
            )
    else:
        lines.append("_None._")
    lines.extend(["", "## Boundary Matrix", ""])
    matrix = report.get("boundary_matrix") if isinstance(report.get("boundary_matrix"), list) else []
    if matrix:
        lines.extend(
            [
                "| Action | Authority | Automatic | AI execute | Human decision |",
                "|---|---|---|---|---|",
            ]
        )
        for item in matrix:
            lines.append(
                "| {action} | `{level}` | {auto} | {execute} | {decision} |".format(
                    action=_md(item.get("action")),
                    level=_md(item.get("authority_level")),
                    auto=_bool(item.get("automatic_allowed")),
                    execute=_bool(item.get("ai_may_execute")),
                    decision=_md(item.get("human_decision")),
                )
            )
    else:
        lines.append("_None._")
    lines.extend(["", "## Branch-Specific Boundaries", ""])
    branches = report.get("branch_specific_boundaries") if isinstance(report.get("branch_specific_boundaries"), dict) else {}
    for branch in BRANCHES:
        rules = branches.get(branch) if isinstance(branches.get(branch), dict) else {}
        lines.extend([f"### {branch}", ""])
        lines.append("May:")
        lines.extend(_list_lines(rules.get("may") if isinstance(rules, dict) else []))
        lines.append("")
        lines.append("May not:")
        lines.extend(_list_lines(rules.get("may_not") if isinstance(rules, dict) else []))
        lines.append("")
        lines.append("Human-only:")
        lines.extend(_list_lines(rules.get("human_only") if isinstance(rules, dict) else []))
        lines.append("")
    lines.extend(["## Human Review Checklist", ""])
    lines.extend(_list_lines(report.get("human_review_checklist")))
    lines.extend(["", "## Guardrails", ""])
    lines.extend(_list_lines(report.get("boundaries_guardrails")))
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: `{str(bool(guardrails[key])).lower()}`")
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    alt_phase = report.get("alternative_next_phase") if isinstance(report.get("alternative_next_phase"), dict) else {}
    lines.extend(
        [
            "",
            "## Recommended Next Phase",
            "",
            f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
            f"- **Title:** {_md(next_phase.get('title', ''))}",
            f"- **Reason:** {_md(next_phase.get('reason', ''))}",
            f"- **Alternative:** `{_md(alt_phase.get('phase_id', ''))}` - {_md(alt_phase.get('title', ''))}",
            "",
        ]
    )
    return "\n".join(lines)


def write_human_review_boundary_map(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build and write HUMAN.N1 JSON/Markdown boundary artifacts."""
    report = build_human_review_boundary_map(report_id=report_id, created_at=created_at)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_human_review_boundary_map_markdown(report), encoding="utf-8")
    return {
        "ok": report["boundary_status"] in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
