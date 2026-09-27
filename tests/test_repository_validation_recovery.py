"""OPS.VALIDATE.1 — real repository validation recovery.

The 2026-08-30 black-box field test reproduced four failures in the production
validation path, and every one of them came from the same root cause: the path
answered *one* question ("is validation ok?") where there are three.

  A. Default Python preflight emitted a bare ``pytest``.  The active
     virtualenv owned pytest; PATH did not.  C.A.T.T.U.S could not validate its
     own repository.
  B. A flat ``solution.py`` / ``test_solution.py`` repository fell through to
     ``python -m unittest``, which collected none of its pytest functions.
  C. ``Ran 0 tests`` / ``NO TESTS RAN`` was classified ``test_failure`` - a
     non-event reported as a defect.
  D. ``detect_repo_language`` returned ``typescript`` and the detector had no
     TypeScript branch, so a large TypeScript repository got
     ``no_validation_command`` plus C#/Python advice.

So the suite below is organised around the three questions the path now answers
separately: which command, did anything run, and did it pass.

These tests execute real subprocesses through the production entry points on
purpose.  They make no model call and no network call, and they never install
anything.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.preflight import (  # noqa: E402
    detect_default_preflight_command,
    no_validation_command_hint,
    run_preflight_validation,
)
from core.validation_command import (  # noqa: E402
    get_default_validation_command,
    repo_uses_pytest,
    resolve_node_package_manager,
)
from core.validation_outcome import (  # noqa: E402
    CATEGORY_NO_TESTS_COLLECTED,
    CATEGORY_NO_VALIDATION_COMMAND,
    CATEGORY_VALIDATION_TOOL_UNAVAILABLE,
    VALIDATION_FAILED,
    VALIDATION_INCONCLUSIVE,
    VALIDATION_PASSED,
    is_compiler_grounded_category,
    is_executed_failure_evidence,
    validation_outcome,
)
from core.validator import (  # noqa: E402
    ValidationRun,
    classify_validation_output,
    detect_no_tests_collected,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

PASSING_TEST = "def test_ok():\n    assert 1 + 1 == 2\n"
FAILING_TEST = "def test_math():\n    assert 1 + 1 == 3\n"


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _pytest_repo(root: Path, *, flat: bool, test_body: str = PASSING_TEST) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _write(root, "solution.py", "def add(a, b):\n    return a + b\n")
    _write(root, "test_solution.py" if flat else "tests/test_solution.py", test_body)
    return root


# =========================================================================== #
# 1. Which command?  Python
# =========================================================================== #
def test_detected_python_validation_never_emits_a_bare_pytest(tmp_path):
    """Field-test failure A. The command must name an interpreter, not PATH."""
    repo = _pytest_repo(tmp_path / "repo", flat=False)

    for command in (
        detect_default_preflight_command("python", repo),
        get_default_validation_command("python", repo),
    ):
        assert command == "python -m pytest"
        assert command.split()[0] != "pytest"


def test_python_pytest_command_binds_to_the_running_interpreter(tmp_path):
    """`python` in the emitted command resolves to *this* interpreter.

    Not to whatever PATH holds - that is precisely the gap that made the field
    test unable to validate a repository whose pytest lived in a virtualenv.
    """
    from core.validator import _current_interpreter_argv

    assert _current_interpreter_argv("python -m pytest") == [
        sys.executable,
        "-m",
        "pytest",
    ]
    # No second attempt exists: a bare `pytest` is not rewritten into anything.
    assert _current_interpreter_argv("pytest") is None


def test_pytest_is_absent_from_path_but_reachable_through_the_interpreter():
    """The field test's environment, asserted rather than assumed.

    If pytest ever becomes globally resolvable on the machine running this
    suite, the test skips instead of silently proving nothing.
    """
    import shutil

    if shutil.which("pytest") is not None:
        pytest.skip("pytest is on PATH here; the field-test gap cannot be shown")

    run = _run("python -m pytest --version", REPO_ROOT)
    assert run.ok, run.output


def _run(command: str, cwd: Path) -> ValidationRun:
    from core.validator import run_validation_command_detailed

    return run_validation_command_detailed(command, cwd=str(cwd), timeout=120)


def test_flat_root_level_pytest_repository_is_detected(tmp_path):
    """Field-test failure B: no tests/ directory, no config, still pytest."""
    repo = _pytest_repo(tmp_path / "flat", flat=True)

    assert repo_uses_pytest(repo) is True
    assert detect_default_preflight_command("python", repo) == "python -m pytest"
    assert get_default_validation_command("python", repo) == "python -m pytest"


@pytest.mark.parametrize(
    "marker, body",
    [
        ("pytest.ini", "[pytest]\n"),
        ("conftest.py", "import pytest\n"),
        ("pyproject.toml", "[tool.pytest.ini_options]\naddopts = '-q'\n"),
        ("setup.cfg", "[tool:pytest]\naddopts = -q\n"),
        ("test_thing.py", PASSING_TEST),
        ("thing_test.py", PASSING_TEST),
    ],
)
def test_bounded_root_markers_select_pytest(tmp_path, marker, body):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo, "solution.py", "x = 1\n")
    assert repo_uses_pytest(repo) is False

    _write(repo, marker, body)
    assert repo_uses_pytest(repo) is True
    assert get_default_validation_command("python", repo) == "python -m pytest"


def test_unittest_repositories_still_select_unittest(tmp_path):
    """Absence of pytest markers is what selects unittest - nothing else."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo, "helpers.py", "def add(a, b):\n    return a + b\n")

    assert repo_uses_pytest(repo) is False
    assert get_default_validation_command("python", repo) == "python -m unittest"
    assert detect_default_preflight_command("python", repo) == "python -m unittest"


