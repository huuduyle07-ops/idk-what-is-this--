"""OPS.PATCH.2 — explicit-change candidate sandbox validation regressions.

The fixture in here is the real failure class the post-PATCH.BASIS black-box
rerun found: a task/priority repository whose final two-operation plan taught
``store.py`` to pass ``priority=`` into a ``Task`` that ``models.py`` never grew.
Every existing test in that repository fails with ``TypeError: Task.__init__()
got an unexpected keyword argument 'priority'`` the moment the plan is applied —
and before this phase, nothing applied it anywhere before calling it
approval-ready.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path

import pytest

from core import candidate_sandbox_validation as csv_mod
from core import control_engine, pipeline
from core.agent_state import AgentState
from core.candidate_sandbox_validation import (
    BASELINE_UNAVAILABLE,
    CANDIDATE_VALIDATION_FAILED,
    CANDIDATE_VALIDATION_INCONCLUSIVE,
    CANDIDATE_VALIDATION_LEGACY_UNVALIDATED,
    CANDIDATE_VALIDATION_PASSED,
    CATEGORY_CANDIDATE_APPLY_FAILED,
    CATEGORY_NO_CANDIDATE,
    CATEGORY_SANDBOX_UNAVAILABLE,
    SANDBOX_APPLY_APPLIED,
    SANDBOX_APPLY_FAILED,
    SANDBOX_APPLY_NOT_ATTEMPTED,
    SANDBOX_APPLY_UNAVAILABLE,
    candidate_fingerprint_from_payload,
    candidate_plan_from_payload,
    candidate_validation_is_current,
    candidate_validation_status_of_payload,
    describe_candidate_validation,
    normalize_baseline_validation,
    patch_candidate_as_plan,
    patch_plan_fingerprint,
    validate_candidate_in_sandbox,
)
from core.live_task_routing import route_live_task
from core.patch_basis import (
    PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
    PATCH_BASIS_GROUNDED_DEFECT,
)
from core.validation_outcome import (
    CATEGORY_NO_TESTS_COLLECTED,
    CATEGORY_NO_VALIDATION_COMMAND,
    CATEGORY_VALIDATION_TOOL_UNAVAILABLE,
)
from policy.decision_helper import build_patch_policy


PYTEST_COMMAND = "python -m pytest"

MODELS = '''from dataclasses import dataclass


@dataclass
class Task:
    title: str
    done: bool = False
'''

STORE = '''from models import Task


def build_task(title, done=False):
    return Task(title=title, done=done)


class TaskStore:
    def __init__(self):
        self.tasks = []

    def add(self, title, done=False):
        task = build_task(title, done)
        self.tasks.append(task)
        return task
'''

FILTERS = '''def only_open(tasks):
    return [t for t in tasks if not t.done]


def by_title(tasks, needle):
    return [t for t in tasks if needle in t.title]
'''

CLI = '''from store import TaskStore


def add_command(store, title):
    return store.add(title)


def list_command(store):
    return [t.title for t in store.tasks]
'''

TESTS = '''from store import TaskStore
from filters import only_open, by_title
from cli import add_command, list_command


def test_add_and_list():
    store = TaskStore()
    add_command(store, "write report")
    assert list_command(store) == ["write report"]


def test_only_open():
    store = TaskStore()
    store.add("a")
    store.add("b", done=True)
    assert [t.title for t in only_open(store.tasks)] == ["a"]


def test_by_title():
    store = TaskStore()
    store.add("alpha")
    assert len(by_title(store.tasks, "alph")) == 1
'''


def build_task_repo(root: Path) -> Path:
    """The T4-class repository: Task has no priority field anywhere."""

    root.mkdir(parents=True, exist_ok=True)
    (root / "models.py").write_text(MODELS, encoding="utf-8")
    (root / "store.py").write_text(STORE, encoding="utf-8")
    (root / "filters.py").write_text(FILTERS, encoding="utf-8")
    (root / "cli.py").write_text(CLI, encoding="utf-8")
    (root / "test_tasks.py").write_text(TESTS, encoding="utf-8")
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    return root


def snapshot_bytes(root: Path) -> dict[str, str]:
    """Every file under ``root`` by content hash — the real-repo tripwire."""

    return {
        str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def incoherent_plan() -> list[dict]:
    """The field test's final two-op plan: store + filters, models untouched."""

    return [
        {
            "op": "replace_snippet",
            "file": "store.py",
            "target_snippet": (
                "    def add(self, title, done=False):\n"
                "        task = build_task(title, done)"
            ),
            "patched_snippet": (
                "    def add(self, title, done=False, priority=0):\n"
                "        task = Task(title=title, done=done, priority=priority)"
            ),
        },
        {
            "op": "replace_snippet",
            "file": "filters.py",
            "target_snippet": "def by_title(tasks, needle):",
            "patched_snippet": (
                "def by_priority(tasks, minimum):\n"
                "    return [t for t in tasks if t.priority >= minimum]\n"
                "\n"
                "\n"
                "def by_title(tasks, needle):"
            ),
        },
    ]


