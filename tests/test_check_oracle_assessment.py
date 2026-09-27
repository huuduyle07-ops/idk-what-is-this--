from __future__ import annotations

from dataclasses import replace
import inspect
from pathlib import Path

import core.check_oracle_assessment as oracle
from core.check_oracle_assessment import (
    ASSESSMENT_CURRENT,
    ASSESSMENT_INVALIDATED_CHECK,
    ASSESSMENT_STALE_CHECK,
    ASSESSMENT_STALE_PROBE,
    CHECK_FAILED,
    CHECK_NOT_RUN,
    ROLE_CANDIDATE_REGRESSION_ORACLE,
    ROLE_CONFLICT_UNRESOLVED,
    ROLE_DEFECT_PRESERVATION_ORACLE,
    ROLE_INSUFFICIENT_BASIS,
    ROLE_UNRELATED,
    assess_selected_check_oracles,
    check_oracle_assessment_freshness,
    check_oracle_assessment_is_current,
    check_oracle_guardrails,
)
from core.defect_probe import (
    EXPECTATION_BASIS_EXISTING_TEST,
    EXPECTATION_BASIS_MODEL_AUTHORED,
    EXPECTATION_BASIS_REPOSITORY_CONTRACT,
    INPUT_BASIS_EXISTING_TEST,
    INPUT_BASIS_REPOSITORY_CONTRACT,
    PROBE_BASIS_EXISTING_TEST,
    PROBE_BASIS_REPOSITORY_CONTRACT,
    build_probe_target_binding,
    build_python_function_probe,
)
from core.targeted_repository_validation import (
    TargetedValidationResult,
    build_targeted_validation_request,
)
from core.validation_outcome import VALIDATION_FAILED, VALIDATION_PASSED
from graph.schema import build_graph


TARGET = "calc.py::add"
CHECK = "tests/test_calc.py::test_add"


def _write_case(repo: Path, assertion: str) -> None:
    (repo / "tests").mkdir(parents=True, exist_ok=True)
    (repo / "calc.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_calc.py").write_text(
        "from calc import add\n\n"
        "def test_add():\n"
        f"    {assertion}\n",
        encoding="utf-8",
    )


def _graph():
    return build_graph(
        [
            {"id": "calc.py", "type": "file"},
            {"id": TARGET, "type": "function", "file": "calc.py"},
            {"id": "tests/test_calc.py", "type": "file"},
            {"id": CHECK, "type": "function", "file": "tests/test_calc.py"},
        ],
        [{"source": CHECK, "target": TARGET, "type": "resolved_call"}],
    )


def _plan(*, path: str = "calc.py") -> list[dict]:
    if path == "calc.py":
        return [
            {
                "op": "replace_snippet",
                "relative_path": path,
                "target_snippet": "    return a + b\n",
                "patched_snippet": "    return a - b\n",
            }
        ]
    return [
        {
            "op": "replace_snippet",
            "relative_path": path,
            "target_snippet": "    assert add(2, 2) == 4\n",
            "patched_snippet": "    assert add(2, 2) == 5\n",
        }
    ]


def _contract(repo: Path, *, expected=4, source_paths=()):
    source = (repo / "calc.py").read_text(encoding="utf-8")
    binding = build_probe_target_binding(
        repo_path=repo,
        target_file="calc.py",
        target_symbol="add",
        source_snippet=source.strip(),
        candidate_eligible=True,
    )
    assert binding is not None
    return build_python_function_probe(
        target=binding,
        args=(2, 2),
        expected=expected,
        probe_basis=(
            PROBE_BASIS_EXISTING_TEST
            if source_paths
            else PROBE_BASIS_REPOSITORY_CONTRACT
        ),
        input_basis=(
            INPUT_BASIS_EXISTING_TEST
            if source_paths
            else INPUT_BASIS_REPOSITORY_CONTRACT
        ),
        expected_behavior_basis=(
            EXPECTATION_BASIS_EXISTING_TEST
            if source_paths
            else EXPECTATION_BASIS_REPOSITORY_CONTRACT
        ),
        provenance_reference="independent arithmetic contract",
        expectation_source_paths=source_paths,
    )


