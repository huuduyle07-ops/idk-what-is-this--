"""Phase 8.2b tests for the MCP worker-run import harness."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core import handoff_notes, worker_runs
from mcp_server import artifact_write
from mcp_server.artifact_write import import_worker_run_as_proposal_harness


@pytest.fixture
def env(tmp_path: Path, monkeypatch):
    worker_runs_root = tmp_path / "worker_runs"
    proposals_root = tmp_path / "proposals"
    handoff_root = tmp_path / "handoffs"
    fake_repo = tmp_path / "repo"
    (fake_repo / "src").mkdir(parents=True)
    (fake_repo / "src" / "foo.py").write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(worker_runs, "DEFAULT_WORKER_RUNS_ROOT", worker_runs_root)
    monkeypatch.setattr(worker_runs, "DEFAULT_PROPOSALS_ROOT", proposals_root)
    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(
        artifact_write,
        "record_mcp_invocation",
        lambda **_kwargs: None,
        raising=False,
    )

    return {
        "worker_runs_root": worker_runs_root,
        "proposals_root": proposals_root,
        "handoff_root": handoff_root,
        "fake_repo": fake_repo,
    }


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _make_run(
    env,
    run_id: str,
    *,
    complete: bool = True,
    dry_run: bool = False,
) -> Path:
    run_dir = env["worker_runs_root"] / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    note = handoff_notes.create_handoff_note(
        title="Import worker run",
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=str(env["fake_repo"]),
        handoff_root=env["handoff_root"],
    )
    (run_dir / "handoff.md").write_text(
        Path(note["path"]).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_json(run_dir / "worker_run.json", {
        "dry_run": dry_run,
        "worker": "codex",
        "command": "codex exec",
        "handoff_path": note["path"],
        "artifact_dir": str(run_dir),
    })
    (run_dir / "raw_output.txt").write_text("worker output\n", encoding="utf-8")
    if complete:
        (run_dir / "proposal.md").write_text("# Worker proposal\n", encoding="utf-8")
        _write_json(run_dir / "patch_plan.json", [{
            "op": "replace_snippet",
            "relative_path": "src/foo.py",
            "target_snippet": "x = 1",
            "patched_snippet": "x = 2",
        }])
    return run_dir


def _repo_state(repo: Path) -> dict[str, str]:
    return {
        path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in repo.rglob("*")
        if path.is_file()
    }


def test_valid_import_creates_review_proposal(env):
    _make_run(env, "20260521_010203_imp")

    result = import_worker_run_as_proposal_harness({
        "worker_run_id": "20260521_010203_imp",
    })

    proposal_dir = Path(result["proposal_dir"])
    assert result == {
        "ok": True,
        "proposal_dir": str(proposal_dir),
        "message": (
            "Worker run imported as proposal. "
            "Review it before validation or lesson creation."
        ),
    }
    assert (proposal_dir / "proposal.md").is_file()
    assert (proposal_dir / "patch_plan.json").is_file()
    for name in (
        "validation.json",
        "apply_result.json",
        "case.json",
        "patch_proposal.json",
    ):
        assert not (proposal_dir / name).exists()


def test_incomplete_worker_run_is_rejected(env):
    _make_run(env, "20260521_010203_inc", complete=False)

    with pytest.raises(FileNotFoundError, match="incomplete"):
        import_worker_run_as_proposal_harness({
            "worker_run_id": "20260521_010203_inc",
        })


def test_dry_run_worker_run_is_rejected(env):
    _make_run(env, "20260521_010203_dry", dry_run=True)

    with pytest.raises(ValueError, match="dry-run"):
        import_worker_run_as_proposal_harness({
            "worker_run_id": "20260521_010203_dry",
        })


@pytest.mark.parametrize("worker_run_id", ["../escape", "nested/run", "..\\escape"])
def test_worker_run_id_traversal_is_rejected(env, worker_run_id):
    with pytest.raises(ValueError, match="worker_run_id"):
        import_worker_run_as_proposal_harness({"worker_run_id": worker_run_id})


def test_worker_run_id_absolute_path_is_rejected(env):
    with pytest.raises(ValueError, match="worker_run_id"):
        import_worker_run_as_proposal_harness({
            "worker_run_id": str((env["worker_runs_root"] / "run").resolve()),
        })


def test_worker_run_id_empty_is_rejected(env):
    with pytest.raises(ValueError, match="worker_run_id"):
        import_worker_run_as_proposal_harness({"worker_run_id": "   "})


def test_unknown_input_field_is_rejected(env):
    with pytest.raises(ValueError, match="unknown field"):
        import_worker_run_as_proposal_harness({
            "worker_run_id": "20260521_010203_imp",
            "repo_path": "nope",
        })


def test_harness_does_not_invoke_subprocess(env, monkeypatch):
    import os
    import subprocess

    _make_run(env, "20260521_010203_noproc")
    tripped = {"hit": False}

    def _trip(*_args, **_kwargs):
        tripped["hit"] = True
        raise AssertionError("worker-run import harness must not run subprocess")

    monkeypatch.setattr(subprocess, "run", _trip)
    monkeypatch.setattr(subprocess, "Popen", _trip)
    monkeypatch.setattr(os, "system", _trip)

    result = import_worker_run_as_proposal_harness({
        "worker_run_id": "20260521_010203_noproc",
    })

    assert result["ok"] is True
    assert tripped["hit"] is False


def test_harness_does_not_modify_real_repo(env):
    _make_run(env, "20260521_010203_repo")
    before = _repo_state(env["fake_repo"])

    result = import_worker_run_as_proposal_harness({
        "worker_run_id": "20260521_010203_repo",
    })

    assert result["ok"] is True
    assert _repo_state(env["fake_repo"]) == before


def test_success_records_audit_event(env, monkeypatch):
    _make_run(env, "20260521_010203_audit")
    events = []
    monkeypatch.setattr(
        artifact_write,
        "record_mcp_invocation",
        lambda **kwargs: events.append(kwargs),
    )

    result = import_worker_run_as_proposal_harness({
        "worker_run_id": "20260521_010203_audit",
    })

    assert len(events) == 1
    assert events[0]["tool_name"] == "import_worker_run_as_proposal"
    assert events[0]["allowed"] is True
    assert result["proposal_dir"] in events[0]["artifacts"]


def test_blocked_import_records_audit_event(env, monkeypatch):
    events = []
    monkeypatch.setattr(
        artifact_write,
        "record_mcp_invocation",
        lambda **kwargs: events.append(kwargs),
    )

    with pytest.raises(ValueError, match="worker_run_id"):
        import_worker_run_as_proposal_harness({"worker_run_id": "../escape"})

    assert len(events) == 1
    assert events[0]["allowed"] is False
    assert events[0]["result_summary"] is None
    assert events[0]["artifacts"] == []


def test_audit_write_failure_keeps_import_success(env, monkeypatch):
    _make_run(env, "20260521_010203_failopen")
    attempts = {"count": 0}

    def _raise_audit_error(**_kwargs):
        attempts["count"] += 1
        raise OSError("audit offline")

    monkeypatch.setattr(artifact_write, "record_mcp_invocation", _raise_audit_error)

    result = import_worker_run_as_proposal_harness({
        "worker_run_id": "20260521_010203_failopen",
    })

    assert result["ok"] is True
    assert attempts["count"] == 1


def test_audit_write_failure_keeps_import_error(env, monkeypatch):
    attempts = {"count": 0}

    def _raise_audit_error(**_kwargs):
        attempts["count"] += 1
        raise OSError("audit offline")

    monkeypatch.setattr(artifact_write, "record_mcp_invocation", _raise_audit_error)

    with pytest.raises(ValueError, match="worker_run_id"):
        import_worker_run_as_proposal_harness({"worker_run_id": "../escape"})
    assert attempts["count"] == 1
