"""AUTO.2b — GitHub Remote PR Safety Contract (report-only).

Reads one upstream evidence artifact — an AUTO.1e sandbox self-evolution evidence
pack or an AUTO.2a evidence summary contract — and shapes a contract describing
what must be true before a *future* system may draft a remote pull request. It is
meant to prepare a future remote-PR workflow without building any part of it yet.

AUTO.2b defines the safety contract. It does not contact a remote git host, create
branches, push commits, open PRs, merge anything, call Webhooks, make any network
request, call models, apply patches, run validation or a benchmark check, write to
the real repo, or contact Telegram / N8N. A future PR is never merge authority;
human review and branch protection remain required.

This module is stdlib-only and pure: it reads an already-parsed artifact record
(a plain dict) and returns a deterministic contract record plus Markdown. It reads
no files and never mutates the source artifact.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "github_pr_safety_contract"

#: Upstream final verdicts this contract recognises (consumed, not produced here).
SOURCE_FINAL_VERDICTS: tuple[str, ...] = (
    "ready_for_human_review",
    "needs_more_validation",
    "blocked",
    "incomplete_pack",
)

#: Source-artifact kinds this contract can normalise.
SOURCE_KIND_EVIDENCE_PACK = "self_evolution_evidence_pack"
SOURCE_KIND_TELEGRAM_CONTRACT = "telegram_evidence_contract"
SOURCE_KIND_UNKNOWN = "unknown"

#: Informational future actions a human-driven workflow could later take.
ALLOWED_FUTURE_ACTIONS: tuple[str, ...] = (
    "prepare_draft_pr_after_human_review",
    "request_more_validation",
    "reject_candidate",
    "keep_local_only",
)

#: Actions this contract forbids being taken automatically on this evidence.
FORBIDDEN_ACTIONS: tuple[str, ...] = (
    "push_to_main",
    "force_push",
    "open_pr_without_human_review",
    "merge_pr",
    "enable_auto_merge",
    "bypass_branch_protection",
    "apply_patch_to_real_repo",
    "launch_worker",
    "call_model",
    "contact_remote_service",
)

#: Source guardrail booleans that MUST be false; true means a hard breach (rule 4).
_BREACH_BOOL_SHOULD_BE_FALSE: tuple[tuple[str, str], ...] = (
    ("self_approval_allowed", "allows self-approval"),
    ("eligible_for_auto_merge", "marks the candidate eligible for auto-merge"),
    ("real_repo_modified", "reports the real repo was modified unexpectedly"),
    ("patch_applied_to_real_repo", "reports a patch was applied to the real repo by automation"),
    ("push_performed", "reports a push was performed"),
    ("merge_performed", "reports a merge was performed"),
    ("model_call_performed", "reports a model call was performed unexpectedly"),
    ("worker_launch_performed", "reports a worker was launched"),
)

#: PR-readiness status values.
STATUS_DRAFT_ALLOWED = "draft_pr_allowed_after_human_review"
STATUS_NEEDS_MORE_VALIDATION = "needs_more_validation"
STATUS_BLOCKED = "blocked"
STATUS_INCOMPLETE = "incomplete"
STATUS_NOT_READY = "not_ready"

#: Report artifact filenames.
JSON_NAME = "github_pr_safety_contract.json"
MD_NAME = "github_pr_safety_contract.md"

GITHUB_PR_SAFETY_GUARDRAIL_NOTE = (
    "GitHub Remote PR Safety Contract is report-only: it reads an AUTO.1e evidence "
    "pack or an AUTO.2a evidence summary and defines what must be true before a future "
    "system may draft a remote PR. It does not contact GitHub, create branches, push "
    "commits, open PRs, merge anything, call Webhooks, make any network request, call "
    "models, apply patches, run validation or a benchmark check, write to the real repo, "
    "or contact Telegram / N8N. A future PR is not merge authority; human review and "
    "branch protection remain required."
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _str(value: Any, default: str = "") -> str:
    return str(value) if value is not None else default


def _str_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _dedupe(items: list[str]) -> list[str]:
    """Preserve order, drop duplicates (deterministic)."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ── Source detection + normalisation ───────────────────────────────────────────

