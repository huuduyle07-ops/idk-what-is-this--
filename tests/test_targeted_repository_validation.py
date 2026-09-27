from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.pipeline as pipeline
import core.targeted_repository_validation as targeted
from core.agent_state import AgentState
from core.patch_basis import (
    PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
    PATCH_BASIS_GROUNDED_DEFECT,
)
from core.targeted_repository_validation import (
    CATEGORY_BASELINE_TARGETED_FAILED,
    CATEGORY_CANDIDATE_FINGERPRINT_STALE,
    CATEGORY_NO_RELEVANT_EXISTING_CHECKS,
    CATEGORY_SELECTED_CHECK_MODIFIED,
    CATEGORY_SELECTION_BUDGET_EXCEEDED,
    CATEGORY_TARGETED_CHECKS_PASSED,
    DEFAULT_MAX_TARGETED_TEST_FILES,
    DEFAULT_MAX_TARGETED_TEST_NODES,
    DEFAULT_TARGETED_VALIDATION_BUDGET_SECONDS,
    SELECTION_DIRECT_SYMBOL_CALL,
    SELECTION_EXPLICIT_USER_CHECK,
    SELECTION_MODULE_DEPENDENCY,
    TargetedCheckRun,
    build_targeted_validation_request,
    select_targeted_checks,
    targeted_validation_guardrails,
    validate_targeted_candidate,
)
from core.validation_execution import SafeValidationResult
from core.validation_outcome import (
    CATEGORY_VALIDATION_BUDGET_EXHAUSTED,
    CATEGORY_VALIDATION_TOOL_UNAVAILABLE,
    VALIDATION_FAILED,
    VALIDATION_INCONCLUSIVE,
    VALIDATION_PASSED,
)
from graph.schema import build_graph


TARGET = "core/calc.py::calc"


def _graph(*, direct: int = 1, imports: int = 0, unrelated: int = 0):
    nodes = [
        {"id": "core/calc.py", "type": "file"},
        {"id": TARGET, "type": "function", "file": "core/calc.py"},
    ]
    edges = [{"source": "core/calc.py", "target": TARGET, "type": "contains"}]
    for index in range(direct):
        path = f"tests/test_direct_{index}.py"
        symbol = f"{path}::test_calc_{index}"
        nodes.extend(
            [
                {"id": path, "type": "file"},
                {"id": symbol, "type": "function", "file": path},
            ]
        )
        edges.append({"source": symbol, "target": TARGET, "type": "resolved_call"})
    for index in range(imports):
        path = f"tests/test_import_{index}.py"
        nodes.append({"id": path, "type": "file"})
        edges.append({"source": path, "target": "core/calc.py", "type": "imports"})
    for index in range(unrelated):
        path = f"tests/test_unrelated_{index}.py"
        symbol = f"{path}::test_other_{index}"
        nodes.extend(
            [
                {"id": path, "type": "file"},
                {"id": symbol, "type": "function", "file": path},
                {"id": f"core/other_{index}.py::other", "type": "function"},
            ]
        )
        edges.append(
            {
                "source": symbol,
                "target": f"core/other_{index}.py::other",
                "type": "resolved_call",
            }
        )
    return build_graph(nodes, edges)


def _write_repo(repo: Path, assertion: str = "assert calc() > 0") -> None:
    (repo / "core").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "core" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "core" / "calc.py").write_text(
        "def calc():\n    return 1\n", encoding="utf-8"
    )
    (repo / "tests" / "test_calc.py").write_text(
        "from core.calc import calc\n\n"
        "def test_calc():\n"
        f"    {assertion}\n",
        encoding="utf-8",
    )


def _repo_graph():
    return build_graph(
        [
            {"id": "core/calc.py", "type": "file"},
            {"id": TARGET, "type": "function", "file": "core/calc.py"},
            {"id": "tests/test_calc.py", "type": "file"},
            {
                "id": "tests/test_calc.py::test_calc",
                "type": "function",
                "file": "tests/test_calc.py",
            },
        ],
        [
            {
                "source": "tests/test_calc.py::test_calc",
                "target": TARGET,
                "type": "resolved_call",
            },
            {
                "source": "tests/test_calc.py",
                "target": "core/calc.py",
                "type": "imports",
            },
        ],
    )


