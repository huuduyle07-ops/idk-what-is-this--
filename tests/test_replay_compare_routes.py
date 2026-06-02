"""Read-only Flask routes for Phase 13R.3 replay compare."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.replay_compare import GUARDRAIL_NOTE
from core.replay_recorder import create_replay_bundle, write_replay_artifact


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


def _summary(body: dict, name: str) -> dict:
    for item in body["compare"]["artifact_summaries"]:
        if item["artifact_name"] == name:
            return item
    raise AssertionError(f"missing summary for {name}")


def test_compare_route_returns_read_only_compare_result(client, repo):
    bundle = create_replay_bundle(repo, run_kind="patch")
    write_replay_artifact(bundle, "model_prompt.txt", "old prompt\n")
    debug_dir = repo / ".agent"
    debug_dir.mkdir(exist_ok=True)
    (debug_dir / "debug_last_control_prompt.txt").write_text(
        "new prompt\n",
        encoding="utf-8",
    )

    response = client.get(
        f"/replays/{bundle.replay_id}/compare",
        query_string={"repo_path": str(repo)},
    )
    body = response.get_json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["replay_id"] == bundle.replay_id
    assert body["compare"]["replay_id"] == bundle.replay_id
    assert body["compare"]["guardrail_note"] == GUARDRAIL_NOTE
    summary = _summary(body, "model_prompt.txt")
    assert summary["status"] == "changed"
    assert "-old prompt" in summary["diff"]
    assert "+new prompt" in summary["diff"]


def test_compare_route_handles_missing_current_artifacts(client, repo):
    bundle = create_replay_bundle(repo, run_kind="patch")
    write_replay_artifact(bundle, "model_prompt.txt", "old prompt\n")

    response = client.get(
        f"/replays/{bundle.replay_id}/compare",
        query_string={"repo_path": str(repo)},
    )
    body = response.get_json()

    assert response.status_code == 200
    summary = _summary(body, "model_prompt.txt")
    assert summary["status"] == "current_missing"
    assert "model_prompt.txt" in body["compare"]["artifacts_missing_current"]


def test_compare_route_returns_markdown_when_requested(client, repo):
    bundle = create_replay_bundle(repo, run_kind="patch")

    response = client.get(
        f"/replays/{bundle.replay_id}/compare",
        query_string={"repo_path": str(repo), "format": "markdown"},
    )

    assert response.status_code == 200
    assert response.mimetype == "text/markdown"
    assert f"# Replay Compare: {bundle.replay_id}" in response.get_data(as_text=True)


def test_compare_route_unknown_replay_returns_404(client, repo):
    response = client.get(
        "/replays/20260101_000000_missing/compare",
        query_string={"repo_path": str(repo)},
    )
    body = response.get_json()

    assert response.status_code == 404
    assert body["ok"] is False
    assert "not found" in body["error"]


@pytest.mark.parametrize("bad_id", ["..%5Cescape", "bad%20id", ".env"])
def test_compare_route_rejects_traversal_replay_id(client, repo, bad_id):
    response = client.get(
        f"/replays/{bad_id}/compare",
        query_string={"repo_path": str(repo)},
    )
    body = response.get_json()

    assert response.status_code == 400
    assert body["ok"] is False
    assert "invalid" in body["error"].lower()


def test_compare_route_ast_guard_read_only_scope():
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