def test_python_entry_point_precedence_is_unchanged(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo, "test.py", "print('ok')\n")
    assert get_default_validation_command("python", repo) == "python test.py"

    main_only = tmp_path / "main_only"
    main_only.mkdir()
    _write(main_only, "main.py", "print('ok')\n")
    assert get_default_validation_command("python", main_only) == "python main.py"

    app_only = tmp_path / "app_only"
    app_only.mkdir()
    _write(app_only, "app.py", "app = object()\n")
    assert (
        get_default_validation_command("python", app_only) == 'python -c "import app"'
    )


def test_validation_selection_does_not_walk_the_repository():
    """§47: the traversal budget did not grow.

    The C#, Go and Rust branches have always used ``rglob``; those counts are
    pinned so this phase cannot quietly add a fourth walker.  The Python and
    TypeScript selectors this phase wrote must contain none at all: root-level
    ``test_*.py`` discovery is one non-recursive glob, not a tree walk.
    """
    import inspect

    from core import validation_command as vc

    for relative, allowed_rglob in (
        ("core/validation_command.py", 4),
        ("core/preflight.py", 2),
    ):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert source.count(".rglob(") == allowed_rglob, relative
        assert "os.walk(" not in source, relative
        assert 'glob("**/' not in source, relative

    for function in (
        vc.repo_uses_pytest,
        vc.detect_python_validation_command,
        vc.detect_typescript_validation_command,
        vc.resolve_node_package_manager,
        vc.package_json_scripts,
        vc._root_glob_matches,
    ):
        body = inspect.getsource(function)
        assert ".rglob(" not in body, function.__name__
        assert "**" not in body, function.__name__


# =========================================================================== #
# 2. Did anything run?  Python
# =========================================================================== #
def test_primary_pytest_repository_actually_validates(tmp_path):
    """§27: detection, execution and classification, end to end."""
    repo = _pytest_repo(tmp_path / "repo", flat=False)

    result = run_preflight_validation(repo_path=str(repo), language="python")

    assert result["command"] == "python -m pytest"
    assert result["ran"] is True
    assert result["outcome"] == VALIDATION_PASSED
    assert result["category"] == VALIDATION_PASSED
    assert result["ok"] is True


def test_flat_pytest_repository_actually_collects_and_runs_its_test(tmp_path):
    """§29: the field test's flat repository, executed for real."""
    repo = _pytest_repo(tmp_path / "flat", flat=True)

    result = run_preflight_validation(repo_path=str(repo), language="python")

    assert result["command"] == "python -m pytest"
    assert result["outcome"] == VALIDATION_PASSED
    assert "1 passed" in result["output"]
    # It must not have fallen through to unittest and reported zero tests.
    assert result["category"] != CATEGORY_NO_TESTS_COLLECTED


def test_cattus_like_repository_selects_the_interpreter_and_validates(tmp_path):
    """§28: a bounded stand-in for C.A.T.T.U.S's own layout.

    pytest.ini plus a tests/ directory - the shape whose default command used to
    be a bare ``pytest`` that this machine cannot resolve. One tiny test proves
    the selected command really executes here.
    """
    repo = tmp_path / "cattus_like"
    repo.mkdir()
    _write(repo, "pytest.ini", "[pytest]\ntestpaths = tests\n")
    _write(repo, "core/thing.py", "def thing():\n    return 42\n")
    _write(repo, "tests/test_thing.py", "def test_thing():\n    assert 42 == 42\n")

    result = run_preflight_validation(repo_path=str(repo), language="python")

    assert result["command"] == "python -m pytest"
    assert result["command"] != "pytest"
    assert result["ran"] is True
    assert result["outcome"] == VALIDATION_PASSED


