from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.replay_recorder import (
    create_replay_bundle,
    finalize_replay_bundle,
    list_replay_bundles,
    read_replay_manifest,
    write_replay_artifact,
    write_replay_json,
)


def test_replay_bundle_directory_is_created_under_repo_agent_replays(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    bundle = create_replay_bundle(
        repo,
        run_kind="unit",
        user_query="fix yesterday's failure",
        now=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    )

    assert bundle.replay_dir.parent == repo / ".agent" / "replays"
    assert bundle.replay_dir.is_dir()
    assert bundle.replay_id.startswith("20260102_030405_")
    assert (bundle.replay_dir / "user_query.txt").read_text(encoding="utf-8") == (
        "fix yesterday's failure"
    )


def test_replay_id_is_path_safe(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    bundle = create_replay_bundle(repo, run_kind="unit")

    assert Path(bundle.replay_id).name == bundle.replay_id
    assert "/" not in bundle.replay_id
    assert "\\" not in bundle.replay_id
    assert re.fullmatch(r"[0-9]{8}_[0-9]{6}_[A-Za-z0-9]+(?:-\d+)?", bundle.replay_id)


def test_manifest_has_schema_version_and_unpinned_default(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    bundle = create_replay_bundle(repo, run_kind="patch")
    manifest = read_replay_manifest(repo, bundle.replay_id)

    assert manifest is not None
    assert manifest["schema_version"] == 1
    assert manifest["pinned"] is False
    assert manifest["run_kind"] == "patch"
    assert manifest["replay_id"] == bundle.replay_id
    assert "replay_manifest.json" in manifest["files_present"]


def test_text_artifacts_are_written_safely(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    bundle = create_replay_bundle(repo, run_kind="unit")

    write_replay_artifact(bundle, "model_prompt.txt", "prompt body")

    assert (bundle.replay_dir / "model_prompt.txt").read_text(encoding="utf-8") == (
        "prompt body"
    )
    manifest = read_replay_manifest(repo, bundle.replay_id)
    assert "model_prompt.txt" in manifest["files_present"]


def test_json_artifacts_are_written_safely_and_update_brain_stamp(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    bundle = create_replay_bundle(repo, run_kind="unit")

    write_replay_json(bundle, "control_result.json", {"ok": True})
    write_replay_json(bundle, "brain_stamp.json", {"brain_stamp_id": "stamp-123"})

    assert json.loads((bundle.replay_dir / "control_result.json").read_text(encoding="utf-8")) == {
        "ok": True
    }
    manifest = read_replay_manifest(repo, bundle.replay_id)
    assert "control_result.json" in manifest["files_present"]
    assert manifest["brain_stamp_id"] == "stamp-123"


@pytest.mark.parametrize("name", ["../escape.txt", "nested/file.txt", r"nested\\file.txt"])
def test_path_traversal_artifact_names_are_rejected(tmp_path, name):
    repo = tmp_path / "repo"
    repo.mkdir()
    bundle = create_replay_bundle(repo, run_kind="unit")

    with pytest.raises(ValueError):
        write_replay_artifact(bundle, name, "nope")

    with pytest.raises(ValueError):
        write_replay_json(bundle, name, {})


def test_list_replay_bundles_returns_newest_first_manifests(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
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

    manifests = list_replay_bundles(repo)

    assert [item["replay_id"] for item in manifests] == [
        second.replay_id,
        first.replay_id,
    ]
    assert [item["run_kind"] for item in manifests] == ["second", "first"]


def test_partial_bundles_are_allowed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    bundle = create_replay_bundle(repo, run_kind="partial")
    manifest = read_replay_manifest(repo, bundle.replay_id)

    assert manifest["final_status"] is None
    assert manifest["files_present"] == ["replay_manifest.json"]


def test_finalization_updates_final_status_and_files_present(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    bundle = create_replay_bundle(repo, run_kind="unit")

    write_replay_json(bundle, "apply_result.json", {"success": True})
    manifest = finalize_replay_bundle(bundle, {"status": "success"})

    assert manifest["final_status"] == "success"
    assert "apply_result.json" in manifest["files_present"]
    assert "final_status.json" in manifest["files_present"]


def test_read_replay_manifest_rejects_path_traversal_ids(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(ValueError):
        read_replay_manifest(repo, "../escape")


def test_replay_recorder_ast_guard_has_no_unsafe_side_effects():
    src = Path("core/replay_recorder.py")
    tree = ast.parse(src.read_text(encoding="utf-8"))
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
        "run_gemini_request",
        "run_deepseek_review",
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
