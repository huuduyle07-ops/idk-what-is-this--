"""UX.2 — Run Timeline / Progress Surface (passive visibility layer).

Builds a deterministic timeline report that surfaces run progress from existing
or explicitly supplied event state. The timeline shows what happened (or is
happening) during a run: which stage is active, how far along the operator
visibility progress is, which events are blocking, and what the next operator
action is.

Core principle: UX.2 is a passive visibility layer. It does not execute tasks,
run agents, call models, apply patches, run validation, run benchmarks, contact
network services, launch workers, push, merge, or open PRs. It only reads state
that is explicitly supplied to it and writes a report.

This module is stdlib-only and pure apart from ``write_timeline_artifacts``
(which writes two report files). All analysis functions are side-effect-free.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "run_timeline_surface"

#: Ordered standard run stages.
STAGES: tuple[str, ...] = (
    "received",
    "mode_selected",
    "context_loaded",
    "plan_ready",
    "model_work",
    "patch_ready",
    "evidence_ready",
    "validation_ready",
    "review_ready",
    "complete",
)

#: Stage → operator-visibility progress percent when that stage is done.
_STAGE_PROGRESS: dict[str, int] = {
    "received":         10,
    "mode_selected":    20,
    "context_loaded":   30,
    "plan_ready":       40,
    "model_work":       55,
    "patch_ready":      65,
    "evidence_ready":   75,
    "validation_ready": 85,
    "review_ready":     95,
    "complete":         100,
}

#: Event status values.
STATUS_WAITING = "waiting"
STATUS_RUNNING = "running"
STATUS_DONE    = "done"
STATUS_BLOCKED = "blocked"
STATUS_FAILED  = "failed"
STATUS_SKIPPED = "skipped"
STATUS_UNKNOWN = "unknown"

_ACTIVE_STATUSES = (STATUS_RUNNING, STATUS_WAITING)
_DONE_STATUS = STATUS_DONE

#: Timeline report status values.
TIMELINE_STATUS_READY   = "ready_for_review"
TIMELINE_STATUS_RUNNING = "running_snapshot"
TIMELINE_STATUS_BLOCKED = "blocked"
TIMELINE_STATUS_FAILED  = "failed"
TIMELINE_STATUS_EMPTY   = "empty"

#: Artifact file names.
JSON_NAME = "run_timeline_surface.json"
MD_NAME   = "run_timeline_surface.md"

GUARDRAIL_NOTE = (
    "Run Timeline Surface is a passive visibility layer: it surfaces run progress "
    "from existing or explicitly supplied event state. It does not execute tasks, "
    "run agents, call models, apply patches, run validation, run benchmarks, contact "
    "network services, launch workers, push, merge, or open PRs. No backend execution "
    "is changed. Human review is required before any action."
)

#: Human-readable titles for known stages.
_STAGE_TITLES: dict[str, str] = {
    "received":         "Task Received",
    "mode_selected":    "Mode Selected",
    "context_loaded":   "Context Loaded",
    "plan_ready":       "Plan Ready",
    "model_work":       "Model Work",
    "patch_ready":      "Patch Ready",
    "evidence_ready":   "Evidence Ready",
    "validation_ready": "Validation Ready",
    "review_ready":     "Ready for Review",
    "complete":         "Complete",
}

#: Default next-action text by timeline status / stage.
_NEXT_ACTION_COMPLETE   = "Review the result and evidence before taking any action."
_NEXT_ACTION_EMPTY      = "Submit a task to start a new run."
_NEXT_ACTION_FAILED     = "Inspect the failed stage and decide whether to retry or investigate."
_NEXT_ACTION_BLOCKED    = "Resolve the blocking condition before continuing."
_NEXT_ACTION_IN_PROGRESS = "Wait for the current stage to finish, then review."

#: Boundaries enforced by UX.2.
_BOUNDARIES: tuple[str, ...] = (
    "UX.2 is a passive visibility layer.",
    "UX.2 does not execute tasks.",
    "UX.2 does not run agents.",
    "UX.2 does not call models.",
    "UX.2 does not apply patches.",
    "UX.2 does not run validation.",
    "UX.2 does not run benchmarks.",
    "UX.2 does not contact network services.",
    "UX.2 does not launch workers.",
    "UX.2 does not push, merge, or open PRs.",
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _short_id(seed: str) -> str:
    return hashlib.sha1(seed.encode()).hexdigest()[:8]


# ── Event normalisation ───────────────────────────────────────────────────────

def normalize_timeline_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a fully populated timeline event from a raw dict (pure, no I/O)."""
    stage  = str(raw.get("stage", "unknown")).strip() or "unknown"
    status = str(raw.get("status", STATUS_UNKNOWN)).strip() or STATUS_UNKNOWN

    ev: dict[str, Any] = dict(raw)
    ev["stage"]  = stage
    ev["status"] = status

    if not ev.get("event_id"):
        ev["event_id"] = _short_id(f"{stage}:{status}:{ev.get('created_at','')}")
    if not ev.get("title"):
        ev["title"] = _STAGE_TITLES.get(stage, stage.replace("_", " ").title())
    ev.setdefault("summary", "")
    ev.setdefault("details", "")
    ev.setdefault("created_at", "")
    ev.setdefault("source", "timeline")
    ev.setdefault("artifact_path", "")

    # is_current / is_blocking may be supplied or derived
    if "is_current" not in ev:
        ev["is_current"] = status in _ACTIVE_STATUSES
    if "is_blocking" not in ev:
        ev["is_blocking"] = status == STATUS_BLOCKED
    ev.setdefault("next_action", "")

    return ev


