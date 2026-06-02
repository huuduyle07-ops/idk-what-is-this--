"""Read-only Flask routes for Phase 13R.2 replay viewing."""
from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.replay_recorder import (
    create_replay_bundle,
    write_replay_artifact,
    write_replay_json,
)
from web.routes import replay_routes


@pytest.fixture
def client():
    from web.app import app

    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    return path


def test_replays_route_returns_newest_first_manifests(client, repo):
    first = create_replay_bundle(
        repo,
        run_kind="first",
        now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    second = create_replay_bundle(
        repo,
        run_kind="second",
        now=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
    )

    response = client.get("/replays", query_string={"repo_path": str(repo)})
    body = response.get_json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert [item["replay_id"] for item in body["replays"]] == [
        second.replay_id,
        first.replay_id,
    ]


def test_replays_route_handles_no_replays_gracefully(client, repo):
    response = client.get("/replays", query_string={"repo_path": str(repo)})
    body = response.get_json()

    assert response.status_code == 200
    assert body == {
        "ok": True,
        "repo_path": str(repo.resolve()),
        "replays": [],
        "count": 0,
        "limit": 50,
    }


def test_replay_detail_returns_manifest_and_artifact_previews(client, repo):
    bundle = create_replay_bundle(repo, run_kind="patch", user_query="fix it")
    write_replay_json(bundle, "control_result.json", {"ok": True, "z": [2, 1]})

    response = client.get(
        f"/replays/{bundle.replay_id}",
        query_string={"repo_path": str(repo)},
    )
    body = response.get_json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["manifest"]["replay_id"] == bundle.replay_id
    assert body["artifacts"]["user_query.txt"]["captured"] is True
    assert body["artifacts"]["user_query.txt"]["preview"] == "fix it"
    control = body["artifacts"]["control_result.json"]
    assert control["captured"] is True
    assert control["content_type"] == "json"
    assert json.loads(control["preview"]) == {"ok": True, "z": [2, 1]}
    assert "\n  \"ok\": true" in control["preview"]


def test_unknown_replay_id_returns_404_json(client, repo):
    response = client.get(
        "/replays/20260101_000000_missing",
        query_string={"repo_path": str(repo)},
    )
    body = response.get_json()

    assert response.status_code == 404
    assert body["ok"] is False
    assert "not found" in body["error"]


@pytest.mark.parametrize("bad_id", ["..%5Cescape", "bad%20id", ".env"])
def test_traversal_or_invalid_replay_id_is_rejected(client, repo, bad_id):
    response = client.get(
        f"/replays/{bad_id}",
        query_string={"repo_path": str(repo)},
    )
    body = response.get_json()

    assert response.status_code == 400
    assert body["ok"] is False
    assert "invalid" in body["error"].lower()


@pytest.mark.parametrize("artifact_name", ["..%5C.env", ".env", "nested%5Cfile.txt"])
def test_traversal_or_unlisted_artifact_name_is_rejected(
    client,
    repo,
    artifact_name,
):
    bundle = create_replay_bundle(repo, run_kind="patch")

    response = client.get(
        f"/replays/{bundle.replay_id}/artifact/{artifact_name}",
        query_string={"repo_path": str(repo)},
    )
    body = response.get_json()

    assert response.status_code == 400
    assert body["ok"] is False
    assert "artifact" in body["error"].lower()


def test_missing_artifacts_do_not_crash_detail_route(client, repo):
    bundle = create_replay_bundle(repo, run_kind="partial")

    response = client.get(
        f"/replays/{bundle.replay_id}",
        query_string={"repo_path": str(repo)},
    )
    body = response.get_json()

    assert response.status_code == 200
    assert body["artifacts"]["model_prompt.txt"] == {
        "name": "model_prompt.txt",
        "captured": False,
        "content_type": "text",
        "preview": "",
        "truncated": False,
        "size_bytes": 0,
        "preview_char_limit": replay_routes.PREVIEW_CHAR_LIMIT,
    }


def test_large_artifact_preview_is_truncated(client, repo):
    bundle = create_replay_bundle(repo, run_kind="patch")
    write_replay_artifact(
        bundle,
        "model_prompt.txt",
        "x" * (replay_routes.PREVIEW_CHAR_LIMIT + 100),
    )

    response = client.get(
        f"/replays/{bundle.replay_id}",
        query_string={"repo_path": str(repo)},
    )
    artifact = response.get_json()["artifacts"]["model_prompt.txt"]

    assert artifact["captured"] is True
    assert artifact["truncated"] is True
    assert len(artifact["preview"]) == replay_routes.PREVIEW_CHAR_LIMIT


def test_artifact_route_returns_one_safe_artifact(client, repo):
    bundle = create_replay_bundle(repo, run_kind="patch")
    write_replay_artifact(bundle, "validation_output.txt", "passed\n")

    response = client.get(
        f"/replays/{bundle.replay_id}/artifact/validation_output.txt",
        query_string={"repo_path": str(repo)},
    )
    body = response.get_json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["artifact"]["preview"] == "passed\n"
    assert body["artifact"]["content_type"] == "text"


def test_artifact_route_returns_404_for_missing_allowed_artifact(client, repo):
    bundle = create_replay_bundle(repo, run_kind="patch")

    response = client.get(
        f"/replays/{bundle.replay_id}/artifact/model_prompt.txt",
        query_string={"repo_path": str(repo)},
    )
    body = response.get_json()

    assert response.status_code == 404
    assert body["ok"] is False
    assert "not captured" in body["error"]


def test_replay_viewer_routes_ast_guard_read_only_scope():
    tree = ast.parse(Path("web/routes/replay_routes.py").read_text(encoding="utf-8"))
    imports = _imported_modules(tree)
    calls = _called_names(tree)

    forbidden_import_roots = {
        "agents",
        "anthropic",
        "benchmarks",
        "database",
        "docker",
        "google",
        "openai",
        "requests",
        "httpx",
        "subprocess",
        "shutil",
    }
    forbidden_calls = {
        "ChatCompletion",
        "Popen",
        "apply_patch_plan",
        "check_call",
        "check_output",
        "commit",
        "execute",
        "executemany",
        "from_env",
        "generate_content",
        "remove",
        "removedirs",
        "rmdir",
        "rmtree",
        "run_benchmark",
        "run_benchmarks",
        "run_deepseek_review",
        "run_gemini_request",
        "run_patch_plan_with_artifacts",
        "run_validation_command",
        "start_overnight_async",
        "system",
        "unlink",
    }

    assert {name.split(".", 1)[0] for name in imports}.isdisjoint(forbidden_import_roots)
    assert calls.isdisjoint(forbidden_calls)


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names