def _plan(value: int = 2, *, path: str = "core/calc.py") -> list[dict]:
    return [
        {
            "op": "replace_snippet",
            "relative_path": path,
            "target_snippet": "    return 1\n",
            "patched_snippet": f"    return {value}\n",
        }
    ]


def _request(repo: Path, plan: list[dict] | None = None):
    return build_targeted_validation_request(
        repo_path=repo,
        candidate_plan=plan or _plan(),
        graph=_repo_graph(),
        changed_symbols=(TARGET,),
    )


def _digest_tree(repo: Path) -> dict[str, str]:
    return {
        path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(repo.rglob("*"))
        if path.is_file()
    }


def test_direct_existing_test_symbol_is_selected_before_module_dependency():
    selection = select_targeted_checks(
        _graph(direct=2, imports=2, unrelated=2),
        changed_paths=("core/calc.py",),
        changed_symbols=(TARGET,),
    )

    assert selection.complete is True
    assert [check.identifier for check in selection.checks] == [
        "tests/test_direct_0.py::test_calc_0",
        "tests/test_direct_1.py::test_calc_1",
    ]
    assert {check.provenance for check in selection.checks} == {
        SELECTION_DIRECT_SYMBOL_CALL
    }


def test_test_module_dependency_is_the_deterministic_fallback():
    selection = select_targeted_checks(
        _graph(direct=0, imports=2, unrelated=2),
        changed_paths=("core/calc.py",),
        changed_symbols=(TARGET,),
    )

    assert [check.identifier for check in selection.checks] == [
        "tests/test_import_0.py",
        "tests/test_import_1.py",
    ]
    assert {check.provenance for check in selection.checks} == {
        SELECTION_MODULE_DEPENDENCY
    }


def test_preserved_bounded_user_selector_has_highest_precedence():
    graph = _graph(direct=2, imports=0)
    selection = select_targeted_checks(
        graph,
        changed_paths=("core/calc.py",),
        changed_symbols=(TARGET,),
        preserved_user_command=(
            "python -m pytest tests/test_direct_1.py::test_calc_1 -q"
        ),
    )

    assert [check.identifier for check in selection.checks] == [
        "tests/test_direct_1.py::test_calc_1"
    ]
    assert selection.checks[0].provenance == SELECTION_EXPLICIT_USER_CHECK


def test_unrelated_tests_are_excluded_and_related_set_is_bounded():
    selection = select_targeted_checks(
        _graph(direct=3, unrelated=12),
        changed_paths=("core/calc.py",),
        changed_symbols=(TARGET,),
    )

    assert len(selection.checks) == 3
    assert all("unrelated" not in check.identifier for check in selection.checks)


def test_ambiguous_over_cap_selection_is_inconclusive_not_a_partial_pick():
    selection = select_targeted_checks(
        _graph(direct=DEFAULT_MAX_TARGETED_TEST_NODES + 1),
        changed_paths=("core/calc.py",),
        changed_symbols=(TARGET,),
    )

    assert selection.complete is False
    assert selection.category == CATEGORY_SELECTION_BUDGET_EXCEEDED
    assert selection.checks == ()
    assert selection.related_check_count == DEFAULT_MAX_TARGETED_TEST_NODES + 1


def test_too_many_related_files_is_also_inconclusive():
    selection = select_targeted_checks(
        _graph(direct=DEFAULT_MAX_TARGETED_TEST_FILES + 1),
        changed_paths=("core/calc.py",),
        changed_symbols=(TARGET,),
    )

    assert selection.complete is False
    assert selection.category == CATEGORY_SELECTION_BUDGET_EXCEEDED
    assert selection.checks == ()


