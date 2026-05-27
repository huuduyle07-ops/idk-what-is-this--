"""Phase 4.7d — Structured Trial Content Enrichment.

Phase 4.7b shipped a working scaffolding but the section bodies were largely
generic prompt-questions. These tests pin the new contract:

- Rich input shows up concretely in reference / evaluation / refutation.
- Empty / minimal input cannot produce an overconfident decision.
- Markdown sections are not made of only-question placeholders.
- Missing markdown files still land in `unknowns` (regression guard).
- patch / apply / commit remain blocked.
- No model / benchmark / shell-out / patch-executor imports leak in.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import dream_trials


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    return r


# ---------------------------------------------------------------------------
# Rich input must surface concretely in the report bodies.
# ---------------------------------------------------------------------------

def test_rich_reference_notes_surface_in_reference_evaluation_and_refutation(repo):
    notes = (
        "We piloted heuristic X on dataset D and saw a 12% latency reduction. "
        "Memory grew 30%. Production scale impact is untested."
    )
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="idea_trial",
        action_level="report_only",
        title="Adopt heuristic X for retrieval",
        hint="memory budget is a concern",
        reference_notes=notes,
    )
    trial_dir = Path(result.trial_dir)
    ref_md = (trial_dir / "01_reference_study.md").read_text(encoding="utf-8").lower()
    eval_md = (trial_dir / "04_multi_perspective_evaluation.md").read_text(encoding="utf-8").lower()
    refut_md = (trial_dir / "05_refutation.md").read_text(encoding="utf-8").lower()

    # Reference Study must surface the specific claims from the notes.
    assert "heuristic x" in ref_md or "12%" in ref_md or "memory" in ref_md
    # The multi-perspective and refutation sections must reference the actual
    # idea, not generic prompt text.
    assert "heuristic x" in eval_md or "retrieval" in eval_md
    assert "heuristic x" in refut_md or "retrieval" in refut_md or "memory" in refut_md


def test_baseline_answer_mentions_the_idea_and_is_not_just_a_question(repo):
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="idea_trial",
        action_level="report_only",
        title="Adopt cache layer for embeddings",
        hint="reduce DB pressure on hot path",
        reference_notes="Prior benchmarks show 2x improvement.",
    )
    body = (Path(result.trial_dir) / "02_baseline_answer.md").read_text(encoding="utf-8")
    assert "Adopt cache layer" in body
    # The baseline answer body must include declarative content, not only an
    # interrogative prompt sentence.
    non_heading_lines = [
        ln.strip()
        for ln in body.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    statement_lines = [
        ln for ln in non_heading_lines if not ln.endswith("?")
    ]
    assert len(statement_lines) >= 2, body


def test_reasoning_chunks_are_concrete_and_in_count_range(repo):
    notes = "We are exploring whether caching helps for the embeddings lookup hot path."
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="idea_trial",
        action_level="report_only",
        title="Cache embeddings for retrieval",
        hint="reduce DB pressure",
        reference_notes=notes,
    )
    data = json.loads(Path(result.trial_path).read_text(encoding="utf-8"))
    chunks = data["reasoning_chunks"]
    assert 3 <= len(chunks) <= 7
    joined = " ".join(c.get("output", "") for c in chunks).lower()
    assert "cache" in joined or "embeddings" in joined or "retrieval" in joined
    # Every chunk has all four structural fields with non-empty content.
    for c in chunks:
        for key in ("question", "reasoning", "output", "risk_or_unknown"):
            assert key in c, f"missing key {key} in chunk: {c!r}"
            assert c[key].strip(), f"empty {key} in chunk: {c!r}"


def test_multi_perspective_evaluation_views_are_not_only_questions(repo):
    """Phase 4.7b shipped views like
       'Explain the idea so a curious newcomer can grasp it ... ?'
    Phase 4.7d must replace those with concrete analysis — at minimum,
    no view body is allowed to be a single question."""
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="idea_trial",
        action_level="report_only",
        title="Adopt pilot pattern Z for the retrieval pipeline",
        hint="Already measured small-scale wins",
        reference_notes="Initial pilot reduced latency by 40%; memory stable.",
    )
    data = json.loads(Path(result.trial_path).read_text(encoding="utf-8"))
    perspectives = data["multi_perspective_evaluation"]
    for view in ("beginner", "professor", "profit", "maintainer", "safety"):
        text = perspectives[view].strip()
        assert text, f"view {view} is empty"
        # A view made of only question marks (no declarative content) is the
        # specific Phase 4.7b placeholder we are replacing.
        question_count = text.count("?")
        statement_count = text.count(".")
        assert statement_count >= 1, (
            f"view {view!r} contains no declarative sentences: {text!r}"
        )
        # And the rich-input title should appear somewhere across the views.
    blob = " ".join(perspectives[v] for v in perspectives).lower()
    assert "pilot" in blob or "pattern" in blob or "retrieval" in blob


def test_refutation_main_objections_reference_the_idea(repo):
    notes = "We have no clear data on production-scale impact."
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="idea_trial",
        action_level="report_only",
        title="Roll out idea Q globally",
        hint="Pilot was tiny",
        reference_notes=notes,
    )
    data = json.loads(Path(result.trial_path).read_text(encoding="utf-8"))
    refut = data["refutation"]
    objections_text = " ".join(refut["main_objections"]).lower()
    # The title or its key words must show up in the objections.
    assert any(
        token in objections_text
        for token in ("idea q", "roll out", "globally", "global", "idea")
    ), refut["main_objections"]
    # Worst-case is not a generic templated sentence — it should namedrop the idea.
    assert refut["worst_case"], refut
    assert any(
        token in refut["worst_case"].lower()
        for token in ("idea q", "roll out", "globally", "production-scale", "idea")
    )


# ---------------------------------------------------------------------------
# Weak evidence must be flagged, not silently masked.
# ---------------------------------------------------------------------------

def test_reference_study_explicitly_says_evidence_is_weak_when_no_input(repo):
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="idea_trial",
        action_level="report_only",
        title="Something vague",
    )
    data = json.loads(Path(result.trial_path).read_text(encoding="utf-8"))
    # Either assumptions or unknowns must mention the word "weak" so the
    # user sees the warning without having to read every section.
    blob = (
        " ".join(data["reference_study"]["assumptions"])
        + " "
        + " ".join(data["reference_study"]["unknowns"])
    ).lower()
    assert "weak" in blob, data["reference_study"]


def test_empty_input_does_not_produce_overconfident_decision(repo):
    """Empty / minimal input cannot land on recommend_human_approval or
    greenlight_report_only — those imply a level of grounding we don't have."""
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="idea_trial",
        action_level="report_only",
        title="X",  # one word, no substance
    )
    assert result.decision != "recommend_human_approval"
    # And the decision should explicitly land on one of the cautious states.
    assert result.decision in {
        "needs_more_evidence",
        "needs_human_review",
        "rework",
        "rejected",
    }


