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

    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(runner, "HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(runner, "WORKER_RUNS_ROOT", worker_runs_root)

    from web import app as web_app

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        c._handoff_root = handoff_root  # type: ignore[attr-defined]
        yield c


def _goal_brief() -> dict:
    return {
        "goal": "Fix checkout total regression",
        "evidence": {"actual_result": "total is 19"},
        "constraints": {"allowed_files": ["core/checkout.py"]},
        "validation": {"command": "python -m pytest tests/test_checkout.py -q"},
    }


def test_handoffs_compose_route_returns_json_and_writes_no_files(client):
    before = sorted(path.relative_to(client._handoff_root.parent) for path in client._handoff_root.parent.rglob("*"))

    resp = client.post(
        "/handoffs/compose",
        json={"goal_brief": _goal_brief(), "repo_path": "/repo/app"},
    )

    after = sorted(path.relative_to(client._handoff_root.parent) for path in client._handoff_root.parent.rglob("*"))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["draft"]["title"] == "Fix checkout total regression"
    assert body["markdown"].startswith("# Handoff Draft")
    assert "handoff_path" not in body
    assert before == after


def test_handoffs_compose_route_accepts_field_input(client):
    resp = client.post(
        "/handoffs/compose",
        data={
            "title": "Explain graph weights",
            "task_summary": "Explain current graph weighting behavior.",
            "repo_path": "/repo/app",
            "allowed_files": "graph/weights.py",
            "validation_command": "python -m pytest tests/test_graph_weights.py -q",
        },
    )

    body = resp.get_json()
    assert resp.status_code == 200
    assert body["draft"]["title"] == "Explain graph weights"
    assert body["draft"]["allowed_files"] == ["graph/weights.py"]


def test_handoffs_compose_panel_is_rendered(client):
    html = client.get("/").get_data(as_text=True)

    assert "Compose handoff draft" in html
    assert "Use in Handoff form" in html
    assert 'id="handoffDraftPreview"' in html
    assert "composeHandoffDraftFromGoalBrief" in html


def test_ui_compose_button_does_not_call_create_or_run(client):
    html = client.get("/").get_data(as_text=True)
    start = html.index("async function composeHandoffDraftFromGoalBrief()")
    end = html.index("function useHandoffDraftInForm()")
    function_body = html[start:end]

    assert 'fetch("/handoffs/compose"' in function_body
    forbidden_endpoints = [
        "/handoffs/create",
        "/handoffs/run",
        "/generate_patch",
        "/apply_patch",
        "/benchmarks/run",
        "/dream/run",
    ]
    for endpoint in forbidden_endpoints:
        assert endpoint not in function_body


def test_use_handoff_draft_in_form_is_client_side_only(client):
    html = client.get("/").get_data(as_text=True)
    start = html.index("function useHandoffDraftInForm()")
    end = html.index("async function refreshHandoffs()")
    function_body = html[start:end]

    assert "handoffTitle" in function_body
    assert "handoffAllowed" in function_body
    assert "handoffValidation" in function_body
    assert "fetch(" not in function_body


def test_existing_handoff_create_route_unchanged(client):
    resp = client.post(
        "/handoffs/create",
        data={
            "title": "Create still writes",
            "intended_worker": "codex",
            "task_type": "proposal_only",
            "context_summary": "ctx",
            "validation_command": "echo ok",
            "allowed_files": "core/foo.py",
        },
    )

    body = resp.get_json()
    assert resp.status_code == 200
    assert body["ok"] is True
    assert body["handoff_id"].endswith(".md")
    assert Path(body["handoff_path"]).is_file()


def test_route_source_does_not_reference_write_or_run_targets_for_compose():
    source = Path("web/app.py").read_text(encoding="utf-8")
    route_start = source.index('@app.route("/handoffs/compose"')
    route_end = source.index('@app.route("/handoffs/create"', route_start)
    route_source = source[route_start:route_end]

    assert "create_handoff_note" not in route_source
    assert "run_handoff" not in route_source
    assert "run_benchmarks" not in route_source
    assert "run_patch_plan_with_artifacts" not in route_source
    assert "promote" not in route_source
