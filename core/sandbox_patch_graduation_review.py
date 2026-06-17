"""AUTO.1d — Sandbox Patch Graduation Review (review-only).

Consumes a sandbox patch candidate evaluation artifact (the AUTO.1c report) and
decides whether the candidate is eligible for human review. Passing in a sandbox
is not the same as being safe to graduate: a candidate may be recommended for
human review, but it may not approve itself.

This module is review-only. It reads a parsed evaluation record (a plain dict)
and emits a deterministic graduation decision plus an operator-readable report.
It never applies patches, never runs validation, never runs a benchmark check,
never calls a model, never writes to the real repo, and never pushes, merges,
opens a PR, or contacts a remote git host / chat service / external automation.
Human approval is required before any real repo change.
"""
from __future__ import annotations

from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "sandbox_patch_graduation_review"

#: The source artifact kind AUTO.1d knows how to read (the AUTO.1c report).
EXPECTED_SOURCE_KIND = "sandbox_patch_candidate_evaluation"

#: Deterministic graduation verdicts.
GRADUATION_VERDICTS: tuple[str, ...] = (
    "eligible_for_human_review",
    "needs_more_validation",
    "blocked_by_safety",
    "not_reviewable",
)

#: Recommended next steps (a human always acts on these).
RECOMMENDED_NEXT_STEPS: tuple[str, ...] = (
    "prepare_human_review_packet",
    "request_more_validation",
    "reject_candidate",
    "narrow_patch_scope",
    "manual_review_required",
)

#: How each AUTO.1c source verdict is categorised for the graduation decision.
_SOURCE_VERDICT_CATEGORIES: dict[str, str] = {
    "patch_candidate_passed": "pass",
    "validation_skipped": "conditional",
    "patch_candidate_failed_validation": "not_reviewable",
    "patch_candidate_failed_apply": "not_reviewable",
    "sandbox_setup_failed": "not_reviewable",
    "patch_candidate_rejected_by_safety": "blocked",
    "blocked_by_contract": "blocked",
}

#: Path segments / file prefixes that must never be touched (defense in depth on
#: top of whatever the source evaluation already recorded).
_FORBIDDEN_PATH_SEGMENTS: tuple[str, ...] = (
    ".git",
    ".agent",
    "secrets",
    "secret",
    "node_modules",
    "__pycache__",
)
_FORBIDDEN_PATH_PREFIXES: tuple[str, ...] = (".env",)

