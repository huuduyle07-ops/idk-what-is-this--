from __future__ import annotations

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


def test_goal_brief_autocomplete_route_returns_json_draft(client):
    resp = client.post(
        "/goal-brief/autocomplete",
        json={
            "messy_intent": "Fix failing checkout test in core/checkout.py",
            "repo_path": "/repo/app",
            "validation_hint": "python -m pytest tests/test_checkout.py -q",
        },
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["draft"]["suggested_mode"] == "debug"
    assert body["draft"]["suspected_files_or_areas"] == ["core/checkout.py"]
    assert body["markdown"].startswith("# Goal Brief Draft")
    assert "brief_path" not in body


def test_goal_brief_autocomplete_route_rejects_empty_input(client):
    resp = client.post("/goal-brief/autocomplete", data={"messy_intent": "  "})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "messy_intent" in body["error"]


def test_goal_brief_autocomplete_route_does_not_write_files(client, tmp_path):
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    resp = client.post(
        "/goal-brief/autocomplete",
        data={
            "messy_intent": "Explain how the router picks debug mode",
            "repo_path": "/repo/app",
        },
    )

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert resp.status_code == 200
    assert before == after


def test_goal_brief_autocomplete_panel_is_rendered(client):
    resp = client.get("/")

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="goalBriefMessyIntent"' in html
    assert "Add logs, likely files, validation ideas, or rough notes" in html
    assert "Help me structure this" in html
    assert "Use this in Goal Brief" in html
    assert "goalBriefAutocompletePreview" in html


def test_ui_draft_button_only_calls_autocomplete_not_action_endpoints(client):
    html = client.get("/").get_data(as_text=True)
    start = html.index("function draftGoalBriefAutocomplete()")
    end = html.index("function useGoalBriefAutocompleteDraft()")
    function_body = html[start:end]

    assert 'fetch("/goal-brief/autocomplete"' in function_body
    forbidden_endpoints = [
        "/goal-brief/start",
        "/goal-brief/update",
        "/patch",
        "/patch/plan",
        "/benchmarks/run",
        "/dream",
        "/dream-trials",
    ]
    for endpoint in forbidden_endpoints:
        assert endpoint not in function_body


def test_use_this_in_goal_brief_is_client_side_only(client):
    html = client.get("/").get_data(as_text=True)
    start = html.index("function useGoalBriefAutocompleteDraft()")
    end = html.index("function startGoalBrief()")
    function_body = html[start:end]

    assert "goalBriefGoal" in function_body
    assert "goalBriefAnswer" in function_body
    assert "fetch(" not in function_body


def test_route_source_does_not_reference_write_targets_for_autocomplete():
    source = Path("web/app.py").read_text(encoding="utf-8")
    route_start = source.index('@app.route("/goal-brief/autocomplete"')
    route_end = source.index('@app.route("/goal-brief/start"', route_start)
    route_source = source[route_start:route_end]

    assert "create_goal_brief" not in route_source
    assert "update_goal_brief" not in route_source
    assert "run_benchmarks" not in route_source
    assert "run_patch_plan_with_artifacts" not in route_source
    assert "promote" not in route_source
