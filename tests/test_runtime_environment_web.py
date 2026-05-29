from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"


def test_runtime_environment_ui_contains_dropdown_options_and_help_text():
    template = INDEX_TEMPLATE.read_text(encoding="utf-8")

    assert 'for="runtimeEnvironmentSelect">Running environment' in template
    assert (
        "Choose where C.A.T.T.U.S is running, not where your browser is open."
        in template
    )
    for value in (
        "auto",
        "local_windows",
        "local_linux",
        "local_macos",
        "docker",
        "codespaces",
        "custom",
    ):
        assert f'value="{value}"' in template
    assert 'name="runtime_environment_custom_name"' in template
    assert 'name="runtime_environment_notes"' in template


def test_web_route_passes_runtime_environment_state_to_agent(
    tmp_path,
    monkeypatch,
):
    from web import app as web_app

    repo = tmp_path / "repo"
    repo.mkdir()
    session_file = tmp_path / "sessions.json"
    captured: dict[str, object] = {}

    def fake_run_mode(
        *,
        mode,
        query,
        repo_path,
        agent_mode,
        project_tag,
        patch_style,
        ignore_repo_dna,
        runtime_environment,
        runtime_environment_custom_name,
        runtime_environment_notes,
    ):
        captured.update(
            {
                "mode": mode,
                "query": query,
                "repo_path": repo_path,
                "agent_mode": agent_mode,
                "project_tag": project_tag,
                "patch_style": patch_style,
                "ignore_repo_dna": ignore_repo_dna,
                "runtime_environment": runtime_environment,
                "runtime_environment_custom_name": runtime_environment_custom_name,
                "runtime_environment_notes": runtime_environment_notes,
            }
        )
        return {
            "answer": "ok",
            "context": "",
            "graph": "",
            "state": "",
            "patch": "",
            "validation": "",
        }, project_tag

    monkeypatch.setattr(web_app, "SESSION_FILE", session_file)
    monkeypatch.setattr(web_app, "_run_mode", fake_run_mode)
    monkeypatch.setattr(web_app, "build_project_tag", lambda repo_path, user_tag: "demo-tag")

    with web_app.app.test_client() as client:
        response = client.post(
            "/",
            data={
                "query": "fix the bug",
                "repo_path": str(repo),
                "mode": "full",
                "agent_mode": "reviewer",
                "patch_style": "balanced",
                "runtime_environment": "codespaces",
                "runtime_environment_custom_name": "",
                "runtime_environment_notes": "",
            },
        )

    assert response.status_code == 200
    assert captured["runtime_environment"] == "codespaces"
    assert captured["runtime_environment_custom_name"] == ""
    assert captured["runtime_environment_notes"] == ""

    sessions = json.loads(session_file.read_text(encoding="utf-8"))
    assert sessions[0]["runtime_environment"] == "codespaces"
    assert sessions[0]["result"]["runtime_environment"] == "codespaces"


def test_web_route_preserves_custom_runtime_environment_details(
    tmp_path,
    monkeypatch,
):
    from web import app as web_app

    repo = tmp_path / "repo"
    repo.mkdir()
    session_file = tmp_path / "sessions.json"
    captured: dict[str, object] = {}

    def fake_run_mode(**kwargs):
        captured.update(kwargs)
        return {
            "answer": "ok",
            "context": "",
            "graph": "",
            "state": "",
            "patch": "",
            "validation": "",
        }, kwargs["project_tag"]

    monkeypatch.setattr(web_app, "SESSION_FILE", session_file)
    monkeypatch.setattr(web_app, "_run_mode", fake_run_mode)
    monkeypatch.setattr(web_app, "build_project_tag", lambda repo_path, user_tag: "demo-tag")

    with web_app.app.test_client() as client:
        response = client.post(
            "/",
            data={
                "query": "inspect env",
                "repo_path": str(repo),
                "mode": "full",
                "agent_mode": "reviewer",
                "patch_style": "safe_minimal",
                "runtime_environment": "custom",
                "runtime_environment_custom_name": "Remote Pod",
                "runtime_environment_notes": "Browser is local, agent is remote.",
            },
        )

    assert response.status_code == 200
    assert captured["runtime_environment"] == "custom"
    assert captured["runtime_environment_custom_name"] == "Remote Pod"
    assert captured["runtime_environment_notes"] == "Browser is local, agent is remote."

    sessions = json.loads(session_file.read_text(encoding="utf-8"))
    assert sessions[0]["runtime_environment_custom_name"] == "Remote Pod"
    assert sessions[0]["runtime_environment_notes"] == "Browser is local, agent is remote."


def test_run_agent_web_includes_runtime_environment_metadata_on_early_error(tmp_path):
    from web.runner import run_agent_web

    result = run_agent_web(
        "fix it",
        str(tmp_path),
        runtime_environment="custom",
        runtime_environment_custom_name="CI worker",
        runtime_environment_notes="Empty repo returns before model calls.",
    )

    assert result["runtime_environment"] == "custom"
    assert result["runtime_environment_custom_name"] == "CI worker"
    assert result["runtime_environment_notes"] == "Empty repo returns before model calls."
