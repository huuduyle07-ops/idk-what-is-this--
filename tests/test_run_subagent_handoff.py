"""Phase 7.1 — tests for scripts/run_subagent_handoff.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core import handoff_notes
from scripts import run_subagent_handoff as runner


@pytest.fixture
def env(tmp_path: Path, monkeypatch) -> dict:
    handoff_root = tmp_path / "handoffs"
    worker_runs_root = tmp_path / "worker_runs"
    fake_repo = tmp_path / "repo"
    (fake_repo / "src").mkdir(parents=True)
    (fake_repo / "src" / "foo.py").write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(runner, "HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(runner, "WORKER_RUNS_ROOT", worker_runs_root)
    return {
        "handoff_root": handoff_root,
        "worker_runs_root": worker_runs_root,
        "fake_repo": fake_repo,
    }


def _create_note(env, **overrides):
    kwargs = dict(
        title="run me",
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=str(env["fake_repo"]),
        handoff_root=env["handoff_root"],
    )
    kwargs.update(overrides)
    return handoff_notes.create_handoff_note(**kwargs)


def test_dry_run_does_not_execute_subprocess(env, monkeypatch):
    note = _create_note(env)

    def fail(*args, **kwargs):
        raise AssertionError("subprocess.run must not be called in dry-run")

    monkeypatch.setattr(runner.subprocess, "run", fail)

    result = runner.run_handoff(
        note_path=note["path"],
        allow_run=False,
    )

    assert result["dry_run"] is True
    assert result["exit_code"] is None
    assert "codex" in result["command"]
    artifact_dir = Path(result["artifact_dir"])
    assert (artifact_dir / "worker_run.json").is_file()
    assert (artifact_dir / "handoff.md").is_file()
    raw = (artifact_dir / "raw_output.txt").read_text(encoding="utf-8")
    assert raw == ""


def test_dry_run_does_not_change_handoff_status(env, monkeypatch):
    note = _create_note(env)
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    runner.run_handoff(note_path=note["path"], allow_run=False)
    parsed = handoff_notes.read_handoff_note(note["path"], handoff_root=env["handoff_root"])
    assert parsed["meta"]["status"] == "draft"


def test_dry_run_main_returns_zero(env, monkeypatch, capsys):
    note = _create_note(env)
    monkeypatch.setattr(sys, "argv", ["run_subagent_handoff.py", "--note", note["path"]])
    rc = runner.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out


def test_other_worker_without_command_refuses(env, monkeypatch):
    note = _create_note(env, intended_worker="other")
    result = runner.run_handoff(
        note_path=note["path"],
        allow_run=False,
        worker_override="other",
    )
    assert result["dry_run"] is True
    assert result["error"] is not None
    assert "worker_command" in result["error"]


def test_env_var_overrides_worker_command(env, monkeypatch):
    note = _create_note(env, intended_worker="gemini")
    monkeypatch.setenv("HANDOFF_GEMINI_CMD", "my-gemini --custom")
    result = runner.run_handoff(note_path=note["path"], allow_run=False)
    assert "my-gemini --custom" in result["command"]

def _record_real_repo_state(repo: Path) -> dict[str, str]:
    import hashlib
    state: dict[str, str] = {}
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo).as_posix()
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        state[rel] = h
    return state


def test_allow_run_uses_temp_clone_and_does_not_modify_real_repo(env, monkeypatch):
    note = _create_note(env)
    before = _record_real_repo_state(env["fake_repo"])

    captured: dict = {}

    class FakeCompleted:
        returncode = 0
        stdout = "worker says hi"
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        # Confirm cwd is NOT the real repo.
        assert Path(kwargs["cwd"]).resolve() != env["fake_repo"].resolve()
        # Confirm HANDOFF.md is in the temp clone.
        assert (Path(kwargs["cwd"]) / "HANDOFF.md").is_file()
        # Simulate worker producing a proposal.md
        (Path(kwargs["cwd"]) / "proposal.md").write_text("worker-proposal", encoding="utf-8")
        return FakeCompleted()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.run_handoff(note_path=note["path"], allow_run=True)

    assert result["dry_run"] is False
    assert result["exit_code"] == 0
    assert result["timed_out"] is False
    artifact_dir = Path(result["artifact_dir"])
    assert (artifact_dir / "raw_output.txt").read_text(encoding="utf-8") == "worker says hi"
    assert (artifact_dir / "proposal.md").read_text(encoding="utf-8") == "worker-proposal"

    after = _record_real_repo_state(env["fake_repo"])
    assert before == after, "real repo files must be byte-identical after --allow-run"


def test_allow_run_timeout_records_timed_out_true(env, monkeypatch):
    note = _create_note(env)

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.run_handoff(note_path=note["path"], allow_run=True, timeout_sec=1)

    assert result["timed_out"] is True
    assert result["dry_run"] is False

    parsed = handoff_notes.read_handoff_note(note["path"], handoff_root=env["handoff_root"])
    assert parsed["meta"]["status"] == "failed"


def test_allow_run_success_updates_status_to_ran(env, monkeypatch):
    note = _create_note(env)

    class FakeCompleted:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(runner.subprocess, "run", lambda cmd, **kw: FakeCompleted())
    runner.run_handoff(note_path=note["path"], allow_run=True)
    parsed = handoff_notes.read_handoff_note(note["path"], handoff_root=env["handoff_root"])
    assert parsed["meta"]["status"] == "ran"


def test_allow_run_non_zero_exit_updates_status_to_failed(env, monkeypatch):
    note = _create_note(env)

    class FakeCompleted:
        returncode = 3
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(runner.subprocess, "run", lambda cmd, **kw: FakeCompleted())
    runner.run_handoff(note_path=note["path"], allow_run=True)
    parsed = handoff_notes.read_handoff_note(note["path"], handoff_root=env["handoff_root"])
    assert parsed["meta"]["status"] == "failed"


def test_allow_run_skips_ignored_dirs_in_temp_clone(env, monkeypatch):
    (env["fake_repo"] / ".git").mkdir()
    (env["fake_repo"] / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (env["fake_repo"] / ".agent").mkdir()
    (env["fake_repo"] / ".agent" / "secret.txt").write_text("nope", encoding="utf-8")

    note = _create_note(env)

    seen: dict = {}

    def fake_run(cmd, **kwargs):
        cwd = Path(kwargs["cwd"])
        seen["has_git"] = (cwd / ".git").exists()
        seen["has_agent"] = (cwd / ".agent").exists()
        seen["has_src_foo"] = (cwd / "src" / "foo.py").exists()

        class C: returncode = 0; stdout = ""; stderr = ""
        return C()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.run_handoff(note_path=note["path"], allow_run=True)

    assert seen["has_git"] is False
    assert seen["has_agent"] is False
    assert seen["has_src_foo"] is True