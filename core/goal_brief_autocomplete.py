"""Deterministic, draft-only Goal Brief autocomplete.

This module formats messy operator intent into a structured draft. It does not
execute commands, call models, write files, or touch patch/benchmark/Dream
systems.
"""
from __future__ import annotations

import re
from typing import Any, Literal, TypedDict


GoalBriefMode = Literal[
    "debug",
    "explain",
    "benchmark",
    "replay",
    "dream",
    "project_evolution",
    "unknown",
]


class GoalBriefDraft(TypedDict):
    title: str
    problem_statement: str
    desired_outcome: str
    suspected_files_or_areas: list[str]
    constraints: list[str]
    safety_notes: list[str]
    suggested_mode: GoalBriefMode
    validation_hints: list[str]
    open_questions: list[str]


MODE_RULES: tuple[tuple[GoalBriefMode, tuple[str, ...]], ...] = (
    ("debug", ("fix", "bug", "error", "traceback", "failing test")),
    ("replay", ("replay", "compare", "previous run")),
    ("benchmark", ("benchmark", "case", "suite", "regression")),
    (
        "project_evolution",
        ("migration", "architecture", "multi-file", "replace provider", "project-wide"),
    ),
    ("dream", ("dream", "idea", "research", "trial")),
    ("explain", ("explain", "teach", "why", "how does")),
)

SAFETY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("delete files", ("delete files", "remove files", "rm -", "remove-item", "del ")),
    ("edit .env", ("edit .env", ".env")),
    ("install packages", ("install packages", "pip install", "npm install", "pnpm add", "yarn add")),
    ("run shell commands", ("run shell", "shell commands", "execute command", "run command")),
    ("broad project rewrite", ("broad project rewrite", "rewrite project", "project-wide", "whole project")),
    ("credentials/secrets", ("credential", "credentials", "secret", "secrets", "api key", "token")),
)

CONSTRAINTS = [
    "Draft only; do not execute actions from this autocomplete draft.",
    "Do not generate or apply patches from autocomplete.",
    "Do not run validation, benchmarks, Dream, subprocesses, Docker, network, model/API calls, or DB writes.",
]