def coherent_plan() -> list[dict]:
    """The coherent five-op version: model field, store, filter and CLI."""

    return [
        {
            "op": "replace_snippet",
            "file": "models.py",
            "target_snippet": "    title: str\n    done: bool = False",
            "patched_snippet": (
                "    title: str\n    done: bool = False\n    priority: int = 0"
            ),
        },
        {
            "op": "replace_snippet",
            "file": "store.py",
            "target_snippet": (
                "def build_task(title, done=False):\n"
                "    return Task(title=title, done=done)"
            ),
            "patched_snippet": (
                "def build_task(title, done=False, priority=0):\n"
                "    return Task(title=title, done=done, priority=priority)"
            ),
        },
        {
            "op": "replace_snippet",
            "file": "store.py",
            "target_snippet": (
                "    def add(self, title, done=False):\n"
                "        task = build_task(title, done)"
            ),
            "patched_snippet": (
                "    def add(self, title, done=False, priority=0):\n"
                "        task = build_task(title, done, priority)"
            ),
        },
        {
            "op": "replace_snippet",
            "file": "filters.py",
            "target_snippet": "def by_title(tasks, needle):",
            "patched_snippet": (
                "def by_priority(tasks, minimum):\n"
                "    return [t for t in tasks if t.priority >= minimum]\n"
                "\n"
                "\n"
                "def by_title(tasks, needle):"
            ),
        },
        {
            "op": "replace_snippet",
            "file": "cli.py",
            "target_snippet": (
                "def add_command(store, title):\n    return store.add(title)"
            ),
            "patched_snippet": (
                "def add_command(store, title, priority=0):\n"
                "    return store.add(title, priority=priority)"
            ),
        },
    ]


PASSING_BASELINE = {
    "ran": True,
    "ok": True,
    "outcome": "passed",
    "category": "",
    "command": PYTEST_COMMAND,
}


# ── The two headline cases ───────────────────────────────────────────────────


def test_incoherent_t4_candidate_fails_candidate_validation(tmp_path):
    repo = build_task_repo(tmp_path / "repo")

    result = validate_candidate_in_sandbox(
        repo,
        incoherent_plan(),
        validation_command=PYTEST_COMMAND,
        baseline_validation=PASSING_BASELINE,
    )

    assert result.status == CANDIDATE_VALIDATION_FAILED
    assert result.sandbox_apply_status == SANDBOX_APPLY_APPLIED
    assert result.approval_ready is False
    assert result.reviewable is True
    assert "unexpected keyword argument" in result.output_excerpt
    assert "Task" in result.output_excerpt
    assert result.command == PYTEST_COMMAND


def test_coherent_feature_candidate_passes_candidate_validation(tmp_path):
    repo = build_task_repo(tmp_path / "repo")

    result = validate_candidate_in_sandbox(
        repo,
        coherent_plan(),
        validation_command=PYTEST_COMMAND,
        baseline_validation=PASSING_BASELINE,
    )

    assert result.status == CANDIDATE_VALIDATION_PASSED
    assert result.sandbox_apply_status == SANDBOX_APPLY_APPLIED
    assert result.approval_ready is True
    assert result.reviewable is True


# ── Candidate identity ───────────────────────────────────────────────────────


def test_validation_result_binds_to_the_exact_final_candidate(tmp_path):
    repo = build_task_repo(tmp_path / "repo")
    plan = coherent_plan()

    result = validate_candidate_in_sandbox(
        repo, plan, validation_command=PYTEST_COMMAND
    )

    assert result.fingerprint == patch_plan_fingerprint(plan)
    payload = {"patch_plan": plan, **result.as_telemetry()}
    assert candidate_validation_is_current(payload) is True
    assert candidate_validation_status_of_payload(payload) == (
        CANDIDATE_VALIDATION_PASSED
    )


def test_refinement_invalidates_a_previous_candidate_validation(tmp_path):
    repo = build_task_repo(tmp_path / "repo")
    draft = coherent_plan()

    passed = validate_candidate_in_sandbox(
        repo, draft, validation_command=PYTEST_COMMAND
    )
    assert passed.status == CANDIDATE_VALIDATION_PASSED

    # The reviewer/refine step replaces the plan. The stored result belongs to
    # the plan it validated, so it stops matching the moment the plan changes.
    refined_payload = {"patch_plan": incoherent_plan(), **passed.as_telemetry()}
    assert candidate_validation_is_current(refined_payload) is False
    assert passed.fingerprint != candidate_fingerprint_from_payload(refined_payload)

    revalidated = validate_candidate_in_sandbox(
        repo, incoherent_plan(), validation_command=PYTEST_COMMAND
    )
    assert revalidated.status == CANDIDATE_VALIDATION_FAILED
    assert revalidated.approval_ready is False


