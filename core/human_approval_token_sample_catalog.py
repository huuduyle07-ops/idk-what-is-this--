"""HUMAN.N4 - Human Approval Token Sample Catalog.

Creates a report-only catalog of documentation-only sample approval tokens for
HUMAN.N2/HUMAN.N3 documentation, regression tests, and future enforcement
design. This module does not issue real approval tokens, approve or reject work,
consume tokens, enforce route behavior, apply patches, run validation or
benchmarks, call models, route models, launch workers, invoke MCP tools, use
network access, execute subprocesses, write to databases, or change auth policy.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "human_approval_token_sample_catalog"
THIS_PHASE_ID = "HUMAN.N4"

STATUS_READY = "approval_token_sample_catalog_ready"
STATUS_READY_WITH_WARNINGS = "approval_token_sample_catalog_ready_with_warnings"
STATUS_INCOMPLETE = "approval_token_sample_catalog_incomplete"
STATUS_BLOCKED = "approval_token_sample_catalog_blocked"

JSON_NAME = "human_approval_token_sample_catalog.json"
MD_NAME = "human_approval_token_sample_catalog.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "human" / "approval_token_sample_catalog"

SOURCE_CONTRACT_PHASE = "HUMAN.N2"
SOURCE_VALIDATOR_PHASE = "HUMAN.N3"

TOKEN_DRY_RUN_VALID = "token_dry_run_valid"
TOKEN_DRY_RUN_VALID_WITH_WARNINGS = "token_dry_run_valid_with_warnings"
TOKEN_DRY_RUN_INVALID = "token_dry_run_invalid"
TOKEN_DRY_RUN_BLOCKED = "token_dry_run_blocked"

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "HUMAN.CLOSE",
    "title": "Human Authority Branch Checkpoint",
    "reason": (
        "HUMAN.N1-N4 now provide an authority map, approval-token contract, "
        "dry-run validator, and sample token catalog; freeze the branch before "
        "runtime enforcement design."
    ),
}

GUARDRAIL_NOTE = (
    "HUMAN.N4 is report-only and sample-catalog-only. It writes example tokens "
    "for documentation and tests; samples are not live approvals and authorize "
    "no action."
)

SAMPLE_FILE_NAMES: dict[str, str] = {
    "valid_patch_apply_token": "valid_patch_apply_token.json",
    "warning_validation_run_token": "warning_high_risk_no_expiry_token.json",
    "invalid_generic_confirmation_token": "invalid_generic_confirmation_token.json",
    "blocked_hidden_mutation_token": "blocked_hidden_mutation_token.json",
}

REQUIRED_SAMPLE_IDS: tuple[str, ...] = (
    "valid_patch_apply_token",
    "warning_validation_run_token",
    "invalid_generic_confirmation_token",
    "blocked_hidden_mutation_token",
)

DEFAULT_DOCUMENTATION_NOTES: tuple[str, ...] = (
    "Sample tokens demonstrate HUMAN.N2 token shape and HUMAN.N3 dry-run outcomes.",
    "Sample tokens are deliberately inert documentation artifacts.",
    "A valid or warning dry-run expectation does not mean a sample is a live approval.",
    "Blocked samples document forbidden metadata authority such as hidden mutation or bypass auth.",
)

DEFAULT_FORBIDDEN_USAGE: tuple[str, ...] = (
    "samples are documentation only",
    "samples are not live approvals",
    "samples must not be accepted by runtime routes",
    "samples must not authorize patch apply",
    "samples must not authorize worker launch",
    "samples must not authorize tool/MCP/network/database actions",
    "samples must not bypass auth",
    "samples must not be reused as real confirmations",
    "sample presence must not imply user consent",
)

BOUNDARY_GUARDRAILS: tuple[str, ...] = (
    "report-only",
    "sample catalog only",
    "documentation-only tokens",
    "no runtime enforcement",
    "no approval/rejection",
    "no token issuance",
    "no token consumption",
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
    "writes sample/catalog artifacts only",
)

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "real_approval_issued",
    "approval_or_rejection_performed",
    "token_consumption_performed",
    "runtime_enforcement_added",
    "route_approval_enforcement_added",
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
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _guardrails() -> dict[str, bool]:
    data = {key: False for key in GUARDRAIL_FALSE_FLAGS}
    data["report_only"] = True
    data["sample_catalog_only"] = True
    data["writes_sample_catalog_artifacts_only"] = True
    return data


def _sample_metadata(**extra: Any) -> dict[str, Any]:
    metadata = {
        "documentation_only": True,
        "sample_catalog_only": True,
        "safe_to_use_as_real_approval": False,
        "sample_presence_implies_user_consent": False,
    }
    metadata.update(extra)
    return metadata


def _sample_token_entry(
    *,
    sample_id: str,
    sample_name: str,
    sample_class: str,
    sample_purpose: str,
    expected_dry_run_status: str,
    expected_findings: list[str],
    token: dict[str, Any],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "sample_id": sample_id,
        "sample_name": sample_name,
        "sample_class": sample_class,
        "sample_purpose": sample_purpose,
        "expected_dry_run_status": expected_dry_run_status,
        "expected_findings": list(expected_findings),
        "token": dict(token),
        "safe_to_use_as_real_approval": False,
        "documentation_only": True,
        "sample_artifact_path": f".agent/human/approval_token_sample_catalog/samples/{SAMPLE_FILE_NAMES[sample_id]}",
        "warnings": list(warnings or []),
    }


def _default_samples() -> list[dict[str, Any]]:
    return [
        _sample_token_entry(
            sample_id="valid_patch_apply_token",
            sample_name="Valid Patch Apply Token",
            sample_class="valid_sample",
            sample_purpose=(
                "Demonstrates an explicit, bounded high-risk patch approval shape "
                "with single-use semantics, expiry, evidence refs, and boundary refs."
            ),
            expected_dry_run_status=TOKEN_DRY_RUN_VALID,
            expected_findings=["token_dry_run_valid"],
            token={
                "token_id": "valid_patch_apply_token",
                "approval_action": "approve_patch_apply",
                "target_type": "patch",
                "target_id": "demo_patch_001",
                "target_artifact_path": "demo/patches/demo_patch_001.diff",
                "risk_level": "high",
                "confirmation_text": (
                    "I approve high risk patch apply for patch demo_patch_001 "
                    "after reviewing the listed evidence and rollback boundary."
                ),
                "confirmation_scope": "single_artifact",
                "operator_id": "documentation_sample_operator",
                "created_at": "2026-07-07T00:00:00+00:00",
                "expires_at": "2099-12-31T23:59:59+00:00",
                "revoked_at": "",
                "revocation_reason": "",
                "single_use": True,
                "consumed_at": "",
                "evidence_refs": ["demo_evidence_quality_report"],
                "boundary_refs": ["human_review_boundary_map"],
                "warnings": [],
                "metadata": _sample_metadata(),
            },
            warnings=[],
        ),
        _sample_token_entry(
            sample_id="warning_validation_run_token",
            sample_name="Warning Validation Run Token",
            sample_class="valid_with_warnings_sample",
            sample_purpose=(
                "Demonstrates a structurally valid medium-risk validation-run "
                "sample that omits optional evidence_refs and boundary_refs."
            ),
            expected_dry_run_status=TOKEN_DRY_RUN_VALID_WITH_WARNINGS,
            expected_findings=[
                "missing_evidence_refs",
                "missing_boundary_refs",
            ],
            token={
                "token_id": "warning_validation_run_token",
                "approval_action": "approve_validation_run",
                "target_type": "validation_plan",
                "target_id": "demo_validation_plan_001",
                "target_artifact_path": "demo/validation/demo_validation_plan_001.json",
                "risk_level": "medium",
                "confirmation_text": (
                    "I approve validation run for validation plan "
                    "demo_validation_plan_001 for this single run."
                ),
                "confirmation_scope": "single_run",
                "operator_id": "documentation_sample_operator",
                "created_at": "2026-07-07T00:00:00+00:00",
                "expires_at": "",
                "revoked_at": "",
                "revocation_reason": "",
                "single_use": True,
                "consumed_at": "",
                "warnings": [],
                "metadata": _sample_metadata(),
            },
            warnings=["Intentionally omits optional evidence_refs and boundary_refs."],
        ),
        _sample_token_entry(
            sample_id="invalid_generic_confirmation_token",
            sample_name="Invalid Generic Confirmation Token",
            sample_class="invalid_sample",
            sample_purpose=(
                "Demonstrates a high-risk patch sample with generic confirmation "
                "text that must fail HUMAN.N3 dry-run validation."
            ),
            expected_dry_run_status=TOKEN_DRY_RUN_INVALID,
            expected_findings=["generic_confirmation_text"],
            token={
                "token_id": "invalid_generic_confirmation_token",
                "approval_action": "approve_patch_apply",
                "target_type": "patch",
                "target_id": "demo_patch_002",
                "target_artifact_path": "demo/patches/demo_patch_002.diff",
                "risk_level": "high",
                "confirmation_text": "ok",
                "confirmation_scope": "single_artifact",
                "operator_id": "documentation_sample_operator",
                "created_at": "2026-07-07T00:00:00+00:00",
                "expires_at": "2099-12-31T23:59:59+00:00",
                "revoked_at": "",
                "revocation_reason": "",
                "single_use": True,
                "consumed_at": "",
                "evidence_refs": ["demo_evidence_quality_report"],
                "boundary_refs": ["human_review_boundary_map"],
                "warnings": [],
                "metadata": _sample_metadata(),
            },
            warnings=["Generic confirmation text is intentionally invalid."],
        ),
        _sample_token_entry(
            sample_id="blocked_hidden_mutation_token",
            sample_name="Blocked Hidden Mutation Token",
            sample_class="blocked_sample",
            sample_purpose=(
                "Demonstrates forbidden metadata that must be blocked because it "
                "implies hidden mutation and auth bypass authority."
            ),
            expected_dry_run_status=TOKEN_DRY_RUN_BLOCKED,
            expected_findings=[
                "metadata_hidden_mutation_forbidden",
                "metadata_bypass_auth_forbidden",
            ],
            token={
                "token_id": "blocked_hidden_mutation_token",
                "approval_action": "approve_patch_apply",
                "target_type": "patch",
                "target_id": "demo_patch_003",
                "target_artifact_path": "demo/patches/demo_patch_003.diff",
                "risk_level": "critical",
                "confirmation_text": "I approve critical risk patch apply for patch demo_patch_003.",
                "confirmation_scope": "single_artifact",
                "operator_id": "documentation_sample_operator",
                "created_at": "2026-07-07T00:00:00+00:00",
                "expires_at": "2099-12-31T23:59:59+00:00",
                "revoked_at": "",
                "revocation_reason": "",
                "single_use": True,
                "consumed_at": "",
                "evidence_refs": ["demo_evidence_quality_report"],
                "boundary_refs": ["human_review_boundary_map"],
                "warnings": [],
                "metadata": _sample_metadata(hidden_mutation=True, bypass_auth=True),
            },
            warnings=["Forbidden metadata is intentionally present for blocked-case documentation."],
        ),
    ]


def _finding(reason: str, message: str) -> dict[str, str]:
    return {"reason": reason, "message": message}


def _evaluate_catalog(
    *,
    samples: list[dict[str, Any]],
    documentation_notes: list[str],
    expectations: dict[str, str],
    warnings: list[str],
) -> tuple[str, list[dict[str, str]], list[str]]:
    blocked: list[dict[str, str]] = []
    incomplete: list[str] = []
    by_id = {str(sample.get("sample_id", "")): sample for sample in samples}
    missing = sorted(set(REQUIRED_SAMPLE_IDS) - set(by_id))
    if missing:
        blocked.append(_finding("missing_required_sample_classes", "Missing required samples: " + ", ".join(missing)))
    if "blocked_hidden_mutation_token" not in by_id:
        blocked.append(_finding("blocked_sample_absent", "Blocked hidden-mutation sample is absent."))
    if "invalid_generic_confirmation_token" not in by_id:
        blocked.append(_finding("invalid_sample_absent", "Invalid generic confirmation sample is absent."))

    for sample in samples:
        sample_id = str(sample.get("sample_id", ""))
        if sample.get("safe_to_use_as_real_approval") is True:
            blocked.append(
                _finding(
                    "sample_marked_safe_as_real_approval",
                    f"{sample_id} is marked safe_to_use_as_real_approval=true.",
                )
            )
        if sample.get("documentation_only") is not True:
            blocked.append(_finding("sample_not_documentation_only", f"{sample_id} is not documentation_only."))
        if sample_id not in expectations:
            incomplete.append(f"missing_validation_expectation:{sample_id}")

    if expectations.get("blocked_hidden_mutation_token") != TOKEN_DRY_RUN_BLOCKED:
        blocked.append(
            _finding(
                "hidden_mutation_sample_not_expected_blocked",
                "blocked_hidden_mutation_token must expect token_dry_run_blocked.",
            )
        )
    if expectations.get("invalid_generic_confirmation_token") != TOKEN_DRY_RUN_INVALID:
        blocked.append(
            _finding(
                "invalid_sample_not_expected_invalid",
                "invalid_generic_confirmation_token must expect token_dry_run_invalid.",
            )
        )
    if not documentation_notes:
        incomplete.append("missing_documentation_notes")
    if not expectations:
        incomplete.append("missing_validation_expectations")

    if blocked:
        return STATUS_BLOCKED, blocked, sorted(set(incomplete))
    if incomplete:
        return STATUS_INCOMPLETE, blocked, sorted(set(incomplete))
    if warnings:
        return STATUS_READY_WITH_WARNINGS, blocked, []
    return STATUS_READY, blocked, []


def _copy_samples(samples: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> list[dict[str, Any]]:
    source = _default_samples() if samples is None else samples
    copied: list[dict[str, Any]] = []
    for sample in source:
        entry = dict(sample)
        token = entry.get("token")
        entry["token"] = dict(token) if isinstance(token, dict) else {}
        entry["safe_to_use_as_real_approval"] = bool(entry.get("safe_to_use_as_real_approval"))
        entry["documentation_only"] = entry.get("documentation_only") is True
        entry["expected_findings"] = [str(item) for item in (entry.get("expected_findings") or [])]
        entry["warnings"] = [str(item) for item in (entry.get("warnings") or [])]
        copied.append(entry)
    return copied


def build_human_approval_token_sample_catalog(
    *,
    catalog_id: str = "",
    created_at: str = "",
    sample_tokens: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    documentation_notes: list[str] | tuple[str, ...] | None = None,
    forbidden_usage: list[str] | tuple[str, ...] | None = None,
    warnings: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Build the HUMAN.N4 report-only sample approval token catalog."""
    samples = _copy_samples(sample_tokens)
    notes = [str(item) for item in (DEFAULT_DOCUMENTATION_NOTES if documentation_notes is None else documentation_notes)]
    forbidden = [str(item) for item in (DEFAULT_FORBIDDEN_USAGE if forbidden_usage is None else forbidden_usage)]
    warning_list = [str(item) for item in ([] if warnings is None else warnings)]
    expectations = {
        str(sample.get("sample_id")): str(sample.get("expected_dry_run_status"))
        for sample in samples
        if str(sample.get("sample_id", "")).strip()
    }
    status, blocked, incomplete = _evaluate_catalog(
        samples=samples,
        documentation_notes=notes,
        expectations=expectations,
        warnings=warning_list,
    )
    summary = {
        "catalog_status": status,
        "sample_count": len(samples),
        "required_sample_count": len(REQUIRED_SAMPLE_IDS),
        "required_samples_present": sorted(set(REQUIRED_SAMPLE_IDS) & set(expectations)),
        "missing_required_samples": sorted(set(REQUIRED_SAMPLE_IDS) - set(expectations)),
        "validation_expectation_count": len(expectations),
        "documentation_note_count": len(notes),
        "forbidden_usage_count": len(forbidden),
        "blocked_reason_count": len(blocked),
        "incomplete_reason_count": len(incomplete),
        "warning_count": len(warning_list),
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
    }
    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "guardrail_note": GUARDRAIL_NOTE,
        "catalog_id": str(catalog_id or ""),
        "created_at": str(created_at or _utc_now()),
        "catalog_status": status,
        "source_contract_phase": SOURCE_CONTRACT_PHASE,
        "source_validator_phase": SOURCE_VALIDATOR_PHASE,
        "summary": summary,
        "sample_tokens": samples,
        "sample_validation_expectations": expectations,
        "documentation_notes": notes,
        "forbidden_usage": forbidden,
        "warnings": warning_list,
        "blocked_reasons": blocked,
        "incomplete_reasons": incomplete,
        "boundaries": _guardrails(),
        "boundaries_guardrails": list(BOUNDARY_GUARDRAILS),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "final_verdict": {
            "status": status,
            "catalog_ready": status == STATUS_READY,
            "catalog_ready_with_warnings": status == STATUS_READY_WITH_WARNINGS,
            "documentation_only": True,
            "authorizes_action": False,
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
        },
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


