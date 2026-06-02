"""Phase 12.15c - Docker Compose Patch Preview / Apply with Backup tests.

`preview_compose_patch` computes the overlay-vs-compose diff (writes nothing).
`apply_compose_patch` backs up docker-compose.yml first, then surgically updates
ONLY the `cattus-web` service `environment:` keys, leaving other services,
volumes, healthchecks, and comments byte-identical. It never runs Docker.
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

import pytest

from core import harness_controls as hc


PROJECT_ROOT = Path(__file__).resolve().parent.parent

FIXED_NOW = datetime(2026, 6, 1, 9, 30, 0)
EXPECTED_BACKUP = "docker-compose.yml.bak-20260601_093000"

COMPOSE_BODY = (
    "services:\n"
    "  cattus-web:\n"
    "    build:\n"
    "      context: .\n"
    "    ports:\n"
    '      - "5056:5000"\n'
    "    environment:\n"
    '      WEB_HOST: "0.0.0.0"\n'
    "      # embedding provider note\n"
    '      EMBEDDING_PROVIDER: "off"\n'
    '      DB_ENABLED: "true"\n'
    '      SANDBOX_BACKEND: "temp_clone"\n'
    "\n"
    "  db:\n"
    "    image: pgvector/pgvector:pg16\n"
    "    restart: unless-stopped\n"
    "    environment:\n"
    "      POSTGRES_USER: myuser\n"
    "    healthcheck:\n"
    '      test: ["CMD-SHELL", "pg_isready -U myuser"]\n'
    "      interval: 5s\n"
    "\n"
    "volumes:\n"
    "  pgdata:\n"
)

# A compose without EMBEDDING_PROVIDER (for the append test).
COMPOSE_NO_EMBED = (
    "services:\n"
    "  cattus-web:\n"
    "    environment:\n"
    '      WEB_HOST: "0.0.0.0"\n'
    '      DB_ENABLED: "true"\n'
    "\n"
    "  db:\n"
    "    image: pg\n"
)


def _setup(tmp_path: Path, overlay: dict, body: str = COMPOSE_BODY) -> tuple[Path, Path]:
    compose_path = tmp_path / "docker-compose.yml"
    compose_path.write_text(body, encoding="utf-8")
    overlay_path = tmp_path / "harness_overrides.json"
    hc.save_overlay(overlay, overlay_path=overlay_path)
    return compose_path, overlay_path


# --------------------------------------------------------------------------
# 1-2. preview
# --------------------------------------------------------------------------

def test_preview_returns_diff_and_writes_nothing(tmp_path):
    compose_path, overlay_path = _setup(tmp_path, {"DB_ENABLED": "false"})
    before = compose_path.read_text(encoding="utf-8")
    diff = hc.preview_compose_patch(repo_path=tmp_path, overlay_path=overlay_path)
    by_var = {d["env_var"]: d for d in diff}
    assert by_var["DB_ENABLED"]["old"] == "true"
    assert by_var["DB_ENABLED"]["new"] == "false"
    assert by_var["DB_ENABLED"]["restart_required"] is True
    # nothing written
    assert compose_path.read_text(encoding="utf-8") == before


def test_preview_only_includes_compose_target_controls(tmp_path):
    # LESSON_RETRIEVAL_ENABLED targets .env only -> not eligible for compose.
    _, overlay_path = _setup(
        tmp_path, {"DB_ENABLED": "false", "LESSON_RETRIEVAL_ENABLED": "true"}
    )
    diff = hc.preview_compose_patch(repo_path=tmp_path, overlay_path=overlay_path)
    env_vars = {d["env_var"] for d in diff}
    assert "DB_ENABLED" in env_vars
    assert "LESSON_RETRIEVAL_ENABLED" not in env_vars


# --------------------------------------------------------------------------
# 3. rejections
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "control_id",
    [
        "MEMORY_TEMPERATURE_TIEBREAK_ONLY",      # planned
        "quote_grounding",                       # locked
        "nope_unknown",                          # unknown
        "LESSON_RETRIEVAL_ENABLED",              # editable but .env-only (non-compose)
    ],
)
def test_planned_locked_unknown_noncompose_rejected(tmp_path, control_id):
    compose_path, overlay_path = _setup(tmp_path, {"DB_ENABLED": "false"})
    with pytest.raises(hc.HarnessControlError):
        hc.preview_compose_patch(
            control_ids=[control_id], repo_path=tmp_path, overlay_path=overlay_path
        )
    with pytest.raises(hc.HarnessControlError):
        hc.apply_compose_patch(
            control_ids=[control_id], repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW
        )
    assert compose_path.read_text(encoding="utf-8") == COMPOSE_BODY


# --------------------------------------------------------------------------
# 4. no-op
# --------------------------------------------------------------------------

def test_no_pending_diff_is_safe_noop(tmp_path):
    compose_path, overlay_path = _setup(tmp_path, {})
    report = hc.apply_compose_patch(repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW)
    assert report["noop"] is True
    assert report["backup_created"] is None
    assert report["file_written"] is None
    assert compose_path.read_text(encoding="utf-8") == COMPOSE_BODY
    assert not (tmp_path / EXPECTED_BACKUP).exists()


# --------------------------------------------------------------------------
# 5-6. backup
# --------------------------------------------------------------------------

def test_apply_creates_backup_before_writing(tmp_path):
    compose_path, overlay_path = _setup(tmp_path, {"DB_ENABLED": "false"})
    report = hc.apply_compose_patch(repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW)
    backup = tmp_path / EXPECTED_BACKUP
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == COMPOSE_BODY
    assert report["backup_created"] == str(backup)
    assert report["file_written"] == str(compose_path)
    assert report["restart_required"] is True


def test_backup_failure_aborts_and_leaves_compose_untouched(tmp_path, monkeypatch):
    compose_path, overlay_path = _setup(tmp_path, {"DB_ENABLED": "false"})

    def _boom(*a, **k):
        raise OSError("simulated backup failure")

    monkeypatch.setattr(hc, "_backup_compose_file", _boom)
    with pytest.raises(hc.HarnessControlError):
        hc.apply_compose_patch(repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW)
    assert compose_path.read_text(encoding="utf-8") == COMPOSE_BODY
    assert not (tmp_path / EXPECTED_BACKUP).exists()


# --------------------------------------------------------------------------
# 7-10. surgical edit preserves everything else
# --------------------------------------------------------------------------

def test_only_cattus_web_env_key_changes(tmp_path):
    compose_path, overlay_path = _setup(tmp_path, {"DB_ENABLED": "false"})
    hc.apply_compose_patch(repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW)
    after = compose_path.read_text(encoding="utf-8")

    before_lines = COMPOSE_BODY.split("\n")
    after_lines = after.split("\n")
    assert len(before_lines) == len(after_lines)  # value replaced in place
    for b, a in zip(before_lines, after_lines):
        if b.strip().startswith("DB_ENABLED:"):
            assert a.strip() == 'DB_ENABLED: "false"'
        else:
            assert b == a  # everything else byte-identical


def test_unrelated_services_volumes_healthchecks_comments_preserved(tmp_path):
    compose_path, overlay_path = _setup(tmp_path, {"DB_ENABLED": "false"})
    hc.apply_compose_patch(repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW)
    after = compose_path.read_text(encoding="utf-8")
    # db service untouched
    assert "  db:\n    image: pgvector/pgvector:pg16\n" in after
    assert "    restart: unless-stopped\n" in after
    # healthcheck untouched
    assert '      test: ["CMD-SHELL", "pg_isready -U myuser"]\n' in after
    assert "      interval: 5s\n" in after
    # volumes untouched
    assert "volumes:\n  pgdata:\n" in after
    # comment untouched
    assert "      # embedding provider note\n" in after
    # the db service's own POSTGRES_USER env is NOT touched
    assert "      POSTGRES_USER: myuser\n" in after


def test_missing_target_env_key_is_appended(tmp_path):
    compose_path, overlay_path = _setup(
        tmp_path, {"EMBEDDING_PROVIDER": "gemini"}, body=COMPOSE_NO_EMBED
    )
    report = hc.apply_compose_patch(repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW)
    after = compose_path.read_text(encoding="utf-8")
    # appended under cattus-web.environment at the env-key indent (6 spaces)
    assert '      EMBEDDING_PROVIDER: "gemini"\n' in after
    # db service still intact
    assert "  db:\n    image: pg\n" in after
    changed = {c["env_var"]: c for c in report["changes"]}
    assert changed["EMBEDDING_PROVIDER"]["old"] is None
    assert changed["EMBEDDING_PROVIDER"]["new"] == "gemini"


# --------------------------------------------------------------------------
# 12-14. routes
# --------------------------------------------------------------------------

@pytest.fixture
def client():
    from web import app as web_app

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def routed_compose(tmp_path, monkeypatch):
    compose_path = tmp_path / "docker-compose.yml"
    compose_path.write_text(COMPOSE_BODY, encoding="utf-8")
    overlay_path = tmp_path / "harness_overrides.json"
    monkeypatch.setattr(hc, "default_compose_path", lambda: compose_path)
    monkeypatch.setattr(hc, "default_overlay_path", lambda: overlay_path)
    return compose_path, overlay_path


def test_compose_preview_route_happy_path(client, routed_compose):
    compose_path, overlay_path = routed_compose
    hc.save_overlay({"DB_ENABLED": "false"}, overlay_path=overlay_path)
    resp = client.post("/harness/controls/compose-preview", json={})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["ok"] is True
    env_vars = {d["env_var"] for d in body["diff"]}
    assert "DB_ENABLED" in env_vars
    # preview wrote nothing
    assert compose_path.read_text(encoding="utf-8") == COMPOSE_BODY


def test_compose_apply_route_happy_path(client, routed_compose):
    compose_path, overlay_path = routed_compose
    hc.save_overlay({"DB_ENABLED": "false"}, overlay_path=overlay_path)
    resp = client.post("/harness/controls/compose-apply", json={})
    assert resp.status_code == 200
    report = resp.get_json()["report"]
    assert report["file_written"]
    assert report["backup_created"]
    assert report["restart_required"] is True
    assert 'DB_ENABLED: "false"' in compose_path.read_text(encoding="utf-8")


def test_compose_apply_route_noop(client, routed_compose):
    resp = client.post("/harness/controls/compose-apply", json={})
    assert resp.status_code == 200
    assert resp.get_json()["report"]["noop"] is True


def test_compose_routes_reject_locked_and_unknown(client, routed_compose):
    for control_id in ("quote_grounding", "nope", "LESSON_RETRIEVAL_ENABLED"):
        r1 = client.post("/harness/controls/compose-preview", json={"control_ids": [control_id]})
        r2 = client.post("/harness/controls/compose-apply", json={"control_ids": [control_id]})
        assert r1.status_code == 400, control_id
        assert r2.status_code == 400, control_id


def test_compose_route_bad_control_ids_type(client, routed_compose):
    resp = client.post("/harness/controls/compose-apply", json={"control_ids": "DB_ENABLED"})
    assert resp.status_code == 400


# --------------------------------------------------------------------------
# 15. AST guard
# --------------------------------------------------------------------------

def _imports_and_calls(path: Path) -> tuple[list[str], list[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.append(func.id)
            elif isinstance(func, ast.Attribute):
                calls.append(func.attr)
    return imported, calls


def test_no_forbidden_imports_or_calls():
    for rel in ("core/harness_controls.py", "web/routes/harness_controls_routes.py"):
        imported, calls = _imports_and_calls(PROJECT_ROOT / rel)
        forbidden_areas = (
            "patching", "validation", "validator", "run_benchmarks", "model", "api",
        )
        for imp in imported:
            parts = imp.split(".")
            for area in forbidden_areas:
                assert not any(p == area for p in parts), (rel, imp)
        forbidden_top = {
            "requests", "httpx", "urllib", "aiohttp", "socket", "subprocess",
            "openai", "psycopg", "psycopg2", "sqlite3", "sqlalchemy", "database",
        }
        assert forbidden_top.isdisjoint(p.split(".")[0] for p in imported), rel
        forbidden_calls = {
            "call_model", "call_api", "run_gemini_request", "validate",
            "run_benchmarks", "start_benchmark_run_async", "connect", "Popen", "run",
        }
        assert forbidden_calls.isdisjoint(calls), rel
