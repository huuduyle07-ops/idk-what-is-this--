"""EXEC.AUTH.LIVE.1 — execution authorization and outcome telemetry regressions.

The field-test regression this file exists for is concrete: T1/T2/T3 rewrote
repository files, validation passed, the bytes stayed on disk, and the payload
handed to the operator still read ``write_authority=false``,
``patch_application_authority=false``, ``human_approval_required=true`` and
nothing at all about whether a patch had been applied.

So the tests below are organised around the three subjects that were being
conflated, and around the collapses that must stay impossible: authorization is
not application, application is not persistence, and neither sandbox validation
nor patch basis nor model confidence is authorization.
"""

from __future__ import annotations

import ast
import inspect
import json
import shutil
from pathlib import Path

import pytest

from core import control_engine, pipeline
from core.agent_state import AgentState
from core.candidate_sandbox_validation import CANDIDATE_VALIDATION_PASSED
from core.execution_outcome_telemetry import (
    APPLICATION_APPLIED,
    APPLICATION_FAILED,
    APPLICATION_NOT_ATTEMPTED,
    APPLICATION_NO_OP,
    APPLICATION_ROLLED_BACK,
    AUTHORITY_SCOPE_CONTROL_OR_PLANNING,
    AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY,
    AUTHORITY_SOURCE_LOW_RISK_SINGLE_FILE,
    AUTHORITY_SOURCE_MANUAL_APPLY,
    AUTHORITY_SOURCE_NONE,
    DENIED_AUTO_PATCH_DISABLED,
    DENIED_HUMAN_APPROVAL_REQUIRED,
    DENIED_NO_CHANGE_REQUESTED,
    DENIED_NO_PATCH_BASIS_HANDOFF,
    DENIED_NOT_APPLICABLE,
    DENIED_PATCH_SAFETY_BLOCKED,
    EXECUTION_AUTHORITY_SOURCES,
    EXECUTION_DENIAL_REASONS,
    EXECUTION_TELEMETRY_KEYS,
    FINAL_VALIDATION_NOT_RUN,
    OBSERVATION_INCOMPLETE,
    OBSERVATION_NOT_ATTEMPTED,
    OBSERVATION_PLAN_NAMED_PATHS,
    OBSERVATION_UNAVAILABLE,
    ExecutionReceipt,
    ExecutionTelemetry,
    ExecutionTelemetryError,
    FinalStateObservation,
    attach_execution_telemetry,
    authorized_execution,
    execution_telemetry_guardrails,
    final_state_observation,
    no_execution,
    observe_named_paths,
    plan_execution_receipt,
    single_file_execution_receipt,
)
from core.live_task_routing import route_live_task
from core.rollback_outcome import rollback_completed_verified
from core.patch_basis import (
    PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
    PATCH_BASIS_GROUNDED_DEFECT,
)
from core.postprocess_gates import run_postprocess_gate_battery
from core.preflight import run_preflight_validation
from core.validation_outcome import (
    VALIDATION_FAILED,
    VALIDATION_INCONCLUSIVE,
    VALIDATION_PASSED,
)


# ── Fixture plumbing, shared with the PATCH.BASIS / OPS.PATCH.2 harnesses ────

def _write(repo: Path, relative: str, text: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


_IGNORED_SNAPSHOT_PARTS = {".agent", "__pycache__", ".pytest_cache"}


def _clear_bytecode_cache(repo: Path) -> None:
    """Drop the bytecode preflight left behind, before the patch is applied.

    CPython validates a cached ``.pyc`` against the source's *mtime and size*.
    These fixtures patch ``return a - b`` into ``return a + b`` — identical in
    size, and written within the same mtime tick as the preflight run that
    compiled the buggy version — so the validation run can import the stale
    bytecode and "fail" against code that is no longer on disk.  That is an
    artefact of a millisecond-scale test, not of the apply path, so it is
    removed here rather than worked around in an assertion.
    """
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def _snapshot(repo: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(repo)): path.read_bytes()
        for path in sorted(repo.rglob("*"))
        if path.is_file() and not (_IGNORED_SNAPSHOT_PARTS & set(path.parts))
    }


def _defect_route(text: str = "add returns the wrong value; fix this bug") -> dict:
    return route_live_task(text, repository_available=True).as_dict()


def _analysis_route() -> dict:
    return route_live_task(
        "How does the retrieval layer decide which files to read?",
        repository_available=True,
    ).as_dict()


def _feature_route() -> dict:
    return route_live_task(
        "Add task priority support across model/store/CLI.",
        repository_available=True,
    ).as_dict()


def _control(
    repo: Path,
    symbols: list[str],
    *,
    route: dict | None = None,
    preflight: dict | None = None,
    related_files: list[str] | None = None,
) -> dict:
    hypotheses = [
        {
            "symbol": symbol,
            "score": float(100 - index),
            "confidence": 0.99,
            "reasons": ["test navigation fixture"],
            "called_by": ["graph-only-neighbour"],
            "calls": [],
        }
        for index, symbol in enumerate(symbols)
    ]
    control = {
        "repo_path": str(repo),
        "query": "fix the requested behavior",
        "top_hypothesis": hypotheses[0] if hypotheses else None,
        "hypotheses": hypotheses,
        "evidence": hypotheses,
        "execution_trace": "",
        "related_snippets": [],
    }
    if route is not None:
        control["live_route"] = route
    if preflight is not None:
        control["preflight_validation"] = preflight
    control_engine.refresh_control_safety(control)
    if related_files is not None:
        control["related_snippets"] = [
            {
                "file": relative,
                "symbol": Path(relative).stem,
                "snippet": (repo / relative).read_text(encoding="utf-8"),
            }
            for relative in related_files
        ]
        control_engine.refresh_control_safety(control)
    return control


