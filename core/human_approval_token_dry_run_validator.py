"""HUMAN.N3 - Human Approval Token Dry-Run Validator.

Validates sample approval-token artifacts against the HUMAN.N2 token contract and
writes dry-run reports only. This module does not authorize actions, reject live
actions, enforce route behavior, consume tokens, issue tokens, apply patches, run
validation or benchmarks, call models, route models, launch workers, invoke MCP
tools, use network access, write to databases, or change auth/route policy.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "human_approval_token_dry_run"
THIS_PHASE_ID = "HUMAN.N3"

STATUS_VALID = "token_dry_run_valid"
STATUS_VALID_WITH_WARNINGS = "token_dry_run_valid_with_warnings"
STATUS_INVALID = "token_dry_run_invalid"
STATUS_BLOCKED = "token_dry_run_blocked"

JSON_NAME = "human_approval_token_dry_run.json"
MD_NAME = "human_approval_token_dry_run.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "human" / "approval_token_dry_run"
DEFAULT_CONTRACT_PATH = (
    Path(".agent")
    / "human"
    / "approval_token_contract"
    / "human_approval_token_contract.json"
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "HUMAN.N4",
    "title": "Human Approval Token Sample Catalog",
    "reason": (
        "Create safe sample valid and invalid approval tokens for documentation "
        "and future tests, still without runtime enforcement."
    ),
}

ALTERNATIVE_NEXT_PHASE = {
    "phase_id": "HUMAN.CLOSE",
    "title": "Human Authority Branch Checkpoint",
    "reason": "Freeze the human authority branch after dry-run token validation.",
}

GUARDRAIL_NOTE = (
    "HUMAN.N3 is report-only and dry-run-only. It validates sample approval-token "
    "artifacts against the HUMAN.N2 contract and writes reports; it does not "
    "authorize, reject, enforce, consume, issue, execute, route, or mutate."
)

GENERIC_CONFIRMATIONS: tuple[str, ...] = (
    "yes",
    "ok",
    "okay",
    "do it",
    "approved",
    "sure",
    "go",
    "proceed",
)

FORBIDDEN_METADATA_KEYS: tuple[str, ...] = (
    "auto_run",
    "auto_apply",
    "auto_merge",
    "route_tasks",
    "launch_worker",
    "bypass_auth",
    "hidden_mutation",
    "ai_generated_approval",
)

FORBIDDEN_PATH_PARTS: tuple[str, ...] = (
    ".env",
    ".git",
    "secrets",
    "credentials",
)

FORBIDDEN_PATH_FRAGMENTS: tuple[str, ...] = (
    ".agent/private",
    "id_rsa",
    "id_dsa",
    "private_key",
)

BOUNDARY_GUARDRAILS: tuple[str, ...] = (
    "report-only",
    "dry-run validation only",
    "no runtime enforcement",
    "no approval/rejection",
    "no token consumption",
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
    "writes dry-run artifacts only",
)

REPORT_SECTIONS: tuple[str, ...] = (
    "summary",
    "source_token",
    "contract_reference",
    "schema_findings",
    "action_findings",
    "target_findings",
    "confirmation_text_findings",
    "scope_findings",
    "expiry_findings",
    "revocation_findings",
    "reuse_findings",
    "evidence_reference_findings",
    "authority_boundary_findings",
    "warnings",
    "blocked_reasons",
    "dry_run_verdict",
    "future_enforcement_boundary",
    "recommended_next_phase",
)

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "none", "null"}
    return bool(value)


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _safe_token_id(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and bool(_SAFE_ID_RE.fullmatch(text))


def _output_token_dir(value: Any) -> str:
    text = str(value or "").strip()
    return text if _safe_token_id(text) else "sample"


def _path_parts(raw_path: Any) -> list[str]:
    text = str(raw_path or "").replace("\\", "/")
    return [part.lower() for part in text.split("/") if part not in {"", "."}]


def _unsafe_path_reason(raw_path: Any) -> str:
    text = str(raw_path or "").strip().replace("\\", "/").lower()
    if not text:
        return ""
    if "\x00" in text:
        return "path_contains_nul"
    parts = _path_parts(text)
    if any(part == ".." for part in parts):
        return "path_contains_parent_traversal"
    for forbidden in FORBIDDEN_PATH_PARTS:
        if forbidden in parts or text.endswith("/" + forbidden) or text == forbidden:
            return "path_points_to_forbidden_secret"
    for fragment in FORBIDDEN_PATH_FRAGMENTS:
        if fragment in text:
            return "path_points_to_forbidden_secret"
    return ""


def _finding(severity: str, reason: str, message: str, field: str = "") -> dict[str, str]:
    item = {"severity": severity, "reason": reason, "message": message}
    if field:
        item["field"] = field
    return item


def _append_unique(items: list[dict[str, str]], item: dict[str, str]) -> None:
    reason = item.get("reason")
    field = item.get("field", "")
    if not any(existing.get("reason") == reason and existing.get("field", "") == field for existing in items):
        items.append(item)


def _parse_iso(value: Any) -> datetime | None:
    if _is_blank(value):
        return None
    text = str(value).strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _contract_lists(contract: dict[str, Any]) -> dict[str, list[str]]:
    scope_rules = contract.get("scope_rules") if isinstance(contract.get("scope_rules"), dict) else {}
    return {
        "required_fields": [str(item) for item in (contract.get("required_fields") or [])],
        "allowed_actions": [str(item) for item in (contract.get("allowed_approval_actions") or [])],
        "target_types": [str(item) for item in (contract.get("target_types") or [])],
        "risk_levels": [str(item) for item in (contract.get("risk_levels") or [])],
        "confirmation_scopes": [
            str(item)
            for item in (
                contract.get("confirmation_scopes")
                or scope_rules.get("allowed_scopes")
                or []
            )
        ],
    }


def _contract_missing_sections(contract: Any) -> list[str]:
    if not isinstance(contract, dict):
        return ["contract_json_object"]
    lists = _contract_lists(contract)
    missing: list[str] = []
    for key, value in lists.items():
        if not value:
            missing.append(key)
    return missing


def _action_phrase(action: Any) -> str:
    text = str(action or "").lower().strip()
    if text.startswith("approve_"):
        text = text[len("approve_"):]
    return text.replace("_", " ")


def _text_mentions_action(text: str, action: Any) -> bool:
    action_text = str(action or "").lower().strip()
    phrase = _action_phrase(action)
    compact_phrase = phrase.replace(" ", "_")
    return bool(
        action_text
        and (
            action_text in text
            or phrase in text
            or compact_phrase in text
        )
    )


def _text_mentions_target(text: str, target_id: Any, target_type: Any) -> bool:
    target_id_text = str(target_id or "").lower().strip()
    target_type_text = str(target_type or "").lower().strip()
    return bool(
        (target_id_text and target_id_text in text)
        or (target_type_text and target_type_text in text)
    )


def _all_findings(report: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for key in (
        "schema_findings",
        "action_findings",
        "target_findings",
        "confirmation_text_findings",
        "scope_findings",
        "expiry_findings",
        "revocation_findings",
        "reuse_findings",
        "evidence_reference_findings",
        "authority_boundary_findings",
    ):
        values = report.get(key)
        if isinstance(values, list):
            findings.extend(item for item in values if isinstance(item, dict))
    return findings


def _boundaries() -> dict[str, bool]:
    return {
        "report_only": True,
        "dry_run_only": True,
        "validates_sample_artifacts_only": True,
        "authorizes_action": False,
        "rejects_real_action": False,
        "enforces_runtime_behavior": False,
        "enforces_routes": False,
        "consumes_token": False,
        "issues_token": False,
        "applies_patches": False,
        "runs_validation": False,
        "runs_benchmarks": False,
        "calls_models": False,
        "routes_models": False,
        "launches_workers": False,
        "invokes_mcp": False,
        "uses_network": False,
        "writes_database": False,
        "changes_auth_policy": False,
        "mutates_registry": False,
        "writes_dry_run_artifacts_only": True,
    }


def _empty_report(
    *,
    token: Any,
    contract: Any,
    source_token_path: str,
    source_contract_path: str,
    report_id: str,
    created_at: str,
    preblocked: list[dict[str, str]] | None,
) -> dict[str, Any]:
    token_map = token if isinstance(token, dict) else {}
    token_id = str(token_map.get("token_id") or "sample")
    dry_run_id = str(report_id or "")
    if not dry_run_id:
        dry_run_id = f"human-n3-{_output_token_dir(token_id)}"
    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "guardrail_note": GUARDRAIL_NOTE,
        "dry_run_id": dry_run_id,
        "created_at": str(created_at or _utc_now()),
        "token_id": token_id,
        "source_token_path": str(source_token_path or ""),
        "source_contract_path": str(source_contract_path or ""),
        "dry_run_status": STATUS_BLOCKED,
        "token_summary": {
            "approval_action": str(token_map.get("approval_action") or ""),
            "target_type": str(token_map.get("target_type") or ""),
            "target_id": str(token_map.get("target_id") or ""),
            "risk_level": str(token_map.get("risk_level") or ""),
            "confirmation_scope": str(token_map.get("confirmation_scope") or ""),
            "single_use": bool(token_map.get("single_use")) if "single_use" in token_map else False,
            "has_expires_at": not _is_blank(token_map.get("expires_at")),
            "has_revoked_at": not _is_blank(token_map.get("revoked_at")),
            "has_consumed_at": not _is_blank(token_map.get("consumed_at")),
        },
        "schema_findings": [],
        "action_findings": [],
        "target_findings": [],
        "confirmation_text_findings": [],
        "scope_findings": [],
        "expiry_findings": [],
        "revocation_findings": [],
        "reuse_findings": [],
        "evidence_reference_findings": [],
        "authority_boundary_findings": [],
        "warnings": [],
        "blocked_reasons": list(preblocked or []),
        "boundaries": _boundaries(),
        "boundary_guardrails": list(BOUNDARY_GUARDRAILS),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "alternative_next_phase": dict(ALTERNATIVE_NEXT_PHASE),
        "future_enforcement_boundary": {
            "runtime_enforcement_added": False,
            "live_confirmation_validation_added": False,
            "token_consumption_added": False,
            "approval_authority_added": False,
            "boundary_statement": (
                "HUMAN.N3 reports how a sample token would validate in a future "
                "enforcement phase; it does not authorize any action now."
            ),
        },
        "report_sections": list(REPORT_SECTIONS),
    }


def _evaluate_schema(report: dict[str, Any], token: dict[str, Any], lists: dict[str, list[str]]) -> None:
    required_fields = lists["required_fields"]
    for field in required_fields:
        if field not in token or _is_blank(token.get(field)):
            _append_unique(
                report["schema_findings"],
                _finding("invalid", "missing_required_field", f"Required field is missing: {field}", field),
            )

    token_id = token.get("token_id")
    if not _is_blank(token_id) and not _safe_token_id(token_id):
        _append_unique(
            report["schema_findings"],
            _finding(
                "invalid",
                "unsafe_token_id",
                "token_id must contain only letters, numbers, dot, underscore, or hyphen.",
                "token_id",
            ),
        )

    risk_level = str(token.get("risk_level") or "")
    if risk_level and risk_level not in lists["risk_levels"]:
        _append_unique(
            report["schema_findings"],
            _finding("invalid", "unknown_risk_level", f"Unknown risk_level: {risk_level}", "risk_level"),
        )


def _evaluate_action_target(report: dict[str, Any], token: dict[str, Any], lists: dict[str, list[str]]) -> None:
    action = str(token.get("approval_action") or "")
    if action and action not in lists["allowed_actions"]:
        _append_unique(
            report["action_findings"],
            _finding(
                "invalid",
                "unknown_approval_action",
                f"approval_action is not allowed by HUMAN.N2: {action}",
                "approval_action",
            ),
        )

    target_type = str(token.get("target_type") or "")
    if target_type and target_type not in lists["target_types"]:
        _append_unique(
            report["target_findings"],
            _finding(
                "invalid",
                "unknown_target_type",
                f"target_type is not allowed by HUMAN.N2: {target_type}",
                "target_type",
            ),
        )

    target_path = token.get("target_artifact_path")
    reason = _unsafe_path_reason(target_path)
    if reason:
        _append_unique(
            report["blocked_reasons"],
            _finding(
                "blocked",
                "unsafe_target_artifact_path",
                f"target_artifact_path is unsafe: {reason}",
                "target_artifact_path",
            ),
        )


def _evaluate_confirmation_text(report: dict[str, Any], token: dict[str, Any]) -> None:
    raw_text = token.get("confirmation_text")
    text = str(raw_text or "").strip()
    normalized = text.lower().strip(" \t\r\n.!?,;:")
    if not text:
        _append_unique(
            report["confirmation_text_findings"],
            _finding(
                "invalid",
                "empty_confirmation_text",
                "confirmation_text must not be empty.",
                "confirmation_text",
            ),
        )
        return
    if normalized in GENERIC_CONFIRMATIONS:
        _append_unique(
            report["confirmation_text_findings"],
            _finding(
                "invalid",
                "generic_confirmation_text",
                "confirmation_text is too generic for scoped human approval.",
                "confirmation_text",
            ),
        )
        return

    low = text.lower()
    if not _text_mentions_action(low, token.get("approval_action")):
        _append_unique(
            report["confirmation_text_findings"],
            _finding(
                "warning",
                "weak_confirmation_missing_action",
                "confirmation_text should mention the approval action or a human-readable action phrase.",
                "confirmation_text",
            ),
        )
    if not _text_mentions_target(low, token.get("target_id"), token.get("target_type")):
        _append_unique(
            report["confirmation_text_findings"],
            _finding(
                "warning",
                "weak_confirmation_missing_target",
                "confirmation_text should mention target_id or target_type.",
                "confirmation_text",
            ),
        )
    risk = str(token.get("risk_level") or "").lower()
    if risk in {"high", "critical"} and risk not in low:
        _append_unique(
            report["confirmation_text_findings"],
            _finding(
                "warning",
                "weak_high_or_critical_confirmation_text",
                "high or critical risk approvals should explicitly name the risk level.",
                "confirmation_text",
            ),
        )


def _evaluate_scope(report: dict[str, Any], token: dict[str, Any], lists: dict[str, list[str]]) -> None:
    scope = str(token.get("confirmation_scope") or "")
    if scope and scope not in lists["confirmation_scopes"]:
        _append_unique(
            report["scope_findings"],
            _finding(
                "invalid",
                "unknown_confirmation_scope",
                f"confirmation_scope is not allowed by HUMAN.N2: {scope}",
                "confirmation_scope",
            ),
        )
    if scope.lower() in {"all", "all_actions", "global", "unlimited", "*"}:
        _append_unique(
            report["scope_findings"],
            _finding(
                "invalid",
                "scope_too_broad",
                "confirmation_scope must not be broader than approval_action and target.",
                "confirmation_scope",
            ),
        )
    if scope == "time_limited_session" and _is_blank(token.get("expires_at")):
        _append_unique(
            report["scope_findings"],
            _finding(
                "warning",
                "time_limited_scope_without_expiry",
                "time_limited_session scope should include expires_at.",
                "expires_at",
            ),
        )


def _evaluate_expiry_revocation_reuse(
    report: dict[str, Any],
    token: dict[str, Any],
    *,
    now: str,
) -> None:
    now_dt = _parse_iso(now) or datetime.now(timezone.utc)
    expires_at = token.get("expires_at")
    expires_dt = _parse_iso(expires_at)
    if not _is_blank(expires_at) and expires_dt is None:
        _append_unique(
            report["expiry_findings"],
            _finding("invalid", "malformed_expires_at", "expires_at must be an ISO timestamp.", "expires_at"),
        )
    elif expires_dt is not None and expires_dt <= now_dt:
        _append_unique(
            report["expiry_findings"],
            _finding("invalid", "token_expired", "expires_at is in the past for this dry run.", "expires_at"),
        )
    elif str(token.get("risk_level") or "").lower() in {"high", "critical"} and expires_dt is None:
        _append_unique(
            report["expiry_findings"],
            _finding(
                "warning",
                "high_or_critical_without_expiry",
                "high or critical risk tokens should include expires_at.",
                "expires_at",
            ),
        )

    revoked_at = token.get("revoked_at")
    if not _is_blank(revoked_at):
        if _parse_iso(revoked_at) is None:
            _append_unique(
                report["revocation_findings"],
                _finding("invalid", "malformed_revoked_at", "revoked_at must be an ISO timestamp.", "revoked_at"),
            )
        _append_unique(
            report["revocation_findings"],
            _finding("invalid", "token_revoked", "revoked token would be invalid for future use.", "revoked_at"),
        )
        if _is_blank(token.get("revocation_reason")):
            _append_unique(
                report["revocation_findings"],
                _finding(
                    "warning",
                    "revocation_without_reason",
                    "revoked token should include revocation_reason.",
                    "revocation_reason",
                ),
            )

    consumed_at = token.get("consumed_at")
    if _truthy(token.get("single_use")) and not _is_blank(consumed_at):
        if _parse_iso(consumed_at) is None:
            _append_unique(
                report["reuse_findings"],
                _finding("invalid", "malformed_consumed_at", "consumed_at must be an ISO timestamp.", "consumed_at"),
            )
        _append_unique(
            report["reuse_findings"],
            _finding(
                "invalid",
                "single_use_token_already_consumed",
                "single-use token with consumed_at would be invalid for future use.",
                "consumed_at",
            ),
        )


def _evaluate_references(report: dict[str, Any], token: dict[str, Any]) -> None:
    evidence_refs = token.get("evidence_refs")
    boundary_refs = token.get("boundary_refs")
    operator_id = token.get("operator_id")
    if not operator_id:
        _append_unique(
            report["authority_boundary_findings"],
            _finding("warning", "missing_operator_id", "operator_id is optional but recommended.", "operator_id"),
        )
    if not isinstance(evidence_refs, list) or not evidence_refs:
        _append_unique(
            report["evidence_reference_findings"],
            _finding(
                "warning",
                "missing_evidence_refs",
                "evidence_refs are optional but recommended for review traceability.",
                "evidence_refs",
            ),
        )
    else:
        _append_unique(
            report["evidence_reference_findings"],
            _finding(
                "info",
                "evidence_refs_advisory_only",
                "evidence_refs are advisory references only and are not approval sources.",
                "evidence_refs",
            ),
        )
    if not isinstance(boundary_refs, list) or not boundary_refs:
        _append_unique(
            report["authority_boundary_findings"],
            _finding(
                "warning",
                "missing_boundary_refs",
                "boundary_refs are optional but recommended for HUMAN.N1/HUMAN.N2 traceability.",
                "boundary_refs",
            ),
        )
    else:
        _append_unique(
            report["authority_boundary_findings"],
            _finding(
                "info",
                "boundary_refs_advisory_only",
                "boundary_refs are advisory references only and are not approval sources.",
                "boundary_refs",
            ),
        )


def _evaluate_metadata(report: dict[str, Any], token: dict[str, Any]) -> None:
    metadata = token.get("metadata")
    if metadata is None:
        return
    if not isinstance(metadata, dict):
        _append_unique(
            report["schema_findings"],
            _finding("invalid", "metadata_not_object", "metadata must be an object when present.", "metadata"),
        )
        return
    for key in FORBIDDEN_METADATA_KEYS:
        if key in metadata and _truthy(metadata.get(key)):
            _append_unique(
                report["blocked_reasons"],
                _finding(
                    "blocked",
                    f"metadata_{key}_forbidden",
                    f"metadata must not grant or imply {key} authority.",
                    f"metadata.{key}",
                ),
            )


def _copy_token_warnings(report: dict[str, Any], token: dict[str, Any]) -> None:
    warnings = token.get("warnings")
    if isinstance(warnings, list):
        for warning in warnings:
            if not _is_blank(warning):
                report["warnings"].append(str(warning))
    elif warnings not in (None, ""):
        _append_unique(
            report["schema_findings"],
            _finding("invalid", "warnings_not_list", "warnings must be a list when present.", "warnings"),
        )


def _finalize_status(report: dict[str, Any]) -> None:
    findings = _all_findings(report)
    if report["blocked_reasons"]:
        status = STATUS_BLOCKED
    elif any(item.get("severity") == "invalid" for item in findings):
        status = STATUS_INVALID
    elif report["warnings"] or any(item.get("severity") == "warning" for item in findings):
        status = STATUS_VALID_WITH_WARNINGS
    else:
        status = STATUS_VALID
    report["dry_run_status"] = status
    report["token_summary"]["schema_finding_count"] = len(report["schema_findings"])
    report["token_summary"]["blocked_reason_count"] = len(report["blocked_reasons"])
    report["token_summary"]["warning_count"] = len(report["warnings"]) + sum(
        1 for item in findings if item.get("severity") == "warning"
    )
    report["final_verdict"] = {
        "status": status,
        "dry_run_valid": status == STATUS_VALID,
        "dry_run_valid_with_warnings": status == STATUS_VALID_WITH_WARNINGS,
        "dry_run_invalid": status == STATUS_INVALID,
        "dry_run_blocked": status == STATUS_BLOCKED,
        "authorizes_action": False,
        "rejects_real_action": False,
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
    }


def build_human_approval_token_dry_run(
    *,
    token: Any,
    contract: Any,
    source_token_path: str = "",
    source_contract_path: str = "",
    report_id: str = "",
    created_at: str = "",
    now: str = "",
    preblocked: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a HUMAN.N3 report-only dry-run validation record."""
    report = _empty_report(
        token=token,
        contract=contract,
        source_token_path=source_token_path,
        source_contract_path=source_contract_path,
        report_id=report_id,
        created_at=created_at,
        preblocked=preblocked,
    )

    token_path_reason = _unsafe_path_reason(source_token_path)
    if token_path_reason:
        _append_unique(
            report["blocked_reasons"],
            _finding("blocked", "unsafe_token_path", f"Token path is unsafe: {token_path_reason}", "token_path"),
        )
    contract_path_reason = _unsafe_path_reason(source_contract_path)
    if contract_path_reason:
        _append_unique(
            report["blocked_reasons"],
            _finding(
                "blocked",
                "forbidden_secret_path",
                f"Contract path is unsafe: {contract_path_reason}",
                "contract_path",
            ),
        )

    if not isinstance(token, dict):
        _append_unique(
            report["blocked_reasons"],
            _finding("blocked", "malformed_token_json", "Token JSON must be an object."),
        )
        _finalize_status(report)
        return report

    missing_contract = _contract_missing_sections(contract)
    if missing_contract:
        reason = "malformed_contract" if isinstance(contract, dict) else "malformed_contract_json"
        if not any(item.get("reason") in {"missing_contract", "malformed_contract_json"} for item in report["blocked_reasons"]):
            _append_unique(
                report["blocked_reasons"],
                _finding(
                    "blocked",
                    reason,
                    "Contract is missing required HUMAN.N2 sections: " + ", ".join(missing_contract),
                ),
            )
        _copy_token_warnings(report, token)
        _finalize_status(report)
        return report

    lists = _contract_lists(contract)
    _evaluate_schema(report, token, lists)
    _evaluate_action_target(report, token, lists)
    _evaluate_confirmation_text(report, token)
    _evaluate_scope(report, token, lists)
    _evaluate_expiry_revocation_reuse(report, token, now=now or _utc_now())
    _evaluate_references(report, token)
    _evaluate_metadata(report, token)
    _copy_token_warnings(report, token)
    _finalize_status(report)
    return report


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


