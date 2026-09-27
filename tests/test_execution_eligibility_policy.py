from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import pipeline
from core.candidate_sandbox_validation import patch_plan_fingerprint
from core.execution_eligibility_policy import (
    BLOCK_CANDIDATE_FINGERPRINT_STALE,
    BLOCK_CANDIDATE_REGRESSION_ORACLE,
    BLOCK_FULL_VALIDATION_GENUINE_FAILURE,
    BLOCK_PATCH_SAFETY_NOT_PASSED,
    BLOCK_TARGETED_EVIDENCE_INVALID,
    BLOCK_UNRESOLVED_ORACLE_CONFLICT,
    ELIGIBLE,
    INCONSISTENT_INPUT,
    INELIGIBLE,
    INSUFFICIENT_EVIDENCE,
    LEGACY_UNASSESSED,
    PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    PROFILE_FULL_VALIDATION_REQUIRED,
    REQUIREMENT_IDS,
    describe_execution_eligibility,
    evaluate_execution_eligibility,
    execution_eligibility_guardrails,
    execution_eligibility_status_of_payload,
)


CANDIDATE = "a" * 64
PROBE = "b" * 64
CHECK_SET = "c" * 64
SOURCE = "d" * 64
CHECK_SOURCE_1 = "e" * 64
CHECK_SOURCE_2 = "f" * 64
CHECK_FINGERPRINT_1 = "1" * 64
CHECK_FINGERPRINT_2 = "2" * 64
CHECK_1 = "tests/test_indent.py::test_nested_indent"
CHECK_2 = "tests/test_indent.py::test_deep_indent"


def _assessment(check_id: str, *, source: str, fingerprint: str) -> dict:
    return {
        "check_id": check_id,
        "check_execution_outcome": "failed",
        "oracle_role": "defect_preservation_oracle",
        "probe_fingerprint": PROBE,
        "role_basis": "structured assertion preserves the observed broken result",
        "check_path": check_id.split("::", 1)[0],
        "check_source_sha256": source,
        "check_fingerprint": fingerprint,
        "candidate_fingerprint": CANDIDATE,
        "assessment_status": "current",
    }


def _t6_evidence() -> dict:
    return {
        "task_route": {"selected_workflow": "defect_repair_patch"},
        "patch_basis": "grounded_defect",
        "source_target_grounded": True,
        "candidate_fingerprint": CANDIDATE,
        "patch_safety": {"ok": True, "candidate_fingerprint": CANDIDATE},
        "full_validation": {
            "outcome": "inconclusive",
            "category": "validation_budget_exhausted",
        },
        "pre_probe": {
            "probe_result": "reproduced",
            "execution_stage": "pre_patch",
            "probe_basis": "deterministic_task_fact_adapter",
            "input_basis": "deterministic_fixture_from_preserved_task_fact",
            "expected_behavior_basis": "preserved_task_fact_expected_behavior",
            "probe_freshness": "current_source_isolated_bytecode_cache",
            "probe_fingerprint": PROBE,
            "executed_source_sha256": SOURCE,
            "target_binding": {
                "file": "core/code_dna.py",
                "symbol": "_classify_indent",
                "localized_source_sha256": SOURCE,
                "repository_identity": "existing-probe-repository-binding",
            },
        },
        "candidate_defect_closure": {
            "candidate_fingerprint": CANDIDATE,
            "probe_fingerprint": PROBE,
            "pre_probe_result": "reproduced",
            "post_probe_result": "not_reproduced",
            "defect_closure_status": "fixed",
            "sandbox_only": True,
            "candidate_probe_apply_status": "applied",
            "candidate_probe_sandbox_cleanup_ok": True,
        },
        "targeted_validation": {
            "targeted_validation_status": "failed",
            "targeted_validation_category": "assertion_failure",
            "candidate_fingerprint": CANDIDATE,
            "targeted_check_set_fingerprint": CHECK_SET,
            "selected_check_count": 2,
            "selected_checks": [CHECK_1, CHECK_2],
            "selection_complete": True,
            "baseline_targeted_outcome": "passed",
            "candidate_targeted_outcome": "failed",
            "targeted_validation_sandbox_cleanup_ok": True,
            "baseline_python_bytecode_cache_isolated": True,
            "candidate_python_bytecode_cache_isolated": True,
        },
        "oracle_assessment": {
            "check_oracle_assessment_status": "current",
            "check_oracle_probe_fingerprint": PROBE,
            "check_oracle_check_set_fingerprint": CHECK_SET,
            "check_oracle_candidate_fingerprint": CANDIDATE,
            "check_oracle_assessments": [
                _assessment(
                    CHECK_1,
                    source=CHECK_SOURCE_1,
                    fingerprint=CHECK_FINGERPRINT_1,
                ),
                _assessment(
                    CHECK_2,
                    source=CHECK_SOURCE_2,
                    fingerprint=CHECK_FINGERPRINT_2,
                ),
            ],
        },
        "execution_authorization": {
            "execution_authorized": False,
            "execution_authority_source": "none",
            "execution_authorization_denied_reason": "human_approval_required",
            "human_approval_required_for_execution": True,
            "execution_attempted": False,
            "patch_applied": False,
            "final_repository_changed": False,
        },
    }