def test_no_relevant_existing_checks_is_complete_selection_but_never_passes(tmp_path):
    _write_repo(tmp_path)
    request = build_targeted_validation_request(
        repo_path=tmp_path,
        candidate_plan=_plan(),
        graph=_graph(direct=0, imports=0, unrelated=3),
        changed_symbols=(TARGET,),
    )
    result = validate_targeted_candidate(
        repo_path=tmp_path,
        candidate_plan=_plan(),
        request=request,
    )

    assert request.selection_complete is True
    assert request.selected_checks == ()
    assert result.status == VALIDATION_INCONCLUSIVE
    assert result.category == CATEGORY_NO_RELEVANT_EXISTING_CHECKS


def test_request_is_immutable_and_binds_exact_same_check_set(tmp_path):
    _write_repo(tmp_path)
    request = _request(tmp_path)

    assert isinstance(request.selected_checks, tuple)
    assert request.budget_seconds == DEFAULT_TARGETED_VALIDATION_BUDGET_SECONDS
    assert request.max_test_files == DEFAULT_MAX_TARGETED_TEST_FILES
    assert request.max_test_nodes == DEFAULT_MAX_TARGETED_TEST_NODES
    assert request.check_set_fingerprint == request.check_set_fingerprint
    with pytest.raises(Exception):
        request.selection_reason = "changed"  # type: ignore[misc]


def test_baseline_pass_candidate_pass_uses_sandboxes_and_leaves_repo_unchanged(tmp_path):
    _write_repo(tmp_path, assertion="assert calc() > 0")
    before = _digest_tree(tmp_path)
    request = _request(tmp_path)

    result = validate_targeted_candidate(
        repo_path=tmp_path,
        candidate_plan=_plan(2),
        request=request,
        pre_patch_probe_result="reproduced",
    )

    assert result.status == VALIDATION_PASSED
    assert result.category == CATEGORY_TARGETED_CHECKS_PASSED
    assert result.baseline_outcome == VALIDATION_PASSED
    assert result.candidate_outcome == VALIDATION_PASSED
    assert result.baseline_checks_executed == result.candidate_checks_executed
    assert result.pre_patch_probe_result == "reproduced"
    assert result.sandbox_cleanup_ok is True
    assert result.baseline_python_bytecode_cache_isolated is True
    assert result.candidate_python_bytecode_cache_isolated is True
    assert _digest_tree(tmp_path) == before
    assert not any(path.name == "__pycache__" for path in tmp_path.rglob("__pycache__"))


def test_baseline_pass_candidate_fail_is_failed_and_probe_cannot_override(tmp_path):
    _write_repo(tmp_path, assertion="assert calc() == 1")
    before = _digest_tree(tmp_path)
    request = _request(tmp_path)

    result = validate_targeted_candidate(
        repo_path=tmp_path,
        candidate_plan=_plan(2),
        request=request,
        pre_patch_probe_result="not_reproduced",
    )

    assert result.baseline_outcome == VALIDATION_PASSED
    assert result.candidate_outcome == VALIDATION_FAILED
    assert result.status == VALIDATION_FAILED
    assert result.pre_patch_probe_result == "not_reproduced"
    assert _digest_tree(tmp_path) == before


def test_baseline_failure_is_inconclusive_even_when_candidate_passes(tmp_path):
    _write_repo(tmp_path, assertion="assert calc() == 2")
    request = _request(tmp_path)

    result = validate_targeted_candidate(
        repo_path=tmp_path,
        candidate_plan=_plan(2),
        request=request,
    )

    assert result.baseline_outcome == VALIDATION_FAILED
    assert result.candidate_outcome == VALIDATION_PASSED
    assert result.status == VALIDATION_INCONCLUSIVE
    assert result.category == CATEGORY_BASELINE_TARGETED_FAILED


def test_candidate_cannot_modify_selected_test_and_use_it_as_oracle(tmp_path):
    _write_repo(tmp_path)
    test_plan = [
        {
            "op": "replace_snippet",
            "relative_path": "tests/test_calc.py",
            "target_snippet": "    assert calc() > 0\n",
            "patched_snippet": "    assert calc() < 0\n",
        }
    ]
    request = build_targeted_validation_request(
        repo_path=tmp_path,
        candidate_plan=test_plan,
        graph=_repo_graph(),
        changed_symbols=(TARGET,),
    )

    result = validate_targeted_candidate(
        repo_path=tmp_path,
        candidate_plan=test_plan,
        request=request,
    )

    assert result.status == VALIDATION_INCONCLUSIVE
    assert result.category == CATEGORY_SELECTED_CHECK_MODIFIED
    assert result.baseline_outcome == "targeted_validation_not_run"