def test_fingerprint_ignores_the_two_spellings_of_the_same_path():
    with_file = [{"op": "replace_snippet", "file": "a.py", "target_snippet": "x",
                  "patched_snippet": "y"}]
    with_relative = [{"op": "replace_snippet", "relative_path": "a.py",
                      "target_snippet": "x", "patched_snippet": "y"}]
    assert patch_plan_fingerprint(with_file) == patch_plan_fingerprint(with_relative)

    changed = [{"op": "replace_snippet", "file": "a.py", "target_snippet": "x",
                "patched_snippet": "z"}]
    assert patch_plan_fingerprint(with_file) != patch_plan_fingerprint(changed)


def test_single_file_candidate_is_expressed_as_the_one_op_plan_it_is():
    candidate = {
        "relative_path": "store.py",
        "target_snippet": "a",
        "patched_snippet": "b",
    }
    plan = patch_candidate_as_plan(candidate)
    assert plan == [
        {
            "op": "replace_snippet",
            "relative_path": "store.py",
            "target_snippet": "a",
            "patched_snippet": "b",
        }
    ]
    assert candidate_plan_from_payload({"patch_candidate": candidate}) == plan


# ── Baseline health ──────────────────────────────────────────────────────────


def test_baseline_passed_and_candidate_failed_reads_as_a_plain_regression(tmp_path):
    repo = build_task_repo(tmp_path / "repo")
    result = validate_candidate_in_sandbox(
        repo,
        incoherent_plan(),
        validation_command=PYTEST_COMMAND,
        baseline_validation=PASSING_BASELINE,
    )
    assert result.baseline_status == CANDIDATE_VALIDATION_PASSED
    assert result.status == CANDIDATE_VALIDATION_FAILED
    assert result.approval_ready is False


def test_baseline_failed_does_not_excuse_a_failed_candidate(tmp_path):
    repo = build_task_repo(tmp_path / "repo")
    result = validate_candidate_in_sandbox(
        repo,
        incoherent_plan(),
        validation_command=PYTEST_COMMAND,
        baseline_validation={
            "ran": True,
            "ok": False,
            "outcome": "failed",
            "category": "assertion_failure",
        },
    )
    # No "no worse than baseline" equivalence is attempted in this phase.
    assert result.baseline_status == CANDIDATE_VALIDATION_FAILED
    assert result.status == CANDIDATE_VALIDATION_FAILED
    assert result.approval_ready is False


def test_baseline_inconclusive_is_preserved_as_its_own_fact(tmp_path):
    repo = build_task_repo(tmp_path / "repo")
    result = validate_candidate_in_sandbox(
        repo,
        coherent_plan(),
        validation_command=PYTEST_COMMAND,
        baseline_validation={
            "ran": False,
            "ok": None,
            "outcome": "inconclusive",
            "category": CATEGORY_NO_VALIDATION_COMMAND,
        },
    )
    assert result.baseline_status == CANDIDATE_VALIDATION_INCONCLUSIVE
    assert result.baseline_category == CATEGORY_NO_VALIDATION_COMMAND
    assert result.status == CANDIDATE_VALIDATION_PASSED


def test_absent_baseline_is_unavailable_not_passed():
    assert normalize_baseline_validation(None)["status"] == BASELINE_UNAVAILABLE
    assert normalize_baseline_validation({})["status"] == BASELINE_UNAVAILABLE
    assert normalize_baseline_validation(
        {"ran": False, "ok": None}
    )["status"] == BASELINE_UNAVAILABLE


# ── Inconclusive paths ───────────────────────────────────────────────────────


def test_missing_validation_command_is_inconclusive_not_passed(tmp_path):
    repo = build_task_repo(tmp_path / "repo")
    result = validate_candidate_in_sandbox(
        repo, coherent_plan(), validation_command=""
    )
    assert result.status == CANDIDATE_VALIDATION_INCONCLUSIVE
    assert result.category == CATEGORY_NO_VALIDATION_COMMAND
    assert result.sandbox_apply_status == SANDBOX_APPLY_NOT_ATTEMPTED
    assert result.approval_ready is False
    assert "could not establish success" in describe_candidate_validation(result)


def test_empty_candidate_is_inconclusive(tmp_path):
    repo = build_task_repo(tmp_path / "repo")
    result = validate_candidate_in_sandbox(
        repo, [], validation_command=PYTEST_COMMAND
    )
    assert result.status == CANDIDATE_VALIDATION_INCONCLUSIVE
    assert result.category == CATEGORY_NO_CANDIDATE
    assert result.approval_ready is False


def test_sandbox_creation_failure_is_inconclusive(tmp_path, monkeypatch):
    repo = build_task_repo(tmp_path / "repo")
    before = snapshot_bytes(repo)
    monkeypatch.setattr(
        csv_mod,
        "create_managed_sandbox",
        lambda *a, **k: {"ok": False, "error": "copy failed: OSError: disk full"},
    )

    result = validate_candidate_in_sandbox(
        repo, coherent_plan(), validation_command=PYTEST_COMMAND
    )

    assert result.status == CANDIDATE_VALIDATION_INCONCLUSIVE
    assert result.category == CATEGORY_SANDBOX_UNAVAILABLE
    assert result.sandbox_apply_status == SANDBOX_APPLY_UNAVAILABLE
    assert result.approval_ready is False
    assert "disk full" in result.inconclusive_reason
    assert snapshot_bytes(repo) == before