def _state(
    repo: Path,
    control: dict,
    block: dict,
    *,
    user_input: str,
    intent: str = "bug_fix",
    style: str = "safe_minimal",
) -> AgentState:
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


# ── Single-file grounded-defect fixtures (T1 / T2 / T3 shape) ────────────────

def _calc_state(tmp_path: Path, monkeypatch, *, patched: str = "return a + b"):
    """The proven T1 road: executed failure bound to calc.py::add, exact source."""
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a - b\n")
    _write(tmp_path, "main.py", "from calc import add\nassert add(2, 2) == 4\n")
    preflight = run_preflight_validation(
        str(tmp_path), "python", command="python main.py"
    )
    control = _control(
        tmp_path,
        ["calc.py::add"],
        route=_defect_route(),
        preflight=preflight,
    )
    target = control["patch_intent"]["source_snippet"]
    block = {
        "summary": "Use addition.",
        "issues": [],
        "patch_candidate": {
            "relative_path": "calc.py",
            "file": "calc.py",
            "target_node_name": "add",
            "target_node_kind": "function",
            "target_snippet": target,
            "patched_snippet": target.replace("return a - b", patched),
        },
        "patch_plan": None,
        "confidence": 0.95,
        "needs_escalation": False,
    }
    state = _state(
        tmp_path,
        control,
        block,
        user_input=(
            "add returns the wrong value; fix this bug\n"
            "Validation command: python main.py"
        ),
    )
    run_postprocess_gate_battery(state)
    _disable_persistence(monkeypatch)
    _clear_bytecode_cache(tmp_path)
    return state


def _pytest_state(tmp_path: Path, monkeypatch):
    """The proven T2 road: a flat pytest regression, fixed by the patch."""
    _write(
        tmp_path,
        "solution.py",
        "def length_of_longest_substring(value):\n    return len(value)\n",
    )
    _write(
        tmp_path,
        "test_solution.py",
        "from solution import length_of_longest_substring\n\n"
        "def test_abba():\n"
        "    assert length_of_longest_substring('abba') == 2\n",
    )
    preflight = run_preflight_validation(str(tmp_path), "python")
    control = _control(
        tmp_path,
        ["solution.py::length_of_longest_substring"],
        route=_defect_route("the flat pytest sliding window test fails; fix the bug"),
        preflight=preflight,
    )
    target = control["patch_intent"]["source_snippet"]
    block = {
        "patch_candidate": {
            "relative_path": "solution.py",
            "target_node_name": "length_of_longest_substring",
            "target_snippet": target,
            "patched_snippet": target.replace("return len(value)", "return 2"),
        },
        "patch_plan": None,
        "confidence": 0.95,
        "needs_escalation": False,
        "issues": [],
    }
    state = _state(
        tmp_path,
        control,
        block,
        user_input="the flat pytest sliding window test fails; fix the bug",
    )
    run_postprocess_gate_battery(state)
    _disable_persistence(monkeypatch)
    _clear_bytecode_cache(tmp_path)
    return state


# ── Multi-file grounded-defect plan fixture ─────────────────────────────────

def _plan_state(
    tmp_path: Path,
    monkeypatch,
    plan: list[dict],
    *,
    apply_validation_command: str = "python main.py",
):
    """A grounded-defect run whose payload is a multi-op ``patch_plan``.

    The preflight failure is always established with ``python main.py``, which
    is what makes the defect grounded.  ``apply_validation_command`` is the
    separate command the apply step runs, so a fixture can hold validation
    fixed while varying what the patch itself does.
    """
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a - b\n")
    _write(tmp_path, "helper.py", "LABEL = 'old'\n")
    _write(tmp_path, "main.py", "from calc import add\nassert add(2, 2) == 4\n")
    preflight = run_preflight_validation(
        str(tmp_path), "python", command="python main.py"
    )
    control = _control(
        tmp_path,
        ["calc.py::add"],
        route=_defect_route(),
        preflight=preflight,
        related_files=["calc.py", "helper.py"],
    )
    block = {
        "patch_plan": plan,
        "patch_candidate": None,
        "confidence": 0.95,
        "needs_escalation": False,
        "issues": [],
    }
    control_engine.enforce_control_grounding_on_payload(control, block)
    state = _state(
        tmp_path,
        control,
        block,
        user_input=(
            "add returns the wrong value; fix this bug\n"
            f"Validation command: {apply_validation_command}"
        ),
        style="balanced",
    )
    _disable_persistence(monkeypatch)
    _clear_bytecode_cache(tmp_path)
    return state


def _good_plan() -> list[dict]:
    return [
        {
            "op": "replace_snippet",
            "file": "calc.py",
            "target_snippet": "return a - b",
            "patched_snippet": "return a + b",
        },
        {
            "op": "replace_snippet",
            "file": "helper.py",
            "target_snippet": "LABEL = 'old'",
            "patched_snippet": "LABEL = 'new'",
        },
    ]


# ── 1–3, 13, 16. Successful single-file auto-apply is visibly applied ────────