# ── Stage / progress analysis ─────────────────────────────────────────────────

def compute_current_stage(events: list[dict[str, Any]]) -> str | None:
    """Return the stage name of the first active (running/waiting) event, or last done, or None."""
    if not events:
        return None
    # First running/waiting stage
    for ev in events:
        if ev.get("status") in _ACTIVE_STATUSES:
            return ev["stage"]
    # All done — return last done stage
    last_done = None
    for ev in events:
        if ev.get("status") == _DONE_STATUS:
            last_done = ev["stage"]
    return last_done


def compute_progress_percent(events: list[dict[str, Any]]) -> int:
    """Return the operator-visibility progress percent (0–100) based on done stages."""
    if not events:
        return 0
    best = 0
    for ev in events:
        if ev.get("status") == _DONE_STATUS:
            stage = ev.get("stage", "")
            pct = _STAGE_PROGRESS.get(stage, 0)
            if pct > best:
                best = pct
    return best


def classify_timeline_status(events: list[dict[str, Any]]) -> str:
    """Classify the overall timeline status from a list of events."""
    if not events:
        return TIMELINE_STATUS_EMPTY
    statuses = {ev.get("status", STATUS_UNKNOWN) for ev in events}
    if STATUS_FAILED in statuses:
        return TIMELINE_STATUS_FAILED
    if STATUS_BLOCKED in statuses:
        return TIMELINE_STATUS_BLOCKED
    if STATUS_RUNNING in statuses or STATUS_WAITING in statuses:
        return TIMELINE_STATUS_RUNNING
    # All done / skipped / unknown — check if complete stage is done
    for ev in events:
        if ev.get("stage") == "complete" and ev.get("status") == _DONE_STATUS:
            return TIMELINE_STATUS_READY
    return TIMELINE_STATUS_RUNNING


def _next_operator_action(timeline_status: str, current_stage: str | None) -> str:
    if timeline_status == TIMELINE_STATUS_EMPTY:
        return _NEXT_ACTION_EMPTY
    if timeline_status == TIMELINE_STATUS_FAILED:
        return _NEXT_ACTION_FAILED
    if timeline_status == TIMELINE_STATUS_BLOCKED:
        return _NEXT_ACTION_BLOCKED
    if timeline_status == TIMELINE_STATUS_READY:
        return _NEXT_ACTION_COMPLETE
    return _NEXT_ACTION_IN_PROGRESS


