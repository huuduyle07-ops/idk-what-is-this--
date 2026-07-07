"""HUMAN.N2 - Human Approval Token / Confirmation Contract.

Defines the report-only contract for future explicit human approval tokens. This
module documents schema, validity rules, scope, expiry, revocation, forbidden
token behavior, and future enforcement boundaries. It does not enforce runtime
approval checks, validate live confirmations, issue tokens, approve/reject work,
apply patches, run validation or benchmarks, call models, launch workers, invoke
MCP tools, use network access, execute subprocesses, write to databases, or
change route/auth behavior.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "human_approval_token_contract"
THIS_PHASE_ID = "HUMAN.N2"

STATUS_READY = "approval_token_contract_ready"
STATUS_READY_WITH_WARNINGS = "approval_token_contract_ready_with_warnings"
STATUS_INCOMPLETE = "approval_token_contract_incomplete"
STATUS_BLOCKED = "approval_token_contract_blocked"

JSON_NAME = "human_approval_token_contract.json"
MD_NAME = "human_approval_token_contract.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "human" / "approval_token_contract"

TOKEN_SCHEMA_FIELDS: tuple[str, ...] = (
    "token_id",
    "approval_action",
    "target_type",
    "target_id",
    "target_artifact_path",
    "risk_level",
    "confirmation_text",
    "confirmation_scope",
    "operator_id",
    "created_at",
    "expires_at",
    "revoked_at",
    "revocation_reason",
    "single_use",
    "consumed_at",
    "evidence_refs",
    "boundary_refs",
    "warnings",
    "metadata",
)

REQUIRED_FIELDS: tuple[str, ...] = (
    "token_id",
    "approval_action",
    "target_type",
    "target_id",
    "risk_level",
    "confirmation_text",
    "confirmation_scope",
    "created_at",
    "single_use",
)

ALLOWED_APPROVAL_ACTIONS: tuple[str, ...] = (
    "approve_patch_apply",
    "approve_worker_launch",
    "approve_validation_run",
    "approve_benchmark_run",
    "approve_model_catalog_adoption",
    "approve_registry_mutation",
    "approve_mcp_tool_invocation",
    "approve_network_access",
    "approve_database_write",
    "approve_auth_policy_change",
    "approve_remote_execution",
    "approve_replay_apply",
    "approve_dream_execution",
)

TARGET_TYPES: tuple[str, ...] = (
    "patch",
    "worker_task",
    "validation_plan",
    "benchmark_plan",
    "model_catalog",
    "registry",
    "mcp_tool",
    "network_request",
    "database_change",
    "auth_policy",
    "remote_command",
    "replay_action",
    "dream_run",
    "evidence_report",
    "other",
)

RISK_LEVELS: tuple[str, ...] = ("low", "medium", "high", "critical", "unknown")

CONFIRMATION_SCOPES: tuple[str, ...] = (
    "single_artifact",
    "single_run",
    "single_action",
    "branch_checkpoint",
    "time_limited_session",
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "HUMAN.N3",
    "title": "Human Approval Token Dry-Run Validator",
    "reason": (
        "Validate sample approval tokens against the HUMAN.N2 contract without "
        "enforcing runtime behavior."
    ),
}

ALTERNATIVE_NEXT_PHASE = {
    "phase_id": "HUMAN.CLOSE",
    "title": "Human Authority Branch Checkpoint",
    "reason": "Freeze the human authority branch after confirmation semantics are clear.",
}

GUARDRAIL_NOTE = (
    "HUMAN.N2 is report-only and contract-only. It defines the future shape of "
    "explicit human approval signals before dangerous actions; it does not issue "
    "tokens or enforce approvals."
)

DEFAULT_WARNINGS: tuple[str, ...] = (
    "Future HUMAN.N3 should validate sample tokens against this contract.",
    "This contract intentionally adds no runtime enforcement.",
)

APPROVAL_PHILOSOPHY: tuple[str, ...] = (
    "Approval must be explicit, human-authored, scoped, and tied to a target.",
    "Advisory reports, high evidence quality, Mirror scores, Commander readiness, and model role readiness cannot imply approval.",
    "Dangerous actions require action-specific approval before any future enforcement phase may authorize them.",
    "Tokens should expire or be single-use when risk, scope, or session boundaries make reuse unsafe.",
)

FIELD_DESCRIPTIONS: dict[str, str] = {
    "token_id": "Stable identifier for the approval token.",
    "approval_action": "The exact dangerous action approved by the human.",
    "target_type": "The kind of target the approval applies to.",
    "target_id": "The specific target identifier within the target type.",
    "target_artifact_path": "Optional local artifact path tied to the approval target.",
    "risk_level": "Human-visible risk level for the approved action.",
    "confirmation_text": "Human-readable explicit approval text.",
    "confirmation_scope": "Scope limiting where the token can be used.",
    "operator_id": "Optional identifier for the human operator.",
    "created_at": "Timestamp when the approval signal was recorded.",
    "expires_at": "Optional timestamp after which the token must not authorize future action.",
    "revoked_at": "Optional timestamp when the token was revoked.",
    "revocation_reason": "Optional reason for revocation.",
    "single_use": "Whether the token may be consumed only once.",
    "consumed_at": "Optional timestamp when a single-use token was consumed.",
    "evidence_refs": "Optional evidence artifact references considered by the human.",
    "boundary_refs": "Optional HUMAN.N1/HUMAN.N2 boundary references.",
    "warnings": "Optional human-visible caveats for later review.",
    "metadata": "Optional structured metadata for future validators.",
}

DEFAULT_CONFIRMATION_TEXT_RULES: dict[str, Any] = {
    "must_be_explicit": True,
    "must_mention_action": True,
    "must_mention_target": True,
    "must_not_be_empty": True,
    "generic_confirmation_allowed": False,
    "generic_disallowed_examples": ["yes", "ok", "do it"],
    "high_or_critical_requires_stronger_text": True,
    "future_enforcement_comparison": "future enforcement should compare action + target + risk in text",
}

DEFAULT_SCOPE_RULES: dict[str, Any] = {
    "allowed_scopes": list(CONFIRMATION_SCOPES),
    "must_bind_to_target": True,
    "must_not_approve_broader_scope": True,
    "must_not_reuse_across_unrelated_targets": True,
    "branch_checkpoint_scope_requires_named_branch": True,
    "time_limited_session_requires_expiry": True,
}

DEFAULT_EXPIRY_POLICY: dict[str, Any] = {
    "high_or_critical_should_expire": True,
    "time_limited_session_should_expire": True,
    "default_expiry_may_be_unset_for_report_only_contract": True,
    "future_enforcement_should_prefer_expiry": True,
    "expired_token_must_not_authorize_future_action": True,
}

DEFAULT_REVOCATION_POLICY: dict[str, Any] = {
    "revoked_token_must_not_authorize_future_action": True,
    "revocation_reason_should_be_recorded": True,
    "consumed_single_use_must_not_authorize_repeated_action": True,
    "revoked_at_and_consumed_at_should_be_mutually_reviewed_if_both_present": True,
}

DEFAULT_FORBIDDEN_TOKEN_BEHAVIOR: dict[str, Any] = {
    "ai_generated_approvals_allowed": False,
    "infer_from_advisory_reports_allowed": False,
    "infer_from_evidence_quality_allowed": False,
    "infer_from_mirror_score_allowed": False,
    "infer_from_commander_readiness_allowed": False,
    "infer_from_model_role_readiness_allowed": False,
    "approve_broader_scope_than_stated_allowed": False,
    "bypass_auth_gates_allowed": False,
    "reuse_across_unrelated_targets_allowed": False,
    "authorize_hidden_mutation_allowed": False,
}

DEFAULT_FUTURE_ENFORCEMENT_BOUNDARY: dict[str, Any] = {
    "runtime_enforcement_added": False,
    "live_confirmation_validation_added": False,
    "token_issuance_added": False,
    "boundary_statement": "no runtime enforcement yet; HUMAN.N2 only defines the contract",
    "future_validator_may_check": [
        "required fields",
        "allowed approval_action",
        "allowed target_type",
        "risk level",
        "confirmation text specificity",
        "scope binding",
        "expiry",
        "revocation",
        "single-use consumption",
    ],
}

HUMAN_REVIEW_CHECKLIST: tuple[str, ...] = (
    "Confirm the approval_action is one of the allowed dangerous actions.",
    "Confirm the target_type and target_id are specific.",
    "Confirm confirmation_text explicitly names the action and target.",
    "Confirm generic confirmations such as yes, ok, or do it are not accepted.",
    "Confirm high or critical risk approvals have stronger text and expiry review.",
    "Confirm revoked or consumed single-use tokens cannot authorize future action.",
    "Confirm no approval is inferred from advisory reports, scores, or readiness signals.",
)

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "enforcement_change_performed",
    "live_confirmation_validation_performed",
    "token_issuance_performed",
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
    "contract only",
    "no enforcement change",
    "no approval/rejection",
    "no token issuance",
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
    "writes contract artifacts only",
)

POLICY_SECTION_KEYS: tuple[str, ...] = (
    "confirmation_text_rules",
    "scope_rules",
    "expiry_policy",
    "revocation_policy",
    "forbidden_token_behavior",
    "future_enforcement_boundary",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _bool(value: Any) -> str:
    return str(bool(value)).lower()


def _guardrails() -> dict[str, bool]:
    data = {key: False for key in GUARDRAIL_FALSE_FLAGS}
    data["report_only"] = True
    data["contract_only"] = True
    return data


def _block(blocked: list[dict[str, str]], reason: str, message: str) -> None:
    if not any(item.get("reason") == reason for item in blocked):
        blocked.append({"reason": reason, "message": message})


def _copy_dict(value: dict[str, Any] | None, default: dict[str, Any]) -> dict[str, Any]:
    return dict(default if value is None else value)


def _token_schema(schema_fields: list[str] | tuple[str, ...]) -> dict[str, Any]:
    fields = {
        field: {
            "required": field in REQUIRED_FIELDS,
            "description": FIELD_DESCRIPTIONS.get(field, "Contract field."),
        }
        for field in schema_fields
    }
    optional = [field for field in schema_fields if field not in REQUIRED_FIELDS]
    return {
        "purpose": "Represent one explicit human approval signal before a dangerous action.",
        "fields": fields,
        "required_fields": list(REQUIRED_FIELDS),
        "optional_fields": optional,
    }


def _missing_policy_sections(sections: dict[str, dict[str, Any]]) -> list[str]:
    return sorted(key for key, value in sections.items() if not isinstance(value, dict) or not value)


def _evaluate_contract(
    *,
    schema_fields: list[str],
    allowed_actions: list[str],
    confirmation_text_rules: dict[str, Any],
    forbidden_token_behavior: dict[str, Any],
    policy_sections: dict[str, dict[str, Any]],
    warnings: list[str],
) -> tuple[str, list[str], list[str], list[str], list[dict[str, str]]]:
    missing_required = sorted(set(REQUIRED_FIELDS) - set(schema_fields))
    missing_actions = sorted(set(ALLOWED_APPROVAL_ACTIONS) - set(allowed_actions))
    missing_policy = _missing_policy_sections(policy_sections)
    blocked: list[dict[str, str]] = []

    if missing_required:
        _block(
            blocked,
            "missing_required_schema_fields",
            "Required token schema fields are missing: " + ", ".join(missing_required),
        )
    if missing_actions:
        _block(
            blocked,
            "missing_dangerous_approval_actions",
            "Dangerous approval actions are missing: " + ", ".join(missing_actions),
        )
    if confirmation_text_rules.get("generic_confirmation_allowed") is True:
        _block(
            blocked,
            "generic_confirmation_allowed",
            "Generic confirmations such as yes/ok/do it must not be allowed.",
        )
    if forbidden_token_behavior.get("ai_generated_approvals_allowed") is True:
        _block(
            blocked,
            "ai_generated_approvals_allowed",
            "Tokens must not be generated silently by AI.",
        )
    if forbidden_token_behavior.get("bypass_auth_gates_allowed") is True:
        _block(
            blocked,
            "tokens_bypass_auth_allowed",
            "Tokens must not bypass auth gates.",
        )

    if blocked:
        return STATUS_BLOCKED, missing_required, missing_actions, missing_policy, blocked
    if missing_policy:
        return STATUS_INCOMPLETE, missing_required, missing_actions, missing_policy, blocked
    if warnings:
        return STATUS_READY_WITH_WARNINGS, [], [], [], blocked
    return STATUS_READY, [], [], [], blocked


def build_human_approval_token_contract(
    *,
    report_id: str = "",
    created_at: str = "",
    schema_fields: list[str] | tuple[str, ...] | None = None,
    allowed_actions: list[str] | tuple[str, ...] | None = None,
    target_types: list[str] | tuple[str, ...] | None = None,
    risk_levels: list[str] | tuple[str, ...] | None = None,
    confirmation_scopes: list[str] | tuple[str, ...] | None = None,
    confirmation_text_rules: dict[str, Any] | None = None,
    scope_rules: dict[str, Any] | None = None,
    expiry_policy: dict[str, Any] | None = None,
    revocation_policy: dict[str, Any] | None = None,
    forbidden_token_behavior: dict[str, Any] | None = None,
    future_enforcement_boundary: dict[str, Any] | None = None,
    warnings: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Build the HUMAN.N2 report-only approval-token contract."""
    schema_field_list = [str(field) for field in (TOKEN_SCHEMA_FIELDS if schema_fields is None else schema_fields)]
    allowed_action_list = [str(action) for action in (ALLOWED_APPROVAL_ACTIONS if allowed_actions is None else allowed_actions)]
    target_type_list = [str(target) for target in (TARGET_TYPES if target_types is None else target_types)]
    risk_level_list = [str(risk) for risk in (RISK_LEVELS if risk_levels is None else risk_levels)]
    scope_list = [str(scope) for scope in (CONFIRMATION_SCOPES if confirmation_scopes is None else confirmation_scopes)]
    confirmation_rules = _copy_dict(confirmation_text_rules, DEFAULT_CONFIRMATION_TEXT_RULES)
    scope_policy = _copy_dict(scope_rules, DEFAULT_SCOPE_RULES)
    expiry = _copy_dict(expiry_policy, DEFAULT_EXPIRY_POLICY)
    revocation = _copy_dict(revocation_policy, DEFAULT_REVOCATION_POLICY)
    forbidden = _copy_dict(forbidden_token_behavior, DEFAULT_FORBIDDEN_TOKEN_BEHAVIOR)
    future_boundary = _copy_dict(future_enforcement_boundary, DEFAULT_FUTURE_ENFORCEMENT_BOUNDARY)
    warning_list = [str(item) for item in (DEFAULT_WARNINGS if warnings is None else warnings)]

    policy_sections = {
        "confirmation_text_rules": confirmation_rules,
        "scope_rules": scope_policy,
        "expiry_policy": expiry,
        "revocation_policy": revocation,
        "forbidden_token_behavior": forbidden,
        "future_enforcement_boundary": future_boundary,
    }
    status, missing_required, missing_actions, missing_policy, blocked = _evaluate_contract(
        schema_fields=schema_field_list,
        allowed_actions=allowed_action_list,
        confirmation_text_rules=confirmation_rules,
        forbidden_token_behavior=forbidden,
        policy_sections=policy_sections,
        warnings=warning_list,
    )
    schema = _token_schema(schema_field_list)
    summary = {
        "contract_status": status,
        "schema_field_count": len(schema_field_list),
        "required_field_count": len(REQUIRED_FIELDS),
        "missing_required_fields": list(missing_required),
        "allowed_approval_action_count": len(allowed_action_list),
        "missing_dangerous_approval_actions": list(missing_actions),
        "target_type_count": len(target_type_list),
        "risk_level_count": len(risk_level_list),
        "confirmation_scope_count": len(scope_list),
        "missing_policy_sections": list(missing_policy),
        "policy_sections_complete": not missing_policy,
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
        "contract_status": status,
        "summary": summary,
        "approval_philosophy": list(APPROVAL_PHILOSOPHY),
        "approval_token_purpose": schema["purpose"],
        "token_schema": schema,
        "required_fields": list(REQUIRED_FIELDS),
        "optional_fields": list(schema["optional_fields"]),
        "allowed_approval_actions": allowed_action_list,
        "target_types": target_type_list,
        "risk_levels": risk_level_list,
        "confirmation_scopes": scope_list,
        "confirmation_text_rules": confirmation_rules,
        "scope_rules": scope_policy,
        "expiry_policy": expiry,
        "revocation_policy": revocation,
        "forbidden_token_behavior": forbidden,
        "future_enforcement_boundary": future_boundary,
        "human_review_checklist": list(HUMAN_REVIEW_CHECKLIST),
        "warnings": warning_list,
        "blocked_reasons": blocked,
        "incomplete_reasons": list(missing_policy),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "alternative_next_phase": dict(ALTERNATIVE_NEXT_PHASE),
        "final_verdict": {
            "status": status,
            "contract_ready": status == STATUS_READY,
            "contract_ready_with_warnings": status == STATUS_READY_WITH_WARNINGS,
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


def _list_lines(values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        return ["_None._"]
    return [f"- {_md(item)}" for item in values]


def render_human_approval_token_contract_markdown(report: dict[str, Any]) -> str:
    """Render the HUMAN.N2 approval-token contract as Markdown."""
    lines: list[str] = [
        "# Human Approval Token / Confirmation Contract",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
    ]
    lines.extend(_dict_lines(report.get("summary")))
    lines.extend(["", "## Approval Philosophy", ""])
    lines.extend(_list_lines(report.get("approval_philosophy") if isinstance(report.get("approval_philosophy"), list) else []))
    lines.extend(["", "## Token Schema", ""])
    schema = report.get("token_schema") if isinstance(report.get("token_schema"), dict) else {}
    fields = schema.get("fields") if isinstance(schema.get("fields"), dict) else {}
    if fields:
        lines.extend(["| Field | Required | Description |", "|---|---|---|"])
        for field in fields:
            meta = fields[field] if isinstance(fields[field], dict) else {}
            lines.append(
                f"| `{_md(field)}` | {_bool(meta.get('required'))} | {_md(meta.get('description', ''))} |"
            )
    else:
        lines.append("_None._")
    lines.extend(["", "## Required Fields", ""])
    lines.extend(_list_lines(report.get("required_fields") if isinstance(report.get("required_fields"), list) else []))
    lines.extend(["", "## Allowed Actions", ""])
    lines.extend(_list_lines(report.get("allowed_approval_actions") if isinstance(report.get("allowed_approval_actions"), list) else []))
    lines.extend(["", "## Target Types", ""])
    lines.extend(_list_lines(report.get("target_types") if isinstance(report.get("target_types"), list) else []))
    lines.extend(["", "## Risk Levels", ""])
    lines.extend(_list_lines(report.get("risk_levels") if isinstance(report.get("risk_levels"), list) else []))
    lines.extend(["", "## Confirmation Text Rules", ""])
    lines.extend(_dict_lines(report.get("confirmation_text_rules")))
    lines.extend(["", "## Scope Rules", ""])
    lines.extend(_dict_lines(report.get("scope_rules")))
    lines.extend(["", "## Expiry Policy", ""])
    lines.extend(_dict_lines(report.get("expiry_policy")))
    lines.extend(["", "## Revocation Policy", ""])
    lines.extend(_dict_lines(report.get("revocation_policy")))
    lines.extend(["", "## Forbidden Token Behavior", ""])
    lines.extend(_dict_lines(report.get("forbidden_token_behavior")))
    lines.extend(["", "## Future Enforcement Boundary", ""])
    lines.extend(_dict_lines(report.get("future_enforcement_boundary")))
    lines.extend(["", "## Human Review Checklist", ""])
    lines.extend(_list_lines(report.get("human_review_checklist") if isinstance(report.get("human_review_checklist"), list) else []))
    lines.extend(["", "## Guardrails", ""])
    lines.extend(_list_lines(report.get("boundaries_guardrails") if isinstance(report.get("boundaries_guardrails"), list) else []))
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


def write_human_approval_token_contract(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build and write HUMAN.N2 JSON/Markdown contract artifacts."""
    report = build_human_approval_token_contract(report_id=report_id, created_at=created_at)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_human_approval_token_contract_markdown(report), encoding="utf-8")
    return {
        "ok": report["contract_status"] in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
