"""Phase 7.1 — Flask client tests for the handoff routes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import handoff_notes
from scripts import run_subagent_handoff as runner


@pytest.fixture
def client(tmp_path, monkeypatch):
    handoff_root = tmp_path / "handoffs"
    worker_runs_root = tmp_path / "worker_runs"
    fake_repo = tmp_path / "repo"
    (fake_repo / "src").mkdir(parents=True)
    (fake_repo / "src" / "foo.py").write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(runner, "HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(runner, "WORKER_RUNS_ROOT", worker_runs_root)

    from web import app as web_app

    monkeypatch.setattr(web_app, "_HANDOFF_ROOT", handoff_root, raising=False)
    monkeypatch.setattr(web_app, "_WORKER_RUNS_ROOT", worker_runs_root, raising=False)

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        c._handoff_root = handoff_root  # type: ignore[attr-defined]
        c._worker_runs_root = worker_runs_root  # type: ignore[attr-defined]
        c._fake_repo = fake_repo  # type: ignore[attr-defined]
        yield c


def test_handoffs_create_writes_note(client):
    resp = client.post(
        "/handoffs/create",
        data={
            "title": "From web",
            "intended_worker": "codex",
            "task_type": "proposal_only",
            "context_summary": "ctx",
            "validation_command": "echo ok",
            "allowed_files": "core/foo.py,tests/test_foo.py",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["meta"]["title"] == "From web"
    assert Path(body["handoff_path"]).is_file()


def test_handoffs_create_rejects_unknown_worker(client):
    resp = client.post(
        "/handoffs/create",
        data={
            "title": "x",
            "intended_worker": "bogus",
            "task_type": "proposal_only",
        },
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "intended_worker" in body["error"]


def test_handoffs_list_returns_recent(client):
    handoff_notes.create_handoff_note(
        title="a",
        intended_worker="codex",
        task_type="proposal_only",
        handoff_root=client._handoff_root,
    )
    resp = client.get("/handoffs/list")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert any(item["title"] == "a" for item in body["handoffs"])


def test_handoffs_run_dry_run_does_not_execute(client, monkeypatch):
    created = handoff_notes.create_handoff_note(
        title="dry",
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=str(client._fake_repo),
        handoff_root=client._handoff_root,
    )

    monkeypatch.setattr(
        runner.subprocess, "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    resp = client.post(
        "/handoffs/run",
        data={"handoff_path": created["path"], "allow_run": "false"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["dry_run"] is True
    assert Path(body["artifact_dir"]).is_dir()


def test_worker_runs_list_returns_recent_runs(client, monkeypatch):
    created = handoff_notes.create_handoff_note(
        title="r",
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=str(client._fake_repo),
        handoff_root=client._handoff_root,
    )
    monkeypatch.setattr(
        runner.subprocess, "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    client.post("/handoffs/run", data={"handoff_path": created["path"], "allow_run": "false"})

    resp = client.get("/worker-runs/list")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert len(body["runs"]) >= 1
    assert "dry_run" in body["runs"][0]
    # Legacy /worker-runs/list shape must remain intact after the Task B refactor.
    for legacy_key in ("artifact_dir", "name", "worker", "exit_code",
                       "timed_out", "duration_sec", "command",
                       "started_at", "finished_at", "error"):
        assert legacy_key in body["runs"][0], f"missing legacy key: {legacy_key}"