def test_pytest_zero_tests_is_inconclusive_not_a_test_failure(tmp_path):
    """§30 + field-test failure C, through real pytest exit code 5."""
    repo = tmp_path / "empty"
    repo.mkdir()
    _write(repo, "pytest.ini", "[pytest]\n")
    _write(repo, "solution.py", "def add(a, b):\n    return a + b\n")

    result = run_preflight_validation(repo_path=str(repo), language="python")

    assert result["command"] == "python -m pytest"
    assert result["ran"] is True
    assert result["category"] == CATEGORY_NO_TESTS_COLLECTED
    assert result["outcome"] == VALIDATION_INCONCLUSIVE
    assert result["ok"] is False
    assert result["category"] != "test_failure"
    assert "inconclusive" in result["reason"].lower()
    # And it is not evidence of a defect.
    assert is_executed_failure_evidence(result["category"]) is False
    assert result["locations"] == []


def test_unittest_zero_tests_is_inconclusive_despite_exit_code_zero(tmp_path):
    """§31: `Ran 0 tests` + exit 0 is the one that used to read as success."""
    repo = tmp_path / "unittest_empty"
    repo.mkdir()
    _write(repo, "helpers.py", "def add(a, b):\n    return a + b\n")

    result = run_preflight_validation(repo_path=str(repo), language="python")

    assert result["command"] == "python -m unittest"
    assert "Ran 0 tests" in result["output"]
    assert result["category"] == CATEGORY_NO_TESTS_COLLECTED
    assert result["outcome"] == VALIDATION_INCONCLUSIVE
    assert result["outcome"] != VALIDATION_PASSED
    assert result["ok"] is False


def test_zero_tests_detection_defers_to_a_real_collection_error():
    """`collected 0 items` under a failing exit code is still that failure."""
    assert detect_no_tests_collected("collected 0 items", exit_code=5) is True
    assert detect_no_tests_collected("collected 0 items", exit_code=2) is False
    assert (
        classify_validation_output(
            "ImportError while importing test module\ncollected 0 items",
            exit_code=2,
            command="python -m pytest",
        )["category"]
        == "import_error"
    )


def test_pytest_module_unavailable_is_tool_unavailable_not_test_failure(monkeypatch, tmp_path):
    """§32: the interpreter runs, pytest is not importable inside it."""
    repo = _pytest_repo(tmp_path / "repo", flat=True)

    real_output = f"{sys.executable}: No module named pytest"
    attempts: list[str] = []

    def fake_run(command, cwd, timeout=30):
        attempts.append(command)
        return ValidationRun(ok=False, output=real_output, exit_code=1)

    monkeypatch.setattr("core.preflight.run_validation_command_detailed", fake_run)

    result = run_preflight_validation(repo_path=str(repo), language="python")

    assert result["category"] == CATEGORY_VALIDATION_TOOL_UNAVAILABLE
    assert result["outcome"] == VALIDATION_INCONCLUSIVE
    assert result["category"] not in {"test_failure", "assertion_failure"}
    # No fallback chain: exactly one command was attempted, and no global
    # `pytest` retry and no install were tried after it failed.
    assert attempts == ["python -m pytest"]
    assert "install" not in result["command"]


def test_a_missing_repository_module_is_still_the_repositorys_problem():
    """Only the *runner's* absence is infrastructure; the repo's is a defect."""
    assert (
        classify_validation_output("ModuleNotFoundError: No module named 'requests'")[
            "category"
        ]
        == "import_error"
    )
    assert (
        classify_validation_output("No module named pytest")["category"]
        == CATEGORY_VALIDATION_TOOL_UNAVAILABLE
    )


def test_executable_not_found_is_inconclusive():
    """Field-test failure A's literal shell message."""
    windows = "'pytest' is not recognized as an internal or external command"
    posix = "/bin/sh: 1: pytest: command not found"
    for text in (windows, posix):
        info = classify_validation_output(text, exit_code=127)
        assert info["category"] == CATEGORY_VALIDATION_TOOL_UNAVAILABLE
        assert validation_outcome(category=info["category"], ok=False) == (
            VALIDATION_INCONCLUSIVE
        )


