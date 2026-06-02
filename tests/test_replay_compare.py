"""Read-only replay comparison helpers for Phase 13R.3."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.replay_compare import (
    GUARDRAIL_NOTE,
    compare_artifact_text,
    compare_replay_to_current,
    format_replay_compare_markdown,
)
from core.replay_recorder import (
    create_replay_bundle,
    write_replay_artifact,
    write_replay_json,
)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def _summary(result, name: str):
    for item in result.artifact_summaries:
        if item.artifact_name == name:
            return item
    raise AssertionError(f"missing summary for {name}")


def test_unchanged_artifact_reports_unchanged(tmp_path):
    repo = _repo(tmp_path)
    bundle = create_replay_bundle(repo, run_kind="patch")
    write_replay_artifact(bundle, "model_prompt.txt", "same prompt\n")
    debug_dir = repo / ".agent"
    debug_dir.mkdir(exist_ok=True)
    (debug_dir / "debug_last_control_prompt.txt").write_text(
        "same prompt\n",
        encoding="utf-8",
    )

    result = compare_replay_to_current(repo, bundle.replay_id)
    summary = _summary(result, "model_prompt.txt")

    assert summary.status == "unchanged"
    assert result.unchanged_count == 1
    assert result.changed_count == 0
    assert "model_prompt.txt" in result.artifacts_compared


def test_changed_text_artifact_reports_changed_with_additions_and_deletions():
    summary = compare_artifact_text("a\nold\n", "a\nnew\nadded\n")

    assert summary.status == "changed"
    assert summary.line_additions == 2
    assert summary.line_deletions == 1
    assert "--- replay" in summary.diff
    assert "+++ current" in summary.diff
    assert "+added" in summary.diff


def test_old_missing_artifact_is_handled(tmp_path):
    repo = _repo(tmp_path)
    bundle = create_replay_bundle(repo, run_kind="patch")

    result = compare_replay_to_current(
        repo,
        bundle.replay_id,
        current_artifacts={"control_result.json": {"ok": True}},
    )
    summary = _summary(result, "control_result.json")

    assert summary.status == "old_missing"
    assert "control_result.json" in result.artifacts_missing_old


def test_current_missing_artifact_is_handled(tmp_path):
    repo = _repo(tmp_path)
    bundle = create_replay_bundle(repo, run_kind="patch")
    write_replay_json(bundle, "brain_stamp.json", {"brain_stamp_id": "old"})

    result = compare_replay_to_current(repo, bundle.replay_id)
    summary = _summary(result, "brain_stamp.json")

    assert summary.status == "current_missing"
    assert "brain_stamp.json" in result.artifacts_missing_current
    assert summary.note == "Current artifact is not available without rerunning."


def test_large_artifact_is_skipped_gracefully(tmp_path):
    repo = _repo(tmp_path)
    bundle = create_replay_bundle(repo, run_kind="patch")
    write_replay_artifact(bundle, "model_prompt.txt", "x" * 30)

    result = compare_replay_to_current(
        repo,
        bundle.replay_id,
        current_artifacts={"model_prompt.txt": "small"},
        max_chars=10,
    )
    summary = _summary(result, "model_prompt.txt")

    assert summary.status == "skipped_large"
    assert "exceeds 10 characters" in summary.note
    assert result.changed_count == 0
    assert result.unchanged_count == 0


def test_replay_id_traversal_is_rejected(tmp_path):
    repo = _repo(tmp_path)

    with pytest.raises(ValueError, match="invalid replay id"):
        compare_replay_to_current(repo, "../escape")


def test_compare_does_not_mutate_replay_files(tmp_path):
    repo = _repo(tmp_path)
    bundle = create_replay_bundle(repo, run_kind="patch")
    write_replay_artifact(bundle, "model_prompt.txt", "old\n")
    before = {
        path.name: path.read_bytes()
        for path in bundle.replay_dir.iterdir()
        if path.is_file()
    }

    compare_replay_to_current(
        repo,
        bundle.replay_id,
        current_artifacts={"model_prompt.txt": "new\n"},
    )

    after = {
        path.name: path.read_bytes()
        for path in bundle.replay_dir.iterdir()
        if path.is_file()
    }
    assert after == before


def test_json_artifact_comparison_is_deterministic(tmp_path):
    repo = _repo(tmp_path)
    bundle = create_replay_bundle(repo, run_kind="patch")
    write_replay_json(bundle, "control_result.json", {"b": 2, "a": 1})

    result = compare_replay_to_current(
        repo,
        bundle.replay_id,
        current_artifacts={"control_result.json": {"a": 1, "b": 2}},
    )
    summary = _summary(result, "control_result.json")

    assert summary.status == "unchanged"
    assert result.unchanged_count == 1
    assert result.changed_count == 0


def test_markdown_formatter_includes_guardrail_note(tmp_path):
    repo = _repo(tmp_path)
    bundle = create_replay_bundle(repo, run_kind="patch")
    result = compare_replay_to_current(repo, bundle.replay_id)

    markdown = format_replay_compare_markdown(result)

    assert f"# Replay Compare: {bundle.replay_id}" in markdown
    assert GUARDRAIL_NOTE in markdown


def test_replay_compare_ast_guard_read_only_scope():
    tree = ast.parse(Path("core/replay_compare.py").read_text(encoding="utf-8"))
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
        "write_text",
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