def _profile(report, profile: str):
    return report.assessment_for(profile)


def test_t6_timeout_and_failed_defect_preservation_checks_are_human_review_eligible():
    evidence = _t6_evidence()
    original = deepcopy(evidence)

    report = evaluate_execution_eligibility(evidence)
    strict = _profile(report, PROFILE_FULL_VALIDATION_REQUIRED)
    bounded = _profile(report, PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW)

    assert strict.eligibility_status == INELIGIBLE
    assert bounded.eligibility_status == ELIGIBLE
    assert report.human_review_eligible is True
    assert bounded.accepted_conflicts == ("defect_preservation_oracle",)
    assert bounded.accepted_limitations == ("full_validation_budget_exhausted",)
    assert evidence == original
    assert evidence["targeted_validation"]["targeted_validation_status"] == "failed"
    assert evidence["full_validation"]["outcome"] == "inconclusive"
    assert "not been authorized or applied" in describe_execution_eligibility(report)


def test_evaluator_is_deterministic_and_uses_only_closed_result_vocabularies():
    first = evaluate_execution_eligibility(_t6_evidence())
    second = evaluate_execution_eligibility(_t6_evidence())

    assert first == second
    assert first.as_telemetry() == second.as_telemetry()
    for assessment in first.assessments:
        assert set(assessment.satisfied_requirements) <= set(REQUIREMENT_IDS)
        assert set(assessment.unsatisfied_requirements) <= set(REQUIREMENT_IDS)
        assert "confidence" not in assessment.as_dict()