# =========================================================================== #
# 3. Did it pass?  Genuine failures keep their meaning
# =========================================================================== #
def test_real_assertion_failure_is_a_real_failure(tmp_path):
    """§33: a suite that ran and disagreed with the code."""
    repo = _pytest_repo(tmp_path / "failing", flat=True, test_body=FAILING_TEST)

    result = run_preflight_validation(repo_path=str(repo), language="python")

    assert result["ran"] is True
    assert result["outcome"] == VALIDATION_FAILED
    assert result["ok"] is False
    assert result["category"] in {"assertion_failure", "test_failure"}
    assert is_executed_failure_evidence(result["category"]) is True


def test_real_syntax_error_still_grounds_a_compiler_diagnosis(tmp_path):
    """§34: not every nonzero result became inconclusive."""
    repo = tmp_path / "broken"
    repo.mkdir()
    _write(repo, "main.py", "def broken(:\n    pass\n")

    result = run_preflight_validation(repo_path=str(repo), language="python")

    assert result["command"] == "python main.py"
    assert result["outcome"] == VALIDATION_FAILED
    assert result["category"] == "syntax_error"
    assert is_compiler_grounded_category(result["category"]) is True


def test_preflight_grounding_distinguishes_evidence_from_infrastructure(tmp_path):
    """§35, the critical one. Same repository, two very different runs.

    Case A: pytest executed and an assertion failed - the run is evidence about
    the code, and the existing "skip the weak-model critique, the compiler
    already told us" optimisation stays eligible.

    Case B: pytest could not run, or collected nothing - the run is evidence
    about the environment, and buying the patch extra trust with it would be
    inventing a defect that was never observed.
    """
    failing = _pytest_repo(tmp_path / "case_a", flat=True, test_body=FAILING_TEST)
    empty = tmp_path / "case_b"
    empty.mkdir()
    _write(empty, "pytest.ini", "[pytest]\n")
    _write(empty, "solution.py", "x = 1\n")

    case_a = run_preflight_validation(repo_path=str(failing), language="python")
    case_b = run_preflight_validation(repo_path=str(empty), language="python")

    assert case_a["ok"] is False and case_b["ok"] is False  # both non-passing
    assert is_executed_failure_evidence(case_a["category"]) is True
    assert is_executed_failure_evidence(case_b["category"]) is False

    tool_missing = classify_validation_output("No module named pytest")
    assert is_executed_failure_evidence(tool_missing["category"]) is False
    for infrastructure in ("missing_toolchain", "validation_environment"):
        assert is_executed_failure_evidence(infrastructure) is False


def test_pipeline_grounding_gates_read_the_shared_predicate():
    """The two live consumers ask the vocabulary, not a private list copy."""
    source = (REPO_ROOT / "core" / "pipeline.py").read_text(encoding="utf-8")
    assert "is_executed_failure_evidence(preflight.get(\"category\"))" in source
    assert "is_compiler_grounded_category(preflight.get(\"category\"))" in source
    assert '"missing_toolchain",\n' not in source


# =========================================================================== #
# 4. Which command?  TypeScript
# =========================================================================== #
def _ts_repo(root: Path, scripts: dict, *, lockfile: str = "package-lock.json") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _write(root, "tsconfig.json", json.dumps({"compilerOptions": {"strict": True}}))
    _write(
        root,
        "package.json",
        json.dumps({"name": "fixture", "private": True, "scripts": scripts}),
    )
    if lockfile:
        _write(root, lockfile, "{}\n" if lockfile.endswith(".json") else "\n")
    return root


def test_typescript_repository_selects_a_declared_script(tmp_path):
    """§36 + field-test failure D: TypeScript finally has a branch."""
    repo = _ts_repo(tmp_path / "ts", {"test": "node check.js"})

    assert detect_default_preflight_command("typescript", repo) == "npm run test"
    assert get_default_validation_command("typescript", repo) == "npm run test"


def test_typescript_script_priority_is_deterministic(tmp_path):
    """test → typecheck → check → build, and never anything else."""
    cases = [
        ({"build": "tsc", "check": "tsc --noEmit", "typecheck": "tsc -p .", "test": "node t.js"}, "test"),
        ({"build": "tsc", "check": "tsc --noEmit", "typecheck": "tsc -p ."}, "typecheck"),
        ({"build": "tsc", "check": "tsc --noEmit"}, "check"),
        ({"build": "tsc"}, "build"),
    ]
    for index, (scripts, expected) in enumerate(cases):
        repo = _ts_repo(tmp_path / f"ts{index}", scripts)
        assert get_default_validation_command("typescript", repo) == f"npm run {expected}"

    unrelated = _ts_repo(tmp_path / "ts_unrelated", {"start": "node .", "lint": "eslint ."})
    assert get_default_validation_command("typescript", unrelated) == ""