def detect_source_kind(artifact: dict[str, Any]) -> str:
    """Best-effort detect whether the source is an AUTO.1e pack or AUTO.2a contract."""
    kind = _str(artifact.get("report_kind")).strip()
    if kind == "sandbox_self_evolution_evidence_pack":
        return SOURCE_KIND_EVIDENCE_PACK
    if kind == "telegram_evidence_contract":
        return SOURCE_KIND_TELEGRAM_CONTRACT
    # Structural sniffing when report_kind is absent or unexpected.
    if "human_review_packet" in artifact or "source_artifacts" in artifact:
        return SOURCE_KIND_EVIDENCE_PACK
    if "telegram_message" in artifact or "approval_options" in artifact:
        return SOURCE_KIND_TELEGRAM_CONTRACT
    return SOURCE_KIND_UNKNOWN


def _normalise_source(artifact: dict[str, Any], source_kind: str) -> dict[str, Any]:
    """Project either supported source shape onto one common record."""
    final_verdict = _str(artifact.get("final_verdict")).strip()
    if final_verdict not in SOURCE_FINAL_VERDICTS:
        final_verdict = "incomplete_pack"

    risk = artifact.get("risk_summary") if isinstance(artifact.get("risk_summary"), dict) else {}

    if source_kind == SOURCE_KIND_TELEGRAM_CONTRACT:
        flags = artifact.get("guardrails") if isinstance(artifact.get("guardrails"), dict) else {}
        source_blockers = _str_list(artifact.get("send_blockers"))
        links = [link for link in (artifact.get("evidence_links") or []) if isinstance(link, dict)]
        touched_files: list[str] = []
        validation_status = _str(risk.get("validation"), "(unknown)")
    else:
        flags = artifact
        source_blockers = _str_list(artifact.get("blockers"))
        artifacts = artifact.get("source_artifacts")
        links = [a for a in artifacts if isinstance(a, dict)] if isinstance(artifacts, list) else []
        packet = artifact.get("human_review_packet") if isinstance(artifact.get("human_review_packet"), dict) else {}
        touched_files = _str_list(packet.get("patch_touched_files"))
        validation_status = _str(packet.get("validation_status")) or _str(risk.get("validation"), "(unknown)")

    return {
        "final_verdict": final_verdict,
        "trial_id": _str(artifact.get("trial_id")).strip(),
        "recommended_next_step": _str(artifact.get("recommended_next_step")).strip(),
        "risk": risk,
        "flags": flags,
        "source_blockers": source_blockers,
        "warnings": _str_list(artifact.get("warnings")),
        "links": links,
        "touched_files": touched_files,
        "validation_status": validation_status,
    }


def _detect_hard_breaches(flags: dict[str, Any]) -> list[str]:
    """Return guardrail breach descriptions found in the source (empty if clean)."""
    breaches: list[str] = []
    for field, phrase in _BREACH_BOOL_SHOULD_BE_FALSE:
        if flags.get(field) is True:
            breaches.append(f"the source {phrase} ({field})")
    if flags.get("human_review_required") is False:
        breaches.append("the source does not require human review (human_review_required)")
    return _dedupe(breaches)


# ── Decision rules ──────────────────────────────────────────────────────────────

def _pr_readiness_status(
    *, final_verdict: str, breaches: list[str], source_blockers: list[str]
) -> str:
    if breaches:
        return STATUS_BLOCKED
    if final_verdict == "ready_for_human_review" and not source_blockers:
        return STATUS_DRAFT_ALLOWED
    if final_verdict == "needs_more_validation":
        return STATUS_NEEDS_MORE_VALIDATION
    if final_verdict == "blocked" or source_blockers:
        return STATUS_BLOCKED
    if final_verdict == "incomplete_pack":
        return STATUS_INCOMPLETE
    return STATUS_NOT_READY


def _pr_blockers(
    *,
    final_verdict: str,
    breaches: list[str],
    source_blockers: list[str],
    source_present: bool,
) -> list[str]:
    verdict_reasons: list[str] = []
    if not source_present:
        verdict_reasons.append("the source artifact is missing or malformed")
    if final_verdict == "needs_more_validation":
        verdict_reasons.append("more validation is required before a draft PR may be prepared")
    elif final_verdict == "blocked":
        verdict_reasons.append("the source verdict is blocked")
    elif final_verdict == "incomplete_pack":
        verdict_reasons.append("the source artifact is incomplete")
    return _dedupe(breaches + source_blockers + verdict_reasons)


def _recommended_future_action(
    *, final_verdict: str, breaches: list[str], source_blockers: list[str]
) -> str:
    if breaches:
        return "reject_candidate"
    if final_verdict == "ready_for_human_review" and not source_blockers:
        return "prepare_draft_pr_after_human_review"
    if final_verdict == "needs_more_validation":
        return "request_more_validation"
    if final_verdict == "blocked" or source_blockers:
        return "reject_candidate"
    return "keep_local_only"