def test_t1_successful_auto_apply_is_reported_as_applied(tmp_path, monkeypatch):
    state = _calc_state(tmp_path, monkeypatch)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    block = state.json_block
    assert "return a + b" in (tmp_path / "calc.py").read_text(encoding="utf-8")
    assert block["execution_authorized"] is True
    assert block["execution_authority_source"] == (
        AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY
    )
    assert block["human_approval_required_for_execution"] is False
    assert block["execution_attempted"] is True
    assert block["mutation_observed"] is True
    assert block["patch_applied"] is True
    assert block["application_status"] == APPLICATION_APPLIED
    assert block["rollback_performed"] is False
    assert block["final_repository_changed"] is True
    assert block["final_validation_outcome"] == VALIDATION_PASSED
    assert block["final_state_observation"] == OBSERVATION_PLAN_NAMED_PATHS
    assert block["observed_changed_paths"] == ["calc.py"]
    assert "Patch applied automatically" in block["execution_summary"]
    assert "remain on disk" in block["execution_summary"]


def test_t2_successful_pytest_repair_is_reported_as_applied(tmp_path, monkeypatch):
    state = _pytest_state(tmp_path, monkeypatch)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    block = state.json_block
    assert "return 2" in (tmp_path / "solution.py").read_text(encoding="utf-8")
    assert block["patch_applied"] is True
    assert block["final_repository_changed"] is True
    assert block["final_validation_outcome"] == VALIDATION_PASSED
    assert block["observed_changed_paths"] == ["solution.py"]


def test_t3_safe_implementation_fix_never_touches_the_test_file(
    tmp_path, monkeypatch
):
    state = _pytest_state(tmp_path, monkeypatch)
    original_test = (tmp_path / "test_solution.py").read_text(encoding="utf-8")

    pipeline.maybe_run_auto_patch(state, interactive=False)

    block = state.json_block
    assert block["patch_applied"] is True
    assert block["observed_changed_paths"] == ["solution.py"]
    assert (tmp_path / "test_solution.py").read_text(encoding="utf-8") == (
        original_test
    )


def test_low_risk_override_names_its_own_authority_source(tmp_path, monkeypatch):
    """The second, distinct execution authority the single-file path has.

    ``vibe`` never sets ``auto_apply_allowed``; the run proceeds only because
    ``is_low_risk_single_file_patch`` says so, and the payload names that rule
    rather than borrowing the style policy's name for it.
    """
    state = _calc_state(tmp_path, monkeypatch)
    state.task_info["patch_style"] = "vibe"

    pipeline.maybe_run_auto_patch(state, interactive=False)

    block = state.json_block
    assert block["execution_authorized"] is True
    assert block["execution_authority_source"] == (
        AUTHORITY_SOURCE_LOW_RISK_SINGLE_FILE
    )
    assert block["patch_applied"] is True
    assert "low-risk grounded single-file policy" in block["execution_summary"]


# ── 15. Multi-file patch-plan path reports the same vocabulary ──────────────

def test_multi_file_patch_plan_apply_is_reported_as_applied(tmp_path, monkeypatch):
    state = _plan_state(tmp_path, monkeypatch, _good_plan())

    pipeline.maybe_run_auto_patch(state, interactive=False)

    block = state.json_block
    assert "return a + b" in (tmp_path / "calc.py").read_text(encoding="utf-8")
    assert block["execution_authorized"] is True
    assert block["execution_authority_source"] == (
        AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY
    )
    assert block["execution_attempted"] is True
    assert block["mutation_observed"] is True
    assert block["patch_applied"] is True
    assert block["application_status"] == APPLICATION_APPLIED
    assert block["final_repository_changed"] is True
    assert block["final_validation_outcome"] == VALIDATION_PASSED
    assert block["final_state_observation"] == OBSERVATION_PLAN_NAMED_PATHS
    assert block["observed_changed_paths"] == ["calc.py", "helper.py"]


# ── 12. Authorized apply + validation failure + rollback ────────────────────

def test_rolled_back_run_never_claims_the_repository_changed(
    tmp_path, monkeypatch
):
    plan = [
        {
            "op": "replace_snippet",
            "file": "calc.py",
            "target_snippet": "return a - b",
            "patched_snippet": "return a * b * 0",
        },
    ]
    state = _plan_state(tmp_path, monkeypatch, plan)
    before = _snapshot(tmp_path)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    block = state.json_block
    assert block["execution_authorized"] is True
    assert block["execution_attempted"] is True
    assert block["mutation_observed"] is True
    assert block["rollback_performed"] is True
    assert block["patch_applied"] is False
    assert block["application_status"] == APPLICATION_ROLLED_BACK
    assert block["final_repository_changed"] is False
    assert block["observed_changed_paths"] == []
    assert block["final_validation_outcome"] == VALIDATION_FAILED
    assert "rolled back" in block["execution_summary"]
    assert _snapshot(tmp_path) == before


# ── 11. Authorized attempt whose executor never applied anything ────────────

def test_authorized_attempt_with_no_write_is_not_a_rollback(tmp_path, monkeypatch):
    plan = [
        {
            "op": "replace_snippet",
            "file": "calc.py",
            "target_snippet": "this snippet is not in the file",
            "patched_snippet": "return a + b",
        },
    ]
    state = _plan_state(tmp_path, monkeypatch, plan)
    before = _snapshot(tmp_path)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    block = state.json_block
    assert block["execution_authorized"] is True
    assert block["execution_attempted"] is True
    # The reversal routine ran over an empty set; no mutation was invented.
    assert block["mutation_observed"] is False
    assert block["patch_applied"] is False
    assert block["application_status"] == APPLICATION_FAILED
    assert block["final_repository_changed"] is False
    assert _snapshot(tmp_path) == before


# ── 14. A no-op execution is not an applied patch ───────────────────────────