def test_judge_confidence_is_capped_when_evidence_weak(repo):
    """With no notes and no loaded files, confidence cannot exceed 40."""
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="idea_trial",
        action_level="report_only",
        title="Some thing without grounding",
        hint="hint only, no evidence",
    )
    data = json.loads(Path(result.trial_path).read_text(encoding="utf-8"))
    assert data["judge"]["confidence"] <= 40, data["judge"]
    assert data["judge"]["decision"] != "recommend_human_approval"


# ---------------------------------------------------------------------------
# Invariants that Phase 4.7d must not regress.
# ---------------------------------------------------------------------------

def test_recommend_human_approval_policy_still_blocks_code_changes():
    """The strongest decision must still block patch / apply / commit even
    after content enrichment."""
    policy = dream_trials.DECISION_POLICY["recommend_human_approval"]
    assert "patch" not in policy["allowed_actions"]
    assert "apply" not in policy["allowed_actions"]
    assert "commit" not in policy["allowed_actions"]
    assert {"patch", "apply", "commit"} <= set(policy["blocked_actions"])


def test_every_decision_still_blocks_code_changes():
    for name, policy in dream_trials.DECISION_POLICY.items():
        assert "patch" not in policy["allowed_actions"], name
        assert "apply" not in policy["allowed_actions"], name
        assert "commit" not in policy["allowed_actions"], name
        assert {"patch", "apply", "commit"} <= set(policy["blocked_actions"]), name


def test_missing_markdown_still_lands_in_unknowns_after_enrichment(repo):
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="reference_study",
        action_level="report_only",
        title="missing-file probe",
        markdown_files=["does/not/exist.md"],
    )
    data = json.loads(Path(result.trial_path).read_text(encoding="utf-8"))
    unknowns = " ".join(data["reference_study"]["unknowns"])
    assert "does/not/exist.md" in unknowns or "exist.md" in unknowns


def test_phase_4_7d_keeps_module_import_pure():
    """No model, benchmark, shell-out, or patch-executor imports leaked in."""
    src = Path(dream_trials.__file__).read_text(encoding="utf-8")
    src_lower = src.lower()
    for needle in (
        "subprocess",
        "patch_engine",
        "patch_plan_executor",
        "run_patch_plan",
        "patch_planner",
        "run_benchmarks",
        "benchmark_runner",
        "anthropic",
        "openai",
        "google.genai",
        "litellm",
        "run_gemini_request",
        "agents.gemini_client",
        "agents.deepseek_client",
        "agents.ollama_client",
    ):
        assert needle.lower() not in src_lower, f"forbidden import leaked: {needle}"
