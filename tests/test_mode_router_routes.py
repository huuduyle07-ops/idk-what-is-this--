from __future__ import annotations

from pathlib import Path

import pytest

from core import goal_brief, handoff_notes
from scripts import run_subagent_handoff as runner


@pytest.fixture
def client(tmp_path, monkeypatch):
    goal_root = tmp_path / "goal_briefs"
    handoff_root = tmp_path / "handoffs"
    worker_runs_root = tmp_path / "worker_runs"

    monkeypatch.setattr(goal_brief, "DEFAULT_GOAL_BRIEFS_ROOT", goal_root)
    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(runner, "HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(runner, "WORKER_RUNS_ROOT", worker_runs_root)

    from web import app as web_app

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        c._root = tmp_path  # type: ignore[attr-defined]
        yield c


def test_mode_router_route_returns_json_and_writes_no_files(client):
    before = sorted(path.relative_to(client._root) for path in client._root.rglob("*"))

    resp = client.post("/mode/router", json={"user_intent": "Fix a failing checkout test."})

    after = sorted(path.relative_to(client._root) for path in client._root.rglob("*"))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["draft"]["suggested_mode"] == "debug"
    assert body["draft"]["required_user_confirmation"] is True
    assert body["markdown"].startswith("# Mode Router Draft")
    assert "handoff_path" not in body
    assert before == after


def test_mode_router_route_rejects_empty_input_without_context(client):
    resp = client.post("/mode/router", data={"user_intent": "  "})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "user_intent" in body["error"]


def test_mode_router_route_accepts_goal_and_handoff_context(client):
    resp = client.post(
        "/mode/router",
        json={
            "user_intent": "",
            "goal_brief": {"problem_statement": "Explain why fixture setup works."},
            "handoff_draft": {"title": "Optional worker handoff"},
        },
    )

    body = resp.get_json()
    assert resp.status_code == 200
    assert body["draft"]["suggested_mode"] == "handoff"


def test_mode_router_panel_is_rendered(client):
    html = client.get("/").get_data(as_text=True)

    assert "Suggest workflow mode" in html
    assert 'id="modeRouterIntent"' in html
    assert 'id="modeRouterPreview"' in html
    assert "suggestModeRoute" in html


def test_ui_suggest_button_does_not_call_action_endpoints(client):
    html = client.get("/").get_data(as_text=True)
    start = html.index("async function suggestModeRoute()")
    end = html.index("function _modeRouterValue", start)
    function_body = html[start:end]

    assert 'fetch("/mode/router"' in function_body
    forbidden_endpoints = [
        "/goal-brief/start",
        "/goal-brief/update",
        "/handoffs/create",
        "/handoffs/run",
        "/generate_patch",
        "/apply_patch",
        "/patch",
        "/benchmarks/run",
        "/dream",
        "/dream/run",
        "/validation",
    ]
    for endpoint in forbidden_endpoints:
        assert endpoint not in function_body


def test_route_source_does_not_reference_write_or_run_targets_for_mode_router():
    source = Path("web/app.py").read_text(encoding="utf-8")
    route_start = source.index('@app.route("/mode/router"')
    route_end = source.index('@app.route("/goal-brief/start"', route_start)
    route_source = source[route_start:route_end]

    assert "create_goal_brief" not in route_source
    assert "update_goal_brief" not in route_source
    assert "create_handoff_note" not in route_source
    assert "run_handoff" not in route_source
    assert "run_benchmarks" not in route_source
    assert "run_patch_plan_with_artifacts" not in route_source
    assert "promote" not in route_source