def test_no_op_execution_is_not_reported_as_a_repository_change(tmp_path):
    """An executor that wrote byte-identical content applied no patch.

    This used to be reached through an exact no-op *candidate*, driven all the
    way down the lifecycle.  PATCH.MINIMAL.LIVE.1 now rejects that candidate
    before it can reach an executor (see the test directly below), so the claim
    is pinned here at the reducer that owns it: given an apply the executor
    reports as succeeded and a complete observation in which nothing changed,
    the outcome is ``no_op`` — never ``applied``, and never a repository change.
    """

    _write(tmp_path, "calc.py", "def add(a, b):\n    return a - b\n")
    before = observe_named_paths(tmp_path, ["calc.py"])
    after = observe_named_paths(tmp_path, ["calc.py"])

    telemetry = authorized_execution(
        authority_source=AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY,
        receipt=ExecutionReceipt(
            write_receipted=True,
            apply_succeeded=True,
            validation_requested=True,
            validation_outcome="passed",
        ),
        observation=final_state_observation(before, after),
    )
    block: dict = {}
    attach_execution_telemetry(block, telemetry)

    assert block["execution_authorized"] is True
    assert block["execution_attempted"] is True
    assert block["mutation_observed"] is True
    assert block["patch_applied"] is False
    assert block["application_status"] == APPLICATION_NO_OP
    assert block["final_repository_changed"] is False
    assert block["observed_changed_paths"] == []
    assert "no material repository change" in block["execution_summary"]


def test_an_exact_no_op_candidate_never_reaches_execution(tmp_path, monkeypatch):
    """PATCH.MINIMAL.LIVE.1 — a candidate that changes zero bytes is not one.

    The plan below is the exact case the test above used to drive: replacement
    bytes identical to target bytes.  It is now rejected before any executor,
    so no execution is authorized and the repository is untouched.  Nothing
    about EXEC.AUTH changed — the run simply never reaches it.
    """

    plan = [
        {
            "op": "replace_snippet",
            "file": "calc.py",
            "target_snippet": "return a - b",
            "patched_snippet": "return a - b",
        },
    ]
    state = _plan_state(
        tmp_path, monkeypatch, plan, apply_validation_command="python --version"
    )
    before = _snapshot(tmp_path)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    block = state.json_block
    assert block["candidate_effect_status"] == "no_op"
    assert block["candidate_effect_rejection_reason"] == "no_op_candidate"
    assert block["execution_authorized"] is False
    assert block["execution_attempted"] is False
    assert block["patch_applied"] is False
    assert block["final_repository_changed"] is False
    assert _snapshot(tmp_path) == before


# ── 10. AUTO_PATCH_ENABLED=false overrides every earlier stage ──────────────

def test_auto_patch_disabled_denies_execution_for_a_grounded_defect(
    tmp_path, monkeypatch
):
    state = _calc_state(tmp_path, monkeypatch)
    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    before = _snapshot(tmp_path)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    block = state.json_block
    assert block["patch_basis"] == PATCH_BASIS_GROUNDED_DEFECT
    assert block["execution_authorized"] is False
    assert block["execution_authority_source"] == AUTHORITY_SOURCE_NONE
    assert block["execution_authorization_denied_reason"] == (
        DENIED_AUTO_PATCH_DISABLED
    )
    assert block["execution_attempted"] is False
    assert block["mutation_observed"] is False
    assert block["patch_applied"] is False
    assert block["final_repository_changed"] is False
    assert _snapshot(tmp_path) == before


# ── 4. A harmful test candidate is refused before any execution ─────────────

def test_harmful_test_edit_is_denied_with_high_model_confidence(
    tmp_path, monkeypatch
):
    _write(tmp_path, "solution.py", "def answer():\n    return 4\n")
    _write(
        tmp_path,
        "test_solution.py",
        "from solution import answer\n\n"
        "def test_answer():\n    assert answer() == 5\n",
    )
    preflight = run_preflight_validation(str(tmp_path), "python")
    control = _control(
        tmp_path,
        ["solution.py::answer"],
        route=_defect_route("answer returns the wrong value; fix this bug"),
        preflight=preflight,
        related_files=["solution.py", "test_solution.py"],
    )
    plan = [
        {
            "op": "replace_snippet",
            "file": "solution.py",
            "target_snippet": "return 4",
            "patched_snippet": "return 5",
        },
        {
            # The harmful half: rewrite the test until it agrees with the bug.
            "op": "replace_snippet",
            "file": "test_solution.py",
            "target_snippet": "== 5",
            "patched_snippet": "== 4",
        },
    ]
    block = {
        "patch_plan": plan,
        "patch_candidate": None,
        # Model confidence is at its ceiling and still buys nothing.
        "confidence": 1.0,
        "needs_escalation": False,
        "issues": [],
    }
    control_engine.enforce_control_grounding_on_payload(control, block)
    state = _state(
        tmp_path,
        control,
        block,
        user_input="answer returns the wrong value; fix this bug",
        style="balanced",
    )
    _disable_persistence(monkeypatch)
    before = _snapshot(tmp_path)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert block["confidence"] == 1.0
    assert block["patch_basis"] == PATCH_BASIS_GROUNDED_DEFECT
    assert block["execution_authorized"] is False
    assert block["execution_authority_source"] == AUTHORITY_SOURCE_NONE
    assert block["execution_authorization_denied_reason"] == (
        DENIED_PATCH_SAFETY_BLOCKED
    )
    assert block["execution_attempted"] is False
    assert block["mutation_observed"] is False
    assert block["patch_applied"] is False
    assert block["application_status"] == APPLICATION_NOT_ATTEMPTED
    assert _snapshot(tmp_path) == before


# ── 5/6. An explicit change stays unexecuted, sandbox verdict notwithstanding ─

