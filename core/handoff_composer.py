"""Deterministic, draft-only handoff composer.

Converts Goal Brief-like data into a Mayor Mode handoff draft. This module does
not write notes, execute subagents, run validation, call models, or touch
patch/benchmark/Dream systems.
"""
from __future__ import annotations

import re
from typing import Any, TypedDict


DEFAULT_FORBIDDEN_FILES = [
    ".env",
    ".agent",
    ".git",
    "node_modules",
    "target",
    "tests",
]

DEFAULT_SAFETY_NOTES = [
    "Draft only; review before creating a handoff note.",
    "Do not run subagents, generate/apply patches, run validation, run benchmarks, start Dream, write DB records, or promote lessons from this draft.",
    "human_approved_for_proposal is always false until a human explicitly approves outside the composer.",
]

RISKY_PATH_MARKERS = (".env", ".agent", ".git", "node_modules", "target", "tests")


class HandoffDraft(TypedDict):
    title: str
    task_summary: str
    repo_path: str
    allowed_files: list[str]
    forbidden_files: list[str]
    validation_command: str
    risk_notes: list[str]
    stop_conditions: list[str]
    human_approved_for_proposal: bool
    safety_notes: list[str]
    open_questions: list[str]


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _as_text(item)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[,\n]", value)
    elif isinstance(value, (list, tuple, set)):
        parts = list(value)
    else:
        parts = [value]
    return _dedupe([_as_text(part) for part in parts])


