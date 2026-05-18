"""Flask client tests for the Phase 5 Polish proposal routes.

Covers:
- /dream/plan/latest: returns empty when no plan exists; returns items
  when one does.
- /dream/proposals/make: rejects bad JSON, accepts valid items,
  returns 409 on busy.
- /dream/proposals/status: returns the runner state.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from core import proposal_runner


@pytest.fixture(autouse=True)
def _isolated_runner_state():
    proposal_runner._STATE.update(
        running=False, run_id=None, started_at=None,
        finished_at=None, result=None, error=None,
    )
    if proposal_runner._LOCK.locked():
        try:
            proposal_runner._LOCK.release()
        except RuntimeError:
            pass
    yield
    if proposal_runner._LOCK.locked():
        try:
            proposal_runner._LOCK.release()
        except RuntimeError:
            pass


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(proposal_runner, "PROPOSAL_ROOT", tmp_path)
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_plan_latest_returns_empty_when_no_plan(client, tmp_path, monkeypatch):
    from scripts import run_patch_proposal_queue

    monkeypatch.setattr(run_patch_proposal_queue, "REPORT_DIR", tmp_path / "no_reports")
    resp = client.get("/dream/plan/latest")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["plan_path"] is None
    assert body["items"] == []


def test_plan_latest_returns_items(client, tmp_path, monkeypatch):
    from scripts import run_patch_proposal_queue

    reports = tmp_path / "reports"
    reports.mkdir()
    plan = reports / "background_dream_plan_20260518_120000.json"
    plan.write_text(json.dumps({
        "items": [
            {"case_name": "python_off_by_one", "kind": "bug", "reason": "failed",
             "suggested_mode": "patch_if_safe", "human_approved_for_proposal": False},
            {"case_name": "go_wallet_transfer", "kind": "debt", "reason": "slow",
             "suggested_mode": "plan_only", "human_approved_for_proposal": True},
        ],
    }), encoding="utf-8")

    monkeypatch.setattr(run_patch_proposal_queue, "REPORT_DIR", reports)

    resp = client.get("/dream/plan/latest")
    assert resp.status_code == 200
    body = resp.get_json()
    assert Path(body["plan_path"]).name == plan.name
    assert len(body["items"]) == 2
    assert body["items"][0]["case_name"] == "python_off_by_one"


def test_make_rejects_invalid_json(client):
    resp = client.post(
        "/dream/proposals/make",
        data={"item": "not json"},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "valid JSON" in body["error"]


def test_make_rejects_item_without_case_name(client):
    resp = client.post(
        "/dream/proposals/make",
        data={"item": json.dumps({"kind": "bug"})},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "case_name" in body["error"]


def test_make_happy_path_starts_run(client, monkeypatch):
    done = threading.Event()

    def fake_process(*, item, idx, run_dir, validation_timeout_sec):
        done.set()
        return {"case_name": item["case_name"], "status": "proposal_validated"}

    monkeypatch.setattr(proposal_runner, "_process_item", fake_process)

    resp = client.post(
        "/dream/proposals/make",
        data={"item": json.dumps({"case_name": "python_off_by_one"})},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["run_id"]
    assert done.wait(timeout=2.0)


def test_make_busy_returns_409(client, monkeypatch):
    release = threading.Event()

    def slow_process(**_):
        release.wait(timeout=3.0)
        return {"status": "proposal_validated"}

    monkeypatch.setattr(proposal_runner, "_process_item", slow_process)

    first = client.post(
        "/dream/proposals/make",
        data={"item": json.dumps({"case_name": "case_a"})},
    )
    assert first.status_code == 200

    deadline = time.time() + 1.0
    while time.time() < deadline:
        if proposal_runner._STATE["running"]:
            break
        time.sleep(0.01)

    second = client.post(
        "/dream/proposals/make",
        data={"item": json.dumps({"case_name": "case_b"})},
    )
    assert second.status_code == 409
    body = second.get_json()
    assert body["ok"] is False
    assert "in progress" in body["error"]

    release.set()
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if not proposal_runner._STATE["running"]:
            break
        time.sleep(0.02)


def test_status_returns_runner_state(client):
    proposal_runner._STATE.update(running=True, run_id="run_y")
    resp = client.get("/dream/proposals/status")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["running"] is True
    assert body["run_id"] == "run_y"