def _finding_lines(values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        return ["_None._"]
    lines: list[str] = []
    for item in values:
        if isinstance(item, dict):
            lines.append(f"- `{_md(item.get('reason', ''))}`: {_md(item.get('message', ''))}")
        else:
            lines.append(f"- {_md(item)}")
    return lines


def render_human_approval_token_sample_catalog_markdown(report: dict[str, Any]) -> str:
    """Render the HUMAN.N4 approval-token sample catalog as Markdown."""
    lines: list[str] = [
        "# Human Approval Token Sample Catalog",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "_All samples are documentation-only and are not live approvals._",
        "",
        "## Summary",
        "",
    ]
    lines.extend(_dict_lines(report.get("summary")))
    lines.extend(["", "## Sample Tokens", ""])
    samples = report.get("sample_tokens") if isinstance(report.get("sample_tokens"), list) else []
    if samples:
        lines.extend(
            [
                "| Sample | Class | Expected dry-run status | Documentation-only | Real approval safe | Purpose |",
                "|---|---|---|---|---|---|",
            ]
        )
        for sample in samples:
            lines.append(
                "| {sid} | {sample_class} | `{status}` | {doc} | {real} | {purpose} |".format(
                    sid=_md(sample.get("sample_id", "")),
                    sample_class=_md(sample.get("sample_class", "")),
                    status=_md(sample.get("expected_dry_run_status", "")),
                    doc=str(sample.get("documentation_only") is True).lower(),
                    real=str(sample.get("safe_to_use_as_real_approval") is True).lower(),
                    purpose=_md(sample.get("sample_purpose", "")),
                )
            )
    else:
        lines.append("_None._")
    lines.extend(["", "## Validation Expectations", ""])
    lines.extend(_dict_lines(report.get("sample_validation_expectations")))
    lines.extend(["", "## Documentation Notes", ""])
    lines.extend(_list_lines(report.get("documentation_notes")))
    lines.extend(["", "## Forbidden Usage", ""])
    lines.extend(_list_lines(report.get("forbidden_usage")))
    lines.extend(["", "## Warnings", ""])
    lines.extend(_list_lines(report.get("warnings")))
    lines.extend(["", "## Blocked Reasons", ""])
    lines.extend(_finding_lines(report.get("blocked_reasons")))
    lines.extend(["", "## Boundaries", ""])
    lines.extend(_list_lines(report.get("boundaries_guardrails")))
    guardrails = report.get("boundaries") if isinstance(report.get("boundaries"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: `{str(bool(guardrails[key])).lower()}`")
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
        ]
    )
    return "\n".join(lines)


def write_human_approval_token_sample_catalog(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    catalog_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build and write HUMAN.N4 JSON, Markdown, and sample token artifacts."""
    report = build_human_approval_token_sample_catalog(catalog_id=catalog_id, created_at=created_at)
    out_dir = Path(output_dir)
    samples_dir = out_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_human_approval_token_sample_catalog_markdown(report), encoding="utf-8")

    sample_paths: dict[str, str] = {}
    for sample in report["sample_tokens"]:
        sample_id = str(sample.get("sample_id", ""))
        file_name = SAMPLE_FILE_NAMES.get(sample_id, f"{sample_id or 'sample'}.json")
        path = samples_dir / file_name
        path.write_text(json.dumps(sample.get("token") or {}, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        sample_paths[sample_id] = str(path)

    return {
        "ok": report["catalog_status"] in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "sample_paths": sample_paths,
        "report": report,
    }
