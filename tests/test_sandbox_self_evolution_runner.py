"""Tests for AUTO.1b — Sandbox Self-Evolution Dry-Run Runner.

Covers the prescribed cases:
1.  sandbox copy excludes `.git`, `.agent`, caches, and temp dirs.
2.  a blocked AUTO.1a contract refuses to run.
3.  an auto-merge contract refuses to run.
4.  a self-approval contract refuses to run.
5.  no validation declared -> validation skipped.
6.  safe validation runs inside the sandbox only.
7.  validation side effects are reported.
8.  the real repo remains unmodified.
9.  cleanup only removes the managed sandbox.
10. cleanup refuses unmanaged paths.
11. Markdown contains summary / validation / side effects / boundaries.
12. JSON contains all guardrail booleans.
13. CLI writes JSON + Markdown.
14. deterministic `--trial-id` and `--created-at`.
15. no forbidden imports / calls (model client, patch generation, patch apply to
    the real repo, Dream, Project Evolution, network, lesson promotion, proposal
    import, worker launch, remote git host / chat / external automation, or
    auto-merge).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.sandbox_self_evolution_runner import (
    DRY_RUN_VERDICTS,
    REPORT_KIND,
    cleanup_managed_sandbox,
    contract_block_reason,
    create_managed_sandbox,
    is_managed_sandbox,
    render_sandbox_dry_run_markdown,
    run_dry_run,
)
from core.validation_side_effects import snapshot_repo_files
import scripts.run_sandbox_self_evolution_dry_run as script


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_repo(tmp_path: Path, with_writer: bool = False) -> Path:
    repo = tmp_path / "repo"
    (repo / "core").mkdir(parents=True)
    (repo / "core" / "foo.py").write_text("x = 1\n", encoding="utf-8")
    # directories that must never be copied into a sandbox
    for d in (".git", ".agent", "__pycache__", ".pytest_cache", "node_modules", "tmp_tests", ".venv"):
        (repo / d).mkdir()
        (repo / d / "marker").write_text("x", encoding="utf-8")
    (repo / ".env").write_text("SECRET=x\n", encoding="utf-8")
    if with_writer:
        (repo / "writer.py").write_text(
            "with open('side_effect.txt', 'w', encoding='utf-8') as f:\n"
            "    f.write('hello')\n",
            encoding="utf-8",
        )
    return repo


def _ok_contract(**over) -> dict:
    base = {
        "verdict": "eligible_for_review",
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
        "automation_level": "LOCAL_0_OBSERVE",
        "sandbox_required": True,
        "human_approval_required": True,
    }
    base.update(over)
    return base


# ── 1. sandbox copy excludes vcs / caches / temp ──────────────────────────────

def test_sandbox_copy_excludes_vcs_caches_and_temp(tmp_path):
    repo = _make_repo(tmp_path)
    sb = tmp_path / "sb"
    info = create_managed_sandbox(str(repo), str(sb))
    assert info["ok"] is True
    assert (sb / "core" / "foo.py").is_file()
    for excluded in (".git", ".agent", "__pycache__", ".pytest_cache", "node_modules", "tmp_tests", ".venv"):
        assert not (sb / excluded).exists(), f"{excluded} must not be copied"
    assert not (sb / ".env").exists(), ".env must not be copied"
    assert is_managed_sandbox(sb)


# ── 2-4. contract gate refusals ───────────────────────────────────────────────

def test_blocked_contract_refuses_to_run(tmp_path):
    repo = _make_repo(tmp_path, with_writer=True)
    rec = run_dry_run(
        repo_path=str(repo),
        contract=_ok_contract(verdict="blocked"),
        validation_commands=[["python", "writer.py"]],
        sandbox_root=str(tmp_path / "sb"),
        trial_id="t2",
        created_at="x",
    )
    assert rec["dry_run_verdict"] == "blocked_by_contract"
    assert rec["sandbox_created"] is False
    assert rec["validation_run_by_tool"] is False
    assert rec["contract_block_reason"]
    assert not (repo / "side_effect.txt").exists()


def test_auto_merge_contract_refuses(tmp_path):
    repo = _make_repo(tmp_path)
    rec1 = run_dry_run(
        repo_path=str(repo),
        contract=_ok_contract(eligible_for_auto_merge=True),
        validation_commands=[],
        sandbox_root=str(tmp_path / "a"),
        trial_id="t3a",
        created_at="x",
    )
    assert rec1["dry_run_verdict"] == "blocked_by_contract"
    rec2 = run_dry_run(
        repo_path=str(repo),
        contract=_ok_contract(automation_level="AUTO_4_AUTO_MERGE"),
        validation_commands=[],
        sandbox_root=str(tmp_path / "b"),
        trial_id="t3b",
        created_at="x",
    )
    assert rec2["dry_run_verdict"] == "blocked_by_contract"


def test_self_approval_contract_refuses(tmp_path):
    repo = _make_repo(tmp_path)
    rec = run_dry_run(
        repo_path=str(repo),
        contract=_ok_contract(self_approval_allowed=True),
        validation_commands=[],
        sandbox_root=str(tmp_path / "sb"),
        trial_id="t4",
        created_at="x",
    )
    assert rec["dry_run_verdict"] == "blocked_by_contract"


def test_remote_pr_and_missing_flags_refuse(tmp_path):
    repo = _make_repo(tmp_path)
    cases = [
        {"automation_level": "REMOTE_3_DRAFT_PR"},
        {"sandbox_required": False},
        {"human_approval_required": False},
    ]
    for i, over in enumerate(cases):
        rec = run_dry_run(
            repo_path=str(repo),
            contract=_ok_contract(**over),
            validation_commands=[],
            sandbox_root=str(tmp_path / f"sb{i}"),
            trial_id=f"tr{i}",
            created_at="x",
        )
        assert rec["dry_run_verdict"] == "blocked_by_contract", over


def test_contract_block_reason_direct():
    assert contract_block_reason(_ok_contract()) == ""
    assert contract_block_reason(_ok_contract(verdict="blocked"))
    assert contract_block_reason(None)


# ── 5. no validation declared -> skipped ──────────────────────────────────────

def test_no_validation_declared_is_skipped(tmp_path):
    repo = _make_repo(tmp_path)
    rec = run_dry_run(
        repo_path=str(repo),
        contract=_ok_contract(),
        validation_commands=[],
        sandbox_root=str(tmp_path / "sb"),
        trial_id="t5",
        created_at="x",
    )
    assert rec["dry_run_verdict"] == "validation_skipped"
    assert rec["validation_run_by_tool"] is False
    assert rec["sandbox_created"] is True


# ── 6-7. safe validation runs in sandbox only; side effects reported ──────────

def test_safe_validation_runs_inside_sandbox_only(tmp_path):
    repo = _make_repo(tmp_path, with_writer=True)
    rec = run_dry_run(
        repo_path=str(repo),
        contract=_ok_contract(),
        validation_commands=[["python", "writer.py"]],
        sandbox_root=str(tmp_path / "sandboxes"),
        trial_id="t6",
        created_at="x",
    )
    assert rec["dry_run_verdict"] == "dry_run_passed"
    assert rec["validation_run_by_tool"] is True
    sandbox_path = Path(rec["sandbox_path"])
    assert (sandbox_path / "side_effect.txt").is_file()
    assert not (repo / "side_effect.txt").exists()
    cmd = rec["validation_commands"][0]
    assert cmd["ok"] is True
    assert cmd["exit_code"] == 0


def test_validation_side_effects_are_reported(tmp_path):
    repo = _make_repo(tmp_path, with_writer=True)
    rec = run_dry_run(
        repo_path=str(repo),
        contract=_ok_contract(),
        validation_commands=[["python", "writer.py"]],
        sandbox_root=str(tmp_path / "sb"),
        trial_id="t7",
        created_at="x",
    )
    created = [e["path"] for e in rec["side_effects"]["created"]]
    assert "side_effect.txt" in created
    assert rec["side_effects_sandbox_only"] is True


def test_failing_validation_marks_dry_run_failed(tmp_path):
    repo = _make_repo(tmp_path)
    (repo / "boom.py").write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    rec = run_dry_run(
        repo_path=str(repo),
        contract=_ok_contract(),
        validation_commands=[["python", "boom.py"]],
        sandbox_root=str(tmp_path / "sb"),
        trial_id="t7b",
        created_at="x",
    )
    assert rec["dry_run_verdict"] == "dry_run_failed"
    assert rec["validation_commands"][0]["exit_code"] == 3


# ── 8. real repo unmodified ───────────────────────────────────────────────────

def test_real_repo_remains_unmodified(tmp_path):
    repo = _make_repo(tmp_path, with_writer=True)
    before = snapshot_repo_files(str(repo))
    rec = run_dry_run(
        repo_path=str(repo),
        contract=_ok_contract(),
        validation_commands=[["python", "writer.py"]],
        sandbox_root=str(tmp_path / "sb"),
        trial_id="t8",
        created_at="x",
    )
    after = snapshot_repo_files(str(repo))
    assert before == after
    assert rec["real_repo_modified"] is False


# ── 9-10. cleanup safety ──────────────────────────────────────────────────────

def test_cleanup_removes_managed_sandbox(tmp_path):
    repo = _make_repo(tmp_path)
    rec = run_dry_run(
        repo_path=str(repo),
        contract=_ok_contract(),
        validation_commands=[],
        sandbox_root=str(tmp_path / "sb"),
        trial_id="t9",
        created_at="x",
        cleanup=True,
    )
    assert rec["cleanup_performed"] is True
    assert not Path(rec["sandbox_path"]).exists()


def test_no_cleanup_keeps_sandbox(tmp_path):
    repo = _make_repo(tmp_path)
    rec = run_dry_run(
        repo_path=str(repo),
        contract=_ok_contract(),
        validation_commands=[],
        sandbox_root=str(tmp_path / "sb"),
        trial_id="t9b",
        created_at="x",
        cleanup=False,
    )
    assert rec["cleanup_performed"] is False
    assert Path(rec["sandbox_path"]).is_dir()


def test_cleanup_refuses_unmanaged_path(tmp_path):
    plain = tmp_path / "not_a_sandbox"
    plain.mkdir()
    (plain / "keep.txt").write_text("x", encoding="utf-8")
    ok, reason = cleanup_managed_sandbox(str(plain))
    assert ok is False
    assert "managed" in reason.lower()
    assert plain.is_dir()
    assert (plain / "keep.txt").is_file()


# ── 11. Markdown sections ─────────────────────────────────────────────────────

def test_markdown_contains_required_sections(tmp_path):
    repo = _make_repo(tmp_path, with_writer=True)
    rec = run_dry_run(
        repo_path=str(repo),
        contract=_ok_contract(),
        validation_commands=[["python", "writer.py"]],
        sandbox_root=str(tmp_path / "sb"),
        trial_id="t11",
        created_at="x",
    )
    md = render_sandbox_dry_run_markdown(rec)
    assert "# Sandbox Self-Evolution Dry Run" in md
    assert "## Summary" in md
    assert "## Validation" in md
    assert "## Side Effects" in md
    assert "## Boundaries" in md
    low = md.lower()
    assert "does not call models" in low
    assert "does not generate patches" in low
    assert "does not modify the real repo" in low
    assert "does not push, merge, open prs" in low
    assert "self-approval remains forbidden" in low


# ── 12. guardrail booleans ────────────────────────────────────────────────────

def test_json_contains_all_guardrail_booleans(tmp_path):
    repo = _make_repo(tmp_path)
    rec = run_dry_run(
        repo_path=str(repo),
        contract=_ok_contract(),
        validation_commands=[],
        sandbox_root=str(tmp_path / "sb"),
        trial_id="t12",
        created_at="x",
    )
    boolean_keys = (
        "sandbox_created",
        "sandbox_only",
        "real_repo_modified",
        "push_performed",
        "merge_performed",
        "model_call_performed",
        "worker_launch_performed",
        "patch_generated",
        "patch_applied_to_real_repo",
        "validation_run_by_tool",
        "benchmark_run_by_tool",
        "human_approval_required",
        "self_approval_allowed",
        "eligible_for_auto_merge",
        "cleanup_performed",
    )
    for key in boolean_keys:
        assert key in rec, key
        assert isinstance(rec[key], bool), key
    assert rec["real_repo_modified"] is False
    assert rec["push_performed"] is False
    assert rec["merge_performed"] is False
    assert rec["model_call_performed"] is False
    assert rec["worker_launch_performed"] is False
    assert rec["patch_generated"] is False
    assert rec["patch_applied_to_real_repo"] is False
    assert rec["human_approval_required"] is True
    assert rec["self_approval_allowed"] is False
    assert rec["eligible_for_auto_merge"] is False
    assert rec["sandbox_created"] is True
    assert rec["report_kind"] == REPORT_KIND
    assert rec["dry_run_verdict"] in DRY_RUN_VERDICTS
    assert all(v is False for v in rec["boundaries"].values())


# ── 13. CLI writes JSON + Markdown ────────────────────────────────────────────

def test_cli_writes_json_and_markdown(tmp_path):
    repo = _make_repo(tmp_path)
    out = tmp_path / "out"
    res = script.run_sandbox_self_evolution_dry_run(
        repo_path=str(repo),
        contract=_ok_contract(),
        validation_commands=[],
        sandbox_root=str(tmp_path / "sb"),
        trial_id="cli1",
        created_at="2026-06-17T00:00:00+00:00",
        output_root=str(out),
    )
    assert res["ok"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file()
    assert mp.is_file()
    assert jp.parent.name == "cli1"
    assert jp.name == "sandbox_dry_run.json"
    assert mp.name == "sandbox_dry_run.md"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["trial_id"] == "cli1"
    assert data["dry_run_verdict"] == "validation_skipped"


def test_cli_main_smoke_with_validation_json(tmp_path):
    repo = _make_repo(tmp_path)
    out = tmp_path / "out"
    code = script.main(
        [
            "--repo-path",
            str(repo),
            "--automation-level",
            "LOCAL_0_OBSERVE",
            "--trial-id",
            "clim",
            "--created-at",
            "2026-06-17T00:00:00+00:00",
            "--sandbox-root",
            str(tmp_path / "sb"),
            "--output-root",
            str(out),
            "--validation-json",
            '["python", "-m", "compileall", "-q", "core"]',
        ]
    )
    assert code == 0
    data = json.loads((out / "clim" / "sandbox_dry_run.json").read_text(encoding="utf-8"))
    assert data["validation_run_by_tool"] is True
    assert data["dry_run_verdict"] == "dry_run_passed"


def test_cli_loads_contract_from_path(tmp_path):
    repo = _make_repo(tmp_path)
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(_ok_contract(verdict="blocked")), encoding="utf-8")
    out = tmp_path / "out"
    res = script.run_sandbox_self_evolution_dry_run(
        repo_path=str(repo),
        trial_contract=str(contract_path),
        validation_commands=[],
        sandbox_root=str(tmp_path / "sb"),
        trial_id="cli2",
        created_at="2026-06-17T00:00:00+00:00",
        output_root=str(out),
    )
    assert res["record"]["dry_run_verdict"] == "blocked_by_contract"


# ── 14. deterministic --trial-id and --created-at ─────────────────────────────

def test_deterministic_trial_id_and_created_at(tmp_path):
    repo = _make_repo(tmp_path)

    def run(name: str) -> dict:
        return script.run_sandbox_self_evolution_dry_run(
            repo_path=str(repo),
            contract=_ok_contract(verdict="blocked"),
            validation_commands=[],
            sandbox_root=str(tmp_path / "sb"),
            trial_id="fixed",
            created_at="2026-06-17T12:00:00+00:00",
            output_root=str(tmp_path / name),
        )

    a = run("a")
    b = run("b")
    da = Path(a["json_path"]).read_text(encoding="utf-8")
    db = Path(b["json_path"]).read_text(encoding="utf-8")
    assert da == db
    data = json.loads(da)
    assert data["trial_id"] == "fixed"
    assert data["created_at"] == "2026-06-17T12:00:00+00:00"
    assert data["dry_run_verdict"] == "blocked_by_contract"


# ── 15. import / side-effect guard ────────────────────────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "sandbox_self_evolution_runner.py"
_SCRIPT = (
    Path(__file__).parent.parent / "scripts" / "run_sandbox_self_evolution_dry_run.py"
)
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_are_safe():
    allowed_top = {"__future__", "json", "os", "shutil", "pathlib", "typing", "dataclasses", "core"}
    allowed_core = {
        "core.validation_execution",
        "core.validation_side_effects",
        "core.sandbox_self_evolution_trial",
    }
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {module!r}"
            if top == "core":
                assert module in allowed_core, f"Unexpected core import: {module!r}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed_top, f"Unexpected import in core: {alias.name!r}"


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


def test_no_patch_generation_or_apply():
    for bad in ("generate_patch", "apply_patch", "patch_apply", "run_patch", "build_patch_plan"):
        assert bad not in _BOTH, f"Found patch token {bad!r}"


def test_no_dream_or_project_evolution_execution():
    for bad in ("dream_taxonomy", "dream_trials", "project_evolution", "reverse_dream"):
        assert bad not in _BOTH, f"Found subsystem token {bad!r}"


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


def test_no_auto_merge_execution():
    for bad in ("auto_merge(", "perform_merge", "perform_auto_merge", "merge_to_real", "git_merge"):
        assert bad not in _BOTH, f"Found auto-merge token {bad!r}"


def test_core_does_not_import_executing_modules():
    for bad in ("sandbox_runner", "core.executor", "run_lifecycle", "core.pipeline"):
        assert bad not in _CORE_SRC, f"Found executing-module token {bad!r}"
