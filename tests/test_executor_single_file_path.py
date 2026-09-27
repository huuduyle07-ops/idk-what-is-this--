"""Phase 13.13 - Executor single-file path characterization / coverage.

A pure coverage slice (tests only) that locks down the *current* behavior of the
single-file patch execution path before any future refactor. It exercises the
three entry points that move a single-file change to disk:

  * ``patching.patch_plan_executor.apply_patch_plan`` - the atomic op executor
    (a single-op plan == a single-file change);
  * ``core.run_lifecycle.run_patch_plan_with_artifacts`` - the hardened
    lifecycle chokepoint that runs ``evaluate_patch_safety`` BEFORE the executor
    (Phase 13.4);
  * ``core.executor.Executor.run`` - the single-file ``patch_candidate``
    executor, whose validation flows through the hardened
    ``core.validator.run_validation_command`` shell sink (Phase 13.6).

These tests assert behavior as it is today; they do not change production code.
No model/API calls, no DB writes, no benchmark execution, no Docker lifecycle,
and no real destructive command ever runs (the one unsafe command is blocked by
the 13.6 gate before the shell, with ``subprocess`` stubbed as a tripwire).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _replace_plan(relative_path: str, target: str = "old\n", patched: str = "new\n") -> list[dict]:
    return [
        {
            "op": "replace_snippet",
            "relative_path": relative_path,
            "target_snippet": target,
            "patched_snippet": patched,
        }
    ]


def _create_plan(relative_path: str, content: str = "created\n") -> list[dict]:
    return [{"op": "create_file", "relative_path": relative_path, "content": content}]


def _seed(repo: Path, relative_path: str, text: str) -> Path:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _patch_lifecycle(monkeypatch, repo: Path):
    """Mirror the chokepoint test fixture: keep replay artifacts inside the repo
    and avoid the real brain-stamp scan, so the lifecycle runs hermetically."""
    import core.run_artifacts as run_artifacts
    import core.run_lifecycle as run_lifecycle

    monkeypatch.setattr(
        run_artifacts, "get_agent_dir", lambda repo_path=None: repo / ".agent"
    )
    monkeypatch.setattr(
        run_lifecycle,
        "collect_brain_stamp",
        lambda repo_path: {"brain_stamp_id": "phase-13-13", "schema_version": 2},
    )
    return run_lifecycle


class _SubprocessTripwire:
    """Stand-in for ``core.validator.subprocess`` that must never run a command.

    Used to prove the 13.6 safety gate refuses destructive validation commands
    *before* the shell is ever reached.
    """

    TimeoutExpired = Exception

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def run(self, *args, **kwargs):  # pragma: no cover - asserts non-invocation
        self.calls.append((args, kwargs))
        raise AssertionError("subprocess.run must not execute a blocked command")


# ===========================================================================
# 1. Safe single-file patch applies through the intended executor path
# ===========================================================================
def test_safe_single_file_create_applies_through_patch_plan_executor(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()

    result = apply_patch_plan(str(repo), _create_plan("src/new_feature.py", "print('hi')\n"))

    assert result["success"] is True
    assert result["error"] is None
    assert result["rollback_performed"] is False
    assert (repo / "src/new_feature.py").read_text(encoding="utf-8") == "print('hi')\n"


def test_safe_single_file_replace_applies_through_run_lifecycle_chokepoint(
    monkeypatch, tmp_path
):
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed(repo, "src/app.py", "old\n")
    run_lifecycle = _patch_lifecycle(monkeypatch, repo)

    result = run_lifecycle.run_patch_plan_with_artifacts(
        str(repo), _replace_plan("src/app.py"), source="unit"
    )

    assert result["success"] is True
    assert result["error"] is None
    # Characterization: on the success path the safety gate passes silently — a
    # ``patch_safety`` key is attached only when the gate BLOCKS (see Test 8).
    assert "patch_safety" not in result
    assert result["replay_dir"]
    assert (repo / "src/app.py").read_text(encoding="utf-8") == "new\n"


# ===========================================================================
# 2. Traversal target is blocked
# ===========================================================================
def test_traversal_target_blocked_by_patch_plan_executor(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.py"

    result = apply_patch_plan(str(repo), _create_plan("../outside.py"))

    assert result["success"] is False
    assert "escapes repo" in result["error"]
    assert result["failed_op"]["relative_path"] == "../outside.py"
    assert not outside.exists()


def test_traversal_target_blocked_by_run_lifecycle_before_executor(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_lifecycle = _patch_lifecycle(monkeypatch, repo)
    executor_calls: list[list[dict]] = []

    def executor_must_not_run(project_root, plan, validation_command=None):
        executor_calls.append(plan)
        raise AssertionError("executor ran after traversal was blocked")

    monkeypatch.setattr(run_lifecycle, "apply_patch_plan", executor_must_not_run)

    result = run_lifecycle.run_patch_plan_with_artifacts(
        str(repo), _create_plan("../outside.py"), source="unit"
    )

    assert result["success"] is False
    assert executor_calls == []
    assert result["patch_safety"]["blocked_paths"][0]["category"] == "traversal"
    assert "Patch plan blocked by safety gate" in result["message"]


# ===========================================================================
# 3. Forbidden/protected target blocked by the hardened lifecycle chokepoint
#    (proven by calling run_lifecycle directly, not via any web route)
# ===========================================================================
@pytest.mark.parametrize(
    ("relative_path", "category"),
    [
        ("tests/test_app.py", "test"),
        ("benchmarks/cases/python/example/case.json", "benchmark_validation"),
        (".env", "env"),
        (".agent/session.json", "protected_dir"),
    ],
)
def test_protected_single_file_blocked_by_lifecycle_chokepoint(
    monkeypatch, tmp_path, relative_path, category
):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_lifecycle = _patch_lifecycle(monkeypatch, repo)
    executor_calls: list[list[dict]] = []

    def executor_must_not_run(project_root, plan, validation_command=None):
        executor_calls.append(plan)
        raise AssertionError("executor ran after safety block")

    monkeypatch.setattr(run_lifecycle, "apply_patch_plan", executor_must_not_run)

    result = run_lifecycle.run_patch_plan_with_artifacts(
        str(repo), _create_plan(relative_path), source="unit"
    )

    assert result["success"] is False
    assert executor_calls == []
    assert result["patch_safety"]["blocked_paths"][0]["category"] == category
    # The protected target was never created on disk.
    assert not (repo / relative_path).exists()


# ===========================================================================
# 4. Missing target file returns a friendly failure, not an unhandled exception
# ===========================================================================
def test_missing_target_file_returns_friendly_failure_in_patch_plan_executor(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()

    result = apply_patch_plan(str(repo), _replace_plan("src/missing.py"))

    assert result["success"] is False
    assert "target file does not exist" in result["error"]
    assert result["rollback_performed"] is False
    assert result["rollback_attempted"] is False
    assert result["rollback_status"] == "not_required"
    assert result["failed_op"]["relative_path"] == "src/missing.py"


def test_missing_target_is_conflict_not_exception_in_single_file_executor(tmp_path):
    from core.executor import Executor

    repo = tmp_path / "repo"
    repo.mkdir()
    patch = {
        "file": "nope.py",
        "relative_path": "nope.py",
        "target_snippet": "def f():\n    return 1\n",
        "patched_snippet": "def f():\n    return 2\n",
        "target_node_name": "f",
        "target_node_kind": "function",
    }

    result = Executor(str(repo)).run(patch, language="python")

    assert result.success is False
    assert result.phase == "conflict"
    assert result.validation_ok is None


# ===========================================================================
# 5. Empty / no-op plan returns a stable result (no exception)
# ===========================================================================
@pytest.mark.parametrize("plan", [[], None, "not-a-list", {}])
def test_empty_or_invalid_plan_returns_stable_result(tmp_path, plan):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()

    result = apply_patch_plan(str(repo), plan)

    assert result["success"] is False
    assert result["error"] == "patch_plan must be a non-empty list of ops"
    assert result["applied_ops"] == []
    assert result["rollback_performed"] is False
    assert result["message"] == "Empty or invalid patch_plan."


# ===========================================================================
# 6. Validation command is invoked only through run_validation_command boundary
# ===========================================================================
def test_validation_routed_through_run_validation_command_in_patch_plan_executor(
    monkeypatch, tmp_path
):
    import core.validator as validator
    from core.validator import ValidationRun
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[tuple[str, str]] = []

    def fake_run(command, cwd, timeout=30):
        calls.append((command, cwd))
        return ValidationRun(ok=True, output="all good", exit_code=0)

    monkeypatch.setattr(validator, "run_validation_command_detailed", fake_run)

    result = apply_patch_plan(
        str(repo),
        _create_plan("src/new.py", "x = 1\n"),
        validation_command="pytest -q",
    )

    assert result["success"] is True
    assert result["validation_ok"] is True
    assert calls == [("pytest -q", str(repo.resolve()))]


def test_validation_routed_through_run_validation_command_in_single_file_executor(
    monkeypatch, tmp_path
):
    from core.validator import ValidationRun
    import config
    import core.executor as executor_mod
    from core.executor import Executor

    repo = tmp_path / "repo"
    repo.mkdir()
    # A verbatim named-function literal patch + validation command is the
    # one literal-match case the Executor permits (see _is_verbatim_named_...).
    _seed(repo, "src/app.py", "def greet(name):\n    return 'hi ' + name\n")
    patch = {
        "file": "src/app.py",
        "relative_path": "src/app.py",
        "target_snippet": "def greet(name):\n    return 'hi ' + name\n",
        "patched_snippet": "def greet(name):\n    return 'hello ' + name\n",
        "target_node_name": "greet",
        "target_node_kind": "function",
    }
    calls: list[tuple[str, str]] = []

    def fake_run(command, cwd, timeout=30):
        calls.append((command, cwd))
        return ValidationRun(ok=True, output="ok", exit_code=0)

    monkeypatch.setattr(config, "MUTATION_ORACLE_ENABLED", False, raising=False)
    monkeypatch.setattr(executor_mod, "run_validation_command_detailed", fake_run)

    result = Executor(str(repo)).run(patch, language="python", validation_command="pytest -q")

    assert result.success is True
    assert result.phase == "validated"
    assert result.validation_ok is True
    assert calls == [("pytest -q", str(repo.resolve()))]


# ===========================================================================
# 7. Unsafe validation command is blocked by the 13.6 hardening
# ===========================================================================
def test_unsafe_validation_command_blocked_at_run_validation_command(monkeypatch, tmp_path):
    import core.validator as validator

    repo = tmp_path / "repo"
    repo.mkdir()
    tripwire = _SubprocessTripwire()
    monkeypatch.setattr(validator, "subprocess", tripwire)

    ok, output = validator.run_validation_command("pytest -q; rm -rf /tmp/x", cwd=str(repo))

    assert ok is False
    assert "blocked for safety" in output
    # The destructive command never reached the shell.
    assert tripwire.calls == []


def test_unsafe_validation_command_blocks_and_rolls_back_through_executor(monkeypatch, tmp_path):
    import core.validator as validator
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    tripwire = _SubprocessTripwire()
    monkeypatch.setattr(validator, "subprocess", tripwire)

    created = repo / "src/new.py"

    result = apply_patch_plan(
        str(repo),
        _create_plan("src/new.py", "x = 1\n"),
        validation_command="ls && rm -rf build",
    )

    assert result["success"] is False
    assert result["validation_ok"] is False
    assert result["rollback_performed"] is True
    assert "blocked for safety" in result["validation_output"]
    # Rollback removed the file the op created; the shell never ran.
    assert not created.exists()
    assert tripwire.calls == []


# ===========================================================================
# 8. Patch safety result / error is surfaced clearly
# ===========================================================================
def test_patch_safety_result_is_surfaced_clearly(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_lifecycle = _patch_lifecycle(monkeypatch, repo)

    result = run_lifecycle.run_patch_plan_with_artifacts(
        str(repo), _create_plan(".env", "SECRET=1\n"), source="unit"
    )

    safety = result["patch_safety"]
    assert safety["ok"] is False
    assert safety["blocked_paths"][0]["category"] == "env"
    assert safety["reasons"]
    assert result["error"].startswith("Patch plan blocked by safety gate")
    assert result["message"].startswith("Patch plan blocked by safety gate")


# ===========================================================================
# 9. No accidental writes outside the temp repo
# ===========================================================================
def test_no_writes_outside_temp_repo_on_traversal(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    sentinel_dir = tmp_path / "outside_repo"
    sentinel_dir.mkdir()
    sentinel = sentinel_dir / "keep.txt"
    sentinel.write_text("untouched\n", encoding="utf-8")

    result = apply_patch_plan(str(repo), _create_plan("../outside_repo/escaped.py"))

    assert result["success"] is False
    assert not (sentinel_dir / "escaped.py").exists()
    assert sentinel.read_text(encoding="utf-8") == "untouched\n"
    # Nothing leaked into the repo either.
    assert list(repo.iterdir()) == []


# ===========================================================================
# 10. AST guard: this coverage slice introduces no forbidden behavior
# ===========================================================================
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


def _assigned_names(tree: ast.AST) -> set[str]:
    assigned: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    assigned.add(target.id)
                elif isinstance(target, ast.Attribute):
                    assigned.add(target.attr)
    return assigned


def test_executor_single_file_path_ast_guard():
    tree = ast.parse(THIS_FILE.read_text(encoding="utf-8"))
    imports = _imported_modules(tree)
    calls = _called_names(tree)
    assigned = _assigned_names(tree)

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

    # No model/API, DB, benchmark, container-lifecycle, or real destructive calls.
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
        "unlink",
        "rmtree",
        "remove",
    }
    assert forbidden_calls.isdisjoint(calls)

    # No broad patch-safety policy rewrite from a coverage test.
    forbidden_policy_names = {
        "_CATEGORY_WHY",
        "_PROTECTED_DIRS",
        "_TEST_DIRS",
        "_TEST_FILE_NAMES",
        "_TEST_SUFFIXES",
    }
    assert forbidden_policy_names.isdisjoint(assigned)
