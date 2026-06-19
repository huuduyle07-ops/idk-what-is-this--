"""AUTO.2c — n8n Orchestration Dry Run (report-only).

Reads one or more upstream artifacts — an AUTO.1e self-evolution evidence pack, an
AUTO.2a evidence summary contract, and/or an AUTO.2b PR safety contract — and
produces a deterministic *simulation* of how a future n8n workflow would
orchestrate the review chain. It is meant to prepare a future orchestration
workflow without building any part of it yet.

AUTO.2c simulates only. It does not contact n8n, call Webhooks, make any network
request, send Telegram messages, contact GitHub, run Git commands, create
branches, open or merge PRs, push commits, call models, launch workers, apply
patches, or run validation or a benchmark check. Live execution is never
performed; human review remains required before any live remote action.

This module is stdlib-only and pure: it reads already-parsed artifact records
(plain dicts) and returns a deterministic report record plus Markdown. It reads no
files and never mutates the source artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "n8n_orchestration_dry_run"

SOURCE_KIND_EVIDENCE_PACK = "self_evolution_evidence_pack"
SOURCE_KIND_TELEGRAM = "telegram_evidence_contract"
SOURCE_KIND_GITHUB = "github_pr_safety_contract"
SOURCE_KIND_UNKNOWN = "unknown"
SOURCE_KINDS: tuple[str, ...] = (
    SOURCE_KIND_EVIDENCE_PACK,
    SOURCE_KIND_TELEGRAM,
    SOURCE_KIND_GITHUB,
    SOURCE_KIND_UNKNOWN,
)

#: Upstream final verdicts this report recognises (consumed, not produced here).
KNOWN_VERDICTS: tuple[str, ...] = (
    "ready_for_human_review",
    "needs_more_validation",
    "blocked",
    "incomplete_pack",
)

#: Aggregate dry-run verdicts this report produces.
OVERALL_READY = "dry_run_ready_for_human_review"
OVERALL_NEEDS = "needs_more_validation"
OVERALL_BLOCKED = "blocked"

#: Step status values.
STATUS_SIMULATED = "simulated"
STATUS_BLOCKED = "blocked"
STATUS_HALT = "halt"

#: Source guardrail booleans that MUST be false; true in any source is a breach.
_BREACH_FIELDS: tuple[tuple[str, str], ...] = (
    ("self_approval_allowed", "allows self-approval"),
    ("eligible_for_auto_merge", "is eligible for auto-merge"),
    ("real_repo_modified", "modified the real repo"),
    ("patch_applied_to_real_repo", "applied a patch to the real repo"),
    ("push_performed", "performed a push"),
    ("merge_performed", "performed a merge"),
    ("pr_created", "created a PR"),
    ("branch_created", "created a branch"),
    ("network_call_performed", "performed a network call"),
    ("github_contacted", "contacted the remote host"),
    ("telegram_message_sent", "sent a chat message"),
    ("n8n_contacted", "contacted the orchestrator"),
    ("model_call_performed", "performed a model call"),
    ("worker_launch_performed", "launched a worker"),
)

#: Deterministic simulated step templates (the orchestration plan).
_STEP_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "step_id": "load_evidence_pack",
        "name": "Load evidence artifacts",
        "input_artifacts": list(SOURCE_KINDS[:3]),
        "would_contact": "none (reads local artifact files only)",
        "blocked_actions": [],
        "tier": "load",
    },
    {
        "step_id": "build_telegram_summary",
        "name": "Build the Telegram evidence summary (AUTO.2a)",
        "input_artifacts": [SOURCE_KIND_EVIDENCE_PACK],
        "would_contact": "a future run would send a Telegram message; nothing is sent here",
        "blocked_actions": ["send_telegram_message"],
        "tier": "prepare",
    },
    {
        "step_id": "build_github_pr_safety_contract",
        "name": "Build the GitHub PR safety contract (AUTO.2b)",
        "input_artifacts": [SOURCE_KIND_EVIDENCE_PACK, SOURCE_KIND_TELEGRAM],
        "would_contact": "a future run would contact a remote code-hosting service; nothing is contacted here",
        "blocked_actions": ["contact_github", "create_branch", "open_pr", "push_commits", "merge_pr"],
        "tier": "prepare",
    },
    {
        "step_id": "prepare_human_review_notification",
        "name": "Prepare the human-review notification",
        "input_artifacts": [SOURCE_KIND_TELEGRAM, SOURCE_KIND_GITHUB],
        "would_contact": "a future run would notify a human reviewer; nothing is notified here",
        "blocked_actions": ["send_notification"],
        "tier": "prepare",
    },
    {
        "step_id": "wait_for_human_review",
        "name": "Wait for human review",
        "input_artifacts": [],
        "would_contact": "none (waits for a human decision)",
        "blocked_actions": [],
        "tier": "wait",
    },
    {
        "step_id": "prepare_future_draft_pr_request",
        "name": "Prepare the future draft-PR request",
        "input_artifacts": [SOURCE_KIND_GITHUB],
        "would_contact": "a future run would request a draft PR after human review; nothing is requested here",
        "blocked_actions": ["create_branch", "open_pr", "push_commits", "merge_pr", "enable_auto_merge"],
        "tier": "draft",
    },
    {
        "step_id": "stop_before_live_execution",
        "name": "Stop before live execution",
        "input_artifacts": [],
        "would_contact": "none (live execution is never performed in a dry run)",
        "blocked_actions": ["live_orchestration", "contact_n8n", "launch_worker", "call_model", "merge_pr"],
        "tier": "halt",
    },
)

STEP_IDS: tuple[str, ...] = tuple(tmpl["step_id"] for tmpl in _STEP_TEMPLATES)

#: Report artifact filenames.
JSON_NAME = "n8n_orchestration_dry_run.json"
MD_NAME = "n8n_orchestration_dry_run.md"

N8N_ORCHESTRATION_GUARDRAIL_NOTE = (
    "n8n Orchestration Dry Run is report-only: it reads AUTO.1e / AUTO.2a / AUTO.2b "
    "artifacts and simulates how a future n8n workflow would orchestrate them. It does "
    "not contact n8n, call Webhooks, make any network request, send Telegram messages, "
    "contact GitHub, run Git commands, create branches, open or merge PRs, push commits, "
    "call models, launch workers, apply patches, or run validation or a benchmark check. "
    "Live execution is never performed; human review remains required before any live "
    "remote action."
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _str(value: Any, default: str = "") -> str:
    return str(value) if value is not None else default


def _str_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ── Source detection + normalisation ───────────────────────────────────────────

def detect_source_kind(artifact: dict[str, Any]) -> str:
    """Best-effort detect which upstream artifact kind ``artifact`` is."""
    kind = _str(artifact.get("report_kind")).strip()
    if kind == "sandbox_self_evolution_evidence_pack":
        return SOURCE_KIND_EVIDENCE_PACK
    if kind == "telegram_evidence_contract":
        return SOURCE_KIND_TELEGRAM
    if kind == "github_pr_safety_contract":
        return SOURCE_KIND_GITHUB
    # Structural sniffing when report_kind is absent or unexpected.
    if "human_review_packet" in artifact or "source_artifacts" in artifact:
        return SOURCE_KIND_EVIDENCE_PACK
    if "telegram_message" in artifact or "approval_options" in artifact:
        return SOURCE_KIND_TELEGRAM
    if "pr_readiness" in artifact or "required_branch_protection" in artifact:
        return SOURCE_KIND_GITHUB
    return SOURCE_KIND_UNKNOWN


def _normalise_one(artifact: dict[str, Any], source_kind: str) -> dict[str, Any]:
    """Project any supported source shape onto one common record."""
    final_verdict = _str(artifact.get("final_verdict")).strip()
    if final_verdict not in KNOWN_VERDICTS:
        final_verdict = "incomplete_pack"

    risk = artifact.get("risk_summary") if isinstance(artifact.get("risk_summary"), dict) else {}

    if source_kind == SOURCE_KIND_TELEGRAM:
        flags = artifact.get("guardrails") if isinstance(artifact.get("guardrails"), dict) else {}
        blockers = _str_list(artifact.get("send_blockers"))
        message = _str(artifact.get("telegram_message"))
    elif source_kind == SOURCE_KIND_GITHUB:
        flags = artifact.get("guardrails") if isinstance(artifact.get("guardrails"), dict) else {}
        blockers = _str_list(artifact.get("blockers"))
        message = ""
    else:
        flags = artifact
        blockers = _str_list(artifact.get("blockers"))
        message = ""

    return {
        "verdict": final_verdict,
        "recommended_next_step": _str(artifact.get("recommended_next_step")).strip(),
        "trial_id": _str(artifact.get("trial_id")).strip(),
        "warnings": _str_list(artifact.get("warnings")),
        "risk": risk,
        "flags": flags,
        "blockers": blockers,
        "message": message,
    }


def _detect_breaches(flags: dict[str, Any]) -> list[str]:
    """Return guardrail breach descriptions found in one source (empty if clean)."""
    breaches: list[str] = []
    for field, phrase in _BREACH_FIELDS:
        if flags.get(field) is True:
            breaches.append(f"{phrase} ({field})")
    if flags.get("human_review_required") is False:
        breaches.append("does not require human review (human_review_required)")
    return breaches


# ── Step / notification / action assembly ───────────────────────────────────────

def _step_status(tier: str, overall: str) -> tuple[str, bool]:
    not_blocked = overall in (OVERALL_READY, OVERALL_NEEDS)
    ready = overall == OVERALL_READY
    if tier == "load":
        return STATUS_SIMULATED, True
    if tier == "prepare":
        return (STATUS_SIMULATED, True) if not_blocked else (STATUS_BLOCKED, False)
    if tier == "wait":
        return (STATUS_HALT, True) if not_blocked else (STATUS_BLOCKED, False)
    if tier == "draft":
        return (STATUS_SIMULATED, True) if ready else (STATUS_BLOCKED, False)
    return STATUS_HALT, True  # halt tier: always the deliberate stop


def _step_output_preview(step_id: str, status: str, *, trial_id: str, detected: list[str]) -> str:
    blocked_prefix = "(blocked) " if status == STATUS_BLOCKED else ""
    previews = {
        "load_evidence_pack": f"Loaded {len(detected)} source artifact(s): {', '.join(detected) or '(none)'}",
        "build_telegram_summary": f"Preview: Telegram evidence summary for trial {trial_id or '(none)'}",
        "build_github_pr_safety_contract": f"Preview: GitHub PR safety contract for trial {trial_id or '(none)'}",
        "prepare_human_review_notification": "Preview: human-review notification with evidence links",
        "wait_for_human_review": "Awaiting a human decision (no automated progression)",
        "prepare_future_draft_pr_request": "Preview: future draft-PR request (only after human review)",
        "stop_before_live_execution": "Halt: live orchestration is never performed in a dry run",
    }
    return blocked_prefix + previews.get(step_id, "")


def _build_steps(overall: str, *, trial_id: str, detected: list[str]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for tmpl in _STEP_TEMPLATES:
        status, allowed = _step_status(tmpl["tier"], overall)
        steps.append(
            {
                "step_id": tmpl["step_id"],
                "name": tmpl["name"],
                "status": status,
                "input_artifacts": list(tmpl["input_artifacts"]),
                "output_preview": _step_output_preview(
                    tmpl["step_id"], status, trial_id=trial_id, detected=detected
                ),
                "would_contact": tmpl["would_contact"],
                "actual_contact_performed": False,
                "allowed_in_dry_run": allowed,
                "blocked_actions": list(tmpl["blocked_actions"]),
            }
        )
    return steps


def _simulated_notifications(overall: str, *, trial_id: str, telegram_preview: str) -> list[dict[str, Any]]:
    not_blocked = overall in (OVERALL_READY, OVERALL_NEEDS)
    return [
        {
            "channel": "telegram",
            "title": f"Sandbox self-evolution review — trial {trial_id or '(none)'}",
            "body_preview": telegram_preview or f"Verdict: {overall}; human review remains required.",
            "would_send": "would send to a chat reviewer (not sent here)",
            "actual_send_performed": False,
            "allowed_in_dry_run": not_blocked,
        },
        {
            "channel": "human_review",
            "title": "Human review required before any live remote action",
            "body_preview": f"Verdict: {overall}; human review and branch protection remain required.",
            "would_send": "would notify a human reviewer (not notified here)",
            "actual_send_performed": False,
            "allowed_in_dry_run": not_blocked,
        },
    ]


def _simulated_remote_actions(overall: str) -> list[dict[str, Any]]:
    ready = overall == OVERALL_READY
    return [
        {
            "target": "github",
            "action": "open_draft_pr",
            "would_perform": "would open a draft PR after human review (not opened here)",
            "actual_action_performed": False,
            "allowed_in_dry_run": ready,
        },
        {
            "target": "n8n",
            "action": "trigger_orchestration",
            "would_perform": "would trigger an n8n orchestration after human review (not triggered here)",
            "actual_action_performed": False,
            "allowed_in_dry_run": ready,
        },
    ]


def _required_human_checks() -> list[str]:
    return [
        "Open and read the evidence pack and the touched files; confirm scope before any orchestration.",
        "Confirm validation evidence is present and was not skipped.",
        "Confirm branch protection and required checks on the target branch before any future PR.",
        "Confirm no direct push to the protected main branch and that auto-merge stays disabled.",
        "Confirm a linked evidence pack / evidence summary accompanies any future review notification.",
        "Author and review any future PR by hand; this dry run is not merge authority.",
    ]


def _risk_summary(risk: dict[str, Any]) -> dict[str, str]:
    return {
        "safety": _str(risk.get("safety"), "(unknown)"),
        "scope": _str(risk.get("scope"), "(unknown)"),
        "validation": _str(risk.get("validation"), "(unknown)"),
        "side_effects": _str(risk.get("side_effects"), "(unknown)"),
        "human_gate": _str(risk.get("human_gate"), "(unknown)"),
        "orchestration": "Simulated only; no live n8n or remote orchestration is performed.",
        "live_execution": "Live execution is never performed in this dry run.",
        "merge_authority": (
            "Neither this dry run nor any future notification is merge authority; human "
            "review and branch protection remain required."
        ),
    }


def _guardrails() -> dict[str, bool]:
    """The report's own guardrails — this tool performs none of these actions."""
    return {
        "human_review_required": True,
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
        "live_execution_allowed": False,
        "network_call_performed": False,
        "n8n_contacted": False,
        "telegram_message_sent": False,
        "github_contacted": False,
        "pr_created": False,
        "branch_created": False,
        "push_performed": False,
        "merge_performed": False,
        "model_call_performed": False,
        "worker_launch_performed": False,
        "patch_applied_to_real_repo": False,
        "validation_run_by_tool": False,
        "benchmark_run_by_tool": False,
    }


