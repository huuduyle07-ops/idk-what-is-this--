from __future__ import annotations

import ast
import json
from pathlib import Path

from core.run_lifecycle import run_patch_plan_with_artifacts


def test_patch_lifecycle_writes_replay_bundle_without_changing_apply_result(
    tmp_path,
    monkeypatch,
):
    import core.run_lifecycle as run_lifecycle

    repo = tmp_path / "repo"
    repo.mkdir()
    plan = [{"op": "create_file", "relative_path": "created.txt", "content": "hello\n"}]
    apply_result = {
        "success": True,
        "applied_ops": plan,
        "diffs": ["diff-body"],
        "rollback_performed": False,
        "failed_op_index": None,
        "failed_op": None,
        "error": None,
        "validation_ok": True,
        "validation_command": "pytest -q",
        "validation_output": "passed",
        "message": "fake executor success",
    }
    apply_calls: list[dict] = []

    monkeypatch.setattr(
        run_lifecycle,
        "collect_brain_stamp",
        lambda repo_path: {"brain_stamp_id": "stamp-life", "hash": "hash-life"},
    )
    monkeypatch.setattr(
        run_lifecycle,
        "evaluate_patch_safety",
        lambda changed_files, project_root=None: {
            "ok": True,
            "blocked_paths": [],
            "reasons": [],
        },
    )

    def fake_apply(project_root, incoming_plan, validation_command=None):
        apply_calls.append(
            {
                "project_root": project_root,
                "plan": incoming_plan,
                "validation_command": validation_command,
            }
        )
        return dict(apply_result)

    monkeypatch.setattr(run_lifecycle, "apply_patch_plan", fake_apply)

    result = run_patch_plan_with_artifacts(
        str(repo),
        plan,
        validation_command="pytest -q",
        user_query="create a file",
        control_result={"summary": "control"},
        source="unit",
    )

    assert apply_calls == [
        {
            "project_root": str(repo),
            "plan": plan,
            "validation_command": "pytest -q",
        }
    ]
    for key, value in apply_result.items():
        assert result[key] == value
    assert result["brain_stamp_id"] == "stamp-life"
    assert result["replay_id"]

    replay_dir = Path(result["replay_dir"])
    assert replay_dir.parent == repo / ".agent" / "replays"
    assert (replay_dir / "user_query.txt").read_text(encoding="utf-8") == "create a file"
    assert json.loads((replay_dir / "control_result.json").read_text(encoding="utf-8")) == {
        "summary": "control"
    }
    assert json.loads((replay_dir / "patch_parsed.json").read_text(encoding="utf-8")) == plan
    assert json.loads((replay_dir / "apply_result.json").read_text(encoding="utf-8"))[
        "success"
    ] is True
    assert (replay_dir / "validation_output.txt").read_text(encoding="utf-8") == "passed"
    manifest = json.loads((replay_dir / "replay_manifest.json").read_text(encoding="utf-8"))
    assert manifest["final_status"] == "success"
    assert manifest["pinned"] is False
    assert manifest["brain_stamp_id"] == "stamp-life"
    assert set(
        [
            "apply_result.json",
            "brain_stamp.json",
            "control_result.json",
            "events.jsonl",
            "final_status.json",
            "patch_parsed.json",
            "patch_plan.json",
            "replay_manifest.json",
            "user_query.txt",
            "validation_output.txt",
        ]
    ).issubset(set(manifest["files_present"]))


def test_partial_replay_written_for_lifecycle_safety_block(tmp_path, monkeypatch):
    import core.run_lifecycle as run_lifecycle

    repo = tmp_path / "repo"
    repo.mkdir()
    plan = [{"op": "create_file", "relative_path": ".env", "content": "secret=1\n"}]
    executor_calls: list[list[dict]] = []

    monkeypatch.setattr(
        run_lifecycle,
        "collect_brain_stamp",
        lambda repo_path: {"brain_stamp_id": "stamp-blocked"},
    )
    monkeypatch.setattr(
        run_lifecycle,
        "apply_patch_plan",
        lambda project_root, incoming_plan, validation_command=None: executor_calls.append(
            incoming_plan
        ),
    )

    result = run_patch_plan_with_artifacts(str(repo), plan, source="unit")

    assert result["success"] is False
    assert executor_calls == []
    replay_dir = Path(result["replay_dir"])
    assert replay_dir.parent == repo / ".agent" / "replays"
    assert (replay_dir / "apply_result.json").is_file()
    assert (replay_dir / "validation_output.txt").is_file()
    manifest = json.loads((replay_dir / "replay_manifest.json").read_text(encoding="utf-8"))
    assert manifest["final_status"] == "failed"
    assert "patch_safety" in json.loads(
        (replay_dir / "apply_result.json").read_text(encoding="utf-8")
    )


def test_old_debug_last_control_prompt_behavior_is_preserved():
    text = Path("core/pipeline.py").read_text(encoding="utf-8")

    assert "debug_last_control_prompt.txt" in text
    assert "build_control_prompt(" in text
    assert "build_control_prompt_human(" in text


def test_replay_lifecycle_ast_guard_for_scope():
    guarded_files = [
        Path("core/replay_recorder.py"),
        Path("core/run_lifecycle.py"),
    ]
    imports: set[str] = set()
    calls: set[str] = set()
    for path in guarded_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports |= _imported_modules(tree)
        calls |= _called_names(tree)

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
        "build_control_prompt",
        "build_deepseek_review",
        "build_prompt",
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
        "system",
        "unlink",
        "upsert_tooling_profile",
    }

    imported_roots = {name.split(".", 1)[0] for name in imports}
    assert imported_roots.isdisjoint(forbidden_import_roots)
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