GRADUATION_GUARDRAIL_NOTE = (
    "Sandbox Patch Graduation Review is review-only. It reads a sandbox patch "
    "candidate evaluation and decides whether the candidate is eligible for "
    "human review. Passing in a sandbox is not the same as being safe to "
    "graduate: a candidate may be recommended for human review, but it may not "
    "approve itself. This review does not apply patches, run validation, run a "
    "benchmark check, call a model, write to the real repo, push, merge, open a "
    "PR, or contact a remote git host / chat service / external automation. "
    "Human approval is required before any real repo change."
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def source_verdict_category(verdict: Any) -> str:
    """Categorise a source evaluation verdict.

    Returns one of ``pass`` / ``conditional`` / ``not_reviewable`` / ``blocked``
    / ``unknown``.
    """
    return _SOURCE_VERDICT_CATEGORIES.get(str(verdict or ""), "unknown")


def _is_forbidden_path(path: Any) -> str:
    """Return why a touched path is forbidden, or ``""`` if it is acceptable."""
    raw = str(path or "").strip()
    if not raw:
        return ""
    normalized = raw.replace("\\", "/")
    if normalized.startswith("/") or (len(raw) >= 2 and raw[1] == ":"):
        return f"touches an absolute path that escapes the repo: {raw}"
    parts = [part for part in normalized.split("/") if part]
    if ".." in parts:
        return f"touches a parent-traversal path that escapes the repo: {raw}"
    for part in parts:
        low = part.lower()
        if low in _FORBIDDEN_PATH_SEGMENTS:
            return f"touches a protected path segment ({part}): {raw}"
        for prefix in _FORBIDDEN_PATH_PREFIXES:
            if low == prefix or low.startswith(prefix + "."):
                return f"touches a protected file ({part}): {raw}"
    return ""


def _has_forbidden_touched_path(ev: dict[str, Any]) -> bool:
    if any(_is_forbidden_path(p) for p in (ev.get("patch_touched_paths") or [])):
        return True
    safety = ev.get("patch_safety") or {}
    return bool(safety.get("rejected_paths"))


def _has_hard_safety_breach(ev: dict[str, Any]) -> bool:
    return (
        ev.get("real_repo_modified") is True
        or ev.get("patch_applied_to_real_repo") is True
        or ev.get("sandbox_only") is False
        or ev.get("side_effects_sandbox_only") is False
        or ev.get("human_approval_required") is False
        or ev.get("self_approval_allowed") is True
        or ev.get("eligible_for_auto_merge") is True
        or ev.get("patch_generated") is True
        or _has_forbidden_touched_path(ev)
    )


def _suspicious_side_effects(ev: dict[str, Any]) -> list[str]:
    """Non-generated sandbox effects that should slow graduation down."""
    notes: list[str] = []
    validation = ev.get("validation_side_effects") or {}
    for change in ("created", "modified", "deleted"):
        for entry in validation.get(change) or []:
            if not isinstance(entry, dict):
                continue
            if entry.get("known_generated_or_noisy") is True:
                continue
            notes.append(
                f"validation {change} a non-generated file in the sandbox: "
                f"{entry.get('path', '')}"
            )
    patch = ev.get("patch_side_effects") or {}
    for change in ("created", "modified", "deleted"):
        for entry in patch.get(change) or []:
            if isinstance(entry, dict) and entry.get("inside_patch_touched_scope") is False:
                notes.append(
                    f"patch {change} a file outside its declared scope: "
                    f"{entry.get('path', '')}"
                )
    return notes


def _noisy_side_effects(ev: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for key, label in (("validation_side_effects", "validation"), ("patch_side_effects", "patch")):
        block = ev.get(key) or {}
        for change in ("created", "modified", "deleted"):
            for entry in block.get(change) or []:
                if isinstance(entry, dict) and entry.get("known_generated_or_noisy") is True:
                    notes.append(f"{label} {change} a generated/noisy file: {entry.get('path', '')}")
    return notes


def _side_effect_summaries(ev: dict[str, Any]) -> dict[str, dict[str, int]]:
    def summarize(key: str) -> dict[str, int]:
        summary = (ev.get(key) or {}).get("summary") or {}
        return {
            "created": _int(summary.get("created")),
            "modified": _int(summary.get("modified")),
            "deleted": _int(summary.get("deleted")),
        }

    return {"patch": summarize("patch_side_effects"), "validation": summarize("validation_side_effects")}


# ── Deterministic checks ──────────────────────────────────────────────────────

def _evaluate_checks(
    ev: dict[str, Any],
) -> tuple[list[dict[str, str]], list[str], list[str], dict[str, Any]]:
    checks: list[dict[str, str]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    def add(check: str, result: str, reason: str) -> None:
        checks.append({"check": check, "result": result, "reason": reason})

    verdict = str(ev.get("verdict", ""))
    category = source_verdict_category(verdict)

    # 1. source verdict is acceptable
    if category == "pass":
        add("source_verdict_acceptable", "pass", f"source verdict is {verdict!r}")
    elif category == "conditional":
        add("source_verdict_acceptable", "warn", f"source verdict is {verdict!r} (validation was skipped)")
        warnings.append(f"source evaluation skipped validation ({verdict})")
    elif category == "blocked":
        add("source_verdict_acceptable", "fail", f"source verdict is {verdict!r}")
        blockers.append(f"source evaluation verdict {verdict} is a safety / contract block")
    elif category == "not_reviewable":
        add("source_verdict_acceptable", "fail", f"source verdict is {verdict!r}; candidate is not in a reviewable state")
    else:
        add("source_verdict_acceptable", "fail", f"source verdict {verdict!r} is unknown")

    # 2. real repo unchanged
    real_repo_issues: list[str] = []
    if ev.get("real_repo_modified") is True:
        real_repo_issues.append("source evaluation reports the real repo was modified")
    if ev.get("patch_applied_to_real_repo") is True:
        real_repo_issues.append("source evaluation reports the patch was written to the real repo")
    if real_repo_issues:
        add("real_repo_unchanged", "fail", "; ".join(real_repo_issues))
        blockers.extend(real_repo_issues)
    else:
        add("real_repo_unchanged", "pass", "the real repo was not modified")

    # 3. sandbox-only
    sandbox_issues: list[str] = []
    if ev.get("sandbox_only") is False:
        sandbox_issues.append("source evaluation was not sandbox-only")
    if ev.get("side_effects_sandbox_only") is False:
        sandbox_issues.append("source evaluation side effects were not sandbox-only")
    if sandbox_issues:
        add("sandbox_only", "fail", "; ".join(sandbox_issues))
        blockers.extend(sandbox_issues)
    else:
        add("sandbox_only", "pass", "all reported effects were sandbox-only")

    # 4. human gate preserved
    gate_issues: list[str] = []
    if ev.get("human_approval_required") is False:
        gate_issues.append("source evaluation does not require human approval")
    if ev.get("self_approval_allowed") is True:
        gate_issues.append("source evaluation allowed self-approval")
    if ev.get("eligible_for_auto_merge") is True:
        gate_issues.append("source evaluation is marked eligible for auto-merge")
    if gate_issues:
        add("human_gate_preserved", "fail", "; ".join(gate_issues))
        blockers.extend(gate_issues)
    else:
        add("human_gate_preserved", "pass", "human gate intact; no self-approval and no auto-merge")

    # 5. patch safety
    safety = ev.get("patch_safety") or {}
    safety_issues: list[str] = []
    for entry in safety.get("rejected_paths") or []:
        if isinstance(entry, dict):
            path, reason = entry.get("path", ""), entry.get("reason", "")
        else:
            path, reason = str(entry), ""
        safety_issues.append(f"source evaluation rejected path {path} ({reason})".strip())
    for path in ev.get("patch_touched_paths") or []:
        why = _is_forbidden_path(path)
        if why:
            safety_issues.append(f"patch {why}")
    if ev.get("patch_generated") is True:
        safety_issues.append("source evaluation reports a generated patch; AUTO.1d only reviews provided candidates")
    supplied = ev.get("patch_candidate_supplied")
    too_large = bool(safety.get("too_large"))
    if safety_issues:
        add("patch_safety", "fail", "; ".join(safety_issues))
        blockers.extend(safety_issues)
    elif supplied is False:
        add("patch_safety", "fail", "no patch candidate was supplied to the evaluation")
    elif too_large:
        add("patch_safety", "warn", "the candidate is large; its scope should be narrowed before review")
        warnings.append("the candidate is large; a human reviewer should consider narrowing its scope")
    else:
        add("patch_safety", "pass", "no forbidden paths; a provided candidate within a reviewable size")

    # 6. validation
    validation_status = str(ev.get("validation_status", ""))
    if category == "pass":
        add("validation", "pass", "declared validation passed inside the sandbox")
    elif category == "conditional":
        add("validation", "warn", "no validation was declared; more validation is needed before review")
    elif verdict == "patch_candidate_failed_validation":
        add("validation", "fail", "declared validation failed inside the sandbox")
    else:
        add("validation", "n/a", f"validation status: {validation_status or 'unknown'}")

    # 7. side effects
    suspicious = _suspicious_side_effects(ev)
    noisy = _noisy_side_effects(ev)
    if real_repo_issues:
        add("side_effects", "fail", "a real repo effect was reported by the source evaluation")
    elif suspicious:
        add("side_effects", "warn", "; ".join(suspicious))
        warnings.extend(suspicious)
    elif noisy:
        add("side_effects", "warn", "only generated / noisy sandbox side effects were reported")
        warnings.extend(noisy)
    else:
        add("side_effects", "pass", "no suspicious sandbox side effects")

    # 8. reviewability
    touched = ev.get("patch_touched_paths") or []
    if not touched and category in ("pass", "conditional"):
        add("reviewability", "fail", "no touched files are recorded; there is nothing to review")
    else:
        add("reviewability", "pass", f"{len(touched)} touched file(s) recorded for human inspection")

    flags = {"too_large": too_large, "supplied": supplied, "suspicious": bool(suspicious)}
    return checks, blockers, warnings, flags


def _decide_verdict(
    category: str, blockers: list[str], flags: dict[str, Any], ev: dict[str, Any]
) -> str:
    if blockers:
        return "blocked_by_safety"
    if category == "blocked":
        return "blocked_by_safety"
    if category == "not_reviewable":
        return "not_reviewable"
    if category == "conditional":
        return "needs_more_validation"
    if category == "pass":
        if flags.get("suspicious"):
            return "needs_more_validation"
        touched = ev.get("patch_touched_paths") or []
        if not touched or flags.get("supplied") is False:
            return "not_reviewable"
        return "eligible_for_human_review"
    return "not_reviewable"


def _recommend_next_step(verdict_out: str, flags: dict[str, Any], ev: dict[str, Any]) -> str:
    if verdict_out == "eligible_for_human_review":
        return "prepare_human_review_packet"
    if verdict_out == "needs_more_validation":
        return "request_more_validation"
    if verdict_out == "blocked_by_safety":
        if flags.get("too_large") and not _has_hard_safety_breach(ev):
            return "narrow_patch_scope"
        return "reject_candidate"
    # not_reviewable
    if str(ev.get("verdict", "")) == "patch_candidate_failed_validation":
        return "reject_candidate"
    return "manual_review_required"


# ── Record assembly ───────────────────────────────────────────────────────────

def _boundaries() -> dict[str, bool]:
    return {
        "applies_patches": False,
        "runs_validation": False,
        "runs_benchmark_check": False,
        "calls_models": False,
        "modifies_real_repo": False,
        "pushes_merges_or_opens_pr": False,
        "contacts_remote_or_chat_or_automation": False,
        "allows_self_approval": False,
    }


def _base_record(
    *,
    review_id: str,
    created_at: str,
    source_evaluation_path: str,
    trial_id: str,
    source_verdict: str,
    ev: dict[str, Any] | None,
) -> dict[str, Any]:
    source = ev or {}
    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": GRADUATION_GUARDRAIL_NOTE,
        "review_id": str(review_id or ""),
        "created_at": str(created_at or ""),
        "source_evaluation_path": str(source_evaluation_path or ""),
        "source_report_kind": str(source.get("report_kind", "")),
        "trial_id": str(trial_id or ""),
        "source_verdict": str(source_verdict or ""),
        "graduation_verdict": "",
        "recommended_next_step": "",
        # human review packet context (echoed from the source, read-only)
        "source_patch_touched_paths": list(source.get("patch_touched_paths") or []),
        "source_patch_changed_lines": _int(source.get("patch_changed_lines")),
        "source_patch_file_count": _int(source.get("patch_file_count")),
        "source_validation_status": str(source.get("validation_status", "")),
        "source_side_effects": _side_effect_summaries(source),
        "checks": [],
        "blockers": [],
        "warnings": [],
        # ── AUTO.1d guardrail booleans (this tool does none of these) ──
        "human_review_required": True,
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
        "real_repo_modified": False,
        "patch_applied_to_real_repo": False,
        "push_performed": False,
        "merge_performed": False,
        "model_call_performed": False,
        "validation_run_by_tool": False,
        "benchmark_run_by_tool": False,
        "worker_launch_performed": False,
        "boundaries": _boundaries(),
    }


def _malformed_reason(evaluation: Any) -> str:
    if not isinstance(evaluation, dict):
        return "source artifact is missing or is not a JSON object"
    kind = str(evaluation.get("report_kind", ""))
    if kind != EXPECTED_SOURCE_KIND:
        return (
            "source artifact is not a sandbox patch candidate evaluation "
            f"(report_kind={kind or 'missing'!r})"
        )
    if not str(evaluation.get("verdict", "")).strip():
        return "source artifact has no verdict to review"
    return ""


def build_graduation_review(
    *,
    evaluation: Any,
    source_evaluation_path: str = "",
    review_id: str = "",
    created_at: str = "",
    trial_id: str = "",
) -> dict[str, Any]:
    """Decide whether a sandbox patch candidate is eligible for human review.

    ``evaluation`` is the parsed AUTO.1c evaluation record (a dict), or ``None``
    when the artifact could not be read. This function never reads or writes any
    file and never runs anything — it is a pure decision over the record.
    """
    ev = evaluation if isinstance(evaluation, dict) else None
    resolved_trial = str(trial_id or (ev.get("trial_id") if ev else "") or "").strip()
    source_verdict = str(ev.get("verdict", "")) if ev else ""

    record = _base_record(
        review_id=review_id,
        created_at=created_at,
        source_evaluation_path=source_evaluation_path,
        trial_id=resolved_trial or str(review_id or ""),
        source_verdict=source_verdict,
        ev=ev,
    )

    malformed = _malformed_reason(evaluation)
    if malformed:
        record["graduation_verdict"] = "not_reviewable"
        record["recommended_next_step"] = "manual_review_required"
        record["checks"] = [
            {"check": "source_artifact_parseable", "result": "fail", "reason": malformed}
        ]
        record["blockers"] = [malformed]
        return record

    assert ev is not None  # guaranteed by _malformed_reason
    checks, blockers, warnings, flags = _evaluate_checks(ev)
    category = source_verdict_category(source_verdict)
    verdict_out = _decide_verdict(category, blockers, flags, ev)
    next_step = _recommend_next_step(verdict_out, flags, ev)

    record["checks"] = checks
    record["blockers"] = blockers
    record["warnings"] = warnings
    record["graduation_verdict"] = verdict_out
    record["recommended_next_step"] = next_step
    return record


# ── Markdown rendering ────────────────────────────────────────────────────────

def render_graduation_review_markdown(record: dict[str, Any]) -> str:
    """Render the graduation review record as operator-readable Markdown."""
    lines: list[str] = [
        "# Sandbox Patch Graduation Review",
        "",
        f"> {record.get('guardrail_note', GRADUATION_GUARDRAIL_NOTE)}",
        "",
        "_Review only: this gate reads a sandbox patch candidate evaluation and "
        "decides whether the candidate is eligible for human review. It applies "
        "nothing, runs nothing, and changes nothing in the real repo. A candidate "
        "may be recommended for human review, but it may not approve itself._",
        "",
        "---",
        "",
        "## Summary",
        "",
    ]
    lines.append(f"- **Trial id:** `{_md(record.get('trial_id') or '(none)')}`")
    lines.append(
        f"- **Source evaluation:** `{_md(record.get('source_evaluation_path') or '(inline)')}` "
        f"(verdict `{_md(record.get('source_verdict') or '(none)')}`)"
    )
    lines.append(f"- **Graduation verdict:** `{_md(record.get('graduation_verdict') or '')}`")
    lines.append(f"- **Recommended next step:** `{_md(record.get('recommended_next_step') or '')}`")
    lines.append(f"- **Human review required:** {str(record.get('human_review_required', True)).lower()}")
    lines.append("")

    # Graduation Checks
    lines += ["## Graduation Checks", "", "| Check | Result | Reason |", "|---|---|---|"]
    for check in record.get("checks") or []:
        lines.append(
            f"| {_md(check.get('check'))} | {_md(check.get('result'))} | {_md(check.get('reason'))} |"
        )
    lines.append("")

    # Blockers
    lines += ["## Blockers", ""]
    blockers = record.get("blockers") or []
    if blockers:
        for blocker in blockers:
            lines.append(f"- {_md(blocker)}")
    else:
        lines.append("_None._")
    lines.append("")

    # Warnings
    lines += ["## Warnings", ""]
    warnings = record.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- {_md(warning)}")
    else:
        lines.append("_None._")
    lines.append("")

    # Human Review Packet
    lines += ["## Human Review Packet", ""]
    touched = record.get("source_patch_touched_paths") or []
    lines.append(
        "- **Touched files:** "
        + (", ".join(f"`{_md(path)}`" for path in touched) or "none")
    )
    lines.append(
        f"- **Patch size:** {record.get('source_patch_changed_lines', 0)} changed lines "
        f"across {record.get('source_patch_file_count', 0)} files"
    )
    lines.append(f"- **Validation status:** {_md(record.get('source_validation_status') or 'unknown')}")
    side = record.get("source_side_effects") or {}
    patch_se = side.get("patch") or {}
    validation_se = side.get("validation") or {}
    lines.append(
        "- **Side effects:** patch ("
        f"created {patch_se.get('created', 0)}, modified {patch_se.get('modified', 0)}, "
        f"deleted {patch_se.get('deleted', 0)}); validation ("
        f"created {validation_se.get('created', 0)}, modified {validation_se.get('modified', 0)}, "
        f"deleted {validation_se.get('deleted', 0)})"
    )
    lines.append(
        "- **Inspect manually:** the touched files listed above, the sandbox validation "
        "result, and any reported side effects before approving any real repo change."
    )
    lines.append("")

    # Boundaries
    lines += ["## Boundaries", ""]
    lines += [
        "- This review does not apply patches.",
        "- This review does not run validation.",
        "- This review does not run a benchmark check.",
        "- This review does not call models.",
        "- This review does not modify the real repo.",
        "- This review does not push, merge, open PRs, or contact a remote git host, "
        "chat app, or external automation.",
        "- Human approval is required before any real repo change.",
        "",
    ]
    return "\n".join(lines) + "\n"
