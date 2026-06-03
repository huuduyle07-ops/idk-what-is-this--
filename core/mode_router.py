"""Deterministic, suggestion-only workflow mode router.

This module explains which workflow mode appears to fit a request. It does not
write files, call models, create handoffs, run validation, run benchmarks,
start Dream, or touch patch systems.
"""
from __future__ import annotations

import re
from typing import Any, Literal, TypedDict


ModeName = Literal[
    "debug",
    "explain",
    "benchmark",
    "replay",
    "dream_trial",
    "project_evolution",
    "handoff",
    "unknown",
]


class ModeRouteDraft(TypedDict):
    suggested_mode: ModeName
    confidence: float
    reasons: list[str]
    why_not_other_modes: list[str]
    risk_notes: list[str]
    required_user_confirmation: bool
    next_safe_action: str


MODE_RULES: tuple[tuple[ModeName, tuple[str, ...]], ...] = (
    ("debug", ("bug", "error", "failing test", "traceback", "small fix", "fix")),
    ("explain", ("explain", "teach", "why", "how does")),
    ("benchmark", ("benchmark", "case", "suite", "regression", "pass rate")),
    ("replay", ("replay", "previous run", "compare", "debug artifact")),
    ("dream_trial", ("dream", "idea", "research", "trial", "refutation")),
    (
        "project_evolution",
        ("migration", "architecture", "multi-file", "provider replacement", "replace provider", "project-wide"),
    ),
    ("handoff", ("delegate", "claude", "codex", "worker", "subagent", "handoff")),
)

MODE_LABELS: dict[ModeName, str] = {
    "debug": "Debug Mode",
    "explain": "Explain Mode",
    "benchmark": "Benchmark Mode",
    "replay": "Replay Mode",
    "dream_trial": "Dream Trial",
    "project_evolution": "Project Evolution Mode",
    "handoff": "Mayor Mode Handoff",
    "unknown": "Unknown",
}

RISK_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("delete files", ("delete files", "delete old files", "remove files", "rm -", "remove-item", "del ")),
    ("edit .env", ("edit .env", ".env")),
    ("install packages", ("install packages", "pip install", "npm install", "pnpm add", "yarn add")),
    ("run shell commands", ("run shell", "shell commands", "execute command", "run command")),
    ("broad project rewrite", ("broad project rewrite", "rewrite project", "project-wide", "whole project")),
    ("credentials/secrets", ("credential", "credentials", "secret", "secrets", "api key", "token")),
    ("handoff/subagent request requires explicit approval", ("delegate", "worker", "subagent", "handoff")),
)


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


def _contains_phrase(text: str, phrase: str) -> bool:
    if " " in phrase or "-" in phrase:
        return phrase in text
    return bool(re.search(rf"\b{re.escape(phrase)}\b", text))


def _context_text(value: dict[str, Any] | None) -> str:
    if not isinstance(value, dict):
        return ""
    parts: list[str] = []
    for key in (
        "title",
        "goal",
        "problem_statement",
        "task_summary",
        "desired_outcome",
        "suggested_mode",
        "validation_command",
    ):
        raw = value.get(key)
        if isinstance(raw, (str, int, float, bool)):
            parts.append(_as_text(raw))
    return " ".join(_dedupe(parts))


def _score_modes(text: str) -> dict[ModeName, list[str]]:
    lowered = text.lower()
    scores: dict[ModeName, list[str]] = {}
    for mode, phrases in MODE_RULES:
        matches = [phrase for phrase in phrases if _contains_phrase(lowered, phrase)]
        if matches:
            scores[mode] = matches
    return scores


def _choose_mode(scores: dict[ModeName, list[str]]) -> tuple[ModeName, float]:
    if not scores:
        return "unknown", 0.2
    ordered_modes = [mode for mode, _ in MODE_RULES]
    best = max(
        scores,
        key=lambda mode: (len(scores[mode]), ordered_modes.index(mode)),
    )
    match_count = len(scores[best])
    competing = sum(1 for mode, matches in scores.items() if mode != best and matches)
    confidence = min(0.95, 0.55 + (0.15 * match_count))
    if competing:
        confidence = max(0.45, confidence - (0.12 * competing))
    return best, round(confidence, 2)


def _reasons(mode: ModeName, scores: dict[ModeName, list[str]]) -> list[str]:
    if mode == "unknown":
        return ["No deterministic mode keywords were found."]
    matches = ", ".join(scores.get(mode, []))
    return [f"Matched {MODE_LABELS[mode]} keywords: {matches}."]


def _why_not_other_modes(mode: ModeName, scores: dict[ModeName, list[str]]) -> list[str]:
    notes: list[str] = []
    for candidate, _ in MODE_RULES:
        if candidate == mode:
            continue
        if candidate in scores:
            notes.append(
                f"{MODE_LABELS[candidate]} also matched ({', '.join(scores[candidate])}) but was weaker."
            )
        else:
            notes.append(f"{MODE_LABELS[candidate]} did not have a stronger keyword signal.")
    if mode != "unknown":
        notes.append("Unknown was not chosen because at least one deterministic mode signal matched.")
    return notes


def _risk_notes(text: str) -> list[str]:
    lowered = text.lower()
    return _dedupe(
        [
            label
            for label, phrases in RISK_RULES
            if any(phrase in lowered for phrase in phrases)
        ]
    )


def _next_safe_action(mode: ModeName) -> str:
    if mode == "unknown":
        return "Ask the user to clarify the intended workflow mode."
    return f"Review this suggestion with the user before opening {MODE_LABELS[mode]}; do not execute actions automatically."


def route_mode(
    user_intent: str,
    *,
    goal_brief: dict[str, Any] | None = None,
    handoff_draft: dict[str, Any] | None = None,
) -> dict[str, Any]:
    intent = _as_text(user_intent)
    goal_text = _context_text(goal_brief)
    handoff_text = _context_text(handoff_draft)
    combined = " ".join(_dedupe([intent, goal_text, handoff_text]))
    if not combined:
        return {
            "ok": False,
            "error": "user_intent must be a non-empty string or include goal/handoff context",
        }

    if handoff_text:
        combined = f"{combined} handoff"

    scores = _score_modes(combined)
    mode, confidence = _choose_mode(scores)
    draft: ModeRouteDraft = {
        "suggested_mode": mode,
        "confidence": confidence,
        "reasons": _reasons(mode, scores),
        "why_not_other_modes": _why_not_other_modes(mode, scores),
        "risk_notes": _risk_notes(combined),
        "required_user_confirmation": True,
        "next_safe_action": _next_safe_action(mode),
    }
    return {"ok": True, "draft": draft}


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def render_mode_route_markdown(draft: ModeRouteDraft | dict[str, Any]) -> str:
    return (
        "# Mode Router Draft\n\n"
        f"## Suggested Mode\n\n{_as_text(draft.get('suggested_mode')) or 'unknown'}\n\n"
        f"## Confidence\n\n{_as_text(draft.get('confidence')) or '0'}\n\n"
        "## Reasons\n\n"
        f"{_bullet_list(list(draft.get('reasons') or []))}\n\n"
        "## Why Not Other Modes\n\n"
        f"{_bullet_list(list(draft.get('why_not_other_modes') or []))}\n\n"
        "## Risk Notes\n\n"
        f"{_bullet_list(list(draft.get('risk_notes') or []))}\n\n"
        "## Required User Confirmation\n\ntrue\n\n"
        f"## Next Safe Action\n\n{_as_text(draft.get('next_safe_action')) or 'Ask the user to confirm the mode.'}\n"
    )
