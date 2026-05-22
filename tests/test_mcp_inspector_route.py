"""Route tests for local MCP Inspector launch shortcuts."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def client():
    from web import app as web_app

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        yield c


@pytest.mark.parametrize(
    ("target", "script_name"),
    [
        ("read_only", "mcp_readonly_server.py"),
        ("artifact_write", "mcp_artifact_write_server.py"),
    ],
)
def test_mcp_inspector_launch_uses_fixed_server_targets(
    client, monkeypatch, target, script_name
):
    from web import app as web_app

    launched = {}

    def fake_launch(command):
        launched["command"] = command

    monkeypatch.setattr(web_app, "_launch_mcp_inspector", fake_launch)

    response = client.post("/mcp/inspector/launch", data={"target": target})
    body = response.get_json()

    assert response.status_code == 200
    assert body == {"ok": True, "target": target}
    assert "@modelcontextprotocol/inspector" in launched["command"]
    assert Path(launched["command"][-1]).name == script_name
    assert launched["command"][-1] == f"scripts/{script_name}"
    assert " " not in launched["command"][-1]


def test_mcp_inspector_launch_rejects_unknown_target(client, monkeypatch):
    from web import app as web_app

    monkeypatch.setattr(
        web_app,
        "_launch_mcp_inspector",
        lambda _command: (_ for _ in ()).throw(AssertionError("must not launch")),
    )

    response = client.post("/mcp/inspector/launch", data={"target": "anything"})
    body = response.get_json()

    assert response.status_code == 400
    assert body["ok"] is False
    assert "target" in body["error"]


def test_mcp_inspector_launch_reports_target_on_launch_error(client, monkeypatch):
    from web import app as web_app

    def raise_missing(_command):
        raise FileNotFoundError("npx")

    monkeypatch.setattr(web_app, "_launch_mcp_inspector", raise_missing)

    response = client.post("/mcp/inspector/launch", data={"target": "read_only"})
    body = response.get_json()

    assert response.status_code == 500
    assert body["ok"] is False
    assert body["target"] == "read_only"
    assert "read_only" in body["error"]
