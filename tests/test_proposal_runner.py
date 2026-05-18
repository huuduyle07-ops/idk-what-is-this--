"""Tests for core.proposal_runner — the Flask-friendly wrapper around the
patch proposal queue CLI.

The wrapper enforces:
- Reject bad item shape (not a dict, missing case_name).
- Single concurrent run (busy lock).
- The UI click counts as human_approved_for_proposal=true.

These tests stub `_process_item` so they don't actually run the LLM-bound
proposal pipeline.
"""
from __future__ import annotations

import threading
import time

import pytest

from core import proposal_runner


@pytest.fixture(autouse=True)
def _reset_runner_state(monkeypatch):
    """Each test gets a fresh, idle runner state and a temp PROPOSAL_ROOT."""
    proposal_runner._STATE.update(
        running=False, run_id=None, started_at=None,
        finished_at=None, result=None, error=None,
    )
    # If the previous test failed mid-run and left the lock held, release it.
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


def test_rejects_non_dict_item():
    result = proposal_runner.make_proposal_for_item("not a dict")  # type: ignore[arg-type]
    assert result["ok"] is False
    assert "case_name" in result["error"]


def test_rejects_dict_without_case_name():
    result = proposal_runner.make_proposal_for_item({"kind": "bug"})
    assert result["ok"] is False
    assert "case_name" in result["error"]


def test_happy_path_calls_process_item_with_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(proposal_runner, "PROPOSAL_ROOT", tmp_path)

    captured = {}
    done = threading.Event()

    def fake_process(*, item, idx, run_dir, validation_timeout_sec):
        captured["item"] = dict(item)
        captured["idx"] = idx
        captured["run_dir"] = run_dir
        captured["timeout"] = validation_timeout_sec
        # Simulate a fast successful run.
        time.sleep(0.05)
        done.set()
        return {"case_name": item["case_name"], "status": "proposal_validated"}

    monkeypatch.setattr(proposal_runner, "_process_item", fake_process)

    result = proposal_runner.make_proposal_for_item({"case_name": "python_off_by_one"})
    assert result["ok"] is True
    assert result["run_id"]
    assert result["run_dir"]

    assert done.wait(timeout=2.0), "background run never finished"

    # The wrapper forced the approval flag for the in-memory copy.
    assert captured["item"]["case_name"] == "python_off_by_one"
    assert captured["item"]["human_approved_for_proposal"] is True
    assert captured["idx"] == 1
    assert captured["timeout"] == 60

    # State reflects completion.
    # Give the finally clause a moment to flip running=False after done.set().
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if not proposal_runner._STATE["running"]:
            break
        time.sleep(0.02)
    assert proposal_runner._STATE["running"] is False
    assert proposal_runner._STATE["result"]["status"] == "proposal_validated"
    assert proposal_runner._STATE["error"] is None


def test_busy_lock_rejects_second_call(tmp_path, monkeypatch):
    monkeypatch.setattr(proposal_runner, "PROPOSAL_ROOT", tmp_path)

    release = threading.Event()

    def slow_process(**_):
        release.wait(timeout=3.0)
        return {"status": "proposal_validated"}

    monkeypatch.setattr(proposal_runner, "_process_item", slow_process)

    first = proposal_runner.make_proposal_for_item({"case_name": "case_a"})
    assert first["ok"] is True

    # Wait briefly so the background thread has time to actually start and
    # be holding the lock when we attempt the second call.
    deadline = time.time() + 1.0
    while time.time() < deadline:
        if proposal_runner._STATE["running"]:
            break
        time.sleep(0.01)

    second = proposal_runner.make_proposal_for_item({"case_name": "case_b"})
    assert second["ok"] is False
    assert "in progress" in second["error"]

    # Let the first run finish so we don't leak the lock.
    release.set()
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if not proposal_runner._STATE["running"]:
            break
        time.sleep(0.02)
    assert proposal_runner._STATE["running"] is False


def test_get_status_returns_snapshot():
    proposal_runner._STATE.update(running=True, run_id="run_x", result=None)
    snap = proposal_runner.get_status()
    assert snap["running"] is True
    assert snap["run_id"] == "run_x"
    # Mutating the snapshot must not affect the live state.
    snap["running"] = False
    assert proposal_runner._STATE["running"] is True


def test_exception_in_process_item_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(proposal_runner, "PROPOSAL_ROOT", tmp_path)

    done = threading.Event()

    def boom(**_):
        try:
            raise RuntimeError("kaboom")
        finally:
            done.set()

    monkeypatch.setattr(proposal_runner, "_process_item", boom)

    result = proposal_runner.make_proposal_for_item({"case_name": "case_x"})
    assert result["ok"] is True

    assert done.wait(timeout=2.0)
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if not proposal_runner._STATE["running"]:
            break
        time.sleep(0.02)

    assert proposal_runner._STATE["running"] is False
    assert proposal_runner._STATE["error"]
    assert "kaboom" in proposal_runner._STATE["error"]