def _guardrails(ui_visibility_added: bool = False) -> dict[str, bool]:
    return {
        "ui_visibility_added":       ui_visibility_added,
        "backend_execution_changed": False,
        "task_execution_performed":  False,
        "agent_launched":            False,
        "model_call_performed":      False,
        "patch_applied":             False,
        "validation_run":            False,
        "benchmark_run_performed":   False,
        "network_call_performed":    False,
        "database_write_performed":  False,
        "worker_launch_performed":   False,
        "merge_performed":           False,
    }


# ── Report builders ───────────────────────────────────────────────────────────

def build_timeline_from_events(
    events: list[dict[str, Any]],
    *,
    repo_path: str = ".",
    timeline_id: str = "timeline",
    created_at: str = "",
    ui_visibility_added: bool = False,
) -> dict[str, Any]:
    """Build a timeline report from a list of raw events (pure, no I/O)."""
    normalised = [normalize_timeline_event(ev) for ev in events]
    timeline_status = classify_timeline_status(normalised)
    current_stage   = compute_current_stage(normalised)
    progress_pct    = compute_progress_percent(normalised)
    blocking        = [ev for ev in normalised if ev.get("is_blocking") or ev.get("status") == STATUS_BLOCKED]
    completed       = [ev for ev in normalised if ev.get("status") == _DONE_STATUS]
    next_action     = _next_operator_action(timeline_status, current_stage)

    return {
        "report_kind":          REPORT_KIND,
        "timeline_id":          timeline_id,
        "created_at":           created_at,
        "repo_path":            repo_path,
        "timeline_status":      timeline_status,
        "current_stage":        current_stage,
        "progress_percent":     progress_pct,
        "events":               normalised,
        "blocking_events":      blocking,
        "completed_events":     completed,
        "next_operator_action": next_action,
        "warnings":             [],
        "guardrails":           _guardrails(ui_visibility_added),
        "guardrail_note":       GUARDRAIL_NOTE,
        "boundaries":           list(_BOUNDARIES),
    }


def build_default_timeline(
    *,
    repo_path: str = ".",
    timeline_id: str = "timeline",
    created_at: str = "",
    ui_visibility_added: bool = False,
) -> dict[str, Any]:
    """Build a default timeline with all standard stages in waiting status."""
    events = [
        {"stage": s, "status": STATUS_WAITING, "title": _STAGE_TITLES.get(s, s)}
        for s in STAGES
    ]
    return build_timeline_from_events(
        events,
        repo_path=repo_path,
        timeline_id=timeline_id,
        created_at=created_at,
        ui_visibility_added=ui_visibility_added,
    )


def build_demo_timeline(
    *,
    repo_path: str = ".",
    timeline_id: str = "demo",
    created_at: str = "",
) -> dict[str, Any]:
    """Build a static demo timeline from hardcoded local data (no I/O, no network)."""
    demo_events: list[dict[str, Any]] = [
        {"stage": "received",      "status": "done",    "summary": "Task accepted from operator.", "created_at": "2026-06-25T10:00:00+00:00"},
        {"stage": "mode_selected", "status": "done",    "summary": "Instant run selected.", "created_at": "2026-06-25T10:00:01+00:00"},
        {"stage": "context_loaded","status": "done",    "summary": "Context retrieved from repo.", "created_at": "2026-06-25T10:00:03+00:00"},
        {"stage": "plan_ready",    "status": "done",    "summary": "Plan approved.", "created_at": "2026-06-25T10:00:05+00:00"},
        {"stage": "model_work",    "status": "running", "summary": "Model generating answer.", "is_current": True, "created_at": "2026-06-25T10:00:10+00:00"},
        {"stage": "patch_ready",   "status": "waiting", "summary": "Waiting for model to finish.", "created_at": ""},
        {"stage": "evidence_ready","status": "waiting", "summary": "", "created_at": ""},
        {"stage": "validation_ready","status": "waiting","summary": "", "created_at": ""},
        {"stage": "review_ready",  "status": "waiting", "summary": "", "created_at": ""},
        {"stage": "complete",      "status": "waiting", "summary": "", "created_at": ""},
    ]
    return build_timeline_from_events(
        demo_events,
        repo_path=repo_path,
        timeline_id=timeline_id,
        created_at=created_at,
        ui_visibility_added=True,
    )


