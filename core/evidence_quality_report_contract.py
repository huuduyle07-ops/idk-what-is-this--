"""EVAL.N2 - Evidence Quality Report Contract (report-only).

Inspects explicitly supplied artifacts and builds an advisory evidence quality
report contract using the EVAL.N1 dimensions. EVAL.N2 never runs validation,
benchmarks, models, patch application, MCP tools, workers, network calls,
database writes, scoring gates, or approval/rejection logic.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.evidence_quality_plan import EVIDENCE_DIMENSIONS, FUTURE_VERDICTS


REPORT_KIND = "evidence_quality_report_contract"
JSON_NAME = "evidence_quality_report_contract.json"
MD_NAME = "evidence_quality_report_contract.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "eval" / "evidence_quality_report_contract"
EXCERPT_CHAR_LIMIT = 240

EVIDENCE_QUALITY_REPORT_STATUSES: tuple[str, ...] = (
    "evidence_quality_report_ready",
    "evidence_quality_report_ready_with_warnings",
    "evidence_quality_report_incomplete",
    "evidence_quality_report_blocked",
)

ARTIFACT_SLOTS: tuple[tuple[str, str], ...] = (
    ("patch", "patch proposal/diff artifact"),
    ("diff", "diff text"),
    ("validation", "validation result artifact/text"),
    ("benchmark", "benchmark result artifact/text"),
    ("final_answer", "final answer text"),
    ("mirror_preview", "MIRROR.8 live trace scoring preview JSON"),
    ("commander_review", "CMD.N6 assignment review pack JSON"),
    ("evidence_pack", "existing evidence pack JSON/MD"),
)

FORBIDDEN_PATH_PARTS: tuple[str, ...] = (
    ".env",
    ".agent/private",
    "secrets",
    "secret",
    "credentials",
    "credential",
)

CLAIM_PATTERNS: tuple[tuple[str, str], ...] = (
    ("tests_passed", r"\btests?\s+(?:all\s+)?pass(?:ed)?\b|\b\d+\s+passed\b"),
    ("validation_passed", r"\bvalidation\s+(?:result\s+)?pass(?:ed)?\b"),
    ("benchmark_passed", r"\bbenchmarks?\s+(?:result\s+)?pass(?:ed)?\b"),
    ("fixed", r"\bfix(?:ed|es)?\b"),
    ("verified", r"\bverified\b|\bverify\b"),
    ("safe", r"\bsafe\b"),
    ("no_blockers", r"\bno\s+blockers?\b"),
    ("no_warnings", r"\bno\s+warnings?\b"),
    ("ready", r"\bready\b"),
    ("complete", r"\bcomplete(?:d)?\b"),
    ("applied", r"\bapplied\b"),
    ("generated", r"\bgenerated\b"),
    ("evidence_exists", r"\bevidence\s+exists\b"),
)

CAVEAT_TERMS: tuple[str, ...] = (
    "timed out",
    "timeout",
    "not counted",
    "not claimed",
    "not run",
    "did not run",
    "not verified",
    "not safe",
)

AUTHORITY_CLAIMS: tuple[str, ...] = (
    "approved to apply",
    "safe to apply",
    "approved for merge",
    "approval granted",
    "apply patch now",
    "auto-merge approved",
    "safe to merge",
)

TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?\b"
)

EVIDENCE_QUALITY_REPORT_GUARDRAIL_NOTE = (
    "Evidence Quality Report Contract is report-only and artifact-inspection-only: "
    "it reads explicitly supplied artifacts, applies deterministic claim/evidence "
    "scanning, and writes advisory JSON/Markdown reports. It does not run tests, "
    "run benchmarks, call models, apply patches, change scoring gates, invoke MCP "
    "tools, launch workers, contact networks, write databases, or approve/reject work."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "EVAL.N3",
    "title": "Evidence Quality Report Builder",
    "reason": (
        "Use this contract to build an actual evidence quality report from a "
        "realistic existing run/evidence pack, still without executing validation, "
        "benchmarks, models, patch application, or approval logic."
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


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def _path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _forbidden_path(path: Path) -> bool:
    lowered = [part.lower() for part in path.parts]
    joined = "/".join(lowered)
    for forbidden in FORBIDDEN_PATH_PARTS:
        if "/" in forbidden and forbidden in joined:
            return True
        if forbidden in lowered:
            return True
    return False


def _excerpt(text: str) -> str:
    if len(text) <= EXCERPT_CHAR_LIMIT:
        return text
    return text[:EXCERPT_CHAR_LIMIT] + "..."


def _first_timestamp(text: str) -> str:
    match = TIMESTAMP_RE.search(text)
    return match.group(0) if match else ""


def _has_caveat(text: str) -> bool:
    low = text.lower()
    return any(term in low for term in CAVEAT_TERMS)


def _read_artifact(
    artifact_key: str,
    artifact_type: str,
    value: str | Path | None,
    *,
    repo_root: str | Path | None,
) -> tuple[dict[str, Any] | None, str, list[dict[str, str]]]:
    """Read one explicitly supplied artifact path, returning inventory + text.

    The function reads no recursive paths and performs no discovery. A missing
    optional value returns ``None``. An explicitly supplied bad path returns a
    blocked inventory entry and blocked reason.
    """
    if value in (None, ""):
        return None, "", []

    root = Path(repo_root or Path.cwd()).resolve(strict=False)
    raw_path = Path(value)
    candidate = raw_path if raw_path.is_absolute() else root / raw_path
    resolved = candidate.resolve(strict=False)
    entry: dict[str, Any] = {
        "artifact_key": artifact_key,
        "artifact_type": artifact_type,
        "path": str(raw_path),
        "resolved_path": str(resolved),
        "read_status": "pending",
        "size_chars": 0,
        "excerpt": "",
        "timestamp": "",
    }
    blocked: list[dict[str, str]] = []

    if not _path_is_relative_to(resolved, root):
        entry["read_status"] = "blocked"
        blocked.append(
            {
                "reason_id": "unsafe_source_path",
                "artifact_key": artifact_key,
                "message": "Source artifact path is outside the configured repository root.",
            }
        )
        return entry, "", blocked

    if _forbidden_path(resolved):
        entry["read_status"] = "blocked"
        blocked.append(
            {
                "reason_id": "forbidden_source_path",
                "artifact_key": artifact_key,
                "message": "Source artifact path points at a forbidden .env/secret/credential location.",
            }
        )
        return entry, "", blocked

    if not resolved.is_file():
        entry["read_status"] = "unreadable"
        blocked.append(
            {
                "reason_id": "source_artifact_unreadable",
                "artifact_key": artifact_key,
                "message": "Explicitly supplied source artifact is missing or not a file.",
            }
        )
        return entry, "", blocked

    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        entry["read_status"] = "unreadable"
        blocked.append(
            {
                "reason_id": "source_artifact_unreadable",
                "artifact_key": artifact_key,
                "message": f"Explicitly supplied source artifact could not be read: {exc}",
            }
        )
        return entry, "", blocked

    entry["size_chars"] = len(text)
    entry["excerpt"] = _excerpt(text)
    entry["timestamp"] = _first_timestamp(text)
    entry["read_status"] = "empty" if not text.strip() else "present"

    if resolved.suffix.lower() == ".json" and text.strip():
        try:
            json.loads(text)
        except json.JSONDecodeError:
            entry["read_status"] = "malformed_json"
            blocked.append(
                {
                    "reason_id": "malformed_json_artifact",
                    "artifact_key": artifact_key,
                    "message": "Artifact has a .json suffix but is not valid JSON.",
                }
            )

    lowered = text.lower()
    if any(phrase in lowered for phrase in AUTHORITY_CLAIMS):
        blocked.append(
            {
                "reason_id": "artifact_claims_executable_authority",
                "artifact_key": artifact_key,
                "message": "Artifact claims approval/apply/merge authority that this report cannot grant.",
            }
        )

    return entry, text, blocked


def _load_artifacts(
    *,
    repo_root: str | Path | None,
    patch: str | Path | None,
    diff: str | Path | None,
    validation: str | Path | None,
    benchmark: str | Path | None,
    final_answer: str | Path | None,
    mirror_preview: str | Path | None,
    commander_review: str | Path | None,
    evidence_pack: str | Path | None,
) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, str]]]:
    values = {
        "patch": patch,
        "diff": diff,
        "validation": validation,
        "benchmark": benchmark,
        "final_answer": final_answer,
        "mirror_preview": mirror_preview,
        "commander_review": commander_review,
        "evidence_pack": evidence_pack,
    }
    inventory: list[dict[str, Any]] = []
    texts: dict[str, str] = {}
    blocked: list[dict[str, str]] = []
    for key, artifact_type in ARTIFACT_SLOTS:
        entry, text, reasons = _read_artifact(key, artifact_type, values.get(key), repo_root=repo_root)
        if entry is None:
            continue
        inventory.append(entry)
        if text:
            texts[key] = text
        blocked.extend(reasons)
    return inventory, texts, blocked


def _claim_inventory(texts: dict[str, str]) -> list[dict[str, str]]:
    claims: list[dict[str, str]] = []
    claim_index = 1
    for artifact_key in sorted(texts):
        text = texts[artifact_key]
        for claim_type, pattern in CLAIM_PATTERNS:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                start = max(match.start() - 45, 0)
                end = min(match.end() + 45, len(text))
                claims.append(
                    {
                        "claim_id": f"claim-{claim_index:03d}",
                        "artifact_key": artifact_key,
                        "claim_type": claim_type,
                        "phrase": match.group(0),
                        "excerpt": _excerpt(text[start:end].strip()),
                    }
                )
                claim_index += 1
    return claims


def _types(claims: list[dict[str, str]]) -> set[str]:
    return {claim["claim_type"] for claim in claims}


def _evidence_status(text: str) -> str:
    low = text.lower()
    if "timed out" in low or "timeout" in low:
        return "timed_out"
    if any(word in low for word in ("failed", "failure", "error", "blocked")):
        return "failed"
    if any(word in low for word in ("passed", "pass", "success", "ok")):
        return "passed"
    return "present"


def _evidence_inventory(inventory: list[dict[str, Any]], texts: dict[str, str]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in inventory:
        key = str(item.get("artifact_key", ""))
        status = str(item.get("read_status", ""))
        if status in {"blocked", "unreadable", "malformed_json"}:
            evidence_status = "blocked"
            result_signal = "unavailable"
            signals: list[str] = []
        elif status == "empty":
            evidence_status = "empty"
            result_signal = "empty"
            signals = []
        else:
            text = texts.get(key, "")
            evidence_status = "present"
            result_signal = _evidence_status(text)
            signals = sorted(_types(_claim_inventory({key: text})))
        evidence.append(
            {
                "artifact_key": key,
                "artifact_type": item.get("artifact_type", ""),
                "evidence_status": evidence_status,
                "result_signal": result_signal,
                "signals": signals,
                "timestamp": item.get("timestamp", ""),
                "excerpt": item.get("excerpt", ""),
            }
        )
    return evidence


def _present(inventory: list[dict[str, Any]], key: str) -> bool:
    return any(
        item.get("artifact_key") == key and item.get("read_status") == "present"
        for item in inventory
    )


def _meaningful(inventory: list[dict[str, Any]]) -> bool:
    return any(item.get("read_status") == "present" for item in inventory)


def _add_warning(
    warnings: list[dict[str, str]],
    warning_id: str,
    message: str,
    *,
    severity: str = "medium",
    artifact_key: str = "",
) -> None:
    if not any(w.get("warning_id") == warning_id and w.get("artifact_key") == artifact_key for w in warnings):
        warnings.append(
            {
                "warning_id": warning_id,
                "severity": severity,
                "artifact_key": artifact_key,
                "message": message,
            }
        )


def _missing_evidence(
    claims: list[dict[str, str]],
    inventory: list[dict[str, Any]],
    warnings: list[dict[str, str]],
) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    claim_types = _types(claims)
    has_validation = _present(inventory, "validation")
    has_benchmark = _present(inventory, "benchmark")
    has_patch_or_diff = _present(inventory, "patch") or _present(inventory, "diff")

    def add(missing_id: str, evidence_type: str, reason: str) -> None:
        if not any(item["missing_id"] == missing_id for item in missing):
            missing.append({"missing_id": missing_id, "evidence_type": evidence_type, "reason": reason})
            _add_warning(warnings, missing_id, reason, severity="medium")

    if {"tests_passed", "validation_passed"} & claim_types and not has_validation:
        add(
            "missing_validation_for_validation_claim",
            "validation",
            "Validation/test success is claimed but no validation artifact was supplied.",
        )
    if "benchmark_passed" in claim_types and not has_benchmark:
        add(
            "missing_benchmark_for_benchmark_claim",
            "benchmark",
            "Benchmark success is claimed but no benchmark artifact was supplied.",
        )
    if {"fixed", "applied"} & claim_types and not has_patch_or_diff:
        add(
            "missing_patch_or_diff_for_change_claim",
            "patch_or_diff",
            "A fix/apply claim exists but no patch or diff artifact was supplied.",
        )
    if has_patch_or_diff and not has_validation:
        add(
            "missing_validation_for_patch",
            "validation",
            "Patch/diff evidence exists but no validation artifact was supplied.",
        )
    return missing


def _contradiction_risks(
    claims: list[dict[str, str]],
    texts: dict[str, str],
    warnings: list[dict[str, str]],
) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    claim_types = _types(claims)

    def add(risk_id: str, artifact_key: str, reason: str) -> None:
        risks.append({"risk_id": risk_id, "artifact_key": artifact_key, "reason": reason})
        _add_warning(warnings, risk_id, reason, severity="high", artifact_key=artifact_key)

    validation_text = texts.get("validation", "").lower()
    if {"tests_passed", "validation_passed"} & claim_types and any(
        word in validation_text for word in ("failed", "failure", "error")
    ):
        add("validation_claim_conflicts_with_artifact", "validation", "Validation/test pass claim conflicts with validation artifact text.")

    benchmark_text = texts.get("benchmark", "").lower()
    if "benchmark_passed" in claim_types and any(word in benchmark_text for word in ("failed", "failure", "error")):
        add("benchmark_claim_conflicts_with_artifact", "benchmark", "Benchmark pass claim conflicts with benchmark artifact text.")

    if "no_warnings" in claim_types:
        for key, text in texts.items():
            if key != "final_answer" and "warning" in text.lower():
                add("no_warnings_claim_conflicts_with_artifact", key, "A no-warnings claim conflicts with warning text in an artifact.")
                break

    if "no_blockers" in claim_types:
        for key, text in texts.items():
            if key != "final_answer" and "blocker" in text.lower():
                add("no_blockers_claim_conflicts_with_artifact", key, "A no-blockers claim conflicts with blocker text in an artifact.")
                break

    return risks


def _freshness_findings(inventory: list[dict[str, Any]], warnings: list[dict[str, str]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    meaningful = [item for item in inventory if item.get("read_status") == "present"]
    if not meaningful:
        findings.append(
            {
                "finding_id": "unknown_freshness",
                "freshness_status": "unknown_timestamp",
                "message": "No meaningful source artifact timestamps are available.",
            }
        )
        _add_warning(warnings, "unknown_freshness", "No meaningful source artifact timestamps are available.", severity="low")
        return findings

    timestamps = {str(item.get("artifact_key")): str(item.get("timestamp") or "") for item in meaningful}
    if not any(timestamps.values()):
        findings.append(
            {
                "finding_id": "unknown_freshness",
                "freshness_status": "unknown_timestamp",
                "message": "Supplied artifacts did not contain parseable timestamps.",
            }
        )
        _add_warning(warnings, "unknown_freshness", "Supplied artifacts did not contain parseable timestamps.", severity="low")

    patch_time = timestamps.get("patch") or timestamps.get("diff") or ""
    if patch_time:
        for key in ("validation", "benchmark", "evidence_pack", "mirror_preview", "commander_review"):
            evidence_time = timestamps.get(key, "")
            if evidence_time and evidence_time < patch_time:
                finding_id = f"{key}_pre_patch"
                findings.append(
                    {
                        "finding_id": finding_id,
                        "freshness_status": "pre_patch",
                        "message": f"{key} evidence timestamp appears older than patch/diff timestamp.",
                    }
                )
                _add_warning(warnings, finding_id, f"{key} evidence appears stale/pre-patch.", severity="medium", artifact_key=key)
            elif key in timestamps and not evidence_time:
                finding_id = f"{key}_unknown_freshness"
                findings.append(
                    {
                        "finding_id": finding_id,
                        "freshness_status": "unknown_timestamp",
                        "message": f"{key} evidence has no parseable timestamp.",
                    }
                )
                _add_warning(warnings, finding_id, f"{key} evidence has unknown freshness.", severity="low", artifact_key=key)

    if not findings:
        findings.append(
            {
                "finding_id": "freshness_reviewed",
                "freshness_status": "reviewed",
                "message": "Freshness was inspected with no stale evidence found.",
            }
        )
    return findings


def _confidence_alignment_findings(
    claims: list[dict[str, str]],
    texts: dict[str, str],
    inventory: list[dict[str, Any]],
    warnings: list[dict[str, str]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    claim_types = _types(claims)
    confidence_claims = {"verified", "safe", "complete", "ready", "tests_passed", "validation_passed", "benchmark_passed"}
    if not (claim_types & confidence_claims):
        return [
            {
                "finding_id": "no_confidence_claims_detected",
                "severity": "info",
                "message": "No strong confidence claim was detected.",
            }
        ]

    support_keys = ("patch", "diff", "validation", "benchmark", "mirror_preview", "commander_review", "evidence_pack")
    support_count = sum(1 for key in support_keys if _present(inventory, key))
    final_text = texts.get("final_answer", "")
    caveated = _has_caveat(final_text)
    if support_count == 0:
        severity = "low" if caveated else "high"
        warning_id = "confidence_overstated_caveated" if caveated else "confidence_overstated"
        finding = {
            "finding_id": "confidence_overstated",
            "severity": severity,
            "message": "Final-answer confidence is stronger than the supplied evidence artifacts support.",
        }
        findings.append(finding)
        _add_warning(
            warnings,
            warning_id,
            finding["message"],
            severity=severity,
            artifact_key="final_answer",
        )
    elif {"complete", "ready", "safe"} & claim_types and not (_present(inventory, "validation") or _present(inventory, "benchmark")):
        finding = {
            "finding_id": "confidence_partially_supported",
            "severity": "medium",
            "message": "Confidence language is present, but validation/benchmark support is absent.",
        }
        findings.append(finding)
        _add_warning(warnings, "confidence_partially_supported", finding["message"], severity="medium", artifact_key="final_answer")
    else:
        findings.append(
            {
                "finding_id": "confidence_evidence_aligned",
                "severity": "info",
                "message": "Confidence language has at least one matching support artifact.",
            }
        )
    return findings


def _scope_alignment_findings(
    claims: list[dict[str, str]],
    inventory: list[dict[str, Any]],
    warnings: list[dict[str, str]],
) -> list[dict[str, str]]:
    claim_types = _types(claims)
    findings: list[dict[str, str]] = []
    has_patch_or_diff = _present(inventory, "patch") or _present(inventory, "diff")
    if {"complete", "ready", "safe"} & claim_types and not (_present(inventory, "validation") or _present(inventory, "benchmark")):
        findings.append(
            {
                "finding_id": "scope_claim_exceeds_supplied_evidence",
                "severity": "medium",
                "message": "Broad completion/readiness language exceeds the supplied validation or benchmark evidence.",
            }
        )
        _add_warning(
            warnings,
            "scope_claim_exceeds_supplied_evidence",
            "Broad completion/readiness language exceeds supplied evidence.",
            severity="medium",
        )
    elif {"complete", "ready", "fixed", "applied"} & claim_types and not has_patch_or_diff:
        findings.append(
            {
                "finding_id": "change_scope_missing_patch_or_diff",
                "severity": "medium",
                "message": "Change-readiness language is present, but no patch/diff artifact was supplied.",
            }
        )
        _add_warning(
            warnings,
            "change_scope_missing_patch_or_diff",
            "Change-readiness language is present without patch/diff evidence.",
            severity="medium",
        )
    if not findings:
        findings.append(
            {
                "finding_id": "scope_reviewed",
                "severity": "info",
                "message": "Scope alignment was reviewed from the supplied artifacts.",
            }
        )
    return findings


def _dimension_reviews(
    *,
    claims: list[dict[str, str]],
    inventory: list[dict[str, Any]],
    missing: list[dict[str, str]],
    contradictions: list[dict[str, str]],
    freshness: list[dict[str, str]],
    confidence: list[dict[str, str]],
    scope: list[dict[str, str]],
) -> list[dict[str, Any]]:
    claim_types = _types(claims)
    has_patch = _present(inventory, "patch") or _present(inventory, "diff")
    has_validation = _present(inventory, "validation")
    has_benchmark = _present(inventory, "benchmark")
    review_by_id: dict[str, tuple[str, list[str]]] = {
        "claim_support": (
            "contradicted" if contradictions else ("missing_evidence" if missing and claims else ("supported" if claims else "not_applicable")),
            ["Deterministic claim scan completed."],
        ),
        "patch_relevance": (
            "supported" if has_patch else ("missing_evidence" if {"fixed", "applied"} & claim_types else "not_applicable"),
            ["Patch/diff evidence inspected only when supplied."],
        ),
        "validation_relevance": (
            "supported" if has_validation and {"tests_passed", "validation_passed"} & claim_types else (
                "partially_supported" if has_validation else (
                    "missing_evidence" if {"tests_passed", "validation_passed"} & claim_types else "not_applicable"
                )
            ),
            ["Validation artifact presence was compared with validation/test claims."],
        ),
        "benchmark_relevance": (
            "supported" if has_benchmark and "benchmark_passed" in claim_types else (
                "partially_supported" if has_benchmark else (
                    "missing_evidence" if "benchmark_passed" in claim_types else "not_applicable"
                )
            ),
            ["Benchmark artifact presence was compared with benchmark claims."],
        ),
        "missing_evidence": (
            "missing_evidence" if missing else "supported",
            [f"{len(missing)} missing evidence item(s) recorded."],
        ),
        "evidence_freshness": (
            "weakly_supported" if any(item.get("freshness_status") in {"unknown_timestamp", "pre_patch"} for item in freshness) else "supported",
            [item.get("message", "") for item in freshness],
        ),
        "contradiction_detection": (
            "contradicted" if contradictions else "supported",
            [f"{len(contradictions)} contradiction risk(s) recorded."],
        ),
        "confidence_alignment": (
            "weakly_supported" if any(item.get("finding_id") in {"confidence_overstated", "confidence_partially_supported"} for item in confidence) else "supported",
            [item.get("message", "") for item in confidence],
        ),
        "scope_alignment": (
            "weakly_supported" if any(item.get("severity") == "medium" for item in scope) else "supported",
            [item.get("message", "") for item in scope],
        ),
        "human_review_boundary": (
            "supported",
            ["Report is advisory only; human review remains required."],
        ),
    }
    reviews: list[dict[str, Any]] = []
    for item in EVIDENCE_DIMENSIONS:
        dimension_id = item["dimension_id"]
        verdict, findings = review_by_id[dimension_id]
        reviews.append(
            {
                "dimension_id": dimension_id,
                "question": item.get("question", ""),
                "verdict": verdict,
                "findings": findings,
            }
        )
    return reviews


def _human_review_boundary() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "approved": False,
        "safe_to_apply": False,
        "manual_review_required": [
            "Review whether claims are fully supported by supplied artifacts.",
            "Review missing validation, benchmark, patch, freshness, and contradiction findings.",
            "Review production readiness, policy judgment, risk acceptance, and visual/UI evidence manually.",
            "Do not treat this report as approval, rejection, merge authority, or safe-to-apply authority.",
        ],
    }


def _status(
    *,
    blocked_reasons: list[dict[str, str]],
    meaningful: bool,
    warnings: list[dict[str, str]],
) -> str:
    if blocked_reasons:
        return "evidence_quality_report_blocked"
    if not meaningful:
        return "evidence_quality_report_incomplete"
    if warnings:
        return "evidence_quality_report_ready_with_warnings"
    return "evidence_quality_report_ready"


def build_evidence_quality_report_contract(
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
    report_id: str = "evidence-quality-report-contract",
) -> dict[str, Any]:
    """Build a deterministic advisory EVAL.N2 evidence quality report contract."""
    artifact_inventory, texts, blocked_reasons = _load_artifacts(
        repo_root=repo_root,
        patch=patch,
        diff=diff,
        validation=validation,
        benchmark=benchmark,
        final_answer=final_answer,
        mirror_preview=mirror_preview,
        commander_review=commander_review,
        evidence_pack=evidence_pack,
    )
    warnings: list[dict[str, str]] = []
    meaningful = _meaningful(artifact_inventory)
    if not meaningful and not blocked_reasons:
        _add_warning(
            warnings,
            "no_meaningful_evidence_artifacts",
            "No meaningful evidence artifacts were supplied.",
            severity="medium",
        )

    claims = [] if blocked_reasons else _claim_inventory(texts)
    evidence_inventory = _evidence_inventory(artifact_inventory, texts)
    missing = [] if blocked_reasons else _missing_evidence(claims, artifact_inventory, warnings)
    contradictions = [] if blocked_reasons else _contradiction_risks(claims, texts, warnings)
    freshness = [] if blocked_reasons else _freshness_findings(artifact_inventory, warnings)
    confidence = [] if blocked_reasons else _confidence_alignment_findings(claims, texts, artifact_inventory, warnings)
    scope = [] if blocked_reasons else _scope_alignment_findings(claims, artifact_inventory, warnings)
    dimensions = _dimension_reviews(
        claims=claims,
        inventory=artifact_inventory,
        missing=missing,
        contradictions=contradictions,
        freshness=freshness,
        confidence=confidence,
        scope=scope,
    )
    source_artifacts = [
        {
            "artifact_key": item.get("artifact_key", ""),
            "artifact_type": item.get("artifact_type", ""),
            "path": item.get("path", ""),
            "read_status": item.get("read_status", ""),
        }
        for item in artifact_inventory
        if item.get("read_status") == "present"
    ]

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": EVIDENCE_QUALITY_REPORT_GUARDRAIL_NOTE,
        "report_id": str(report_id or "evidence-quality-report-contract"),
        "source_artifacts": source_artifacts,
        "evidence_quality_status": _status(
            blocked_reasons=blocked_reasons,
            meaningful=meaningful,
            warnings=warnings,
        ),
        "artifact_inventory": artifact_inventory,
        "claim_inventory": claims,
        "evidence_inventory": evidence_inventory,
        "dimension_reviews": dimensions,
        "missing_evidence": missing,
        "contradiction_risks": contradictions,
        "freshness_findings": freshness,
        "confidence_alignment_findings": confidence,
        "scope_alignment_findings": scope,
        "human_review_boundary": _human_review_boundary(),
        "warnings": warnings,
        "blocked_reasons": blocked_reasons,
        "boundaries": {
            "report_only": True,
            "artifact_inspection_only": True,
            "deterministic_scanning_only": True,
            "reads_only_explicit_source_artifacts": True,
            "writes_report_artifacts_only": True,
            "advisory_only": True,
        },
        "guardrails": _guardrails(),
        "report_statuses": list(EVIDENCE_QUALITY_REPORT_STATUSES),
        "future_verdicts": list(FUTURE_VERDICTS),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def _render_items(lines: list[str], values: list[Any]) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if not isinstance(value, dict) else f"- `{_md(json.dumps(value, sort_keys=True))}`")
    else:
        lines.append("_None._")
    lines.append("")


def render_evidence_quality_report_contract_markdown(report: dict[str, Any]) -> str:
    """Render an EVAL.N2 evidence quality report contract as Markdown."""
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    lines: list[str] = [
        "# Evidence Quality Report Contract",
        "",
        f"> {report.get('guardrail_note', EVIDENCE_QUALITY_REPORT_GUARDRAIL_NOTE)}",
        "",
        "_Report only: EVAL.N2 inspects explicitly supplied artifacts and grants no approval, rejection, execution, validation, benchmark, model, patch, or scoring-gate authority._",
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


def write_evidence_quality_report_contract(
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
    report_id: str = "evidence-quality-report-contract",
) -> dict[str, Any]:
    """Build and write EVAL.N2 JSON + Markdown report contract artifacts."""
    report = build_evidence_quality_report_contract(
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
    md_path.write_text(render_evidence_quality_report_contract_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
