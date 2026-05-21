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
    assert len(body["tools"]) == 19
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


# --- Phase 8-prep.1: mode-aware allowlist behavior -------------------------

def _tools_by_name(body):
    return {t["name"]: t for t in body["tools"]}


def test_tools_registry_default_mode_is_read_only(client):
    resp = client.get("/tools/registry")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["capability_mode"] == "read_only"


def test_tools_registry_invalid_mode_returns_400(client):
    resp = client.get("/tools/registry?mode=root")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "mode" in body.get("error", "").lower()


def test_tools_registry_read_only_marks_get_health_allowed_and_apply_patch_not(client):
    resp = client.get("/tools/registry?mode=read_only")
    body = resp.get_json()
    by_name = _tools_by_name(body)
    assert by_name["get_health"]["allowed"] is True
    assert by_name["apply_patch"]["allowed"] is False


def test_tools_registry_artifact_write_marks_validate_allowed(client):
    resp = client.get("/tools/registry?mode=artifact_write")
    body = resp.get_json()
    by_name = _tools_by_name(body)
    assert by_name["validate_imported_worker_proposal"]["allowed"] is True
    # And read tools stay allowed in this mode
    assert by_name["get_health"]["allowed"] is True
    # But real-repo writes remain blocked
    assert by_name["apply_patch"]["allowed"] is False


def test_tools_registry_operator_still_blocks_apply_patch(client):
    resp = client.get("/tools/registry?mode=operator")
    body = resp.get_json()
    by_name = _tools_by_name(body)
    assert by_name["apply_patch"]["allowed"] is False
    assert by_name["apply_patch_plan"]["allowed"] is False
    assert by_name["dream_apply"]["allowed"] is False


def test_tools_registry_response_includes_allowed_count_and_total_count(client):
    resp = client.get("/tools/registry?mode=read_only")
    body = resp.get_json()
    assert body["total_count"] == len(body["tools"])
    assert body["allowed_count"] == sum(1 for t in body["tools"] if t["allowed"])
    # In read_only every `read` category tool is exposable -> 10 allowed
    # (9 original read tools + list_tool_registry added in Phase 8.1).
    assert body["allowed_count"] == 10


def test_tools_registry_route_does_not_execute_tools(client):
    """Pure metadata read: response shape must not contain any tool execution
    artifacts (apply_result, validation_output, worker run ids, etc.), and the
    call must be idempotent.
    """
    forbidden_keys = {
        "apply_result", "applied", "validation_output", "validation",
        "worker_run", "subprocess_output", "rolled_back",
    }
    r1 = client.get("/tools/registry").get_json()
    r2 = client.get("/tools/registry").get_json()
    assert r1 == r2  # idempotent
    assert not (forbidden_keys & set(r1.keys()))
    for t in r1["tools"]:
        assert not (forbidden_keys & set(t.keys())), (
            f"{t['name']} leaked execution-shaped field"
        )
