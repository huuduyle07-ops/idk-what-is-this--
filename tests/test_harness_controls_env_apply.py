"""Phase 12.15b - Environment File Apply with Backup tests.

`apply_to_env_files` explicitly writes overlay values into `.env` after a
timestamped backup. It only touches editable controls whose env_targets include
".env", never writes docker-compose.yml, edits only targeted KEY=value lines,
and leaves all other lines byte-identical.
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

import pytest

from core import harness_controls as hc


PROJECT_ROOT = Path(__file__).resolve().parent.parent

FIXED_NOW = datetime(2026, 6, 1, 9, 30, 0)
EXPECTED_BACKUP = ".env.bak-20260601_093000"

ENV_BODY = (
    "# top comment\n"
    "APP_ENV=local\n"
    "\n"
    "LESSON_RETRIEVAL_ENABLED = false\n"
    "DB_ENABLED=true\n"
    "# trailing comment\n"
)


def _setup(tmp_path: Path, overlay: dict) -> tuple[Path, Path]:
    env_path = tmp_path / ".env"
    env_path.write_text(ENV_BODY, encoding="utf-8")
    overlay_path = tmp_path / "harness_overrides.json"
    hc.save_overlay(overlay, overlay_path=overlay_path)
    return env_path, overlay_path


# --------------------------------------------------------------------------
# 1. pending diff
# --------------------------------------------------------------------------

def test_pending_env_diff_reports_overlay_vs_env(tmp_path):
    _, overlay_path = _setup(
        tmp_path,
        {"LESSON_RETRIEVAL_ENABLED": "true", "DB_ENABLED": "true"},
    )
    diff = hc.pending_env_diff(repo_path=tmp_path, overlay_path=overlay_path)
    by_id = {d["env_var"]: d for d in diff}
    # changed: false -> true
    assert "LESSON_RETRIEVAL_ENABLED" in by_id
    assert by_id["LESSON_RETRIEVAL_ENABLED"]["old"] == "false"
    assert by_id["LESSON_RETRIEVAL_ENABLED"]["new"] == "true"
    # unchanged (overlay == env) is not a diff
    assert "DB_ENABLED" not in by_id


# --------------------------------------------------------------------------
# 2-5. apply behavior
# --------------------------------------------------------------------------

def test_apply_creates_backup_before_writing(tmp_path):
    env_path, overlay_path = _setup(tmp_path, {"LESSON_RETRIEVAL_ENABLED": "true"})
    report = hc.apply_to_env_files(
        repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW
    )
    backup = tmp_path / EXPECTED_BACKUP
    assert backup.exists()
    # backup holds the ORIGINAL bytes
    assert backup.read_text(encoding="utf-8") == ENV_BODY
    assert report["backup_created"] == str(backup)
    assert report["file_written"] == str(env_path)


def test_apply_only_changes_targeted_key(tmp_path):
    env_path, overlay_path = _setup(tmp_path, {"LESSON_RETRIEVAL_ENABLED": "true"})
    hc.apply_to_env_files(repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW)
    after = env_path.read_text(encoding="utf-8")
    # targeted key updated to canonical KEY=value
    assert "LESSON_RETRIEVAL_ENABLED=true" in after
    assert "LESSON_RETRIEVAL_ENABLED = false" not in after


def test_apply_preserves_unrelated_lines_byte_identical(tmp_path):
    env_path, overlay_path = _setup(tmp_path, {"LESSON_RETRIEVAL_ENABLED": "true"})
    hc.apply_to_env_files(repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW)
    after_lines = env_path.read_text(encoding="utf-8").split("\n")
    # every line except the targeted one is identical to the original
    before_lines = ENV_BODY.split("\n")
    for before, after in zip(before_lines, after_lines):
        if before.strip().startswith("LESSON_RETRIEVAL_ENABLED"):
            continue
        assert before == after
    # comments + blank line still present
    assert "# top comment" in after_lines
    assert "# trailing comment" in after_lines
    assert "" in after_lines


def test_apply_appends_missing_key(tmp_path):
    env_path, overlay_path = _setup(tmp_path, {"MUTATION_ORACLE_ENABLED": "true"})
    report = hc.apply_to_env_files(repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW)
    after = env_path.read_text(encoding="utf-8")
    assert "MUTATION_ORACLE_ENABLED=true" in after
    changed = {c["env_var"]: c for c in report["changes"]}
    assert changed["MUTATION_ORACLE_ENABLED"]["old"] is None
    assert changed["MUTATION_ORACLE_ENABLED"]["new"] == "true"


# --------------------------------------------------------------------------
# 6. backup failure aborts
# --------------------------------------------------------------------------

def test_backup_failure_aborts_and_leaves_env_untouched(tmp_path, monkeypatch):
    env_path, overlay_path = _setup(tmp_path, {"LESSON_RETRIEVAL_ENABLED": "true"})

    def _boom(*a, **k):
        raise OSError("simulated backup failure")

    monkeypatch.setattr(hc, "_backup_env_file", _boom)
    with pytest.raises(hc.HarnessControlError):
        hc.apply_to_env_files(repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW)
    # .env unchanged; no backup file created
    assert env_path.read_text(encoding="utf-8") == ENV_BODY
    assert not (tmp_path / EXPECTED_BACKUP).exists()


# --------------------------------------------------------------------------
# 7. no-op
# --------------------------------------------------------------------------

def test_no_pending_diff_is_safe_noop(tmp_path):
    env_path, overlay_path = _setup(tmp_path, {})  # empty overlay
    report = hc.apply_to_env_files(repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW)
    assert report["noop"] is True
    assert report["backup_created"] is None
    assert report["file_written"] is None
    # nothing written, no backup
    assert env_path.read_text(encoding="utf-8") == ENV_BODY
    assert not (tmp_path / EXPECTED_BACKUP).exists()


# --------------------------------------------------------------------------
# 8. rejections
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "control_id",
    ["MEMORY_TEMPERATURE_TIEBREAK_ONLY", "quote_grounding", "nope_unknown"],
)
def test_planned_locked_unknown_controls_rejected(tmp_path, control_id):
    env_path, overlay_path = _setup(tmp_path, {"LESSON_RETRIEVAL_ENABLED": "true"})
    with pytest.raises(hc.HarnessControlError):
        hc.apply_to_env_files(
            control_ids=[control_id], repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW
        )
    assert env_path.read_text(encoding="utf-8") == ENV_BODY


# --------------------------------------------------------------------------
# docker-compose is never written by this phase
# --------------------------------------------------------------------------

def test_apply_never_writes_docker_compose(tmp_path):
    env_path, overlay_path = _setup(
        tmp_path, {"DB_ENABLED": "false", "EMBEDDING_PROVIDER": "gemini"}
    )
    compose = tmp_path / "docker-compose.yml"
    compose_body = "services:\n  db:\n    image: pg\n"
    compose.write_text(compose_body, encoding="utf-8")

    hc.apply_to_env_files(repo_path=tmp_path, overlay_path=overlay_path, now=FIXED_NOW)

    # docker-compose.yml is byte-identical (untouched) even though DB_ENABLED /
    # EMBEDDING_PROVIDER list it as an env_target.
    assert compose.read_text(encoding="utf-8") == compose_body
    # .env did get the changes
    after = env_path.read_text(encoding="utf-8")
    assert "DB_ENABLED=false" in after
    assert "EMBEDDING_PROVIDER=gemini" in after


# --------------------------------------------------------------------------
# 9-11. routes
# --------------------------------------------------------------------------

@pytest.fixture
def client():
    from web import app as web_app

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def routed_env(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(ENV_BODY, encoding="utf-8")
    overlay_path = tmp_path / "harness_overrides.json"
    monkeypatch.setattr(hc, "default_env_path", lambda: env_path)
    monkeypatch.setattr(hc, "default_overlay_path", lambda: overlay_path)
    return env_path, overlay_path


def test_apply_env_route_happy_path(client, routed_env):
    env_path, overlay_path = routed_env
    hc.save_overlay({"LESSON_RETRIEVAL_ENABLED": "true"}, overlay_path=overlay_path)
    resp = client.post("/harness/controls/apply-env", json={})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["ok"] is True
    report = body["report"]
    assert report["backup_created"]
    assert report["file_written"]
    changed = {c["env_var"] for c in report["changes"]}
    assert "LESSON_RETRIEVAL_ENABLED" in changed
    assert "LESSON_RETRIEVAL_ENABLED=true" in env_path.read_text(encoding="utf-8")


def test_apply_env_route_returns_restart_required(client, routed_env):
    env_path, overlay_path = routed_env
    hc.save_overlay({"AUTO_PATCH_ENABLED": "false"}, overlay_path=overlay_path)
    resp = client.post("/harness/controls/apply-env", json={})
    assert resp.status_code == 200
    report = resp.get_json()["report"]
    assert "AUTO_PATCH_ENABLED" in report["restart_required"]


def test_apply_env_route_rejects_locked(client, routed_env):
    resp = client.post(
        "/harness/controls/apply-env", json={"control_ids": ["quote_grounding"]}
    )
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_apply_env_route_rejects_unknown(client, routed_env):
    resp = client.post(
        "/harness/controls/apply-env", json={"control_ids": ["nope"]}
    )
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_apply_env_route_noop_when_no_overlay(client, routed_env):
    resp = client.post("/harness/controls/apply-env", json={})
    assert resp.status_code == 200
    report = resp.get_json()["report"]
    assert report["noop"] is True


# --------------------------------------------------------------------------
# 12. AST guard
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