def test_refined_candidate_invalidates_fingerprint_before_sandbox(tmp_path):
    _write_repo(tmp_path)
    request = _request(tmp_path, _plan(2))

    result = validate_targeted_candidate(
        repo_path=tmp_path,
        candidate_plan=_plan(3),
        request=request,
    )

    assert result.status == VALIDATION_INCONCLUSIVE
    assert result.category == CATEGORY_CANDIDATE_FINGERPRINT_STALE


def test_targeted_timeout_is_inconclusive_not_test_failure(tmp_path, monkeypatch):
    _write_repo(tmp_path)
    request = _request(tmp_path)

    monkeypatch.setattr(
        targeted,
        "_run_check_set",
        lambda *_args, **_kwargs: TargetedCheckRun(
            outcome=VALIDATION_INCONCLUSIVE,
            category=CATEGORY_VALIDATION_BUDGET_EXHAUSTED,
            attempted=True,
            completed=False,
            timed_out=True,
            checks_executed=(),
        ),
    )
    result = validate_targeted_candidate(
        repo_path=tmp_path,
        candidate_plan=_plan(),
        request=request,
    )

    assert result.status == VALIDATION_INCONCLUSIVE
    assert result.category == CATEGORY_VALIDATION_BUDGET_EXHAUSTED


def test_missing_pytest_is_inconclusive_and_nothing_is_installed(tmp_path, monkeypatch):
    _write_repo(tmp_path)
    request = _request(tmp_path)
    monkeypatch.setattr(
        targeted,
        "run_safe_validation_command",
        lambda command: SafeValidationResult(
            ok=False,
            blocked=False,
            block_reason="",
            exit_code=1,
            stdout="",
            stderr="python: No module named pytest",
            timed_out=False,
            command=command.command,
            cwd=str(command.cwd),
            timeout_sec=command.timeout_sec,
            python_bytecode_cache_isolated=True,
        ),
    )

    run = targeted._run_check_set(tmp_path, request, timeout_seconds=2)

    assert run.outcome == VALIDATION_INCONCLUSIVE
    assert run.category == CATEGORY_VALIDATION_TOOL_UNAVAILABLE


def _probe_receipt() -> dict:
    digest = "a" * 64
    return {
        "probe_result": "reproduced",
        "execution_stage": "pre_patch",
        "probe_basis": "deterministic_task_fact_adapter",
        "input_basis": "deterministic_fixture_from_preserved_task_fact",
        "expected_behavior_basis": "preserved_task_fact_expected_behavior",
        "probe_freshness": "current_source_isolated_bytecode_cache",
        "executed_source_sha256": digest,
        "target_binding": {
            "file": "core/calc.py",
            "symbol": "calc",
            "localized_source_sha256": digest,
        },
    }


def _state(repo: Path, *, basis: str = PATCH_BASIS_GROUNDED_DEFECT) -> AgentState:
    state = AgentState(
        interface="agent",
        mode="control",
        user_input="Fix the reproduced calc defect",
        file_paths=[str(repo)],
        primary_file=None,
        input_mode="project",
        language="python",
        task_type="bug_fix",
        repo_path=str(repo),
        is_project_input=True,
        live_route={"selected_workflow": "defect_repair_patch"},
        repository_graph=_repo_graph(),
    )
    state.control_result = {
        "preflight_validation": {
            "outcome": "inconclusive",
            "category": "validation_budget_exhausted",
        },
        "defect_probe": _probe_receipt(),
    }
    state.json_block = {
        "patch_basis": basis,
        "patch_plan": _plan(),
        "execution_authorized": False,
        "write_authority": False,
    }
    return state