def _targeted(
    repo: Path,
    *,
    plan: list[dict] | None = None,
    candidate_outcome: str = VALIDATION_FAILED,
    output: str | None = None,
) -> TargetedValidationResult:
    chosen_plan = plan or _plan()
    request = build_targeted_validation_request(
        repo_path=repo,
        candidate_plan=chosen_plan,
        graph=_graph(),
        changed_symbols=(TARGET,),
    )
    executed = () if "tests/test_calc.py" in request.changed_paths else (CHECK,)
    return TargetedValidationResult(
        status=candidate_outcome,
        category=("assertion_failure" if candidate_outcome == VALIDATION_FAILED else "targeted_checks_passed"),
        request=request,
        baseline_outcome=VALIDATION_PASSED,
        candidate_outcome=candidate_outcome,
        baseline_checks_executed=(CHECK,),
        candidate_checks_executed=executed,
        pre_patch_probe_result="reproduced",
        output_excerpt=(
            output
            if output is not None
            else f"FAILED {CHECK} - assert 0 == 4\n"
        ),
    )


def _assess(repo: Path, *, expected=4, plan=None, candidate_outcome=VALIDATION_FAILED):
    contract = _contract(repo, expected=expected)
    targeted = _targeted(
        repo,
        plan=plan,
        candidate_outcome=candidate_outcome,
    )
    closure = {
        "probe_fingerprint": contract.fingerprint,
        "candidate_fingerprint": targeted.request.candidate_fingerprint,
        "pre_probe_result": "reproduced",
        "pre_probe_observed": 5,
        "post_probe_result": "not_reproduced",
        "post_probe_observed": expected,
        "defect_closure_status": "fixed",
    }
    receipt = assess_selected_check_oracles(
        repo_path=repo,
        probe_contract=contract,
        targeted_validation=targeted,
        defect_closure=closure,
        full_validation={
            "outcome": "inconclusive",
            "category": "validation_budget_exhausted",
        },
    )
    return contract, targeted, receipt


def test_compatible_simple_equality_is_candidate_regression_oracle_and_failure_stays_failed(tmp_path):
    _write_case(tmp_path, "assert add(2, 2) == 4")
    _contract_value, targeted, receipt = _assess(tmp_path)
    assessment = receipt.assessments[0]

    assert assessment.oracle_role == ROLE_CANDIDATE_REGRESSION_ORACLE
    assert assessment.check_execution_outcome == CHECK_FAILED
    assert assessment.assessment_status == ASSESSMENT_CURRENT
    assert targeted.status == VALIDATION_FAILED
    assert receipt.evidence_matrix["targeted_validation"]["outcome"] == VALIDATION_FAILED
    assert receipt.evidence_matrix["post_probe"] == {
        "result": "not_reproduced",
        "observed": 4,
        "defect_closure_status": "fixed",
    }
    assert receipt.evidence_matrix["full_validation"] == {
        "outcome": "inconclusive",
        "category": "validation_budget_exhausted",
    }


def test_conflicting_simple_equality_is_defect_preservation_oracle(tmp_path):
    _write_case(tmp_path, "assert add(2, 2) == 5")
    _contract_value, _targeted_value, receipt = _assess(tmp_path)

    assert receipt.assessments[0].oracle_role == ROLE_DEFECT_PRESERVATION_ORACLE
    assert "conflicts with desired behavior" in receipt.assessments[0].role_basis


def test_conflicting_simple_inequality_is_defect_preservation_oracle(tmp_path):
    _write_case(tmp_path, "assert add(2, 2) != 4")
    _contract_value, _targeted_value, receipt = _assess(tmp_path)

    assert receipt.assessments[0].oracle_role == ROLE_DEFECT_PRESERVATION_ORACLE


def test_different_bounded_input_is_unrelated_even_when_selected_check_failed(tmp_path):
    _write_case(tmp_path, "assert add(3, 2) == 5")
    _contract_value, _targeted_value, receipt = _assess(tmp_path)

    assessment = receipt.assessments[0]
    assert assessment.oracle_role == ROLE_UNRELATED
    assert assessment.check_execution_outcome == CHECK_FAILED


def test_complex_target_assertion_is_unresolved_not_guessed(tmp_path):
    _write_case(tmp_path, "assert int(add(2, 2)) == 4")
    _contract_value, _targeted_value, receipt = _assess(tmp_path)

    assert receipt.assessments[0].oracle_role == ROLE_CONFLICT_UNRESOLVED


def test_model_only_desired_behavior_is_insufficient_basis(tmp_path):
    _write_case(tmp_path, "assert add(2, 2) == 4")
    contract = replace(
        _contract(tmp_path),
        expected_behavior_basis=EXPECTATION_BASIS_MODEL_AUTHORED,
    )
    targeted = _targeted(tmp_path)
    receipt = assess_selected_check_oracles(
        repo_path=tmp_path,
        probe_contract=contract,
        targeted_validation=targeted,
    )

    assert receipt.assessments[0].oracle_role == ROLE_INSUFFICIENT_BASIS


