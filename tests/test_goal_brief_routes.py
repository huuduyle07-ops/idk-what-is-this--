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
    assert "Copy final prompt" in html
