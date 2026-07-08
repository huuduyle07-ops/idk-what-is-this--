"""Operator-facing report for HARDEN.N4 approval enforcement simulations.

HARDEN.N4 summarizes HARDEN.N3 dry-run approval-gate decisions for a human
operator. It never enforces gates, approves or rejects real actions, issues or
consumes tokens, changes auth, changes routes, calls models, or invokes tools.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "approval_enforcement_operator_report"
THIS_PHASE_ID = "HARDEN.N4"

STATUS_READY = "approval_enforcement_operator_report_ready"
STATUS_READY_WITH_WARNINGS = "approval_enforcement_operator_report_ready_with_warnings"
STATUS_INCOMPLETE = "approval_enforcement_operator_report_incomplete"
STATUS_BLOCKED = "approval_enforcement_operator_report_blocked"

JSON_NAME = "approval_enforcement_operator_report.json"
MD_NAME = "approval_enforcement_operator_report.md"

DEFAULT_OUTPUT_ROOT = Path(".agent") / "harden" / "approval_enforcement_operator_report"
DEFAULT_SIMULATOR_PATH = (
    Path(".agent")
    / "harden"
    / "approval_enforcement_dry_run_gate_simulator"
    / "approval_enforcement_dry_run_gate_simulator.json"
)
DEFAULT_ATTACHMENT_PLAN_PATH = (
    Path(".agent")
    / "harden"
    / "approval_enforcement_attachment_plan"
    / "approval_enforcement_attachment_plan.json"
)
DEFAULT_READINESS_AUDIT_PATH = (
    Path(".agent")
    / "harden"
    / "approval_enforcement_readiness_audit"
    / "approval_enforcement_readiness_audit.json"
)
DEFAULT_TOKEN_CONTRACT_PATH = (
    Path(".agent") / "human" / "approval_token_contract" / "human_approval_token_contract.json"
)
DEFAULT_HUMAN_CLOSE_CHECKPOINT_PATH = (
    Path(".agent") / "human" / "authority_branch_checkpoint" / "human_authority_branch_checkpoint.json"
)

DECISION_VALUES: tuple[str, ...] = (
    "would_allow_with_valid_token",
    "would_warn_with_weak_token",
    "would_deny_missing_token",
    "would_deny_mismatched_token",
    "would_deny_expired_token",
    "would_deny_revoked_token",
    "would_deny_consumed_token",
    "would_block_forbidden_action",
    "would_block_hidden_mutation",
    "would_block_auto_approval",
    "would_block_auto_rejection",
    "would_block_unsafe_metadata",
    "would_require_human_review",
    "simulation_incomplete",
)

DENY_DECISIONS = {
    "would_deny_missing_token",
    "would_deny_mismatched_token",
    "would_deny_expired_token",
    "would_deny_revoked_token",
    "would_deny_consumed_token",
}
BLOCK_DECISIONS = {
    "would_block_forbidden_action",
    "would_block_hidden_mutation",
    "would_block_auto_approval",
    "would_block_auto_rejection",
    "would_block_unsafe_metadata",
}
BLOCKED_FOREVER_DECISIONS = {
    "would_block_forbidden_action",
    "would_block_hidden_mutation",
    "would_block_auto_approval",
    "would_block_auto_rejection",
    "would_block_unsafe_metadata",
}

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "HARDEN.CLOSE",
    "title": "Approval Enforcement Planning Branch Checkpoint",
    "reason": "Freeze HARDEN.N1-N4 as a complete non-enforcing approval-enforcement planning branch.",
}

GUARDRAIL_NOTE = (
    "HARDEN.N4 is report-only and operator-report-only. It summarizes simulated "
    "approval outcomes but does not approve, reject, enforce, issue tokens, "
    "consume tokens, change routes, or change auth."
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "operator report only",
    "no runtime enforcement",
    "no token validation gate",
    "no approval/rejection of real actions",
    "no token issuance",
    "no token consumption",
    "no model call",
    "no model routing",
    "no worker launch",
    "no patch apply",
    "no validation run",
    "no benchmark run",
    "no MCP/tool invocation",
    "no Dream execution",
    "no Replay janitor apply",
    "no Docker/subprocess execution except normal CLI script execution",
    "no network",
    "no database write",
    "no route behavior change",
    "no auth policy change",
    "no automatic authority escalation",
)

RUNTIME_MARKER_LABELS: dict[str, str] = {
    "enforcement_was_applied": "enforcement was applied",
    "approval_gate_enforced": "approval gate enforcement was applied",
    "simulated_allow_treated_as_real_authority": "simulated allow was treated as real authority",
    "sample_token_treated_as_real_authority": "sample token was treated as real authority",
    "approval_token_issuance_performed": "approval token was issued",
    "approval_token_consumption_performed": "approval token was consumed",
    "route_behavior_changed": "runtime behavior changed through route behavior",
    "auth_policy_changed": "runtime behavior changed through auth policy",
    "hidden_mutation_allowed": "hidden mutation was allowed",
    "automatic_approval_allowed": "automatic approval was allowed",
    "automatic_rejection_allowed": "automatic rejection was allowed",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm_path(value: str | Path | None) -> str:
    return str(value or "").replace("\\", "/")


def _resolve(repo: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo / candidate


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|")


def _bool(value: Any) -> str:
    return "true" if bool(value) else "false"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item)
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _read_json_object(repo: Path, path: str | Path, label: str) -> tuple[dict[str, Any] | None, str]:
    resolved = _resolve(repo, path)
    if not resolved.is_file():
        return None, f"{label} missing at {_norm_path(path)}"
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{label} unreadable at {_norm_path(path)}: {exc}"
    if not isinstance(data, dict):
        return None, f"{label} is not a JSON object at {_norm_path(path)}"
    return data, ""


def _artifact_summary(
    phase_id: str,
    path: str | Path,
    data: dict[str, Any] | None,
    expected_kind: str,
    error: str,
    required: bool,
) -> dict[str, Any]:
    return {
        "phase_id": phase_id,
        "path": _norm_path(path),
        "required": required,
        "present": data is not None and not error,
        "expected_report_kind": expected_kind,
        "report_kind": data.get("report_kind") if isinstance(data, dict) else "",
        "report_kind_ok": bool(isinstance(data, dict) and data.get("report_kind") == expected_kind),
        "error": error,
    }


def _source_artifacts(
    *,
    repo: Path,
    simulator_path: str | Path,
    attachment_plan_path: str | Path,
    readiness_audit_path: str | Path,
    token_contract_path: str | Path,
    human_close_checkpoint_path: str | Path,
) -> tuple[dict[str, dict[str, Any] | None], list[dict[str, Any]], list[str]]:
    simulator, simulator_error = _read_json_object(repo, simulator_path, "HARDEN.N3 simulator artifact")
    attachment, attachment_error = _read_json_object(repo, attachment_plan_path, "HARDEN.N2 attachment plan")
    readiness, readiness_error = _read_json_object(repo, readiness_audit_path, "HARDEN.N1 readiness audit")
    token_contract, token_error = _read_json_object(repo, token_contract_path, "HUMAN.N2 token contract")
    human_close, human_close_error = _read_json_object(repo, human_close_checkpoint_path, "HUMAN.CLOSE checkpoint")

    artifacts = [
        _artifact_summary(
            "HARDEN.N3",
            simulator_path,
            simulator,
            "approval_enforcement_dry_run_gate_simulator",
            simulator_error,
            True,
        ),
        _artifact_summary(
            "HARDEN.N2",
            attachment_plan_path,
            attachment,
            "approval_enforcement_attachment_plan",
            attachment_error,
            True,
        ),
        _artifact_summary(
            "HARDEN.N1",
            readiness_audit_path,
            readiness,
            "approval_enforcement_readiness_audit",
            readiness_error,
            True,
        ),
        _artifact_summary(
            "HUMAN.N2",
            token_contract_path,
            token_contract,
            "human_approval_token_contract",
            token_error,
            True,
        ),
        _artifact_summary(
            "HUMAN.CLOSE",
            human_close_checkpoint_path,
            human_close,
            "human_authority_branch_checkpoint",
            human_close_error,
            False,
        ),
    ]
    return (
        {
            "simulator": simulator,
            "attachment_plan": attachment,
            "readiness_audit": readiness,
            "token_contract": token_contract,
            "human_close": human_close,
        },
        artifacts,
        [artifact["error"] for artifact in artifacts if artifact["required"] and artifact["error"]],
    )


def _decision_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = {decision: 0 for decision in DECISION_VALUES}
    for result in results:
        decision = str(result.get("simulated_decision") or "")
        if decision not in counts:
            counts[decision] = 0
        counts[decision] += 1
    return counts


def _attention_level(decision: str) -> str:
    if decision == "would_allow_with_valid_token":
        return "info"
    if decision in {"would_deny_missing_token", "would_deny_mismatched_token"}:
        return "high_risk"
    if decision in {"would_deny_expired_token", "would_deny_revoked_token", "would_deny_consumed_token"}:
        return "caution"
    if decision in BLOCK_DECISIONS:
        return "blocked"
    if decision in {"would_warn_with_weak_token", "would_require_human_review"}:
        return "review"
    return "review"


def _operator_summary(decision: str, scenario_id: str, action_category: str) -> str:
    summaries = {
        "would_allow_with_valid_token": "The sample request and sample token would match a future gate, but this is not authority.",
        "would_warn_with_weak_token": "The sample token would pass with a warning that an operator should review.",
        "would_deny_missing_token": "A future gate would deny the sample request because no token is present.",
        "would_deny_mismatched_token": "A future gate would deny the sample request because token scope does not match.",
        "would_deny_expired_token": "A future gate would deny the sample request because the token is expired.",
        "would_deny_revoked_token": "A future gate would deny the sample request because the token is revoked.",
        "would_deny_consumed_token": "A future gate would deny the sample request because a single-use token is consumed.",
        "would_block_forbidden_action": "The scenario is inside a forbidden boundary and should stay blocked.",
        "would_block_hidden_mutation": "The scenario attempts hidden mutation and should stay blocked.",
        "would_block_auto_approval": "The scenario attempts automatic approval and should stay blocked.",
        "would_block_auto_rejection": "The scenario attempts automatic rejection and should stay blocked.",
        "would_block_unsafe_metadata": "The scenario carries unsafe metadata and should stay blocked.",
        "would_require_human_review": "The scenario remains a human-review case because no enforcement phase exists.",
        "simulation_incomplete": "The scenario could not be summarized completely from the simulator artifact.",
    }
    return summaries.get(decision, f"{scenario_id} in {action_category} produced {decision}.")


def _why_it_matters(decision: str) -> str:
    if decision == "would_allow_with_valid_token":
        return "Operators need to see that a simulated allow is still documentation-only."
    if decision in DENY_DECISIONS:
        return "Token denial cases show where future enforcement would protect risky actions."
    if decision in BLOCK_DECISIONS:
        return "Blocked cases identify boundaries that must never become automatic authority."
    if decision == "would_require_human_review":
        return "Human review remains the boundary until a separate approved enforcement phase exists."
    return "The operator needs a clear non-enforcing summary of the simulated outcome."


def _recommended_action(decision: str) -> str:
    if decision == "would_allow_with_valid_token":
        return "Review as a simulated allow only; do not dispatch or approve real work from this report."
    if decision in DENY_DECISIONS:
        return "Confirm the denial reason is legible for a future enforcement design."
    if decision in BLOCK_DECISIONS:
        return "Keep this category blocked in any future design unless a later approved phase changes scope."
    if decision == "would_require_human_review":
        return "Keep explicit human review before any runtime routing or execution."
    return "Inspect the simulator input before planning any follow-up."


def _review_item(result: dict[str, Any]) -> dict[str, Any]:
    request_summary = result.get("action_request_summary") if isinstance(result.get("action_request_summary"), dict) else {}
    scenario_id = str(result.get("scenario_id") or "")
    action_category = str(request_summary.get("action_category") or "")
    decision = str(result.get("simulated_decision") or "simulation_incomplete")
    return {
        "scenario_id": scenario_id,
        "action_category": action_category,
        "simulated_decision": decision,
        "human_readable_summary": _operator_summary(decision, scenario_id, action_category),
        "operator_attention_level": _attention_level(decision),
        "why_it_matters": _why_it_matters(decision),
        "future_enforcement_note": "Future enforcement remains intentionally unimplemented in HARDEN.N4.",
        "required_human_boundary": "Human operator review is required before any real action or future enforcement change.",
        "recommended_operator_action": _recommended_action(decision),
        "simulated_only": True,
    }


def _simulated_allow_treated_as_real_authority(results: list[dict[str, Any]]) -> bool:
    for result in results:
        if result.get("simulated_decision") != "would_allow_with_valid_token":
            continue
        boundary = result.get("boundary_result") if isinstance(result.get("boundary_result"), dict) else {}
        if _truthy(boundary.get("authorizes_real_action")) or _truthy(boundary.get("real_dispatch_allowed")):
            return True
    return False


def _runtime_flags(
    simulator: dict[str, Any] | None,
    runtime_change_markers: dict[str, Any] | None,
    *,
    enforcement_was_applied: bool,
    token_was_issued: bool,
    token_was_consumed: bool,
    runtime_behavior_changed: bool,
    simulated_allow_treated_as_real_authority: bool,
) -> dict[str, bool]:
    markers = runtime_change_markers or {}
    boundary = simulator.get("boundary_checks") if isinstance(simulator, dict) and isinstance(simulator.get("boundary_checks"), dict) else {}
    guardrails = simulator.get("guardrails") if isinstance(simulator, dict) and isinstance(simulator.get("guardrails"), dict) else {}
    return {
        "enforcement_was_applied": (
            bool(enforcement_was_applied)
            or _truthy(markers.get("enforcement_was_applied"))
            or _truthy(markers.get("approval_gate_enforced"))
            or _truthy(simulator.get("enforcement_was_applied") if isinstance(simulator, dict) else False)
            or _truthy(guardrails.get("enforcement_was_applied"))
            or _truthy(guardrails.get("approval_gate_enforced"))
        ),
        "token_was_issued": (
            bool(token_was_issued)
            or _truthy(markers.get("approval_token_issuance_performed"))
            or _truthy(boundary.get("token_issuance_performed"))
            or _truthy(guardrails.get("approval_token_issuance_performed"))
        ),
        "token_was_consumed": (
            bool(token_was_consumed)
            or _truthy(markers.get("approval_token_consumption_performed"))
            or _truthy(boundary.get("token_consumption_performed"))
            or _truthy(guardrails.get("approval_token_consumption_performed"))
        ),
        "runtime_behavior_changed": (
            bool(runtime_behavior_changed)
            or _truthy(markers.get("route_behavior_changed"))
            or _truthy(markers.get("auth_policy_changed"))
            or _truthy(boundary.get("route_behavior_changed"))
            or _truthy(boundary.get("auth_policy_changed"))
            or _truthy(guardrails.get("route_behavior_changed"))
            or _truthy(guardrails.get("auth_policy_changed"))
        ),
        "simulated_allow_treated_as_real_authority": (
            bool(simulated_allow_treated_as_real_authority)
            or _truthy(markers.get("simulated_allow_treated_as_real_authority"))
            or _truthy(markers.get("sample_token_treated_as_real_authority"))
            or _truthy(simulator.get("sample_tokens_treated_as_real_authority") if isinstance(simulator, dict) else False)
        ),
        "automatic_approval_allowed": _truthy(markers.get("automatic_approval_allowed")),
        "automatic_rejection_allowed": _truthy(markers.get("automatic_rejection_allowed")),
        "hidden_mutation_allowed": _truthy(markers.get("hidden_mutation_allowed")),
    }


def _runtime_blockers(flags: dict[str, bool]) -> list[str]:
    blockers: list[str] = []
    if flags["enforcement_was_applied"]:
        blockers.append("enforcement was applied in an operator-report phase")
    if flags["token_was_issued"]:
        blockers.append("approval token was issued in an operator-report phase")
    if flags["token_was_consumed"]:
        blockers.append("approval token was consumed in an operator-report phase")
    if flags["runtime_behavior_changed"]:
        blockers.append("runtime behavior changed in an operator-report phase")
    if flags["simulated_allow_treated_as_real_authority"]:
        blockers.append("simulated allow was treated as real authority")
    if flags["automatic_approval_allowed"]:
        blockers.append("automatic approval was allowed")
    if flags["automatic_rejection_allowed"]:
        blockers.append("automatic rejection was allowed")
    if flags["hidden_mutation_allowed"]:
        blockers.append("hidden mutation was allowed")
    return blockers


def _decision_blockers(items: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    for item in items:
        category = item["action_category"]
        decision = item["simulated_decision"]
        if category == "automatic_approval" and decision != "would_block_auto_approval":
            blockers.append("automatic approval scenario is not blocked")
        if category == "automatic_rejection" and decision != "would_block_auto_rejection":
            blockers.append("automatic rejection scenario is not blocked")
        if category == "hidden_mutation" and decision != "would_block_hidden_mutation":
            blockers.append("hidden mutation scenario is not blocked")
    return blockers


def _status(blockers: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blockers:
        return STATUS_BLOCKED
    if incomplete:
        return STATUS_INCOMPLETE
    if warnings:
        return STATUS_READY_WITH_WARNINGS
    return STATUS_READY


def _guardrails(flags: dict[str, bool]) -> dict[str, bool]:
    return {
        "report_only": True,
        "operator_report_only": True,
        "simulated_only": True,
        "no_runtime_enforcement": not flags["enforcement_was_applied"],
        "no_token_validation_gate": True,
        "no_approval_rejection_of_real_actions": True,
        "no_token_issuance": not flags["token_was_issued"],
        "no_token_consumption": not flags["token_was_consumed"],
        "no_model_call": True,
        "no_model_routing": True,
        "no_worker_launch": True,
        "no_patch_apply": True,
        "no_validation_run": True,
        "no_benchmark_run": True,
        "no_mcp_tool_invocation": True,
        "no_network": True,
        "no_database_write": True,
        "no_route_behavior_change": not flags["runtime_behavior_changed"],
        "no_auth_policy_change": not flags["runtime_behavior_changed"],
        "no_automatic_authority_escalation": True,
        "simulated_allow_is_not_real_authority": not flags["simulated_allow_treated_as_real_authority"],
    }


def _list_lines(values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        return ["_None._"]
    lines: list[str] = []
    for value in values:
        if isinstance(value, dict):
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            text = str(value)
        lines.append(f"- {_md(text)}")
    return lines


def _dict_lines(values: Any) -> list[str]:
    if not isinstance(values, dict) or not values:
        return ["_None._"]
    lines: list[str] = []
    for key in values:
        value = values[key]
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f"- `{_md(key)}`: {_md(value)}")
    return lines


def build_approval_enforcement_operator_report(
    *,
    repo_root: str | Path = ".",
    source_simulator_path: str | Path = DEFAULT_SIMULATOR_PATH,
    source_attachment_plan_path: str | Path = DEFAULT_ATTACHMENT_PLAN_PATH,
    source_readiness_audit_path: str | Path = DEFAULT_READINESS_AUDIT_PATH,
    source_token_contract_path: str | Path = DEFAULT_TOKEN_CONTRACT_PATH,
    source_human_close_checkpoint_path: str | Path = DEFAULT_HUMAN_CLOSE_CHECKPOINT_PATH,
    report_id: str = "",
    created_at: str = "",
    runtime_change_markers: dict[str, Any] | None = None,
    enforcement_was_applied: bool = False,
    token_was_issued: bool = False,
    token_was_consumed: bool = False,
    runtime_behavior_changed: bool = False,
    simulated_allow_treated_as_real_authority: bool = False,
) -> dict[str, Any]:
    """Build a read-only HARDEN.N4 operator report from local artifacts."""
    repo = Path(repo_root or ".").resolve()
    source_data, source_artifacts, source_warnings = _source_artifacts(
        repo=repo,
        simulator_path=source_simulator_path,
        attachment_plan_path=source_attachment_plan_path,
        readiness_audit_path=source_readiness_audit_path,
        token_contract_path=source_token_contract_path,
        human_close_checkpoint_path=source_human_close_checkpoint_path,
    )
    simulator = source_data["simulator"]
    incomplete: list[str] = []
    warnings: list[str] = [
        "Future enforcement remains intentionally unimplemented in HARDEN.N4.",
        "Operator report items are simulated-only and do not authorize real actions.",
    ]
    warnings.extend(source_warnings)

    results = simulator.get("simulation_results") if isinstance(simulator, dict) else None
    if not isinstance(results, list) or not results:
        incomplete.append("HARDEN.N3 simulator artifact has no simulation results")
        results = []
    typed_results = [item for item in results if isinstance(item, dict)]
    if len(typed_results) != len(results):
        incomplete.append("HARDEN.N3 simulator artifact contains malformed simulation result entries")

    decision_summary = _decision_summary(typed_results)
    if not decision_summary or not any(decision_summary.values()):
        incomplete.append("decision summary cannot be built from the simulator artifact")

    operator_items = [_review_item(result) for result in typed_results]
    if _simulated_allow_treated_as_real_authority(typed_results):
        simulated_allow_treated_as_real_authority = True

    flags = _runtime_flags(
        simulator,
        runtime_change_markers,
        enforcement_was_applied=enforcement_was_applied,
        token_was_issued=token_was_issued,
        token_was_consumed=token_was_consumed,
        runtime_behavior_changed=runtime_behavior_changed,
        simulated_allow_treated_as_real_authority=simulated_allow_treated_as_real_authority,
    )
    blockers = _runtime_blockers(flags) + _decision_blockers(operator_items)
    blockers = _dedupe(blockers)
    incomplete = _dedupe(incomplete)
    warnings = _dedupe(warnings)
    status = _status(blockers, incomplete, warnings)

    allow_items = [item for item in operator_items if item["simulated_decision"] == "would_allow_with_valid_token"]
    deny_items = [item for item in operator_items if item["simulated_decision"] in DENY_DECISIONS]
    block_items = [item for item in operator_items if item["simulated_decision"] in BLOCK_DECISIONS]
    warning_items = [
        item
        for item in operator_items
        if item["simulated_decision"] in {"would_warn_with_weak_token", "would_require_human_review"}
    ]
    incomplete_items = [item for item in operator_items if item["simulated_decision"] == "simulation_incomplete"]
    high_risk_items = [item for item in operator_items if item["operator_attention_level"] == "high_risk"]
    blocked_forever_items = [item for item in operator_items if item["simulated_decision"] in BLOCKED_FOREVER_DECISIONS]

    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "report_id": str(report_id or "harden-n4-approval-enforcement-operator-report"),
        "created_at": str(created_at or _utc_now()),
        "guardrail_note": GUARDRAIL_NOTE,
        "report_status": status,
        "source_simulator_path": _norm_path(source_simulator_path),
        "source_attachment_plan_path": _norm_path(source_attachment_plan_path),
        "source_readiness_audit_path": _norm_path(source_readiness_audit_path),
        "source_token_contract_path": _norm_path(source_token_contract_path),
        "source_human_close_checkpoint_path": _norm_path(source_human_close_checkpoint_path),
        "source_artifacts": source_artifacts,
        "scenario_count": len(typed_results),
        "decision_summary": decision_summary,
        "allow_simulations": allow_items,
        "deny_simulations": deny_items,
        "block_simulations": block_items,
        "warning_simulations": warning_items,
        "human_review_required": warning_items,
        "incomplete_simulations": incomplete_items,
        "operator_review_items": operator_items,
        "high_risk_items": high_risk_items,
        "blocked_forever_items": blocked_forever_items,
        "simulated_only_notice": {
            "simulated_only": True,
            "authorizes_real_action": False,
            "approves_real_action": False,
            "rejects_real_action": False,
            "dispatches_real_action": False,
            "message": "This report is an operator summary of simulations only.",
        },
        "enforcement_was_applied": flags["enforcement_was_applied"],
        "token_was_issued": flags["token_was_issued"],
        "token_was_consumed": flags["token_was_consumed"],
        "runtime_behavior_changed": flags["runtime_behavior_changed"],
        "warnings": warnings,
        "blocked_reasons": blockers,
        "incomplete_reasons": incomplete,
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "final_verdict": {
            "status": status,
            "operator_report_ready": status in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
            "authorizes_action": False,
            "enforces_gate": False,
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
            "message": (
                "Operator report is complete with warnings because future enforcement remains intentionally unimplemented."
                if status == STATUS_READY_WITH_WARNINGS
                else f"Operator report status is {status}."
            ),
        },
        "guardrails": _guardrails(flags),
        "boundaries": list(BOUNDARIES),
    }


def render_approval_enforcement_operator_report_markdown(report: dict[str, Any]) -> str:
    """Render a HARDEN.N4 approval enforcement operator report as Markdown."""
    lines: list[str] = [
        "# Approval Enforcement Operator Report",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Report status:** `{_md(report.get('report_status', ''))}`",
        f"- **Scenarios summarized:** {report.get('scenario_count', 0)}",
        f"- **Enforcement was applied:** `{_bool(report.get('enforcement_was_applied'))}`",
        f"- **Token was issued:** `{_bool(report.get('token_was_issued'))}`",
        f"- **Token was consumed:** `{_bool(report.get('token_was_consumed'))}`",
        f"- **Runtime behavior changed:** `{_bool(report.get('runtime_behavior_changed'))}`",
        "",
        "## Source Artifacts",
        "",
    ]
    artifacts = report.get("source_artifacts") if isinstance(report.get("source_artifacts"), list) else []
    if artifacts:
        lines.extend(["| Phase | Required | Present | Kind OK | Path |", "|---|---|---|---|---|"])
        for artifact in artifacts:
            lines.append(
                f"| {_md(artifact.get('phase_id'))} | {_bool(artifact.get('required'))} | "
                f"{_bool(artifact.get('present'))} | {_bool(artifact.get('report_kind_ok'))} | "
                f"`{_md(artifact.get('path'))}` |"
            )
    else:
        lines.append("_None._")

    lines.extend(["", "## Operator Notice", ""])
    lines.extend(_dict_lines(report.get("simulated_only_notice")))
    lines.extend(["", "## Decision Summary", ""])
    lines.extend(_dict_lines(report.get("decision_summary")))
    lines.extend(["", "## Allow Simulations", ""])
    lines.extend(_list_lines(report.get("allow_simulations")))
    lines.extend(["", "## Deny Simulations", ""])
    lines.extend(_list_lines(report.get("deny_simulations")))
    lines.extend(["", "## Block Simulations", ""])
    lines.extend(_list_lines(report.get("block_simulations")))
    lines.extend(["", "## Human Review Required", ""])
    lines.extend(_list_lines(report.get("human_review_required")))
    lines.extend(["", "## High-Risk Items", ""])
    lines.extend(_list_lines(report.get("high_risk_items")))
    lines.extend(["", "## Blocked-Forever Items", ""])
    lines.extend(_list_lines(report.get("blocked_forever_items")))
    lines.extend(["", "## Operator Review Checklist", ""])
    items = report.get("operator_review_items") if isinstance(report.get("operator_review_items"), list) else []
    if items:
        lines.extend(["| Scenario | Category | Decision | Attention | Simulated Only |", "|---|---|---|---|---|"])
        for item in items:
            lines.append(
                f"| {_md(item.get('scenario_id'))} | {_md(item.get('action_category'))} | "
                f"`{_md(item.get('simulated_decision'))}` | {_md(item.get('operator_attention_level'))} | "
                f"{_bool(item.get('simulated_only'))} |"
            )
    else:
        lines.append("_None._")
    lines.extend(["", "## Simulated-Only Boundary", ""])
    lines.extend(_dict_lines(report.get("simulated_only_notice")))
    lines.extend(["", "## Warnings", ""])
    lines.extend(_list_lines(report.get("warnings")))
    lines.extend(["", "## Blocked Reasons", ""])
    lines.extend(_list_lines(report.get("blocked_reasons")))
    lines.extend(["", "## Incomplete Reasons", ""])
    lines.extend(_list_lines(report.get("incomplete_reasons")))
    lines.extend(["", "## Final Verdict", ""])
    lines.extend(_dict_lines(report.get("final_verdict")))

    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    lines.extend(
        [
            "",
            "## Recommended Next Phase",
            "",
            f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
            f"- **Title:** {_md(next_phase.get('title', ''))}",
            f"- **Reason:** {_md(next_phase.get('reason', ''))}",
            "",
            "## Guardrails",
            "",
        ]
    )
    lines.extend(_list_lines(report.get("boundaries")))
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: `{str(bool(guardrails[key])).lower()}`")
    lines.append("")
    return "\n".join(lines)


def write_approval_enforcement_operator_report(
    *,
    repo_root: str | Path = ".",
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    source_simulator_path: str | Path = DEFAULT_SIMULATOR_PATH,
    source_attachment_plan_path: str | Path = DEFAULT_ATTACHMENT_PLAN_PATH,
    source_readiness_audit_path: str | Path = DEFAULT_READINESS_AUDIT_PATH,
    source_token_contract_path: str | Path = DEFAULT_TOKEN_CONTRACT_PATH,
    source_human_close_checkpoint_path: str | Path = DEFAULT_HUMAN_CLOSE_CHECKPOINT_PATH,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build and write HARDEN.N4 JSON/Markdown operator report artifacts."""
    report = build_approval_enforcement_operator_report(
        repo_root=repo_root,
        source_simulator_path=source_simulator_path,
        source_attachment_plan_path=source_attachment_plan_path,
        source_readiness_audit_path=source_readiness_audit_path,
        source_token_contract_path=source_token_contract_path,
        source_human_close_checkpoint_path=source_human_close_checkpoint_path,
        report_id=report_id,
        created_at=created_at,
    )
    out = Path(output_dir)
    if not out.is_absolute():
        out = Path(repo_root or ".") / out
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    md_path = out / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_approval_enforcement_operator_report_markdown(report), encoding="utf-8")
    return {
        "ok": report["report_status"] in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