@pytest.mark.parametrize(
    "lockfile, manager",
    [
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("package-lock.json", "npm"),
        ("", "npm"),
    ],
)
def test_package_manager_comes_from_the_repositorys_own_lockfile(tmp_path, lockfile, manager):
    """§18: the repository says which manager it uses; nothing is assumed."""
    repo = _ts_repo(tmp_path / f"ts_{manager}", {"test": "node t.js"}, lockfile=lockfile)
    assert resolve_node_package_manager(repo) == manager
    assert get_default_validation_command("typescript", repo) == f"{manager} run test"


def test_typescript_without_a_usable_script_says_so_in_typescript_terms(tmp_path):
    """§37: no fabricated success, and no advice about .csproj files."""
    repo = tmp_path / "ts_bare"
    repo.mkdir()
    _write(repo, "tsconfig.json", "{}\n")
    _write(repo, "package.json", json.dumps({"name": "bare", "scripts": {}}))
    _write(repo, "index.ts", "export const x: number = 1;\n")

    assert get_default_validation_command("typescript", repo) == ""

    result = run_preflight_validation(repo_path=str(repo), language="typescript")

    assert result["ran"] is False
    assert result["category"] == CATEGORY_NO_VALIDATION_COMMAND
    assert result["outcome"] == VALIDATION_INCONCLUSIVE
    hint = result["hint"]
    assert "package.json" in hint
    assert ".csproj" not in hint
    assert "pytest" not in hint
    assert "never installed automatically" in hint


def test_no_validation_command_hints_name_the_repositorys_own_ecosystem():
    assert ".csproj" in no_validation_command_hint("csharp")
    assert "pytest" in no_validation_command_hint("python")
    assert "package.json" in no_validation_command_hint("typescript")
    assert ".csproj" not in no_validation_command_hint("typescript")
    assert no_validation_command_hint("klingon")


def test_typescript_selection_never_implies_an_installation(tmp_path):
    """§19: no command this phase can emit fetches anything."""
    forbidden = ("npm install", "pnpm install", "yarn install", "npx ", "pip install")
    for scripts in ({"test": "node t.js"}, {"typecheck": "tsc -p ."}, {"build": "tsc"}):
        repo = _ts_repo(tmp_path / f"ts_{next(iter(scripts))}", scripts)
        command = get_default_validation_command("typescript", repo)
        for token in forbidden:
            assert token not in command

    source = (REPO_ROOT / "core" / "validation_command.py").read_text(encoding="utf-8")
    for token in ("npm install", "pnpm install", "yarn install", "pip install"):
        assert token not in source


def test_missing_package_manager_is_inconclusive_not_a_test_failure(tmp_path):
    """§38: a yarn repository on a machine without yarn."""
    import shutil

    if shutil.which("yarn") is not None:
        pytest.skip("yarn is installed here; the missing-manager path cannot run")

    repo = _ts_repo(tmp_path / "ts_yarn", {"test": "node t.js"}, lockfile="yarn.lock")
    _write(repo, "t.js", "process.exit(0);\n")

    result = run_preflight_validation(repo_path=str(repo), language="typescript")

    assert result["command"] == "yarn run test"
    assert result["outcome"] == VALIDATION_INCONCLUSIVE
    assert result["category"] in {
        CATEGORY_VALIDATION_TOOL_UNAVAILABLE,
        "missing_toolchain",
    }
    assert result["category"] not in {"test_failure", "assertion_failure"}


def test_javascript_detection_is_unchanged(tmp_path):
    """§39: adding TypeScript moved nothing on the JavaScript side."""
    with_test_script = tmp_path / "js_scripts"
    with_test_script.mkdir()
    _write(with_test_script, "package.json", json.dumps({"scripts": {"test": "node t.js"}}))
    assert detect_default_preflight_command("javascript", with_test_script) == "npm test"
    assert get_default_validation_command("javascript", with_test_script) == "npm test"

    with_test_js = tmp_path / "js_file"
    with_test_js.mkdir()
    _write(with_test_js, "test.js", "console.log('ok');\n")
    assert detect_default_preflight_command("javascript", with_test_js) == "node test.js"

    bare = tmp_path / "js_bare"
    bare.mkdir()
    assert detect_default_preflight_command("javascript", bare) == ""


