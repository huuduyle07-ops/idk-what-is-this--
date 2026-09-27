"""Phase 13.5 characterization + Phase 13.6 hardening — validation command safety.

Phase 13.5 characterized the gap: only the user-text path
(``extract_user_validation_command``) was screened, while hardcoded defaults and
DB/profile-derived commands reached ``run_validation_command(shell=True)``
unscreened.

Phase 13.6 closes that gap at the shared shell chokepoint:
``core.validator.run_validation_command`` now calls
``validation_command_safety_issue`` BEFORE any ``subprocess.run(..., shell=True)``
and refuses destructive commands with a clear blocked result — without executing
them. Because every lifecycle executor (executor / patch_plan_executor /
preflight / mutation_oracle) reaches the shell only through this one function,
screening it protects the default path AND the DB/profile path at once.

What 13.6 deliberately did NOT change: shell=True stays, the default command
table (``get_default_validation_command``) is untouched, and the validation
output classifier (``classify_validation_output``) is untouched.

OPS.VALIDATE.1 update. The screened sink is now
``core.validator.run_validation_command_detailed``; ``run_validation_command``
is the ``(ok, output)`` wrapper over it, so the screen still lives in exactly
one function and every lifecycle executor still reaches the shell only through
it.  Two 13.6 scope pins genuinely moved, and are re-pinned below rather than
deleted: the default command table now emits ``python -m pytest`` instead of a
bare ``pytest``, and the classifier gained the two infrastructure categories
that separate "nothing was checked" from "the code is broken".  The shell is
still used for every command that needs one - a plain ``python ...`` command is
run as argv so it binds to the current interpreter, which is a *narrower* use
of the shell, not a wider one.

Safety of THIS suite: tests that exercise the sink with destructive commands
install a ``subprocess.run`` spy first, so no destructive command can ever
actually run — not even if the screen regressed.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.validator as validator  # noqa: E402
from core.validation_command import (  # noqa: E402
    extract_user_validation_command,
    get_default_validation_command,
    validation_command_safety_issue,
)

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[1]


# --------------------------------------------------------------------------- #
# subprocess spy — guarantees no command (benign or destructive) ever runs.
# --------------------------------------------------------------------------- #
class _FakeCompleted:
    def __init__(self, returncode: int = 0, stdout: str = "ok", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _install_subprocess_spy(monkeypatch) -> list[dict]:
    """Replace core.validator.subprocess.run with a recording stub that NEVER
    executes anything. Returns the list of recorded calls."""
    calls: list[dict] = []

    def fake_run(command, *args, **kwargs):
        calls.append({"command": command, "args": args, "kwargs": kwargs})
        return _FakeCompleted()

    monkeypatch.setattr(validator.subprocess, "run", fake_run)
    return calls


# --------------------------------------------------------------------------- #
# Screen primitive (unchanged in 13.6) — kept from the 13.5 characterization.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "rm -fr build",
        "del /q important.txt",
        "del /s /q C:\\data",
        "erase /f secrets.txt",
        "rmdir /s /q node_modules",
        "rd /q dist",
        "remove-item -recurse foo",
        "format C:",
        "mkfs /dev/sda",
        "shutdown now",
        "reboot",
        "git reset --hard HEAD~3",
        "git clean -fdx",
    ],
)
def test_user_supplied_destructive_command_is_detected(command):
    issue = validation_command_safety_issue(command)
    assert issue, f"expected {command!r} to be flagged as destructive"
    assert "destructive" in issue.lower()


def test_extract_user_validation_command_drops_destructive_command():
    text = "Please verify.\nValidation command: rm -rf build\nThanks!"
    assert extract_user_validation_command(text) == ""


@pytest.mark.parametrize(
    "command",
    ["pytest ; rm -rf build", "echo done; del /q out.txt", "make; shutdown now"],
)
def test_command_chaining_with_semicolon_is_detected(command):
    assert validation_command_safety_issue(command), command


@pytest.mark.parametrize(
    "command",
    ["pytest && rm -rf build", "npm test && del /q dist", "cargo build && reboot"],
)
def test_command_chaining_with_double_ampersand_is_detected(command):
    assert validation_command_safety_issue(command), command


@pytest.mark.parametrize(
    "command",
    [
        "pytest",
        "pytest -q",
        "dotnet test",
        "npm test",
        "go test ./...",
        "cargo test",
        "python -m unittest",
        'python -c "import app"',
        "npm test && npm run build",
    ],
)
def test_benign_command_is_allowed(command):
    assert validation_command_safety_issue(command) == ""


def test_extract_user_validation_command_returns_benign_command_verbatim():
    text = "notes\nValidation command: pytest -q\nmore notes"
    assert extract_user_validation_command(text) == "pytest -q"


# --------------------------------------------------------------------------- #
# 1. run_validation_command calls validation_command_safety_issue.
# --------------------------------------------------------------------------- #
def test_run_validation_command_calls_the_safety_screen():
    tree = _module_tree("core/validator.py")
    sink = _find_function(tree, "run_validation_command_detailed")
    assert sink is not None
    assert "validation_command_safety_issue" in _called_names(sink), (
        "the validation sink must screen the command before executing it"
    )

    # The compatibility wrapper must not become a second, unscreened door.
    wrapper = _find_function(tree, "run_validation_command")
    assert wrapper is not None
    assert "run_validation_command_detailed" in _called_names(wrapper)
    assert "subprocess" not in _called_names(wrapper)


# --------------------------------------------------------------------------- #
# 2, 3, 6, 7, 9. The shared sink refuses destructive commands, never executes
#    them, and surfaces the safety reason — for plain, ';'-chained, and
#    '&&'-chained destructive commands.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "pytest ; rm -rf build",       # semicolon chain
        "pytest && rm -rf build",      # && chain
        "npm test && del /q dist",
        "make; shutdown now",
        "git reset --hard HEAD~3",
    ],
)
def test_sink_blocks_destructive_command_without_executing(monkeypatch, tmp_path, command):
    calls = _install_subprocess_spy(monkeypatch)
    ok, output = validator.run_validation_command(command, cwd=str(tmp_path))
    assert ok is False
    assert calls == [], "subprocess.run must not run for a blocked command"
    assert "destructive" in output.lower()
    assert "block" in output.lower()


def test_blocked_result_message_includes_safety_reason(monkeypatch, tmp_path):
    calls = _install_subprocess_spy(monkeypatch)
    ok, output = validator.run_validation_command("rm -rf /", cwd=str(tmp_path))
    assert ok is False
    reason = validation_command_safety_issue("rm -rf /")
    assert reason and reason in output
    assert calls == []


# --------------------------------------------------------------------------- #
# 4, 8. Default / benign commands (including benign '&&' chains) still reach
#    subprocess.run and are allowed.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "command",
    [
        "pytest",
        "pytest -q",
        "dotnet test",
        'python -c "import app"',
        "npm test && npm run build",   # benign && chain remains allowed
    ],
)
def test_benign_command_reaches_subprocess_run(monkeypatch, tmp_path, command):
    calls = _install_subprocess_spy(monkeypatch)
    ok, output = validator.run_validation_command(command, cwd=str(tmp_path))
    assert len(calls) == 1
    passed = calls[0]["command"]
    if isinstance(passed, list):
        # OPS.VALIDATE.1: a plain python command is executed as argv bound to
        # this interpreter, so the tail of the command must survive verbatim.
        assert passed[0] == sys.executable
        assert command.split()[0].lower() in {"python", "python3", "py"}
    else:
        assert passed == command
    assert ok is True


# --------------------------------------------------------------------------- #
# 5. The DB/profile-derived command path is protected because it reaches the
#    shared, now-screened sink.
# --------------------------------------------------------------------------- #
def test_profile_derived_destructive_command_is_blocked_at_shared_sink(monkeypatch, tmp_path):
    # A destructive command a DB tooling profile could supply
    # (tooling.get("test_command")) converges on run_validation_command like
    # every other source, and is screened there.
    calls = _install_subprocess_spy(monkeypatch)
    ok, output = validator.run_validation_command("pytest && rm -rf /", cwd=str(tmp_path))
    assert ok is False
    assert calls == []
    assert "destructive" in output.lower()


def test_all_lifecycle_validation_runs_through_the_screened_sink():
    # Every lifecycle executor reaches the shell ONLY via run_validation_command
    # and never imports subprocess directly, so screening that one function
    # protects the default path AND the DB/profile path.
    for rel_path in (
        "core/executor.py",
        "patching/patch_plan_executor.py",
        "core/preflight.py",
        "core/mutation_oracle.py",
    ):
        tree = _module_tree(rel_path)
        called = _called_names(tree)
        assert called & {
            "run_validation_command",
            "run_validation_command_detailed",
        }, rel_path
        roots = {m.split(".", 1)[0] for m in _imported_modules(tree)}
        assert "subprocess" not in roots, (
            f"{rel_path} imports subprocess and could bypass the screened sink"
        )


# --------------------------------------------------------------------------- #
# 7 (scope). shell=True is retained in this phase.
# --------------------------------------------------------------------------- #
def test_shell_execution_is_narrowed_never_widened(monkeypatch, tmp_path):
    """The shell still runs shell-shaped commands, and nothing more.

    13.6 pinned ``shell=True`` so the hardening could not quietly change how
    commands execute.  OPS.VALIDATE.1 removes the shell from exactly one
    family - a bare ``python ...`` command with no shell syntax in it - so the
    active interpreter is used instead of whatever PATH happens to resolve.
    Every other command still goes to the shell, which is what this now pins.
    """
    calls = _install_subprocess_spy(monkeypatch)
    validator.run_validation_command("npm test && npm run build", cwd=str(tmp_path))
    validator.run_validation_command("pytest -q", cwd=str(tmp_path))
    assert [c["kwargs"]["shell"] for c in calls] == [True, True]
    assert [c["command"] for c in calls] == [
        "npm test && npm run build",
        "pytest -q",
    ]

    calls.clear()
    validator.run_validation_command("python -m pytest", cwd=str(tmp_path))
    assert calls[0]["kwargs"]["shell"] is False
    assert calls[0]["command"] == [sys.executable, "-m", "pytest"]


# --------------------------------------------------------------------------- #
# 10. Census: the screen is now invoked by the user-text path AND the shared
#     sink — no longer only extract_user_validation_command.
# --------------------------------------------------------------------------- #
def test_safety_screen_invoked_by_user_path_and_shared_sink():
    assert _functions_calling_screen() == {
        "extract_user_validation_command",
        "run_validation_command_detailed",
    }


# --------------------------------------------------------------------------- #
# Scope 8 & 9 regression pins: the hardening must not touch the default command
# table or the validation output classifier.
# --------------------------------------------------------------------------- #
def test_default_command_table_selects_the_current_interpreter(tmp_path):
    """13.6's scope pin, re-pinned at OPS.VALIDATE.1's corrected value.

    A bare ``pytest`` is exactly what the field test could not run: the active
    virtualenv owned pytest, PATH did not, and C.A.T.T.U.S could not validate
    its own repository.  The table now names the interpreter instead.
    """
    py_with_tests = tmp_path / "py_with_tests"
    (py_with_tests / "tests").mkdir(parents=True)
    py_empty = tmp_path / "py_empty"
    py_empty.mkdir()

    assert get_default_validation_command("python", py_with_tests) == "python -m pytest"
    assert get_default_validation_command("python", py_empty) == "python -m unittest"
    assert get_default_validation_command("klingon", py_empty) == ""


def test_validation_output_classifier_keeps_its_code_taxonomy():
    """The code categories are untouched; only infrastructure ones were added."""
    from core.validator import classify_validation_output

    assert classify_validation_output("AssertionError: boom")["category"] == "assertion_failure"
    assert classify_validation_output("ModuleNotFoundError: x")["category"] == "import_error"
    assert classify_validation_output("")["category"] == "unknown"


def test_hardening_is_isolated_to_the_screen():
    # The chokepoint only gained the safety screen; it must not reach into the
    # default command table or the output classifier.
    tree = _module_tree("core/validator.py")
    func = _find_function(tree, "run_validation_command_detailed")
    called = _called_names(func)
    assert "validation_command_safety_issue" in called
    assert "get_default_validation_command" not in called
    assert "classify_validation_output" not in called


# --------------------------------------------------------------------------- #
# 11. AST guard: this suite must not call models/APIs, write to the DB, run
#     benchmarks, apply patches, or drive Docker, and must not bypass the screen
#     with a raw shell call.
# --------------------------------------------------------------------------- #
def test_hardening_suite_has_no_unsafe_side_effects():
    tree = ast.parse(THIS_FILE.read_text(encoding="utf-8"))
    imports = _imported_modules(tree)
    imported_roots = {name.split(".", 1)[0] for name in imports}
    calls = _called_names(tree)

    forbidden_import_roots = {
        "subprocess",
        "openai",
        "google",
        "anthropic",
        "docker",
        "agents",
        "database",
        "benchmarks",
        "requests",
        "httpx",
    }
    forbidden_imports = {
        "core.executor",
        "core.mutation_oracle",
        "core.preflight",
        "core.prompter",
        "patching.patch_plan_executor",
    }
    forbidden_calls = {
        # raw shell bypass (the spy stands in for subprocess)
        "Popen",
        "system",
        "check_call",
        "check_output",
        # model / API
        "ChatCompletion",
        "build_prompt",
        "build_control_prompt",
        "build_deepseek_review",
        "generate_content",
        "run_gemini",
        "run_ollama",
        "run_deepseek",
        # DB writes
        "commit",
        "execute",
        "executemany",
        "save_artifact",
        "save_engineering_memory",
        "save_patch_attempt",
        "upsert_tooling_profile",
        # benchmark execution
        "run_benchmark",
        "run_benchmarks",
        # patch application
        "apply_patch",
        "apply_patch_plan",
        "apply_patch_from_json",
        "run_patch_plan_with_artifacts",
        # docker lifecycle
        "from_env",
    }

    assert imported_roots.isdisjoint(forbidden_import_roots)
    assert imports.isdisjoint(forbidden_imports)
    assert calls.isdisjoint(forbidden_calls)


# --------------------------------------------------------------------------- #
# AST / source helpers
# --------------------------------------------------------------------------- #
_CENSUS_MODULES = (
    "core/validation_command.py",
    "core/validator.py",
    "core/pipeline.py",
    "core/preflight.py",
    "core/executor.py",
    "core/worker_runs.py",
    "core/mutation_oracle.py",
    "patching/patch_plan_executor.py",
    "web/runner.py",
    "web/routes/patch_routes.py",
    "web/app.py",
    "cli/interactive.py",
)


def _module_tree(rel_path: str) -> ast.AST:
    return ast.parse((REPO_ROOT / rel_path).read_text(encoding="utf-8"))


def _find_function(tree: ast.AST, name: str) -> "ast.FunctionDef | None":
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name):
                names.add(n.func.id)
            elif isinstance(n.func, ast.Attribute):
                names.add(n.func.attr)
    return names


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _functions_calling_screen() -> set[str]:
    """Names of functions that call validation_command_safety_issue across the
    lifecycle/executor/patch-plan modules (including the shared shell sink)."""
    callers: set[str] = set()
    for rel_path in _CENSUS_MODULES:
        tree = _module_tree(rel_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if "validation_command_safety_issue" in _called_names(node):
                    callers.add(node.name)
    return callers


def _subprocess_run_uses_shell_true(func: ast.AST) -> bool:
    for n in ast.walk(func):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "run":
            for kw in n.keywords:
                if (
                    kw.arg == "shell"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                ):
                    return True
    return False
