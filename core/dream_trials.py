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


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_BULLET_PREFIX_RE = re.compile(r"^[#\-*]+\s*")
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_FILEPATH_RE = re.compile(r"\b[\w./-]+\.[a-zA-Z]{1,5}\b")


def _split_into_snippets(text: str, max_count: int = 6, max_chars: int = 240) -> list[str]:
    """Split a blob of text into concrete short snippets.

    Phase 4.7d: prefer per-line / per-bullet splits (common for pasted notes
    and markdown headings), and fall back to sentence splits when the text is
    a single line. Each snippet is capped at `max_chars` so the rendered
    Markdown stays readable.
    """
    if not text:
        return []
    candidates: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        stripped = _BULLET_PREFIX_RE.sub("", stripped)
        if stripped:
            candidates.append(stripped)
    if len(candidates) < 2:
        candidates = [c.strip() for c in _SENTENCE_SPLIT_RE.split(text.strip()) if c.strip()]

    snippets: list[str] = []
    for c in candidates:
        if len(snippets) >= max_count:
            break
        if len(c) > max_chars:
            c = c[:max_chars].rstrip() + "..."
        snippets.append(c)
    return snippets


def _extract_surface_hints(text: str) -> list[str]:
    """Best-effort heuristic: find `backticked` tokens and file-path-shaped
    substrings in the inputs so the reasoning chunks can call them out by
    name instead of vague placeholders.
    """
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _BACKTICK_RE.finditer(text):
        tok = m.group(1).strip()
        if tok and tok not in seen:
            seen.add(tok); out.append(tok)
    for m in _FILEPATH_RE.finditer(text):
        tok = m.group(0).strip()
        if tok and tok not in seen and 3 <= len(tok) <= 80:
            seen.add(tok); out.append(tok)
    return out[:8]


def _first_sentence(text: str, max_chars: int = 200) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    parts = _SENTENCE_SPLIT_RE.split(text)
    head = parts[0].strip() if parts else text
    if len(head) > max_chars:
        head = head[:max_chars].rstrip() + "..."
    return head


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
        # Phase 4.7d: split into concrete snippets at line / sentence
        # boundaries instead of dumping one big blob, so the user sees each
        # claim separately and the renderer can show them as bullets.
        evidence.extend(_split_into_snippets(notes_stripped, max_count=6))
    for text in loaded_texts:
        if text.strip():
            evidence.extend(_split_into_snippets(text.strip(), max_count=4, max_chars=600))

    evidence_is_weak = not evidence

    if not notes_stripped:
        assumptions.append(
            "No reference notes were provided; the analysis has no human-supplied anchor."
        )
    if not markdown_files_attempted:
        assumptions.append("No markdown reference files were attached.")
    if evidence_is_weak:
        # Phase 4.7d: explicitly mark weak grounding so the user can't read
        # silence as a clean bill of health.
        assumptions.append(
            "Evidence is weak — the trial proceeds on intuition only, so every "
            "downstream judgment should be treated as low-confidence."
        )

    for path in missing_files:
        unknowns.append(f"Referenced file unavailable: {path}")
    if evidence_is_weak:
        unknowns.append("No grounded evidence is available for this trial.")

    return {
        "evidence": evidence,
        "assumptions": assumptions,
        "unknowns": unknowns,
    }


# ---------------------------------------------------------------------------
# Reasoning scaffolding (no model calls)
# ---------------------------------------------------------------------------

def _build_baseline_answer(
    title: str,
    hint: str,
    reference_notes: str,
    evidence_is_weak: bool,
) -> str:
    """Phase 4.7d: a concrete one-paragraph baseline that interpolates the
    title, hint, and the first sentence of the reference notes. Earlier
    versions were a generic prompt that didn't name the idea concretely.
    """
    parts: list[str] = [
        f"Naively, the idea {title!r} would be evaluated by reading it once and "
        "deciding whether it sounds promising."
    ]
    if hint:
        parts.append(f"The author's hint adds context: \"{hint}\".")
    notes_head = _first_sentence(reference_notes, max_chars=240)
    if notes_head:
        parts.append(f"The reference notes claim: \"{notes_head}\".")
    if evidence_is_weak:
        parts.append(
            "With no grounded evidence attached, the unstructured baseline is to "
            "either shelve the idea or gather more data before any action."
        )
    else:
        parts.append(
            "An unstructured baseline would lean on the cited evidence and the "
            "hint to either pursue or shelve the idea — without an explicit "
            "refutation step."
        )
    parts.append(
        "The structured trial below replaces that ad-hoc baseline with explicit "
        "evidence, refutation, and an auditable decision."
    )
    return " ".join(parts)