# =========================================================================== #
# 5. Precedence and safety
# =========================================================================== #
def test_explicit_validation_command_still_outranks_detection(tmp_path):
    """§40: a programmatically supplied command wins, as it always did."""
    repo = _pytest_repo(tmp_path / "repo", flat=False)

    result = run_preflight_validation(
        repo_path=str(repo),
        language="python",
        command="python -c \"print('explicit override ran')\"",
    )

    assert result["command"] == "python -c \"print('explicit override ran')\""
    assert "explicit override ran" in result["output"]
    assert result["outcome"] == VALIDATION_PASSED


def test_multiline_user_text_override_still_wins_over_detection(tmp_path):
    """The `Validation command:` directive keeps its precedence end to end."""
    from core.validation_command import extract_user_validation_command

    repo = _pytest_repo(tmp_path / "repo", flat=False)
    user_text = (
        "Please fix the adder.\n"
        "Validation command: python -c \"print('from user text')\"\n"
        "Thanks."
    )
    explicit = extract_user_validation_command(user_text)
    assert explicit == "python -c \"print('from user text')\""

    result = run_preflight_validation(
        repo_path=str(repo),
        language="python",
        command=explicit,
    )
    assert result["command"] == explicit
    assert "from user text" in result["output"]


def test_a_destructive_override_is_still_refused(tmp_path):
    """§23: the safety layer is reported, never routed around."""
    repo = _pytest_repo(tmp_path / "repo", flat=True)

    result = run_preflight_validation(
        repo_path=str(repo),
        language="python",
        command="pytest && rm -rf build",
    )

    assert result["ran"] is True
    assert result["ok"] is False
    assert "blocked for safety" in result["output"].lower()


def test_a_detected_command_does_not_by_itself_grant_patch_authority(tmp_path):
    """§45: validation is a precondition, never a grant.

    Detecting a command for a repository that had none - which is exactly what
    the TypeScript branch now does - lets that repository reach the *existing*
    gate. It does not open it. CONTROL.SAFETY.LIVE.1 also makes explicit that
    localization rank cannot supply the missing authority.
    """
    from policy.decision_helper import build_patch_policy

    with_command = build_patch_policy(
        "balanced",
        language="typescript",
        control_confidence=0.9,
        has_validation_command=True,
        repo_manifest={"primary_language": "typescript"},
    )
    assert with_command.require_validation_for_apply is True
    assert with_command.auto_apply_allowed is False

    grounded_patch = build_patch_policy(
        "balanced",
        language="typescript",
        has_validation_command=True,
        patch_confidence=0.9,
        defect_grounded=True,
        repo_manifest={"primary_language": "typescript"},
    )
    assert grounded_patch.auto_apply_allowed is True

    # A command alone is not enough: low confidence still refuses.
    low_confidence = build_patch_policy(
        "balanced",
        language="typescript",
        control_confidence=0.4,
        has_validation_command=True,
        repo_manifest={"primary_language": "typescript"},
    )
    assert low_confidence.auto_apply_allowed is False

    # An unknown language still refuses, command or not.
    unknown_language = build_patch_policy(
        "balanced",
        language="unknown",
        control_confidence=0.99,
        has_validation_command=True,
        repo_manifest={"primary_language": "unknown"},
    )
    assert unknown_language.auto_apply_allowed is False

    # And the pipeline still refuses everything when auto-patch is switched off.
    source = (REPO_ROOT / "core" / "pipeline.py").read_text(encoding="utf-8")
    assert "if not AUTO_PATCH_ENABLED:" in source
    assert "if not policy.auto_apply_allowed:" in source


def test_no_validation_score_or_confidence_was_introduced():
    """§44: categorical facts only."""
    for relative in (
        "core/validation_outcome.py",
        "core/preflight.py",
        "core/validation_command.py",
    ):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        for token in ("validation_confidence", "validation_score", "confidence ="):
            assert token not in source, relative


def test_no_command_retry_loop_exists():
    """§43: selection is deterministic; nothing is tried until something passes."""
    source = (REPO_ROOT / "core" / "validation_command.py").read_text(encoding="utf-8")
    assert "except subprocess" not in source
    assert "subprocess" not in source
    # The detector returns one command, or none. It cannot execute anything.
    assert "run_validation_command" not in source


# =========================================================================== #
# 6. Downstream: apply, rollback and the receipt
# =========================================================================== #
def _replace_op(relative: str, old: str, new: str) -> dict:
    return {
        "op": "replace_snippet",
        "relative_path": relative,
        "target_snippet": old,
        "patched_snippet": new,
    }