def _feature_state(tmp_path: Path, monkeypatch, plan: list[dict]):
    _write(tmp_path, "model.py", "PRIORITY = 0\n")
    _write(tmp_path, "store.py", "STORED_PRIORITY = 0\n")
    _write(tmp_path, "cli.py", "CLI_PRIORITY = 0\n")
    # A real test the repository owns, so OPS.PATCH.2's sandbox validation has
    # something to run and can genuinely pass on a coherent candidate.
    _write(
        tmp_path,
        "test_priority.py",
        "import cli\nimport model\nimport store\n\n\n"
        "def test_priorities_are_integers():\n"
        "    assert isinstance(model.PRIORITY, int)\n"
        "    assert isinstance(store.STORED_PRIORITY, int)\n"
        "    assert isinstance(cli.CLI_PRIORITY, int)\n",
    )
    control = _control(
        tmp_path,
        ["model.py::PRIORITY"],
        route=_feature_route(),
        related_files=["model.py", "store.py", "cli.py"],
    )
    block = {
        "patch_plan": plan,
        "patch_candidate": None,
        "confidence": 1.0,
        "needs_escalation": False,
        "issues": [],
    }
    control_engine.enforce_control_grounding_on_payload(control, block)
    state = _state(
        tmp_path,
        control,
        block,
        user_input="Add task priority support across model/store/CLI.",
        intent="feature_add",
        style="vibe",
    )
    _disable_persistence(monkeypatch)
    _clear_bytecode_cache(tmp_path)
    return state


def _coherent_feature_plan() -> list[dict]:
    """Every surface the request named — model, store and CLI."""
    return [
        {
            "op": "replace_snippet",
            "file": "model.py",
            "target_snippet": "PRIORITY = 0",
            "patched_snippet": "PRIORITY = 1",
        },
        {
            "op": "replace_snippet",
            "file": "store.py",
            "target_snippet": "STORED_PRIORITY = 0",
            "patched_snippet": "STORED_PRIORITY = 1",
        },
        {
            "op": "replace_snippet",
            "file": "cli.py",
            "target_snippet": "CLI_PRIORITY = 0",
            "patched_snippet": "CLI_PRIORITY = 1",
        },
    ]


def _broken_feature_plan() -> list[dict]:
    """The same scope, with one operation that cannot even be imported."""
    plan = _coherent_feature_plan()
    plan[0] = {
        "op": "replace_snippet",
        "file": "model.py",
        "target_snippet": "PRIORITY = 0",
        "patched_snippet": "PRIORITY = (",
    }
    return plan


@pytest.mark.parametrize(
    "plan_factory", [_coherent_feature_plan, _broken_feature_plan]
)
def test_explicit_change_is_never_executed_whatever_the_sandbox_says(
    tmp_path, monkeypatch, plan_factory
):
    state = _feature_state(tmp_path, monkeypatch, plan_factory())
    before = _snapshot(tmp_path)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    block = state.json_block
    assert block["patch_basis"] == PATCH_BASIS_EXPLICIT_CHANGE_REQUEST
    assert block["execution_authorized"] is False
    assert block["execution_authority_source"] == AUTHORITY_SOURCE_NONE
    assert block["execution_authorization_denied_reason"] == (
        DENIED_HUMAN_APPROVAL_REQUIRED
    )
    assert block["human_approval_required_for_execution"] is True
    assert block["execution_attempted"] is False
    assert block["mutation_observed"] is False
    assert block["patch_applied"] is False
    assert block["final_repository_changed"] is False
    assert "human approval is required" in block["execution_summary"]
    # Historical component-authority fields keep their old values and meaning.
    assert block["write_authority"] is False
    assert block["patch_application_authority"] is False
    assert block["human_approval_required"] is True
    assert _snapshot(tmp_path) == before


def test_sandbox_passing_candidate_is_approval_ready_but_unexecuted(
    tmp_path, monkeypatch
):
    state = _feature_state(tmp_path, monkeypatch, _coherent_feature_plan())

    pipeline.maybe_run_auto_patch(state, interactive=False)

    block = state.json_block
    # §29: OPS.PATCH.2 really did materialize and validate this candidate, and
    # it really did pass.  That is still not execution authority.
    assert block["candidate_validation_status"] == CANDIDATE_VALIDATION_PASSED
    assert block["approval_ready"] is True
    assert block["execution_authorized"] is False
    assert block["execution_attempted"] is False
    assert block["patch_applied"] is False
    assert block["human_approval_required_for_execution"] is True


# ── 7/8/9. Read-only and ungrounded routes report the absence of execution ──

def test_analysis_route_reports_no_execution(tmp_path, monkeypatch):
    control = _control(tmp_path, [], route=_analysis_route())
    block = {"summary": "The retrieval layer ranks candidates.", "issues": []}
    state = _state(
        tmp_path,
        control,
        block,
        user_input="How does the retrieval layer decide which files to read?",
        intent="analysis",
    )
    _disable_persistence(monkeypatch)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert block["execution_authorized"] is False
    assert block["execution_authorization_denied_reason"] == (
        DENIED_NO_CHANGE_REQUESTED
    )
    assert block["execution_attempted"] is False
    assert block["mutation_observed"] is False
    assert block["patch_applied"] is False


def test_clarification_route_reports_no_execution(tmp_path, monkeypatch):
    route = route_live_task("make it better", repository_available=True).as_dict()
    control = _control(tmp_path, [], route=route)
    block = {"summary": "Which behaviour should change?", "issues": []}
    state = _state(
        tmp_path, control, block, user_input="make it better", intent="analysis"
    )
    _disable_persistence(monkeypatch)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert route["selected_workflow"] == "clarification"
    assert block["execution_authorized"] is False
    assert block["execution_attempted"] is False
    assert block["patch_applied"] is False