def _build_reasoning_chunks(
    title: str,
    hint: str,
    reference_notes: str,
    evidence_is_weak: bool,
    loaded_count: int,
    missing_count: int,
) -> list[dict]:
    """Phase 4.7d: five concrete chunks instead of generic prompts.

    Order matches the brief: problem → surface affected → artifact output
    → risk boundary → next safe action.
    """
    surface_hints = _extract_surface_hints(f"{title}\n{hint}\n{reference_notes}")
    notes_head = _first_sentence(reference_notes, max_chars=160)
    hint_clause = f" Hint: {hint}." if hint else " No hint was provided."
    notes_clause = f" Notes mention: {notes_head}." if notes_head else ""
    surface_clause = (
        f"Surface hints in the inputs: {', '.join(surface_hints)}."
        if surface_hints
        else "No file paths or backticked symbols were detected in the inputs."
    )

    weak_risk_note = (
        "Evidence is weak — any downstream action MUST add grounding first."
        if evidence_is_weak
        else "Detection was heuristic; final scope always needs human read-through."
    )

    safe_next_action_output = (
        "Human review of the artifact. Optionally: gather more grounding evidence "
        "and re-run this trial before proposing a code change."
        if evidence_is_weak
        else "Human review of the artifact. If the judge says recommend_human_approval, "
        "the next allowed step is create_proposal_draft — still report-only."
    )

    missing_clause = (
        f" {missing_count} referenced file(s) could not be read; those rows are unknowns."
        if missing_count
        else f" {loaded_count} referenced file(s) were ingested." if loaded_count
        else " No reference files were attached."
    )

    return [
        {
            "question": "What problem does this idea try to solve?",
            "reasoning": f"Title: {title}.{hint_clause}{notes_clause}",
            "output": (
                f"Problem framing recorded for {title!r}."
                + (f" Surface hints: {', '.join(surface_hints[:5])}." if surface_hints else "")
            ),
            "risk_or_unknown": weak_risk_note,
        },
        {
            "question": "What part of the current system would this touch?",
            "reasoning": surface_clause,
            "output": (
                "Likely affected surface: "
                + (", ".join(surface_hints[:5]) if surface_hints else "unknown until reviewed.")
            ),
            "risk_or_unknown": (
                "Surface detection is a string-match heuristic; treat the list "
                "as a starting point, not a guarantee."
            ),
        },
        {
            "question": "What artifact would a successful trial produce?",
            "reasoning": (
                "Phase 4.7b/c trials produce seven structured markdown files plus "
                "trial.json. No code change is produced in this phase."
            ),
            "output": (
                f"A report-only artifact for human review of {title!r}. "
                "No patch, no commit, no proposal."
            ),
            "risk_or_unknown": (
                "Trial output is artifacts only by construction; no shell-out, "
                "no benchmark execution, no model API calls."
            ),
        },
        {
            "question": "Where is the risk boundary?",
            "reasoning": f"This trial is report-only.{missing_clause}",
            "output": (
                "Strictly out of scope: patch, apply, commit, benchmark execution. "
                "Re-running with code changes is gated by human review of this report."
            ),
            "risk_or_unknown": (
                "If unreviewed, the idea remains an unprocessed candidate."
                if not evidence_is_weak
                else "Evidence is weak — downstream action MUST add grounding."
            ),
        },
        {
            "question": "What is the safe next action?",
            "reasoning": (
                "The judge maps scores + risk to a decision; see 06_judge_report.md."
            ),
            "output": safe_next_action_output,
            "risk_or_unknown": (
                "Heuristic scores are not probabilities; the human is the source of truth."
            ),
        },
    ]


def _build_multi_perspective(
    title: str,
    hint: str,
    reference_notes: str,
    evidence_is_weak: bool,
) -> dict:
    """Phase 4.7d: five concrete views that namedrop the idea and reference
    notes, rather than generic prompt questions."""
    notes_head = _first_sentence(reference_notes, max_chars=160)
    hint_present = bool(hint and hint.strip())

    grounding_clause = (
        f' Reference snippet: "{notes_head}".'
        if notes_head
        else " No reference notes were attached, so this view runs on the title and hint alone."
    )
    weak_clause = (
        " Supporting evidence is weak, so every verdict here is provisional."
        if evidence_is_weak
        else " Supporting evidence is at least partially grounded."
    )

    return {
        "beginner": (
            f"In plain terms, {title!r} proposes a change that is worth a careful read. "
            f"The author's hint says: \"{hint}\"." if hint_present
            else f"In plain terms, {title!r} proposes a change that is worth a careful read. "
            "No hint was attached, so a newcomer reading just the title cannot tell what "
            "the idea concretely changes."
        ) + grounding_clause,
        "professor": (
            f"Rigor check on {title!r}: "
            + (
                "reference notes are attached and form the starting evidence."
                if notes_head
                else "no citations are attached; every claim about the idea stands on author intuition."
            )
            + weak_clause
        ),
        "profit": (
            f"Value-to-effort estimate for {title!r}: "
            + (
                f"the cited evidence — \"{notes_head}\" — hints at upside that must be "
                "verified at production scale before any rollout."
                if notes_head
                else "value cannot be estimated without grounding. Effort is unknown until a proposal draft exists."
            )
        ),
        "maintainer": (
            f"Upkeep view on {title!r}: every new mechanism adds a long tail of edge "
            f"cases, on-call surface, and review burden."
            + (f" The hint hints at the affected surface: \"{hint}\"." if hint_present
               else " No hint was attached to narrow the touched surface.")
        ),
        "safety": (
            f"Failure-mode view on {title!r}: "
            + (
                "cited evidence reduces — but does not eliminate — the risk of a regression "
                "in unrelated areas."
                if notes_head
                else "with no grounding, the worst case is that the idea ships and silently "
                "breaks an unrelated pipeline."
            )
            + " Validation commands and sandbox dry-run are explicitly out of scope for this phase."
        ),
    }


