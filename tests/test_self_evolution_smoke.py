"""Tests for AUTO.1f — End-to-End Sandbox Self-Evolution Smoke Scenario.

AUTO.1f is a deterministic single-trial smoke runner. It drives the AUTO.1a->1e
chain over ONE harmless patch candidate inside ONE trial directory, so every
artifact shares the same ``trial_id`` and output folder before any future
external review automation is added.

The smoke runner orchestrates the existing AUTO.1a-1e tools in-process. It runs
only declared safe validation inside a disposable managed sandbox; it never
writes to the real repo, generates a patch, calls a model, pushes, merges, opens
a PR, or contacts external automation.

Covers the prescribed cases:
1.  single-trial chain creates all expected artifacts (10 files).
2.  all artifacts share the same trial_id.
3.  all artifacts live under the same trial directory.
4.  final evidence pack verdict is ready_for_human_review for the clean smoke.
5.  each chain step reports its clean verdict.
6.  the smoke result has an explicit, inspectable shape.
7.  the real repo is unchanged (no demo file leaks out of the sandbox).
8.  cleanup removes the managed sandbox when requested.
9.  cleanup keeps the managed sandbox when not requested (explicit behavior).
10. the CLI runs the full chain and writes the evidence pack.
11. the CLI --keep-sandbox flag is honored.
12. the default patch is an explicit literal candidate touching a harmless file.
13. no forbidden imports / calls (model clients, network, GitHub, Telegram, n8n,
    Dream, Project Evolution, lesson promotion, proposal import, worker launch,
    auto-merge, real repo patch apply).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.run_self_evolution_smoke as smoke


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_repo(root: Path) -> None:
    """A tiny but real repo: a ``core/`` package the sandbox can compile."""
    (root / "core").mkdir(parents=True)
    (root / "core" / "ok.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "README.md").write_text("# temp repo for AUTO.1f smoke\n", encoding="utf-8")


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


_TRIAL_ID = "auto1f_demo"
_CREATED_AT = "2026-06-18T00:00:00+00:00"

#: The ten artifacts a clean single-trial chain must produce.
_EXPECTED_FILES = (
    "self_evolution_trial.json",
    "self_evolution_trial.md",
    "sandbox_dry_run.json",
    "sandbox_dry_run.md",
    "patch_candidate_evaluation.json",
    "patch_candidate_evaluation.md",
    "patch_graduation_review.json",
    "patch_graduation_review.md",
    "self_evolution_evidence_pack.json",
    "self_evolution_evidence_pack.md",
)


@pytest.fixture(scope="module")
def clean_chain(tmp_path_factory):
    """Run the full clean chain once (sandbox kept) and share it read-only."""
    base = tmp_path_factory.mktemp("auto1f")
    repo = base / "repo"
    _make_repo(repo)
    out = base / "out"
    sand = base / "sandboxes"
    before = _snapshot(repo)
    result = smoke.run_self_evolution_smoke(
        repo_path=str(repo),
        trial_id=_TRIAL_ID,
        created_at=_CREATED_AT,
        output_root=str(out),
        sandbox_root=str(sand),
        cleanup=False,
    )
    return {
        "result": result,
        "repo": repo,
        "out": out,
        "sand": sand,
        "before": before,
        "trial_dir": Path(result["trial_dir"]),
    }


# ── 1. all artifacts created ──────────────────────────────────────────────────

def test_single_trial_chain_creates_all_artifacts(clean_chain):
    trial_dir = clean_chain["trial_dir"]
    for name in _EXPECTED_FILES:
        assert (trial_dir / name).is_file(), f"missing artifact: {name}"


# ── 2. shared trial_id ────────────────────────────────────────────────────────

def test_all_artifacts_share_trial_id(clean_chain):
    trial_dir = clean_chain["trial_dir"]
    for name in (
        "self_evolution_trial.json",
        "sandbox_dry_run.json",
        "patch_candidate_evaluation.json",
        "patch_graduation_review.json",
        "self_evolution_evidence_pack.json",
    ):
        data = json.loads((trial_dir / name).read_text(encoding="utf-8"))
        assert data.get("trial_id") == _TRIAL_ID, f"{name} trial_id={data.get('trial_id')!r}"


# ── 3. one shared trial directory ─────────────────────────────────────────────

def test_artifacts_share_one_trial_directory(clean_chain):
    result = clean_chain["result"]
    trial_dir = clean_chain["trial_dir"]
    parents = {str(Path(step["json_path"]).parent) for step in result["steps"]}
    assert parents == {str(trial_dir)}
    # the trial dir is named for the deterministic trial id
    assert trial_dir.name == _TRIAL_ID


# ── 4. clean smoke -> ready_for_human_review ──────────────────────────────────

def test_final_evidence_pack_is_ready_for_human_review(clean_chain):
    result = clean_chain["result"]
    assert result["final_verdict"] == "ready_for_human_review"
    assert result["recommended_next_step"] == "review_patch_candidate"
    pack = result["records"]["evidence_pack"]
    assert pack["final_verdict"] == "ready_for_human_review"
    assert pack["blockers"] == []


# ── 5. each step clean verdict ────────────────────────────────────────────────

def test_each_step_reports_clean_verdict(clean_chain):
    records = clean_chain["result"]["records"]
    assert records["contract"]["verdict"] == "eligible_for_review"
    assert records["dry_run"]["dry_run_verdict"] == "dry_run_passed"
    assert records["patch_evaluation"]["verdict"] == "patch_candidate_passed"
    assert records["graduation_review"]["graduation_verdict"] == "eligible_for_human_review"
    assert records["evidence_pack"]["final_verdict"] == "ready_for_human_review"


# ── 6. result shape ───────────────────────────────────────────────────────────

def test_smoke_result_shape(clean_chain):
    result = clean_chain["result"]
    assert result["ok"] is True
    assert result["trial_id"] == _TRIAL_ID
    assert len(result["steps"]) == 5
    assert {s["name"] for s in result["steps"]} == {
        "contract",
        "dry_run",
        "patch_evaluation",
        "graduation_review",
        "evidence_pack",
    }
    assert set(result["records"]) == {
        "contract",
        "dry_run",
        "patch_evaluation",
        "graduation_review",
        "evidence_pack",
    }


# ── 7. real repo unchanged ────────────────────────────────────────────────────

def test_real_repo_unchanged(clean_chain):
    repo = clean_chain["repo"]
    assert _snapshot(repo) == clean_chain["before"]
    # the harmless demo file only ever exists inside the sandbox copy
    target = smoke.SMOKE_PATCH_TARGET
    assert not (repo / target).exists()


# ── 8-9. explicit cleanup behavior ────────────────────────────────────────────

def test_cleanup_removes_managed_sandbox_when_requested(tmp_path):
    repo = tmp_path / "repo"
    _make_repo(repo)
    result = smoke.run_self_evolution_smoke(
        repo_path=str(repo),
        trial_id="auto1f_cleanup",
        created_at=_CREATED_AT,
        output_root=str(tmp_path / "out"),
        sandbox_root=str(tmp_path / "sand"),
        cleanup=True,
    )
    assert result["cleanup_requested"] is True
    assert result["sandbox_exists_after"] is False
    assert not Path(result["sandbox_path"]).exists()
    # the run still succeeded end-to-end
    assert result["final_verdict"] == "ready_for_human_review"


def test_keep_sandbox_when_not_requested(clean_chain):
    result = clean_chain["result"]
    assert result["cleanup_requested"] is False
    assert result["sandbox_exists_after"] is True
    assert Path(result["sandbox_path"]).is_dir()


# ── 10-11. CLI ────────────────────────────────────────────────────────────────

def test_cli_main_runs_full_chain(tmp_path, capsys):
    repo = tmp_path / "repo"
    _make_repo(repo)
    out = tmp_path / "out"
    code = smoke.main(
        [
            "--repo-path",
            str(repo),
            "--trial-id",
            "auto1f_cli",
            "--created-at",
            _CREATED_AT,
            "--output-root",
            str(out),
            "--sandbox-root",
            str(tmp_path / "sand"),
        ]
    )
    assert code == 0
    pack = json.loads((out / "auto1f_cli" / "self_evolution_evidence_pack.json").read_text(encoding="utf-8"))
    assert pack["final_verdict"] == "ready_for_human_review"
    # default cleanup removes the managed sandbox
    assert not (tmp_path / "sand" / "auto1f_cli").exists()


def test_cli_keep_sandbox_flag(tmp_path):
    repo = tmp_path / "repo"
    _make_repo(repo)
    code = smoke.main(
        [
            "--repo-path",
            str(repo),
            "--trial-id",
            "auto1f_keep",
            "--created-at",
            _CREATED_AT,
            "--output-root",
            str(tmp_path / "out"),
            "--sandbox-root",
            str(tmp_path / "sand"),
            "--keep-sandbox",
        ]
    )
    assert code == 0
    assert (tmp_path / "sand" / "auto1f_keep").is_dir()


# ── 12. explicit harmless literal patch ───────────────────────────────────────

def test_default_patch_targets_harmless_new_file(clean_chain):
    records = clean_chain["result"]["records"]
    touched = records["patch_evaluation"]["patch_touched_paths"]
    assert touched == [smoke.SMOKE_PATCH_TARGET]
    # the target is a harmless text file, not code / tests / protected paths
    assert smoke.SMOKE_PATCH_TARGET.endswith(".txt")
    for forbidden in (".agent", ".git", "secrets", "tests/", "benchmarks/"):
        assert forbidden not in smoke.SMOKE_PATCH_TARGET


def test_patch_is_explicit_literal_not_generated():
    # the candidate is a fixed, consumed literal diff — never generated
    assert "diff --git" in smoke.SMOKE_PATCH_TEXT
    assert smoke.SMOKE_PATCH_TARGET in smoke.SMOKE_PATCH_TEXT
    assert "--- /dev/null" in smoke.SMOKE_PATCH_TEXT  # it creates a new file


# ── 13. guardrail booleans inert in the final pack ────────────────────────────

def test_final_pack_guardrail_booleans_are_inert(clean_chain):
    pack = clean_chain["result"]["records"]["evidence_pack"]
    assert pack["human_review_required"] is True
    for key in (
        "self_approval_allowed",
        "eligible_for_auto_merge",
        "real_repo_modified",
        "patch_applied_to_real_repo",
        "push_performed",
        "merge_performed",
        "model_call_performed",
        "validation_run_by_tool",
        "benchmark_run_by_tool",
        "worker_launch_performed",
    ):
        assert pack[key] is False, key


# ── 14. import / call guards on the smoke script source ───────────────────────

_SCRIPT = Path(__file__).parent.parent / "scripts" / "run_self_evolution_smoke.py"
_SRC = _SCRIPT.read_text(encoding="utf-8")


def test_no_model_clients():
    for bad in (
        "anthropic",
        "openai",
        "litellm",
        "ollama",
        "bedrock",
        "generativeai",
        "claude",
        "codex",
        "gemini",
        "deepseek",
    ):
        assert bad not in _SRC, f"Found model client token {bad!r}"


def test_no_network_or_external_automation():
    for bad in (
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "aiohttp",
        "webhook",
        "telegram",
        "n8n",
        "github",
    ):
        assert bad not in _SRC, f"Found network/automation token {bad!r}"


def test_no_dream_or_project_evolution_execution():
    for bad in ("dream_taxonomy", "dream_trials", "project_evolution", "reverse_dream"):
        assert bad not in _SRC, f"Found subsystem token {bad!r}"


def test_no_lesson_promotion():
    for bad in ("promote_lesson", "lesson_store", "save_active_lesson"):
        assert bad not in _SRC, f"Found lesson-promotion token {bad!r}"


def test_no_proposal_import_or_worker_launch():
    for bad in ("import_proposal", "proposal_runner", "launch_worker", "worker_launch(", "spawn_worker"):
        assert bad not in _SRC, f"Found proposal/worker token {bad!r}"


def test_no_auto_merge_execution():
    for bad in ("auto_merge(", "perform_merge", "perform_auto_merge", "merge_to_real", "git_merge"):
        assert bad not in _SRC, f"Found auto-merge token {bad!r}"


def test_no_real_repo_patch_apply_or_generation():
    for bad in (
        "apply_patch",
        "patch_apply",
        "apply_to_real_repo",
        "write_to_real_repo",
        "generate_patch",
        "build_patch_plan",
    ):
        assert bad not in _SRC, f"Found patch apply/generation token {bad!r}"


def test_no_benchmark_execution_from_smoke():
    assert "run_benchmarks" not in _SRC