def test_zero_tests_does_not_accept_a_patch_and_says_why(tmp_path):
    """§13 + §25: not accepted, rolled back, and never called a test failure."""
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo, "pytest.ini", "[pytest]\n")
    original = "def add(a, b):\n    return a - b\n"
    (repo / "solution.py").write_bytes(original.encode("utf-8"))

    result = apply_patch_plan(
        str(repo),
        [_replace_op("solution.py", "return a - b", "return a + b")],
        validation_command="python -m pytest",
    )

    assert result["success"] is False
    assert result["validation_ok"] is False
    assert result["validation_outcome"] == VALIDATION_INCONCLUSIVE
    assert result["validation_info"]["category"] == CATEGORY_NO_TESTS_COLLECTED
    assert "inconclusive" in result["message"].lower()
    assert "validation failed" not in result["message"].lower()
    assert "test failure" not in result["message"].lower()

    # §14/§51: rollback still restores the exact original bytes.
    assert result["rollback_performed"] is True
    assert (repo / "solution.py").read_bytes() == original.encode("utf-8")


def test_inconclusive_rollback_is_byte_exact_for_crlf_files(tmp_path):
    """§51: OPS.PATCH.1's guarantee holds under the new outcome too."""
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo, "pytest.ini", "[pytest]\n")
    original = b"def add(a, b):\r\n    return a - b\r\n"
    (repo / "solution.py").write_bytes(original)

    result = apply_patch_plan(
        str(repo),
        [_replace_op("solution.py", "return a - b", "return a + b")],
        validation_command="python -m pytest",
    )

    assert result["validation_outcome"] == VALIDATION_INCONCLUSIVE
    assert (repo / "solution.py").read_bytes() == original


def test_a_real_failing_test_still_reports_a_failure(tmp_path):
    """The other side of the same gate: a genuine red suite stays 'failed'."""
    from patching.patch_plan_executor import apply_patch_plan

    repo = _pytest_repo(tmp_path / "repo", flat=True, test_body=FAILING_TEST)
    original = (repo / "solution.py").read_bytes()

    result = apply_patch_plan(
        str(repo),
        [_replace_op("solution.py", "return a + b", "return a + b + 0")],
        validation_command="python -m pytest",
    )

    assert result["success"] is False
    assert result["validation_outcome"] == VALIDATION_FAILED
    assert result["validation_info"]["category"] in {
        "assertion_failure",
        "test_failure",
    }
    assert "inconclusive" not in result["message"].lower()
    assert (repo / "solution.py").read_bytes() == original


