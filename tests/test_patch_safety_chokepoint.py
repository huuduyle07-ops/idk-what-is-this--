from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


THIS_FILE = Path(__file__).resolve()


def _patch_candidate(relative_path: str) -> dict:
    return {
        "relative_path": relative_path,
        "target_snippet": "old\n",
        "patched_snippet": "new\n",
    }


def _replace_plan(relative_path: str) -> list[dict]:
    return [
        {
            "op": "replace_snippet",
            "relative_path": relative_path,
            "target_snippet": "old\n",
            "patched_snippet": "new\n",
        }
    ]


def _create_plan(relative_path: str) -> list[dict]:
    return [
        {
            "op": "create_file",
            "relative_path": relative_path,
            "content": "created by characterization test\n",
        }
    ]


def _client():
    from web.app import app

    app.config["TESTING"] = True
    return app.test_client()


def _patch_lifecycle_replay(monkeypatch, tmp_path):
    import core.run_artifacts as run_artifacts
    import core.run_lifecycle as run_lifecycle

    monkeypatch.setattr(
        run_artifacts,
        "get_agent_dir",
        lambda repo_path=None: tmp_path / ".agent",
    )
    monkeypatch.setattr(
        run_lifecycle,
        "collect_brain_stamp",
        lambda repo_path: {"brain_stamp_id": "phase-13-4", "schema_version": 2},
    )
    return run_lifecycle


def test_current_web_apply_patch_rejects_test_file_through_evaluate_patch_safety(
    monkeypatch, tmp_path
):
    from core.patch_safety import evaluate_patch_safety as real_evaluate
    from web.routes import patch_routes

    repo = tmp_path / "repo"
    repo.mkdir()
    safety_calls: list[list[str]] = []

    def spy(changed_files, project_root=None):
        safety_calls.append(list(changed_files))
        return real_evaluate(changed_files, project_root=project_root)

    class ExecutorMustNotRun:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Executor ran after patch safety blocked the route")

    monkeypatch.setattr(patch_routes, "evaluate_patch_safety", spy)
    monkeypatch.setattr(patch_routes, "Executor", ExecutorMustNotRun)

    resp = _client().post(
        "/apply_patch",
        data={
            "repo_path": str(repo),
            "patch": json.dumps(_patch_candidate("tests/test_app.py")),
        },
    )

    body = resp.get_json()
    assert resp.status_code == 200
    assert safety_calls == [["tests/test_app.py"]]
    assert body["success"] is False
    assert body["patch_safety"]["blocked_paths"][0]["category"] == "test"
    assert "Patch blocked by safety gate" in body["message"]


def test_current_web_apply_patch_rejects_env_file_through_evaluate_patch_safety(
    monkeypatch, tmp_path
):
    from core.patch_safety import evaluate_patch_safety as real_evaluate
    from web.routes import patch_routes

    repo = tmp_path / "repo"
    repo.mkdir()
    safety_calls: list[list[str]] = []

    def spy(changed_files, project_root=None):
        safety_calls.append(list(changed_files))
        return real_evaluate(changed_files, project_root=project_root)

    class ExecutorMustNotRun:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Executor ran after patch safety blocked the route")

    monkeypatch.setattr(patch_routes, "evaluate_patch_safety", spy)
    monkeypatch.setattr(patch_routes, "Executor", ExecutorMustNotRun)

    resp = _client().post(
        "/apply_patch",
        data={
            "repo_path": str(repo),
            "patch": json.dumps(_patch_candidate(".env")),
        },
    )

    body = resp.get_json()
    assert resp.status_code == 200
    assert safety_calls == [[".env"]]
    assert body["success"] is False
    assert body["patch_safety"]["blocked_paths"][0]["category"] == "env"
    assert "Patch blocked by safety gate" in body["message"]


@pytest.mark.parametrize(
    ("relative_path", "category"),
    [
        ("tests/test_app.py", "test"),
        ("benchmarks/cases/python/example/case.json", "benchmark_validation"),
        (".env", "env"),
        (".agent/session.json", "protected_dir"),
        ("../outside.py", "traversal"),
    ],
)
def test_current_web_apply_patch_plan_rejects_protected_categories_before_executor(
    monkeypatch, tmp_path, relative_path, category
):
    from core.patch_safety import evaluate_patch_safety as real_evaluate
    from web.routes import patch_routes

    repo = tmp_path / "repo"
    repo.mkdir()
    safety_calls: list[list[str]] = []
    executor_calls: list[dict] = []

    def spy(changed_files, project_root=None):
        safety_calls.append(list(changed_files))
        return real_evaluate(changed_files, project_root=project_root)

    def executor_must_not_run(*args, **kwargs):
        executor_calls.append({"args": args, "kwargs": kwargs})
        raise AssertionError("run_patch_plan_with_artifacts ran after safety block")

    monkeypatch.setattr(patch_routes, "evaluate_patch_safety", spy)
    monkeypatch.setattr(
        patch_routes,
        "run_patch_plan_with_artifacts",
        executor_must_not_run,
    )

    resp = _client().post(
        "/apply_patch_plan",
        data={
            "repo_path": str(repo),
            "patch_style": "balanced",
            "patch": json.dumps({"patch_plan": _replace_plan(relative_path)}),
        },
    )

    body = resp.get_json()
    assert resp.status_code == 200
    assert safety_calls == [[relative_path]]
    assert executor_calls == []
    assert body["success"] is False
    assert body["patch_safety"]["blocked_paths"][0]["category"] == category
    assert "Patch plan blocked by safety gate" in body["message"]


