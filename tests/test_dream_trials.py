"""Phase 4.7b — Structured dream-trial reports.

Report-only structured reasoning artifacts. Tests must verify:
- The 7 markdown files + trial.json are created.
- The trial.json schema is stable.
- Only the allowed dream_types are accepted.
- Missing reference files are recorded as unknowns (never crash).
- Decision policy never auto-approves code changes.
- The module is import-pure: no benchmark / patch_executor / model API imports.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

from core import dream_trials


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    return r


# ---------------------------------------------------------------------------
# File creation + schema
# ---------------------------------------------------------------------------

def test_creates_all_expected_files(repo):
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="idea_trial",
        action_level="report_only",
        title="Try X out as a tiny experiment",
    )
    trial_dir = Path(result.trial_dir)
    assert trial_dir.is_dir()

    expected = {
        "trial.json",
        "01_reference_study.md",
        "02_baseline_answer.md",
        "03_reasoning_chunks.md",
        "04_multi_perspective_evaluation.md",
        "05_refutation.md",
        "06_judge_report.md",
        "07_final_decision.md",
    }
    actual = {p.name for p in trial_dir.iterdir() if p.is_file()}
    assert expected <= actual, f"missing files: {expected - actual}"


def test_trial_json_contains_stable_schema(repo):
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="idea_trial",
        action_level="report_only",
        title="Try X",
        hint="some hint",
        reference_notes="some notes",
    )
    data = json.loads(Path(result.trial_path).read_text(encoding="utf-8"))

    required_top = {
        "trial_id", "created_at", "dream_type", "action_level",
        "title", "hint", "reference_notes", "markdown_files", "status",
        "reference_study", "baseline_answer", "reasoning_chunks",
        "multi_perspective_evaluation", "refutation", "judge",
        "allowed_actions", "blocked_actions",
    }
    assert required_top <= set(data.keys()), (
        f"missing top-level keys: {required_top - set(data.keys())}"
    )
    assert {"evidence", "assumptions", "unknowns"} <= set(data["reference_study"])
    assert {"beginner", "professor", "profit", "maintainer", "safety"} <= set(
        data["multi_perspective_evaluation"]
    )
    assert {"main_objections", "cost_concerns", "worst_case", "simpler_alternative"} <= set(
        data["refutation"]
    )
    assert {"proposal_score", "refutation_strength", "confidence", "risk", "decision", "reason"} <= set(
        data["judge"]
    )


def test_trial_id_is_deterministic_when_now_is_pinned(repo):
    fixed = datetime(2026, 5, 27, 12, 30, 45)
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="idea_trial",
        action_level="report_only",
        title="Adventure",
        now=fixed,
    )
    assert result.trial_id.startswith("20260527-123045-")
    assert "adventure" in result.trial_id


# ---------------------------------------------------------------------------
# Allowed/disallowed dream_types
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dream_type", [
    "idea_trial",
    "research_study",
    "reference_study",
    "case_idea_research",
])
def test_applies_to_allowed_dream_types(repo, dream_type):
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type=dream_type,
        action_level="report_only",
        title="t",
    )
    assert Path(result.trial_dir).is_dir()
    data = json.loads(Path(result.trial_path).read_text(encoding="utf-8"))
    assert data["dream_type"] == dream_type


@pytest.mark.parametrize("dream_type", ["bug_investigation", "debt_cleanup"])
def test_rejects_disallowed_dream_types(repo, dream_type):
    with pytest.raises(ValueError) as exc:
        dream_trials.create_structured_dream_trial(
            repo_path=str(repo),
            dream_type=dream_type,
            action_level="report_only",
            title="t",
        )
    assert dream_type in str(exc.value)


def test_rejects_action_level_patch_if_safe(repo):
    """Phase 4.7b is report-only — patch_if_safe action_level is rejected."""
    with pytest.raises(ValueError) as exc:
        dream_trials.create_structured_dream_trial(
            repo_path=str(repo),
            dream_type="idea_trial",
            action_level="patch_if_safe",
            title="t",
        )
    assert "report_only" in str(exc.value)


def test_rejects_empty_title(repo):
    with pytest.raises(ValueError):
        dream_trials.create_structured_dream_trial(
            repo_path=str(repo),
            dream_type="idea_trial",
            action_level="report_only",
            title="   ",
        )


# ---------------------------------------------------------------------------
# Markdown file ingestion
# ---------------------------------------------------------------------------

def test_missing_markdown_file_recorded_as_unknown_not_crash(repo):
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="reference_study",
        action_level="report_only",
        title="ref study",
        markdown_files=["does/not/exist.md"],
    )
    data = json.loads(Path(result.trial_path).read_text(encoding="utf-8"))
    unknowns = " ".join(data["reference_study"]["unknowns"])
    assert "does/not/exist.md" in unknowns or "exist.md" in unknowns
    # 01_reference_study.md must mention the missing file too.
    text = (Path(result.trial_dir) / "01_reference_study.md").read_text(encoding="utf-8")
    assert "does/not/exist.md" in text or "exist.md" in text


def test_existing_markdown_file_lands_in_evidence(repo):
    ref = repo / "notes.md"
    ref.write_text("# Title\n\nReal grounded content.\n", encoding="utf-8")
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="reference_study",
        action_level="report_only",
        title="ref study",
        markdown_files=["notes.md"],
    )
    data = json.loads(Path(result.trial_path).read_text(encoding="utf-8"))
    evidence_joined = " ".join(data["reference_study"]["evidence"])
    assert "Real grounded content" in evidence_joined


def test_path_traversal_markdown_file_is_recorded_as_unknown(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")

    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="reference_study",
        action_level="report_only",
        title="traversal probe",
        markdown_files=["../outside.md"],
    )
    data = json.loads(Path(result.trial_path).read_text(encoding="utf-8"))
    evidence_joined = " ".join(data["reference_study"]["evidence"])
    assert "secret" not in evidence_joined
    unknowns_joined = " ".join(data["reference_study"]["unknowns"])
    assert "outside.md" in unknowns_joined


# ---------------------------------------------------------------------------
# Reference notes
# ---------------------------------------------------------------------------

def test_reference_notes_included_in_trial_and_markdown(repo):
    notes = "Important context: this is a research study about thing X"
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="research_study",
        action_level="report_only",
        title="ref",
        reference_notes=notes,
    )
    data = json.loads(Path(result.trial_path).read_text(encoding="utf-8"))
    assert data["reference_notes"] == notes
    text = (Path(result.trial_dir) / "01_reference_study.md").read_text(encoding="utf-8")
    assert "Important context" in text


def test_evidence_assumptions_unknowns_are_separated(repo):
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="idea_trial",
        action_level="report_only",
        title="separation",
        reference_notes="EVIDENCE_NEEDLE",
        markdown_files=["missing.md"],
    )
    data = json.loads(Path(result.trial_path).read_text(encoding="utf-8"))
    rs = data["reference_study"]
    assert isinstance(rs["evidence"], list)
    assert isinstance(rs["assumptions"], list)
    assert isinstance(rs["unknowns"], list)
    assert any("EVIDENCE_NEEDLE" in e for e in rs["evidence"])
    assert any("missing.md" in u for u in rs["unknowns"])


# ---------------------------------------------------------------------------
# Decision policy — the critical safety surface for this phase
# ---------------------------------------------------------------------------

def test_decision_policy_blocks_patch_apply_commit_for_every_decision():
    for name, policy in dream_trials.DECISION_POLICY.items():
        assert "patch" not in policy["allowed_actions"], name
        assert "apply" not in policy["allowed_actions"], name
        assert "commit" not in policy["allowed_actions"], name
        # Every decision must explicitly block patch+apply+commit so the UI /
        # downstream code can't accidentally interpret silence as permission.
        assert {"patch", "apply", "commit"} <= set(policy["blocked_actions"]), name


def test_recommend_human_approval_does_not_auto_approve_code_changes():
    policy = dream_trials.DECISION_POLICY["recommend_human_approval"]
    assert "patch" not in policy["allowed_actions"]
    assert "apply" not in policy["allowed_actions"]
    assert "commit" not in policy["allowed_actions"]
    assert {"patch", "apply", "commit"} <= set(policy["blocked_actions"])
    # The only "extra" privilege it unlocks is drafting a proposal — which is
    # itself a write_report-style action, not a code change.
    assert "create_proposal_draft" in policy["allowed_actions"]


def test_trial_result_actions_match_decision_policy(repo):
    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="idea_trial",
        action_level="report_only",
        title="actions-match-policy",
    )
    policy = dream_trials.DECISION_POLICY[result.decision]
    assert result.allowed_actions == policy["allowed_actions"]
    assert result.blocked_actions == policy["blocked_actions"]


# ---------------------------------------------------------------------------
# _compute_decision — pure-function unit tests for the routing rules
# ---------------------------------------------------------------------------

def test_compute_decision_recommend_human_approval():
    assert dream_trials._compute_decision(
        proposal_score=85, refutation_strength=20, confidence=70,
        risk="low", has_evidence=True,
    ) == "recommend_human_approval"


def test_compute_decision_needs_human_review_for_middle_scores():
    assert dream_trials._compute_decision(
        proposal_score=70, refutation_strength=40, confidence=50,
        risk="medium", has_evidence=True,
    ) == "needs_human_review"


def test_compute_decision_rework_when_refutation_strong():
    assert dream_trials._compute_decision(
        proposal_score=70, refutation_strength=75, confidence=40,
        risk="high", has_evidence=True,
    ) == "rework"


def test_compute_decision_rejected_when_refutation_overwhelming():
    assert dream_trials._compute_decision(
        proposal_score=70, refutation_strength=95, confidence=20,
        risk="high", has_evidence=True,
    ) == "rejected"


def test_compute_decision_needs_more_evidence_when_no_evidence():
    assert dream_trials._compute_decision(
        proposal_score=85, refutation_strength=10, confidence=80,
        risk="low", has_evidence=False,
    ) == "needs_more_evidence"


def test_compute_decision_falls_back_to_greenlight_report_only():
    assert dream_trials._compute_decision(
        proposal_score=40, refutation_strength=20, confidence=40,
        risk="medium", has_evidence=True,
    ) == "greenlight_report_only"


# ---------------------------------------------------------------------------
# Side-effect guards (the "do NOT" list from the Phase 4.7b brief)
# ---------------------------------------------------------------------------

def test_module_has_no_benchmark_runtime_imports():
    src = Path(dream_trials.__file__).read_text(encoding="utf-8")
    for needle in ("run_benchmarks", "benchmark_runner", "benchmark_report"):
        assert needle not in src, f"benchmark import leaked: {needle}"


def test_module_has_no_patch_executor_imports():
    src = Path(dream_trials.__file__).read_text(encoding="utf-8")
    for needle in (
        "patch_engine",
        "patch_plan_executor",
        "run_patch_plan",
        "patch_planner",
        "subprocess",
    ):
        assert needle not in src, f"patch / shell import leaked: {needle}"


def test_module_has_no_model_api_calls():
    src = Path(dream_trials.__file__).read_text(encoding="utf-8")
    src_lower = src.lower()
    for needle in (
        "run_gemini_request",
        "anthropic",
        "openai",
        "google.genai",
        "litellm",
        "agents.gemini_client",
        "agents.deepseek_client",
        "agents.ollama_client",
    ):
        assert needle.lower() not in src_lower, f"model client leaked: {needle}"


# ---------------------------------------------------------------------------
# CLI (scripts/create_dream_trial.py)
# ---------------------------------------------------------------------------

def _import_cli():
    """Import scripts/create_dream_trial.py as a module."""
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "create_dream_trial.py"
    if str(script_path.parent.parent) not in sys.path:
        sys.path.insert(0, str(script_path.parent.parent))
    import importlib.util
    spec = importlib.util.spec_from_file_location("create_dream_trial", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_creates_trial_when_args_are_valid(repo, capsys):
    cli = _import_cli()
    exit_code = cli.main([
        "--repo", str(repo),
        "--dream-type", "idea_trial",
        "--action-level", "report_only",
        "--title", "Test trial",
    ])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Trial written" in out
    assert "Decision" in out


def test_cli_returns_nonzero_on_invalid_dream_type(repo, capsys):
    cli = _import_cli()
    exit_code = cli.main([
        "--repo", str(repo),
        "--dream-type", "bug_investigation",
        "--action-level", "report_only",
        "--title", "x",
    ])
    assert exit_code != 0
    err = capsys.readouterr().err
    assert "bug_investigation" in err


def test_cli_returns_nonzero_on_empty_title(repo, capsys):
    cli = _import_cli()
    exit_code = cli.main([
        "--repo", str(repo),
        "--dream-type", "idea_trial",
        "--action-level", "report_only",
        "--title", "   ",
    ])
    assert exit_code != 0
    err = capsys.readouterr().err
    assert "title" in err.lower()