def test_candidate_regression_oracle_failure_blocks_bounded_profile():
    evidence = _t6_evidence()
    evidence["oracle_assessment"]["check_oracle_assessments"][0][
        "oracle_role"
    ] = "candidate_regression_oracle"

    bounded = _profile(
        evaluate_execution_eligibility(evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )

    assert bounded.eligibility_status == INELIGIBLE
    assert BLOCK_CANDIDATE_REGRESSION_ORACLE in bounded.blocking_reasons
    assert bounded.accepted_conflicts == ()


@pytest.mark.parametrize(
    "role",
    ["conflict_unresolved", "insufficient_basis", "unrelated"],
)
def test_unresolved_or_possibly_regressive_failed_check_cannot_be_ignored(role):
    evidence = _t6_evidence()
    evidence["oracle_assessment"]["check_oracle_assessments"][0][
        "oracle_role"
    ] = role

    bounded = _profile(
        evaluate_execution_eligibility(evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )

    assert bounded.eligibility_status == INSUFFICIENT_EVIDENCE
    assert BLOCK_UNRESOLVED_ORACLE_CONFLICT in bounded.blocking_reasons
    assert bounded.accepted_conflicts == ()


@pytest.mark.parametrize(
    ("category", "oracle_status"),
    [
        ("selected_validation_check_modified", "current"),
        ("assertion_failure", "candidate_modified_check"),
    ],
)
def test_tampered_selected_validation_evidence_is_a_hard_block(
    category, oracle_status
):
    evidence = _t6_evidence()
    evidence["targeted_validation"].update(
        {
            "targeted_validation_status": (
                "inconclusive"
                if category == "selected_validation_check_modified"
                else "failed"
            ),
            "targeted_validation_category": category,
            "candidate_targeted_outcome": (
                "targeted_validation_not_run"
                if category == "selected_validation_check_modified"
                else "failed"
            ),
        }
    )
    evidence["oracle_assessment"][
        "check_oracle_assessment_status"
    ] = oracle_status

    bounded = _profile(
        evaluate_execution_eligibility(evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )

    assert bounded.eligibility_status == INELIGIBLE
    assert BLOCK_TARGETED_EVIDENCE_INVALID in bounded.blocking_reasons


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("probe_basis", "model_authored"),
        ("input_basis", "model_authored_input"),
        ("expected_behavior_basis", "model_authored_expectation"),
    ],
)
def test_model_only_probe_oracle_provenance_cannot_qualify(field, value):
    evidence = _t6_evidence()
    evidence["pre_probe"][field] = value

    bounded = _profile(
        evaluate_execution_eligibility(evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )

    assert bounded.eligibility_status == INELIGIBLE
    assert "probe_provenance_not_independent" in bounded.blocking_reasons


@pytest.mark.parametrize(
    ("closure_status", "post_result", "expected_status"),
    [
        ("still_reproduced", "reproduced", INELIGIBLE),
        ("changed_but_unresolved", "reproduced", INELIGIBLE),
        ("inconclusive", "inconclusive", INSUFFICIENT_EVIDENCE),
    ],
)
def test_probe_not_fixed_never_qualifies(
    closure_status, post_result, expected_status
):
    evidence = _t6_evidence()
    evidence["candidate_defect_closure"].update(
        {
            "defect_closure_status": closure_status,
            "post_probe_result": post_result,
        }
    )

    bounded = _profile(
        evaluate_execution_eligibility(evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )

    assert bounded.eligibility_status == expected_status
    assert "post_probe_not_fixed" in bounded.blocking_reasons


def test_full_suite_genuine_failure_cannot_be_overridden_by_targeted_evidence():
    evidence = _t6_evidence()
    evidence["full_validation"] = {
        "outcome": "failed",
        "category": "assertion_failure",
    }

    bounded = _profile(
        evaluate_execution_eligibility(evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )

    assert bounded.eligibility_status == INELIGIBLE
    assert BLOCK_FULL_VALIDATION_GENUINE_FAILURE in bounded.blocking_reasons
    assert bounded.accepted_limitations == ()


@pytest.mark.parametrize("category", ["missing_tool", "invalid_command", "sandbox_unavailable"])
def test_only_budget_exhaustion_is_an_accepted_full_validation_limitation(category):
    evidence = _t6_evidence()
    evidence["full_validation"]["category"] = category

    bounded = _profile(
        evaluate_execution_eligibility(evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )

    assert bounded.eligibility_status == INSUFFICIENT_EVIDENCE
    assert bounded.accepted_limitations == ()


def test_patch_safety_failure_blocks_both_profiles():
    evidence = _t6_evidence()
    evidence["full_validation"] = {"outcome": "passed", "category": "passed"}
    evidence["patch_safety"]["ok"] = False

    report = evaluate_execution_eligibility(evidence)

    for assessment in report.assessments:
        assert assessment.eligibility_status == INELIGIBLE
        assert BLOCK_PATCH_SAFETY_NOT_PASSED in assessment.blocking_reasons


@pytest.mark.parametrize(
    "location",
    ["patch_safety", "candidate_defect_closure", "targeted_validation", "oracle_assessment"],
)
def test_candidate_fingerprint_mismatch_is_inconsistent_input(location):
    evidence = _t6_evidence()
    key = {
        "patch_safety": "candidate_fingerprint",
        "candidate_defect_closure": "candidate_fingerprint",
        "targeted_validation": "candidate_fingerprint",
        "oracle_assessment": "check_oracle_candidate_fingerprint",
    }[location]
    evidence[location][key] = "9" * 64

    bounded = _profile(
        evaluate_execution_eligibility(evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )

    assert bounded.eligibility_status == INCONSISTENT_INPUT
    assert BLOCK_CANDIDATE_FINGERPRINT_STALE in bounded.blocking_reasons


def test_probe_and_check_set_fingerprint_mismatches_invalidate_eligibility():
    probe_evidence = _t6_evidence()
    probe_evidence["candidate_defect_closure"]["probe_fingerprint"] = "8" * 64
    probe_status = _profile(
        evaluate_execution_eligibility(probe_evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )
    assert probe_status.eligibility_status == INCONSISTENT_INPUT
    assert "probe_fingerprint_mismatch" in probe_status.blocking_reasons

    check_evidence = _t6_evidence()
    check_evidence["oracle_assessment"][
        "check_oracle_check_set_fingerprint"
    ] = "7" * 64
    check_status = _profile(
        evaluate_execution_eligibility(check_evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )
    assert check_status.eligibility_status == INCONSISTENT_INPUT
    assert "targeted_check_set_fingerprint_mismatch" in check_status.blocking_reasons


def test_stale_source_or_repository_identity_is_inconsistent_input():
    source_evidence = _t6_evidence()
    source_evidence["pre_probe"]["executed_source_sha256"] = "6" * 64
    source_status = _profile(
        evaluate_execution_eligibility(source_evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )
    assert source_status.eligibility_status == INCONSISTENT_INPUT

    repository_evidence = _t6_evidence()
    repository_evidence["targeted_validation"][
        "targeted_validation_category"
    ] = "repository_identity_mismatch"
    repository_status = _profile(
        evaluate_execution_eligibility(repository_evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )
    assert repository_status.eligibility_status == INCONSISTENT_INPUT


def test_missing_evidence_is_insufficient_and_never_eligible():
    evidence = _t6_evidence()
    evidence.pop("candidate_defect_closure")

    bounded = _profile(
        evaluate_execution_eligibility(evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )

    assert bounded.eligibility_status == INSUFFICIENT_EVIDENCE
    assert "required_evidence_missing" in bounded.blocking_reasons


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("candidate_fingerprint", "", "candidate_missing"),
        ("patch_basis", "none", "patch_basis_not_grounded_defect"),
        ("task_route", {"selected_workflow": "analysis_only"}, "task_route_not_defect_repair"),
    ],
)
def test_no_candidate_no_patch_basis_and_analysis_route_are_ineligible(
    field, value, reason
):
    evidence = _t6_evidence()
    evidence[field] = value

    bounded = _profile(
        evaluate_execution_eligibility(evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )

    assert bounded.eligibility_status == INELIGIBLE
    assert reason in bounded.blocking_reasons


def test_eligible_does_not_mean_authorized_or_approved():
    evidence = _t6_evidence()
    report = evaluate_execution_eligibility(evidence)
    telemetry = report.as_telemetry()

    assert telemetry["human_review_eligible"] is True
    assert telemetry["execution_eligibility_authority_effect"] == "none"
    assert telemetry["execution_eligibility_auto_apply_effect"] == "none"
    assert evidence["execution_authorization"]["execution_authorized"] is False
    assert evidence["execution_authorization"][
        "human_approval_required_for_execution"
    ] is True


def test_independent_execution_safety_denial_blocks_review_eligibility():
    evidence = _t6_evidence()
    evidence["execution_authorization"][
        "execution_authorization_denied_reason"
    ] = "unsafe_validation_command"

    bounded = _profile(
        evaluate_execution_eligibility(evidence),
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )

    assert bounded.eligibility_status == INELIGIBLE
    assert "independent_execution_safety_denial" in bounded.blocking_reasons


def test_full_validation_required_accepts_only_an_actual_pass():
    evidence = _t6_evidence()
    evidence["full_validation"] = {"outcome": "passed", "category": "passed"}

    strict = _profile(
        evaluate_execution_eligibility(evidence),
        PROFILE_FULL_VALIDATION_REQUIRED,
    )

    assert strict.eligibility_status == ELIGIBLE
    assert "full_validation_passed" in strict.satisfied_requirements


def test_historical_artifact_without_receipt_is_legacy_unassessed_not_eligible():
    assert execution_eligibility_status_of_payload({"patch_basis": "grounded_defect"}) == (
        LEGACY_UNASSESSED
    )
    report = evaluate_execution_eligibility(_t6_evidence())
    assert execution_eligibility_status_of_payload(report.as_telemetry()) == ELIGIBLE


def test_live_adapter_attaches_eligibility_without_widening_authority():
    plan = [
        {
            "op": "replace_snippet",
            "relative_path": "core/code_dna.py",
            "target_snippet": "old",
            "patched_snippet": "new",
        }
    ]
    candidate = patch_plan_fingerprint(plan)
    evidence = _t6_evidence()

    def rebind(value):
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if key in {
                    "candidate_fingerprint",
                    "check_oracle_candidate_fingerprint",
                } and item == CANDIDATE:
                    value[key] = candidate
                else:
                    rebind(item)
        elif isinstance(value, list):
            for item in value:
                rebind(item)

    rebind(evidence)
    block = {
        "patch_plan": plan,
        "patch_basis": "grounded_defect",
        "target_source_grounded": True,
        "auto_apply_allowed": False,
        "execution_authorized": False,
        "execution_authority_source": "none",
        "execution_authorization_denied_reason": "human_approval_required",
        "human_approval_required_for_execution": True,
        "execution_attempted": False,
        "patch_applied": False,
        "final_repository_changed": False,
        **evidence["candidate_defect_closure"],
        **evidence["targeted_validation"],
        **evidence["oracle_assessment"],
    }
    state = SimpleNamespace(
        json_block=block,
        patch_policy={},
        control_result={
            "live_route": evidence["task_route"],
            "preflight_validation": evidence["full_validation"],
            "defect_probe": evidence["pre_probe"],
        },
        live_route=evidence["task_route"],
    )

    report = pipeline._record_execution_eligibility(
        state,
        SimpleNamespace(patch_basis="grounded_defect"),
        patch_safety={"ok": True},
    )

    assert report is not None
    assert state.json_block["human_review_eligible"] is True
    assert state.json_block["execution_authorized"] is False
    assert state.json_block["auto_apply_allowed"] is False
    assert state.json_block["patch_applied"] is False
    assert state.json_block["final_repository_changed"] is False
    assert state.json_block["human_approval_required_for_execution"] is True


def test_refined_candidate_drops_only_candidate_bound_policy_receipt():
    old_plan = [
        {
            "op": "replace_snippet",
            "relative_path": "x.py",
            "target_snippet": "a",
            "patched_snippet": "b",
        }
    ]
    new_plan = [
        {
            "op": "replace_snippet",
            "relative_path": "x.py",
            "target_snippet": "a",
            "patched_snippet": "c",
        }
    ]
    state = SimpleNamespace(
        json_block={
            "patch_plan": new_plan,
            "execution_eligibility_status": ELIGIBLE,
            "execution_eligibility_candidate_fingerprint": patch_plan_fingerprint(
                old_plan
            ),
            "human_review_eligible": True,
            "execution_authorized": False,
            "full_validation_outcome": "inconclusive",
        },
        patch_policy={"human_review_eligible": True},
    )

    pipeline._drop_stale_candidate_validation(state)

    assert "execution_eligibility_status" not in state.json_block
    assert "human_review_eligible" not in state.json_block
    assert state.json_block["execution_authorized"] is False
    assert state.json_block["full_validation_outcome"] == "inconclusive"


def test_guardrails_and_source_pin_zero_io_model_network_validation_and_authority():
    guardrails = execution_eligibility_guardrails()
    assert guardrails == {
        "pure_evidence_reduction": True,
        "failed_validation_rewritten": False,
        "full_validation_rewritten": False,
        "targeted_validation_rewritten": False,
        "defect_probe_rewritten": False,
        "patch_safety_overridden": False,
        "execution_authority_granted": False,
        "auto_apply_granted": False,
        "human_approval_bypassed": False,
        "evidence_generated": False,
        "validation_called": False,
        "retrieval_called": False,
        "repository_traversed": False,
        "model_called": False,
        "network_called": False,
    }

    source = Path("core/execution_eligibility_policy.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not imports.intersection(
        {"os", "pathlib", "subprocess", "socket", "requests", "urllib", "agents"}
    )

