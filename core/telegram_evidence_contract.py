"""AUTO.2a — Telegram Evidence Summary Contract (report-only).

Reads an AUTO.1e sandbox self-evolution evidence pack and shapes a compact,
human-readable evidence-summary message plus a contract describing what a human
may, and may not, do on the strength of that summary. It is meant to prepare a
future chat-review workflow without building any part of it yet.

AUTO.2a defines the summary. It does not contact Telegram, send messages, call
Webhooks, make any network request, call models, apply patches, run validation or
a benchmark check, write to the real repo, push, merge, open PRs, or contact a
remote git host / N8N / external automation. Chat approval is never merge
authority; human review, local evidence, and branch protection remain required.

This module is stdlib-only and pure: it reads an already-parsed evidence-pack
record (a plain dict) and returns a deterministic contract record plus Markdown.
It reads no files and never mutates the source pack.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "telegram_evidence_contract"

#: AUTO.1e final verdicts this contract recognises (consumed, not produced here).
SOURCE_FINAL_VERDICTS: tuple[str, ...] = (
    "ready_for_human_review",
    "needs_more_validation",
    "blocked",
    "incomplete_pack",
)

#: Verdicts for which a summary may be marked sendable.
_SENDABLE_VERDICTS: tuple[str, ...] = ("ready_for_human_review", "needs_more_validation")

#: Informational approval options a human chooses from (none of these acts).
APPROVAL_OPTIONS: tuple[str, ...] = ("review", "defer", "reject", "request_more_validation")

#: The option emphasised when the pack needs more validation.
_EMPHASIS_OPTION = "request_more_validation"

#: Actions this contract forbids being taken on the strength of a chat summary.
FORBIDDEN_ACTIONS: tuple[str, ...] = (
    "approve_merge",
    "push",
    "merge",
    "apply_patch",
    "run_worker",
    "launch_model",
    "rerun_automation",
    "contact_network",
)

#: Source-pack guardrail booleans that MUST be false; true means a hard breach.
_PACK_BOOL_SHOULD_BE_FALSE: tuple[tuple[str, str], ...] = (
    ("self_approval_allowed", "allows self-approval"),
    ("eligible_for_auto_merge", "marks the candidate eligible for auto-merge"),
    ("real_repo_modified", "reports the real repo was modified"),
    ("patch_applied_to_real_repo", "reports a patch was written to the real repo"),
    ("push_performed", "reports a push was performed"),
    ("merge_performed", "reports a merge was performed"),
    ("model_call_performed", "reports a model call was performed"),
    ("validation_run_by_tool", "reports validation was run by a tool"),
    ("benchmark_run_by_tool", "reports a benchmark check was run by a tool"),
    ("worker_launch_performed", "reports a worker was launched"),
)

#: Report artifact filenames.
JSON_NAME = "telegram_evidence_contract.json"
MD_NAME = "telegram_evidence_contract.md"

TELEGRAM_EVIDENCE_GUARDRAIL_NOTE = (
    "Telegram Evidence Summary Contract is report-only: it reads an AUTO.1e evidence "
    "pack and defines what a chat-review summary should contain. It does not contact "
    "Telegram, send messages, call Webhooks, make any network request, call models, "
    "apply patches, run validation or a benchmark check, write to the real repo, push, "
    "merge, open PRs, or contact a remote git host / N8N / external automation. Chat "
    "approval is not merge authority; human review, local evidence, and branch "
    "protection remain required."
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


# ── Deterministic analysis ─────────────────────────────────────────────────────

def _detect_hard_breaches(pack: dict[str, Any]) -> list[str]:
    """Return breach descriptions found in the source pack (empty if clean).

    A breach means a report-only / sandbox-only contract was violated somewhere
    upstream, so the summary must never be sendable regardless of the verdict.
    """
    breaches: list[str] = []
    for field, phrase in _PACK_BOOL_SHOULD_BE_FALSE:
        if pack.get(field) is True:
            breaches.append(f"the evidence pack {phrase} ({field})")
    if pack.get("human_review_required") is False:
        breaches.append("the evidence pack does not require human review (human_review_required)")
    # The pack's own hard blockers (from AUTO.1e) are surfaced verbatim.
    for blocker in _str_list(pack.get("blockers")):
        breaches.append(blocker)
    return _dedupe(breaches)


def _approval_options(final_verdict: str) -> tuple[list[str], str]:
    """Return (ordered options, emphasised option)."""
    if final_verdict == "needs_more_validation":
        ordered = [_EMPHASIS_OPTION] + [o for o in APPROVAL_OPTIONS if o != _EMPHASIS_OPTION]
        return ordered, _EMPHASIS_OPTION
    return list(APPROVAL_OPTIONS), ""


def _side_effect_summary(packet: dict[str, Any], risk: dict[str, Any]) -> str:
    side = packet.get("sandbox_side_effects")
    if isinstance(side, dict):
        patch = side.get("patch") or {}
        validation = side.get("validation") or {}
        return (
            "sandbox-only: patch ("
            f"created {patch.get('created', 0)}, modified {patch.get('modified', 0)}, "
            f"deleted {patch.get('deleted', 0)}); validation ("
            f"created {validation.get('created', 0)}, modified {validation.get('modified', 0)}, "
            f"deleted {validation.get('deleted', 0)})"
        )
    return _str(risk.get("side_effects"), "(unknown)")


def _build_message(
    *,
    trial_id: str,
    phase_or_objective: str,
    final_verdict: str,
    recommended_next_step: str,
    touched_files: list[str],
    validation_status: str,
    side_effects: str,
    blockers: list[str],
    warnings: list[str],
    approval_options: list[str],
    emphasis_option: str,
) -> str:
    """A compact, human-readable chat summary. Text only — nothing is ever sent."""
    lines = [
        f"Sandbox self-evolution review — trial {trial_id or '(none)'}",
        f"Phase / objective: {phase_or_objective}",
        f"Verdict: {final_verdict or '(unknown)'}",
        f"Recommended next step: {recommended_next_step or '(none)'}",
        "Touched files: " + (", ".join(touched_files) if touched_files else "(none reported)"),
        f"Validation: {validation_status or '(unknown)'}",
        f"Side effects: {side_effects}",
    ]
    if blockers:
        lines.append("Blockers: " + "; ".join(blockers))
    if warnings:
        lines.append("Warnings: " + "; ".join(warnings))
    lines.append("Human action options: " + ", ".join(approval_options))
    if emphasis_option:
        lines.append(f"Recommended option: {emphasis_option}")
    lines.append(
        "Human review required. Chat approval is not merge authority; branch protection "
        "and local evidence remain required before any real repo change."
    )
    return "\n".join(lines)


def _required_human_checks() -> list[str]:
    return [
        "Open and read the touched files; confirm they match the intended scope.",
        "Confirm the sandbox validation result and that validation was not skipped.",
        "Confirm no real repo change, push, merge, or PR resulted from the sandbox trial.",
        "Confirm branch protection and local evidence requirements before any real repo change.",
        "Treat this summary as informational only; human review remains required.",
    ]


def _evidence_links(pack: dict[str, Any], source_evidence_pack: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    if source_evidence_pack:
        links.append({"label": "Evidence pack", "path": str(source_evidence_pack)})
    artifacts = pack.get("source_artifacts")
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if isinstance(artifact, dict):
                links.append(
                    {"label": _str(artifact.get("label"), "Artifact"), "path": _str(artifact.get("path"))}
                )
    return links


def _risk_summary(pack: dict[str, Any]) -> dict[str, str]:
    source = pack.get("risk_summary") if isinstance(pack.get("risk_summary"), dict) else {}
    return {
        "safety": _str(source.get("safety"), "(unknown)"),
        "scope": _str(source.get("scope"), "(unknown)"),
        "validation": _str(source.get("validation"), "(unknown)"),
        "side_effects": _str(source.get("side_effects"), "(unknown)"),
        "budget_or_model_use": _str(source.get("budget_or_model_use"), "(unknown)"),
        "human_gate": _str(source.get("human_gate"), "(unknown)"),
        "merge_authority": (
            "Chat approval is not merge authority; human review, local evidence, and "
            "branch protection remain required before any real repo change."
        ),
    }


def _guardrails() -> dict[str, bool]:
    """The contract's own guardrails — this tool performs none of these actions."""
    return {
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
        "network_call_performed": False,
        "telegram_message_sent": False,
    }