def _boundaries() -> dict[str, bool]:
    return {
        "simulates_orchestration_only": True,
        "contacts_orchestrator": False,
        "calls_callbacks": False,
        "makes_network_call": False,
        "sends_chat_messages": False,
        "contacts_remote_host": False,
        "runs_version_control": False,
        "opens_or_merges_pr": False,
        "calls_models": False,
        "launches_workers": False,
        "performs_live_execution": False,
        "is_merge_authority": False,
    }


# ── Report assembly ─────────────────────────────────────────────────────────────

def build_n8n_orchestration_dry_run(
    *,
    sources: Any,
    dry_run_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Shape one or more upstream artifacts into a deterministic orchestration dry run.

    ``sources`` is a list of ``{"path", "artifact", "load_error"}`` records, where
    ``artifact`` is an already-parsed dict (or ``None`` if it could not be loaded).
    Pure: never mutates the sources and never runs or contacts anything.
    """
    source_list = list(sources) if isinstance(sources, list) else []

    records: list[dict[str, Any]] = []
    detected: list[str] = []
    verdicts: list[str] = []
    all_breaches: list[str] = []
    all_blockers: list[str] = []
    all_warnings: list[str] = []
    any_unloaded = False
    any_unknown = False
    trial_id = ""
    chosen_risk: dict[str, Any] = {}
    telegram_preview = ""

    for src in source_list:
        src = src if isinstance(src, dict) else {}
        path = _str(src.get("path"))
        artifact = src.get("artifact")
        load_error = _str(src.get("load_error"))

        if isinstance(artifact, dict) and artifact:
            kind = detect_source_kind(artifact)
            norm = _normalise_one(artifact, kind)
            breaches = _detect_breaches(norm["flags"])
            detected.append(kind)
            verdicts.append(norm["verdict"])
            all_breaches += [f"{kind} ({path or 'source'}): {b}" for b in breaches]
            all_blockers += [f"{kind} ({path or 'source'}): {b}" for b in norm["blockers"]]
            all_warnings += norm["warnings"]
            if kind == SOURCE_KIND_UNKNOWN:
                any_unknown = True
            if not trial_id and norm["trial_id"]:
                trial_id = norm["trial_id"]
            if not chosen_risk and norm["risk"]:
                chosen_risk = norm["risk"]
            if not telegram_preview and norm["message"]:
                telegram_preview = _md(norm["message"])[:200]
            records.append(
                {
                    "path": path,
                    "source_kind": kind,
                    "loaded": True,
                    "verdict": norm["verdict"],
                    "recommended_next_step": norm["recommended_next_step"],
                    "errors": [load_error] if load_error else [],
                    "warnings": norm["warnings"],
                }
            )
        else:
            any_unloaded = True
            err = load_error or "source artifact could not be loaded"
            detected.append(SOURCE_KIND_UNKNOWN)
            verdicts.append("incomplete_pack")
            all_blockers.append(f"{path or 'source'}: {err}")
            records.append(
                {
                    "path": path,
                    "source_kind": SOURCE_KIND_UNKNOWN,
                    "loaded": False,
                    "verdict": "incomplete_pack",
                    "recommended_next_step": "",
                    "errors": [err],
                    "warnings": [],
                }
            )

    no_sources = len(source_list) == 0

    # ── Decision rules ──────────────────────────────────────────────────────────
    verdict_reasons: list[str] = []
    if no_sources:
        overall = OVERALL_BLOCKED
        verdict_reasons.append("no source artifacts were provided")
    elif all_breaches or any_unloaded or any(v in ("blocked", "incomplete_pack") for v in verdicts):
        overall = OVERALL_BLOCKED
        for rec in records:
            if rec["loaded"] and rec["verdict"] == "blocked":
                verdict_reasons.append(f"{rec['source_kind']} ({rec['path'] or 'source'}) verdict is blocked")
            elif rec["loaded"] and rec["verdict"] == "incomplete_pack":
                verdict_reasons.append(f"{rec['source_kind']} ({rec['path'] or 'source'}) is incomplete")
    elif any(v == "needs_more_validation" for v in verdicts):
        overall = OVERALL_NEEDS
    elif verdicts and all(v == "ready_for_human_review" for v in verdicts):
        overall = OVERALL_READY
    else:
        overall = OVERALL_BLOCKED
        verdict_reasons.append("source verdicts are inconsistent or unrecognised")

    blockers = _dedupe(all_breaches + all_blockers + verdict_reasons)

    warnings = list(all_warnings)
    if overall == OVERALL_NEEDS:
        warnings.append("more validation is required before the future draft-PR step may run")
    if any_unknown:
        warnings.append("one or more source artifacts had an unrecognised kind")
    warnings = _dedupe(warnings)

    detected_sources = sorted(set(detected))
    is_orchestration_allowed_in_future = overall == OVERALL_READY

    steps = _build_steps(overall, trial_id=trial_id, detected=detected_sources)
    orchestration_plan = {
        "summary": (
            "Simulated n8n orchestration of the AUTO.1e -> AUTO.2a -> AUTO.2b review "
            "chain; halts before any live remote action."
        ),
        "step_sequence": list(STEP_IDS),
        "halts_at": "stop_before_live_execution",
        "is_orchestration_allowed_in_future": is_orchestration_allowed_in_future,
        "is_live_execution_allowed": False,
    }

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": N8N_ORCHESTRATION_GUARDRAIL_NOTE,
        "dry_run_id": str(dry_run_id or ""),
        "created_at": str(created_at or ""),
        "source_artifacts": records,
        "detected_sources": detected_sources,
        "trial_id": trial_id,
        "overall_verdict": overall,
        "orchestration_plan": orchestration_plan,
        "steps": steps,
        "simulated_notifications": _simulated_notifications(
            overall, trial_id=trial_id, telegram_preview=telegram_preview
        ),
        "simulated_remote_actions": _simulated_remote_actions(overall),
        "required_human_checks": _required_human_checks(),
        "risk_summary": _risk_summary(chosen_risk),
        "blockers": blockers,
        "warnings": warnings,
        "guardrails": _guardrails(),
        "is_orchestration_allowed_in_future": is_orchestration_allowed_in_future,
        "is_live_execution_allowed": False,
        "is_merge_allowed": False,
        "is_auto_merge_allowed": False,
        "boundaries": _boundaries(),
    }


# ── Markdown rendering ──────────────────────────────────────────────────────────

def render_n8n_orchestration_dry_run_markdown(report: dict[str, Any]) -> str:
    """Render a dry-run record as one operator-readable Markdown report."""
    plan = report.get("orchestration_plan") or {}
    lines: list[str] = [
        "# n8n Orchestration Dry Run",
        "",
        f"> {report.get('guardrail_note', N8N_ORCHESTRATION_GUARDRAIL_NOTE)}",
        "",
        "_Report only: AUTO.2c simulates how a future n8n workflow would orchestrate the "
        "AUTO.1e / AUTO.2a / AUTO.2b review chain. It contacts nothing, sends nothing, and "
        "changes nothing. Live execution is never performed; human review remains required._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Dry-run id:** `{_md(report.get('dry_run_id') or '(none)')}`",
        f"- **Created at:** `{_md(report.get('created_at') or '(none)')}`",
        f"- **Trial id:** `{_md(report.get('trial_id') or '(none)')}`",
        f"- **Overall verdict:** `{_md(report.get('overall_verdict') or '')}`",
        f"- **Detected sources:** {', '.join(report.get('detected_sources') or []) or '(none)'}",
        f"- **Orchestration allowed in future:** {str(bool(report.get('is_orchestration_allowed_in_future'))).lower()}",
        f"- **Live execution allowed:** {str(bool(report.get('is_live_execution_allowed'))).lower()}",
        f"- **Merge allowed:** {str(bool(report.get('is_merge_allowed'))).lower()}",
        f"- **Auto-merge allowed:** {str(bool(report.get('is_auto_merge_allowed'))).lower()}",
        "",
    ]

    # Source artifacts
    lines += ["## Source Artifacts", ""]
    records = report.get("source_artifacts") or []
    if records:
        lines += ["| Path | Kind | Loaded | Verdict | Next step |", "| --- | --- | --- | --- | --- |"]
        for rec in records:
            lines.append(
                f"| `{_md(rec.get('path') or '(none)')}` | {_md(rec.get('source_kind'))} | "
                f"{str(bool(rec.get('loaded'))).lower()} | {_md(rec.get('verdict'))} | "
                f"{_md(rec.get('recommended_next_step') or '(none)')} |"
            )
    else:
        lines.append("_None — no source artifacts were provided._")
    lines.append("")

    # Orchestration plan
    lines += ["## Orchestration Plan", ""]
    lines.append(f"- **Summary:** {_md(plan.get('summary', ''))}")
    lines.append(f"- **Halts at:** `{_md(plan.get('halts_at', ''))}`")
    lines.append(f"- **Step sequence:** {', '.join(plan.get('step_sequence') or [])}")
    lines.append("")

    # Simulated steps
    lines += ["## Simulated Steps", ""]
    for step in report.get("steps") or []:
        lines.append(f"### `{_md(step.get('step_id'))}` — {_md(step.get('name'))}")
        lines.append(f"- **Status:** {_md(step.get('status'))}")
        lines.append(f"- **Allowed in dry run:** {str(bool(step.get('allowed_in_dry_run'))).lower()}")
        lines.append(f"- **Output preview:** {_md(step.get('output_preview'))}")
        lines.append(f"- **Would contact:** {_md(step.get('would_contact'))}")
        lines.append(f"- **Actual contact performed:** {str(bool(step.get('actual_contact_performed'))).lower()}")
        blocked = step.get("blocked_actions") or []
        lines.append(f"- **Blocked actions:** {', '.join(f'`{_md(a)}`' for a in blocked) if blocked else '(none)'}")
        lines.append("")

    # Simulated notifications
    lines += ["## Simulated Notifications", ""]
    for note in report.get("simulated_notifications") or []:
        lines.append(
            f"- **{_md(note.get('channel'))}** — {_md(note.get('title'))}: {_md(note.get('body_preview'))} "
            f"(would send: {_md(note.get('would_send'))}; "
            f"actual send performed: {str(bool(note.get('actual_send_performed'))).lower()})"
        )
    lines.append("")

    # Simulated remote actions
    lines += ["## Simulated Remote Actions", ""]
    for action in report.get("simulated_remote_actions") or []:
        lines.append(
            f"- **{_md(action.get('target'))}** — `{_md(action.get('action'))}`: "
            f"{_md(action.get('would_perform'))} "
            f"(actual action performed: {str(bool(action.get('actual_action_performed'))).lower()})"
        )
    lines.append("")

    # Required human checks
    lines += ["## Required Human Checks", ""]
    for check in report.get("required_human_checks") or []:
        lines.append(f"- {_md(check)}")
    lines.append("")

    # Risk summary
    lines += ["## Risk Summary", ""]
    risk = report.get("risk_summary") or {}
    for key, label in (
        ("safety", "Safety"),
        ("scope", "Scope"),
        ("validation", "Validation"),
        ("side_effects", "Side effects"),
        ("human_gate", "Human gate"),
        ("orchestration", "Orchestration"),
        ("live_execution", "Live execution"),
        ("merge_authority", "Merge authority"),
    ):
        lines.append(f"- **{label}:** {_md(risk.get(key, ''))}")
    lines.append("")

    # Blockers
    lines += ["## Blockers", ""]
    blockers = report.get("blockers") or []
    if blockers:
        for blocker in blockers:
            lines.append(f"- {_md(blocker)}")
    else:
        lines.append("_None — no blocker to a simulated dry run for human review._")
    lines.append("")

    # Warnings
    lines += ["## Warnings", ""]
    warnings = report.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- {_md(warning)}")
    else:
        lines.append("_None._")
    lines.append("")

    # Boundaries
    lines += ["## Boundaries", ""]
    lines += [
        "- AUTO.2c does not contact n8n.",
        "- AUTO.2c does not call Webhooks.",
        "- AUTO.2c does not send Telegram messages.",
        "- AUTO.2c does not contact GitHub.",
        "- AUTO.2c does not run Git commands.",
        "- AUTO.2c does not create branches.",
        "- AUTO.2c does not open PRs.",
        "- AUTO.2c does not push or merge.",
        "- AUTO.2c does not call models.",
        "- AUTO.2c does not launch workers.",
        "- AUTO.2c does not apply patches.",
        "- AUTO.2c does not run validation or benchmarks.",
        "- AUTO.2c is a dry-run contract only.",
        "- Human review remains required before any live remote action.",
        "",
    ]
    return "\n".join(lines) + "\n"


# ── Report writing ──────────────────────────────────────────────────────────────

def write_n8n_orchestration_dry_run(
    sources: Any,
    output_dir: str | Path,
    dry_run_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build the dry run and write the JSON + Markdown artifacts.

    Returns ``{ok, json_path, md_path, report}``. Nothing is run or contacted.
    """
    report = build_n8n_orchestration_dry_run(
        sources=sources, dry_run_id=dry_run_id, created_at=created_at
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    md_path.write_text(render_n8n_orchestration_dry_run_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