PATH_RE = re.compile(
    r"(?<![\w./\\-])"
    r"((?:[A-Za-z0-9_.-]+[/\\])+[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+|"
    r"[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+)"
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


def suggest_mode(messy_intent: str, mode_hint: str | None = None) -> GoalBriefMode:
    hinted = _as_text(mode_hint).lower()
    allowed = {mode for mode, _ in MODE_RULES} | {"unknown"}
    if hinted in allowed:
        return hinted  # type: ignore[return-value]

    lowered = messy_intent.lower()
    for mode, phrases in MODE_RULES:
        if any(_contains_phrase(lowered, phrase) for phrase in phrases):
            return mode
    return "unknown"


def _extract_paths(text: str) -> list[str]:
    blocked_names = {".env"}
    paths = []
    for match in PATH_RE.finditer(text):
        candidate = match.group(1).replace("\\", "/").strip(".,;:)")
        if candidate.lower() in blocked_names:
            continue
        if "/" not in candidate and not candidate.startswith("test_") and candidate.count(".") == 1:
            prefix, suffix = candidate.rsplit(".", 1)
            if suffix.lower() not in {"py", "js", "ts", "tsx", "jsx", "go", "rs", "html", "css", "json", "md"}:
                continue
            if prefix.lower() in {"e.g", "i.e"}:
                continue
        paths.append(candidate)
    return _dedupe(paths)


def _first_sentence(text: str) -> str:
    match = re.search(r"(.+?)(?:[.!?]\s|$)", text, flags=re.S)
    sentence = _as_text(match.group(1) if match else text)
    return re.sub(r"\s+", " ", sentence)


def _make_title(text: str, mode: GoalBriefMode) -> str:
    sentence = _first_sentence(text)
    if len(sentence) > 84:
        sentence = sentence[:81].rstrip() + "..."
    if mode == "unknown":
        return sentence or "Goal Brief Draft"
    label = mode.replace("_", " ").title()
    if sentence.lower().startswith(label.lower()):
        return sentence
    return f"{label}: {sentence}" if sentence else f"{label} Goal Brief Draft"


def _desired_outcome(text: str, mode: GoalBriefMode) -> str:
    expected_match = re.search(r"(?i)\bexpected\b\s*:?\s*(.+)", text)
    if expected_match:
        return _as_text(expected_match.group(1))
    if mode == "explain":
        return "A clear explanation that answers the operator's question without changing code."
    if mode == "benchmark":
        return "A clear benchmark-oriented brief with target behavior, scope, and validation still to be confirmed."
    if mode == "replay":
        return "A clear replay/comparison brief identifying the prior run and comparison target."
    if mode == "project_evolution":
        return "A scoped project-evolution brief with migration boundaries and validation still to be confirmed."
    if mode == "dream":
        return "A draft research or trial brief only; no Dream run should start from autocomplete."
    return "The expected behavior is confirmed and captured before any action is taken."


def _safety_notes(text: str) -> list[str]:
    lowered = text.lower()
    notes = [
        label
        for label, phrases in SAFETY_RULES
        if any(phrase in lowered for phrase in phrases)
    ]
    return _dedupe(notes)


def _validation_hints(validation_hint: str | None) -> list[str]:
    return _dedupe([_as_text(validation_hint)])


def _open_questions(
    *,
    repo_path: str | None,
    desired_outcome: str,
    validation_hints: list[str],
    suspected_files_or_areas: list[str],
) -> list[str]:
    questions: list[str] = []
    if not _as_text(repo_path):
        questions.append("repo/path unknown")
    if not desired_outcome or desired_outcome.startswith("The expected behavior is confirmed"):
        questions.append("expected behavior unknown")
    if not validation_hints:
        questions.append("validation command unknown")
    if not suspected_files_or_areas:
        questions.append("target files unknown")
    questions.append("user has not said whether patching is allowed")
    return _dedupe(questions)


def autocomplete_goal_brief(
    messy_intent: str,
    *,
    repo_path: str | None = None,
    mode_hint: str | None = None,
    validation_hint: str | None = None,
) -> dict[str, Any]:
    text = _as_text(messy_intent)
    if not text:
        return {"ok": False, "error": "messy_intent must be a non-empty string"}

    mode = suggest_mode(text, mode_hint)
    paths = _extract_paths(text)
    validation_hints = _validation_hints(validation_hint)
    desired_outcome = _desired_outcome(text, mode)
    safety_notes = _safety_notes(text)

    draft: GoalBriefDraft = {
        "title": _make_title(text, mode),
        "problem_statement": text,
        "desired_outcome": desired_outcome,
        "suspected_files_or_areas": paths,
        "constraints": CONSTRAINTS.copy(),
        "safety_notes": safety_notes,
        "suggested_mode": mode,
        "validation_hints": validation_hints,
        "open_questions": _open_questions(
            repo_path=repo_path,
            desired_outcome=desired_outcome,
            validation_hints=validation_hints,
            suspected_files_or_areas=paths,
        ),
    }
    return {"ok": True, "draft": draft}


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def render_goal_brief_draft_markdown(draft: GoalBriefDraft | dict[str, Any]) -> str:
    return (
        "# Goal Brief Draft\n\n"
        f"## Title\n\n{_as_text(draft.get('title')) or 'Untitled'}\n\n"
        f"## Problem Statement\n\n{_as_text(draft.get('problem_statement')) or 'Missing'}\n\n"
        f"## Desired Outcome\n\n{_as_text(draft.get('desired_outcome')) or 'Missing'}\n\n"
        "## Suspected Files Or Areas\n\n"
        f"{_bullet_list(list(draft.get('suspected_files_or_areas') or []))}\n\n"
        "## Constraints\n\n"
        f"{_bullet_list(list(draft.get('constraints') or []))}\n\n"
        "## Safety Notes\n\n"
        f"{_bullet_list(list(draft.get('safety_notes') or []))}\n\n"
        f"## Suggested Mode\n\n{_as_text(draft.get('suggested_mode')) or 'unknown'}\n\n"
        "## Validation Hints\n\n"
        f"{_bullet_list(list(draft.get('validation_hints') or []))}\n\n"
        "## Open Questions\n\n"
        f"{_bullet_list(list(draft.get('open_questions') or []))}\n"
    )
