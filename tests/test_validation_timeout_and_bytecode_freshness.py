"""OPS.VALIDATE.2 — timeout truthfulness and Python bytecode freshness.

Two reproduced production defects, one file, because they are the same claim:
*the thing validation reports must be the thing that actually happened*.

**Defect A — timeout laundering.**  On the C.A.T.T.U.S self-repository
black-box task (~8,944 tests, ``python -m pytest``, 30 s budget) the command
exceeded its budget and production reported ``test_failure``.  It is false: the
validator ran out of time, and the tests established nothing about the
candidate.  A budget is a fact about the validator, never evidence about the
code, so it must be ``inconclusive`` and it must never ground a defect.

**Defect B — stale bytecode.**  CPython accepts a cached ``.pyc`` when the
source's *size* and *whole-second mtime* match the pyc header.  A same-size
patch inside one timestamp second satisfies both, so validation could execute
the pre-patch bytecode.  ``return "A"`` → ``return "B"`` reproduces it, and
``-B`` / ``PYTHONDONTWRITEBYTECODE`` do **not** fix it — they stop writes, not
reads.

The tests below run real subprocesses through the production entry points.  No
model call, no network call, nothing installed, and no timing-based waiting:
the timeout cases use a tiny budget against a deliberately slower command, so
the suite never sits for 30 seconds to prove a point.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.executor import Executor  # noqa: E402
from core.live_validation_receipt import live_validation_result  # noqa: E402
from core.post_run_reconciliation import (  # noqa: E402
    RECEIPT_FAILED,
    RECEIPT_PASSED,
    RECEIPT_RESULTS,
    RECEIPT_TIMED_OUT,
)
from core.preflight import run_preflight_validation  # noqa: E402
from core.run_lifecycle import _shadow_validation_facts  # noqa: E402
from core.validation_bytecode_cache import (  # noqa: E402
    PYCACHE_PREFIX_ENV,
    VALIDATION_PYCACHE_DIR_PREFIX,
    create_validation_bytecode_cache_dir,
    discard_validation_bytecode_cache_dir,
    validation_bytecode_cache,
    validation_bytecode_cache_guarantees,
)
from core.validation_execution import (  # noqa: E402
    VALIDATION_BUDGET_EXHAUSTED_MARKER,
    SafeValidationCommand,
    run_safe_validation_command,
)
from core.validation_outcome import (  # noqa: E402
    CATEGORY_NO_TESTS_COLLECTED,
    CATEGORY_VALIDATION_BUDGET_EXHAUSTED,
    CATEGORY_VALIDATION_TOOL_UNAVAILABLE,
    VALIDATION_FAILED,
    VALIDATION_INCONCLUSIVE,
    VALIDATION_PASSED,
    budget_exhausted_info,
    is_compiler_grounded_category,
    is_executed_failure_evidence,
    is_inconclusive_category,
    is_validation_budget_exhausted,
    validation_outcome,
)
from core.validator import (  # noqa: E402
    classify_validation_output,
    detect_validation_budget_exhausted,
    run_validation_command_detailed,
)
from patching.patch_plan_executor import apply_patch_plan  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

#: A command that certainly outlives a one-second budget without being a test
#: failure of any kind.  ``python -c`` is refused by the safe-argv gate, so the
#: slow work lives in a real file the fixture writes.
_SLEEPER = "import time\ntime.sleep(30)\n"

#: The partial output a stopped pytest run leaves behind.  This is the exact
#: text shape that used to be classified ``test_failure``.
_PARTIAL_PYTEST_OUTPUT = (
    "============================= test session starts =====================\n"
    "collected 8944 items\n\n"
    "tests/test_a.py ......................................            [  1%]\n"
    "tests/test_b.py ...F..                                            [  2%]\n"
    "FAILED tests/test_b.py::test_thing\n"
)


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


def _sleeper_repo(root: Path) -> Path:
    """A repository whose validation command reliably exceeds a tiny budget."""
    root.mkdir(parents=True, exist_ok=True)
    _write(root, "slow_validation.py", _SLEEPER)
    return root


def _safe_sleeper(root: Path, timeout_sec: int = 1) -> SafeValidationCommand:
    return SafeValidationCommand(
        command=["python", "slow_validation.py"],
        cwd=str(root),
        timeout_sec=timeout_sec,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. Vocabulary — one canonical word, in the inconclusive set and nowhere else
# ══════════════════════════════════════════════════════════════════════════════

def test_budget_exhausted_is_inconclusive_and_never_executed_failure_evidence():
    assert is_inconclusive_category(CATEGORY_VALIDATION_BUDGET_EXHAUSTED)
    assert is_validation_budget_exhausted(CATEGORY_VALIDATION_BUDGET_EXHAUSTED)
    assert not is_executed_failure_evidence(CATEGORY_VALIDATION_BUDGET_EXHAUSTED)
    assert not is_compiler_grounded_category(CATEGORY_VALIDATION_BUDGET_EXHAUSTED)


def test_budget_exhausted_resolves_to_inconclusive_whatever_the_boolean_says():
    for ok in (True, False, None):
        assert (
            validation_outcome(
                category=CATEGORY_VALIDATION_BUDGET_EXHAUSTED, ok=ok
            )
            == VALIDATION_INCONCLUSIVE
        )


def test_budget_exhausted_info_carries_no_score_and_no_prediction():
    info = budget_exhausted_info(30)
    assert info["category"] == CATEGORY_VALIDATION_BUDGET_EXHAUSTED
    assert "30s" in info["reason"]
    # No score, no confidence, and no claim about the eventual verdict.
    assert not {"score", "confidence", "weight"} & set(info)
    text = (info["reason"] + info["hint"]).lower()
    assert "fail" not in text.replace("would pass or fail", "")
    assert "test_failure" not in text


# ══════════════════════════════════════════════════════════════════════════════
# 2. The classifier — the exact place the laundering happened
# ══════════════════════════════════════════════════════════════════════════════

def test_partial_pytest_output_looks_like_defect_evidence_on_its_own():
    """The defect, pinned.

    Read without knowing a budget ran out, the partial output of a stopped
    pytest run lands in an *executed-failure* category — the set that is
    allowed to ground a diagnosis.  That is precisely how a 30 s budget on
    ~8,944 tests became ``test_failure`` in production.
    """
    category = classify_validation_output(_PARTIAL_PYTEST_OUTPUT)["category"]
    assert is_executed_failure_evidence(category)
    assert not is_inconclusive_category(category)


def test_timed_out_flag_beats_every_taxonomy_branch():
    info = classify_validation_output(
        _PARTIAL_PYTEST_OUTPUT, timed_out=True, timeout_seconds=30
    )
    assert info["category"] == CATEGORY_VALIDATION_BUDGET_EXHAUSTED
    assert info["category"] != "test_failure"


def test_budget_marker_in_output_alone_prevents_laundering():
    """Defence in depth: a caller that drops the flag still cannot mislead."""
    text = f"Validation {VALIDATION_BUDGET_EXHAUSTED_MARKER} after 30s\n"
    assert detect_validation_budget_exhausted(text)
    info = classify_validation_output(text + _PARTIAL_PYTEST_OUTPUT)
    assert info["category"] == CATEGORY_VALIDATION_BUDGET_EXHAUSTED


@pytest.mark.parametrize(
    "output, expected",
    [
        ("E       AssertionError: 1 != 2", "assertion_failure"),
        ("ModuleNotFoundError: No module named 'x'", "import_error"),
        ("  File \"a.py\", line 2\nSyntaxError: invalid syntax", "syntax_error"),
        ("FAILED tests/test_a.py::test_b\n1 failed, 3 passed", "assertion_failure"),
        ("collected 12 items\n1 failed, 11 passed", "test_failure"),
    ],
)
def test_ordinary_classification_is_untouched(output, expected):
    """§15: not every non-zero or unfinished-looking result is inconclusive."""
    assert classify_validation_output(output)["category"] == expected
    assert is_executed_failure_evidence(expected)


# ══════════════════════════════════════════════════════════════════════════════
# 3. The runners — a timeout is an attempted validation that did not complete
# ══════════════════════════════════════════════════════════════════════════════

def test_safe_runner_reports_attempt_budget_and_timeout(tmp_path):
    root = _sleeper_repo(tmp_path / "repo")
    result = run_safe_validation_command(_safe_sleeper(root))

    # command selected / attempted / not completed
    assert result.blocked is False, "the command was not refused, it was run"
    assert result.timed_out is True
    assert result.ok is False
    assert result.exit_code is None, "an unfinished command has no exit code"
    assert result.timeout_sec == 1
    assert VALIDATION_BUDGET_EXHAUSTED_MARKER in result.output.lower()


def test_legacy_runner_reports_attempt_budget_and_timeout(tmp_path):
    root = _sleeper_repo(tmp_path / "repo")
    run = run_validation_command_detailed(
        "python slow_validation.py", cwd=str(root), timeout=1
    )
    assert run.timed_out is True
    assert run.ok is False
    assert run.timeout_seconds == 1
    assert detect_validation_budget_exhausted(run.output)


def test_timeout_is_not_represented_as_validation_not_run(tmp_path):
    """§3: the command DID run.  It simply did not finish."""
    root = _sleeper_repo(tmp_path / "repo")
    result = run_safe_validation_command(_safe_sleeper(root))
    facts = {
        "command_selected": bool(result.command),
        "command_attempted": not result.blocked,
        "command_completed": result.exit_code is not None,
        "timed_out": result.timed_out,
    }
    assert facts == {
        "command_selected": True,
        "command_attempted": True,
        "command_completed": False,
        "timed_out": True,
    }


def test_timeout_leaves_no_validation_subprocess_running(tmp_path):
    """§30: termination is bounded — the runner returns, it does not detach."""
    root = _sleeper_repo(tmp_path / "repo")
    result = run_safe_validation_command(_safe_sleeper(root))
    assert result.timed_out is True
    # subprocess.run kills and reaps before re-raising TimeoutExpired; if it had
    # not, this second identical run would contend with a live 30s child.
    again = run_safe_validation_command(_safe_sleeper(root))
    assert again.timed_out is True


# ══════════════════════════════════════════════════════════════════════════════
# 4. Preflight — §9
# ══════════════════════════════════════════════════════════════════════════════

def test_preflight_timeout_is_inconclusive_and_yields_no_defect_locations(
    tmp_path, monkeypatch
):
    root = _sleeper_repo(tmp_path / "repo")
    monkeypatch.setattr(
        "core.preflight.run_validation_command_detailed",
        lambda command, cwd, **kw: run_validation_command_detailed(
            command, cwd=cwd, timeout=1
        ),
    )
    report = run_preflight_validation(
        str(root), "python", command="python slow_validation.py"
    )

    assert report["ran"] is True, "the command was attempted"
    assert report["ok"] is False
    assert report["outcome"] == VALIDATION_INCONCLUSIVE
    assert report["category"] == CATEGORY_VALIDATION_BUDGET_EXHAUSTED
    assert report["timed_out"] is True
    assert report["timeout_seconds"] == 1
    assert report["validation_budget_exhausted"] is True
    # A validation that established nothing has no defect locations to give.
    assert report["locations"] == []


def test_preflight_timeout_cannot_ground_a_defect(tmp_path, monkeypatch):
    """§7: the shared predicate, not a copied category list, is what refuses."""
    root = _sleeper_repo(tmp_path / "repo")
    monkeypatch.setattr(
        "core.preflight.run_validation_command_detailed",
        lambda command, cwd, **kw: run_validation_command_detailed(
            command, cwd=cwd, timeout=1
        ),
    )
    preflight = run_preflight_validation(
        str(root), "python", command="python slow_validation.py"
    )

    genuine_failure = bool(
        preflight.get("ran")
        and preflight.get("ok") is False
        and is_executed_failure_evidence(preflight.get("category"))
    )
    compiler_grounded = bool(
        preflight.get("ran")
        and preflight.get("ok") is False
        and is_compiler_grounded_category(preflight.get("category"))
    )
    assert genuine_failure is False
    assert compiler_grounded is False


def test_preflight_reports_bytecode_isolation(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _write(root, "solution.py", "def add(a, b):\n    return a + b\n")
    _write(root, "tests/test_solution.py", "def test_ok():\n    assert True\n")
    report = run_preflight_validation(str(root), "python")
    assert report["python_bytecode_cache_isolated"] is True
    assert report["timed_out"] is False


# ══════════════════════════════════════════════════════════════════════════════
# 4b. CONTROL / PATCH.BASIS — §7, §8, §9
# ══════════════════════════════════════════════════════════════════════════════

def _timed_out_preflight(root: Path) -> dict:
    """A real preflight run whose command exhausts a one-second budget.

    Real, not hand-built: the point is that the *production* path produces
    something CONTROL then refuses to ground on.
    """
    import core.preflight as preflight_mod

    original = preflight_mod.run_validation_command_detailed
    preflight_mod.run_validation_command_detailed = (
        lambda command, cwd, **kw: run_validation_command_detailed(
            command, cwd=cwd, timeout=1
        )
    )
    try:
        return run_preflight_validation(
            str(root), "python", command="python slow_validation.py"
        )
    finally:
        preflight_mod.run_validation_command_detailed = original


def test_defect_task_with_timed_out_baseline_gets_no_grounded_defect(tmp_path):
    """§7: a budget that ran out is not a defect somebody proved."""
    from core.live_task_routing import route_live_task
    from core.patch_basis import PATCH_BASIS_GROUNDED_DEFECT
    from core import control_engine

    root = tmp_path / "repo"
    root.mkdir()
    (root / "calc.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )
    (root / "slow_validation.py").write_text(_SLEEPER, encoding="utf-8", newline="")
    preflight = _timed_out_preflight(root)
    assert preflight["category"] == CATEGORY_VALIDATION_BUDGET_EXHAUSTED

    control = {
        "repo_path": str(root),
        "query": "add returns the wrong value",
        "top_hypothesis": {"symbol": "calc.py::add", "score": 100.0, "confidence": 0.99},
        "hypotheses": [
            {
                "symbol": "calc.py::add",
                "score": 100.0,
                "confidence": 0.99,
                "reasons": ["fixture"],
                "called_by": [],
                "calls": [],
            }
        ],
        "evidence": [],
        "execution_trace": "",
        "related_snippets": [],
        "live_route": route_live_task(
            "add returns the wrong value; fix this bug", repository_available=True
        ).as_dict(),
        "preflight_validation": preflight,
    }
    control_engine.refresh_control_safety(control)

    state = control["patch_candidate_state"]
    assert state["patch_basis"] != PATCH_BASIS_GROUNDED_DEFECT
    # §8: no executed-failure grounding, and no failure location bound.
    assert control.get("grounded_hypothesis") is None
    assert not control.get("defect_evidence")
    assert state["write_authority"] is False


def test_explicit_change_request_survives_a_timed_out_baseline(tmp_path):
    """§9: feature intent does not depend on baseline failure."""
    from core.live_task_routing import route_live_task
    from core.patch_basis import PATCH_BASIS_EXPLICIT_CHANGE_REQUEST
    from core import control_engine

    root = tmp_path / "repo"
    root.mkdir()
    (root / "models.py").write_text(
        "class Task:\n    def __init__(self, title):\n        self.title = title\n",
        encoding="utf-8",
    )
    (root / "slow_validation.py").write_text(_SLEEPER, encoding="utf-8", newline="")
    preflight = _timed_out_preflight(root)
    assert preflight["outcome"] == VALIDATION_INCONCLUSIVE

    control = {
        "repo_path": str(root),
        "query": "add task priority support",
        "top_hypothesis": {
            "symbol": "models.py::Task",
            "score": 100.0,
            "confidence": 0.99,
        },
        "hypotheses": [
            {
                "symbol": "models.py::Task",
                "score": 100.0,
                "confidence": 0.99,
                "reasons": ["fixture"],
                "called_by": [],
                "calls": [],
            }
        ],
        "evidence": [],
        "execution_trace": "",
        "related_snippets": [],
        "live_route": route_live_task(
            "Add task priority support across model/store/CLI.",
            repository_available=True,
        ).as_dict(),
        "preflight_validation": preflight,
    }
    control_engine.refresh_control_safety(control)

    state = control["patch_candidate_state"]
    assert state["patch_basis"] == PATCH_BASIS_EXPLICIT_CHANGE_REQUEST
    # The explicit change request is not erased, and it is still not authority.
    assert state["write_authority"] is False


# ══════════════════════════════════════════════════════════════════════════════
# 5. Post-patch timeout + rollback — §10
# ══════════════════════════════════════════════════════════════════════════════

def _patchable_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir(parents=True, exist_ok=True)
    _write(root, "calc.py", "def sub(a, b):\n    return a - b\n")
    _write(root, "slow_validation.py", _SLEEPER)
    return root


def test_plan_post_patch_timeout_is_inconclusive_and_rolls_back(tmp_path):
    root = _patchable_repo(tmp_path)
    original = (root / "calc.py").read_bytes()

    result = apply_patch_plan(
        str(root),
        [
            {
                "op": "replace_snippet",
                "file": "calc.py",
                "target_snippet": "return a - b",
                "patched_snippet": "return a + b",
            }
        ],
        safe_validation_command=_safe_sleeper(root),
    )

    assert result["success"] is False
    assert result["validation_outcome"] == VALIDATION_INCONCLUSIVE
    assert result["validation_info"]["category"] == CATEGORY_VALIDATION_BUDGET_EXHAUSTED
    assert result["validation_timed_out"] is True
    assert result["validation_timeout_seconds"] == 1
    assert result["rollback_performed"] is True
    # OPS.PATCH.1 byte fidelity survives an inconclusive outcome.
    assert (root / "calc.py").read_bytes() == original


def test_executor_post_patch_timeout_is_environment_failure_and_rolls_back(
    tmp_path, monkeypatch
):
    import core.executor as executor_mod

    root = _patchable_repo(tmp_path)
    original = (root / "calc.py").read_bytes()

    # The real production runner, on a one-second budget instead of thirty, so
    # this is a genuine subprocess timeout the suite does not have to wait for.
    monkeypatch.setattr(
        executor_mod,
        "run_validation_command_detailed",
        lambda command, cwd, **kw: run_validation_command_detailed(
            command, cwd=cwd, timeout=1
        ),
    )

    result = Executor(str(root)).run(
        {
            "file": "calc.py",
            "relative_path": "calc.py",
            "target_snippet": "def sub(a, b):\n    return a - b\n",
            "patched_snippet": "def sub(a, b):\n    return a + b\n",
            "target_node_name": "sub",
            "target_node_kind": "function",
        },
        language="python",
        validation_command="python slow_validation.py",
    )

    assert result.success is False
    assert result.validation_outcome == VALIDATION_INCONCLUSIVE
    assert result.phase == "validation_environment_failed"
    assert result.failure_info["category"] == CATEGORY_VALIDATION_BUDGET_EXHAUSTED
    assert result.rollback_performed is True
    assert (root / "calc.py").read_bytes() == original


def test_exec_auth_projects_timeout_as_inconclusive_and_rolled_back(tmp_path):
    """§13: EXEC.AUTH.LIVE.1 inherits the truthful validation fact unchanged."""
    from core.execution_outcome_telemetry import (
        APPLICATION_ROLLED_BACK,
        AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY,
        OBSERVATION_UNAVAILABLE,
        FinalStateObservation,
        authorized_execution,
        plan_execution_receipt,
    )

    root = _patchable_repo(tmp_path)
    result = apply_patch_plan(
        str(root),
        [
            {
                "op": "replace_snippet",
                "file": "calc.py",
                "target_snippet": "return a - b",
                "patched_snippet": "return a + b",
            }
        ],
        safe_validation_command=_safe_sleeper(root),
    )
    receipt = plan_execution_receipt(result)
    telemetry = authorized_execution(
        authority_source=AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY,
        receipt=receipt,
        observation=FinalStateObservation(scope=OBSERVATION_UNAVAILABLE),
    )

    assert telemetry.execution_authorized is True
    assert telemetry.execution_attempted is True
    assert telemetry.mutation_observed is True
    assert telemetry.final_validation_outcome == VALIDATION_INCONCLUSIVE
    assert telemetry.rollback_performed is True
    assert telemetry.application_status == APPLICATION_ROLLED_BACK
    assert telemetry.patch_applied is False
    assert telemetry.final_repository_changed is False


# ══════════════════════════════════════════════════════════════════════════════
# 6. Sandbox candidate timeout — §11
# ══════════════════════════════════════════════════════════════════════════════

def test_sandbox_candidate_timeout_is_inconclusive_and_not_approval_ready(
    tmp_path, monkeypatch
):
    import patching.patch_plan_executor as ppe
    from core.candidate_sandbox_validation import validate_candidate_in_sandbox

    root = _patchable_repo(tmp_path)
    real_apply = ppe.apply_patch_plan

    def _timed_out_apply(sandbox_root, operations, validation_command=None, **kw):
        """Same production primitive, forced onto the one-second budget."""
        return real_apply(
            sandbox_root,
            operations,
            safe_validation_command=SafeValidationCommand(
                command=["python", "slow_validation.py"],
                cwd=str(sandbox_root),
                timeout_sec=1,
            ),
        )

    monkeypatch.setattr(ppe, "apply_patch_plan", _timed_out_apply)

    outcome = validate_candidate_in_sandbox(
        str(root),
        [
            {
                "op": "replace_snippet",
                "file": "calc.py",
                "target_snippet": "return a - b",
                "patched_snippet": "return a + b",
            }
        ],
        validation_command="python slow_validation.py",
    )

    assert outcome.status == VALIDATION_INCONCLUSIVE
    assert outcome.status != VALIDATION_FAILED
    assert outcome.status != VALIDATION_PASSED
    assert outcome.approval_ready is False
    # The real repository was never touched.
    assert (root / "calc.py").read_bytes() == b"def sub(a, b):\n    return a - b\n"


# ══════════════════════════════════════════════════════════════════════════════
# 7. CHECK.LIVE projection — §12
# ══════════════════════════════════════════════════════════════════════════════

def test_check_live_projects_timeout_through_frozen_vocabulary():
    result = live_validation_result(
        executed=True, passed=False, timed_out=True, inconclusive=True
    )
    assert result == RECEIPT_TIMED_OUT
    assert result in RECEIPT_RESULTS, "CHECK.1 vocabulary is not extended"
    assert result != RECEIPT_PASSED
    assert result != RECEIPT_FAILED


def test_lifecycle_reads_the_typed_timeout_fact_without_reclassifying():
    facts = _shadow_validation_facts(
        {
            "validation_ok": False,
            "validation_outcome": VALIDATION_INCONCLUSIVE,
            "validation_timed_out": True,
            "failed_op": {
                "op": "validation",
                "category": CATEGORY_VALIDATION_BUDGET_EXHAUSTED,
            },
        }
    )
    assert facts["validation_executed"] is True
    assert facts["validation_timed_out"] is True
    assert facts["validation_inconclusive"] is True
    assert facts["validation_passed"] is False
    assert facts["validation_crashed"] is False


def test_live_run_emits_a_timed_out_receipt_end_to_end(tmp_path, monkeypatch):
    """The whole wire: apply -> post-patch timeout -> CHECK.LIVE receipt."""
    import core.run_lifecycle as run_lifecycle
    from core.post_run_reconciliation_shadow import ENVIRONMENT_FLAG

    root = _patchable_repo(tmp_path)
    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    monkeypatch.setattr(
        run_lifecycle,
        "collect_brain_stamp",
        lambda repo: {"brain_stamp_id": "stamp", "schema_version": 2},
    )

    result = run_lifecycle.run_patch_plan_with_artifacts(
        str(root),
        [
            {
                "op": "replace_snippet",
                "file": "calc.py",
                "target_snippet": "return a - b",
                "patched_snippet": "return a + b",
            }
        ],
        safe_validation_command=_safe_sleeper(root),
        source="unit",
    )

    assert result["validation_outcome"] == VALIDATION_INCONCLUSIVE
    assert result["validation_timed_out"] is True
    assert result["rollback_performed"] is True

    from core.post_run_reconciliation_shadow import SHADOW_ARTIFACT_NAME

    receipt = json.loads(
        (Path(result["replay_dir"]) / SHADOW_ARTIFACT_NAME).read_text(
            encoding="utf-8"
        )
    )
    # CHECK.1's frozen `timed_out`, not a bare `errored` and never `failed`.
    assert receipt["observation"]["validation_receipt_result"] == RECEIPT_TIMED_OUT
    assert receipt["authoritative_effect"] is False


def test_lifecycle_timeout_fact_is_false_without_one():
    facts = _shadow_validation_facts(
        {"validation_ok": False, "validation_outcome": VALIDATION_FAILED}
    )
    assert facts["validation_timed_out"] is False


# ══════════════════════════════════════════════════════════════════════════════
# 8. Normal validation is unchanged — §15, §16
# ══════════════════════════════════════════════════════════════════════════════

def test_real_pass_remains_passed(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _write(root, "solution.py", "def add(a, b):\n    return a + b\n")
    _write(
        root,
        "tests/test_solution.py",
        "from solution import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
    )
    report = run_preflight_validation(str(root), "python")
    assert report["outcome"] == VALIDATION_PASSED
    assert report["ok"] is True
    assert report["timed_out"] is False


def test_real_assertion_failure_remains_failed(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _write(root, "solution.py", "def add(a, b):\n    return a - b\n")
    _write(
        root,
        "tests/test_solution.py",
        "from solution import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
    )
    report = run_preflight_validation(str(root), "python")
    assert report["outcome"] == VALIDATION_FAILED
    assert report["category"] in {"assertion_failure", "test_failure"}
    assert report["timed_out"] is False
    assert is_executed_failure_evidence(report["category"])


def test_zero_tests_remains_inconclusive(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _write(root, "solution.py", "def add(a, b):\n    return a + b\n")
    _write(root, "tests/test_solution.py", "# no tests here\n")
    report = run_preflight_validation(str(root), "python")
    assert report["outcome"] == VALIDATION_INCONCLUSIVE
    assert report["category"] == CATEGORY_NO_TESTS_COLLECTED
    assert report["category"] != CATEGORY_VALIDATION_BUDGET_EXHAUSTED


def test_tool_unavailable_remains_inconclusive():
    info = classify_validation_output("No module named pytest")
    assert info["category"] == CATEGORY_VALIDATION_TOOL_UNAVAILABLE
    assert validation_outcome(category=info["category"], ok=False) == (
        VALIDATION_INCONCLUSIVE
    )


# ══════════════════════════════════════════════════════════════════════════════
# 9. Bytecode freshness — §17-§22
# ══════════════════════════════════════════════════════════════════════════════

_MODULE_A = b'def f():\n    return "A"\n'
_MODULE_B = b'def f():\n    return "B"\n'


def _stale_pyc_repo(root: Path) -> Path:
    """A repository whose ``__pycache__`` holds bytecode for the OLD source.

    Built the only honest way: run once so the interpreter caches ``"A"``, then
    replace the source with same-size ``"B"`` bytes and restore the original
    mtime.  Both halves of CPython's timestamp+size validity condition then
    still hold for the cached file.
    """
    root.mkdir(parents=True, exist_ok=True)
    module = root / "mod.py"
    module.write_bytes(_MODULE_A)
    _write(
        root,
        "tests/test_mod.py",
        "import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
        "import mod\n\n\n"
        'def test_observes_current_source():\n    assert mod.f() == "B"\n',
    )
    # Populate the repository cache for source state "A".
    subprocess.run(
        [sys.executable, "-c", "import mod"],
        cwd=str(root),
        capture_output=True,
    )
    before = module.stat()
    module.write_bytes(_MODULE_B)
    os.utime(module, (before.st_atime, before.st_mtime))
    after = module.stat()
    assert after.st_size == before.st_size, "the fixture must be same-size"
    assert after.st_mtime == before.st_mtime, "the fixture must be same-mtime"
    return root


def test_fixture_really_reproduces_the_stale_pyc_defect(tmp_path):
    """Without isolation the interpreter genuinely executes the old bytecode."""
    root = _stale_pyc_repo(tmp_path / "repo")
    assert (root / "__pycache__").is_dir(), "no cache means nothing to be stale"
    stale = subprocess.run(
        [sys.executable, "-c", "import mod; print(mod.f())"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert stale.stdout.strip() == "A", (
        "this platform did not reproduce the defect; the rest of this section "
        "would then prove nothing"
    )


def test_dont_write_bytecode_does_not_fix_stale_reads(tmp_path):
    """§19, verified rather than assumed: -B stops writes, not reads."""
    root = _stale_pyc_repo(tmp_path / "repo")
    result = subprocess.run(
        [sys.executable, "-B", "-c", "import mod; print(mod.f())"],
        cwd=str(root),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.stdout.strip() == "A", (
        "-B must NOT be treated as a freshness mechanism"
    )


def test_safe_runner_observes_same_size_same_timestamp_patch(tmp_path):
    """§22 through the real production subprocess environment."""
    root = _stale_pyc_repo(tmp_path / "repo")
    result = run_safe_validation_command(
        SafeValidationCommand(
            command=["python", "-m", "pytest", "-q", "tests/test_mod.py"],
            cwd=str(root),
            timeout_sec=120,
        )
    )
    assert result.ok is True, result.output
    assert result.python_bytecode_cache_isolated is True


def test_legacy_runner_observes_same_size_same_timestamp_patch(tmp_path):
    root = _stale_pyc_repo(tmp_path / "repo")
    run = run_validation_command_detailed(
        "python -m pytest -q tests/test_mod.py", cwd=str(root), timeout=120
    )
    assert run.ok is True, run.output
    assert run.python_bytecode_cache_isolated is True


def test_preflight_observes_same_size_same_timestamp_patch(tmp_path):
    root = _stale_pyc_repo(tmp_path / "repo")
    report = run_preflight_validation(str(root), "python")
    assert report["outcome"] == VALIDATION_PASSED, report["output"]


# ══════════════════════════════════════════════════════════════════════════════
# 10. Patch → validate, rollback → validate, sandbox — §23, §24, §25
# ══════════════════════════════════════════════════════════════════════════════

def _same_size_patch_repo(root: Path) -> Path:
    """Baseline ``a - b``, validated once, ready for a same-size ``a + b``."""
    root.mkdir(parents=True, exist_ok=True)
    calc = root / "calc.py"
    calc.write_bytes(b"def op(a, b):\n    return a - b\n")
    _write(
        root,
        "tests/test_calc.py",
        "import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
        "from calc import op\n\n\n"
        "def test_op():\n    assert op(3, 1) == 4\n",
    )
    return root


def test_post_patch_validation_executes_the_patched_source(tmp_path):
    """§23: baseline → same-size patch → validate sees the patch."""
    root = _same_size_patch_repo(tmp_path / "repo")
    calc = root / "calc.py"

    # Baseline validation: fails, and caches bytecode for `a - b`.
    baseline = run_preflight_validation(str(root), "python")
    assert baseline["outcome"] == VALIDATION_FAILED

    before = calc.stat()
    result = apply_patch_plan(
        str(root),
        [
            {
                "op": "replace_snippet",
                "file": "calc.py",
                "target_snippet": "return a - b",
                "patched_snippet": "return a + b",
            }
        ],
        validation_command="python -m pytest -q",
    )
    # Force the adversarial timestamp: same size, same whole-second mtime.
    assert calc.stat().st_size == before.st_size
    os.utime(calc, (before.st_atime, before.st_mtime))

    assert result["success"] is True, result.get("error") or result.get("validation_output")
    assert result["validation_ok"] is True
    assert calc.read_bytes() == b"def op(a, b):\n    return a + b\n"

    # And an independent later validation still sees the patched source.
    after = run_preflight_validation(str(root), "python")
    assert after["outcome"] == VALIDATION_PASSED, after["output"]


def test_validation_after_rollback_observes_the_restored_source(tmp_path):
    """§24: rollback restores exact bytes, and validation then sees them."""
    root = _same_size_patch_repo(tmp_path / "repo")
    calc = root / "calc.py"
    original = calc.read_bytes()

    _write(root, "slow_validation.py", _SLEEPER)
    result = apply_patch_plan(
        str(root),
        [
            {
                "op": "replace_snippet",
                "file": "calc.py",
                "target_snippet": "return a - b",
                "patched_snippet": "return a + b",
            }
        ],
        safe_validation_command=_safe_sleeper(root),
    )
    assert result["rollback_performed"] is True
    assert result["validation_outcome"] == VALIDATION_INCONCLUSIVE
    assert calc.read_bytes() == original

    # The temporary patched source may have produced bytecode; validation must
    # not run against it.  `a - b` fails the test, so a stale `a + b` cache
    # would show up as a pass.
    after = run_preflight_validation(str(root), "python")
    assert after["outcome"] == VALIDATION_FAILED, after["output"]


def test_sandbox_candidate_validation_uses_the_freshness_guarantee(tmp_path):
    """§25: no candidate verdict may rest on bytecode from the copied state."""
    from core.candidate_sandbox_validation import validate_candidate_in_sandbox

    root = _same_size_patch_repo(tmp_path / "repo")
    # Seed the source repository's own cache for the *baseline* `a - b`, so the
    # sandbox copy carries bytecode built for the state before the candidate.
    # Seeded directly rather than through production validation, because
    # production validation no longer writes into the repository at all.
    subprocess.run(
        [sys.executable, "-c", "import calc"],
        cwd=str(root),
        capture_output=True,
    )
    assert (root / "__pycache__").is_dir()

    outcome = validate_candidate_in_sandbox(
        str(root),
        [
            {
                "op": "replace_snippet",
                "file": "calc.py",
                "target_snippet": "return a - b",
                "patched_snippet": "return a + b",
            }
        ],
        validation_command="python -m pytest -q",
    )
    assert outcome.status == VALIDATION_PASSED, outcome.output_excerpt
    assert outcome.approval_ready is True


def test_worker_queue_validation_observes_the_current_source(tmp_path):
    """The proposal-queue runner reaches production through core.worker_runs.

    It validates in a temp clone that carries the source repository's
    ``__pycache__`` with it, so it needs the same guarantee — a same-size
    candidate must not be judged against the bytecode of the state before it.
    """
    from scripts.run_patch_proposal_queue import _run_validation_command

    root = _stale_pyc_repo(tmp_path / "repo")
    result = _run_validation_command(
        "python -m pytest -q tests/test_mod.py", cwd=root, timeout_sec=120
    )
    assert result["validation_ok"] is True, result["output"]
    # And the repository's own cache is still there, untouched.
    assert (root / "__pycache__").is_dir()


# ══════════════════════════════════════════════════════════════════════════════
# 11. What the freshness mechanism refuses to do — §26, §28, §29, §30
# ══════════════════════════════════════════════════════════════════════════════

def test_repository_caches_are_never_deleted(tmp_path):
    root = _stale_pyc_repo(tmp_path / "repo")
    cache_dir = root / "__pycache__"
    before = sorted(p.name for p in cache_dir.iterdir())
    assert before, "fixture must have produced a cache"

    run_validation_command_detailed(
        "python -m pytest -q tests/test_mod.py", cwd=str(root), timeout=120
    )

    assert cache_dir.is_dir(), "the repository cache directory was removed"
    assert sorted(p.name for p in cache_dir.iterdir()) == before


def test_validation_bytecode_lands_outside_the_repository(tmp_path):
    root = _same_size_patch_repo(tmp_path / "repo")
    observed: list[str] = []

    import core.validation_bytecode_cache as cache_mod

    real_create = cache_mod.create_validation_bytecode_cache_dir

    def _spy():
        path = real_create()
        observed.append(path)
        return path

    cache_mod.create_validation_bytecode_cache_dir = _spy
    try:
        run_validation_command_detailed(
            "python -m pytest -q", cwd=str(root), timeout=120
        )
    finally:
        cache_mod.create_validation_bytecode_cache_dir = real_create

    assert observed and observed[0]
    prefix = Path(observed[0])
    assert prefix.name.startswith(VALIDATION_PYCACHE_DIR_PREFIX)
    with pytest.raises(ValueError):
        prefix.relative_to(root)
    # …and it is gone again afterwards.
    assert not prefix.exists()


def test_temp_cache_is_cleaned_up_after_a_timeout(tmp_path):
    """§30: an exhausted budget cleans up exactly like a completed run."""
    root = _sleeper_repo(tmp_path / "repo")
    observed: list[str] = []

    import core.validation_bytecode_cache as cache_mod

    real_create = cache_mod.create_validation_bytecode_cache_dir

    def _spy():
        path = real_create()
        observed.append(path)
        return path

    cache_mod.create_validation_bytecode_cache_dir = _spy
    try:
        result = run_safe_validation_command(_safe_sleeper(root))
    finally:
        cache_mod.create_validation_bytecode_cache_dir = real_create

    assert result.timed_out is True
    assert observed and not Path(observed[0]).exists()


def test_cache_helper_refuses_to_delete_anything_it_did_not_create(tmp_path):
    outsider = tmp_path / "not-ours"
    outsider.mkdir()
    (outsider / "keep.txt").write_text("keep", encoding="utf-8")

    assert discard_validation_bytecode_cache_dir(str(outsider)) is False
    assert (outsider / "keep.txt").exists()

    # An empty path is "nothing to remove", not an error.
    assert discard_validation_bytecode_cache_dir("") is True
    assert discard_validation_bytecode_cache_dir(None) is True


def test_cache_helper_creates_and_removes_its_own_directory():
    path = create_validation_bytecode_cache_dir()
    assert path
    directory = Path(path)
    assert directory.is_dir()
    assert directory.name.startswith(VALIDATION_PYCACHE_DIR_PREFIX)
    assert Path(tempfile.gettempdir()).resolve() in directory.resolve().parents
    assert discard_validation_bytecode_cache_dir(path) is True
    assert not directory.exists()


def test_context_manager_cleans_up_on_exception():
    seen = ""
    with pytest.raises(RuntimeError):
        with validation_bytecode_cache() as prefix:
            seen = prefix
            raise RuntimeError("boom")
    assert seen and not Path(seen).exists()


def test_freshness_costs_zero_repository_traversal():
    """§28: the mechanism never walks the repository looking for caches."""
    source = Path("core/validation_bytecode_cache.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "rglob" not in called
    assert "glob" not in called
    assert "walk" not in called
    assert "iterdir" not in called
    # rmtree exists, but only behind the ownership guard tested above.
    assert "rmtree" in called


def test_production_validation_modules_never_remove_repository_caches():
    """§26/§28: no production validation path deletes or hunts for caches.

    The claim is about *calls*, not about words: ``core/validator.py`` has
    always named ``__pycache__`` in its source-scan skip list, and that is a
    directory it declines to read, not one it removes.
    """
    for relative in (
        "core/validator.py",
        "core/validation_execution.py",
        "core/validation_bytecode_cache.py",
        "core/preflight.py",
        "core/executor.py",
        "patching/patch_plan_executor.py",
    ):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        if relative != "core/validation_bytecode_cache.py":
            # Only the freshness module may remove anything at all, and only
            # its own temp directory, behind the ownership guard.
            assert not (called & {"rmtree", "rmdir"}), (
                f"{relative} removes directories"
            )
        # Nobody hunts the repository for caches.  (Pre-existing rglob use in
        # the language detectors is OPS.VALIDATE.1's, pinned there and about
        # source files, not bytecode; what must not exist is a cache hunt.)
        for token in ("__pycache__", ".pytest_cache", "*.pyc"):
            assert f'rglob("{token}")' not in source
            assert f"rglob('{token}')" not in source
            assert f'glob("{token}")' not in source


def test_guarantees_are_bounded_and_path_free():
    guarantees = validation_bytecode_cache_guarantees()
    assert guarantees["repository_pycache_deleted"] is False
    assert guarantees["repository_traversed"] is False
    assert guarantees["source_files_mutated"] is False
    assert guarantees["fresh_cache_per_validation_execution"] is True
    assert all(isinstance(value, bool) for value in guarantees.values())


# ══════════════════════════════════════════════════════════════════════════════
# 12. Non-Python validation is unchanged — §21
# ══════════════════════════════════════════════════════════════════════════════

def test_typescript_command_selection_is_unchanged(tmp_path):
    from core.validation_command import detect_typescript_validation_command

    root = tmp_path / "ts"
    root.mkdir()
    _write(root, "tsconfig.json", "{}\n")
    _write(
        root,
        "package.json",
        '{"scripts": {"test": "vitest run", "build": "tsc"}}\n',
    )
    assert detect_typescript_validation_command(root) == "npm run test"


def test_node_validation_is_not_given_a_python_specific_branch(tmp_path):
    root = tmp_path / "node"
    root.mkdir()
    _write(root, "check.js", "process.exit(0);\n")
    result = run_safe_validation_command(
        SafeValidationCommand(
            command=["node", "check.js"], cwd=str(root), timeout_sec=60
        )
    )
    if result.blocked or "not recognized" in result.output.lower():
        pytest.skip("node is not available in this environment")
    assert result.ok is True
    # The Python cache variable is inherited harmlessly; nothing else changed.
    assert result.python_bytecode_cache_isolated is True


# ══════════════════════════════════════════════════════════════════════════════
# 13. Budget policy — §5, §6
# ══════════════════════════════════════════════════════════════════════════════

def test_default_validation_budget_was_not_raised():
    """§5: truthful classification, not a bigger global timeout."""
    import inspect

    from core.validator import run_validation_command, run_validation_command_detailed

    for function in (run_validation_command, run_validation_command_detailed):
        assert (
            inspect.signature(function).parameters["timeout"].default == 30
        ), "the global validation budget must stay where it was"


def test_explicit_timeout_override_still_works(tmp_path):
    """§6: one timeout system, and the existing override is preserved."""
    root = _sleeper_repo(tmp_path / "repo")
    run = run_validation_command_detailed(
        "python slow_validation.py", cwd=str(root), timeout=1
    )
    assert run.timeout_seconds == 1
    assert run.timed_out is True

    command = SafeValidationCommand(
        command=["python", "slow_validation.py"], cwd=str(root), timeout_sec=2
    )
    assert command.timeout_sec == 2
