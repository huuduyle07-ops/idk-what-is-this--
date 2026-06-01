from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import goal_brief


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(goal_brief, "DEFAULT_GOAL_BRIEFS_ROOT", tmp_path)

    from web.app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_goal_brief_start_route_creates_draft(client):
    resp = client.post("/goal-brief/start", data={"goal": "Fix weird auth failure"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["brief"]["goal"] == "Fix weird auth failure"
    assert "summary" not in body["brief"]
    assert set(body["brief"]) == set(goal_brief.GOAL_BRIEF_SCHEMA)
    assert body["summary"]["rows"][0]["label"] == "Goal"
    assert body["summary"]["rows"][0]["value"] == "Fix weird auth failure"
    assert Path(body["brief_path"]).is_file()


def test_goal_brief_start_route_rejects_empty_goal(client):
    resp = client.post("/goal-brief/start", data={"goal": "  "})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "goal must be a non-empty string" in body["error"]


def test_goal_brief_update_route_records_manual_answer(client):
    created = goal_brief.create_goal_brief(goal="Fix worker route", goal_briefs_root=goal_brief.DEFAULT_GOAL_BRIEFS_ROOT)

    resp = client.post(
        "/goal-brief/update",
        data={
            "brief_ref": created["brief_path"],
            "answer": json.dumps(
                {
                    "evidence": {"actual_result": "route returns 500"},
                    "validation": {"command": "python -m pytest tests/test_worker_runs_routes.py -q"},
                }
            ),
        },
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["brief"]["evidence"]["actual_result"] == "route returns 500"
    assert body["brief"]["validation"]["command"] == "python -m pytest tests/test_worker_runs_routes.py -q"


def test_goal_brief_update_route_blocks_path_traversal(client, tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    resp = client.post(
        "/goal-brief/update",
        data={"brief_ref": str(outside), "answer": "Actual: no"},
    )

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False


def test_goal_brief_panel_is_rendered(client):
    resp = client.get("/")

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "ws-tab-goal-brief" in html
    assert "Start brief" in html
    assert "goalBriefSummary" in html
    assert "Reply or paste command output" in html
    assert "Bug fix" in html
    assert "Raw details" in html
    assert "Copy final prompt" in html


def test_goal_brief_panel_renders_guided_checklist(client):
    resp = client.get("/")

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="goalBriefChecklist"' in html
    assert "goal-brief-checklist-empty" in html
    assert "Start with a goal to build the checklist." in html
    assert "Task type" in html
    assert "Observed result" in html
    assert "Success criteria" in html
    assert "Expected pass" in html
    assert "Actual failure" in html
    assert "Allowed files" in html
    assert "Validation command" in html
    assert 'const goalComplete = Boolean(String(brief.goal || "").trim());' in html
    assert "insertGoalBriefReply('expected_result: all tests pass')" in html
    assert "insertGoalBriefReply('validation_command: python -m pytest tests -q')" in html