def test_wrong_target_run_never_implies_a_patch_was_attempted(
    tmp_path, monkeypatch
):
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a - b\n")
    _write(tmp_path, "unrelated.py", "VALUE = 1\n")
    control = _control(tmp_path, ["calc.py::add"], route=_defect_route())
    block = {
        "patch_candidate": {
            "relative_path": "unrelated.py",
            "file": "unrelated.py",
            "target_snippet": "VALUE = 1",
            "patched_snippet": "VALUE = 2",
        },
        "patch_plan": None,
        "confidence": 0.99,
        "needs_escalation": False,
        "issues": [],
    }
    state = _state(
        tmp_path,
        control,
        block,
        user_input="add returns the wrong value; fix this bug",
    )
    _disable_persistence(monkeypatch)
    before = _snapshot(tmp_path)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert block["execution_authorized"] is False
    assert block["execution_authorization_denied_reason"] == (
        DENIED_NO_PATCH_BASIS_HANDOFF
    )
    assert block["execution_attempted"] is False
    assert block["patch_applied"] is False
    assert "No patch was applied" in block["execution_summary"]
    assert _snapshot(tmp_path) == before


# ── 17/20. Historical fields keep their value, their meaning and their scope ─

def test_historical_authority_fields_are_preserved_and_scoped(
    tmp_path, monkeypatch
):
    state = _calc_state(tmp_path, monkeypatch)

    pipeline.maybe_run_auto_patch(state, interactive=False)

    block = state.json_block
    # CONTROL still cannot authorize a write, and says so, while the patch it
    # produced was legitimately applied by a downstream gate.
    assert block["write_authority"] is False
    assert block["patch_application_authority"] is False
    assert block["human_approval_required"] is True
    assert block["authority_scope"] == AUTHORITY_SCOPE_CONTROL_OR_PLANNING
    assert block["patch_applied"] is True
    assert (
        state.control_result["patch_candidate_state"]["write_authority"] is False
    )
    assert state.live_route["write_authority"] is False
    assert state.live_route["patch_application_authority"] is False


def test_historical_artifact_without_telemetry_still_loads_unchanged():
    """A pre-EXEC.AUTH artifact is readable, and gains no new meaning."""
    historical = json.loads(
        json.dumps(
            {
                "patch_candidate": {"file": "calc.py"},
                "write_authority": False,
                "patch_application_authority": False,
                "human_approval_required": True,
            }
        )
    )
    assert not set(EXECUTION_TELEMETRY_KEYS) & set(historical)
    # Reading it does not retroactively assert anything about execution.
    assert "patch_applied" not in historical
    assert "final_repository_changed" not in historical


# ── 19. The authority-source vocabulary is closed and prose-free ────────────

def test_authority_source_vocabulary_is_a_small_closed_enum():
    assert EXECUTION_AUTHORITY_SOURCES == (
        AUTHORITY_SOURCE_NONE,
        AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY,
        AUTHORITY_SOURCE_LOW_RISK_SINGLE_FILE,
        AUTHORITY_SOURCE_MANUAL_APPLY,
    )
    for source in EXECUTION_AUTHORITY_SOURCES:
        assert source == source.lower()
        assert " " not in source
    with pytest.raises(ExecutionTelemetryError):
        ExecutionTelemetry(
            execution_authorized=True,
            execution_authority_source="confidence=1.0",
        )


def test_denial_reason_vocabulary_is_closed():
    for reason in EXECUTION_DENIAL_REASONS:
        assert reason == reason.lower()
        assert " " not in reason
    with pytest.raises(ExecutionTelemetryError):
        no_execution("because the model felt unsure")


# ── 5/6 of the spec: the hard invariants, asserted structurally ─────────────

def test_authorization_never_implies_application():
    telemetry = authorized_execution(
        authority_source=AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY,
        receipt=ExecutionReceipt(apply_succeeded=False),
        observation=FinalStateObservation(scope=OBSERVATION_UNAVAILABLE),
    )
    assert telemetry.execution_authorized is True
    assert telemetry.execution_attempted is True
    assert telemetry.patch_applied is False


def test_attempt_never_implies_persistence():
    telemetry = authorized_execution(
        authority_source=AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY,
        receipt=ExecutionReceipt(
            write_receipted=True,
            apply_succeeded=False,
            rollback_outcome=rollback_completed_verified(),
            validation_requested=True,
            validation_outcome=VALIDATION_FAILED,
        ),
        observation=FinalStateObservation(scope=OBSERVATION_UNAVAILABLE),
    )
    assert telemetry.mutation_observed is True
    assert telemetry.rollback_performed is True
    assert telemetry.final_repository_changed is False
    assert telemetry.patch_applied is False
    assert telemetry.application_status == APPLICATION_ROLLED_BACK


@pytest.mark.parametrize(
    "kwargs",
    [
        # attempted without authorization
        {"execution_attempted": True},
        # a mutation with no attempt
        {"mutation_observed": True},
    ],
)
def test_contradictory_fact_sets_are_refused(kwargs):
    with pytest.raises(ExecutionTelemetryError):
        ExecutionTelemetry(**kwargs)


def test_a_rolled_back_run_may_not_claim_persistence():
    with pytest.raises(ExecutionTelemetryError):
        ExecutionTelemetry(
            execution_authorized=True,
            execution_authority_source=AUTHORITY_SOURCE_MANUAL_APPLY,
            execution_attempted=True,
            mutation_observed=True,
            rollback_performed=True,
            final_repository_changed=True,
            application_status=APPLICATION_ROLLED_BACK,
            final_state_observation=OBSERVATION_PLAN_NAMED_PATHS,
        )