def test_production_trigger_records_targeted_and_preserves_full_and_authority(
    tmp_path, monkeypatch
):
    _write_repo(tmp_path)
    state = _state(tmp_path)
    policy = SimpleNamespace(patch_basis=PATCH_BASIS_GROUNDED_DEFECT)
    request = _request(tmp_path)
    fake = targeted.TargetedValidationResult(
        status=VALIDATION_PASSED,
        category=CATEGORY_TARGETED_CHECKS_PASSED,
        request=request,
        baseline_outcome=VALIDATION_PASSED,
        candidate_outcome=VALIDATION_PASSED,
    )
    oracle_calls = []
    fake_oracle = SimpleNamespace(
        as_telemetry=lambda: {
            "check_oracle_assessment_status": "current",
            "check_oracle_assessments": [],
            "check_oracle_authority_effect": "none",
        }
    )
    monkeypatch.setattr(pipeline, "validate_targeted_candidate", lambda **_kwargs: fake)
    monkeypatch.setattr(
        pipeline,
        "derive_control_defect_probe_contract",
        lambda _control: SimpleNamespace(fingerprint="f" * 64),
    )
    monkeypatch.setattr(
        pipeline,
        "assess_selected_check_oracles",
        lambda **kwargs: oracle_calls.append(kwargs) or fake_oracle,
    )
    monkeypatch.setattr(
        pipeline,
        "describe_check_oracle_assessment",
        lambda _receipt: "classified",
    )

    result = pipeline._record_targeted_repository_validation(
        state,
        policy,
        tmp_path,
        patch_safety={"ok": True},
    )

    assert result is fake
    assert state.json_block["targeted_validation_status"] == VALIDATION_PASSED
    assert state.json_block["full_validation_outcome"] == "inconclusive"
    assert state.json_block["full_validation_category"] == "validation_budget_exhausted"
    assert state.json_block["execution_authorized"] is False
    assert state.json_block["write_authority"] is False
    assert state.json_block["targeted_validation_authority_effect"] == "none"
    assert state.json_block["check_oracle_assessment_status"] == "current"
    assert state.json_block["check_oracle_authority_effect"] == "none"
    assert len(oracle_calls) == 1
    assert oracle_calls[0]["targeted_validation"] is fake
    assert oracle_calls[0]["full_validation"] == state.control_result["preflight_validation"]


def test_oracle_classifier_failure_cannot_rewrite_targeted_validation(
    tmp_path, monkeypatch
):
    _write_repo(tmp_path)
    state = _state(tmp_path)
    policy = SimpleNamespace(patch_basis=PATCH_BASIS_GROUNDED_DEFECT)
    fake = targeted.TargetedValidationResult(
        status=VALIDATION_PASSED,
        category=CATEGORY_TARGETED_CHECKS_PASSED,
        request=_request(tmp_path),
        baseline_outcome=VALIDATION_PASSED,
        candidate_outcome=VALIDATION_PASSED,
    )
    monkeypatch.setattr(pipeline, "validate_targeted_candidate", lambda **_kwargs: fake)
    monkeypatch.setattr(
        pipeline,
        "derive_control_defect_probe_contract",
        lambda _control: SimpleNamespace(fingerprint="f" * 64),
    )

    def unavailable_classifier(**_kwargs):
        raise RuntimeError("classifier unavailable")

    monkeypatch.setattr(
        pipeline,
        "assess_selected_check_oracles",
        unavailable_classifier,
    )

    result = pipeline._record_targeted_repository_validation(
        state,
        policy,
        tmp_path,
        patch_safety={"ok": True},
    )

    assert result is fake
    assert state.json_block["targeted_validation_status"] == VALIDATION_PASSED
    assert state.json_block["candidate_targeted_outcome"] == VALIDATION_PASSED
    assert state.json_block["check_oracle_assessment_status"] == "unavailable"
    assert state.json_block["check_oracle_authority_effect"] == "none"