def test_missing_repository_path_is_inconclusive(tmp_path):
    result = validate_candidate_in_sandbox(
        tmp_path / "nope", coherent_plan(), validation_command=PYTEST_COMMAND
    )
    assert result.status == CANDIDATE_VALIDATION_INCONCLUSIVE
    assert result.category == CATEGORY_SANDBOX_UNAVAILABLE
    assert result.approval_ready is False


def test_repository_with_no_tests_is_inconclusive_not_passed(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (repo / "lib.py").write_text("VALUE = 0\n", encoding="utf-8")

    result = validate_candidate_in_sandbox(
        repo,
        [
            {
                "op": "replace_snippet",
                "file": "lib.py",
                "target_snippet": "VALUE = 0",
                "patched_snippet": "VALUE = 1",
            }
        ],
        validation_command=PYTEST_COMMAND,
    )

    assert result.status == CANDIDATE_VALIDATION_INCONCLUSIVE
    assert result.category == CATEGORY_NO_TESTS_COLLECTED
    assert result.sandbox_apply_status == SANDBOX_APPLY_APPLIED
    assert result.approval_ready is False


def test_unavailable_validation_tool_is_inconclusive_not_a_repository_defect(
    tmp_path,
):
    """A missing runner says nothing about the candidate.

    OPS.VALIDATE.1 already draws this line; the sandbox path inherits it rather
    than letting an absent tool masquerade as proof the candidate is broken.
    """

    repo = build_task_repo(tmp_path / "repo")
    result = validate_candidate_in_sandbox(
        repo,
        coherent_plan(),
        validation_command="definitely-not-a-real-validation-tool --run",
        baseline_validation=PASSING_BASELINE,
    )

    assert result.status == CANDIDATE_VALIDATION_INCONCLUSIVE
    assert result.category == CATEGORY_VALIDATION_TOOL_UNAVAILABLE
    assert result.sandbox_apply_status == SANDBOX_APPLY_APPLIED
    assert result.approval_ready is False
    assert snapshot_bytes(repo) == snapshot_bytes(repo)


def test_no_dependency_is_installed_to_rescue_an_unavailable_tool(tmp_path):
    """Fail closed rather than reaching for the network."""

    repo = build_task_repo(tmp_path / "repo")
    before = snapshot_bytes(repo)
    result = validate_candidate_in_sandbox(
        repo,
        coherent_plan(),
        validation_command="definitely-not-a-real-validation-tool --run",
    )
    assert result.status == CANDIDATE_VALIDATION_INCONCLUSIVE
    assert snapshot_bytes(repo) == before


# ── Apply failures ───────────────────────────────────────────────────────────


def test_patch_application_failure_is_failed(tmp_path):
    repo = build_task_repo(tmp_path / "repo")
    result = validate_candidate_in_sandbox(
        repo,
        [
            {
                "op": "replace_snippet",
                "file": "store.py",
                "target_snippet": "this snippet is not in the file",
                "patched_snippet": "anything",
            }
        ],
        validation_command=PYTEST_COMMAND,
    )

    assert result.status == CANDIDATE_VALIDATION_FAILED
    assert result.category == CATEGORY_CANDIDATE_APPLY_FAILED
    assert result.sandbox_apply_status == SANDBOX_APPLY_FAILED
    assert result.failed_op_index == 0
    assert result.approval_ready is False
    assert "could not be materialized" in describe_candidate_validation(result)


def test_create_over_an_existing_file_fails_the_candidate(tmp_path):
    repo = build_task_repo(tmp_path / "repo")
    result = validate_candidate_in_sandbox(
        repo,
        [{"op": "create_file", "file": "models.py", "content": "X = 1\n"}],
        validation_command=PYTEST_COMMAND,
    )
    assert result.status == CANDIDATE_VALIDATION_FAILED
    assert result.sandbox_apply_status == SANDBOX_APPLY_FAILED


# ── Real repository isolation ────────────────────────────────────────────────


def test_real_repository_is_byte_identical_after_a_passing_candidate(tmp_path):
    repo = build_task_repo(tmp_path / "repo")
    before = snapshot_bytes(repo)

    result = validate_candidate_in_sandbox(
        repo, coherent_plan(), validation_command=PYTEST_COMMAND
    )

    assert result.status == CANDIDATE_VALIDATION_PASSED
    assert snapshot_bytes(repo) == before


def test_real_repository_is_byte_identical_after_a_failing_candidate(tmp_path):
    repo = build_task_repo(tmp_path / "repo")
    before = snapshot_bytes(repo)

    result = validate_candidate_in_sandbox(
        repo, incoherent_plan(), validation_command=PYTEST_COMMAND
    )

    assert result.status == CANDIDATE_VALIDATION_FAILED
    assert snapshot_bytes(repo) == before


def test_validation_side_effects_never_reach_the_real_repository(tmp_path):
    """__pycache__ and friends belong to the sandbox and die with it."""

    repo = build_task_repo(tmp_path / "repo")
    before = snapshot_bytes(repo)

    validate_candidate_in_sandbox(
        repo, coherent_plan(), validation_command=PYTEST_COMMAND
    )

    after = snapshot_bytes(repo)
    assert after == before
    assert not (repo / "__pycache__").exists()
    assert not (repo / ".pytest_cache").exists()
    assert not (repo / ".agent").exists()


def test_ops_patch_1_byte_semantics_survive_the_sandbox_path(tmp_path):
    """A CRLF file keeps CRLF; only the requested replacement differs."""

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (repo / "crlf.py").write_bytes(b"VALUE = 0\r\nOTHER = 1\r\n")
    (repo / "test_crlf.py").write_text(
        "from crlf import VALUE\n\n\ndef test_value():\n    assert VALUE == 1\n",
        encoding="utf-8",
    )
    original = (repo / "crlf.py").read_bytes()

    result = validate_candidate_in_sandbox(
        repo,
        [
            {
                "op": "replace_snippet",
                "file": "crlf.py",
                "target_snippet": "VALUE = 0",
                "patched_snippet": "VALUE = 1",
            }
        ],
        validation_command=PYTEST_COMMAND,
        keep_sandbox=True,
    )

    assert result.status == CANDIDATE_VALIDATION_PASSED
    # Real file untouched, terminators included.
    assert (repo / "crlf.py").read_bytes() == original
    # Sandbox copy kept CRLF; only the value changed.
    sandbox_bytes = (Path(result.sandbox_path) / "crlf.py").read_bytes()
    assert sandbox_bytes == b"VALUE = 1\r\nOTHER = 1\r\n"


def test_create_file_and_multi_file_candidates_materialize_together(tmp_path):
    repo = build_task_repo(tmp_path / "repo")
    before = snapshot_bytes(repo)

    plan = coherent_plan() + [
        {
            "op": "create_file",
            "file": "priority.py",
            "content": "HIGH = 10\nLOW = 0\n",
        },
        {
            "op": "replace_snippet",
            "file": "filters.py",
            "target_snippet": "def only_open(tasks):",
            "patched_snippet": (
                "from priority import HIGH  # noqa: F401\n\n\ndef only_open(tasks):"
            ),
        },
    ]

    result = validate_candidate_in_sandbox(
        repo, plan, validation_command=PYTEST_COMMAND, keep_sandbox=True
    )

    assert result.status == CANDIDATE_VALIDATION_PASSED
    assert result.sandbox_apply_status == SANDBOX_APPLY_APPLIED
    assert (Path(result.sandbox_path) / "priority.py").is_file()
    # The created file exists only in the sandbox.
    assert not (repo / "priority.py").exists()
    assert snapshot_bytes(repo) == before


# ── Telemetry ────────────────────────────────────────────────────────────────


def test_telemetry_is_bounded_categorical_and_carries_no_score(tmp_path):
    repo = build_task_repo(tmp_path / "repo")
    result = validate_candidate_in_sandbox(
        repo,
        incoherent_plan(),
        validation_command=PYTEST_COMMAND,
        baseline_validation=PASSING_BASELINE,
    )
    telemetry = result.as_telemetry()

    for key in (
        "candidate_validation_status",
        "candidate_validation_category",
        "candidate_validation_command",
        "candidate_validation_fingerprint",
        "candidate_validation_inconclusive_reason",
        "baseline_validation_status",
        "sandbox_apply_status",
        "approval_ready",
    ):
        assert key in telemetry, key

    forbidden = {"score", "confidence", "quality", "regression_score", "weight"}
    assert not any(
        any(word in key for word in forbidden) for key in telemetry
    )
    assert len(telemetry["candidate_validation_output_excerpt"]) <= (
        csv_mod.MAX_OUTPUT_EXCERPT_CHARS
    )
    assert set(result.timings) >= {
        "sandbox_create_sec",
        "candidate_apply_and_validation_sec",
        "cleanup_sec",
        "total_sec",
    }


def test_historical_artifacts_read_as_legacy_unvalidated_not_passed():
    historical = {
        "patch_basis": PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
        "patch_plan": incoherent_plan(),
        "human_approval_required": True,
        "write_authority": False,
    }
    assert candidate_validation_status_of_payload(historical) == (
        CANDIDATE_VALIDATION_LEGACY_UNVALIDATED
    )
    assert candidate_validation_is_current(historical) is False
    assert candidate_validation_status_of_payload(None) == (
        CANDIDATE_VALIDATION_LEGACY_UNVALIDATED
    )


def test_wording_never_calls_a_non_passing_candidate_ready_or_clean(tmp_path):
    repo = build_task_repo(tmp_path / "repo")
    failed = validate_candidate_in_sandbox(
        repo, incoherent_plan(), validation_command=PYTEST_COMMAND
    )
    inconclusive = validate_candidate_in_sandbox(
        repo, coherent_plan(), validation_command=""
    )

    for result in (failed, inconclusive):
        text = describe_candidate_validation(result).lower()
        for word in ("clean", "ready to apply", "working"):
            assert word not in text
        assert "has not been applied to the real repository" in text or (
            "could not establish success" in text
        )

    passed = validate_candidate_in_sandbox(
        repo, coherent_plan(), validation_command=PYTEST_COMMAND
    )
    assert "passed" in describe_candidate_validation(passed).lower()


# ── Boundaries: no model, no network, no git mutation, no install ────────────


def _executable_source(module) -> str:
    """The module's code with docstrings and comments removed.

    Scanning raw text would trip over this module's own prose, which names
    ``git stash`` precisely to say it is not used.  Unparsing the AST after
    stripping docstrings leaves only what actually runs.
    """

    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(ast.fix_missing_locations(tree))


def test_gate_adds_no_model_network_or_dependency_installation():
    tree = ast.parse(inspect.getsource(csv_mod))
    forbidden_calls = {
        "run_gemini_request",
        "run_gemini_request_2",
        "run_deepseek_review",
        "urlopen",
        "urlretrieve",
        "build_graph_from_repo",
        "trace_execution_flow",
        "build_index",
        "retrieve_context",
        "system",
        "check_output",
        "Popen",
    }
    assert not any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id in forbidden_calls)
            or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in forbidden_calls
            )
        )
        for node in ast.walk(tree)
    )

    code = _executable_source(csv_mod).lower()
    for forbidden in (
        "pip install",
        "npm install",
        "pnpm install",
        "yarn install",
        "npx ",
        "git stash",
        "git reset",
        "git clean",
        "http://",
        "https://",
    ):
        assert forbidden not in code, forbidden


