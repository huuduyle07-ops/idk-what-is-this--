"""Phase 8-prep — Flask client test for GET /tools/registry."""
from __future__ import annotations

import pytest


@pytest.fixture
def client():
    from web import app as web_app
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        yield c


def test_tools_registry_route_returns_tool_list(client):
    resp = client.get("/tools/registry")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert isinstance(body["tools"], list)
    assert len(body["tools"]) == 18
    names = {t["name"] for t in body["tools"]}
    assert "get_health" in names
    assert "apply_patch" in names  # registered but mcp_exposable=False
    assert "create_handoff_note" in names


def test_tools_registry_route_is_get_only(client):
    resp = client.post("/tools/registry")
    assert resp.status_code in (405, 404)


def test_tools_registry_entries_contain_required_fields(client):
    resp = client.get("/tools/registry")
    body = resp.get_json()
    required = {
        "name", "title", "description", "category", "phase",
        "reads", "writes", "can_touch_real_repo", "can_run_subprocess",
        "requires_human_approval", "mcp_exposable", "default_enabled",
        "route_or_function", "notes",
    }
    for t in body["tools"]:
        assert required.issubset(t.keys()), f"{t.get('name')} missing keys: {required - set(t.keys())}"