def _finding_lines(values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        return ["_None._"]
    lines: list[str] = []
    for item in values:
        if not isinstance(item, dict):
            lines.append(f"- {_md(item)}")
            continue
        field = f" `{_md(item.get('field'))}`" if item.get("field") else ""
        lines.append(
            f"- **{_md(item.get('severity', 'info'))}**{field}: "
            f"{_md(item.get('reason', ''))} - {_md(item.get('message', ''))}"
        )
    return lines


def _list_lines(values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        return ["_None._"]
    return [f"- {_md(item)}" for item in values]


def render_human_approval_token_dry_run_markdown(report: dict[str, Any]) -> str:
    """Render a HUMAN.N3 dry-run report as Markdown."""
    lines: list[str] = [
        "# Human Approval Token Dry-Run",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
    ]
    lines.extend(_dict_lines(report.get("token_summary")))
    lines.extend(["", "## Source Token", ""])
    lines.append(f"- **Path:** `{_md(report.get('source_token_path', ''))}`")
    lines.append(f"- **Token ID:** `{_md(report.get('token_id', 'sample'))}`")
    lines.extend(["", "## Contract Reference", ""])
    lines.append(f"- **Path:** `{_md(report.get('source_contract_path', ''))}`")
    lines.extend(["", "## Schema Findings", ""])
    lines.extend(_finding_lines(report.get("schema_findings")))
    lines.extend(["", "## Action / Target Findings", ""])
    lines.extend(_finding_lines(report.get("action_findings")))
    lines.extend(_finding_lines(report.get("target_findings")))
    lines.extend(["", "## Confirmation Text Findings", ""])
    lines.extend(_finding_lines(report.get("confirmation_text_findings")))
    lines.extend(["", "## Scope Findings", ""])
    lines.extend(_finding_lines(report.get("scope_findings")))
    lines.extend(["", "## Expiry / Revocation / Reuse Findings", ""])
    lines.extend(_finding_lines(report.get("expiry_findings")))
    lines.extend(_finding_lines(report.get("revocation_findings")))
    lines.extend(_finding_lines(report.get("reuse_findings")))
    lines.extend(["", "## Evidence and Boundary References", ""])
    lines.extend(_finding_lines(report.get("evidence_reference_findings")))
    lines.extend(["", "## Authority Boundary Findings", ""])
    lines.extend(_finding_lines(report.get("authority_boundary_findings")))
    lines.extend(["", "## Warnings", ""])
    lines.extend(_list_lines(report.get("warnings")))
    lines.extend(["", "## Blocked Reasons", ""])
    lines.extend(_finding_lines(report.get("blocked_reasons")))
    lines.extend(["", "## Dry-Run Verdict", ""])
    verdict = report.get("final_verdict") if isinstance(report.get("final_verdict"), dict) else {}
    lines.extend(_dict_lines(verdict))
    lines.extend(["", "## Future Enforcement Boundary", ""])
    lines.extend(_dict_lines(report.get("future_enforcement_boundary")))
    lines.extend(["", "## Boundary Guardrails", ""])
    lines.extend(_list_lines(report.get("boundary_guardrails")))
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


def _load_json(path: Path) -> tuple[Any, str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except json.JSONDecodeError:
        return None, "json"
    except OSError:
        return None, "missing"


def write_human_approval_token_dry_run(
    *,
    token_path: str | Path,
    contract_path: str | Path = DEFAULT_CONTRACT_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str = "",
    created_at: str = "",
    now: str = "",
) -> dict[str, Any]:
    """Read sample token/contract JSON and write HUMAN.N3 dry-run artifacts."""
    token_source = Path(token_path)
    contract_source = Path(contract_path)
    preblocked: list[dict[str, str]] = []

    token: Any = {}
    token_path_reason = _unsafe_path_reason(str(token_source))
    if token_path_reason:
        _append_unique(
            preblocked,
            _finding("blocked", "unsafe_token_path", f"Token path is unsafe: {token_path_reason}", "token_path"),
        )
    else:
        token, token_error = _load_json(token_source)
        if token_error == "missing":
            _append_unique(
                preblocked,
                _finding("blocked", "missing_token", "Token JSON file is missing.", "token_path"),
            )
            token = {}
        elif token_error == "json":
            _append_unique(
                preblocked,
                _finding("blocked", "malformed_token_json", "Token JSON is malformed.", "token_path"),
            )
            token = {}

    contract: Any = None
    contract_path_reason = _unsafe_path_reason(str(contract_source))
    if contract_path_reason:
        _append_unique(
            preblocked,
            _finding(
                "blocked",
                "forbidden_secret_path",
                f"Contract path is unsafe: {contract_path_reason}",
                "contract_path",
            ),
        )
    else:
        contract, contract_error = _load_json(contract_source)
        if contract_error == "missing":
            _append_unique(
                preblocked,
                _finding("blocked", "missing_contract", "HUMAN.N2 contract JSON file is missing.", "contract_path"),
            )
            contract = None
        elif contract_error == "json":
            _append_unique(
                preblocked,
                _finding("blocked", "malformed_contract_json", "HUMAN.N2 contract JSON is malformed.", "contract_path"),
            )
            contract = None

    report = build_human_approval_token_dry_run(
        token=token,
        contract=contract,
        source_token_path=str(token_source),
        source_contract_path=str(contract_source),
        report_id=report_id,
        created_at=created_at,
        now=now,
        preblocked=preblocked,
    )

    out_dir = Path(output_dir) / _output_token_dir(report.get("token_id"))
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_human_approval_token_dry_run_markdown(report), encoding="utf-8")
    return {
        "ok": report["dry_run_status"] in {STATUS_VALID, STATUS_VALID_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