def _allowed_future_actions(emphasis: str) -> list[str]:
    """Full set, reordered so the emphasised action is first (informational only)."""
    if emphasis in ALLOWED_FUTURE_ACTIONS:
        return [emphasis] + [a for a in ALLOWED_FUTURE_ACTIONS if a != emphasis]
    return list(ALLOWED_FUTURE_ACTIONS)


# ── Static contract content ─────────────────────────────────────────────────────

def _required_checks() -> list[str]:
    return [
        "Human review of the candidate is complete and recorded before any PR is drafted.",
        "A link or path to the evidence pack (AUTO.1e) or evidence summary (AUTO.2a) is attached.",
        "Validation evidence is present and validation was not skipped.",
        "Branch protection is enabled on the target branch.",
        "Required status checks are configured and must pass.",
        "No direct push to the protected main branch.",
        "Auto-merge is disabled; a merge requires explicit human action.",
        "Rollback notes or a rejection path is documented.",
    ]


def _required_branch_protection() -> list[str]:
    return [
        "Protect the main branch and disallow direct pushes.",
        "Require pull-request review before a merge.",
        "Require status checks to pass before a merge.",
        "Disable auto-merge; require an explicit human merge.",
        "Disallow force-pushes and deletion of protected branches.",
        "Restrict who may merge into the protected branch.",
    ]


def _required_human_checks() -> list[str]:
    return [
        "Open and read the touched files; confirm they match the intended scope.",
        "Confirm the sandbox validation result and that validation was not skipped.",
        "Confirm no real repo change, push, or merge has occurred from the trial.",
        "Confirm branch protection and required checks are configured on the target branch.",
        "Author and review any future PR by hand; a future PR is not merge authority.",
    ]


def _risk_summary(risk: dict[str, Any]) -> dict[str, str]:
    return {
        "safety": _str(risk.get("safety"), "(unknown)"),
        "scope": _str(risk.get("scope"), "(unknown)"),
        "validation": _str(risk.get("validation"), "(unknown)"),
        "side_effects": _str(risk.get("side_effects"), "(unknown)"),
        "budget_or_model_use": _str(risk.get("budget_or_model_use"), "(unknown)"),
        "human_gate": _str(risk.get("human_gate"), "(unknown)"),
        "merge_authority": (
            "A future PR is not merge authority; human review, validation evidence, and "
            "branch protection remain required before any merge."
        ),
    }