def test_a_passing_suite_still_accepts_the_patch(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = _pytest_repo(tmp_path / "repo", flat=True)
    (repo / "solution.py").write_bytes(b"def add(a, b):\n    return a - b\n")

    result = apply_patch_plan(
        str(repo),
        [_replace_op("solution.py", "return a - b", "return a + b")],
        validation_command="python -m pytest",
    )

    assert result["success"] is True
    assert result["validation_ok"] is True
    assert result["validation_outcome"] == VALIDATION_PASSED
    assert result["rollback_performed"] is False


def test_live_receipt_calls_an_inconclusive_validation_errored_not_failed():
    """§25/§26: CHECK.1's frozen vocabulary already had the honest word."""
    from core.live_validation_receipt import live_validation_result
    from core.post_run_reconciliation import (
        RECEIPT_ERRORED,
        RECEIPT_FAILED,
        RECEIPT_PASSED,
    )

    assert (
        live_validation_result(executed=True, passed=False, inconclusive=True)
        == RECEIPT_ERRORED
    )
    assert live_validation_result(executed=True, passed=False) == RECEIPT_FAILED
    assert live_validation_result(executed=True, passed=True) == RECEIPT_PASSED
    # A validation that never ran still produces no receipt at all.
    assert live_validation_result(executed=False, passed=None) is None


def test_an_inconclusive_receipt_still_blocks_a_required_expectation():
    """Honest, and still conservative: `errored` remains a failing result."""
    from core.post_run_reconciliation import (
        RECEIPT_ERRORED,
        RECEIPT_PASSED,
        _FAILING_RECEIPT_RESULTS,
    )

    assert RECEIPT_ERRORED in _FAILING_RECEIPT_RESULTS
    assert RECEIPT_PASSED not in _FAILING_RECEIPT_RESULTS


def test_worker_report_does_not_claim_a_failure_it_never_observed():
    from core.live_worker_report import declared_validation_action
    from core.post_run_reconciliation import (
        DECLARED_VALIDATION_FAILED,
        DECLARED_VALIDATION_NOT_RUN,
    )

    inconclusive = declared_validation_action(
        validation_id="live-validation",
        validation_kind="unit_tests",
        executed=True,
        passed=False,
        inconclusive=True,
    )
    genuine = declared_validation_action(
        validation_id="live-validation",
        validation_kind="unit_tests",
        executed=True,
        passed=False,
    )
    assert inconclusive.declared_result == DECLARED_VALIDATION_NOT_RUN
    assert genuine.declared_result == DECLARED_VALIDATION_FAILED


def test_run_lifecycle_reads_the_typed_outcome_it_was_given():
    """The shadow observer never re-classifies output to learn this."""
    from core.run_lifecycle import _shadow_validation_facts

    inconclusive = _shadow_validation_facts(
        {"validation_ok": False, "validation_outcome": VALIDATION_INCONCLUSIVE}
    )
    failed = _shadow_validation_facts(
        {"validation_ok": False, "validation_outcome": VALIDATION_FAILED}
    )
    blocked = _shadow_validation_facts(
        {"validation_ok": None, "validation_mode": "blocked_unsafe_legacy_shell"}
    )

    assert inconclusive["validation_inconclusive"] is True
    assert failed["validation_inconclusive"] is False
    assert blocked["validation_inconclusive"] is False
    assert blocked["validation_executed"] is False


# =========================================================================== #
# 7. Auto-detection actually reaches production code
# =========================================================================== #
def test_benchmark_cases_may_omit_a_validation_command(tmp_path):
    """§41: the 54-case suite hardcodes commands, so detection was never run.

    A case can now opt in to auto-detection, which is what puts the shipped
    detector - not a benchmark-local copy of it - on the path.
    """
    from benchmarks.run_benchmarks import check_case

    case_dir = tmp_path / "auto_case"
    (case_dir / "buggy_repo").mkdir(parents=True)
    _write(case_dir / "buggy_repo", "solution.py", "def add(a, b):\n    return a - b\n")
    _write(case_dir / "buggy_repo", "test_solution.py", PASSING_TEST)

    body = {
        "name": "auto_detect_python_flat_pytest",
        "language": "python",
        "auto_detect_validation": True,
        "expected_changed_files": ["solution.py"],
        "forbidden_changed_files": ["test_solution.py"],
        "prompt": "Fix the adder.",
    }
    case_file = case_dir / "case.json"
    case_file.write_text(json.dumps(body), encoding="utf-8")
    assert check_case(case_file)["errors"] == []

    # Omitting it without opting in is still an error, so a typo cannot become
    # silent auto-detection.
    body.pop("auto_detect_validation")
    case_file.write_text(json.dumps(body), encoding="utf-8")
    assert "Missing required field: validation_command" in check_case(case_file)["errors"]

    # And a case cannot claim both.
    body["auto_detect_validation"] = True
    body["validation_command"] = "python -m pytest"
    case_file.write_text(json.dumps(body), encoding="utf-8")
    assert any("must not also set" in e for e in check_case(case_file)["errors"])


@pytest.mark.parametrize(
    "language, build, expected_command",
    [
        ("python", "flat_pytest", "python -m pytest"),
        ("typescript", "package_script", "npm run test"),
    ],
)
def test_auto_detection_integration_selects_and_executes(
    tmp_path, language, build, expected_command
):
    """§41/§42: a deterministic harness with no `validation_command` at all.

    The production detector picks the command and the production preflight runs
    it, over a repository shaped like the two the field test broke on. No model
    is involved, so this measures validation plumbing rather than intelligence.
    """
    import shutil

    repo = tmp_path / build
    if build == "flat_pytest":
        _pytest_repo(repo, flat=True)
    else:
        if shutil.which("npm") is None:
            pytest.skip("npm is not installed here")
        repo = _ts_repo(repo, {"test": "node check.js"})
        _write(repo, "check.js", "if (1 + 1 !== 2) { process.exit(1); }\n")
        _write(repo, "index.ts", "export const add = (a: number, b: number) => a + b;\n")

    case = {"language": language, "prompt": "fix it", "auto_detect_validation": True}
    assert not case.get("validation_command")

    selected = get_default_validation_command(case["language"], repo)
    assert selected == expected_command

    result = run_preflight_validation(repo_path=str(repo), language=language)
    assert result["command"] == expected_command
    assert result["ran"] is True
    assert result["outcome"] == VALIDATION_PASSED, result["output"]