def _build_refutation(
    title: str,
    hint: str,
    reference_notes: str,
    evidence_is_weak: bool,
    missing_count: int,
) -> dict:
    """Phase 4.7d: refutation that quotes the idea concretely and adapts its
    objections to whether evidence is present."""
    notes_head = _first_sentence(reference_notes, max_chars=160)
    missing_clause = (
        f" {missing_count} referenced file(s) could not be read — treat their content as missing sources."
        if missing_count
        else ""
    )

    if evidence_is_weak:
        weakest_assumption = (
            f"The strongest unstated assumption behind {title!r} is that it works at all — "
            f"there is no grounded evidence attached.{missing_clause}"
        )
        worst_case = (
            f"{title!r} is implemented based on intuition; a downstream area silently "
            "regresses and the rollback cost outstrips a pre-commit review."
        )
        simpler_alternative = (
            f"Write a one-paragraph note describing {title!r}, shelve it under "
            "`.agent/dream_trials/` (this report is exactly that), and revisit only "
            "when a concrete pain-point makes the cost / benefit obvious."
        )
    else:
        weakest_assumption = (
            f"The riskiest assumption in {title!r} is that the cited evidence "
            f"generalizes from its source context to this repo.{missing_clause}"
            + (f" The cited claim was: \"{notes_head}\"." if notes_head else "")
        )
        worst_case = (
            f"{title!r} ships, the cited gains do not generalize, and the team spends "
            "more time un-doing it than the pilot ever saved."
        )
        simpler_alternative = (
            f"Run {title!r} as a tiny pilot on the smallest viable scope first, and only "
            "then propose a broader change with measurements."
        )

    second_objection = (
        f"The hint \"{hint}\" provides framing but is not itself evidence."
        if hint and hint.strip()
        else f"No hint was provided, so the framing of {title!r} rests entirely on the title."
    )

    cost_concerns = [
        f"Implementation effort and review burden for {title!r} are not yet estimated.",
        "Token and time cost of any future LLM-based variant is not in scope here.",
    ]
    if missing_count:
        cost_concerns.append(
            "Re-running with the missing reference file(s) resolved would change scoring; "
            "that cost is deferred to a follow-up trial."
        )

    return {
        "main_objections": [weakest_assumption, second_objection],
        "cost_concerns": cost_concerns,
        "worst_case": worst_case,
        "simpler_alternative": simpler_alternative,
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
    # Phase 4.7d: explicit weak-evidence cap. No grounded source → confidence
    # cannot exceed 30 regardless of how many "soft" signals are present.
    if not has_notes and not loaded_count:
        confidence = min(confidence, 30)
    # Phase 4.7d: if more than one referenced file failed to load, treat the
    # uncertainty as a confidence ceiling at 60.
    if missing_count >= 2:
        confidence = min(confidence, 60)
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
    evidence_is_weak = not reference_study["evidence"]
    baseline_answer = _build_baseline_answer(
        title=title,
        hint=hint,
        reference_notes=reference_notes,
        evidence_is_weak=evidence_is_weak,
    )
    reasoning_chunks = _build_reasoning_chunks(
        title=title,
        hint=hint,
        reference_notes=reference_notes,
        evidence_is_weak=evidence_is_weak,
        loaded_count=len(loaded_texts),
        missing_count=len(missing_files),
    )
    multi_perspective = _build_multi_perspective(
        title=title,
        hint=hint,
        reference_notes=reference_notes,
        evidence_is_weak=evidence_is_weak,
    )
    refutation = _build_refutation(
        title=title,
        hint=hint,
        reference_notes=reference_notes,
        evidence_is_weak=evidence_is_weak,
        missing_count=len(missing_files),
    )

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