def test_gate_never_shells_out_or_imports_a_network_client():
    code = _executable_source(csv_mod)
    for forbidden in ("subprocess", "requests", "urllib", "socket", "git"):
        assert forbidden not in code, forbidden


# ── Pipeline wiring ──────────────────────────────────────────────────────────


def _write(repo: Path, relative: str, text: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


#: The field test's premise: an ordinary explicit change with no literal
#: "across A/B/C" multi-surface obligation, so CONTROL's scope gate has nothing
#: to reject and the incoherent plan legitimately reaches patch safety. Only
#: sandbox validation can catch it from there.
FEATURE_REQUEST = "Add a priority field to tasks so they can be sorted by priority."

#: The same feature written with an explicit multi-surface scope. CONTROL
#: rejects a plan that skips a named layer long before any sandbox exists.
SCOPED_FEATURE_REQUEST = (
    "Add task priority support across model/store/filters/cli."
)


def _feature_route(text: str = FEATURE_REQUEST) -> dict:
    return route_live_task(text, repository_available=True).as_dict()


def _control(repo: Path, route: dict, related: list[str]) -> dict:
    hypotheses = [
        {
            "symbol": "models.py::Task",
            "score": 100.0,
            "confidence": 0.99,
            "reasons": ["fixture"],
            "called_by": [],
            "calls": [],
        }
    ]
    control = {
        "repo_path": str(repo),
        "query": "add task priority support",
        "top_hypothesis": hypotheses[0],
        "hypotheses": hypotheses,
        "evidence": hypotheses,
        "execution_trace": "",
        "related_snippets": [],
        "live_route": route,
        "preflight_validation": dict(PASSING_BASELINE),
    }
    control_engine.refresh_control_safety(control)
    control["related_snippets"] = [
        {
            "file": relative,
            "symbol": Path(relative).stem,
            "snippet": (repo / relative).read_text(encoding="utf-8"),
        }
        for relative in related
    ]
    control_engine.refresh_control_safety(control)
    return control


def _state(
    repo: Path,
    control: dict,
    block: dict,
    *,
    intent: str,
    style: str,
    user_input: str = FEATURE_REQUEST,
):
    return AgentState(
        interface="agent",
        mode="reviewer",
        user_input=user_input,
        file_paths=[str(repo)],
        primary_file=None,
        input_mode="error_log",
        language="python",
        task_type=intent,
        task_info={
            "intent": intent,
            "complexity": "simple",
            "language": "python",
            "patch_style": style,
        },
        is_project_input=True,
        repo_path=str(repo),
        control_result=control,
        live_route=control.get("live_route") or {},
        json_block=block,
    )


def _disable_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "get_tooling_profile", lambda *a, **k: {})
    monkeypatch.setattr(pipeline, "upsert_tooling_profile", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "save_patch_attempt", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "save_engineering_memory", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "refresh_memory_block", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", True)


def _spy_sandbox(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Record every sandbox materialization the pipeline attempts."""

    calls: list[dict] = []
    original = pipeline.validate_candidate_in_sandbox

    def _record(repo_path, plan, **kwargs):
        calls.append({"repo_path": str(repo_path), "plan": plan, **kwargs})
        return original(repo_path, plan, **kwargs)

    monkeypatch.setattr(pipeline, "validate_candidate_in_sandbox", _record)
    return calls


def _feature_state(tmp_path, plan, monkeypatch, *, style="vibe"):
    repo = build_task_repo(tmp_path / "repo")
    control = _control(
        repo,
        _feature_route(),
        ["models.py", "store.py", "filters.py", "cli.py"],
    )
    block = {
        "patch_plan": plan,
        "patch_candidate": None,
        "confidence": 1.0,
        "needs_escalation": False,
        "issues": [],
    }
    control_engine.enforce_control_grounding_on_payload(control, block)
    state = _state(repo, control, block, intent="feature_add", style=style)
    _disable_persistence(monkeypatch)
    return repo, state


def test_pipeline_blocks_approval_for_the_incoherent_final_candidate(
    tmp_path, monkeypatch
):
    repo, state = _feature_state(tmp_path, incoherent_plan(), monkeypatch)
    before = snapshot_bytes(repo)
    calls = _spy_sandbox(monkeypatch)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert state.json_block["patch_basis"] == PATCH_BASIS_EXPLICIT_CHANGE_REQUEST
    assert state.patch_policy["patch_safety"]["ok"] is True
    assert len(calls) == 1
    assert state.json_block["candidate_validation_status"] == (
        CANDIDATE_VALIDATION_FAILED
    )
    assert state.json_block["sandbox_apply_status"] == SANDBOX_APPLY_APPLIED
    assert state.json_block["approval_ready"] is False
    assert state.json_block["baseline_validation_status"] == (
        CANDIDATE_VALIDATION_PASSED
    )
    assert state.json_block["write_authority"] is False
    assert state.json_block["patch_application_authority"] is False
    assert state.json_block["human_approval_required"] is True
    # Diagnostics survive; the plan stays visible for human reading.
    assert state.json_block["patch_plan"] == incoherent_plan()
    assert "unexpected keyword argument" in (
        state.json_block["candidate_validation_output_excerpt"]
    )
    assert snapshot_bytes(repo) == before


def test_pipeline_marks_the_coherent_final_candidate_validated_without_writing(
    tmp_path, monkeypatch
):
    repo, state = _feature_state(tmp_path, coherent_plan(), monkeypatch)
    before = snapshot_bytes(repo)
    calls = _spy_sandbox(monkeypatch)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert len(calls) == 1
    assert calls[0]["validation_command"] == PYTEST_COMMAND
    assert state.json_block["candidate_validation_status"] == (
        CANDIDATE_VALIDATION_PASSED
    )
    assert state.json_block["approval_ready"] is True
    # Passing validation is not write authority.
    assert state.json_block["write_authority"] is False
    assert state.json_block["patch_application_authority"] is False
    assert state.json_block["human_approval_required"] is True
    assert state.json_block["auto_apply_allowed"] is False
    assert snapshot_bytes(repo) == before


def test_pipeline_binds_the_recorded_fingerprint_to_the_presented_candidate(
    tmp_path, monkeypatch
):
    repo, state = _feature_state(tmp_path, coherent_plan(), monkeypatch)
    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert candidate_validation_is_current(state.json_block) is True
    assert state.json_block["candidate_validation_fingerprint"] == (
        patch_plan_fingerprint(state.json_block["patch_plan"])
    )

    # A later refinement replaces the plan: the stored validation is stale.
    state.json_block["patch_plan"] = incoherent_plan()
    assert candidate_validation_is_current(state.json_block) is False


def test_failed_refinement_does_not_resurrect_the_passing_draft(
    tmp_path, monkeypatch
):
    repo, state = _feature_state(tmp_path, coherent_plan(), monkeypatch)
    pipeline.maybe_run_auto_patch(state, interactive=False)
    assert state.json_block["candidate_validation_status"] == (
        CANDIDATE_VALIDATION_PASSED
    )
    draft = list(state.json_block["patch_plan"])

    # Refinement degrades the plan; the pipeline revalidates the new one and
    # blocks it. It does not silently swap the earlier draft back in.
    state.json_block["patch_plan"] = incoherent_plan()
    state.json_block["eligible_for_patch_safety_handoff"] = True
    state.json_block["needs_escalation"] = False
    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert state.json_block["candidate_validation_status"] == (
        CANDIDATE_VALIDATION_FAILED
    )
    assert state.json_block["approval_ready"] is False
    assert state.json_block["patch_plan"] == incoherent_plan()
    assert state.json_block["patch_plan"] != draft
    assert snapshot_bytes(repo) == snapshot_bytes(repo)


def test_test_path_candidate_is_rejected_by_safety_before_any_sandbox(
    tmp_path, monkeypatch
):
    """A candidate that rewrites a test expectation never reaches the sandbox.

    Sandbox validation must not become a way around the test-path gate: a
    corrupted test that happens to pass is still a corrupted test, so patch
    safety refuses the candidate first and nothing is ever materialized.
    """

    repo = build_task_repo(tmp_path / "repo")
    control = _control(repo, _feature_route(), ["models.py", "test_tasks.py"])
    block = {
        "patch_plan": [
            {
                "op": "replace_snippet",
                "file": "test_tasks.py",
                "target_snippet": 'assert list_command(store) == ["write report"]',
                "patched_snippet": "assert True",
            }
        ],
        # Pre-marked as grounded so the candidate reaches patch safety rather
        # than stopping at CONTROL: this test is about the safety gate.
        "patch_basis": PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
        "target_source_grounded": True,
        "eligible_for_patch_safety_handoff": True,
        "confidence": 1.0,
        "needs_escalation": False,
    }
    state = _state(repo, control, block, intent="feature_add", style="vibe")
    state.is_project_input = False
    _disable_persistence(monkeypatch)
    calls = _spy_sandbox(monkeypatch)
    before = snapshot_bytes(repo)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert calls == []
    assert state.patch_policy["patch_safety"]["ok"] is False
    assert "test path" in " ".join(state.patch_policy["patch_safety"]["reasons"])
    assert state.json_block["approval_ready"] is False
    assert state.json_block["candidate_validation_status"] == (
        CANDIDATE_VALIDATION_INCONCLUSIVE
    )
    assert state.json_block["sandbox_apply_status"] == SANDBOX_APPLY_NOT_ATTEMPTED
    assert snapshot_bytes(repo) == before


def test_scoped_request_rejects_a_layer_skipping_plan_before_any_sandbox(
    tmp_path, monkeypatch
):
    """Preserved multi-surface scope still runs first and still fails closed."""

    repo = build_task_repo(tmp_path / "repo")
    control = _control(
        repo,
        _feature_route(SCOPED_FEATURE_REQUEST),
        ["models.py", "store.py", "filters.py", "cli.py"],
    )
    block = {"patch_plan": incoherent_plan(), "confidence": 1.0,
             "needs_escalation": False}
    control_engine.enforce_control_grounding_on_payload(control, block)
    assert block["change_scope_grounded"] is False
    assert block["patch_plan"] is None

    state = _state(
        repo,
        control,
        block,
        intent="feature_add",
        style="vibe",
        user_input=SCOPED_FEATURE_REQUEST,
    )
    _disable_persistence(monkeypatch)
    calls = _spy_sandbox(monkeypatch)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert calls == []


def test_arbitrary_new_target_is_rejected_before_any_sandbox(tmp_path, monkeypatch):
    repo = build_task_repo(tmp_path / "repo")
    control = _control(repo, _feature_route(), ["models.py"])
    block = {
        "patch_plan": [
            {"op": "create_file", "file": "surprise.py", "content": "VALUE = 1\n"}
        ],
        "confidence": 1.0,
        "needs_escalation": False,
    }
    control_engine.enforce_control_grounding_on_payload(control, block)
    state = _state(repo, control, block, intent="feature_add", style="vibe")
    _disable_persistence(monkeypatch)
    calls = _spy_sandbox(monkeypatch)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert block["patch_plan"] is None
    assert calls == []
    assert not (repo / "surprise.py").exists()


def test_grounded_defect_handoff_does_not_enter_the_candidate_sandbox_gate(
    tmp_path, monkeypatch
):
    """T1/T2/T3 defect semantics are untouched by this phase."""

    repo = build_task_repo(tmp_path / "repo")
    control = _control(repo, _feature_route(), ["models.py"])
    block = {
        "patch_plan": coherent_plan(),
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "target_source_grounded": True,
        "eligible_for_patch_safety_handoff": True,
        "confidence": 1.0,
        "needs_escalation": False,
    }
    state = _state(repo, control, block, intent="bug_fix", style="vibe")
    state.is_project_input = False  # skip the CONTROL grounding re-derivation
    _disable_persistence(monkeypatch)
    calls = _spy_sandbox(monkeypatch)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert calls == []
    assert "candidate_validation_status" not in state.json_block
    assert state.patch_policy["write_authority"] is False


def test_analysis_route_never_materializes_a_sandbox(tmp_path, monkeypatch):
    repo = build_task_repo(tmp_path / "repo")
    route = route_live_task(
        "Explain how the task store works.", repository_available=True
    ).as_dict()
    control = _control(repo, route, ["models.py"])
    block = {"patch_plan": coherent_plan(), "confidence": 1.0}
    state = _state(repo, control, block, intent="analysis", style="vibe")
    _disable_persistence(monkeypatch)
    calls = _spy_sandbox(monkeypatch)
    before = snapshot_bytes(repo)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert calls == []
    assert snapshot_bytes(repo) == before


def test_clarification_route_never_materializes_a_sandbox(tmp_path, monkeypatch):
    repo = build_task_repo(tmp_path / "repo")
    route = route_live_task("do the thing", repository_available=True).as_dict()
    control = _control(repo, route, ["models.py"])
    block = {"patch_plan": coherent_plan(), "confidence": 1.0}
    state = _state(repo, control, block, intent="feature_add", style="vibe")
    _disable_persistence(monkeypatch)
    calls = _spy_sandbox(monkeypatch)
    before = snapshot_bytes(repo)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert calls == []
    assert snapshot_bytes(repo) == before


def test_explicit_change_policy_still_forbids_automatic_application():
    policy = build_patch_policy(
        "vibe",
        language="python",
        patch_confidence=1.0,
        patch_basis=PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
        has_validation_command=True,
    )
    assert policy.patch_basis_accepted is True
    assert policy.auto_apply_allowed is False
    assert policy.human_approval_required is True
