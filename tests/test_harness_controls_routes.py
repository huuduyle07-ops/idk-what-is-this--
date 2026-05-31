"""Phase 12.15a - Harness Control routes tests.

GET /harness/controls returns the grouped registry + read-only docker status.
POST /harness/controls/overlay saves a desired override (Save overlay) and
live-patches editable_live controls; it rejects planned/locked/unknown controls.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client():
    from web import app as web_app

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _isolated_overlay(tmp_path, monkeypatch):
    """Point the overlay at a temp file so tests never touch the real .agent."""
    from core import harness_controls as hc

    overlay = tmp_path / "harness_overrides.json"
    monkeypatch.setattr(hc, "default_overlay_path", lambda: overlay)
    return overlay


def test_get_controls_returns_categories_and_docker_status(client):
    resp = client.get("/harness/controls")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert "categories" in body
    cats = body["categories"]
    # grouped by category
    assert "gates" in cats and "invariants" in cats
    all_ids = {c["id"] for group in cats.values() for c in group}
    assert "LESSON_RETRIEVAL_ENABLED" in all_ids
    assert "quote_grounding" in all_ids
    # docker status present (read-only probe; value not asserted)
    assert "docker_status" in body


def test_overlay_route_happy_path_live_control(client, monkeypatch):
    import config as config_module

    # Auto-restored after the test regardless of what the route sets.
    monkeypatch.setattr(config_module, "MUTATION_ORACLE_ENABLED", False, raising=False)

    resp = client.post(
        "/harness/controls/overlay",
        json={"control_id": "MUTATION_ORACLE_ENABLED", "value": "true"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["ok"] is True
    assert body["control"]["applied_live"] is True
    assert config_module.MUTATION_ORACLE_ENABLED is True


def test_overlay_route_restart_required_does_not_patch_live(client, monkeypatch):
    import config as config_module

    monkeypatch.setattr(config_module, "AUTO_PATCH_ENABLED", True, raising=False)
    resp = client.post(
        "/harness/controls/overlay",
        json={"control_id": "AUTO_PATCH_ENABLED", "value": "false"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["control"]["applied_live"] is False
    assert body["control"]["restart_required"] is True
    # live config untouched
    assert config_module.AUTO_PATCH_ENABLED is True


def test_overlay_route_rejects_planned_control(client):
    resp = client.post(
        "/harness/controls/overlay",
        json={"control_id": "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED", "value": "true"},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False


def test_overlay_route_rejects_locked_invariant(client):
    resp = client.post(
        "/harness/controls/overlay",
        json={"control_id": "quote_grounding", "value": "false"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_overlay_route_rejects_unknown_control(client):
    resp = client.post(
        "/harness/controls/overlay",
        json={"control_id": "nope", "value": "true"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_overlay_route_rejects_missing_control_id(client):
    resp = client.post("/harness/controls/overlay", json={"value": "true"})
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_routes_module_has_no_forbidden_imports():
    source = (PROJECT_ROOT / "web" / "routes" / "harness_controls_routes.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden_areas = ("patching", "validation", "validator", "run_benchmarks", "model")
    for imp in imported:
        parts = imp.split(".")
        for area in forbidden_areas:
            assert not any(p == area for p in parts), imp

    forbidden_top = {
        "requests", "httpx", "subprocess", "openai",
        "psycopg", "psycopg2", "sqlite3", "sqlalchemy", "database",
    }
    assert forbidden_top.isdisjoint(p.split(".")[0] for p in imported)