def _safe_rel_path(value: Any) -> str | None:
    text = _as_text(value).replace("\\", "/")
    if not text or text.startswith("/") or re.match(r"^[A-Za-z]:/", text):
        return None
    parts = [part for part in text.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        return None
    return "/".join(parts)


def _safe_paths(value: Any) -> list[str]:
    safe: list[str] = []
    for item in _as_list(value):
        path = _safe_rel_path(item)
        if path and path not in safe:
            safe.append(path)
    return safe


def _goal_brief_value(goal_brief: dict[str, Any], *keys: str) -> Any:
    current: Any = goal_brief
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _derive_title(goal_brief: dict[str, Any], fields: dict[str, Any]) -> str:
    title = _as_text(fields.get("title")) or _as_text(goal_brief.get("title")) or _as_text(goal_brief.get("goal"))
    if title:
        return title[:120]
    summary = _as_text(fields.get("task_summary")) or _as_text(goal_brief.get("problem_statement"))
    return (summary[:117] + "...") if len(summary) > 120 else (summary or "Handoff Draft")


def _derive_summary(goal_brief: dict[str, Any], fields: dict[str, Any]) -> str:
    explicit = _as_text(fields.get("task_summary"))
    if explicit:
        return explicit

    parts = [
        _as_text(goal_brief.get("problem_statement")),
        _as_text(goal_brief.get("goal")),
        _as_text(_goal_brief_value(goal_brief, "evidence", "expected_result")),
        _as_text(_goal_brief_value(goal_brief, "evidence", "actual_result")),
        _as_text(_goal_brief_value(goal_brief, "evidence", "error_output")),
        _as_text(_goal_brief_value(goal_brief, "validation", "success_criteria")),
    ]
    return "\n".join(_dedupe(parts)) or "Review the source Goal Brief and prepare a proposal-only handoff."


def _merge_forbidden(user_forbidden: Any, allowed_files: list[str]) -> list[str]:
    forbidden = _safe_paths(user_forbidden)
    for default in DEFAULT_FORBIDDEN_FILES:
        if default not in forbidden:
            forbidden.append(default)
    final: list[str] = []
    for item in forbidden:
        explicitly_allowed = any(path == item or path.startswith(item + "/") for path in allowed_files)
        if explicitly_allowed:
            continue
        final.append(item)
    return final


def _risk_notes(allowed_files: list[str], forbidden_files: list[str]) -> list[str]:
    notes: list[str] = []
    for path in allowed_files:
        for marker in RISKY_PATH_MARKERS:
            if path == marker or path.startswith(marker + "/"):
                notes.append(f"Allowed file overlaps default risky area: {path}")
    for path in forbidden_files:
        if path in DEFAULT_FORBIDDEN_FILES:
            notes.append(f"Default forbidden area remains blocked: {path}")
    return _dedupe(notes)


def _safety_notes(risk_notes: list[str]) -> list[str]:
    notes = DEFAULT_SAFETY_NOTES.copy()
    for risk in risk_notes:
        notes.append(f"Review risk before creating handoff: {risk}")
    return _dedupe(notes)


def _stop_conditions(validation_command: str, allowed_files: list[str]) -> list[str]:
    conditions = [
        "Stop if the task requires editing files outside allowed_files.",
        "Stop if credentials, secrets, .env, .agent, .git, node_modules, or target changes appear necessary.",
        "Stop if the worker would need to apply a patch, commit, push, run Docker, use network, or execute a benchmark/Dream run.",
    ]
    if not allowed_files:
        conditions.append("Stop until the human chooses allowed files.")
    if not validation_command:
        conditions.append("Stop until the human provides a validation command.")
    return conditions


def compose_handoff_draft(
    *,
    goal_brief: dict[str, Any] | None = None,
    repo_path: str | None = None,
    allowed_files: Any = None,
    validation_command: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    source = goal_brief if isinstance(goal_brief, dict) else {}
    title = _derive_title(source, fields)
    task_summary = _derive_summary(source, fields)

    allowed = _safe_paths(
        allowed_files
        if allowed_files is not None
        else fields.get("allowed_files", _goal_brief_value(source, "constraints", "allowed_files"))
    )
    validation = (
        _as_text(validation_command)
        or _as_text(fields.get("validation_command"))
        or _as_text(_goal_brief_value(source, "validation", "command"))
    )
    forbidden = _merge_forbidden(
        fields.get("forbidden_files", _goal_brief_value(source, "constraints", "forbidden_files")),
        allowed,
    )
    risk_notes = _risk_notes(allowed, forbidden)
    open_questions: list[str] = []
    if not allowed:
        open_questions.append("Choose the allowed files for this handoff.")
    if not validation:
        open_questions.append("Provide the validation command for this handoff.")

    draft: HandoffDraft = {
        "title": title,
        "task_summary": task_summary,
        "repo_path": _as_text(repo_path) or _as_text(fields.get("repo_path")),
        "allowed_files": allowed,
        "forbidden_files": forbidden,
        "validation_command": validation,
        "risk_notes": risk_notes,
        "stop_conditions": _stop_conditions(validation, allowed),
        "human_approved_for_proposal": False,
        "safety_notes": _safety_notes(risk_notes),
        "open_questions": open_questions,
    }
    return {"ok": True, "draft": draft}


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def render_handoff_draft_markdown(draft: HandoffDraft | dict[str, Any]) -> str:
    return (
        "# Handoff Draft\n\n"
        f"## Title\n\n{_as_text(draft.get('title')) or 'Untitled'}\n\n"
        f"## Task Summary\n\n{_as_text(draft.get('task_summary')) or 'Missing'}\n\n"
        f"## Repo Path\n\n{_as_text(draft.get('repo_path')) or 'Missing'}\n\n"
        "## Allowed Files\n\n"
        f"{_bullet_list(list(draft.get('allowed_files') or []))}\n\n"
        "## Forbidden Files\n\n"
        f"{_bullet_list(list(draft.get('forbidden_files') or []))}\n\n"
        f"## Validation Command\n\n{_as_text(draft.get('validation_command')) or 'Missing'}\n\n"
        "## Risk Notes\n\n"
        f"{_bullet_list(list(draft.get('risk_notes') or []))}\n\n"
        "## Stop Conditions\n\n"
        f"{_bullet_list(list(draft.get('stop_conditions') or []))}\n\n"
        "## Approval\n\n"
        "human_approved_for_proposal: false\n\n"
        "## Safety Notes\n\n"
        f"{_bullet_list(list(draft.get('safety_notes') or []))}\n\n"
        "## Open Questions\n\n"
        f"{_bullet_list(list(draft.get('open_questions') or []))}\n"
    )
