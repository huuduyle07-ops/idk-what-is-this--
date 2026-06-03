"""Deterministic, generation-only review pack generator.

Combines existing operator artifacts into a worker-facing prompt draft. This
module does not write files, call models, create handoffs, run validation, run
benchmarks, start Dream, or touch patch systems.
"""
from __future__ import annotations

import re
from typing import Any, Literal, TypedDict


WorkerTarget = Literal["claude", "codex", "gemini", "generic"]

DEFAULT_FORBIDDEN_FILES = [
    ".env",
    ".agent",
    ".git",
    "node_modules",
    "target",
]

SAFETY_RULES = [
    "Do not apply patches.",
    "Do not commit.",
    "Do not push.",
    "Ask before touching forbidden files.",
    "Report changed files and validation evidence.",
]


class ReviewPackDraft(TypedDict):
    title: str
    worker_target: WorkerTarget
    recommended_mode: str
    task_prompt: str
    evidence_checklist: list[str]
    constraints: list[str]
    allowed_files: list[str]
    forbidden_files: list[str]
    validation_hints: list[str]
    stop_conditions: list[str]
    expected_deliverable: str
    safety_notes: list[str]
    missing_information: list[str]


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


def _nested(mapping: dict[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _normalize_worker_target(value: Any) -> WorkerTarget:
    text = _as_text(value).lower()
    if text in {"claude", "codex", "gemini", "generic"}:
        return text  # type: ignore[return-value]
    return "generic"


def _recommended_mode(goal_brief: dict[str, Any], mode_router_result: dict[str, Any] | None) -> str:
    if isinstance(mode_router_result, dict):
        direct = _as_text(mode_router_result.get("suggested_mode"))
        if direct:
            return direct
        draft = mode_router_result.get("draft")
        if isinstance(draft, dict):
            nested = _as_text(draft.get("suggested_mode"))
            if nested:
                return nested
    return _as_text(goal_brief.get("suggested_mode")) or "unknown"


def _allowed_files(goal_brief: dict[str, Any], handoff_draft: dict[str, Any] | None) -> list[str]:
    values: list[str] = []
    if isinstance(handoff_draft, dict):
        values.extend(_as_list(handoff_draft.get("allowed_files")))
    values.extend(_as_list(goal_brief.get("suspected_files_or_areas")))
    values.extend(_as_list(_nested(goal_brief, "constraints", "allowed_files")))
    return _dedupe(values)


def _forbidden_files(goal_brief: dict[str, Any], handoff_draft: dict[str, Any] | None) -> list[str]:
    values: list[str] = []
    if isinstance(handoff_draft, dict):
        values.extend(_as_list(handoff_draft.get("forbidden_files")))
    values.extend(_as_list(_nested(goal_brief, "constraints", "forbidden_files")))
    for path in DEFAULT_FORBIDDEN_FILES:
        values.append(path)
    return _dedupe(values)


def _validation_hints(goal_brief: dict[str, Any], handoff_draft: dict[str, Any] | None) -> list[str]:
    values: list[str] = []
    values.extend(_as_list(goal_brief.get("validation_hints")))
    values.extend(_as_list(_nested(goal_brief, "validation", "command")))
    if isinstance(handoff_draft, dict):
        values.extend(_as_list(handoff_draft.get("validation_command")))
    return _dedupe(values)


def _constraints(goal_brief: dict[str, Any], handoff_draft: dict[str, Any] | None) -> list[str]:
    values = _as_list(goal_brief.get("constraints"))
    if isinstance(handoff_draft, dict):
        values.extend(_as_list(handoff_draft.get("stop_conditions")))
    values.extend(SAFETY_RULES)
    return _dedupe(values)


def _safety_notes(
    goal_brief: dict[str, Any],
    mode_router_result: dict[str, Any] | None,
    handoff_draft: dict[str, Any] | None,
    forbidden_files: list[str],
) -> list[str]:
    values: list[str] = []
    values.extend(_as_list(goal_brief.get("safety_notes")))
    if isinstance(mode_router_result, dict):
        values.extend(_as_list(mode_router_result.get("risk_notes")))
        draft = mode_router_result.get("draft")
        if isinstance(draft, dict):
            values.extend(_as_list(draft.get("risk_notes")))
    if isinstance(handoff_draft, dict):
        values.extend(_as_list(handoff_draft.get("risk_notes")))
        values.extend(_as_list(handoff_draft.get("safety_notes")))
    for path in forbidden_files:
        values.append(f"Forbidden file preserved: {path}")
    values.extend(SAFETY_RULES)
    return _dedupe(values)


def _missing_information(
    *,
    repo_path: str,
    allowed_files: list[str],
    validation_hints: list[str],
    problem_statement: str,
    desired_outcome: str,
) -> list[str]:
    missing: list[str] = []
    if not repo_path:
        missing.append("TODO: Confirm repo path.")
    if not problem_statement:
        missing.append("TODO: Add the problem statement.")
    if not desired_outcome:
        missing.append("TODO: Add the desired outcome.")
    if not allowed_files:
        missing.append("TODO: Choose allowed files or areas.")
    if not validation_hints:
        missing.append("TODO: Add validation command or evidence expectations.")
    return missing


def _evidence_checklist(validation_hints: list[str], missing_information: list[str]) -> list[str]:
    items = [
        "Confirm the problem statement matches the source Goal Brief.",
        "List every file that would need to change; do not change files in this review pack.",
        "Identify risks, assumptions, and any forbidden-file pressure.",
    ]
    if validation_hints:
        items.append("Report validation evidence for the provided validation hints.")
    else:
        items.append("TODO: Validation evidence cannot be checked until validation hints are provided.")
    items.extend(item for item in missing_information if item.startswith("TODO:"))
    return _dedupe(items)


def _expected_deliverable(mode: str) -> str:
    if mode == "project_evolution":
        return "A reviewable planning prompt with proposed phases, risks, touched areas, and validation evidence to collect."
    if mode == "explain":
        return "A reviewable explanation prompt and evidence checklist; no code changes."
    if mode == "benchmark":
        return "A reviewable benchmark prompt with cases, expected evidence, and validation reporting requirements."
    if mode == "replay":
        return "A reviewable replay prompt with comparison target, expected evidence, and unresolved questions."
    if mode == "dream_trial":
        return "A reviewable research/trial prompt only; no Dream run."
    if mode == "handoff":
        return "A reviewable handoff-style worker prompt draft; no handoff note is created."
    return "A reviewable worker prompt with changed files and validation evidence reported back."


def _target_intro(worker_target: WorkerTarget) -> str:
    labels = {
        "claude": "Claude worker",
        "codex": "Codex worker",
        "gemini": "Gemini worker",
        "generic": "generic worker",
    }
    return labels[worker_target]


def _task_prompt(
    *,
    title: str,
    worker_target: WorkerTarget,
    mode: str,
    repo_path: str,
    problem_statement: str,
    desired_outcome: str,
    allowed_files: list[str],
    forbidden_files: list[str],
    validation_hints: list[str],
    missing_information: list[str],
) -> str:
    mode_line = (
        "This is a planning-oriented review for a broader project evolution task."
        if mode == "project_evolution"
        else f"Recommended workflow mode: {mode}."
    )
    validation_block = "\n".join(f"- {item}" for item in validation_hints) or "- TODO: Add validation command or evidence expectations."
    missing_block = "\n".join(f"- {item}" for item in missing_information) or "- None"
    allowed_block = "\n".join(f"- {item}" for item in allowed_files) or "- TODO: Choose allowed files or areas."
    forbidden_block = "\n".join(f"- {item}" for item in forbidden_files) or "- None"

    return (
        f"You are the {_target_intro(worker_target)} reviewing this operator task.\n\n"
        f"Title: {title}\n"
        f"Repo path: {repo_path or 'TODO: Confirm repo path.'}\n"
        f"{mode_line}\n\n"
        f"Problem statement:\n{problem_statement or 'TODO: Add the problem statement.'}\n\n"
        f"Desired outcome:\n{desired_outcome or 'TODO: Add the desired outcome.'}\n\n"
        "Allowed files or areas:\n"
        f"{allowed_block}\n\n"
        "Forbidden files or areas:\n"
        f"{forbidden_block}\n\n"
        "Validation hints:\n"
        f"{validation_block}\n\n"
        "Safety rules:\n"
        "- Do not apply patches.\n"
        "- Do not commit.\n"
        "- Do not push.\n"
        "- Ask before touching forbidden files.\n"
        "- Report changed files and validation evidence.\n\n"
        "Missing information:\n"
        f"{missing_block}"
    )


def generate_review_pack(
    *,
    goal_brief: dict[str, Any] | None,
    mode_router_result: dict[str, Any] | None = None,
    handoff_draft: dict[str, Any] | None = None,
    repo_path: str | None = None,
    worker_target: str | None = None,
) -> dict[str, Any]:
    source = goal_brief if isinstance(goal_brief, dict) else {}
    title = _as_text(source.get("title")) or _as_text(source.get("goal"))
    problem_statement = _as_text(source.get("problem_statement")) or _as_text(source.get("goal"))
    desired_outcome = _as_text(source.get("desired_outcome")) or _as_text(_nested(source, "evidence", "expected_result"))
    if not title and not problem_statement and not desired_outcome:
        return {"ok": False, "error": "goal_brief must include at least a title, goal, problem_statement, or desired_outcome"}

    target = _normalize_worker_target(worker_target)
    mode = _recommended_mode(source, mode_router_result)
    repo = _as_text(repo_path) or _as_text(source.get("repo_path"))
    if isinstance(handoff_draft, dict):
        repo = repo or _as_text(handoff_draft.get("repo_path"))
    allowed = _allowed_files(source, handoff_draft)
    forbidden = _forbidden_files(source, handoff_draft)
    validation = _validation_hints(source, handoff_draft)
    missing = _missing_information(
        repo_path=repo,
        allowed_files=allowed,
        validation_hints=validation,
        problem_statement=problem_statement,
        desired_outcome=desired_outcome,
    )

    draft: ReviewPackDraft = {
        "title": title or problem_statement[:120] or "Review Pack",
        "worker_target": target,
        "recommended_mode": mode,
        "task_prompt": _task_prompt(
            title=title or problem_statement[:120] or "Review Pack",
            worker_target=target,
            mode=mode,
            repo_path=repo,
            problem_statement=problem_statement,
            desired_outcome=desired_outcome,
            allowed_files=allowed,
            forbidden_files=forbidden,
            validation_hints=validation,
            missing_information=missing,
        ),
        "evidence_checklist": _evidence_checklist(validation, missing),
        "constraints": _constraints(source, handoff_draft),
        "allowed_files": allowed,
        "forbidden_files": forbidden,
        "validation_hints": validation or ["TODO: Add validation command or evidence expectations."],
        "stop_conditions": [
            "Stop if patch application, commits, pushes, validation execution, benchmark execution, Dream, network, Docker, DB writes, or model/API calls are needed.",
            "Stop and ask if forbidden files need to be touched.",
            "Stop and ask if missing information blocks a concrete review.",
        ],
        "expected_deliverable": _expected_deliverable(mode),
        "safety_notes": _safety_notes(source, mode_router_result, handoff_draft, forbidden),
        "missing_information": missing,
    }
    return {"ok": True, "draft": draft}


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def render_review_pack_markdown(draft: ReviewPackDraft | dict[str, Any]) -> str:
    return (
        "# Review Pack\n\n"
        f"## Title\n\n{_as_text(draft.get('title')) or 'Untitled'}\n\n"
        f"## Worker Target\n\n{_as_text(draft.get('worker_target')) or 'generic'}\n\n"
        f"## Recommended Mode\n\n{_as_text(draft.get('recommended_mode')) or 'unknown'}\n\n"
        f"## Task Prompt\n\n{_as_text(draft.get('task_prompt')) or 'Missing'}\n\n"
        "## Evidence Checklist\n\n"
        f"{_bullet_list(list(draft.get('evidence_checklist') or []))}\n\n"
        "## Constraints\n\n"
        f"{_bullet_list(list(draft.get('constraints') or []))}\n\n"
        "## Allowed Files\n\n"
        f"{_bullet_list(list(draft.get('allowed_files') or []))}\n\n"
        "## Forbidden Files\n\n"
        f"{_bullet_list(list(draft.get('forbidden_files') or []))}\n\n"
        "## Validation Hints\n\n"
        f"{_bullet_list(list(draft.get('validation_hints') or []))}\n\n"
        "## Stop Conditions\n\n"
        f"{_bullet_list(list(draft.get('stop_conditions') or []))}\n\n"
        f"## Expected Deliverable\n\n{_as_text(draft.get('expected_deliverable')) or 'Missing'}\n\n"
        "## Safety Notes\n\n"
        f"{_bullet_list(list(draft.get('safety_notes') or []))}\n\n"
        "## Missing Information\n\n"
        f"{_bullet_list(list(draft.get('missing_information') or []))}\n"
    )