def test_applied_requires_a_surviving_change():
    with pytest.raises(ExecutionTelemetryError):
        ExecutionTelemetry(
            execution_authorized=True,
            execution_authority_source=AUTHORITY_SOURCE_MANUAL_APPLY,
            execution_attempted=True,
            mutation_observed=True,
            patch_applied=True,
            final_repository_changed=False,
            application_status=APPLICATION_APPLIED,
            final_state_observation=OBSERVATION_PLAN_NAMED_PATHS,
        )


# ── 20/22. Human-approval stage semantics stay separable ───────────────────

def test_human_approval_is_reported_per_stage(tmp_path, monkeypatch):
    applied = _calc_state(tmp_path / "applied", monkeypatch)
    pipeline.maybe_run_auto_patch(applied, interactive=False)

    feature = _feature_state(tmp_path / "feature", monkeypatch, _coherent_feature_plan())
    pipeline.maybe_run_auto_patch(feature, interactive=False)

    # Same candidate-review requirement, different execution requirement.
    assert applied.json_block["human_approval_required"] is True
    assert feature.json_block["human_approval_required"] is True
    assert applied.json_block["human_approval_required_for_execution"] is False
    assert feature.json_block["human_approval_required_for_execution"] is True


# ── 21. CHECK.LIVE.1 reuse: observation, never authorization ────────────────

def test_final_state_is_observed_with_the_check_live_observer(tmp_path):
    _write(tmp_path, "a.py", "VALUE = 1\n")
    _write(tmp_path, "b.py", "OTHER = 1\n")
    before = observe_named_paths(tmp_path, ["a.py", "b.py"])
    (tmp_path / "a.py").write_text("VALUE = 2\n", encoding="utf-8")
    after = observe_named_paths(tmp_path, ["a.py", "b.py"])

    observation = final_state_observation(before, after)
    assert observation.scope == OBSERVATION_PLAN_NAMED_PATHS
    assert observation.complete is True
    assert observation.changed_paths == ("a.py",)


def test_observation_of_an_unnamed_path_is_incomplete_not_invented(tmp_path):
    _write(tmp_path, "a.py", "VALUE = 1\n")
    before = observe_named_paths(tmp_path, ["a.py"])
    _write(tmp_path, "late.py", "LATE = 1\n")
    after = observe_named_paths(tmp_path, ["a.py", "late.py"])

    observation = final_state_observation(before, after)
    assert observation.scope == OBSERVATION_INCOMPLETE
    assert observation.complete is False
    # The untyped path is not silently reported as a change.
    assert observation.changed_paths == ()


def test_incomplete_observation_falls_back_to_the_executor_receipt():
    telemetry = authorized_execution(
        authority_source=AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY,
        receipt=ExecutionReceipt(
            write_receipted=True,
            apply_succeeded=True,
            validation_requested=True,
            validation_outcome=VALIDATION_PASSED,
        ),
        observation=FinalStateObservation(scope=OBSERVATION_INCOMPLETE),
    )
    assert telemetry.final_repository_changed is True
    assert telemetry.patch_applied is True
    assert telemetry.final_state_observation == OBSERVATION_INCOMPLETE


def test_telemetry_never_authorizes_anything():
    guardrails = execution_telemetry_guardrails()
    assert guardrails["authority_described_not_granted"] is True
    assert guardrails["authority_widening_possible"] is False
    assert guardrails["execution_behavior_changed"] is False
    assert guardrails["human_approval_policy_changed"] is False
    assert guardrails["auto_patch_policy_changed"] is False
    assert guardrails["model_self_report_consumed"] is False
    assert guardrails["repository_traversed"] is False
    assert guardrails["model_called"] is False
    assert guardrails["network_call_performed"] is False
    assert guardrails["authoritative_effect"] is False


# ── 24. The manual apply action is a real, named authority source ───────────

def test_manual_apply_reports_its_own_authority_source():
    telemetry = authorized_execution(
        authority_source=AUTHORITY_SOURCE_MANUAL_APPLY,
        receipt=ExecutionReceipt(
            write_receipted=True,
            apply_succeeded=True,
            validation_requested=True,
            validation_outcome=VALIDATION_PASSED,
        ),
        observation=FinalStateObservation(
            scope=OBSERVATION_PLAN_NAMED_PATHS,
            changed_paths=("model.py",),
            complete=True,
        ),
    )
    assert telemetry.execution_authority_source == AUTHORITY_SOURCE_MANUAL_APPLY
    assert telemetry.patch_applied is True
    assert "human apply action" in telemetry.summary()


def test_web_runner_records_the_two_branches_that_never_reach_the_pipeline():
    """Read-only and harness-blocked runs skip ``maybe_run_auto_patch`` entirely.

    Those two branches are the only operator-visible results the pipeline never
    sees, so the runner has to state the absence of execution itself or the
    payload would simply be silent about it.
    """
    from web import runner

    source = inspect.getsource(runner.run_agent_web)
    assert source.count("attach_execution_telemetry(") == 2
    assert "no_execution(DENIED_NO_CHANGE_REQUESTED)" in source
    assert "no_execution(DENIED_HARNESS_MODE_BLOCKED)" in source


def test_web_dream_apply_route_records_execution_telemetry():
    from web import app as web_app

    source = inspect.getsource(web_app.dream_apply_route)
    assert "AUTHORITY_SOURCE_MANUAL_APPLY" in source
    assert "authorized_execution(" in source
    assert "observe_named_paths(" in source


# ── 34. Execution behaviour delta is zero ──────────────────────────────────

