"""INPUT.3 — deterministic completion policy tests.

The policy has one job: say whether an understood order is complete enough to
hand off, and when it is not, say *who* owns the problem.  These tests pin the
state vocabulary, the precedence, the ownership split between the user and the
system, and the invariants that stop a READY verdict from being assembled by
hand.
"""

from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path

import pytest

from core.input_understanding import understand_request
from core.intake_completion import (
    COMPLETION_OWNERS,
    COMPLETION_STATES,
    HANDOFF_BLOCKER_PRESERVATION_FAILED,
    HANDOFF_BLOCKER_SEMANTIC_RECEIPT_INVALID,
    HANDOFF_BLOCKER_SEMANTIC_RECEIPT_MISSING,
    OPERATIONAL_TASK_TYPES,
    OWNER_EXPLICIT_CONSTRAINT_CONFLICT,
    OWNER_OPERATIONAL_DETAIL_MISSING,
    OWNER_SEMANTIC_SYSTEM_FAILURE,
    OWNER_USER_MEANING_AMBIGUITY,
    REASON_CONFLICTING_OUTPUT_FORMATS,
    REASON_EXPLICIT_CONSTRAINT_CONFLICT,
    REASON_INTAKE_SUFFICIENT,
    REASON_NO_CONTRACT,
    REASON_OPERATIONAL_DETAIL_MISSING,
    REASON_OUTPUT_REPRESENTATION_LIMIT,
    REASON_PRESERVATION_FAILED,
    REASON_SEMANTIC_STATUS_FAILED,
    REASON_SEMANTIC_STATUS_UNRECOGNISED,
    REASON_UNRESOLVED_MEANING,
    SEMANTIC_EVIDENCE_INVALID,
    SEMANTIC_EVIDENCE_MISSING,
    SEMANTIC_EVIDENCE_VALID,
    SEMANTIC_STATUS_NOT_RUN,
    SEVERITY_SUGGESTED,
    STATE_ASK_CLARIFICATION,
    STATE_BLOCKED_CONTRADICTION,
    STATE_GOAL_BRIEF_ASSIST,
    STATE_READY,
    STATE_SEMANTIC_SYSTEM_FAILURE,
    ClarificationNeed,
    CompletionDecision,
    MissingRequirement,
    collect_missing_requirements,
    decide_from_semantic_outcome,
    decide_intake_completion,
    detect_explicit_contradictions,
    intake_authority,
    is_broad_operational_task,
    render_completion_decision_json,
)
from core.semantic_waiter import SemanticInterpretation, StaticSemanticInterpreter
from core.semantic_waiter_runner import (
    SEMANTIC_DETERMINISTIC_FALLBACK,
    SEMANTIC_INTERPRETATION_FAILED,
    SEMANTIC_INTERPRETATION_OK,
    SEMANTIC_INTERPRETATION_REPAIRED,
    SEMANTIC_MODEL_UNAVAILABLE,
    SEMANTIC_OUTPUT_INVALID,
    SemanticWaiterOutcome,
    SemanticWaiterReceipt,
)
from core.task_contract import (
    PRESERVATION_FAILED,
    PRESERVATION_PASSED,
    PROVENANCE_EXPLICIT,
    PROVENANCE_INFERRED,
    ExecutionRequirements,
    Relationship,
    Subject,
    TaskClassification,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: The modules whose decisions must never depend on a model.
INPUT_3_POLICY_MODULES = (
    "intake_completion",
    "goal_brief_projection",
    "intake_assistant",
    "input_completion",
)


def _interpretation(**kwargs) -> SemanticInterpretation:
    kwargs.setdefault(
        "task", TaskClassification(type="unknown", provenance=PROVENANCE_INFERRED)
    )
    return SemanticInterpretation(**kwargs)


def _contract(text: str, **kwargs):
    """A contract whose interpretation is dictated, not modelled."""
    return understand_request(
        text, interpreter=StaticSemanticInterpreter(_interpretation(**kwargs))
    )


def _broad_implementation(text: str, **kwargs):
    kwargs.setdefault(
        "task", TaskClassification(type="implementation", provenance=PROVENANCE_INFERRED)
    )
    kwargs.setdefault(
        "execution_requirements",
        ExecutionRequirements(
            multi_stage=True,
            repository_inspection_required=True,
            local_repository_required=True,
            provenance=PROVENANCE_INFERRED,
        ),
    )
    return _contract(text, **kwargs)


def _receipt(
    status: str = SEMANTIC_INTERPRETATION_OK,
    *,
    final_status: str | None = None,
    structured_output_valid: bool = True,
    fallback_used: bool = False,
) -> SemanticWaiterReceipt:
    """A bounded INPUT.2 receipt for INPUT.3 handoff tests."""
    if status == SEMANTIC_INTERPRETATION_REPAIRED:
        first_attempt_status = "preservation_failed"
        repair_attempted = True
        repair_status = "ok"
        attempt_count = 2
    elif status == SEMANTIC_MODEL_UNAVAILABLE:
        first_attempt_status = "model_unavailable"
        repair_attempted = False
        repair_status = None
        attempt_count = 1
    elif status == SEMANTIC_OUTPUT_INVALID:
        first_attempt_status = "output_invalid"
        repair_attempted = False
        repair_status = None
        attempt_count = 1
    else:
        first_attempt_status = "ok"
        repair_attempted = False
        repair_status = None
        attempt_count = 1
    return SemanticWaiterReceipt(
        adapter_name="test-semantic-adapter",
        configured_model="test-semantic-model",
        final_status=final_status or status,
        first_attempt_status=first_attempt_status,
        attempt_count=attempt_count,
        model_call_count=attempt_count,
        repair_attempted=repair_attempted,
        repair_status=repair_status,
        structured_output_valid=structured_output_valid,
        fallback_used=fallback_used,
    )


def _receipt_backed_decision(
    contract,
    status: str = SEMANTIC_INTERPRETATION_OK,
    *,
    receipt: SemanticWaiterReceipt | None = None,
):
    return decide_from_semantic_outcome(
        SemanticWaiterOutcome(
            status=status,
            receipt=receipt or _receipt(status),
            contract=contract,
        )
    )


# ══ vocabulary ════════════════════════════════════════════════════════════════

def test_the_state_set_is_small_and_stable():
    assert COMPLETION_STATES == (
        "ready",
        "goal_brief_assist",
        "ask_clarification",
        "blocked_contradiction",
        "semantic_system_failure",
    )


def test_the_owner_vocabulary_is_bounded():
    assert COMPLETION_OWNERS == (
        "user_meaning_ambiguity",
        "operational_detail_missing",
        "semantic_system_failure",
        "explicit_constraint_conflict",
    )


# ══ decision invariants ═══════════════════════════════════════════════════════

def test_handoff_readiness_is_derived_and_cannot_be_set_independently():
    decision = CompletionDecision(
        state=STATE_READY,
        reasons=(REASON_INTAKE_SUFFICIENT,),
        semantic_status=SEMANTIC_INTERPRETATION_OK,
        contract_present=True,
        semantic_receipt=_receipt(),
    )

    assert decision.ready_for_future_handoff is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.ready_for_future_handoff = False  # type: ignore[misc]
    with pytest.raises(TypeError, match="unexpected keyword"):
        CompletionDecision(  # type: ignore[call-arg]
            state=STATE_READY,
            ready_for_future_handoff=True,
        )


def test_a_non_ready_state_can_never_report_readiness():
    decision = CompletionDecision(
        state=STATE_ASK_CLARIFICATION,
        owner=OWNER_USER_MEANING_AMBIGUITY,
        reasons=(REASON_UNRESOLVED_MEANING,),
        ambiguities=(ClarificationNeed(kind="reported_ambiguity", index=1, detail="which one"),),
    )

    assert decision.ready_for_future_handoff is False


def test_ready_may_not_carry_an_owner():
    with pytest.raises(ValueError, match="no unresolved owner"):
        CompletionDecision(
            state=STATE_READY,
            owner=OWNER_USER_MEANING_AMBIGUITY,
            reasons=(REASON_INTAKE_SUFFICIENT,),
        )


def test_ready_may_not_carry_an_unresolved_ambiguity():
    with pytest.raises(ValueError, match="unresolved ambiguities"):
        CompletionDecision(
            state=STATE_READY,
            reasons=(REASON_INTAKE_SUFFICIENT,),
            ambiguities=(
                ClarificationNeed(kind="reported_ambiguity", index=1, detail="which one"),
            ),
        )


def test_ready_may_not_require_anything_before_handoff():
    with pytest.raises(ValueError, match="require anything before handoff"):
        CompletionDecision(
            state=STATE_READY,
            reasons=(REASON_INTAKE_SUFFICIENT,),
            missing_requirements=(
                MissingRequirement(field="scope", index=1, reason="unknown"),
            ),
        )


def test_each_non_ready_state_has_exactly_one_permitted_owner():
    with pytest.raises(ValueError, match="must be owned by"):
        CompletionDecision(
            state=STATE_ASK_CLARIFICATION,
            owner=OWNER_SEMANTIC_SYSTEM_FAILURE,
            reasons=(REASON_UNRESOLVED_MEANING,),
            ambiguities=(
                ClarificationNeed(kind="reported_ambiguity", index=1, detail="which one"),
            ),
        )


def test_asking_for_clarification_requires_something_to_ask_about():
    with pytest.raises(ValueError, match="at least one need"):
        CompletionDecision(
            state=STATE_ASK_CLARIFICATION,
            owner=OWNER_USER_MEANING_AMBIGUITY,
            reasons=(REASON_UNRESOLVED_MEANING,),
        )


def test_goal_brief_assistance_requires_a_field_that_actually_blocks():
    with pytest.raises(ValueError, match="at least one field needed"):
        CompletionDecision(
            state=STATE_GOAL_BRIEF_ASSIST,
            owner=OWNER_OPERATIONAL_DETAIL_MISSING,
            reasons=(REASON_OPERATIONAL_DETAIL_MISSING,),
            missing_requirements=(
                MissingRequirement(
                    field="validation", index=1, reason="nice to have",
                    severity=SEVERITY_SUGGESTED,
                ),
            ),
        )


def test_required_and_optional_are_split_by_severity():
    decision = CompletionDecision(
        state=STATE_GOAL_BRIEF_ASSIST,
        owner=OWNER_OPERATIONAL_DETAIL_MISSING,
        reasons=(REASON_OPERATIONAL_DETAIL_MISSING,),
        missing_requirements=(
            MissingRequirement(field="scope", index=1, reason="unknown"),
            MissingRequirement(
                field="validation", index=2, reason="helps", severity=SEVERITY_SUGGESTED
            ),
        ),
    )

    assert decision.required_before_handoff == ("scope",)
    assert decision.optional_improvements == ("validation",)
    assert decision.need_ids() == ("missing_1", "missing_2")


# ══ authority ═════════════════════════════════════════════════════════════════

def test_no_completion_state_grants_any_authority():
    for state, contract in (
        (STATE_READY, _contract("Explain what DeepSeek Harness is.")),
        (STATE_GOAL_BRIEF_ASSIST, _broad_implementation("Migrate the storage backend.")),
    ):
        decision = decide_intake_completion(contract)
        assert decision.state == state
        assert set(decision.as_dict()["authority"].values()) == {False, True}
        for name, value in decision.as_dict()["authority"].items():
            if name == "human_approval_required":
                assert value is True
            else:
                assert value is False, name


def test_the_authority_block_names_every_power_input_3_declines():
    authority = intake_authority()

    for name in (
        "routing_authority",
        "execution_authority",
        "repository_read_authority",
        "repository_write_authority",
        "patch_authority",
        "validation_authority",
        "benchmark_authority",
        "provider_selection_authority",
        "model_escalation_authority",
        "dream_authority",
        "project_evolution_authority",
        "mode_selection_authority",
    ):
        assert authority[name] is False, name
    assert authority["work" + "er_launch_authority"] is False
    assert authority["human_approval_required"] is True


def test_readiness_is_not_routing_permission():
    decision = _receipt_backed_decision(_contract("Explain what DeepSeek Harness is."))

    assert decision.ready_for_future_handoff is True
    assert decision.as_dict()["authority"]["routing_authority"] is False
    assert decision.as_dict()["authority"]["execution_authority"] is False
    assert "routing_allowed" not in decision.as_dict()


# ══ system failure is never the user's fault ══════════════════════════════════

@pytest.mark.parametrize(
    "status",
    [
        SEMANTIC_INTERPRETATION_FAILED,
        SEMANTIC_OUTPUT_INVALID,
        SEMANTIC_MODEL_UNAVAILABLE,
        SEMANTIC_DETERMINISTIC_FALLBACK,
    ],
)
def test_every_semantic_failure_status_is_owned_by_the_system(status):
    decision = decide_intake_completion(
        _contract("Explain what DeepSeek Harness is."), semantic_status=status
    )

    assert decision.state == STATE_SEMANTIC_SYSTEM_FAILURE
    assert decision.owner == OWNER_SEMANTIC_SYSTEM_FAILURE
    assert decision.reasons == (REASON_SEMANTIC_STATUS_FAILED,)
    assert decision.ambiguities == ()


def test_a_model_failure_never_becomes_a_request_for_clarification():
    decision = decide_intake_completion(
        _contract("Explain what DeepSeek Harness is."),
        semantic_status=SEMANTIC_MODEL_UNAVAILABLE,
    )

    assert decision.state != STATE_ASK_CLARIFICATION
    assert decision.owner != OWNER_USER_MEANING_AMBIGUITY


@pytest.mark.parametrize(
    "status",
    [None, SEMANTIC_STATUS_NOT_RUN, SEMANTIC_INTERPRETATION_OK, SEMANTIC_INTERPRETATION_REPAIRED],
)
def test_healthy_statuses_let_the_policy_continue(status):
    decision = decide_intake_completion(
        _contract("Explain what DeepSeek Harness is."), semantic_status=status
    )

    assert decision.state == STATE_READY


def test_a_bare_accepted_semantic_status_is_only_a_preview_not_handoff_evidence():
    decision = decide_intake_completion(
        _contract("Explain what DeepSeek Harness is."),
        semantic_status=SEMANTIC_INTERPRETATION_OK,
    )

    assert decision.state == STATE_READY
    assert decision.contract_present is True
    assert decision.semantic_evidence_status == SEMANTIC_EVIDENCE_MISSING
    assert decision.handoff_blockers == (HANDOFF_BLOCKER_SEMANTIC_RECEIPT_MISSING,)
    assert decision.ready_for_future_handoff is False


def test_a_valid_input_2_receipt_makes_a_preserved_ready_contract_handoff_ready():
    decision = _receipt_backed_decision(_contract("Explain what DeepSeek Harness is."))

    assert decision.state == STATE_READY
    assert decision.preservation_status == PRESERVATION_PASSED
    assert decision.semantic_evidence_status == SEMANTIC_EVIDENCE_VALID
    assert decision.semantic_evidence_valid is True
    assert decision.handoff_blockers == ()
    assert decision.ready_for_future_handoff is True


def test_a_repaired_input_2_receipt_is_valid_handoff_evidence():
    decision = _receipt_backed_decision(
        _contract("Explain what DeepSeek Harness is."),
        status=SEMANTIC_INTERPRETATION_REPAIRED,
    )

    assert decision.state == STATE_READY
    assert decision.semantic_evidence_status == SEMANTIC_EVIDENCE_VALID
    assert decision.ready_for_future_handoff is True


def test_a_receipt_must_agree_with_the_accepted_semantic_status():
    decision = decide_intake_completion(
        _contract("Explain what DeepSeek Harness is."),
        semantic_status=SEMANTIC_INTERPRETATION_OK,
        semantic_receipt=_receipt(SEMANTIC_INTERPRETATION_REPAIRED),
    )

    assert decision.state == STATE_READY
    assert decision.semantic_evidence_status == SEMANTIC_EVIDENCE_INVALID
    assert decision.handoff_blockers == (HANDOFF_BLOCKER_SEMANTIC_RECEIPT_INVALID,)
    assert decision.ready_for_future_handoff is False


def test_a_forged_or_impossible_success_receipt_is_not_handoff_evidence():
    zero_call_receipt = SemanticWaiterReceipt(
        adapter_name="test-semantic-adapter",
        configured_model="test-semantic-model",
        final_status=SEMANTIC_INTERPRETATION_OK,
        first_attempt_status="ok",
        attempt_count=0,
        model_call_count=0,
        structured_output_valid=True,
    )
    wrong_attempt_shape = dataclasses.replace(
        _receipt(),
        first_attempt_status="model_unavailable",
    )

    for receipt in (zero_call_receipt, wrong_attempt_shape):
        decision = decide_intake_completion(
            _contract("Explain what DeepSeek Harness is."),
            semantic_status=SEMANTIC_INTERPRETATION_OK,
            semantic_receipt=receipt,
        )

        assert decision.state == STATE_READY
        assert decision.semantic_evidence_status == SEMANTIC_EVIDENCE_INVALID
        assert decision.handoff_blockers == (HANDOFF_BLOCKER_SEMANTIC_RECEIPT_INVALID,)
        assert decision.ready_for_future_handoff is False


@pytest.mark.parametrize(
    "status",
    [SEMANTIC_MODEL_UNAVAILABLE, SEMANTIC_OUTPUT_INVALID],
)
def test_failed_or_invalid_semantic_receipts_never_qualify_for_handoff(status):
    policy_decision = decide_intake_completion(
        _contract("Explain what DeepSeek Harness is."),
        semantic_status=status,
        semantic_receipt=_receipt(status, structured_output_valid=False),
    )
    ready_looking_decision = CompletionDecision(
        state=STATE_READY,
        reasons=(REASON_INTAKE_SUFFICIENT,),
        semantic_status=status,
        preservation_status=PRESERVATION_PASSED,
        contract_present=True,
        semantic_receipt=_receipt(status, structured_output_valid=False),
    )

    assert policy_decision.state == STATE_SEMANTIC_SYSTEM_FAILURE
    assert policy_decision.semantic_evidence_status == SEMANTIC_EVIDENCE_INVALID
    assert policy_decision.ready_for_future_handoff is False
    assert ready_looking_decision.state == STATE_READY
    assert ready_looking_decision.semantic_evidence_status == SEMANTIC_EVIDENCE_INVALID
    assert ready_looking_decision.ready_for_future_handoff is False


def test_an_unrecognised_semantic_status_fails_closed_as_a_system_problem():
    decision = decide_intake_completion(
        _contract("Explain what DeepSeek Harness is."), semantic_status="something_new"
    )

    assert decision.state == STATE_SEMANTIC_SYSTEM_FAILURE
    assert decision.reasons == (REASON_SEMANTIC_STATUS_UNRECOGNISED,)


def test_a_preservation_failure_is_a_system_problem_not_a_user_problem():
    lossy = _contract(
        "Analyze DeepSeek Harness against C.A.T.T.U.S.",
        subjects=(Subject(value="DeepSeek Harness", provenance=PROVENANCE_EXPLICIT),),
    )
    assert lossy.preservation.status == PRESERVATION_FAILED

    decision = decide_intake_completion(lossy)

    assert decision.state == STATE_SEMANTIC_SYSTEM_FAILURE
    assert decision.owner == OWNER_SEMANTIC_SYSTEM_FAILURE
    assert decision.reasons == (REASON_PRESERVATION_FAILED,)
    assert decision.preservation_status == PRESERVATION_FAILED
    assert decision.ready_for_future_handoff is False


def test_a_semantic_run_with_no_contract_at_all_is_a_system_failure():
    outcome = SemanticWaiterOutcome(
        status=SEMANTIC_MODEL_UNAVAILABLE,
        receipt=SemanticWaiterReceipt(
            adapter_name="a",
            configured_model="m",
            final_status=SEMANTIC_MODEL_UNAVAILABLE,
            first_attempt_status="model_unavailable",
        ),
        contract=None,
    )

    decision = decide_from_semantic_outcome(outcome)

    assert decision.state == STATE_SEMANTIC_SYSTEM_FAILURE
    assert decision.reasons == (REASON_NO_CONTRACT,)
    assert decision.contract_present is False
    assert decision.ready_for_future_handoff is False


# ══ contradiction ═════════════════════════════════════════════════════════════

def test_an_explicit_requirement_and_prohibition_over_the_same_object_block():
    contract = understand_request("You must modify the tests. You must not modify the tests.")

    decision = decide_intake_completion(contract)

    assert decision.state == STATE_BLOCKED_CONTRADICTION
    assert decision.owner == OWNER_EXPLICIT_CONSTRAINT_CONFLICT
    assert decision.reasons == (REASON_EXPLICIT_CONSTRAINT_CONFLICT,)
    assert len(decision.contradiction_reasons) == 1
    assert "modify the tests" in decision.contradiction_reasons[0]
    assert decision.ready_for_future_handoff is False


def test_a_requirement_and_a_prohibition_about_different_things_do_not_conflict():
    contract = understand_request("You must update the docs. You must not modify the tests.")

    assert detect_explicit_contradictions(contract) == ()
    assert decide_intake_completion(contract).state != STATE_BLOCKED_CONTRADICTION


def test_a_prohibition_alone_is_not_a_contradiction():
    contract = understand_request("Analyze this architecture, but do not inspect tests.")

    assert detect_explicit_contradictions(contract) == ()


def test_two_incompatible_output_formats_with_an_exclusivity_marker_block():
    contract = understand_request("Give me the result in JSON. Return it in markdown only.")

    decision = decide_intake_completion(contract)

    assert decision.state == STATE_BLOCKED_CONTRADICTION
    assert "json" in decision.contradiction_reasons[0]
    assert "markdown" in decision.contradiction_reasons[0]


def test_two_incompatible_output_formats_without_a_marker_are_only_ambiguous():
    contract = understand_request("Give me the result in JSON. Also give it to me in markdown.")

    decision = decide_intake_completion(contract)

    assert decision.state == STATE_ASK_CLARIFICATION
    assert decision.owner == OWNER_USER_MEANING_AMBIGUITY
    assert decision.reasons == (REASON_CONFLICTING_OUTPUT_FORMATS,)
    assert decision.contradiction_reasons == ()


def test_compatible_presentation_formats_do_not_conflict():
    """A markdown table is one answer, not two irreconcilable ones.

    INPUT.1 carries a single requested output, so its gate reports the second
    cue as lost.  Nothing the user said actually disappeared, and the decision
    records the representation limit rather than calling it a system fault.
    """
    contract = understand_request("Compare the two options as a table in markdown.")
    assert contract.preservation.status == PRESERVATION_FAILED

    decision = decide_intake_completion(
        contract,
        semantic_status=SEMANTIC_INTERPRETATION_OK,
        semantic_receipt=_receipt(),
    )

    assert detect_explicit_contradictions(contract) == ()
    assert decision.state == STATE_READY
    assert REASON_OUTPUT_REPRESENTATION_LIMIT in decision.reasons
    assert decision.preservation_status == PRESERVATION_FAILED
    assert decision.semantic_evidence_status == SEMANTIC_EVIDENCE_VALID
    assert decision.handoff_blockers == (HANDOFF_BLOCKER_PRESERVATION_FAILED,)
    assert decision.ready_for_future_handoff is False


def test_a_wider_preservation_failure_outranks_a_contradiction():
    """A dropped subject is a real interpreter fault and is reported as one."""
    contract = _contract(
        "Analyze DeepSeek Harness against C.A.T.T.U.S. "
        "You must modify the tests. You must not modify the tests.",
        subjects=(Subject(value="DeepSeek Harness", provenance=PROVENANCE_EXPLICIT),),
    )
    assert detect_explicit_contradictions(contract)

    decision = decide_intake_completion(contract)

    assert decision.state == STATE_SEMANTIC_SYSTEM_FAILURE
    assert decision.reasons == (REASON_PRESERVATION_FAILED,)


# ══ operational breadth ═══════════════════════════════════════════════════════

def test_only_operational_task_types_can_be_broad():
    assert OPERATIONAL_TASK_TYPES == ("implementation", "debugging", "planning")
    comparative = _contract(
        "Compare these two pasted functions for readability.",
        task=TaskClassification(type="comparative_analysis", provenance=PROVENANCE_INFERRED),
        execution_requirements=ExecutionRequirements(
            multi_stage=True,
            repository_inspection_required=True,
            provenance=PROVENANCE_INFERRED,
        ),
    )

    assert is_broad_operational_task(comparative) is False
    assert collect_missing_requirements(comparative) == ()


def test_an_operational_task_with_no_breadth_signal_is_not_broad():
    narrow = _contract(
        "Rename one variable.",
        task=TaskClassification(type="implementation", provenance=PROVENANCE_INFERRED),
    )

    assert is_broad_operational_task(narrow) is False


def test_a_broad_task_missing_scope_is_offered_assistance():
    contract = _broad_implementation("Migrate the storage backend to PostgreSQL.")

    decision = decide_intake_completion(contract)

    assert decision.state == STATE_GOAL_BRIEF_ASSIST
    assert decision.owner == OWNER_OPERATIONAL_DETAIL_MISSING
    assert "scope" in decision.required_before_handoff


def test_a_broad_task_that_names_its_scope_is_ready():
    contract = _broad_implementation("Migrate the storage backend in storage/db.py.")

    decision = decide_intake_completion(contract)

    assert decision.state == STATE_READY
    assert decision.required_before_handoff == ()


def test_a_ready_broad_task_is_offered_no_suggestions_at_all():
    """READY means nothing is asked and nothing is volunteered."""
    contract = _broad_implementation("Migrate the storage backend in storage/db.py.")

    decision = decide_intake_completion(contract)

    assert decision.optional_improvements == ()
    assert decision.missing_requirements == ()


def test_reported_missing_information_blocks_only_a_broad_task():
    broad = _broad_implementation(
        "Migrate the storage backend in storage/db.py.",
        missing_information=("which compatibility guarantee to keep",),
    )
    conversational = _contract(
        "Explain what DeepSeek Harness is.",
        task=TaskClassification(type="question", provenance=PROVENANCE_INFERRED),
        missing_information=("which compatibility guarantee to keep",),
    )

    assert decide_intake_completion(broad).state == STATE_GOAL_BRIEF_ASSIST
    assert decide_intake_completion(conversational).state == STATE_READY


def test_suggestions_never_include_why_or_desired_output():
    contract = _broad_implementation("Migrate the storage backend to PostgreSQL.")

    decision = decide_intake_completion(contract)

    assert "why" not in decision.optional_improvements
    assert "desired_output" not in decision.optional_improvements
    assert set(decision.optional_improvements) <= {"constraints", "validation", "stop_conditions"}


def test_missing_requirements_stay_within_the_bound():
    contract = _broad_implementation(
        "Migrate everything.",
        missing_information=tuple(f"gap {index}" for index in range(12)),
    )

    decision = decide_intake_completion(contract)

    assert len(decision.missing_requirements) <= 8


# ══ ambiguity ═════════════════════════════════════════════════════════════════

def test_an_interpreter_reported_ambiguity_becomes_a_clarification_need():
    contract = _contract(
        "Replace it with the other one.",
        ambiguities=("'it' has no resolvable referent",),
    )

    decision = decide_intake_completion(contract)

    assert decision.state == STATE_ASK_CLARIFICATION
    assert decision.owner == OWNER_USER_MEANING_AMBIGUITY
    assert decision.reasons == (REASON_UNRESOLVED_MEANING,)
    assert decision.ambiguities[0].detail == "'it' has no resolvable referent"


def test_need_ids_are_unique_across_kinds():
    contract = _contract(
        "Compare it with the other one.",
        ambiguities=("'it' has no resolvable referent",),
        relationships=(
            Relationship(
                type="comparison",
                subjects=("the first thing", "the second thing"),
                provenance=PROVENANCE_INFERRED,
                confidence=0.4,
            ),
        ),
    )

    decision = decide_intake_completion(contract)
    ids = decision.need_ids()

    assert len(ids) == len(set(ids))
    assert len(ids) >= 2


def test_need_ids_are_short_enough_for_a_small_model_to_copy():
    """The anchor is the one string a 4B model must reproduce exactly."""
    contract = _broad_implementation(
        "Migrate the storage backend.", missing_information=("which guarantee to keep",)
    )

    for need_id in decide_intake_completion(contract).need_ids():
        assert ":" not in need_id
        assert " " not in need_id
        assert len(need_id) <= 20
        assert need_id.isascii()


def test_a_decision_refuses_colliding_need_anchors():
    with pytest.raises(ValueError, match="distinct anchor id"):
        CompletionDecision(
            state=STATE_GOAL_BRIEF_ASSIST,
            owner=OWNER_OPERATIONAL_DETAIL_MISSING,
            reasons=(REASON_OPERATIONAL_DETAIL_MISSING,),
            missing_requirements=(
                MissingRequirement(field="scope", index=1, reason="a"),
                MissingRequirement(field="unspecified", index=1, reason="b"),
            ),
        )


def test_clarification_needs_are_bounded():
    contract = _contract(
        "Do the thing.",
        ambiguities=tuple(f"ambiguity {index}" for index in range(9)),
    )

    assert len(decide_intake_completion(contract).ambiguities) <= 4


def test_ambiguity_outranks_operational_incompleteness():
    contract = _broad_implementation(
        "Migrate it somewhere.",
        ambiguities=("'it' has no resolvable referent",),
    )

    assert decide_intake_completion(contract).state == STATE_ASK_CLARIFICATION


def test_every_non_ready_state_is_non_handoff_ready_even_with_valid_evidence():
    goal_brief = decide_intake_completion(
        _broad_implementation("Migrate the storage backend to PostgreSQL."),
        semantic_status=SEMANTIC_INTERPRETATION_OK,
        semantic_receipt=_receipt(),
    )
    clarification = decide_intake_completion(
        _contract(
            "Replace it with the other one.",
            ambiguities=("'it' has no resolvable referent",),
        ),
        semantic_status=SEMANTIC_INTERPRETATION_OK,
        semantic_receipt=_receipt(),
    )
    contradiction = decide_intake_completion(
        understand_request("You must modify the tests. You must not modify the tests."),
        semantic_status=SEMANTIC_INTERPRETATION_OK,
        semantic_receipt=_receipt(),
    )
    system_failure = decide_intake_completion(
        _contract("Explain what DeepSeek Harness is."),
        semantic_status=SEMANTIC_MODEL_UNAVAILABLE,
        semantic_receipt=_receipt(SEMANTIC_MODEL_UNAVAILABLE, structured_output_valid=False),
    )

    assert goal_brief.state == STATE_GOAL_BRIEF_ASSIST
    assert clarification.state == STATE_ASK_CLARIFICATION
    assert contradiction.state == STATE_BLOCKED_CONTRADICTION
    assert system_failure.state == STATE_SEMANTIC_SYSTEM_FAILURE
    for decision in (goal_brief, clarification, contradiction, system_failure):
        assert decision.ready_for_future_handoff is False


def test_the_policy_does_not_reread_the_prompt_for_pronouns():
    """Reference resolution is the Semantic Waiter's job, not the policy's.

    Both of these prompts are pronoun-shaped and evidence-free.  With no
    interpreter report to go on, the policy treats them identically rather than
    guessing which one is unresolvable.
    """
    ambiguous = decide_intake_completion(understand_request("Replace it with the other one."))
    bounded = decide_intake_completion(
        understand_request("Compare these two pasted functions for readability.")
    )

    assert ambiguous.state == bounded.state == STATE_READY


# ══ serialization ═════════════════════════════════════════════════════════════

def test_a_decision_serializes_to_stable_json():
    decision = decide_intake_completion(_contract("Explain what DeepSeek Harness is."))

    payload = json.loads(render_completion_decision_json(decision))

    assert payload["phase_id"] == "INPUT.3"
    assert payload["state"] == STATE_READY
    assert payload["preservation_status"] == PRESERVATION_PASSED
    assert payload["semantic_status"] == SEMANTIC_STATUS_NOT_RUN
    assert payload["semantic_evidence_status"] == SEMANTIC_EVIDENCE_MISSING
    assert payload["handoff_blockers"] == [HANDOFF_BLOCKER_SEMANTIC_RECEIPT_MISSING]
    assert payload["ready_for_future_handoff"] is False
    assert payload["required_before_handoff"] == []


def test_a_decision_requires_an_actual_task_contract():
    with pytest.raises(TypeError):
        decide_intake_completion("Explain what DeepSeek Harness is.")  # type: ignore[arg-type]


# ══ purity ════════════════════════════════════════════════════════════════════

def _module_source(name: str) -> str:
    return (PROJECT_ROOT / "core" / f"{name}.py").read_text(encoding="utf-8")


def test_the_policy_modules_import_no_execution_subsystem():
    allowed_core = {
        "explicit_evidence",
        "task_contract",
        "semantic_waiter",
        "requirement_preservation",
        "input_understanding",
        "semantic_waiter_adapter",
        "semantic_waiter_runner",
        "json_utils",
        *INPUT_3_POLICY_MODULES,
    }
    for name in INPUT_3_POLICY_MODULES:
        tree = ast.parse(_module_source(name))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("core."):
                    assert module.split(".", 1)[1] in allowed_core, (
                        f"{name} imports outside INPUT.3: {module}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("core."), (
                        f"{name} imports outside INPUT.3: {alias.name}"
                    )


def test_the_policy_modules_use_only_inert_stdlib():
    allowed_top = {"__future__", "dataclasses", "json", "typing", "core"}
    for name in INPUT_3_POLICY_MODULES:
        tree = ast.parse(_module_source(name))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                top = (node.module or "").split(".")[0]
                assert top in allowed_top, f"{name}: unexpected import {node.module!r}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top in allowed_top, f"{name}: unexpected import {alias.name!r}"


def test_the_policy_modules_contain_no_execution_or_provider_tokens():
    for name in INPUT_3_POLICY_MODULES:
        source = _module_source(name)
        for token in (
            "subprocess",
            "Popen",
            "os.system",
            "requests",
            "httpx",
            "urllib",
            "socket",
            "OpenAI",
            "Anthropic",
            "Gemini",
            "ollama",
            "apply_patch",
            "generate_patch",
            "run_benchmarks",
            "mode_router",
            "git push",
        ):
            assert token not in source, f"forbidden token {token!r} in core/{name}.py"