# ── Markdown renderer ─────────────────────────────────────────────────────────

def _status_icon(status: str) -> str:
    return {
        STATUS_DONE:    "✓",
        STATUS_RUNNING: "▶",
        STATUS_WAITING: "○",
        STATUS_BLOCKED: "✗",
        STATUS_FAILED:  "✗",
        STATUS_SKIPPED: "–",
    }.get(status, "?")


def render_timeline_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Run Timeline / Progress Surface")
    lines.append(f"\n**Timeline ID:** {report.get('timeline_id')}  ")
    lines.append(f"**Created:** {report.get('created_at')}  ")
    lines.append(f"**Timeline Status:** {report.get('timeline_status')}  ")
    lines.append(f"**Repo:** {report.get('repo_path')}\n")

    lines.append("## Summary")
    lines.append(
        "UX.2 surfaces run progress from existing event state. "
        "Progress percentages are operator visibility indicators, not runtime certainty. "
        "No execution is performed; no backend behavior is changed.\n"
    )

    lines.append("## Current Stage")
    cs = report.get("current_stage") or "_None_"
    lines.append(f"**{cs}**\n")

    lines.append("## Progress")
    pct = report.get("progress_percent", 0)
    bar_filled = int(pct / 5)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)
    lines.append(f"Operator visibility progress: **{pct}%**")
    lines.append(f"`[{bar}]`")
    lines.append("_(Progress is an operator visibility indicator, not runtime certainty.)_\n")

    lines.append("## Timeline Events")
    events = report.get("events", [])
    if events:
        lines.append("| Stage | Title | Status | Summary |")
        lines.append("| --- | --- | --- | --- |")
        for ev in events:
            icon   = _status_icon(ev.get("status", "unknown"))
            stage  = ev.get("stage", "")
            title  = ev.get("title", "")
            status = ev.get("status", "")
            summ   = ev.get("summary", "").replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {stage} | {icon} {title} | {status} | {summ} |")
    else:
        lines.append("_No events yet._")
    lines.append("")

    lines.append("## Blocking Events")
    blocking = report.get("blocking_events", [])
    if blocking:
        for ev in blocking:
            lines.append(f"- **{ev.get('stage')}** ({ev.get('status')}): {ev.get('summary', '')}")
    else:
        lines.append("_None._")
    lines.append("")

    lines.append("## Next Operator Action")
    lines.append(report.get("next_operator_action", "_None._"))
    lines.append("")

    lines.append("## Warnings")
    warnings = report.get("warnings", [])
    lines.append("\n".join(f"- {w}" for w in warnings) if warnings else "_None._")
    lines.append("")

    lines.append("## Guardrails")
    gs = report.get("guardrails", {})
    for k, v in gs.items():
        lines.append(f"- `{k}` = `{v}`")
    lines.append("")

    lines.append("## Boundaries")
    for b in report.get("boundaries", []):
        lines.append(f"- {b}")
    lines.append("")
    lines.append(f"> {report.get('guardrail_note', '')}")

    return "\n".join(lines)


# ── I/O writer ────────────────────────────────────────────────────────────────

def write_timeline_artifacts(
    report: dict[str, Any],
    output_root: str,
) -> dict[str, Any]:
    """Write JSON + Markdown artifacts. Returns {ok, json_path, md_path}."""
    out = Path(output_root)
    out.mkdir(parents=True, exist_ok=True)
    jp = out / JSON_NAME
    mp = out / MD_NAME
    jp.write_text(json.dumps(report, indent=2), encoding="utf-8")
    mp.write_text(render_timeline_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(jp), "md_path": str(mp)}