def _evidence_links(links: list[dict[str, Any]], source_kind: str, source_artifact: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if source_artifact:
        if source_kind == SOURCE_KIND_TELEGRAM_CONTRACT:
            label = "Evidence summary (AUTO.2a)"
        elif source_kind == SOURCE_KIND_EVIDENCE_PACK:
            label = "Evidence pack (AUTO.1e)"
        else:
            label = "Source artifact"
        out.append({"label": label, "path": str(source_artifact)})
    for link in links:
        out.append({"label": _str(link.get("label"), "Artifact"), "path": _str(link.get("path"))})
    return out


def _guardrails() -> dict[str, bool]:
    """The contract's own guardrails — this tool performs none of these actions."""
    return {
        "human_review_required": True,
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
        "push_performed": False,
        "merge_performed": False,
        "pr_created": False,
        "branch_created": False,
        "github_contacted": False,
        "network_call_performed": False,
        "model_call_performed": False,
        "worker_launch_performed": False,
        "patch_applied_to_real_repo": False,
        "validation_run_by_tool": False,
        "benchmark_run_by_tool": False,
    }


def _boundaries() -> dict[str, bool]:
    return {
        "defines_pr_safety_contract_only": True,
        "contacts_remote_host": False,
        "creates_branches": False,
        "pushes_commits": False,
        "opens_or_merges_pr": False,
        "calls_callbacks": False,
        "makes_network_call": False,
        "calls_models": False,
        "applies_patches": False,
        "runs_validation_or_benchmarks": False,
        "is_merge_authority": False,
    }


# ── Contract assembly ──────────────────────────────────────────────────────────

def build_github_pr_safety_contract(
    *,
    artifact: Any,
    contract_id: str = "",
    created_at: str = "",
    source_artifact: str = "",
) -> dict[str, Any]:
    """Shape an upstream evidence artifact into a deterministic PR-safety contract.

    Pure: never mutates ``artifact`` and never runs or contacts anything. A missing
    or malformed artifact yields a not-ready contract that says so.
    """
    source_present = isinstance(artifact, dict) and bool(artifact)
    data = artifact if isinstance(artifact, dict) else {}
    source_kind = detect_source_kind(data) if data else SOURCE_KIND_UNKNOWN

    norm = _normalise_source(data, source_kind)
    final_verdict = norm["final_verdict"]
    breaches = _detect_hard_breaches(norm["flags"])
    source_blockers = norm["source_blockers"]

    status = _pr_readiness_status(
        final_verdict=final_verdict, breaches=breaches, source_blockers=source_blockers
    )
    blockers = _pr_blockers(
        final_verdict=final_verdict,
        breaches=breaches,
        source_blockers=source_blockers,
        source_present=source_present,
    )

    is_pr_draft_allowed_in_future = status == STATUS_DRAFT_ALLOWED
    # Rules 1 & 3: a merge / auto-merge is never allowed on this evidence.
    is_merge_allowed = False
    is_auto_merge_allowed = False

    emphasis = _recommended_future_action(
        final_verdict=final_verdict, breaches=breaches, source_blockers=source_blockers
    )

    warnings = list(norm["warnings"])
    if source_kind == SOURCE_KIND_UNKNOWN:
        warnings = _dedupe(warnings + ["source kind could not be determined; treating as not ready"])

    pr_readiness = {
        "status": status,
        "draft_pr_allowed_in_future": is_pr_draft_allowed_in_future,
        "merge_allowed": is_merge_allowed,
        "auto_merge_allowed": is_auto_merge_allowed,
        "recommended_future_action": emphasis,
        "reasons": list(blockers)
        if blockers
        else ["source verdict is ready_for_human_review; a draft PR may be prepared only after human review"],
    }

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": GITHUB_PR_SAFETY_GUARDRAIL_NOTE,
        "contract_id": str(contract_id or ""),
        "created_at": str(created_at or ""),
        "source_artifact": str(source_artifact or ""),
        "source_kind": source_kind,
        "trial_id": norm["trial_id"],
        "final_verdict": final_verdict,
        "recommended_next_step": norm["recommended_next_step"],
        "pr_readiness": pr_readiness,
        "required_checks": _required_checks(),
        "required_branch_protection": _required_branch_protection(),
        "required_human_checks": _required_human_checks(),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "allowed_future_actions": _allowed_future_actions(emphasis),
        "risk_summary": _risk_summary(norm["risk"]),
        "evidence_links": _evidence_links(norm["links"], source_kind, source_artifact),
        "guardrails": _guardrails(),
        "is_pr_draft_allowed_in_future": is_pr_draft_allowed_in_future,
        "is_merge_allowed": is_merge_allowed,
        "is_auto_merge_allowed": is_auto_merge_allowed,
        "blockers": blockers,
        "warnings": warnings,
        "boundaries": _boundaries(),
    }


# ── Markdown rendering ──────────────────────────────────────────────────────────

