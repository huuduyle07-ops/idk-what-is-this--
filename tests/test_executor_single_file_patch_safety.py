from __future__ import annotations

import ast
from pathlib import Path

import pytest


THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]


def _seed(repo: Path, relative_path: str, text: str) -> Path:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _patch(relative_path: str, target: str = "old\n", patched: str = "new\n") -> dict:
    return {
        "file": relative_path,
        "relative_path": relative_path,
        "target_snippet": target,
        "patched_snippet": patched,
        "target_node_name": "value",
        "target_node_kind": "function",
    }


def test_safe_single_file_source_patch_still_applies(monkeypatch, tmp_path):
    import config
    import core.executor as executor_mod
    from core.executor import Executor

    repo = tmp_path / "repo"
    repo.mkdir()
    source = "def greet(name):\n    return 'hi ' + name\n"
    target = _seed(repo, "src/app.py", source)
    patch = _patch(
        "src/app.py",
        target=source,
        patched="def greet(name):\n    return 'hello ' + name\n",
    )
    patch["target_node_name"] = "greet"

    validation_calls: list[tuple[str, str]] = []

    def fake_run(command, cwd, timeout=30):
        validation_calls.append((command, cwd))
        return True, "ok"

    monkeypatch.setattr(config, "MUTATION_ORACLE_ENABLED", False, raising=False)
    monkeypatch.setattr(executor_mod, "run_validation_command", fake_run)

    result = Executor(str(repo)).run(
        patch,
        language="python",
        validation_command="python -m pytest -q",
    )

    assert result.success is True
    assert result.phase == "validated"
    assert result.patch_safety_blocked is False
    assert result.patch_safety is None
    assert validation_calls == [("python -m pytest -q", str(repo.resolve()))]
    assert target.read_text(encoding="utf-8") == (
        "def greet(name):\n    return 'hello ' + name\n"
    )


@pytest.mark.parametrize(
    ("relative_path", "category"),
    [
        (".env", "env"),
        (".agent/session.json", "protected_dir"),
        ("tests/test_app.py", "test"),
        ("benchmarks/cases/python/example/case.json", "benchmark_validation"),
    ],
)
def test_single_file_patch_safety_blocks_sensitive_targets_before_apply(
    monkeypatch, tmp_path, relative_path, category
):
    import core.executor as executor_mod
    from core.executor import Executor

    repo = tmp_path / "repo"
    repo.mkdir()
    target = _seed(repo, relative_path, "old\n")
    apply_calls: list[tuple] = []

    def apply_must_not_run(*args, **kwargs):  # pragma: no cover - tripwire
        apply_calls.append((args, kwargs))
        raise AssertionError("apply_patch_from_json must not run after safety block")

    monkeypatch.setattr(executor_mod, "apply_patch_from_json", apply_must_not_run)

    result = Executor(str(repo)).run(
        _patch(relative_path),
        language="python",
        validation_command="python -m pytest -q",
    )

    assert result.success is False
    assert result.phase == "patch_safety_blocked"
    assert result.patch_safety_blocked is True
    assert result.patch_safety["ok"] is False
    assert result.patch_safety["blocked_paths"][0]["category"] == category
    assert result.patch_safety_reasons == result.patch_safety["reasons"]
    assert result.blocked_reason.startswith("Patch blocked by safety gate")
    assert result.validation_ok is None
    assert result.rollback_performed is False
    assert apply_calls == []
    assert target.read_text(encoding="utf-8") == "old\n"


