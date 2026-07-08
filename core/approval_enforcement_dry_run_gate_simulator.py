"""Report-only simulator for future approval enforcement gate decisions.

HARDEN.N3 evaluates sample action requests against sample approval tokens and
the HARDEN.N2 attachment plan. It never authorizes, blocks, issues, consumes, or
enforces anything in runtime behavior.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "approval_enforcement_dry_run_gate_simulator"
THIS_PHASE_ID = "HARDEN.N3"

STATUS_READY = "approval_gate_simulation_ready"
STATUS_READY_WITH_WARNINGS = "approval_gate_simulation_ready_with_warnings"
STATUS_INCOMPLETE = "approval_gate_simulation_incomplete"
STATUS_BLOCKED = "approval_gate_simulation_blocked"

JSON_NAME = "approval_enforcement_dry_run_gate_simulator.json"
MD_NAME = "approval_enforcement_dry_run_gate_simulator.md"

DEFAULT_OUTPUT_ROOT = Path(".agent") / "harden" / "approval_enforcement_dry_run_gate_simulator"
DEFAULT_ATTACHMENT_PLAN_PATH = (
    Path(".agent")
    / "harden"
    / "approval_enforcement_attachment_plan"
    / "approval_enforcement_attachment_plan.json"
)
DEFAULT_TOKEN_CONTRACT_PATH = (
    Path(".agent") / "human" / "approval_token_contract" / "human_approval_token_contract.json"
)
DEFAULT_TOKEN_DRY_RUN_VALIDATOR_PATH = Path("core") / "human_approval_token_dry_run_validator.py"
DEFAULT_SAMPLE_CATALOG_PATH = (
    Path(".agent")
    / "human"
    / "approval_token_sample_catalog"
    / "human_approval_token_sample_catalog.json"
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

DEFAULT_SCENARIO_IDS: tuple[str, ...] = (
    "valid_patch_apply_request_with_valid_token",
    "patch_apply_missing_token",
    "patch_apply_mismatched_target",
    "expired_token",
    "revoked_token",
    "consumed_single_use_token",
    "automatic_approval_attempt",
    "automatic_rejection_attempt",
    "hidden_mutation_attempt",
    "model_routing_without_enforcement_phase",
)

REQUEST_REQUIRED_FIELDS: tuple[str, ...] = (
    "request_id",
    "action_category",
    "approval_action",
    "target_type",
    "target_id",
    "target_artifact_path",
    "risk_level",
    "requested_by",
    "requested_at",
    "confirmation_scope",
    "metadata",
)

FALLBACK_TOKEN_REQUIRED_FIELDS: tuple[str, ...] = (
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

FORBIDDEN_METADATA_KEYS: tuple[str, ...] = (
    "hidden_mutation",
    "bypass_auth",
    "real_authority",
    "approval_authority",
    "enforce_now",
    "runtime_enforcement",
    "route_behavior_change",
    "auth_policy_change",
    "automatic_authority_escalation",
)

RUNTIME_MARKER_LABELS: dict[str, str] = {
    "enforcement_was_applied": "enforcement was applied",
    "approval_gate_enforced": "approval gate enforcement was applied",
    "simulated_allow_treated_as_real_authority": "simulated allow was treated as real authority",
    "sample_token_treated_as_real_authority": "sample token was treated as real authority",
    "approval_token_issuance_performed": "approval token issuance was performed",
    "approval_token_consumption_performed": "approval token consumption was performed",
    "route_behavior_changed": "route behavior changed",
    "auth_policy_changed": "auth policy changed",
    "model_call_performed": "model call was performed",
    "model_routing_performed": "model routing was performed",
    "worker_launch_performed": "worker launch was performed",
    "patch_apply_performed": "patch apply was performed",
    "validation_run_performed": "validation run was performed",
    "benchmark_run_performed": "benchmark run was performed",
    "mcp_tool_invocation_performed": "MCP/tool invocation was performed",
    "network_access_performed": "network access was performed",
    "database_write_performed": "database write was performed",
    "hidden_mutation_allowed": "hidden mutation was allowed",
    "automatic_approval_allowed": "automatic approval was allowed",
    "automatic_rejection_allowed": "automatic rejection was allowed",
}

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "HARDEN.N4",
    "title": "Approval Enforcement Operator Report",
    "reason": (
        "Create a read-only operator-facing report format for simulated "
        "approval-gate outcomes before any runtime enforcement phase."
    ),
}

ALTERNATIVE_NEXT_PHASE = {
    "phase_id": "HARDEN.CLOSE",
    "title": "Hardening Track Closeout",
    "reason": "Freeze the hardening arc after the dry-run simulator if no operator report is needed.",
}

GUARDRAIL_NOTE = (
    "HARDEN.N3 is simulation-only and report-only. Even simulated allow results "
    "do not approve, reject, dispatch, or authorize any real action."
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "simulation-only",
    "no runtime enforcement",
    "no token validation gate",
    "no approval or rejection of real actions",
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm_path(value: str | Path | None) -> str:
    return str(value or "").replace("\\", "/")


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|")


def _bool(value: Any) -> str:
    return "true" if bool(value) else "false"


def _resolve(repo: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo / candidate


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


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


def _read_text_marker(repo: Path, path: str | Path, marker: str, label: str) -> tuple[bool, str]:
    resolved = _resolve(repo, path)
    if not resolved.is_file():
        return False, f"{label} missing at {_norm_path(path)}"
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"{label} unreadable at {_norm_path(path)}: {exc}"
    if marker not in text:
        return False, f"{label} marker {marker!r} missing at {_norm_path(path)}"
    return True, ""


def _artifact_summary(
    *,
    phase_id: str,
    path: str | Path,
    data: dict[str, Any] | None = None,
    expected_kind: str = "",
    error: str = "",
    required: bool = True,
    present: bool | None = None,
    report_kind_ok: bool | None = None,
) -> dict[str, Any]:
    is_present = present if present is not None else data is not None and not error
    if report_kind_ok is None:
        kind_ok = bool(data and (not expected_kind or data.get("report_kind") == expected_kind))
    else:
        kind_ok = report_kind_ok
    return {
        "phase_id": phase_id,
        "path": _norm_path(path),
        "required": required,
        "present": bool(is_present),
        "expected_report_kind": expected_kind,
        "report_kind_ok": bool(kind_ok),
        "error": error,
    }


def _source_artifacts(
    *,
    repo: Path,
    attachment_plan_path: str | Path,
    token_contract_path: str | Path,
    token_dry_run_validator_path: str | Path,
    sample_catalog_path: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    attachment_plan, plan_error = _read_json_object(repo, attachment_plan_path, "HARDEN.N2 attachment plan")
    token_contract, contract_error = _read_json_object(repo, token_contract_path, "HUMAN.N2 approval token contract")
    sample_catalog, catalog_error = _read_json_object(repo, sample_catalog_path, "HUMAN.N4 sample token catalog")
    validator_present, validator_error = _read_text_marker(
        repo,
        token_dry_run_validator_path,
        "human_approval_token_dry_run",
        "HUMAN.N3 approval token dry-run validator",
    )

    artifacts = [
        _artifact_summary(
            phase_id="HARDEN.N2",
            path=attachment_plan_path,
            data=attachment_plan,
            error=plan_error,
            expected_kind="approval_enforcement_attachment_plan",
            required=True,
        ),
        _artifact_summary(
            phase_id="HUMAN.N2",
            path=token_contract_path,
            data=token_contract,
            error=contract_error,
            expected_kind="human_approval_token_contract",
            required=True,
        ),
        _artifact_summary(
            phase_id="HUMAN.N3",
            path=token_dry_run_validator_path,
            error=validator_error,
            expected_kind="human_approval_token_dry_run source marker",
            required=False,
            present=validator_present and not validator_error,
            report_kind_ok=validator_present,
        ),
        _artifact_summary(
            phase_id="HUMAN.N4",
            path=sample_catalog_path,
            data=sample_catalog,
            error=catalog_error,
            expected_kind="human_approval_token_sample_catalog",
            required=False,
        ),
    ]
    incomplete: list[str] = []
    for artifact in artifacts:
        if artifact["required"] and (not artifact["present"] or not artifact["report_kind_ok"]):
            incomplete.append(f"{artifact['phase_id']} source artifact unavailable: {artifact['error']}")
    return {
        "attachment_plan": attachment_plan,
        "token_contract": token_contract,
        "sample_catalog": sample_catalog,
        "validator_present": validator_present,
    }, artifacts, incomplete


def _token_required_fields(contract: dict[str, Any] | None) -> list[str]:
    if isinstance(contract, dict):
        fields = contract.get("required_fields")
        if isinstance(fields, list) and fields:
            return [str(item) for item in fields]
        schema = contract.get("token_schema")
        if isinstance(schema, dict) and isinstance(schema.get("required_fields"), list):
            return [str(item) for item in schema["required_fields"]]
    return list(FALLBACK_TOKEN_REQUIRED_FIELDS)


def _attachment_items_by_category(plan: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    items = plan.get("attachment_items") if isinstance(plan, dict) else []
    if not isinstance(items, list):
        return {}
    return {
        str(item.get("action_category")): item
        for item in items
        if isinstance(item, dict) and str(item.get("action_category", "")).strip()
    }


def _request(
    *,
    request_id: str,
    action_category: str = "patch_apply",
    approval_action: str = "approve_patch_apply",
    target_type: str = "patch",
    target_id: str = "demo_patch_001",
    target_artifact_path: str = "demo/patches/demo_patch_001.diff",
    risk_level: str = "high",
    confirmation_scope: str = "single_artifact",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "action_category": action_category,
        "approval_action": approval_action,
        "target_type": target_type,
        "target_id": target_id,
        "target_artifact_path": target_artifact_path,
        "risk_level": risk_level,
        "requested_by": "documentation_sample_operator",
        "requested_at": "2026-07-08T00:00:00+00:00",
        "confirmation_scope": confirmation_scope,
        "metadata": dict(metadata or {}),
    }


def _token(
    *,
    token_id: str = "valid_patch_apply_token",
    approval_action: str = "approve_patch_apply",
    target_type: str = "patch",
    target_id: str = "demo_patch_001",
    target_artifact_path: str = "demo/patches/demo_patch_001.diff",
    risk_level: str = "high",
    confirmation_scope: str = "single_artifact",
    expires_at: str = "2099-12-31T23:59:59+00:00",
    revoked_at: str = "",
    consumed_at: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "token_id": token_id,
        "approval_action": approval_action,
        "target_type": target_type,
        "target_id": target_id,
        "target_artifact_path": target_artifact_path,
        "risk_level": risk_level,
        "confirmation_text": f"I approve {risk_level} risk {approval_action} for {target_type} {target_id}.",
        "confirmation_scope": confirmation_scope,
        "created_at": "2026-07-08T00:00:00+00:00",
        "expires_at": expires_at,
        "revoked_at": revoked_at,
        "revocation_reason": "sample revocation" if revoked_at else "",
        "single_use": True,
        "consumed_at": consumed_at,
        "evidence_refs": ["demo_evidence_quality_report"],
        "boundary_refs": ["approval_enforcement_attachment_plan"],
        "warnings": [],
        "metadata": dict(metadata or {}),
    }


def _default_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": "valid_patch_apply_request_with_valid_token",
            "action_request": _request(request_id="valid_patch_apply_request_with_valid_token"),
            "approval_token": _token(),
            "expected_simulated_decision": "would_allow_with_valid_token",
        },
        {
            "scenario_id": "patch_apply_missing_token",
            "action_request": _request(request_id="patch_apply_missing_token"),
            "approval_token": None,
            "expected_simulated_decision": "would_deny_missing_token",
        },
        {
            "scenario_id": "patch_apply_mismatched_target",
            "action_request": _request(request_id="patch_apply_mismatched_target"),
            "approval_token": _token(token_id="mismatched_target_token", target_id="demo_patch_999"),
            "expected_simulated_decision": "would_deny_mismatched_token",
        },
        {
            "scenario_id": "expired_token",
            "action_request": _request(request_id="expired_token"),
            "approval_token": _token(token_id="expired_patch_token", expires_at="2000-01-01T00:00:00+00:00"),
            "expected_simulated_decision": "would_deny_expired_token",
        },
        {
            "scenario_id": "revoked_token",
            "action_request": _request(request_id="revoked_token"),
            "approval_token": _token(token_id="revoked_patch_token", revoked_at="2026-07-07T00:00:00+00:00"),
            "expected_simulated_decision": "would_deny_revoked_token",
        },
        {
            "scenario_id": "consumed_single_use_token",
            "action_request": _request(request_id="consumed_single_use_token"),
            "approval_token": _token(token_id="consumed_patch_token", consumed_at="2026-07-07T00:00:00+00:00"),
            "expected_simulated_decision": "would_deny_consumed_token",
        },
        {
            "scenario_id": "automatic_approval_attempt",
            "action_request": _request(
                request_id="automatic_approval_attempt",
                action_category="automatic_approval",
                approval_action="",
            ),
            "approval_token": _token(),
            "expected_simulated_decision": "would_block_auto_approval",
        },
        {
            "scenario_id": "automatic_rejection_attempt",
            "action_request": _request(
                request_id="automatic_rejection_attempt",
                action_category="automatic_rejection",
                approval_action="",
            ),
            "approval_token": _token(),
            "expected_simulated_decision": "would_block_auto_rejection",
        },
        {
            "scenario_id": "hidden_mutation_attempt",
            "action_request": _request(
                request_id="hidden_mutation_attempt",
                metadata={"hidden_mutation": True},
            ),
            "approval_token": _token(),
            "expected_simulated_decision": "would_block_hidden_mutation",
        },
        {
            "scenario_id": "model_routing_without_enforcement_phase",
            "action_request": _request(
                request_id="model_routing_without_enforcement_phase",
                action_category="model_routing",
                approval_action="approve_model_catalog_adoption",
                target_type="model_catalog",
                target_id="demo_model_catalog_001",
                target_artifact_path="demo/model_catalog/demo_model_catalog_001.json",
                risk_level="medium",
                confirmation_scope="single_action",
            ),
            "approval_token": _token(
                token_id="model_routing_sample_token",
                approval_action="approve_model_catalog_adoption",
                target_type="model_catalog",
                target_id="demo_model_catalog_001",
                target_artifact_path="demo/model_catalog/demo_model_catalog_001.json",
                risk_level="medium",
                confirmation_scope="single_action",
            ),
            "expected_simulated_decision": "would_require_human_review",
        },
    ]


def _parse_iso(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _request_summary(request: Any) -> dict[str, Any]:
    request_map = request if isinstance(request, dict) else {}
    return {
        "request_id": str(request_map.get("request_id") or ""),
        "action_category": str(request_map.get("action_category") or ""),
        "approval_action": str(request_map.get("approval_action") or ""),
        "target_type": str(request_map.get("target_type") or ""),
        "target_id": str(request_map.get("target_id") or ""),
        "target_artifact_path": str(request_map.get("target_artifact_path") or ""),
        "risk_level": str(request_map.get("risk_level") or ""),
        "requested_by": str(request_map.get("requested_by") or ""),
        "requested_at": str(request_map.get("requested_at") or ""),
        "confirmation_scope": str(request_map.get("confirmation_scope") or ""),
        "metadata_keys": sorted(str(key) for key in (request_map.get("metadata") or {}).keys())
        if isinstance(request_map.get("metadata"), dict)
        else [],
    }


def _token_summary(token: Any) -> dict[str, Any]:
    token_map = token if isinstance(token, dict) else {}
    return {
        "token_present": isinstance(token, dict) and bool(token),
        "token_id": str(token_map.get("token_id") or ""),
        "approval_action": str(token_map.get("approval_action") or ""),
        "target_type": str(token_map.get("target_type") or ""),
        "target_id": str(token_map.get("target_id") or ""),
        "risk_level": str(token_map.get("risk_level") or ""),
        "confirmation_scope": str(token_map.get("confirmation_scope") or ""),
        "has_expires_at": bool(str(token_map.get("expires_at") or "").strip()),
        "has_revoked_at": bool(str(token_map.get("revoked_at") or "").strip()),
        "has_consumed_at": bool(str(token_map.get("consumed_at") or "").strip()),
        "single_use": bool(token_map.get("single_use")) if "single_use" in token_map else False,
        "metadata_keys": sorted(str(key) for key in (token_map.get("metadata") or {}).keys())
        if isinstance(token_map.get("metadata"), dict)
        else [],
    }


def _check(passed: bool, reason: str = "") -> dict[str, Any]:
    return {"passed": bool(passed), "reason": reason}


def _request_missing_fields(request: Any) -> list[str]:
    if not isinstance(request, dict):
        return list(REQUEST_REQUIRED_FIELDS)
    missing = [field for field in REQUEST_REQUIRED_FIELDS if field not in request or request.get(field) in (None, "")]
    if not isinstance(request.get("metadata"), dict):
        missing.append("metadata_object")
    return _dedupe(missing)


def _metadata_flags(*values: Any) -> dict[str, list[str]]:
    hidden: list[str] = []
    unsafe: list[str] = []
    for value in values:
        metadata = value.get("metadata") if isinstance(value, dict) else {}
        if not isinstance(metadata, dict):
            continue
        for key in FORBIDDEN_METADATA_KEYS:
            if _truthy(metadata.get(key)):
                if key == "hidden_mutation":
                    hidden.append(key)
                else:
                    unsafe.append(key)
    return {"hidden": sorted(set(hidden)), "unsafe": sorted(set(unsafe))}


def _boundary_result(
    *,
    attachment_item: dict[str, Any] | None,
    category: str,
    decision: str,
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "simulation_only": True,
        "authorizes_real_action": False,
        "rejects_real_action": False,
        "real_dispatch_allowed": False,
        "token_consumed": False,
        "token_issued": False,
        "route_or_auth_changed": False,
        "runtime_enforcement_added": False,
        "attachment_layer": str((attachment_item or {}).get("preferred_attachment_layer") or ""),
        "attachment_status": str((attachment_item or {}).get("current_runtime_status") or ""),
        "category": category,
        "decision": decision,
        "reasons": list(reasons),
    }


def _result(
    *,
    scenario_id: str,
    simulation_id: str,
    simulator_status: str,
    source_attachment_plan_path: str | Path,
    source_token_contract_path: str | Path,
    request: Any,
    token: Any,
    decision: str,
    reasons: list[str],
    token_fields: list[str],
    action_category_match: dict[str, Any],
    approval_action_match: dict[str, Any],
    target_match: dict[str, Any],
    risk_level_match: dict[str, Any],
    confirmation_scope_match: dict[str, Any],
    expiry_result: dict[str, Any],
    revocation_result: dict[str, Any],
    reuse_result: dict[str, Any],
    forbidden_metadata_result: dict[str, Any],
    boundary_result: dict[str, Any],
    warnings: list[str] | None = None,
    blocked_reasons: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "simulation_id": simulation_id,
        "simulator_status": simulator_status,
        "source_attachment_plan_path": _norm_path(source_attachment_plan_path),
        "source_token_contract_path": _norm_path(source_token_contract_path),
        "action_request_summary": _request_summary(request),
        "token_summary": _token_summary(token),
        "simulated_decision": decision,
        "simulated_reasons": list(reasons),
        "required_token_fields_checked": list(token_fields),
        "action_category_match": dict(action_category_match),
        "approval_action_match": dict(approval_action_match),
        "target_match": dict(target_match),
        "risk_level_match": dict(risk_level_match),
        "confirmation_scope_match": dict(confirmation_scope_match),
        "expiry_result": dict(expiry_result),
        "revocation_result": dict(revocation_result),
        "reuse_result": dict(reuse_result),
        "forbidden_metadata_result": dict(forbidden_metadata_result),
        "boundary_result": dict(boundary_result),
        "warnings": list(warnings or []),
        "blocked_reasons": list(blocked_reasons or []),
        "enforcement_was_applied": False,
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def _simulate_one(
    *,
    scenario_id: str,
    request: Any,
    token: Any,
    simulation_id: str,
    simulator_status: str,
    source_attachment_plan_path: str | Path,
    source_token_contract_path: str | Path,
    attachment_items: dict[str, dict[str, Any]],
    token_fields: list[str],
    now: str,
) -> dict[str, Any]:
    missing_request = _request_missing_fields(request)
    request_map = request if isinstance(request, dict) else {}
    token_map = token if isinstance(token, dict) else None
    category = str(request_map.get("action_category") or "")
    attachment_item = attachment_items.get(category)
    expected_action = str((attachment_item or {}).get("approval_action") or request_map.get("approval_action") or "")
    reasons: list[str] = []
    warnings: list[str] = []
    blocked: list[str] = []

    action_category_match = _check(bool(attachment_item) or category in {"automatic_approval", "automatic_rejection", "hidden_mutation"}, "")
    approval_action_match = _check(True)
    target_match = _check(True)
    risk_level_match = _check(True)
    confirmation_scope_match = _check(True)
    expiry_result = _check(True)
    revocation_result = _check(True)
    reuse_result = _check(True)
    forbidden_metadata_result = _check(True)

    decision = "would_allow_with_valid_token"
    if category == "automatic_approval":
        decision = "would_block_auto_approval"
        reasons.append("automatic approval is blocked forever")
        blocked.append("automatic approval must never be authorized by a sample token")
    elif category == "automatic_rejection":
        decision = "would_block_auto_rejection"
        reasons.append("automatic rejection is blocked forever")
        blocked.append("automatic rejection must never be authorized by a sample token")
    elif missing_request:
        decision = "simulation_incomplete"
        reasons.append("sample action request is malformed: missing " + ", ".join(missing_request))
    else:
        metadata = _metadata_flags(request_map, token_map or {})
        if metadata["hidden"] or category == "hidden_mutation":
            decision = "would_block_hidden_mutation"
            reasons.append("hidden mutation metadata or category is blocked forever")
            blocked.append("hidden mutation must never be authorized by a sample token")
            forbidden_metadata_result = _check(False, "hidden_mutation")
        elif metadata["unsafe"]:
            decision = "would_block_unsafe_metadata"
            reasons.append("unsafe metadata implies runtime authority: " + ", ".join(metadata["unsafe"]))
            blocked.append("unsafe metadata must not grant or imply approval authority")
            forbidden_metadata_result = _check(False, ", ".join(metadata["unsafe"]))
        elif attachment_item and (
            attachment_item.get("current_runtime_status") == "forbidden_boundary"
            or attachment_item.get("preferred_attachment_layer") == "blocked_forever"
        ):
            decision = "would_block_forbidden_action"
            reasons.append(f"{category} is marked as a forbidden boundary by HARDEN.N2")
            blocked.append(f"{category} is blocked forever")
        elif not token_map:
            decision = "would_deny_missing_token"
            reasons.append("sample approval token is absent")
        else:
            if not attachment_item:
                action_category_match = _check(False, "action category is not mapped by HARDEN.N2")
                decision = "simulation_incomplete"
                reasons.append(f"{category} cannot be mapped to a HARDEN.N2 attachment item")
            if token_map:
                token_action = str(token_map.get("approval_action") or "")
                request_action = str(request_map.get("approval_action") or "")
                if expected_action and request_action and request_action != expected_action:
                    approval_action_match = _check(False, "request approval_action does not match attachment plan")
                    decision = "would_deny_mismatched_token"
                    reasons.append("request approval_action does not match HARDEN.N2 attachment plan")
                elif token_action != request_action:
                    approval_action_match = _check(False, "token approval_action does not match request")
                    decision = "would_deny_mismatched_token"
                    reasons.append("token approval_action does not match request")

                target_same = (
                    str(token_map.get("target_type") or "") == str(request_map.get("target_type") or "")
                    and str(token_map.get("target_id") or "") == str(request_map.get("target_id") or "")
                )
                if not target_same and decision == "would_allow_with_valid_token":
                    target_match = _check(False, "token target does not match request target")
                    decision = "would_deny_mismatched_token"
                    reasons.append("token target does not match request target")

                if str(token_map.get("risk_level") or "") != str(request_map.get("risk_level") or ""):
                    risk_level_match = _check(False, "token risk_level does not match request")
                    if decision == "would_allow_with_valid_token":
                        decision = "would_deny_mismatched_token"
                        reasons.append("token risk_level does not match request")

                if str(token_map.get("confirmation_scope") or "") != str(request_map.get("confirmation_scope") or ""):
                    confirmation_scope_match = _check(False, "token confirmation_scope does not match request")
                    if decision == "would_allow_with_valid_token":
                        decision = "would_deny_mismatched_token"
                        reasons.append("token confirmation_scope does not match request")

                now_dt = _parse_iso(now) or datetime.now(timezone.utc)
                expires_dt = _parse_iso(token_map.get("expires_at"))
                if token_map.get("expires_at") and expires_dt is None:
                    expiry_result = _check(False, "expires_at is malformed")
                    if decision == "would_allow_with_valid_token":
                        decision = "would_warn_with_weak_token"
                        warnings.append("expires_at is malformed in this sample token")
                elif expires_dt and expires_dt <= now_dt:
                    expiry_result = _check(False, "token is expired")
                    decision = "would_deny_expired_token"
                    reasons.append("sample token would be expired for a future gate")

                if token_map.get("revoked_at"):
                    revocation_result = _check(False, "token is revoked")
                    decision = "would_deny_revoked_token"
                    reasons.append("sample token is marked revoked")

                if _truthy(token_map.get("single_use")) and token_map.get("consumed_at"):
                    reuse_result = _check(False, "single-use token is already consumed")
                    decision = "would_deny_consumed_token"
                    reasons.append("sample single-use token is marked consumed")

                missing_token_fields = [
                    field for field in token_fields if field not in token_map or token_map.get(field) in (None, "")
                ]
                if missing_token_fields and decision == "would_allow_with_valid_token":
                    decision = "would_warn_with_weak_token"
                    warnings.append("sample token is missing fields: " + ", ".join(missing_token_fields))

                if category == "model_routing" and decision == "would_allow_with_valid_token":
                    decision = "would_require_human_review"
                    warnings.append("model routing remains a human-review simulation until an explicit enforcement phase")
                    reasons.append("future model-routing gate is simulated but not enforceable in HARDEN.N3")

    if not reasons:
        reasons.append("sample request and sample token match within the simulated future gate")

    boundary = _boundary_result(
        attachment_item=attachment_item,
        category=category,
        decision=decision,
        reasons=reasons,
    )
    return _result(
        scenario_id=scenario_id,
        simulation_id=simulation_id,
        simulator_status=simulator_status,
        source_attachment_plan_path=source_attachment_plan_path,
        source_token_contract_path=source_token_contract_path,
        request=request,
        token=token,
        decision=decision,
        reasons=reasons,
        token_fields=token_fields,
        action_category_match=action_category_match,
        approval_action_match=approval_action_match,
        target_match=target_match,
        risk_level_match=risk_level_match,
        confirmation_scope_match=confirmation_scope_match,
        expiry_result=expiry_result,
        revocation_result=revocation_result,
        reuse_result=reuse_result,
        forbidden_metadata_result=forbidden_metadata_result,
        boundary_result=boundary,
        warnings=warnings,
        blocked_reasons=blocked,
    )


def _runtime_blockers(runtime_change_markers: dict[str, Any] | None) -> list[str]:
    markers = runtime_change_markers or {}
    blockers: list[str] = []
    for key, label in RUNTIME_MARKER_LABELS.items():
        if _truthy(markers.get(key)):
            blockers.append(label + " in HARDEN.N3")
    return blockers


def _guardrails(runtime_change_markers: dict[str, Any] | None = None) -> dict[str, bool]:
    markers = runtime_change_markers or {}
    return {
        "report_only": True,
        "simulation_only": True,
        "approval_gate_enforced": _truthy(markers.get("approval_gate_enforced")),
        "enforcement_was_applied": _truthy(markers.get("enforcement_was_applied")),
        "approval_token_issuance_performed": _truthy(markers.get("approval_token_issuance_performed")),
        "approval_token_consumption_performed": _truthy(markers.get("approval_token_consumption_performed")),
        "route_behavior_changed": _truthy(markers.get("route_behavior_changed")),
        "auth_policy_changed": _truthy(markers.get("auth_policy_changed")),
        "model_call_performed": _truthy(markers.get("model_call_performed")),
        "model_routing_performed": _truthy(markers.get("model_routing_performed")),
        "worker_launch_performed": _truthy(markers.get("worker_launch_performed")),
        "patch_apply_performed": _truthy(markers.get("patch_apply_performed")),
        "validation_run_performed": _truthy(markers.get("validation_run_performed")),
        "benchmark_run_performed": _truthy(markers.get("benchmark_run_performed")),
        "mcp_tool_invocation_performed": _truthy(markers.get("mcp_tool_invocation_performed")),
        "network_access_performed": _truthy(markers.get("network_access_performed")),
        "database_write_performed": _truthy(markers.get("database_write_performed")),
        "hidden_mutation_allowed": _truthy(markers.get("hidden_mutation_allowed")),
        "automatic_approval_allowed": _truthy(markers.get("automatic_approval_allowed")),
        "automatic_rejection_allowed": _truthy(markers.get("automatic_rejection_allowed")),
        "sample_token_treated_as_real_authority": _truthy(markers.get("sample_token_treated_as_real_authority")),
    }


def _status(blockers: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blockers:
        return STATUS_BLOCKED
    if incomplete:
        return STATUS_INCOMPLETE
    if warnings:
        return STATUS_READY_WITH_WARNINGS
    return STATUS_READY


def _copy_scenarios(sample_scenarios: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> list[dict[str, Any]]:
    source = _default_scenarios() if sample_scenarios is None else sample_scenarios
    copied: list[dict[str, Any]] = []
    for scenario in source:
        entry = dict(scenario)
        request = entry.get("action_request")
        token = entry.get("approval_token")
        entry["action_request"] = dict(request) if isinstance(request, dict) else request
        entry["approval_token"] = dict(token) if isinstance(token, dict) else token
        copied.append(entry)
    return copied


def build_approval_enforcement_dry_run_gate_simulator(
    *,
    repo_root: str | Path = ".",
    source_attachment_plan_path: str | Path = DEFAULT_ATTACHMENT_PLAN_PATH,
    source_token_contract_path: str | Path = DEFAULT_TOKEN_CONTRACT_PATH,
    source_token_dry_run_validator_path: str | Path = DEFAULT_TOKEN_DRY_RUN_VALIDATOR_PATH,
    source_sample_catalog_path: str | Path = DEFAULT_SAMPLE_CATALOG_PATH,
    sample_action_request: dict[str, Any] | None = None,
    sample_approval_token: dict[str, Any] | None = None,
    sample_scenarios: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    simulation_id: str = "",
    created_at: str = "",
    now: str = "",
    runtime_change_markers: dict[str, Any] | None = None,
    sample_tokens_treated_as_real_authority: bool = False,
) -> dict[str, Any]:
    """Build a HARDEN.N3 report-only approval gate simulation."""
    repo = Path(repo_root or ".").resolve()
    source_data, source_artifacts, incomplete = _source_artifacts(
        repo=repo,
        attachment_plan_path=source_attachment_plan_path,
        token_contract_path=source_token_contract_path,
        token_dry_run_validator_path=source_token_dry_run_validator_path,
        sample_catalog_path=source_sample_catalog_path,
    )
    token_fields = _token_required_fields(source_data["token_contract"])
    attachment_items = _attachment_items_by_category(source_data["attachment_plan"])
    required_categories = {"patch_apply", "model_routing", "automatic_approval", "automatic_rejection", "hidden_mutation"}
    missing_categories = sorted(required_categories - set(attachment_items))
    if missing_categories:
        incomplete.append("required HARDEN.N2 attachment categories missing: " + ", ".join(missing_categories))

    blockers = _runtime_blockers(runtime_change_markers)
    if sample_tokens_treated_as_real_authority:
        blockers.append("sample approval tokens are treated as real authority in HARDEN.N3")

    warnings = [
        "Future enforcement remains intentionally unimplemented in HARDEN.N3.",
        "Simulated allow results do not authorize real actions or consume tokens.",
    ]
    scenarios = _copy_scenarios(sample_scenarios)
    sid = str(simulation_id or "harden-n3-dry-run-gate-simulator")
    created = str(created_at or _utc_now())
    now_value = str(now or created)

    default_results = [
        _simulate_one(
            scenario_id=str(scenario.get("scenario_id") or f"scenario_{index + 1}"),
            request=scenario.get("action_request"),
            token=scenario.get("approval_token"),
            simulation_id=sid,
            simulator_status=STATUS_READY_WITH_WARNINGS,
            source_attachment_plan_path=source_attachment_plan_path,
            source_token_contract_path=source_token_contract_path,
            attachment_items=attachment_items,
            token_fields=token_fields,
            now=now_value,
        )
        for index, scenario in enumerate(scenarios)
    ]

    custom_result: dict[str, Any] | None = None
    if sample_action_request is not None:
        missing_request = _request_missing_fields(sample_action_request)
        if missing_request:
            incomplete.append("sample action request is malformed: missing " + ", ".join(missing_request))
        custom_result = _simulate_one(
            scenario_id="custom_sample_request",
            request=sample_action_request,
            token=sample_approval_token,
            simulation_id=sid,
            simulator_status=STATUS_READY_WITH_WARNINGS,
            source_attachment_plan_path=source_attachment_plan_path,
            source_token_contract_path=source_token_contract_path,
            attachment_items=attachment_items,
            token_fields=token_fields,
            now=now_value,
        )

    blockers = _dedupe(blockers)
    incomplete = _dedupe(incomplete)
    warnings = _dedupe(warnings)
    status = _status(blockers, incomplete, warnings)
    for result in default_results:
        result["simulator_status"] = status
    if custom_result is not None:
        custom_result["simulator_status"] = status

    decision_counts: dict[str, int] = {}
    for result in default_results + ([custom_result] if custom_result else []):
        decision = str(result.get("simulated_decision") or "")
        decision_counts[decision] = decision_counts.get(decision, 0) + 1

    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "simulation_id": sid,
        "created_at": created,
        "now": now_value,
        "guardrail_note": GUARDRAIL_NOTE,
        "simulator_status": status,
        "source_attachment_plan_path": _norm_path(source_attachment_plan_path),
        "source_token_contract_path": _norm_path(source_token_contract_path),
        "source_token_dry_run_validator_path": _norm_path(source_token_dry_run_validator_path),
        "source_sample_catalog_path": _norm_path(source_sample_catalog_path),
        "source_artifacts": source_artifacts,
        "simulation_philosophy": {
            "summary": "Evaluate sample requests and tokens as inert data, then report hypothetical future decisions.",
            "boundary": "HARDEN.N3 may simulate a future gate; it may not become the gate.",
            "decision_order": [
                "malformed request",
                "blocked automatic or hidden mutation boundary",
                "missing or mismatched token",
                "expired, revoked, or consumed token",
                "weak token warning",
                "simulated allow or human review",
            ],
        },
        "sample_scenario_count": len(scenarios),
        "sample_action_requests": [
            {
                "scenario_id": str(scenario.get("scenario_id") or ""),
                "action_request": scenario.get("action_request"),
                "expected_simulated_decision": scenario.get("expected_simulated_decision"),
            }
            for scenario in scenarios
        ],
        "sample_tokens": [
            {
                "scenario_id": str(scenario.get("scenario_id") or ""),
                "token": scenario.get("approval_token"),
                "safe_to_use_as_real_approval": False,
                "documentation_only": True,
            }
            for scenario in scenarios
        ],
        "simulation_results": default_results,
        "custom_simulation_result": custom_result,
        "simulated_decision_matrix": [
            {
                "scenario_id": result["scenario_id"],
                "action_category": result["action_request_summary"]["action_category"],
                "simulated_decision": result["simulated_decision"],
                "enforcement_was_applied": result["enforcement_was_applied"],
                "reasons": result["simulated_reasons"],
            }
            for result in default_results
        ],
        "decision_counts": decision_counts,
        "token_field_checks": {
            "required_fields": token_fields,
            "checked_against_sample_tokens_only": True,
            "live_token_validation_gate_added": False,
            "source": "HUMAN.N2 approval token contract",
        },
        "boundary_checks": {
            "enforcement_was_applied": False,
            "sample_allow_authorizes_real_action": False,
            "token_issuance_performed": False,
            "token_consumption_performed": False,
            "route_behavior_changed": False,
            "auth_policy_changed": False,
        },
        "forbidden_action_simulations": [
            result
            for result in default_results
            if result["simulated_decision"]
            in {
                "would_block_forbidden_action",
                "would_block_hidden_mutation",
                "would_block_auto_approval",
                "would_block_auto_rejection",
                "would_block_unsafe_metadata",
            }
        ],
        "warnings": warnings,
        "blocked_reasons": blockers,
        "incomplete_reasons": incomplete,
        "enforcement_was_applied": False,
        "sample_tokens_treated_as_real_authority": bool(sample_tokens_treated_as_real_authority),
        "future_enforcement_boundary": {
            "simulation_only": True,
            "enforcement_allowed_now": False,
            "simulated_allow_is_authority": False,
            "not_before_phase": "future explicit approval-enforcement implementation phase after HARDEN.N4",
            "forbidden_now": list(BOUNDARIES),
        },
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "alternative_next_phase": dict(ALTERNATIVE_NEXT_PHASE),
        "final_verdict": {
            "status": status,
            "simulation_ready": status in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
            "authorizes_action": False,
            "rejects_real_action": False,
            "enforcement_was_applied": False,
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
            "message": (
                "Approval gate decisions are simulated with warnings because future enforcement is absent."
                if status == STATUS_READY_WITH_WARNINGS
                else f"Approval gate simulator status is {status}."
            ),
        },
        "guardrails": _guardrails(runtime_change_markers),
        "boundaries": list(BOUNDARIES),
    }


def _dict_lines(values: Any) -> list[str]:
    if not isinstance(values, dict) or not values:
        return ["_None._"]
    lines: list[str] = []
    for key in sorted(values):
        value = values[key]
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f"- `{_md(key)}`: {_md(value)}")
    return lines


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


def render_approval_enforcement_dry_run_gate_simulator_markdown(report: dict[str, Any]) -> str:
    """Render the HARDEN.N3 dry-run gate simulator report as Markdown."""
    lines: list[str] = [
        "# Approval Enforcement Dry-Run Gate Simulator",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Simulator status:** `{_md(report.get('simulator_status', ''))}`",
        f"- **Sample scenarios:** {report.get('sample_scenario_count', 0)}",
        f"- **Enforcement was applied:** `{_bool(report.get('enforcement_was_applied'))}`",
        f"- **Sample tokens treated as real authority:** `{_bool(report.get('sample_tokens_treated_as_real_authority'))}`",
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

    lines.extend(["", "## Simulation Philosophy", ""])
    lines.extend(_dict_lines(report.get("simulation_philosophy")))
    lines.extend(["", "## Sample Action Requests", ""])
    lines.extend(_list_lines(report.get("sample_action_requests")))
    lines.extend(["", "## Sample Tokens", ""])
    lines.extend(_list_lines(report.get("sample_tokens")))

    lines.extend(["", "## Simulated Decision Matrix", ""])
    matrix = report.get("simulated_decision_matrix") if isinstance(report.get("simulated_decision_matrix"), list) else []
    if matrix:
        lines.extend(["| Scenario | Category | Decision | Enforcement Applied |", "|---|---|---|---|"])
        for row in matrix:
            lines.append(
                f"| {_md(row.get('scenario_id'))} | {_md(row.get('action_category'))} | "
                f"`{_md(row.get('simulated_decision'))}` | {_bool(row.get('enforcement_was_applied'))} |"
            )
    else:
        lines.append("_None._")

    lines.extend(["", "## Token Field Checks", ""])
    lines.extend(_dict_lines(report.get("token_field_checks")))
    lines.extend(["", "## Boundary Checks", ""])
    lines.extend(_dict_lines(report.get("boundary_checks")))
    lines.extend(["", "## Forbidden Action Simulations", ""])
    lines.extend(_list_lines(report.get("forbidden_action_simulations")))
    lines.extend(["", "## Warnings", ""])
    lines.extend(_list_lines(report.get("warnings")))
    lines.extend(["", "## Blocked Reasons", ""])
    lines.extend(_list_lines(report.get("blocked_reasons")))
    lines.extend(["", "## Incomplete Reasons", ""])
    lines.extend(_list_lines(report.get("incomplete_reasons")))
    lines.extend(["", "## Future Enforcement Boundary", ""])
    lines.extend(_dict_lines(report.get("future_enforcement_boundary")))
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


def write_approval_enforcement_dry_run_gate_simulator(
    *,
    repo_root: str | Path = ".",
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    source_attachment_plan_path: str | Path = DEFAULT_ATTACHMENT_PLAN_PATH,
    source_token_contract_path: str | Path = DEFAULT_TOKEN_CONTRACT_PATH,
    source_token_dry_run_validator_path: str | Path = DEFAULT_TOKEN_DRY_RUN_VALIDATOR_PATH,
    source_sample_catalog_path: str | Path = DEFAULT_SAMPLE_CATALOG_PATH,
    sample_action_request: dict[str, Any] | None = None,
    sample_approval_token: dict[str, Any] | None = None,
    sample_scenarios: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    simulation_id: str = "",
    created_at: str = "",
    now: str = "",
) -> dict[str, Any]:
    """Build and write HARDEN.N3 JSON/Markdown simulator artifacts."""
    report = build_approval_enforcement_dry_run_gate_simulator(
        repo_root=repo_root,
        source_attachment_plan_path=source_attachment_plan_path,
        source_token_contract_path=source_token_contract_path,
        source_token_dry_run_validator_path=source_token_dry_run_validator_path,
        source_sample_catalog_path=source_sample_catalog_path,
        sample_action_request=sample_action_request,
        sample_approval_token=sample_approval_token,
        sample_scenarios=sample_scenarios,
        simulation_id=simulation_id,
        created_at=created_at,
        now=now,
    )
    out = Path(output_dir)
    if not out.is_absolute():
        out = Path(repo_root or ".") / out
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    md_path = out / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_approval_enforcement_dry_run_gate_simulator_markdown(report), encoding="utf-8")
    return {
        "ok": report["simulator_status"] in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