def _boundaries() -> dict[str, bool]:
    return {
        "defines_summary_only": True,
        "contacts_chat_app": False,
        "sends_messages": False,
        "calls_callbacks": False,
        "makes_network_call": False,
        "calls_models": False,
        "applies_patches": False,
        "runs_validation_or_benchmarks": False,
        "pushes_merges_or_opens_pr": False,
        "is_merge_authority": False,
    }


# ── Contract assembly ──────────────────────────────────────────────────────────

def build_telegram_evidence_contract(
    *,
    evidence_pack: Any,
    contract_id: str = "",
    created_at: str = "",
    source_evidence_pack: str = "",
) -> dict[str, Any]:
    """Shape an AUTO.1e evidence pack into a deterministic chat-summary contract.

    Pure: never mutates ``evidence_pack`` and never runs or contacts anything. A
    missing or malformed pack yields a not-sendable contract that says so.
    """
    pack = evidence_pack if isinstance(evidence_pack, dict) else {}

    final_verdict = _str(pack.get("final_verdict")).strip()
    if final_verdict not in SOURCE_FINAL_VERDICTS:
        # Unknown / missing verdict (e.g. a malformed pack) -> treat as incomplete.
        final_verdict = "incomplete_pack"

    trial_id = _str(pack.get("trial_id")).strip()
    recommended_next_step = _str(pack.get("recommended_next_step")).strip()

    packet = pack.get("human_review_packet") if isinstance(pack.get("human_review_packet"), dict) else {}
    risk = pack.get("risk_summary") if isinstance(pack.get("risk_summary"), dict) else {}
    touched_files = _str_list(packet.get("patch_touched_files"))
    validation_status = _str(packet.get("validation_status")) or _str(risk.get("validation"), "(unknown)")
    side_effects = _side_effect_summary(packet, risk)
    phase_or_objective = _str(packet.get("phase_or_objective"), "(unknown)")

    warnings = _str_list(pack.get("warnings"))
    pack_blockers = _str_list(pack.get("blockers"))

    breaches = _detect_hard_breaches(pack)
    options, emphasis_option = _approval_options(final_verdict)

    # Sendability: only ready / needs-more-validation, and only with no breach.
    send_blockers: list[str] = list(breaches)
    if not pack:
        send_blockers.append("the evidence pack is missing or malformed")
    if final_verdict == "blocked":
        send_blockers.append("the evidence pack verdict is blocked")
    if final_verdict == "incomplete_pack":
        send_blockers.append("the evidence pack is incomplete")
    send_blockers = _dedupe(send_blockers)

    is_sendable = (final_verdict in _SENDABLE_VERDICTS) and not breaches and not send_blockers

    message = _build_message(
        trial_id=trial_id,
        phase_or_objective=phase_or_objective,
        final_verdict=final_verdict,
        recommended_next_step=recommended_next_step,
        touched_files=touched_files,
        validation_status=validation_status,
        side_effects=side_effects,
        blockers=pack_blockers,
        warnings=warnings,
        approval_options=options,
        emphasis_option=emphasis_option,
    )

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": TELEGRAM_EVIDENCE_GUARDRAIL_NOTE,
        "contract_id": str(contract_id or ""),
        "created_at": str(created_at or ""),
        "source_evidence_pack": str(source_evidence_pack or ""),
        "trial_id": trial_id,
        "final_verdict": final_verdict,
        "recommended_next_step": recommended_next_step,
        "telegram_message": message,
        "approval_options": options,
        "approval_emphasis": emphasis_option,
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "required_human_checks": _required_human_checks(),
        "risk_summary": _risk_summary(pack),
        "evidence_links": _evidence_links(pack, source_evidence_pack),
        "guardrails": _guardrails(),
        "is_sendable": is_sendable,
        "send_blockers": send_blockers,
        "warnings": warnings,
        "boundaries": _boundaries(),
    }


