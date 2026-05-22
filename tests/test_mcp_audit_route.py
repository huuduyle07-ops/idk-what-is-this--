"""Flask route tests for the read-only MCP audit view."""
from __future__ import annotations

import pytest


@pytest.fixture
def client():
    from web import app as web_app

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as test_client:
        yield test_client


def test_mcp_audit_route_returns_count_and_limit(client, monkeypatch):
    from web import app as web_app

    monkeypatch.setattr(
        web_app,
        "list_mcp_invocations",
        lambda limit=50: [{"id": "one", "limit_seen": limit}],
        raising=False,
    )

    response = client.get("/mcp/audit?limit=7")

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "events": [{"id": "one", "limit_seen": 7}],
        "count": 1,
        "limit": 7,
    }


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", 50),
        ("?limit=nope", 50),
        ("?limit=0", 50),
        ("?limit=-3", 50),
        ("?limit=999", 200),
    ],
)
def test_mcp_audit_route_normalizes_limit(client, monkeypatch, query, expected):
    from web import app as web_app

    seen = []
    monkeypatch.setattr(
        web_app,
        "list_mcp_invocations",
        lambda limit=50: seen.append(limit) or [],
        raising=False,
    )

    response = client.get("/mcp/audit" + query)

    assert response.status_code == 200
    assert seen == [expected]
    assert response.get_json()["limit"] == expected


def test_mcp_audit_route_is_get_only(client):
    response = client.post("/mcp/audit")

    assert response.status_code in (404, 405)