def test_current_patch_plan_executor_rejects_path_traversal_without_policy_gate(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.py"

    result = apply_patch_plan(str(repo), _create_plan("../outside.py"))

    assert result["success"] is False
    assert "escapes repo" in result["error"]
    assert result["failed_op"]["relative_path"] == "../outside.py"
    assert not outside.exists()


@pytest.mark.parametrize(
    "relative_path",
    [
        "tests/test_app.py",
        "benchmarks/cases/python/example/case.json",
        ".env",
        ".agent/session.json",
    ],
)
def test_current_patch_plan_executor_allows_policy_protected_categories_without_safety_gate(
    tmp_path, relative_path
):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()

    result = apply_patch_plan(str(repo), _create_plan(relative_path))

    assert result["success"] is True
    assert result["error"] is None
    assert (repo / relative_path).read_text(encoding="utf-8") == (
        "created by characterization test\n"
    )


def test_hardened_run_lifecycle_calls_evaluate_patch_safety_before_executor(
    monkeypatch, tmp_path
):
    run_lifecycle = _patch_lifecycle_replay(monkeypatch, tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    plan = _replace_plan("src/app.py")
    safety_calls: list[tuple[list[str], Path]] = []
    executor_calls: list[list[dict]] = []

    def safety_spy(changed_files, project_root=None):
        safety_calls.append((list(changed_files), Path(project_root)))
        return {"ok": True, "blocked_paths": [], "reasons": []}

    def fake_apply(project_root, incoming_plan, validation_command=None):
        executor_calls.append(incoming_plan)
        return {
            "success": True,
            "applied_ops": incoming_plan,
            "diffs": [],
            "rollback_performed": False,
            "error": None,
            "validation_output": "",
            "message": "fake executor success",
        }

    monkeypatch.setattr(run_lifecycle, "evaluate_patch_safety", safety_spy, raising=False)
    monkeypatch.setattr(run_lifecycle, "apply_patch_plan", fake_apply)

    result = run_lifecycle.run_patch_plan_with_artifacts(str(repo), plan, source="unit")

    assert result["success"] is True
    assert safety_calls == [(["src/app.py"], repo.resolve())]
    assert executor_calls == [plan]


@pytest.mark.parametrize(
    ("relative_path", "category"),
    [
        ("tests/test_app.py", "test"),
        ("benchmarks/cases/python/example/case.json", "benchmark_validation"),
        (".env", "env"),
        (".agent/session.json", "protected_dir"),
        ("../outside.py", "traversal"),
    ],
)
def test_hardened_run_lifecycle_blocks_unsafe_patch_plans_before_executor(
    monkeypatch, tmp_path, relative_path, category
):
    run_lifecycle = _patch_lifecycle_replay(monkeypatch, tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    plan = _create_plan(relative_path)
    executor_calls: list[list[dict]] = []

    def fake_apply(project_root, incoming_plan, validation_command=None):
        executor_calls.append(incoming_plan)
        return {
            "success": True,
            "applied_ops": incoming_plan,
            "diffs": [],
            "rollback_performed": False,
            "error": None,
            "validation_output": "",
            "message": "fake executor success",
        }

    monkeypatch.setattr(run_lifecycle, "apply_patch_plan", fake_apply)

    result = run_lifecycle.run_patch_plan_with_artifacts(str(repo), plan, source="unit")

    assert result["success"] is False
    assert executor_calls == []
    assert result["patch_safety"]["blocked_paths"][0]["category"] == category
    assert "Patch plan blocked by safety gate" in result["message"]
    assert result["rollback_performed"] is False


def test_hardened_safe_source_file_patch_plan_reaches_patch_plan_executor(
    monkeypatch, tmp_path
):
    run_lifecycle = _patch_lifecycle_replay(monkeypatch, tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    plan = _create_plan("src/new_feature.py")
    executor_calls: list[list[dict]] = []

    def fake_apply(project_root, incoming_plan, validation_command=None):
        executor_calls.append(incoming_plan)
        return {
            "success": True,
            "applied_ops": incoming_plan,
            "diffs": [],
            "rollback_performed": False,
            "error": None,
            "validation_output": "",
            "message": "fake executor success",
        }

    monkeypatch.setattr(run_lifecycle, "apply_patch_plan", fake_apply)

    result = run_lifecycle.run_patch_plan_with_artifacts(str(repo), plan, source="unit")

    assert result["success"] is True
    assert executor_calls == [plan]


def test_hardened_blocked_patch_plan_does_not_create_or_modify_target_file(
    monkeypatch, tmp_path
):
    run_lifecycle = _patch_lifecycle_replay(monkeypatch, tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / ".env"

    result = run_lifecycle.run_patch_plan_with_artifacts(
        str(repo),
        _create_plan(".env"),
        source="unit",
    )

    assert result["success"] is False
    assert result["patch_safety"]["blocked_paths"][0]["category"] == "env"
    assert not target.exists()


def test_hardened_maybe_run_auto_patch_path_is_protected_by_lifecycle_safety(
    monkeypatch, tmp_path
):
    run_lifecycle = _patch_lifecycle_replay(monkeypatch, tmp_path)
    import core.pipeline as pipeline
    from core.agent_state import AgentState

    repo = tmp_path / "repo"
    repo.mkdir()
    plan = _replace_plan("benchmarks/cases/python/example/case.json")
    executor_calls: list[list[dict]] = []

    def fake_apply(project_root, incoming_plan, validation_command=None):
        executor_calls.append(incoming_plan)
        return {
            "success": True,
            "applied_ops": incoming_plan,
            "diffs": [],
            "rollback_performed": False,
            "error": None,
            "validation_output": "",
            "message": "fake lifecycle success",
        }

    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", True)
    monkeypatch.setattr(
        pipeline,
        "normalize_patch_candidate_with_control_source",
        lambda state: None,
    )
    monkeypatch.setattr(pipeline, "get_confidence_and_escalation", lambda block: (1.0, False))
    monkeypatch.setattr(pipeline, "extract_user_validation_command", lambda text: "")
    monkeypatch.setattr(pipeline, "get_default_validation_command", lambda language, root: "")
    monkeypatch.setattr(pipeline, "save_patch_attempt", lambda **kwargs: None)
    monkeypatch.setattr(
        pipeline,
        "run_patch_plan_with_artifacts",
        run_lifecycle.run_patch_plan_with_artifacts,
    )
    monkeypatch.setattr(run_lifecycle, "apply_patch_plan", fake_apply)

    state = AgentState(
        interface="cli",
        mode="reviewer",
        user_input="fix the benchmark example",
        file_paths=[],
        primary_file=None,
        input_mode="project",
        language="python",
        task_type="bug_fix",
        task_info={"patch_style": "balanced", "intent": "bug_fix"},
        repo_path=str(repo),
        patch_style="balanced",
        json_block={
            "patch_candidate": None,
            "patch_plan": plan,
            "confidence": 1.0,
            "needs_escalation": False,
        },
        control_result={
            "top_hypothesis": {
                "recommended_action": "patch",
                "confidence": 1.0,
            },
            "scout": {"request_type": "bug_fix"},
        },
    )

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert executor_calls == []
    assert "Patch plan blocked by safety gate" in state.auto_patch_result
    assert not (repo / "benchmarks/cases/python/example/case.json").exists()


def test_patch_safety_chokepoint_ast_guard_for_hardening_scope():
    guarded_files = [
        THIS_FILE,
        THIS_FILE.parents[1] / "core" / "run_lifecycle.py",
    ]
    imports: set[str] = set()
    calls: set[str] = set()
    policy_assignments: set[str] = set()
    for path in guarded_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports |= _imported_modules(tree)
        calls |= _called_names(tree)
        policy_assignments |= _assigned_policy_names(tree)

    forbidden_import_roots = {
        "agents",
        "benchmarks",
        "database",
        "docker",
        "google",
        "openai",
        "subprocess",
    }
    forbidden_imports = {"core.prompter"}
    forbidden_calls = {
        "ChatCompletion",
        "build_prompt",
        "build_control_prompt",
        "build_deepseek_review",
        "Popen",
        "check_call",
        "check_output",
        "commit",
        "execute",
        "executemany",
        "generate_content",
        "run_benchmark",
        "run_benchmarks",
        "run_gemini",
        "run_ollama",
        "save_artifact",
        "save_engineering_memory",
        "system",
        "upsert_tooling_profile",
    }

    imported_roots = {name.split(".", 1)[0] for name in imports}
    assert imported_roots.isdisjoint(forbidden_import_roots)
    assert imports.isdisjoint(forbidden_imports)
    assert calls.isdisjoint(forbidden_calls)
    assert policy_assignments == set()


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


def _assigned_policy_names(tree: ast.AST) -> set[str]:
    policy_names = {
        "_CATEGORY_WHY",
        "_PROTECTED_DIRS",
        "_TEST_DIRS",
        "_TEST_FILE_NAMES",
        "_TEST_SUFFIXES",
    }
    assigned: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in policy_names:
                    assigned.add(target.id)
                elif (
                    isinstance(target, ast.Attribute)
                    and target.attr in policy_names
                ):
                    assigned.add(target.attr)
    return assigned
