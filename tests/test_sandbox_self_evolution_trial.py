"""Tests for AUTO.1a — Sandbox Self-Evolution Trial Contract (report-only).

Covers the prescribed cases:
1.  observe / report-only level is eligible.
2.  prepare level is eligible when reviewable.
3.  sandbox draft-patch with empty allowed_files warns or blocks.
4.  auto-merge level is always blocked.
5.  self_approval_allowed=true is blocked.
6.  strong model tier requires approval.
7.  local_only budget passes.
8.  broad allowed_files produces a warning.
9.  missing validation for a draft-patch level warns.
10. Markdown contains summary / scorecard / boundaries.
11. JSON contains all guardrail booleans.
12. CLI writes JSON + Markdown.
13. deterministic ``--trial-id`` and ``--created-at``.
14. no real repo files are modified by the tool.
15. no forbidden imports / calls (model client, external process spawning,
    validation execution, benchmark execution, patch apply, Dream, Project
    Evolution, network, lesson promotion, proposal import, worker launch,
    remote git host, chat approval, or external automation).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.sandbox_self_evolution_trial import (
    AUTOMATION_LEVELS,
    BUDGET_TIERS,
    FORBIDDEN_FILES,
    NEXT_SAFE_STEPS,
    REPORT_KIND,
    SCORE_DIMENSIONS,
    build_sandbox_self_evolution_trial,
    render_sandbox_self_evolution_trial_markdown,
)
import scripts.create_sandbox_self_evolution_trial as script


# ── helpers ───────────────────────────────────────────────────────────────────

def build(**over) -> dict:
    params = dict(
        phase_id="AUTO.1a",
        phase_title="Sandbox trial",
        phase_summary="Try a small self-improvement task in a sandbox.",
        automation_level="LOCAL_0_OBSERVE",
        allowed_files=None,
        validation_commands=None,
        budget_tier="local_only",
        self_approval_allowed=False,
    )
    params.update(over)
    return build_sandbox_self_evolution_trial(**params)


# ── 1. observe / report-only level is eligible ────────────────────────────────

def test_observe_level_is_eligible():
    rec = build(automation_level="LOCAL_0_OBSERVE")
    assert rec["automation_level"] == "LOCAL_0_OBSERVE"
    assert rec["score"]["safety"] == "pass"
    assert rec["verdict"] == "eligible_for_review"
    assert rec["eligible_for_human_review"] is True
    assert rec["next_safe_step"] == "keep_report_only"


# ── 2. prepare level is eligible when reviewable ──────────────────────────────

def test_prepare_level_is_eligible():
    rec = build(automation_level="LOCAL_1_PREPARE")
    assert rec["score"]["safety"] == "pass"
    assert rec["verdict"] == "eligible_for_review"
    assert rec["next_safe_step"] == "create_worker_assignment"


# ── 3. sandbox draft-patch with empty allowed_files warns or blocks ───────────

def test_sandbox_empty_allowed_files_warns_or_blocks():
    rec = build(
        automation_level="SANDBOX_2_DRAFT_PATCH",
        allowed_files=[],
        validation_commands=["python -m pytest -q"],
    )
    assert rec["score"]["scope_control"] in ("warn", "fail")
    assert rec["verdict"] in ("blocked", "not_eligible_for_review")
    assert rec["next_safe_step"] == "blocked_until_scope_is_narrowed"


# ── 4. auto-merge level is always blocked ─────────────────────────────────────

def test_auto_merge_level_is_blocked():
    rec = build(
        automation_level="AUTO_4_AUTO_MERGE",
        allowed_files=["core/foo.py"],
        validation_commands=["python -m pytest -q"],
    )
    assert rec["score"]["safety"] == "fail"
    assert rec["score"]["reviewability"] == "fail"
    assert rec["verdict"] == "blocked"
    assert rec["eligible_for_auto_merge"] is False
    assert rec["eligible_for_human_review"] is False


# ── 5. self_approval_allowed=true is blocked ──────────────────────────────────

def test_self_approval_allowed_is_blocked():
    rec = build(automation_level="LOCAL_0_OBSERVE", self_approval_allowed=True)
    assert rec["self_approval_allowed"] is True
    assert rec["score"]["safety"] == "fail"
    assert rec["verdict"] == "blocked"


# ── 6. strong model tier requires approval ────────────────────────────────────

def test_strong_model_tier_requires_approval():
    rec = build(
        automation_level="LOCAL_0_OBSERVE",
        budget_tier="strong_model_requires_approval",
    )
    assert rec["budget"]["tier"] == "strong_model_requires_approval"
    assert rec["budget"]["strong_model_requires_approval"] is True
    assert rec["budget"]["external_model_allowed"] is False
    assert rec["human_approval_required"] is True
    assert rec["score"]["budget"] == "warn"
    assert rec["next_safe_step"] == "request_human_approval_for_external_model"


# ── 7. local_only budget passes ───────────────────────────────────────────────

def test_local_only_budget_passes():
    rec = build(budget_tier="local_only")
    assert rec["budget"]["tier"] == "local_only"
    assert rec["budget"]["external_model_allowed"] is False
    assert rec["score"]["budget"] == "pass"


def test_cheap_api_budget_warns():
    rec = build(budget_tier="cheap_api_allowed")
    assert rec["budget"]["external_model_allowed"] is True
    assert rec["score"]["budget"] == "warn"


# ── 8. broad allowed_files produces a warning ─────────────────────────────────

def test_broad_allowed_files_warns():
    rec = build(
        automation_level="SANDBOX_2_DRAFT_PATCH",
        allowed_files=["src/*.py"],
        validation_commands=["python -m pytest -q"],
    )
    assert rec["score"]["scope_control"] == "warn"
    assert rec["next_safe_step"] == "blocked_until_scope_is_narrowed"


def test_directory_allowed_files_warns():
    rec = build(
        automation_level="SANDBOX_2_DRAFT_PATCH",
        allowed_files=["core/"],
        validation_commands=["python -m pytest -q"],
    )
    assert rec["score"]["scope_control"] == "warn"


# ── 9. missing validation for a draft-patch level warns ───────────────────────

def test_missing_validation_for_draft_patch_warns():
    rec = build(
        automation_level="SANDBOX_2_DRAFT_PATCH",
        allowed_files=["core/foo.py"],
        validation_commands=[],
    )
    assert rec["score"]["validation_plan"] == "warn"
    assert rec["next_safe_step"] == "blocked_until_validation_is_declared"


def test_well_scoped_sandbox_is_eligible_and_recommends_manual_run():
    rec = build(
        automation_level="SANDBOX_2_DRAFT_PATCH",
        allowed_files=["core/foo.py"],
        validation_commands=["python -m pytest -q"],
        budget_tier="local_only",
    )
    assert rec["score"]["safety"] == "warn"
    assert rec["score"]["scope_control"] == "pass"
    assert rec["score"]["validation_plan"] == "pass"
    assert rec["verdict"] == "eligible_for_review"
    assert rec["next_safe_step"] == "run_sandbox_trial_manually"


# ── 10. Markdown contains summary / scorecard / boundaries ────────────────────

def test_markdown_contains_summary_scorecard_boundaries():
    rec = build(
        automation_level="SANDBOX_2_DRAFT_PATCH",
        allowed_files=["core/foo.py"],
        validation_commands=["python -m pytest -q"],
    )
    md = render_sandbox_self_evolution_trial_markdown(rec)
    assert "# Sandbox Self-Evolution Trial" in md
    assert "## Summary" in md
    assert "## Scorecard" in md
    assert "| Dimension | Result | Reason |" in md
    assert "## Boundaries" in md
    assert "## Next Safe Step" in md
    low = md.lower()
    assert "does not run self-evolution" in low
    assert "does not launch models or external agents" in low
    assert "does not edit the real repo" in low
    assert "does not push, merge, or open" in low
    assert "does not run validation or benchmarks" in low
    assert "self-approval is forbidden" in low


# ── 11. JSON contains all guardrail booleans ──────────────────────────────────

def test_json_contains_all_guardrail_booleans():
    rec = build(automation_level="LOCAL_0_OBSERVE")
    expected = {
        "sandbox_required": True,
        "real_repo_modified": False,
        "push_performed": False,
        "merge_performed": False,
        "model_call_performed": False,
        "worker_launch_performed": False,
        "validation_run_by_tool": False,
        "benchmark_run_by_tool": False,
        "human_approval_required": True,
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
    }
    for key, val in expected.items():
        assert rec[key] is val, f"{key} should be {val}"
    assert isinstance(rec["eligible_for_human_review"], bool)
    # boundaries are all hard-false
    assert rec["boundaries"]
    assert all(v is False for v in rec["boundaries"].values())
    assert rec["report_kind"] == REPORT_KIND


def test_record_has_required_top_level_fields():
    rec = build()
    for key in (
        "trial_id",
        "created_at",
        "phase",
        "automation_level",
        "allowed_files",
        "forbidden_files",
        "validation_commands",
        "budget",
        "score",
        "verdict",
    ):
        assert key in rec, key
    assert set(rec["phase"]) >= {"id", "title", "summary"}
    assert set(rec["score"]) == set(SCORE_DIMENSIONS)
    assert rec["forbidden_files"] == list(FORBIDDEN_FILES)


# ── 12. CLI writes JSON + Markdown ────────────────────────────────────────────

def test_cli_writes_json_and_markdown(tmp_path):
    out = tmp_path / "out"
    res = script.run_sandbox_self_evolution_trial(
        repo_path=str(tmp_path),
        phase_id="AUTO.1a",
        phase_title="Sandbox trial",
        phase_summary="x",
        automation_level="SANDBOX_2_DRAFT_PATCH",
        allowed_files=["core/foo.py"],
        validation_commands=["python -m pytest -q"],
        budget_tier="local_only",
        trial_id="t1",
        created_at="2026-06-16T00:00:00+00:00",
        output_root=str(out),
    )
    assert res["ok"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file()
    assert mp.is_file()
    assert jp.parent.name == "t1"
    assert jp.name == "self_evolution_trial.json"
    assert mp.name == "self_evolution_trial.md"

    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["trial_id"] == "t1"
    assert data["automation_level"] == "SANDBOX_2_DRAFT_PATCH"
    assert data["allowed_files"] == ["core/foo.py"]
    assert data["validation_commands"] == ["python -m pytest -q"]

    md = mp.read_text(encoding="utf-8")
    assert "# Sandbox Self-Evolution Trial" in md
    assert "## Boundaries" in md


def test_cli_main_smoke(tmp_path, capsys):
    out = tmp_path / "out"
    code = script.main(
        [
            "--repo-path",
            str(tmp_path),
            "--phase-id",
            "AUTO.1a",
            "--phase-title",
            "Sandbox trial",
            "--automation-level",
            "LOCAL_0_OBSERVE",
            "--budget-tier",
            "local_only",
            "--trial-id",
            "cli1",
            "--created-at",
            "2026-06-16T00:00:00+00:00",
            "--output-root",
            str(out),
        ]
    )
    assert code == 0
    assert (out / "cli1" / "self_evolution_trial.json").is_file()


def test_cli_allowed_files_and_validation_accept_csv_and_repeat(tmp_path):
    out = tmp_path / "out"
    res = script.run_sandbox_self_evolution_trial(
        repo_path=str(tmp_path),
        phase_id="P",
        phase_title="T",
        automation_level="SANDBOX_2_DRAFT_PATCH",
        allowed_files=["core/a.py", "core/b.py"],
        validation_commands=["cmd one", "cmd two"],
        trial_id="csv",
        created_at="2026-06-16T00:00:00+00:00",
        output_root=str(out),
    )
    assert res["record"]["allowed_files"] == ["core/a.py", "core/b.py"]
    assert res["record"]["validation_commands"] == ["cmd one", "cmd two"]


# ── 13. deterministic --trial-id and --created-at ─────────────────────────────

def test_deterministic_trial_id_and_created_at(tmp_path):
    def run(name: str) -> dict:
        return script.run_sandbox_self_evolution_trial(
            repo_path=str(tmp_path),
            phase_id="P",
            phase_title="T",
            phase_summary="S",
            automation_level="LOCAL_1_PREPARE",
            trial_id="fixed-id",
            created_at="2026-06-16T12:00:00+00:00",
            output_root=str(tmp_path / name),
        )

    a = run("a")
    b = run("b")
    da = Path(a["json_path"]).read_text(encoding="utf-8")
    db = Path(b["json_path"]).read_text(encoding="utf-8")
    assert da == db  # byte-for-byte deterministic
    data = json.loads(da)
    assert data["trial_id"] == "fixed-id"
    assert data["created_at"] == "2026-06-16T12:00:00+00:00"
    assert Path(a["json_path"]).parent.name == "fixed-id"


# ── 14. no real repo files are modified ───────────────────────────────────────

def test_no_real_repo_files_modified(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    sentinel = repo / "keep.py"
    sentinel.write_text("print('hi')\n", encoding="utf-8")
    before = sentinel.read_bytes()

    out = tmp_path / "out"
    res = script.run_sandbox_self_evolution_trial(
        repo_path=str(repo),
        phase_id="P",
        phase_title="T",
        phase_summary="S",
        automation_level="LOCAL_0_OBSERVE",
        trial_id="fixed",
        created_at="2026-06-16T00:00:00+00:00",
        output_root=str(out),
    )
    assert res["ok"] is True
    assert sentinel.read_bytes() == before
    # nothing new was written into the repo tree (artifacts went to out/)
    assert list(repo.iterdir()) == [sentinel]
    assert res["record"]["real_repo_modified"] is False


# ── verdict / scoring edge cases ──────────────────────────────────────────────

def test_remote_pr_level_is_blocked_not_implemented():
    rec = build(
        automation_level="REMOTE_3_DRAFT_PR",
        allowed_files=["core/foo.py"],
        validation_commands=["python -m pytest -q"],
    )
    assert rec["score"]["safety"] == "fail"
    assert rec["verdict"] == "blocked"


def test_unknown_level_is_blocked():
    rec = build(automation_level="BOGUS_LEVEL")
    assert rec["score"]["safety"] == "fail"
    assert rec["verdict"] == "blocked"
    assert rec["next_safe_step"] == "keep_report_only"


def test_forbidden_path_in_allowed_files_fails_scope():
    rec = build(
        automation_level="SANDBOX_2_DRAFT_PATCH",
        allowed_files=[".env"],
        validation_commands=["python -m pytest -q"],
    )
    assert rec["score"]["scope_control"] == "fail"
    assert rec["verdict"] == "blocked"


def test_missing_phase_fields_not_eligible():
    rec = build(phase_id="", phase_title="", automation_level="LOCAL_0_OBSERVE")
    assert rec["missing_critical_fields"]
    assert rec["score"]["reviewability"] == "warn"
    assert rec["verdict"] == "not_eligible_for_review"


def test_automation_levels_defined_and_catalogued():
    rec = build()
    assert list(AUTOMATION_LEVELS) == [
        "LOCAL_0_OBSERVE",
        "LOCAL_1_PREPARE",
        "SANDBOX_2_DRAFT_PATCH",
        "REMOTE_3_DRAFT_PR",
        "AUTO_4_AUTO_MERGE",
    ]
    catalog = rec["automation_levels"]
    levels = [entry["level"] for entry in catalog]
    assert levels == list(AUTOMATION_LEVELS)
    status = {entry["level"]: entry["status"] for entry in catalog}
    assert status["LOCAL_0_OBSERVE"] == "defined"
    assert status["REMOTE_3_DRAFT_PR"] == "future_not_implemented"
    assert status["AUTO_4_AUTO_MERGE"] == "forbidden"


def test_next_safe_step_is_always_a_valid_member():
    for lvl in AUTOMATION_LEVELS:
        rec = build(
            automation_level=lvl,
            allowed_files=["core/foo.py"],
            validation_commands=["python -m pytest -q"],
        )
        assert rec["next_safe_step"] in NEXT_SAFE_STEPS


def test_budget_tiers_are_stable():
    assert set(BUDGET_TIERS) == {
        "local_only",
        "cheap_api_allowed",
        "strong_model_requires_approval",
    }


# ── 15. import / side-effect guard ────────────────────────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "sandbox_self_evolution_trial.py"
_SCRIPT = (
    Path(__file__).parent.parent / "scripts" / "create_sandbox_self_evolution_trial.py"
)
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_only_stdlib():
    stdlib_ok = {"__future__", "json", "pathlib", "typing"}
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            assert top in stdlib_ok, f"Unexpected import in core: {node.module!r}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in stdlib_ok, f"Unexpected import in core: {alias.name!r}"


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
        assert bad not in _BOTH, f"Found model client token {bad!r}"


def test_no_process_spawning_or_exec():
    for bad in ("subprocess", "Popen", "os.system", "exec(", "eval("):
        assert bad not in _BOTH, f"Found process-spawning token {bad!r}"


def test_no_patch_apply():
    for bad in ("apply_patch", "patch_apply", "run_patch"):
        assert bad not in _BOTH, f"Found patch-apply token {bad!r}"


def test_no_validation_or_benchmark_execution():
    for bad in ("run_validation", "run_benchmarks", "run_agent_web", "run_case("):
        assert bad not in _BOTH, f"Found execution token {bad!r}"


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
        assert bad not in _BOTH, f"Found network/automation token {bad!r}"


def test_no_dream_or_project_evolution_execution():
    for bad in ("dream_taxonomy", "dream_trials", "project_evolution", "reverse_dream"):
        assert bad not in _BOTH, f"Found subsystem token {bad!r}"


def test_no_lesson_promotion():
    for bad in ("promote_lesson", "lesson_store", "save_active_lesson"):
        assert bad not in _BOTH, f"Found lesson-promotion token {bad!r}"


def test_no_proposal_import_or_worker_launch():
    for bad in (
        "import_proposal",
        "proposal_runner",
        "launch_worker",
        "worker_launch(",
        "spawn_worker",
    ):
        assert bad not in _BOTH, f"Found proposal/worker token {bad!r}"


def test_does_not_import_executing_modules():
    for bad in (
        "sandbox_runner",
        "core.executor",
        "run_lifecycle",
        "core.pipeline",
        "core.validator",
    ):
        assert bad not in _BOTH, f"Found executing-module token {bad!r}"