def render_github_pr_safety_contract_markdown(contract: dict[str, Any]) -> str:
    """Render a contract record as one operator-readable Markdown report."""
    pr = contract.get("pr_readiness") or {}
    lines: list[str] = [
        "# GitHub Remote PR Safety Contract",
        "",
        f"> {contract.get('guardrail_note', GITHUB_PR_SAFETY_GUARDRAIL_NOTE)}",
        "",
        "_Report only: AUTO.2b defines what must be true before a future system may draft "
        "a remote PR from an AUTO.1e evidence pack or AUTO.2a evidence summary. It contacts "
        "nothing, creates nothing, and changes nothing. A future PR is not merge authority._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Contract id:** `{_md(contract.get('contract_id') or '(none)')}`",
        f"- **Created at:** `{_md(contract.get('created_at') or '(none)')}`",
        f"- **Source artifact:** `{_md(contract.get('source_artifact') or '(none)')}`",
        f"- **Source kind:** `{_md(contract.get('source_kind') or '(unknown)')}`",
        f"- **Trial id:** `{_md(contract.get('trial_id') or '(none)')}`",
        f"- **Final verdict:** `{_md(contract.get('final_verdict') or '')}`",
        f"- **Recommended next step:** `{_md(contract.get('recommended_next_step') or '(none)')}`",
        "",
        "## PR Readiness",
        "",
        f"- **Status:** `{_md(pr.get('status') or '')}`",
        f"- **Draft PR allowed in future:** {str(bool(contract.get('is_pr_draft_allowed_in_future'))).lower()}",
        f"- **Merge allowed:** {str(bool(contract.get('is_merge_allowed'))).lower()}",
        f"- **Auto-merge allowed:** {str(bool(contract.get('is_auto_merge_allowed'))).lower()}",
        f"- **Recommended future action:** `{_md(pr.get('recommended_future_action') or '')}`",
        "",
    ]
    lines.append("Reasons:")
    lines.append("")
    for reason in pr.get("reasons") or []:
        lines.append(f"- {_md(reason)}")
    lines.append("")

    # Required checks
    lines += ["## Required Checks", ""]
    for check in contract.get("required_checks") or []:
        lines.append(f"- {_md(check)}")
    lines.append("")

    # Required branch protection
    lines += ["## Required Branch Protection", ""]
    for item in contract.get("required_branch_protection") or []:
        lines.append(f"- {_md(item)}")
    lines.append("")

    # Required human checks
    lines += ["## Required Human Checks", ""]
    for check in contract.get("required_human_checks") or []:
        lines.append(f"- {_md(check)}")
    lines.append("")

    # Risk summary
    lines += ["## Risk Summary", ""]
    risk = contract.get("risk_summary") or {}
    for key, label in (
        ("safety", "Safety"),
        ("scope", "Scope"),
        ("validation", "Validation"),
        ("side_effects", "Side effects"),
        ("budget_or_model_use", "Budget / model use"),
        ("human_gate", "Human gate"),
        ("merge_authority", "Merge authority"),
    ):
        lines.append(f"- **{label}:** {_md(risk.get(key, ''))}")
    lines.append("")

    # Evidence links
    lines += ["## Evidence Links", ""]
    links = contract.get("evidence_links") or []
    if links:
        for link in links:
            lines.append(f"- **{_md(link.get('label', ''))}:** `{_md(link.get('path', ''))}`")
    else:
        lines.append("_None._")
    lines.append("")

    # Blockers
    lines += ["## Blockers", ""]
    blockers = contract.get("blockers") or []
    if blockers:
        for blocker in blockers:
            lines.append(f"- {_md(blocker)}")
    else:
        lines.append("_None — no blocker to preparing a draft PR after human review._")
    lines.append("")

    # Warnings
    lines += ["## Warnings", ""]
    warnings = contract.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- {_md(warning)}")
    else:
        lines.append("_None._")
    lines.append("")

    # Forbidden actions
    lines += ["## Forbidden Actions", ""]
    lines.append(
        "No automation may take any of these on this evidence — they are not actions this "
        "tool or the future workflow performs without a human in the loop:"
    )
    lines.append("")
    for action in contract.get("forbidden_actions") or []:
        lines.append(f"- `{_md(action)}`")
    lines.append("")

    # Allowed future actions
    lines += ["## Allowed Future Actions", ""]
    lines.append("Informational only — a human-driven workflow could later choose one of:")
    lines.append("")
    emphasis = (contract.get("pr_readiness") or {}).get("recommended_future_action") or ""
    for action in contract.get("allowed_future_actions") or []:
        mark = " (recommended)" if action == emphasis else ""
        lines.append(f"- `{_md(action)}`{mark}")
    lines.append("")

    # Boundaries
    lines += ["## Boundaries", ""]
    lines += [
        "- AUTO.2b does not contact GitHub.",
        "- AUTO.2b does not create branches.",
        "- AUTO.2b does not push commits.",
        "- AUTO.2b does not open PRs.",
        "- AUTO.2b does not merge PRs.",
        "- AUTO.2b does not call Webhooks.",
        "- AUTO.2b does not call models.",
        "- AUTO.2b does not apply patches.",
        "- AUTO.2b does not run validation or benchmarks.",
        "- AUTO.2b does not contact Telegram or N8N.",
        "- A future PR is not merge authority.",
        "- Human review and branch protection remain required.",
        "",
    ]
    return "\n".join(lines) + "\n"


# ── Report writing ──────────────────────────────────────────────────────────────

def write_github_pr_safety_contract(
    artifact: Any,
    output_dir: str | Path,
    contract_id: str = "",
    created_at: str = "",
    *,
    source_artifact: str = "",
) -> dict[str, Any]:
    """Build the contract and write the JSON + Markdown artifacts.

    Returns ``{ok, json_path, md_path, contract}``. Nothing is run or contacted.
    """
    contract = build_github_pr_safety_contract(
        artifact=artifact,
        contract_id=contract_id,
        created_at=created_at,
        source_artifact=source_artifact,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(
        json.dumps(contract, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    md_path.write_text(render_github_pr_safety_contract_markdown(contract), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "contract": contract}
