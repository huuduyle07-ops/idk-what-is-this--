"""Phase 4.7b — Structured Dream Trial Reports.

Report-only structured reasoning artifacts for idea / research / reference
dream items. Each call writes a trial.json and seven numbered markdown files
into `.agent/dream_trials/<trial_id>/`.

Hard rules for this phase:
- Never patches code.
- Never commits.
- Never runs benchmarks.
- Never calls an LLM / model API.
- recommend_human_approval never auto-approves code changes.

The judge is a deterministic heuristic over the inputs (title / hint /
reference_notes / readable markdown files). It produces scores in [0,100] and
a decision routed by `_compute_decision()`. The decision's allowed/blocked
actions are looked up in `DECISION_POLICY` so the contract is testable as
data, not narrative.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config import get_agent_dir


# Phase 4.7b applies only to idea / research / reference dream types. The
# build-it-now dream types (bug_investigation, debt_cleanup) and the
# patch_if_safe action_level are explicitly rejected at the entry point.
ALLOWED_DREAM_TYPES: frozenset[str] = frozenset({
    "idea_trial",
    "research_study",
    "reference_study",
    "case_idea_research",
})

ALLOWED_ACTION_LEVELS: frozenset[str] = frozenset({"report_only"})


# The full decision contract. Each decision lists what may follow
# (`allowed_actions`) and what is explicitly forbidden (`blocked_actions`).
# Patch / apply / commit appear in every `blocked_actions` so silence cannot
# be mistaken for permission.
DECISION_POLICY: dict[str, dict[str, list[str]]] = {
    "greenlight_report_only": {
        "allowed_actions": ["write_report"],
        "blocked_actions": ["patch", "apply", "commit", "create_proposal_draft"],
    },
    "recommend_human_approval": {
        # Strongest decision still does NOT permit any code change. It only
        # unlocks a draft proposal — itself a write_report-style artifact.
        "allowed_actions": ["write_report", "create_proposal_draft"],
        "blocked_actions": ["patch", "apply", "commit"],
    },
    "needs_human_review": {
        "allowed_actions": ["write_report"],
        "blocked_actions": ["patch", "apply", "commit", "create_proposal_draft"],
    },
    "needs_more_evidence": {
        "allowed_actions": ["write_report"],
        "blocked_actions": ["patch", "apply", "commit", "create_proposal_draft"],
    },
    "rework": {
        "allowed_actions": ["write_report"],
        "blocked_actions": ["patch", "apply", "commit", "create_proposal_draft"],
    },
    "rejected": {
        "allowed_actions": ["archive_report"],
        "blocked_actions": ["patch", "apply", "commit", "create_proposal_draft"],
    },
}


@dataclass
class DreamTrialResult:
    trial_id: str
    trial_dir: str
    trial_path: str
    decision: str
    allowed_actions: list[str]
    blocked_actions: list[str]
    files_written: list[str]


# ---------------------------------------------------------------------------
# Paths / id
# ---------------------------------------------------------------------------

def _trials_root(repo_path: str) -> Path:
    return get_agent_dir(repo_path) / "dream_trials"


def _slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text or "").strip("-").lower()
    return s[:max_len] or "trial"


def _build_trial_id(now: datetime, title: str) -> str:
    return f"{now.strftime('%Y%m%d-%H%M%S')}-{_slugify(title)}"


# ---------------------------------------------------------------------------
# Reference ingestion
# ---------------------------------------------------------------------------

_MAX_PER_FILE_CHARS = 1200


def _read_markdown_files(
    repo_root: Path,
    markdown_files: list[str],
) -> tuple[list[str], list[str], list[dict]]:
    """Best-effort read of referenced markdown files.

    Returns `(loaded_texts, missing_paths, details)` where `details` is a list
    of `{path, status, size?}` dicts the caller renders into the report. A
    file outside the repo, a non-markdown suffix, or an OS read error all
    show up as `unknown` rather than crashing the trial.
    """
    loaded: list[str] = []
    missing: list[str] = []
    details: list[dict] = []
    repo_resolved = repo_root.resolve()

    for raw_path in markdown_files:
        path_text = str(raw_path or "").strip()
        if not path_text:
            continue
        candidate = Path(path_text).expanduser()
        resolved = candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()
        try:
            resolved.relative_to(repo_resolved)
        except ValueError:
            missing.append(path_text)
            details.append({"path": path_text, "status": "outside_repo"})
            continue
        if resolved.suffix.lower() not in {".md", ".markdown"}:
            missing.append(path_text)
            details.append({"path": path_text, "status": "non_markdown"})
            continue
        if not resolved.is_file():
            missing.append(path_text)
            details.append({"path": path_text, "status": "missing"})
            continue
        try:
            text = resolved.read_text(encoding="utf-8")
        except OSError as e:
            missing.append(path_text)
            details.append({"path": path_text, "status": f"unreadable: {e}"})
            continue
        loaded.append(text)
        details.append({"path": path_text, "status": "loaded", "size": len(text)})

    return loaded, missing, details


def _build_reference_study(
    reference_notes: str,
    loaded_texts: list[str],
    missing_files: list[str],
    markdown_files_attempted: bool,
) -> dict:
    evidence: list[str] = []
    assumptions: list[str] = []
    unknowns: list[str] = []

    notes_stripped = reference_notes.strip()
    if notes_stripped:
        evidence.append(notes_stripped)
    for text in loaded_texts:
        if text.strip():
            evidence.append(text.strip()[:_MAX_PER_FILE_CHARS])

    if not notes_stripped:
        assumptions.append("No reference notes were provided; the analysis has no human-supplied anchor.")
    if not markdown_files_attempted:
        assumptions.append("No markdown reference files were attached.")

    for path in missing_files:
        unknowns.append(f"Referenced file unavailable: {path}")
    if not evidence:
        unknowns.append("No grounded evidence is available for this trial.")

    return {
        "evidence": evidence,
        "assumptions": assumptions,
        "unknowns": unknowns,
    }


# ---------------------------------------------------------------------------
# Reasoning scaffolding (no model calls)
# ---------------------------------------------------------------------------

def _build_baseline_answer(title: str, hint: str) -> str:
    hint_part = f" The user's hint was: {hint}." if hint else ""
    return (
        f"Without structured reasoning, the naive answer to {title!r} is to weigh "
        "it against gut feel and either pursue it or shelve it."
        f"{hint_part} The structured trial below replaces that ad-hoc judgment "
        "with explicit evidence, refutation, and an auditable decision."
    )


def _build_reasoning_chunks(title: str, hint: str) -> list[dict]:
    hint_text = hint or "(no hint provided)"
    return [
        {
            "question": "What problem does this idea try to solve?",
            "reasoning": f"Title: {title}. Hint: {hint_text}.",
            "output": "Problem framing captured from input metadata. Deeper framing requires human review.",
            "risk_or_unknown": "Framing is templated, not LLM-generated.",
        },
        {
            "question": "What is the smallest concrete step toward validating the idea?",
            "reasoning": (
                "A report-only trial creates artifacts a human can inspect before any "
                "code change is contemplated."
            ),
            "output": "Generate this trial's reports and queue them for human review.",
            "risk_or_unknown": "If no human reads the report, the idea remains an unprocessed candidate.",
        },
        {
            "question": "What evidence and which unknowns are in front of us?",
            "reasoning": "Evidence, assumptions, and unknowns are split in 01_reference_study.md.",
            "output": "trial.json.reference_study captures the split for programmatic inspection.",
            "risk_or_unknown": "Without further analysis, we cannot tell whether the evidence actually grounds the idea.",
        },
        {
            "question": "What would make this idea look foolish in retrospect?",
            "reasoning": "Refutation surfaces objections, cost concerns, worst case, and a simpler alternative.",
            "output": "See 05_refutation.md for the structured attack on the idea.",
            "risk_or_unknown": "Refutation is heuristic; not a substitute for adversarial human review.",
        },
        {
            "question": "What is the safe next action?",
            "reasoning": "The judge maps scores + risk to a decision via a fixed policy.",
            "output": "See trial.json.allowed_actions for what is permitted now.",
            "risk_or_unknown": "Heuristic scores are not probabilities. Final call always rests with the human.",
        },
    ]


def _build_multi_perspective() -> dict:
    return {
        "beginner": (
            "Explain the idea so a curious newcomer can grasp it without jargon — "
            "what is being proposed and why might it matter?"
        ),
        "professor": (
            "Examine rigor: assumptions, citations, theoretical soundness, and "
            "comparable prior work."
        ),
        "profit": (
            "Will this idea move the needle on the project's real goals? What is "
            "the value-to-effort ratio?"
        ),
        "maintainer": (
            "What does this cost in upkeep, complexity, and on-call surface? Are "
            "there hidden long-term burdens?"
        ),
        "safety": (
            "What goes wrong if this is shipped without sufficient guardrails? "
            "What are the failure modes?"
        ),
    }


def _build_refutation(title: str, hint: str) -> dict:
    hint_clause = f" (hint: {hint})" if hint else ""
    return {
        "main_objections": [
            f"The idea {title!r}{hint_clause} may rest on assumptions that have not been validated.",
            "Without grounded evidence, downstream actions risk being based on speculation.",
        ],
        "cost_concerns": [
            "Implementation effort, prompt-token cost, and review burden are not estimated here.",
            "Maintenance cost over time is unknown without further analysis.",
        ],
        "worst_case": (
            "The idea is implemented before adequate analysis, causes regressions in unrelated areas, "
            "and the team is forced to roll it back at higher cost than a pre-commit review would have."
        ),
        "simpler_alternative": (
            "Write a short note describing the idea and shelve it until a concrete pain point makes "
            "the cost / benefit obvious."
        ),
    }


# ---------------------------------------------------------------------------
# Judge — pure heuristic, no LLM
# ---------------------------------------------------------------------------

def _compute_judge_scores(
    title: str,
    hint: str,
    reference_notes: str,
    loaded_texts: list[str],
    missing_files: list[str],
) -> tuple[int, int, int, str]:
    has_title_substance = bool(title and len(title.split()) >= 2)
    has_hint = bool(hint and hint.strip())
    has_notes = bool(reference_notes and reference_notes.strip())
    loaded_count = len(loaded_texts)
    missing_count = len(missing_files)

    proposal_score = 30
    if has_title_substance: proposal_score += 20
    if has_hint:            proposal_score += 20
    if has_notes:           proposal_score += 20
    if loaded_count >= 1:   proposal_score += 10
    proposal_score = min(100, proposal_score)

    refutation_strength = 30
    if not has_notes:                       refutation_strength += 20
    if missing_count:                       refutation_strength += min(20, 10 * missing_count)
    if loaded_count == 0 and not has_notes: refutation_strength += 20
    refutation_strength = min(100, refutation_strength)

    confidence = 30
    if has_notes:    confidence += 25
    if loaded_count: confidence += 25
    if has_hint:     confidence += 10
    if not has_notes and not loaded_count:
        confidence = min(confidence, 30)
    confidence = min(90, max(0, confidence))

    if has_notes and loaded_count:
        risk = "low"
    elif has_notes or loaded_count:
        risk = "medium"
    else:
        risk = "high"

    return proposal_score, refutation_strength, confidence, risk


def _compute_decision(
    proposal_score: int,
    refutation_strength: int,
    confidence: int,
    risk: str,
    has_evidence: bool,
) -> str:
    """Pure policy routing — same inputs always produce the same decision."""
    if not has_evidence:
        return "needs_more_evidence"
    if refutation_strength >= 90:
        return "rejected"
    if refutation_strength >= 70:
        return "rework"
    if proposal_score >= 80 and refutation_strength < 30 and risk == "low":
        return "recommend_human_approval"
    if proposal_score >= 65 and refutation_strength < 50:
        return "needs_human_review"
    return "greenlight_report_only"


def _build_judge_reason(
    proposal_score: int,
    refutation_strength: int,
    confidence: int,
    risk: str,
    decision: str,
    has_evidence: bool,
    missing_count: int,
) -> str:
    parts: list[str] = [
        f"Scores: proposal={proposal_score}, refutation={refutation_strength}, "
        f"confidence={confidence}, risk={risk}."
    ]
    if not has_evidence:
        parts.append("No evidence is grounded yet, so the decision is capped at needs_more_evidence.")
    if missing_count:
        suffix = "s" if missing_count != 1 else ""
        parts.append(f"{missing_count} referenced file{suffix} could not be read.")
    if refutation_strength >= 70:
        parts.append("Refutation is strong enough that the idea cannot be greenlit as-is.")
    if decision == "recommend_human_approval":
        parts.append("A human must still approve any subsequent proposal or code change.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Markdown renderers
# ---------------------------------------------------------------------------

def _render_reference_study_md(
    reference_study: dict,
    reference_notes: str,
    file_details: list[dict],
) -> str:
    lines = ["# 01 — Reference Study", ""]
    lines.append("## Evidence")
    if reference_study["evidence"]:
        for ev in reference_study["evidence"]:
            snippet = ev if len(ev) <= 300 else ev[:300] + "..."
            lines.append(f"- {snippet}")
    else:
        lines.append("- _No evidence available._")
    lines.append("")
    lines.append("## Assumptions")
    if reference_study["assumptions"]:
        for a in reference_study["assumptions"]:
            lines.append(f"- {a}")
    else:
        lines.append("- _None recorded._")
    lines.append("")
    lines.append("## Unknowns")
    if reference_study["unknowns"]:
        for u in reference_study["unknowns"]:
            lines.append(f"- {u}")
    else:
        lines.append("- _None recorded._")
    lines.append("")
    lines.append("## Source files")
    if file_details:
        for d in file_details:
            extra = f" ({d['size']} chars)" if d.get("size") is not None else ""
            lines.append(f"- `{d['path']}` — {d['status']}{extra}")
    else:
        lines.append("- _No markdown files referenced._")
    lines.append("")
    if reference_notes.strip():
        lines.append("## Reference notes (pasted)")
        lines.append("")
        lines.append(reference_notes.strip())
        lines.append("")
    return "\n".join(lines)


def _render_baseline_md(baseline_answer: str) -> str:
    return (
        "# 02 — Baseline Answer\n\n"
        "The naive answer to the idea, before any structured reasoning.\n\n"
        f"{baseline_answer}\n\n"
        "_Note: Phase 4.7b is scaffolding only — no model calls are used to "
        "expand this baseline._\n"
    )


def _render_reasoning_chunks_md(chunks: list[dict]) -> str:
    lines = ["# 03 — Reasoning Chunks", ""]
    for i, chunk in enumerate(chunks, start=1):
        lines.append(f"## Step {i} — {chunk['question']}")
        lines.append("")
        lines.append(f"**Reasoning:** {chunk['reasoning']}")
        lines.append("")
        lines.append(f"**Output:** {chunk['output']}")
        lines.append("")
        risk = chunk.get("risk_or_unknown") or "(none)"
        lines.append(f"**Risk / unknown:** {risk}")
        lines.append("")
    return "\n".join(lines)


def _render_multi_perspective_md(perspectives: dict) -> str:
    lines = ["# 04 — Multi-Perspective Evaluation", ""]
    for view in ("beginner", "professor", "profit", "maintainer", "safety"):
        lines.append(f"## {view.capitalize()}")
        lines.append("")
        lines.append(perspectives[view])
        lines.append("")
    return "\n".join(lines)


def _render_refutation_md(refutation: dict) -> str:
    lines = ["# 05 — Refutation", "", "## Main objections", ""]
    for obj in refutation["main_objections"]:
        lines.append(f"- {obj}")
    lines.append("")
    lines.append("## Cost concerns")
    lines.append("")
    for cost in refutation["cost_concerns"]:
        lines.append(f"- {cost}")
    lines.append("")
    lines.append("## Worst case")
    lines.append("")
    lines.append(refutation["worst_case"])
    lines.append("")
    lines.append("## Simpler alternative")
    lines.append("")
    lines.append(refutation["simpler_alternative"])
    lines.append("")
    return "\n".join(lines)


def _render_judge_md(judge: dict, allowed: list[str], blocked: list[str]) -> str:
    lines = ["# 06 — Judge Report", ""]
    lines.append(f"- **proposal_score:** {judge['proposal_score']}/100")
    lines.append(f"- **refutation_strength:** {judge['refutation_strength']}/100")
    lines.append(f"- **confidence:** {judge['confidence']}/100")
    lines.append(f"- **risk:** {judge['risk']}")
    lines.append(f"- **decision:** {judge['decision']}")
    lines.append("")
    lines.append("## Reason")
    lines.append("")
    lines.append(judge["reason"])
    lines.append("")
    lines.append("## Allowed actions")
    lines.append("")
    for a in allowed:
        lines.append(f"- `{a}`")
    lines.append("")
    lines.append("## Blocked actions")
    lines.append("")
    for b in blocked:
        lines.append(f"- `{b}`")
    lines.append("")
    return "\n".join(lines)


def _render_final_decision_md(judge: dict, allowed: list[str], blocked: list[str]) -> str:
    lines = ["# 07 — Final Decision", ""]
    lines.append(f"**Decision:** `{judge['decision']}`")
    lines.append("")
    lines.append(f"**Reason:** {judge['reason']}")
    lines.append("")
    lines.append(
        f"**Confidence:** {judge['confidence']}/100 · "
        f"**Risk:** {judge['risk']}"
    )
    lines.append("")
    lines.append("## Allowed actions")
    lines.append("")
    for a in allowed:
        lines.append(f"- `{a}`")
    lines.append("")
    lines.append("## Blocked actions")
    lines.append("")
    for b in blocked:
        lines.append(f"- `{b}`")
    lines.append("")
    lines.append(
        "This is a report-only trial. No code changes, patches, or commits "
        "are produced or implied by this decision."
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def create_structured_dream_trial(
    repo_path: str,
    dream_type: str,
    action_level: str,
    title: str,
    hint: str = "",
    reference_notes: str = "",
    markdown_files: list[str] | None = None,
    now: datetime | None = None,
) -> DreamTrialResult:
    """Create a structured dream-trial report.

    Returns a `DreamTrialResult` describing the trial id, on-disk directory,
    the judge's decision, and the allowed/blocked actions. Raises
    `ValueError` on any input the policy forbids.
    """
    if dream_type not in ALLOWED_DREAM_TYPES:
        raise ValueError(
            f"dream_type {dream_type!r} is not supported by structured trials. "
            f"Allowed: {', '.join(sorted(ALLOWED_DREAM_TYPES))}."
        )
    if action_level not in ALLOWED_ACTION_LEVELS:
        raise ValueError(
            f"action_level {action_level!r} is not supported by structured trials. "
            f"Phase 4.7b is report-only — use 'report_only'."
        )
    if not (title or "").strip():
        raise ValueError("title is required for a structured dream trial.")

    repo_root = Path(repo_path).resolve()
    if not repo_root.is_dir():
        raise ValueError(f"repo_path is not a directory: {repo_path}")

    files = list(markdown_files or [])
    now_dt = now or datetime.now()
    trial_id = _build_trial_id(now_dt, title)
    trial_dir = _trials_root(repo_path) / trial_id
    trial_dir.mkdir(parents=True, exist_ok=True)

    loaded_texts, missing_files, file_details = _read_markdown_files(repo_root, files)
    reference_study = _build_reference_study(
        reference_notes=reference_notes,
        loaded_texts=loaded_texts,
        missing_files=missing_files,
        markdown_files_attempted=bool(files),
    )
    baseline_answer = _build_baseline_answer(title, hint)
    reasoning_chunks = _build_reasoning_chunks(title, hint)
    multi_perspective = _build_multi_perspective()
    refutation = _build_refutation(title, hint)

    proposal_score, refutation_strength, confidence, risk = _compute_judge_scores(
        title=title,
        hint=hint,
        reference_notes=reference_notes,
        loaded_texts=loaded_texts,
        missing_files=missing_files,
    )
    has_evidence = bool(reference_study["evidence"])
    decision = _compute_decision(
        proposal_score=proposal_score,
        refutation_strength=refutation_strength,
        confidence=confidence,
        risk=risk,
        has_evidence=has_evidence,
    )
    reason = _build_judge_reason(
        proposal_score, refutation_strength, confidence, risk, decision,
        has_evidence, len(missing_files),
    )
    policy = DECISION_POLICY[decision]
    allowed_actions = list(policy["allowed_actions"])
    blocked_actions = list(policy["blocked_actions"])

    judge = {
        "proposal_score": proposal_score,
        "refutation_strength": refutation_strength,
        "confidence": confidence,
        "risk": risk,
        "decision": decision,
        "reason": reason,
    }

    payload = {
        "trial_id": trial_id,
        "created_at": now_dt.isoformat(timespec="seconds"),
        "dream_type": dream_type,
        "action_level": action_level,
        "title": title,
        "hint": hint,
        "reference_notes": reference_notes,
        "markdown_files": [d["path"] for d in file_details],
        "markdown_file_details": file_details,
        "status": decision,
        "reference_study": reference_study,
        "baseline_answer": baseline_answer,
        "reasoning_chunks": reasoning_chunks,
        "multi_perspective_evaluation": multi_perspective,
        "refutation": refutation,
        "judge": judge,
        "allowed_actions": allowed_actions,
        "blocked_actions": blocked_actions,
    }

    trial_path = trial_dir / "trial.json"
    trial_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    files_written = ["trial.json"]
    rendered = {
        "01_reference_study.md": _render_reference_study_md(reference_study, reference_notes, file_details),
        "02_baseline_answer.md": _render_baseline_md(baseline_answer),
        "03_reasoning_chunks.md": _render_reasoning_chunks_md(reasoning_chunks),
        "04_multi_perspective_evaluation.md": _render_multi_perspective_md(multi_perspective),
        "05_refutation.md": _render_refutation_md(refutation),
        "06_judge_report.md": _render_judge_md(judge, allowed_actions, blocked_actions),
        "07_final_decision.md": _render_final_decision_md(judge, allowed_actions, blocked_actions),
    }
    for name, content in rendered.items():
        (trial_dir / name).write_text(content, encoding="utf-8")
        files_written.append(name)

    return DreamTrialResult(
        trial_id=trial_id,
        trial_dir=str(trial_dir),
        trial_path=str(trial_path),
        decision=decision,
        allowed_actions=allowed_actions,
        blocked_actions=blocked_actions,
        files_written=files_written,
    )