def test_test_cannot_supply_both_probe_expectation_and_independent_comparator(tmp_path):
    _write_case(tmp_path, "assert add(2, 2) == 4")
    contract = _contract(tmp_path, source_paths=("tests/test_calc.py",))
    targeted = _targeted(tmp_path)
    receipt = assess_selected_check_oracles(
        repo_path=tmp_path,
        probe_contract=contract,
        targeted_validation=targeted,
    )

    assert receipt.assessments[0].oracle_role == ROLE_INSUFFICIENT_BASIS


def test_candidate_modified_or_generated_selected_test_remains_invalid(tmp_path):
    _write_case(tmp_path, "assert add(2, 2) == 4")
    plan = _plan(path="tests/test_calc.py")
    _contract_value, targeted, receipt = _assess(tmp_path, plan=plan)
    assessment = receipt.assessments[0]

    assert assessment.assessment_status == ASSESSMENT_INVALIDATED_CHECK
    assert assessment.oracle_role == ROLE_INSUFFICIENT_BASIS
    assert assessment.check_execution_outcome == CHECK_NOT_RUN
    assert targeted.status == VALIDATION_FAILED


def test_recorded_probe_fingerprint_change_marks_assessment_stale(tmp_path):
    _write_case(tmp_path, "assert add(2, 2) == 4")
    contract = _contract(tmp_path)
    targeted = _targeted(tmp_path)
    receipt = assess_selected_check_oracles(
        repo_path=tmp_path,
        probe_contract=contract,
        targeted_validation=targeted,
        defect_closure={"probe_fingerprint": "0" * 64},
    )

    assert receipt.assessment_status == ASSESSMENT_STALE_PROBE
    assert receipt.assessments[0].assessment_status == ASSESSMENT_STALE_PROBE
    assert receipt.assessments[0].oracle_role == ROLE_INSUFFICIENT_BASIS


def test_probe_or_selected_test_state_change_makes_prior_assessment_not_current(tmp_path):
    _write_case(tmp_path, "assert add(2, 2) == 4")
    contract, _targeted_value, receipt = _assess(tmp_path)
    assessment = receipt.assessments[0]

    assert check_oracle_assessment_is_current(
        assessment,
        probe_contract=contract,
        repo_path=tmp_path,
    ) is True
    changed_contract = replace(contract, expected_json="5")
    assert check_oracle_assessment_freshness(
        assessment,
        probe_contract=changed_contract,
        repo_path=tmp_path,
    ) == ASSESSMENT_STALE_PROBE
    assert check_oracle_assessment_is_current(
        assessment,
        probe_contract=changed_contract,
        repo_path=tmp_path,
    ) is False
    (tmp_path / "tests" / "test_calc.py").write_text(
        "from calc import add\n\ndef test_add():\n    assert add(2, 2) == 5\n",
        encoding="utf-8",
    )
    assert check_oracle_assessment_freshness(
        assessment,
        probe_contract=contract,
        repo_path=tmp_path,
    ) == ASSESSMENT_STALE_CHECK
    assert check_oracle_assessment_is_current(
        assessment,
        probe_contract=contract,
        repo_path=tmp_path,
    ) is False


def test_guardrails_and_source_pin_no_policy_retrieval_model_network_or_execution():
    guardrails = check_oracle_guardrails()
    assert guardrails["check_execution_rewritten"] is False
    assert guardrails["targeted_validation_rewritten"] is False
    assert guardrails["full_validation_rewritten"] is False
    assert guardrails["post_probe_rewritten"] is False
    assert guardrails["candidate_modified_check_rehabilitated"] is False
    assert guardrails["test_name_heuristics_used"] is False
    assert guardrails["patch_authority_granted"] is False
    assert guardrails["execution_authority_granted"] is False
    assert guardrails["auto_apply_granted"] is False
    assert guardrails["retrieval_changed"] is False
    assert guardrails["model_called"] is False
    assert guardrails["network_called"] is False
    assert guardrails["repository_traversed"] is False

    source = inspect.getsource(oracle)
    for forbidden in (
        "run_safe_validation_command",
        "create_managed_sandbox",
        "apply_patch_plan",
        "run_gemini_request",
        "run_deepseek_review",
        "requests.",
        "httpx.",
        ".rglob(",
        "os.walk(",
    ):
        assert forbidden not in source
