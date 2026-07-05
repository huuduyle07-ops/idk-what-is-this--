"""EVAL.N3 - Evidence Quality Report Builder (report-only).

Builds an advisory evidence quality report from explicitly supplied existing
artifacts by reusing the EVAL.N2 report contract. EVAL.N3 never runs
validation, benchmarks, models, patch application, MCP tools, workers, network
calls, database writes, scoring gates, or approval/rejection logic.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.evidence_quality_plan import FUTURE_VERDICTS
from core.evidence_quality_report_contract import (
    ARTIFACT_SLOTS,
    EXCERPT_CHAR_LIMIT,
    build_evidence_quality_report_contract,
)


REPORT_KIND = "evidence_quality_report"
JSON_NAME = "evidence_quality_report.json"
MD_NAME = "evidence_quality_report.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "eval" / "evidence_quality_report"

EVIDENCE_QUALITY_STATUSES: tuple[str, ...] = (
    "evidence_quality_ready",
    "evidence_quality_ready_with_warnings",
    "evidence_quality_incomplete",
    "evidence_quality_blocked",
)

OVERALL_EVIDENCE_QUALITY_VALUES: tuple[str, ...] = (
    "strong",
    "adequate",
    "partial",
    "weak",
    "missing",
    "contradicted",
    "blocked",
)

RECOMMENDED_HUMAN_CHECKS: tuple[str, ...] = (
    "review changed files manually",
    "confirm validation was run after patch",
    "confirm benchmark relevance",
    "confirm final answer does not overclaim",
    "confirm missing evidence is acceptable before apply",
    "confirm human approval before patch apply",
)

EVIDENCE_QUALITY_REPORT_GUARDRAIL_NOTE = (
    "Evidence Quality Report Builder is report-only and artifact-inspection-only: "
    "it reads explicitly supplied existing artifacts through the EVAL.N2 contract, "
    "applies deterministic evidence-quality summarization, and writes advisory "
    "JSON/Markdown reports. It does not run tests, run validation, run benchmarks, "
    "call models, apply patches, change scoring gates, invoke MCP tools, launch "
    "workers, contact networks, write databases, or approve/reject work."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "EVAL.N4",
    "title": "Evidence Quality Artifact Loader Plan",
    "reason": (
        "After building a real report, plan how to surface existing evidence "
        "quality artifacts safely without turning them into an approval gate."
    ),
}

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "tests_run_performed",
    "validation_run_performed",
    "benchmark_run_performed",
    "model_call_performed",
    "patch_apply_performed",
    "mcp_invocation_performed",
    "worker_launch_performed",
    "dream_execution_performed",
    "replay_janitor_apply_performed",
    "docker_or_subprocess_used",
    "network_contacted",
    "database_write_performed",
    "route_behavior_changed",
    "auth_policy_changed",
    "scoring_gate_changed",
    "approval_or_rejection_performed",
)

_FILE_TOKEN_RE = re.compile(
    r"(?:[ab]/)?([A-Za-z0-9_.\-/]+\.(?:py|md|json|txt|js|ts|tsx|jsx|html|css|yml|yaml|toml))"
)


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def _status_from_contract(contract_status: str) -> str:
    return {
        "evidence_quality_report_ready": "evidence_quality_ready",
        "evidence_quality_report_ready_with_warnings": "evidence_quality_ready_with_warnings",
        "evidence_quality_report_incomplete": "evidence_quality_incomplete",
        "evidence_quality_report_blocked": "evidence_quality_blocked",
    }.get(str(contract_status), "evidence_quality_incomplete")


def _clone_list(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict)]


def _not_supplied_artifact_entry(artifact_key: str, artifact_type: str) -> dict[str, Any]:
    return {
        "artifact_key": artifact_key,
        "artifact_type": artifact_type,
        "path": "",
        "resolved_path": "",
        "read_status": "not_supplied",
        "size_chars": 0,
        "excerpt": "",
        "timestamp": "",
        "optional": True,
    }


def _not_supplied_evidence_entry(artifact_key: str, artifact_type: str) -> dict[str, Any]:
    return {
        "artifact_key": artifact_key,
        "artifact_type": artifact_type,
        "evidence_status": "not_supplied",
        "result_signal": "not_supplied",
        "signals": [],
        "timestamp": "",
        "excerpt": "",
    }


def _mark_optional_artifact_slots(
    artifact_inventory: list[dict[str, Any]],
    evidence_inventory: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inventory_by_key = {
        str(item.get("artifact_key", "")): dict(item)
        for item in artifact_inventory
        if item.get("artifact_key")
    }
    evidence_by_key = {
        str(item.get("artifact_key", "")): dict(item)
        for item in evidence_inventory
        if item.get("artifact_key")
    }

    ordered_inventory: list[dict[str, Any]] = []
    ordered_evidence: list[dict[str, Any]] = []
    known_keys: set[str] = set()
    for artifact_key, artifact_type in ARTIFACT_SLOTS:
        known_keys.add(artifact_key)
        inventory_entry = inventory_by_key.get(artifact_key)
        if inventory_entry is None:
            inventory_entry = _not_supplied_artifact_entry(artifact_key, artifact_type)
        else:
            inventory_entry.setdefault("artifact_type", artifact_type)
        ordered_inventory.append(inventory_entry)

        evidence_entry = evidence_by_key.get(artifact_key)
        if evidence_entry is None:
            evidence_entry = _not_supplied_evidence_entry(artifact_key, artifact_type)
        else:
            evidence_entry.setdefault("artifact_type", artifact_type)
        ordered_evidence.append(evidence_entry)

    ordered_inventory.extend(
        item for item in artifact_inventory if str(item.get("artifact_key", "")) not in known_keys
    )
    ordered_evidence.extend(
        item for item in evidence_inventory if str(item.get("artifact_key", "")) not in known_keys
    )
    return ordered_inventory, ordered_evidence


def _artifact_present(inventory: list[dict[str, Any]], artifact_key: str) -> bool:
    return any(
        item.get("artifact_key") == artifact_key and item.get("read_status") == "present"
        for item in inventory
    )


def _meaningful(inventory: list[dict[str, Any]]) -> bool:
    return any(item.get("read_status") == "present" for item in inventory)


def _warning_ids(warnings: list[dict[str, Any]]) -> set[str]:
    return {str(item.get("warning_id", "")) for item in warnings}


def _missing_ids(missing: list[dict[str, Any]]) -> set[str]:
    return {str(item.get("missing_id", "")) for item in missing}


def _add_warning(
    warnings: list[dict[str, Any]],
    warning_id: str,
    message: str,
    *,
    severity: str = "medium",
    artifact_key: str = "",
) -> None:
    if not any(
        item.get("warning_id") == warning_id and item.get("artifact_key", "") == artifact_key
        for item in warnings
    ):
        warnings.append(
            {
                "warning_id": warning_id,
                "severity": severity,
                "artifact_key": artifact_key,
                "message": message,
            }
        )


def _artifact_excerpt(inventory: list[dict[str, Any]], artifact_key: str) -> str:
    for item in inventory:
        if item.get("artifact_key") == artifact_key:
            return str(item.get("excerpt", ""))
    return ""


def _extract_file_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for match in _FILE_TOKEN_RE.finditer(text):
        token = match.group(1).replace("\\", "/").lower().strip("/")
        if token:
            tokens.add(token)
            tokens.add(token.rsplit("/", 1)[-1])
    return tokens


def _validation_scope_is_clear(inventory: list[dict[str, Any]]) -> bool:
    has_patch = _artifact_present(inventory, "patch") or _artifact_present(inventory, "diff")
    has_validation = _artifact_present(inventory, "validation")
    if not (has_patch and has_validation):
        return True

    patch_text = _artifact_excerpt(inventory, "patch") + "\n" + _artifact_excerpt(inventory, "diff")
    validation_text = _artifact_excerpt(inventory, "validation").lower()
    file_tokens = _extract_file_tokens(patch_text)
    if any(token and token in validation_text for token in file_tokens):
        return True
    return any(
        phrase in validation_text
        for phrase in (
            "changed file",
            "changed files",
            "changed behavior",
            "affected file",
            "affected files",
            "affected behavior",
            "patch scope",
            "diff scope",
        )
    )


def _dimension_reviews(
    contract_reviews: Any,
    *,
    inventory: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    validation_scope_clear = _validation_scope_is_clear(inventory)
    for item in _clone_list(contract_reviews):
        findings = item.get("findings")
        item["findings"] = list(findings) if isinstance(findings, list) else []
        if item.get("dimension_id") == "validation_relevance" and not validation_scope_clear:
            if item.get("verdict") == "supported":
                item["verdict"] = "partially_supported"
            elif item.get("verdict") in {"partially_supported", "not_applicable"}:
                item["verdict"] = "weakly_supported"
            item["findings"].append(
                "Validation artifact did not mention changed behavior/files from the supplied patch or diff."
            )
            _add_warning(
                warnings,
                "validation_relevance_unclear",
                "Validation evidence exists but does not mention changed behavior/files from the supplied patch or diff.",
                severity="medium",
                artifact_key="validation",
            )
        reviews.append(item)
    return reviews


def _add_builder_warning_aliases(
    *,
    missing: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    ids = _missing_ids(missing)
    if ids & {"missing_validation_for_patch", "missing_validation_for_validation_claim"}:
        _add_warning(
            warnings,
            "missing_validation_evidence",
            "Validation evidence is missing for a validation/test claim or supplied patch/diff.",
            severity="medium",
        )
    if "missing_benchmark_for_benchmark_claim" in ids:
        _add_warning(
            warnings,
            "missing_benchmark_evidence",
            "Benchmark evidence is missing for a benchmark claim.",
            severity="medium",
        )


def _overall_evidence_quality(
    *,
    blocked_reasons: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    dimension_reviews: list[dict[str, Any]],
) -> str:
    if blocked_reasons:
        return "blocked"
    if not _meaningful(inventory):
        return "missing"
    if contradictions:
        return "contradicted"
    if any(item.get("severity") == "high" for item in warnings):
        return "weak"

    verdicts = {str(item.get("verdict", "")) for item in dimension_reviews}
    if "unsupported" in verdicts:
        return "weak"
    if "weakly_supported" in verdicts:
        return "partial"
    if missing or "missing_evidence" in verdicts:
        return "partial"

    ids = _warning_ids(warnings)
    if ids <= {"unknown_freshness"} and warnings:
        return "adequate"
    if warnings:
        return "adequate"
    return "strong"


def _human_review_boundary(boundary: Any) -> dict[str, Any]:
    data = dict(boundary) if isinstance(boundary, dict) else {}
    data["advisory_only"] = True
    data["approved"] = False
    data["safe_to_apply"] = False
    existing = data.get("manual_review_required")
    checks = list(existing) if isinstance(existing, list) else []
    for item in RECOMMENDED_HUMAN_CHECKS:
        if item not in checks:
            checks.append(item)
    data["manual_review_required"] = checks
    return data


def _boundaries() -> dict[str, bool]:
    return {
        "report_only": True,
        "artifact_inspection_only": True,
        "deterministic_scanning_only": True,
        "reads_only_explicit_source_artifacts": True,
        "writes_evidence_quality_artifacts_only": True,
        "advisory_only": True,
        "runs_validation": False,
        "runs_benchmarks": False,
        "calls_models": False,
        "applies_patches": False,
        "changes_scoring_gates": False,
        "approves_or_rejects_work": False,
    }


def build_evidence_quality_report(
    *,
    patch: str | Path | None = None,
    diff: str | Path | None = None,
    validation: str | Path | None = None,
    benchmark: str | Path | None = None,
    final_answer: str | Path | None = None,
    mirror_preview: str | Path | None = None,
    commander_review: str | Path | None = None,
    evidence_pack: str | Path | None = None,
    repo_root: str | Path | None = None,
    report_id: str = "evidence-quality-report",
) -> dict[str, Any]:
    """Build a deterministic advisory EVAL.N3 evidence quality report."""
    contract = build_evidence_quality_report_contract(
        patch=patch,
        diff=diff,
        validation=validation,
        benchmark=benchmark,
        final_answer=final_answer,
        mirror_preview=mirror_preview,
        commander_review=commander_review,
        evidence_pack=evidence_pack,
        repo_root=repo_root,
        report_id=report_id,
    )

    artifact_inventory = _clone_list(contract.get("artifact_inventory"))
    source_artifacts = _clone_list(contract.get("source_artifacts"))
    claims = _clone_list(contract.get("claim_inventory"))
    evidence_inventory = _clone_list(contract.get("evidence_inventory"))
    artifact_inventory, evidence_inventory = _mark_optional_artifact_slots(
        artifact_inventory,
        evidence_inventory,
    )
    missing = _clone_list(contract.get("missing_evidence"))
    contradictions = _clone_list(contract.get("contradiction_risks"))
    freshness = _clone_list(contract.get("freshness_findings"))
    confidence = _clone_list(contract.get("confidence_alignment_findings"))
    scope = _clone_list(contract.get("scope_alignment_findings"))
    warnings = _clone_list(contract.get("warnings"))
    blocked_reasons = _clone_list(contract.get("blocked_reasons"))
    _add_builder_warning_aliases(missing=missing, warnings=warnings)
    dimensions = _dimension_reviews(
        contract.get("dimension_reviews"),
        inventory=artifact_inventory,
        warnings=warnings,
    )
    boundary = _human_review_boundary(contract.get("human_review_boundary"))
    overall = _overall_evidence_quality(
        blocked_reasons=blocked_reasons,
        inventory=artifact_inventory,
        warnings=warnings,
        missing=missing,
        contradictions=contradictions,
        dimension_reviews=dimensions,
    )

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": EVIDENCE_QUALITY_REPORT_GUARDRAIL_NOTE,
        "report_id": str(report_id or "evidence-quality-report"),
        "source_artifacts": source_artifacts,
        "evidence_quality_status": _status_from_contract(str(contract.get("evidence_quality_status", ""))),
        "overall_evidence_quality": overall,
        "artifact_inventory": artifact_inventory,
        "claim_inventory": claims,
        "evidence_inventory": evidence_inventory,
        "dimension_reviews": dimensions,
        "missing_evidence": missing,
        "contradiction_risks": contradictions,
        "freshness_findings": freshness,
        "confidence_alignment_findings": confidence,
        "scope_alignment_findings": scope,
        "human_review_boundary": boundary,
        "recommended_human_checks": list(RECOMMENDED_HUMAN_CHECKS),
        "warnings": warnings,
        "blocked_reasons": blocked_reasons,
        "boundaries": _boundaries(),
        "guardrails": _guardrails(),
        "report_statuses": list(EVIDENCE_QUALITY_STATUSES),
        "overall_evidence_quality_values": list(OVERALL_EVIDENCE_QUALITY_VALUES),
        "verdicts": list(FUTURE_VERDICTS),
        "source_contract_kind": contract.get("report_kind", ""),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def _render_items(lines: list[str], values: list[Any]) -> None:
    if values:
        for value in values:
            if isinstance(value, dict):
                lines.append(f"- `{_md(json.dumps(value, sort_keys=True))}`")
            else:
                lines.append(f"- `{_md(value)}`")
    else:
        lines.append("_None._")
    lines.append("")


def render_evidence_quality_report_markdown(report: dict[str, Any]) -> str:
    """Render an EVAL.N3 evidence quality report as Markdown."""
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    lines: list[str] = [
        "# Evidence Quality Report",
        "",
        f"> {report.get('guardrail_note', EVIDENCE_QUALITY_REPORT_GUARDRAIL_NOTE)}",
        "",
        "_Report only: EVAL.N3 inspects explicitly supplied artifacts and grants no approval, rejection, execution, validation, benchmark, model, patch, or scoring-gate authority._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id', ''))}`",
        f"- **Evidence quality status:** `{_md(report.get('evidence_quality_status', ''))}`",
        f"- **Source artifact count:** {len(report.get('source_artifacts') or [])}",
        f"- **Claim count:** {len(report.get('claim_inventory') or [])}",
        f"- **Evidence item count:** {len(report.get('evidence_inventory') or [])}",
        f"- **Warning count:** {len(report.get('warnings') or [])}",
        f"- **Blocked reason count:** {len(report.get('blocked_reasons') or [])}",
        f"- **Recommended next phase:** `{_md(next_phase.get('phase_id', ''))}`",
        "",
        "## Overall Evidence Quality",
        "",
        f"- **Overall:** `{_md(report.get('overall_evidence_quality', ''))}`",
        "",
    ]

    sections = (
        ("Source Artifacts", "source_artifacts"),
        ("Artifact Inventory", "artifact_inventory"),
        ("Claim Inventory", "claim_inventory"),
        ("Evidence Inventory", "evidence_inventory"),
        ("Dimension Reviews", "dimension_reviews"),
        ("Missing Evidence", "missing_evidence"),
        ("Contradiction Risks", "contradiction_risks"),
        ("Freshness Findings", "freshness_findings"),
        ("Confidence Alignment Findings", "confidence_alignment_findings"),
        ("Scope Alignment Findings", "scope_alignment_findings"),
    )
    for title, key in sections:
        lines += [f"## {title}", ""]
        _render_items(lines, list(report.get(key) or []))

    lines += ["## Human Review Boundary", ""]
    boundary = report.get("human_review_boundary") if isinstance(report.get("human_review_boundary"), dict) else {}
    lines.append(f"- Advisory only: `{str(bool(boundary.get('advisory_only'))).lower()}`")
    lines.append(f"- Approved: `{str(bool(boundary.get('approved'))).lower()}`")
    lines.append(f"- Safe to apply: `{str(bool(boundary.get('safe_to_apply'))).lower()}`")
    for item in boundary.get("manual_review_required") or []:
        lines.append(f"- {_md(item)}")
    lines.append("")

    lines += ["## Recommended Human Checks", ""]
    for item in report.get("recommended_human_checks") or []:
        lines.append(f"- {_md(item)}")
    lines.append("")

    for title, key in (
        ("Warnings", "warnings"),
        ("Blocked Reasons", "blocked_reasons"),
    ):
        lines += [f"## {title}", ""]
        _render_items(lines, list(report.get(key) or []))

    lines += ["## Boundaries", ""]
    boundaries = report.get("boundaries") if isinstance(report.get("boundaries"), dict) else {}
    for key in sorted(boundaries):
        lines.append(f"- `{_md(key)}`: {str(bool(boundaries[key])).lower()}")
    lines.append("")

    lines += [
        "## Recommended Next Phase",
        "",
        f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
        f"- **Title:** {_md(next_phase.get('title', ''))}",
        f"- **Reason:** {_md(next_phase.get('reason', ''))}",
        "",
    ]
    return "\n".join(lines)


def write_evidence_quality_report(
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    *,
    patch: str | Path | None = None,
    diff: str | Path | None = None,
    validation: str | Path | None = None,
    benchmark: str | Path | None = None,
    final_answer: str | Path | None = None,
    mirror_preview: str | Path | None = None,
    commander_review: str | Path | None = None,
    evidence_pack: str | Path | None = None,
    repo_root: str | Path | None = None,
    report_id: str = "evidence-quality-report",
) -> dict[str, Any]:
    """Build and write EVAL.N3 JSON + Markdown evidence quality artifacts."""
    report = build_evidence_quality_report(
        patch=patch,
        diff=diff,
        validation=validation,
        benchmark=benchmark,
        final_answer=final_answer,
        mirror_preview=mirror_preview,
        commander_review=commander_review,
        evidence_pack=evidence_pack,
        repo_root=repo_root,
        report_id=report_id,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_evidence_quality_report_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
