"""ROAD.2 — Phase Picker / Night Candidate Report (report-only).

Reads the ROAD.1 machine-readable phase registry and classifies each phase into a
safe-candidate bucket so an operator can see, at a glance, which phases are safe to
prepare, which need a sandbox, which need human approval, which are blocked, and
which are parked or already shipped.

Core principle: ROAD.2 recommends candidate phases. It does not execute phases,
modify code, call models, run validation or a benchmark check, apply patches, write
to the real repo, push, merge, open PRs, or contact a remote git host / chat
service / external automation. The validation commands inside the registry are
treated as opaque text and are never run here.

ROAD.2 reuses the ROAD.1 validator (``core.phase_registry.validate_phase_registry``)
and never re-implements the schema validation. If the registry is invalid the
report is marked incomplete and no phase is recommended as a safe candidate.

This module is stdlib-only and pure apart from ``write_phase_picker_report`` (which
writes the two report artifacts). The classification functions never read, write,
mutate, or run anything.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.phase_registry import (  # ROAD.2 is allowed to consume the ROAD.1 layer.
    AUTOMATION_LEVELS,
    FORBIDDEN_AUTOMATION_LEVEL,
    RISK_LEVELS,
    _md,
    _natural_tokens,
    validate_phase_registry,
)


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "phase_picker_report"

#: The candidate buckets, in operator-report display order.
BUCKETS: tuple[str, ...] = (
    "safe_to_prepare",
    "sandbox_required",
    "human_approval_required",
    "blocked",
    "deferred_or_parked",
    "complete_or_history",
)

#: The recommended-next-step vocabulary (one per phase summary).
RECOMMENDED_NEXT_STEPS: tuple[str, ...] = (
    "prepare_worker_assignment",
    "prepare_sandbox_trial_contract",
    "request_human_approval",
    "complete_prerequisites",
    "keep_parked",
    "no_action_complete",
    "blocked_until_metadata_fixed",
)

#: Statuses that count as live implementation work eligible for safe prep.
_PREPARABLE_STATUSES: tuple[str, ...] = ("proposed", "active")

#: Automation levels considered local (no sandbox / remote / merge power).
_LOCAL_AUTOMATION: tuple[str, ...] = ("LOCAL_0_OBSERVE", "LOCAL_1_PREPARE")

#: Budget tiers that are cheap enough to prepare without budget approval.
_PREPARABLE_BUDGETS: tuple[str, ...] = ("local_only", "cheap_api_allowed")

#: Risk levels considered safe enough to prepare.
_PREPARABLE_RISKS: tuple[str, ...] = ("low", "medium")

#: The budget tier that forces a phase into the human-approval bucket.
_APPROVAL_BUDGET = "strong_model_requires_approval"

#: The automation level that drafts a real PR (human approval bucket).
_REMOTE_PR_AUTOMATION = "REMOTE_3_DRAFT_PR"

#: The automation level that drafts a sandbox patch (sandbox bucket).
_SANDBOX_AUTOMATION = "SANDBOX_2_DRAFT_PATCH"

#: Track display order for deterministic ranking.
TRACK_ORDER: tuple[str, ...] = (
    "ROAD",
    "AUTO",
    "MODEL",
    "EVAL",
    "HUMAN",
    "ADOPT",
    "CMD",
    "HARDEN",
    "OPS",
    "MIRROR",
    "UX",
    "GOV",
    "A",
    "F",
    "H",
)

#: Rank lookups derived from the ROAD.1 ordered enums (lowest = best).
_RISK_RANK: dict[str, int] = {value: index for index, value in enumerate(RISK_LEVELS)}
_AUTOMATION_RANK: dict[str, int] = {value: index for index, value in enumerate(AUTOMATION_LEVELS)}
_TRACK_RANK: dict[str, int] = {value: index for index, value in enumerate(TRACK_ORDER)}

#: Report artifact filenames.
JSON_NAME = "phase_picker_report.json"
MD_NAME = "phase_picker_report.md"

PHASE_PICKER_GUARDRAIL_NOTE = (
    "Phase Picker / Night Candidate Report is report-only: it reads the ROAD.1 phase "
    "registry and classifies phases into safe-candidate buckets. It does not choose "
    "and execute work, run phases, run validation or a benchmark check, call models, "
    "apply patches, write to the real repo, push, merge, open PRs, or contact a remote "
    "git host, chat app, or external automation. ROAD.2 only recommends; human approval "
    "is required before any phase is acted on."
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _phase_text(phase: dict[str, Any]) -> str:
    """Lowercased title + summary + notes, used for keyword-based hints."""
    parts = [str(phase.get("title", "")), str(phase.get("summary", ""))]
    notes = phase.get("notes")
    if isinstance(notes, list):
        parts += [str(note) for note in notes]
    return " ".join(parts).lower()


def _has_patch_or_sandbox_path(allowed_files: Any) -> bool:
    if not isinstance(allowed_files, list):
        return False
    for entry in allowed_files:
        low = str(entry).lower()
        if "patch" in low or "sandbox" in low:
            return True
    return False


def _ids_with_errors(errors: list[str]) -> set[str]:
    """Phase labels referenced by ROAD.1 per-phase error strings.

    ROAD.1 emits per-phase errors as ``"phase <label> ..."`` (label is the phase id
    or ``"#<index>"`` when the id is missing). Registry-root errors start with
    ``"registry ..."`` and are intentionally not attributed to a single phase.
    """
    labels: set[str] = set()
    for err in errors:
        if err.startswith("phase "):
            rest = err[len("phase "):]
            token = rest.split(" ", 1)[0]
            if token:
                labels.add(token)
    return labels


def _candidate_sort_key(summary: dict[str, Any]) -> tuple[Any, ...]:
    phase_id = str(summary.get("phase_id", ""))
    return (
        _RISK_RANK.get(str(summary.get("risk_level", "")), len(_RISK_RANK)),
        _AUTOMATION_RANK.get(str(summary.get("automation_level", "")), len(_AUTOMATION_RANK)),
        _TRACK_RANK.get(str(summary.get("track", "")), len(_TRACK_RANK)),
        _natural_tokens(phase_id),
        phase_id,
    )


def _summary(phase: dict[str, Any], bucket: str, reasons: list[str], next_step: str) -> dict[str, Any]:
    return {
        "phase_id": str(phase.get("phase_id", "")),
        "title": str(phase.get("title", "")),
        "track": str(phase.get("track", "")),
        "status": str(phase.get("status", "")),
        "bucket": bucket,
        "risk_level": str(phase.get("risk_level", "")),
        "automation_level": str(phase.get("automation_level", "")),
        "budget_tier": str(phase.get("budget_tier", "")),
        "reasons": list(reasons),
        "recommended_next_step": next_step,
    }


# ── Per-phase rule helpers (deterministic, read-only) ──────────────────────────

def _blocked_reasons(phase: dict[str, Any], status: str, has_error: bool) -> list[str]:
    reasons: list[str] = []
    if not str(phase.get("phase_id", "")).strip():
        reasons.append("phase is missing a phase_id")
    if str(phase.get("budget_tier", "")) == "blocked":
        reasons.append("budget_tier is blocked")
    if str(phase.get("risk_level", "")) == "blocked":
        reasons.append("risk_level is blocked")
    if str(phase.get("automation_level", "")) == FORBIDDEN_AUTOMATION_LEVEL:
        reasons.append(f"automation_level {FORBIDDEN_AUTOMATION_LEVEL} is not allowed")
    if phase.get("merge_allowed") is True:
        reasons.append("merge_allowed is true")
    if phase.get("human_approval_required") is False and status != "complete":
        reasons.append("human_approval_required is false for a non-complete phase")
    if phase.get("writes_real_repo") is True and status in _PREPARABLE_STATUSES:
        reasons.append("writes_real_repo is true for a proposed/active phase")
    allowed = phase.get("allowed_files")
    if not isinstance(allowed, list) or not allowed:
        reasons.append("allowed_files is missing or empty")
    validation = phase.get("validation")
    if not isinstance(validation, list) or not validation:
        reasons.append("validation is missing or empty")
    if has_error:
        reasons.append("phase has ROAD.1 validation errors")
    return reasons


def _sandbox_reasons(phase: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if phase.get("requires_sandbox") is True:
        reasons.append("requires_sandbox is true")
    if str(phase.get("automation_level", "")) == _SANDBOX_AUTOMATION:
        reasons.append(f"automation_level is {_SANDBOX_AUTOMATION}")
    if "patch candidate" in _phase_text(phase):
        reasons.append("phase mentions patch candidate evaluation")
    if _has_patch_or_sandbox_path(phase.get("allowed_files")):
        reasons.append("allowed_files include patch/sandbox-related paths")
    return reasons


def _human_reasons(phase: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if str(phase.get("budget_tier", "")) == _APPROVAL_BUDGET:
        reasons.append("budget_tier requires strong-model approval")
    if phase.get("model_calls_allowed") is True:
        reasons.append("model_calls_allowed is true")
    if phase.get("network_allowed") is True:
        reasons.append("network_allowed is true")
    if str(phase.get("automation_level", "")) == _REMOTE_PR_AUTOMATION:
        reasons.append(f"automation_level is {_REMOTE_PR_AUTOMATION}")
    if str(phase.get("risk_level", "")) == "high":
        reasons.append("risk_level is high")
    return reasons


def _is_safe(phase: dict[str, Any], status: str) -> bool:
    allowed = phase.get("allowed_files")
    validation = phase.get("validation")
    return (
        status in _PREPARABLE_STATUSES
        and str(phase.get("automation_level", "")) in _LOCAL_AUTOMATION
        and str(phase.get("budget_tier", "")) in _PREPARABLE_BUDGETS
        and str(phase.get("risk_level", "")) in _PREPARABLE_RISKS
        and phase.get("network_allowed") is False
        and phase.get("model_calls_allowed") is False
        and phase.get("merge_allowed") is False
        and phase.get("writes_real_repo") is False
        and isinstance(allowed, list) and bool(allowed)
        and isinstance(validation, list) and bool(validation)
    )


def _safe_reasons(phase: dict[str, Any], status: str) -> list[str]:
    return [
        f"status is {status}",
        f"automation_level {phase.get('automation_level')} is local",
        f"budget_tier is {phase.get('budget_tier')}",
        f"risk_level is {phase.get('risk_level')}",
        "no network, model calls, merge, or real-repo writes",
        "allowed_files and validation are declared",
    ]


def _classify(
    phase: dict[str, Any],
    *,
    registry_valid: bool,
    has_error: bool,
    complete_ids: set[str],
) -> dict[str, Any]:
    """Return the phase summary (with bucket + reasons + next step)."""
    status = str(phase.get("status", ""))

    # 1. shipped history.
    if status == "complete":
        return _summary(phase, "complete_or_history", ["status is complete (shipped history)"], "no_action_complete")

    # 2. parked / deferred.
    if status in ("parked", "deferred"):
        return _summary(phase, "deferred_or_parked", [f"status is {status}"], "keep_parked")

    # 3. hard blocked.
    blocked = _blocked_reasons(phase, status, has_error)
    if blocked:
        return _summary(phase, "blocked", blocked, "blocked_until_metadata_fixed")

    # 4. sandbox required.
    sandbox = _sandbox_reasons(phase)
    if sandbox:
        return _summary(phase, "sandbox_required", sandbox, "prepare_sandbox_trial_contract")

    # 5. human approval required.
    human = _human_reasons(phase)
    if human:
        return _summary(phase, "human_approval_required", human, "request_human_approval")

    # 6. safe to prepare (only when the whole registry validated cleanly).
    if registry_valid and _is_safe(phase, status):
        reasons = _safe_reasons(phase, status)
        prereqs = [str(p) for p in (phase.get("prerequisites") or [])]
        unmet = sorted(p for p in prereqs if p not in complete_ids)
        if unmet:
            reasons.append("prerequisites not yet complete: " + ", ".join(unmet))
            next_step = "complete_prerequisites"
        else:
            next_step = "prepare_worker_assignment"
        return _summary(phase, "safe_to_prepare", reasons, next_step)

    # 7. conservative fallback.
    fallback = ["does not meet safe-to-prepare criteria; needs human review"]
    if not registry_valid:
        fallback.append("registry has validation errors")
    return _summary(phase, "human_approval_required", fallback, "request_human_approval")


# ── Picking ───────────────────────────────────────────────────────────────────

def pick_phase_candidates(registry_data: Any) -> dict[str, Any]:
    """Validate (via ROAD.1) and classify every phase into candidate buckets.

    Pure: never mutates ``registry_data`` and never runs anything. Returns a dict
    with ``registry_valid``, ``errors``, ``warnings``, ``phase_count``,
    ``buckets`` (every bucket present, each a ranked list of phase summaries), and
    ``top_recommendation`` (the best safe candidate, or ``None``).
    """
    validation = validate_phase_registry(registry_data)
    registry_valid = bool(validation["is_valid"])
    errors = list(validation["errors"])
    warnings = list(validation["warnings"])

    root = registry_data if isinstance(registry_data, dict) else {}
    raw_phases = root.get("phases")
    phase_dicts = [p for p in raw_phases if isinstance(p, dict)] if isinstance(raw_phases, list) else []

    error_labels = _ids_with_errors(errors)
    complete_ids = {
        str(p.get("phase_id", "")).strip()
        for p in phase_dicts
        if str(p.get("status", "")) == "complete" and str(p.get("phase_id", "")).strip()
    }

    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS}
    for index, phase in enumerate(phase_dicts):
        label = str(phase.get("phase_id", "")).strip() or f"#{index}"
        summary = _classify(
            phase,
            registry_valid=registry_valid,
            has_error=label in error_labels,
            complete_ids=complete_ids,
        )
        buckets[summary["bucket"]].append(summary)

    for name in buckets:
        buckets[name].sort(key=_candidate_sort_key)

    safe = buckets["safe_to_prepare"]
    top_recommendation = dict(safe[0]) if safe else None

    return {
        "registry_valid": registry_valid,
        "errors": errors,
        "warnings": warnings,
        "phase_count": len(phase_dicts),
        "buckets": buckets,
        "top_recommendation": top_recommendation,
    }


# ── Summary ───────────────────────────────────────────────────────────────────

def _boundaries() -> dict[str, bool]:
    return {
        "classifies_metadata_only": True,
        "executes_phases": False,
        "runs_validation_or_benchmarks": False,
        "calls_models": False,
        "applies_patches": False,
        "modifies_real_repo": False,
        "pushes_merges_or_opens_pr": False,
        "contacts_remote_or_chat_or_automation": False,
    }


def summarize_phase_candidates(
    pick_result: dict[str, Any],
    *,
    report_id: str = "",
    created_at: str = "",
    registry_path: str = "",
) -> dict[str, Any]:
    """Shape a ``pick_phase_candidates`` result into a deterministic report record.

    Pure: never runs anything. The named bucket fields hold the same ranked phase
    summaries as ``pick_result['buckets']``.
    """
    buckets = pick_result.get("buckets") or {}
    bucket_counts = {name: len(buckets.get(name) or []) for name in BUCKETS}

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": PHASE_PICKER_GUARDRAIL_NOTE,
        "report_id": str(report_id or ""),
        "created_at": str(created_at or ""),
        "registry_path": str(registry_path or ""),
        "registry_valid": bool(pick_result.get("registry_valid")),
        "phase_count": int(pick_result.get("phase_count", 0) or 0),
        "bucket_counts": bucket_counts,
        "safe_to_prepare": list(buckets.get("safe_to_prepare") or []),
        "sandbox_required": list(buckets.get("sandbox_required") or []),
        "human_approval_required": list(buckets.get("human_approval_required") or []),
        "blocked": list(buckets.get("blocked") or []),
        "deferred_or_parked": list(buckets.get("deferred_or_parked") or []),
        "complete_or_history": list(buckets.get("complete_or_history") or []),
        "top_recommendation": pick_result.get("top_recommendation"),
        "errors": list(pick_result.get("errors") or []),
        "warnings": list(pick_result.get("warnings") or []),
        "boundaries": _boundaries(),
        # ── ROAD.2 guardrail booleans (this tool does none of these) ──
        "executes_phases": False,
        "runs_validation_or_benchmarks": False,
        "model_call_performed": False,
        "applies_patches": False,
        "writes_real_repo": False,
    }


# ── Markdown rendering ────────────────────────────────────────────────────────

_BUCKET_TITLES: tuple[tuple[str, str], ...] = (
    ("safe_to_prepare", "Safe to prepare"),
    ("sandbox_required", "Sandbox required"),
    ("human_approval_required", "Human approval required"),
    ("blocked", "Blocked"),
    ("deferred_or_parked", "Deferred or parked"),
    ("complete_or_history", "Complete or history"),
)


def _render_bucket(lines: list[str], title: str, phases: list[dict[str, Any]]) -> None:
    lines += [f"## {title}", ""]
    if phases:
        lines += [
            "| Phase | Title | Track | Status | Risk | Automation | Budget | Next step | Reasons |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for phase in phases:
            lines.append(
                "| {pid} | {title} | {track} | {status} | {risk} | {auto} | {budget} | {step} | {reasons} |".format(
                    pid=_md(phase.get("phase_id", "")),
                    title=_md(phase.get("title", "")),
                    track=_md(phase.get("track", "")),
                    status=_md(phase.get("status", "")),
                    risk=_md(phase.get("risk_level", "")),
                    auto=_md(phase.get("automation_level", "")),
                    budget=_md(phase.get("budget_tier", "")),
                    step=_md(phase.get("recommended_next_step", "")),
                    reasons=_md("; ".join(phase.get("reasons") or [])),
                )
            )
    else:
        lines.append("_None._")
    lines.append("")


def render_phase_picker_markdown(summary: dict[str, Any]) -> str:
    """Render a summary record as one operator-readable Markdown report."""
    is_valid = bool(summary.get("registry_valid"))
    lines: list[str] = [
        "# Phase Picker / Night Candidate Report",
        "",
        f"> {summary.get('guardrail_note', PHASE_PICKER_GUARDRAIL_NOTE)}",
        "",
        "_Report only: ROAD.2 classifies roadmap phase metadata from the ROAD.1 "
        "registry into candidate buckets. It recommends only; it runs nothing, "
        "changes nothing, and contacts nothing._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(summary.get('report_id') or '(none)')}`",
        f"- **Created at:** `{_md(summary.get('created_at') or '(none)')}`",
        f"- **Registry path:** `{_md(summary.get('registry_path') or '(inline)')}`",
        f"- **Registry valid:** {'VALID' if is_valid else 'INVALID'}",
        f"- **Phase count:** {summary.get('phase_count', 0)}",
        "",
        "| Bucket | Count |",
        "|---|---|",
    ]
    bucket_counts = summary.get("bucket_counts") or {}
    for name in BUCKETS:
        lines.append(f"| {name} | {bucket_counts.get(name, 0)} |")
    lines.append("")

    # Errors / warnings (so an invalid registry explains itself).
    errors = summary.get("errors") or []
    warnings = summary.get("warnings") or []
    if errors:
        lines += ["**Registry errors:**", ""]
        lines += [f"- {_md(error)}" for error in errors]
        lines.append("")
    if warnings:
        lines += ["**Registry warnings:**", ""]
        lines += [f"- {_md(warning)}" for warning in warnings]
        lines.append("")

    # Top recommendation.
    lines += ["## Top recommendation", ""]
    top = summary.get("top_recommendation")
    if top:
        lines.append(
            f"- **{_md(top.get('phase_id', ''))}** — {_md(top.get('title', ''))} "
            f"(risk {_md(top.get('risk_level', ''))}, {_md(top.get('automation_level', ''))}) "
            f"→ `{_md(top.get('recommended_next_step', ''))}`"
        )
    else:
        lines.append("_None. No safe candidate to prepare (registry invalid or no eligible phase)._")
    lines.append("")

    # Buckets.
    for key, title in _BUCKET_TITLES:
        _render_bucket(lines, title, summary.get(key) or [])

    # Boundaries.
    lines += ["## Boundaries", ""]
    lines += [
        "- ROAD.2 does not execute phases.",
        "- ROAD.2 does not run validation or benchmarks.",
        "- ROAD.2 does not call models.",
        "- ROAD.2 does not apply patches.",
        "- ROAD.2 does not push, merge, open PRs, or contact GitHub, Telegram, or N8N "
        "/ external automation.",
        "- ROAD.2 only classifies phase metadata from the registry.",
        "",
    ]
    return "\n".join(lines) + "\n"


# ── Report writing ────────────────────────────────────────────────────────────

def write_phase_picker_report(
    registry_data: Any,
    output_dir: str | Path,
    report_id: str = "",
    created_at: str = "",
    *,
    registry_path: str = "",
) -> dict[str, Any]:
    """Classify the registry and write the JSON + Markdown report artifacts.

    Returns ``{ok, json_path, md_path, report}``. The report content is the same
    deterministic record ``summarize_phase_candidates`` returns; nothing is run.
    """
    pick = pick_phase_candidates(registry_data)
    report = summarize_phase_candidates(
        pick, report_id=report_id, created_at=created_at, registry_path=registry_path
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    md_path.write_text(render_phase_picker_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