def test_validation_and_rollback_are_not_run_after_patch_safety_block(
    monkeypatch, tmp_path
):
    import core.executor as executor_mod
    from core.executor import Executor

    repo = tmp_path / "repo"
    repo.mkdir()
    _seed(repo, ".agent/session.json", "old\n")
    calls: list[str] = []

    def apply_must_not_run(*args, **kwargs):  # pragma: no cover - tripwire
        calls.append("apply")
        raise AssertionError("apply_patch_from_json must not run after safety block")

    def validation_must_not_run(*args, **kwargs):  # pragma: no cover - tripwire
        calls.append("validation")
        raise AssertionError("validation must not run after safety block")

    def rollback_must_not_run(*args, **kwargs):  # pragma: no cover - tripwire
        calls.append("rollback")
        raise AssertionError("rollback must not run when no write happened")

    monkeypatch.setattr(executor_mod, "apply_patch_from_json", apply_must_not_run)
    monkeypatch.setattr(executor_mod, "run_validation_command", validation_must_not_run)
    monkeypatch.setattr(executor_mod, "restore_backup", rollback_must_not_run)

    result = Executor(str(repo)).run(
        _patch(".agent/session.json"),
        language="python",
        validation_command="python -m pytest -q",
    )

    assert result.phase == "patch_safety_blocked"
    assert result.validation_ok is None
    assert result.rollback_performed is False
    assert calls == []


def test_path_traversal_remains_blocked_before_apply(monkeypatch, tmp_path):
    import core.executor as executor_mod
    from core.executor import Executor

    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.py"

    def apply_must_not_run(*args, **kwargs):  # pragma: no cover - tripwire
        raise AssertionError("apply_patch_from_json must not run for traversal")

    monkeypatch.setattr(executor_mod, "apply_patch_from_json", apply_must_not_run)

    result = Executor(str(repo)).run(
        _patch("../outside.py"),
        language="python",
        validation_command="python -m pytest -q",
    )

    assert result.success is False
    assert result.phase == "patch_safety_blocked"
    assert result.patch_safety["blocked_paths"][0]["category"] == "traversal"
    assert result.rollback_performed is False
    assert not outside.exists()


def test_self_correct_loop_treats_patch_safety_block_as_policy_block(tmp_path):
    from core.self_correct_loop import run_self_correct_loop

    repo = tmp_path / "repo"
    repo.mkdir()
    _seed(repo, ".agent/session.json", "old\n")

    def re_patch_must_not_run(*args, **kwargs):  # pragma: no cover - tripwire
        raise AssertionError("patch_safety blocks must not trigger re-prompting")

    result = run_self_correct_loop(
        project_root=str(repo),
        initial_patch=_patch(".agent/session.json"),
        language="python",
        re_patch_fn=re_patch_must_not_run,
        validation_command="python -m pytest -q",
        max_attempts=2,
    )

    assert result["success"] is False
    assert result["final_phase"] == "patch_safety_blocked"
    assert result["stop_reason"] == "policy_block"
    assert result["attempts"][0]["patch_safety_blocked"] is True
    assert result["attempts"][0]["patch_safety"]["blocked_paths"][0]["category"] == (
        "protected_dir"
    )
    assert (repo / ".agent/session.json").read_text(encoding="utf-8") == "old\n"


def test_executor_single_file_patch_safety_ast_guard():
    guarded_files = [
        THIS_FILE,
        PROJECT_ROOT / "core" / "executor.py",
    ]
    imports: set[str] = set()
    calls: set[str] = set()
    policy_assignments: set[str] = set()
    for path in guarded_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports |= _imported_modules(tree)
        calls |= _called_names(tree)
        policy_assignments |= _assigned_policy_names(tree)

    imported_roots = {name.split(".", 1)[0] for name in imports}
    forbidden_import_roots = {
        "agents",
        "benchmarks",
        "database",
        "docker",
        "google",
        "openai",
        "requests",
        "httpx",
        "subprocess",
        "socket",
    }
    assert imported_roots.isdisjoint(forbidden_import_roots)

    forbidden_calls = {
        "ChatCompletion",
        "generate_content",
        "run_gemini",
        "run_ollama",
        "build_control_prompt",
        "commit",
        "execute",
        "executemany",
        "run_benchmark",
        "run_benchmarks",
        "Popen",
        "check_call",
        "check_output",
        "system",
        "rmtree",
        "remove",
    }
    assert forbidden_calls.isdisjoint(calls)
    assert policy_assignments == set()


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
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
                elif isinstance(target, ast.Attribute) and target.attr in policy_names:
                    assigned.add(target.attr)
    return assigned