@pytest.mark.parametrize(
    ("basis", "preflight"),
    [
        (PATCH_BASIS_EXPLICIT_CHANGE_REQUEST, ("inconclusive", "validation_budget_exhausted")),
    ],
)
def test_explicit_change_does_not_trigger_defect_targeted_validation(
    tmp_path, monkeypatch, basis, preflight
):
    _write_repo(tmp_path)
    state = _state(tmp_path, basis=basis)
    state.control_result["preflight_validation"] = {
        "outcome": preflight[0],
        "category": preflight[1],
    }
    called = False

    def fail_if_called(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("targeted validation must not run")

    monkeypatch.setattr(pipeline, "validate_targeted_candidate", fail_if_called)
    result = pipeline._record_targeted_repository_validation(
        state,
        SimpleNamespace(patch_basis=basis),
        tmp_path,
        patch_safety={"ok": True},
    )

    assert result is None
    assert called is False


def test_stale_targeted_telemetry_is_removed_without_touching_probe_or_full_receipt(tmp_path):
    _write_repo(tmp_path)
    state = _state(tmp_path)
    state.json_block.update(
        {
            "targeted_validation_status": "passed",
            "candidate_fingerprint": "0" * 64,
            "preflight_validation": {"outcome": "inconclusive"},
            "defect_probe": _probe_receipt(),
        }
    )

    pipeline._drop_stale_candidate_validation(state)

    assert "targeted_validation_status" not in state.json_block
    assert "candidate_fingerprint" not in state.json_block
    assert state.json_block["preflight_validation"]["outcome"] == "inconclusive"
    assert state.json_block["defect_probe"]["probe_result"] == "reproduced"


def test_guardrails_pin_no_authority_model_network_traversal_or_zero_test_pass():
    guardrails = targeted_validation_guardrails()

    assert guardrails["existing_repository_checks_only"] is True
    assert guardrails["same_check_set_before_after"] is True
    assert guardrails["zero_checks_can_pass"] is False
    assert guardrails["modified_test_can_validate_itself"] is False
    assert guardrails["model_generated_tests_accepted"] is False
    assert guardrails["probe_overrides_targeted_failure"] is False
    assert guardrails["targeted_rewrites_full_validation"] is False
    assert guardrails["execution_authority_granted"] is False
    assert guardrails["model_called"] is False
    assert guardrails["network_called"] is False
    assert guardrails["repository_traversal_added"] is False
    assert guardrails["global_timeout_changed"] is False


def test_production_caps_are_smaller_than_whole_repository_validation():
    assert DEFAULT_MAX_TARGETED_TEST_FILES == 3
    assert DEFAULT_MAX_TARGETED_TEST_NODES == 8
    assert DEFAULT_TARGETED_VALIDATION_BUDGET_SECONDS == 20


@pytest.mark.parametrize("preflight_outcome", ["passed", "failed", "inconclusive"])
def test_reproduced_defect_runs_targeted_evidence_independent_of_suite_outcome(
    tmp_path, monkeypatch, preflight_outcome
):
    _write_repo(tmp_path)
    state = _state(tmp_path)
    state.control_result["preflight_validation"] = {"outcome": preflight_outcome}
    calls = []

    def capture(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("test stops after proving the request reached the producer")

    monkeypatch.setattr(pipeline, "validate_targeted_candidate", capture)
    pipeline._record_targeted_repository_validation(
        state, SimpleNamespace(patch_basis=PATCH_BASIS_GROUNDED_DEFECT), tmp_path,
        patch_safety={"ok": True},
    )
    assert len(calls) == 1
    assert calls[0]["pre_patch_probe_result"] == "reproduced"
    assert state.json_block["targeted_validation_status"] == "inconclusive"


def test_reproduced_red_to_green_preserves_all_concrete_unchanged_checks(tmp_path):
    _write_repo(tmp_path, assertion="assert calc() == 2")
    check = tmp_path / "tests" / "test_calc.py"
    check.write_text(check.read_text() + "\ndef test_positive():\n    assert calc() > 0\n")
    before = _digest_tree(tmp_path)
    result = validate_targeted_candidate(
        repo_path=tmp_path, candidate_plan=_plan(2), request=build_targeted_validation_request(
            repo_path=tmp_path, candidate_plan=_plan(2), graph=_repo_graph(),
            changed_symbols=(TARGET,),
            preserved_user_command="python -m pytest tests/test_calc.py",
        ),
        pre_patch_probe_result="reproduced",
    )
    assert result.status == VALIDATION_PASSED
    assert result.category == targeted.CATEGORY_TARGETED_DEFECT_REPAIRED
    assert {outcome for _, outcome in result.baseline_concrete_cases} == {"assertion_failed", "passed"}
    assert {outcome for _, outcome in result.candidate_concrete_cases} == {"passed"}
    assert result.oracle_source_unchanged is True
    assert _digest_tree(tmp_path) == before


@pytest.mark.parametrize("evasion", ["skip", "deselect", "rewrite_oracle", "baseline_error"])
def test_red_to_green_requires_real_same_unchanged_assertions(tmp_path, evasion):
    _write_repo(tmp_path, assertion="assert calc() == 2")
    check = tmp_path / "tests" / "test_calc.py"
    if evasion == "skip":
        check.write_text("import pytest\nfrom core.calc import calc\n"
                         "def test_calc():\n    if calc() == 2:\n        pytest.skip('evaded')\n"
                         "    assert calc() == 2\n")
    elif evasion == "deselect":
        check.write_text(check.read_text() + "\ndef test_positive():\n    assert calc() > 0\n")
        (tmp_path / "conftest.py").write_text(
            "from core.calc import calc\n"
            "def pytest_collection_modifyitems(items):\n"
            "    if calc() == 2:\n"
            "        items[:] = [item for item in items if item.name == 'test_positive']\n")
    elif evasion == "rewrite_oracle":
        (tmp_path / "conftest.py").write_text(
            "import pytest\nfrom pathlib import Path\nfrom core.calc import calc\n"
            "@pytest.fixture(autouse=True)\n"
            "def rewrite():\n"
            "    if calc() == 2:\n"
            "        path = Path(__file__).parent / 'tests' / 'test_calc.py'\n"
            "        path.write_text(path.read_text() + '# rewritten oracle\\n')\n")
    else:
        check.write_text("from core.calc import calc\n"
                         "def test_calc():\n    if calc() == 1:\n        raise RuntimeError('infrastructure failed')\n"
                         "    assert calc() == 2\n")
    result = validate_targeted_candidate(
        repo_path=tmp_path, candidate_plan=_plan(2), request=build_targeted_validation_request(
            repo_path=tmp_path, candidate_plan=_plan(2), graph=_repo_graph(),
            changed_symbols=(TARGET,),
            preserved_user_command="python -m pytest tests/test_calc.py",
        ),
        pre_patch_probe_result="reproduced",
    )
    assert result.status != VALIDATION_PASSED
    assert result.category == CATEGORY_BASELINE_TARGETED_FAILED


@pytest.mark.parametrize("path_kind", ["absolute", "parent"])
def test_oracle_source_fingerprint_refuses_paths_outside_sandbox(tmp_path, path_kind):
    from dataclasses import replace
    _write_repo(tmp_path)
    request = _request(tmp_path)
    original = request.selected_checks[0]
    untrusted_path = str(tmp_path / "outside.py") if path_kind == "absolute" else "../outside.py"
    request = replace(request, selected_checks=(replace(original, path=untrusted_path),))
    assert targeted._oracle_source_fingerprint(tmp_path, request) == ""


def test_invalid_user_selectors_terminate_and_advance_to_following_valid_selector():
    import subprocess
    import sys
    from pathlib import Path
    # A process deadline makes a reintroduced infinite loop an ordinary failure.
    script = """
from types import SimpleNamespace
from core.targeted_repository_validation import _explicit_pytest_checks
nodes = {"tests/test_present.py": {}, "tests/test_present.py::test_known": {}}
graph = SimpleNamespace(nodes=nodes)
for missing in ("../test_outside.py", "tests/test_absent.py", "tests/test_present.py::test_absent"):
    command = "pytest " + missing + " tests/test_present.py::test_known"
    assert [check.identifier for check in _explicit_pytest_checks(graph, command)] == ["tests/test_present.py::test_known"]
"""
    completed = subprocess.run(
        [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