def test_telemetry_recording_is_never_part_of_a_decision():
    """No branch in the pipeline may read a value this phase writes."""
    source = inspect.getsource(pipeline)
    tree = ast.parse(source)
    telemetry_writers = {
        "_record_no_execution",
        "_record_authorized_execution",
        "attach_execution_telemetry",
    }
    for node in ast.walk(tree):
        if not isinstance(node, (ast.If, ast.While)):
            continue
        for inner in ast.walk(node.test):
            if isinstance(inner, ast.Call):
                name = getattr(inner.func, "id", "") or getattr(
                    inner.func, "attr", ""
                )
                assert name not in telemetry_writers
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                assert inner.value not in set(EXECUTION_TELEMETRY_KEYS)


def test_telemetry_module_opens_no_network_and_calls_no_model():
    source = Path("core/execution_outcome_telemetry.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "requests",
        "urllib",
        "httpx",
        "socket",
        "subprocess",
        "os.walk",
        "rglob",
        "iterdir",
        "run_gemini_request",
        "run_deepseek_review",
    ):
        assert forbidden not in source


# ── Receipt adapters read typed executor facts, never prose ─────────────────

def test_plan_receipt_reads_writes_separately_and_legacy_success_fails_closed():
    receipt = plan_execution_receipt(
        {
            "success": False,
            "applied_ops": [],
            "rollback_performed": True,
            "validation_command": "python -m pytest",
        }
    )
    assert receipt.write_receipted is False
    assert receipt.rollback_performed is False
    assert receipt.rollback_outcome.status == "unverifiable"

    receipt = plan_execution_receipt(
        {
            "success": False,
            "applied_ops": [{"op": "replace_snippet"}],
            "rollback_performed": True,
            "validation_command": "python -m pytest",
            "validation_outcome": VALIDATION_FAILED,
        }
    )
    assert receipt.write_receipted is True
    assert receipt.validation_outcome == VALIDATION_FAILED


def test_single_file_receipt_reads_the_terminal_state_of_the_loop():
    attempts = [
        {
            "phase": "validation_failed",
            "rollback_performed": True,
            "validation_outcome": VALIDATION_FAILED,
            "target_file": "/repo/calc.py",
        },
        {
            "phase": "validated",
            "rollback_performed": False,
            "validation_outcome": VALIDATION_PASSED,
            "target_file": "/repo/calc.py",
        },
    ]
    receipt = single_file_execution_receipt(
        attempts, success=True, validation_requested=True
    )
    assert receipt.write_receipted is True
    # An earlier attempt was reversed; the run still ends with a patch on disk.
    assert receipt.rollback_performed is False
    assert receipt.validation_outcome == VALIDATION_PASSED


def test_unrecognised_validation_outcome_is_reported_as_unavailable():
    telemetry = authorized_execution(
        authority_source=AUTHORITY_SOURCE_LOW_RISK_SINGLE_FILE,
        receipt=ExecutionReceipt(
            write_receipted=True,
            apply_succeeded=True,
            validation_requested=True,
            validation_outcome=None,
        ),
        observation=FinalStateObservation(
            scope=OBSERVATION_PLAN_NAMED_PATHS,
            changed_paths=("calc.py",),
            complete=True,
        ),
    )
    assert telemetry.final_validation_outcome == "unavailable"


def test_inconclusive_validation_is_reported_as_it_already_exists():
    """§37: no timeout re-categorisation happens here."""
    telemetry = authorized_execution(
        authority_source=AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY,
        receipt=ExecutionReceipt(
            write_receipted=True,
            apply_succeeded=False,
            rollback_outcome=rollback_completed_verified(),
            validation_requested=True,
            validation_outcome=VALIDATION_INCONCLUSIVE,
        ),
        observation=FinalStateObservation(scope=OBSERVATION_UNAVAILABLE),
    )
    assert telemetry.final_validation_outcome == VALIDATION_INCONCLUSIVE
    assert "inconclusive" in telemetry.summary().lower()


# ── Payload rendering is additive and internally consistent ─────────────────

def test_flat_facts_and_grouped_structures_never_disagree():
    telemetry = no_execution(DENIED_PATCH_SAFETY_BLOCKED)
    fields = telemetry.as_payload_fields()
    for key, value in fields["execution_authorization"].items():
        assert fields[key] == value
    for key, value in fields["execution_outcome"].items():
        assert fields[key] == value
    assert set(fields) == set(EXECUTION_TELEMETRY_KEYS)


def test_attaching_telemetry_preserves_every_existing_key():
    payload = {
        "patch_candidate": {"file": "calc.py"},
        "write_authority": False,
        "patch_application_authority": False,
        "human_approval_required": True,
        "confidence": 0.95,
    }
    before = dict(payload)
    attach_execution_telemetry(payload, no_execution(DENIED_NO_CHANGE_REQUESTED))
    for key, value in before.items():
        assert payload[key] == value


def test_no_execution_default_shape_is_fully_negative():
    telemetry = no_execution(DENIED_NO_CHANGE_REQUESTED)
    assert telemetry.execution_authorized is False
    assert telemetry.execution_authority_source == AUTHORITY_SOURCE_NONE
    assert telemetry.execution_attempted is False
    assert telemetry.mutation_observed is False
    assert telemetry.patch_applied is False
    assert telemetry.rollback_performed is False
    assert telemetry.final_repository_changed is False
    assert telemetry.application_status == APPLICATION_NOT_ATTEMPTED
    assert telemetry.final_validation_outcome == FINAL_VALIDATION_NOT_RUN
    assert telemetry.final_state_observation == OBSERVATION_NOT_ATTEMPTED
    assert telemetry.execution_authorization_denied_reason != DENIED_NOT_APPLICABLE