# ── Markdown rendering ──────────────────────────────────────────────────────────

def render_telegram_evidence_contract_markdown(contract: dict[str, Any]) -> str:
    """Render a contract record as one operator-readable Markdown report."""
    lines: list[str] = [
        "# Telegram Evidence Summary Contract",
        "",
        f"> {contract.get('guardrail_note', TELEGRAM_EVIDENCE_GUARDRAIL_NOTE)}",
        "",
        "_Report only: AUTO.2a defines what a chat-review summary should contain from an "
        "AUTO.1e evidence pack. It contacts nothing, sends nothing, and changes nothing. "
        "Chat approval is not merge authority; human review remains required._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Contract id:** `{_md(contract.get('contract_id') or '(none)')}`",
        f"- **Created at:** `{_md(contract.get('created_at') or '(none)')}`",
        f"- **Source evidence pack:** `{_md(contract.get('source_evidence_pack') or '(none)')}`",
        f"- **Trial id:** `{_md(contract.get('trial_id') or '(none)')}`",
        f"- **Final verdict:** `{_md(contract.get('final_verdict') or '')}`",
        f"- **Recommended next step:** `{_md(contract.get('recommended_next_step') or '(none)')}`",
        f"- **Is sendable:** {str(bool(contract.get('is_sendable'))).lower()}",
        "",
        "## Telegram Message Preview",
        "",
        "```",
        contract.get("telegram_message", ""),
        "```",
        "",
    ]

    # Approval options
    lines += ["## Approval Options", ""]
    options = contract.get("approval_options") or []
    emphasis = contract.get("approval_emphasis") or ""
    if options:
        for option in options:
            mark = " (recommended)" if option == emphasis else ""
            lines.append(f"- `{_md(option)}`{mark}")
    else:
        lines.append("_None._")
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

    # Send blockers
    lines += ["## Send Blockers", ""]
    send_blockers = contract.get("send_blockers") or []
    if send_blockers:
        for blocker in send_blockers:
            lines.append(f"- {_md(blocker)}")
    else:
        lines.append("_None — no blocker to sending this summary for human review._")
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
        "No chat approval option may trigger any of these — they are not actions this "
        "tool or the chat workflow performs:"
    )
    lines.append("")
    for action in contract.get("forbidden_actions") or []:
        lines.append(f"- `{_md(action)}`")
    lines.append("")

    # Boundaries
    lines += ["## Boundaries", ""]
    lines += [
        "- AUTO.2a does not contact Telegram.",
        "- AUTO.2a does not send messages.",
        "- AUTO.2a does not call Webhooks.",
        "- AUTO.2a does not call models.",
        "- AUTO.2a does not apply patches.",
        "- AUTO.2a does not run validation or benchmarks.",
        "- AUTO.2a does not push, merge, open PRs, or contact GitHub / N8N.",
        "- Telegram approval is not merge authority; human review, local evidence, and "
        "branch protection remain required.",
        "",
    ]
    return "\n".join(lines) + "\n"


# ── Report writing ──────────────────────────────────────────────────────────────

def write_telegram_evidence_contract(
    evidence_pack: Any,
    output_dir: str | Path,
    contract_id: str = "",
    created_at: str = "",
    *,
    source_evidence_pack: str = "",
) -> dict[str, Any]:
    """Build the contract and write the JSON + Markdown artifacts.

    Returns ``{ok, json_path, md_path, contract}``. Nothing is run or contacted.
    """
    contract = build_telegram_evidence_contract(
        evidence_pack=evidence_pack,
        contract_id=contract_id,
        created_at=created_at,
        source_evidence_pack=source_evidence_pack,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(
        json.dumps(contract, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    md_path.write_text(render_telegram_evidence_contract_markdown(contract), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "contract": contract}
