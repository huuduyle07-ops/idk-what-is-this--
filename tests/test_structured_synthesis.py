"""Functional acceptance tests for SYNTHESIS.1.

These tests use frozen, valid INPUT.1 and CLAIM.1 records.  The phase under
test may only attach those records to the user-preserved answer shape; it may
not assess, reinterpret, rank, score, or render their content.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from core.claim_assessment import (
    ASSESSMENT_BASIS_GATED_ANALYZER_ASSESSMENTS,
    BASIS_ANALYZER_ASSESSED,
    BASIS_NOT_ESTABLISHED,
    CORROBORATION_NONE,
    INCONSISTENT_EVIDENCE_SET,
    STATUS_CONFLICTING,
    STATUS_CONTRADICTED,
    STATUS_COVERAGE_INCOMPLETE,
    STATUS_CURRENT_STATE_INCONSISTENT,
    STATUS_CURRENT_STATE_UNESTABLISHED,
    STATUS_INCONSISTENT_INPUT as CLAIM_STATUS_INCONSISTENT_INPUT,
    STATUS_INSUFFICIENT,
    STATUS_SUPPORTED,
    ClaimAssessment,
)
from core.evidence_set_assessment import (
    CONFLICT_CONFLICTING,
    CONFLICT_CONTRADICTION_ONLY,
    CONFLICT_NO_DIRECTIONAL_EVIDENCE,
    CONFLICT_SUPPORT_ONLY,
    COVERAGE_NOT_APPLICABLE,
)
from core.evidence_verification import (
    PROPOSITION_NEGATIVE_EXISTENTIAL,
    PROPOSITION_POSITIVE,
    SCOPE_IMPLEMENTATION_STATE,
)
from core.explicit_evidence import ExplicitEvidence, ExplicitRequestedOutput
from core.structured_synthesis import (
    BINDING_EXPLICIT_TASK_CONTRACT,
    BINDING_PRESERVED_RUBRIC,
    DECISION_COMPARATIVE_SELECTION,
    INCONSISTENT_ASSESSMENT_UNBOUND,
    INCONSISTENT_CONSTRAINTS,
    INCONSISTENT_OUTPUT_FORMAT,
    INCONSISTENT_RUBRIC_REORDERED,
    INCONSISTENT_SPECIFICATION_FINGERPRINT,
    INCONSISTENT_STRUCTURE_NARROWED,
    INCONSISTENT_STRUCTURE_WIDENED,
    INCONSISTENT_SUBJECT_DROPPED,
    INCONSISTENT_SUBJECT_RENAMED,
    INCONSISTENT_TASK_FINGERPRINT,
    INCONSISTENT_TASK_OUTPUT_FORMAT_AMBIGUOUS,
    INCONSISTENT_TASK_PRESERVATION,
    INCONSISTENT_TASK_STRUCTURE_TRUNCATED,
    OUTPUT_SHAPE_COMPARISON_MATRIX,
    OUTPUT_SHAPE_ORDERED_SECTIONS,
    OUTPUT_SHAPE_SINGLE_SLOT,
    PRESERVATION_FAILED_STATUS,
    PRESERVATION_CLAIM_REFERENCE_CHANGED,
    PRESERVATION_OUTPUT_SHAPE_CHANGED,
    PRESERVATION_RESULT_DERIVATION_CHANGED,
    SLOT_INCONSISTENT,
    SLOT_MISSING_CLAIM_ASSESSMENT,
    SLOT_MIXED_CLAIM_STATES,
    SLOT_POPULATED,
    SLOT_PROPOSITION_BINDING_REQUIRED,
    SLOT_UNRESOLVED_CONFLICT,
    SLOT_UNRESOLVED_COVERAGE,
    SLOT_UNRESOLVED_CURRENT_STATE,
    SLOT_UNRESOLVED_INSUFFICIENT,
    STATUS_COMPOSED,
    STATUS_COMPOSED_WITH_GAPS,
    STATUS_INCOMPLETE_SPECIFICATION,
    STATUS_INCONSISTENT_INPUT,
    UNRESOLVED_CLAIM_ASSESSMENT,
    UNRESOLVED_CONFLICT,
    UNRESOLVED_COVERAGE,
    UNRESOLVED_CURRENT_STATE,
    UNRESOLVED_DOWNSTREAM_DECISION,
    UNRESOLVED_INSUFFICIENCY,
    UNRESOLVED_MIXED_CLAIMS,
    UNRESOLVED_PROPOSITION_BINDING,
    UNRESOLVED_UPSTREAM_INPUT,
    ClaimAssessmentReference,
    ClaimSlotBinding,
    DecisionRequirement,
    SynthesisConstraint,
    SynthesisRequest,
    SynthesisSlot,
    SynthesisSpecification,
    SynthesisSubject,
    check_synthesis_preservation,
    compose_structured_synthesis,
    render_structured_synthesis_json,
    synthesis_specification_fingerprint,
    task_contract_fingerprint,
    task_preservation_fingerprint,
)
from core.task_contract import (
    PRESERVATION_FAILED,
    PRESERVATION_PASSED,
    PROVENANCE_EXPLICIT,
    PROVENANCE_INFERRED,
    Constraint,
    PreservationReport,
    RawRequest,
    Relationship,
    RequestedOutput,
    Subject,
    TaskClassification,
    TaskContract,
    UserSuppliedFramework,
)


DIMENSIONS = (
    "planning",
    "repository understanding",
    "execution",
    "evidence",
    "safety",
)
SUBJECTS = ("C.A.T.T.U.S", "DeepSeek Harness")


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _claim(
    proposition_id: str,
    status: str = STATUS_SUPPORTED,
    *,
    proposition_text: str | None = None,
    proposition_type: str = PROPOSITION_POSITIVE,
) -> ClaimAssessment:
    """Build a real frozen CLAIM.1 record without running upstream phases."""
    text = proposition_text or f"{proposition_id} has assessed implementation."
    common = {
        "assessment_status": status,
        "proposition_id": proposition_id,
        "proposition_sha256": _digest(text),
        "proposition_text": text,
        "proposition_type": proposition_type,
        "proposition_scope": SCOPE_IMPLEMENTATION_STATE,
        "evidence_set_fingerprint": _digest(f"set:{proposition_id}:{status}"),
        "evidence_set_request_fingerprint": _digest(
            f"set-request:{proposition_id}:{status}"
        ),
        "request_fingerprint": _digest(f"claim-request:{proposition_id}:{status}"),
    }
    if status == CLAIM_STATUS_INCONSISTENT_INPUT:
        return ClaimAssessment(
            **common,
            inconsistencies=(INCONSISTENT_EVIDENCE_SET,),
        )
    conflict_status = {
        STATUS_SUPPORTED: CONFLICT_SUPPORT_ONLY,
        STATUS_CONTRADICTED: CONFLICT_CONTRADICTION_ONLY,
        STATUS_CONFLICTING: CONFLICT_CONFLICTING,
    }.get(status, CONFLICT_NO_DIRECTIONAL_EVIDENCE)
    directional_refs = (
        (_digest(f"directional:{proposition_id}:{status}"),)
        if status
        in {STATUS_SUPPORTED, STATUS_CONTRADICTED, STATUS_CONFLICTING}
        else ()
    )
    return ClaimAssessment(
        **common,
        semantic_basis=BASIS_ANALYZER_ASSESSED,
        assessment_basis=ASSESSMENT_BASIS_GATED_ANALYZER_ASSESSMENTS,
        conflict_status=conflict_status,
        role_coverage_status=COVERAGE_NOT_APPLICABLE,
        scope_coverage=COVERAGE_NOT_APPLICABLE,
        negative_claim_coverage=COVERAGE_NOT_APPLICABLE,
        current_state_coverage=COVERAGE_NOT_APPLICABLE,
        corroboration_status=CORROBORATION_NONE,
        directional_record_refs=directional_refs,
    )


def _task_contract(
    *,
    subjects: tuple[str, ...] = (),
    rubric: tuple[str, ...] = ("answer",),
    output_format: str = "json",
    constraints: tuple[tuple[str, str], ...] = (),
    raw_request: str = "Answer using only assessed claims.",
) -> TaskContract:
    subject_records = tuple(
        Subject(value=label, provenance=PROVENANCE_EXPLICIT)
        for label in subjects
    )
    relationships = (
        (
            Relationship(
                type="comparison",
                subjects=subjects,
                provenance=PROVENANCE_EXPLICIT,
            ),
        )
        if len(subjects) >= 2
        else ()
    )
    return TaskContract(
        raw_request=RawRequest(text=raw_request),
        task=TaskClassification(
            type="comparative_analysis" if relationships else "question",
            provenance=PROVENANCE_EXPLICIT,
        ),
        subjects=subject_records,
        relationships=relationships,
        user_supplied_framework=(
            UserSuppliedFramework(
                type="rubric",
                values=rubric,
                provenance=PROVENANCE_EXPLICIT,
                ordered=True,
            )
            if rubric
            else None
        ),
        requested_output=RequestedOutput(
            format=output_format,
            provenance=PROVENANCE_EXPLICIT,
        ),
        constraints=tuple(
            Constraint(kind=kind, text=text, provenance=PROVENANCE_EXPLICIT)
            for kind, text in constraints
        ),
        explicit_evidence=ExplicitEvidence(),
        preservation=PreservationReport(status=PRESERVATION_PASSED),
        routing_allowed=True,
    )


def _request(
    contract: TaskContract,
    specification: SynthesisSpecification,
    assessments: tuple[ClaimAssessment, ...],
    *,
    expected_fingerprint: str | None = None,
) -> SynthesisRequest:
    return SynthesisRequest(
        task_contract=contract,
        specification=specification,
        claim_assessments=assessments,
        expected_synthesis_specification_fingerprint=(
            synthesis_specification_fingerprint(specification)
            if expected_fingerprint is None
            else expected_fingerprint
        ),
    )


def _single_fixture(
    status: str = STATUS_SUPPORTED,
    *,
    assessment_present: bool = True,
    proposition_type: str = PROPOSITION_POSITIVE,
) -> tuple[SynthesisRequest, ClaimAssessment]:
    contract = _task_contract()
    assessment = _claim("P-1", status, proposition_type=proposition_type)
    slot = SynthesisSlot(
        slot_id="answer",
        label="answer",
        ordinal=1,
        required_proposition_ids=("P-1",),
    )
    binding = ClaimSlotBinding(
        slot_id=slot.slot_id,
        proposition_id=assessment.proposition_id,
        expected_assessment_fingerprint=assessment.assessment_fingerprint,
        provenance=BINDING_EXPLICIT_TASK_CONTRACT,
    )
    specification = SynthesisSpecification(
        task_contract_fingerprint=task_contract_fingerprint(contract),
        preservation_fingerprint=task_preservation_fingerprint(contract),
        output_shape=OUTPUT_SHAPE_SINGLE_SLOT,
        preserved_output_format="json",
        ordered_subjects=(),
        ordered_slots=(slot,),
        constraints=(),
        claim_bindings=(binding,),
    )
    return (
        _request(
            contract,
            specification,
            (assessment,) if assessment_present else (),
        ),
        assessment,
    )


def _deepseek_fixture(
    *,
    statuses: tuple[str, ...] | None = None,
    omit_cell: tuple[str, str] | None = None,
    decision_requested: bool = False,
    reverse_bindings: bool = False,
    reverse_assessments: bool = False,
) -> tuple[SynthesisRequest, tuple[ClaimAssessment, ...]]:
    statuses = statuses or (
        STATUS_SUPPORTED,
        STATUS_SUPPORTED,
        STATUS_CONFLICTING,
        STATUS_SUPPORTED,
        STATUS_CURRENT_STATE_UNESTABLISHED,
        STATUS_SUPPORTED,
        STATUS_SUPPORTED,
        STATUS_CONTRADICTED,
        STATUS_INSUFFICIENT,
        STATUS_COVERAGE_INCOMPLETE,
    )
    assert len(statuses) == len(DIMENSIONS) * len(SUBJECTS)
    constraint = ("requirement", "Preserve every requested comparison cell.")
    contract = _task_contract(
        subjects=SUBJECTS,
        rubric=DIMENSIONS,
        output_format="table",
        constraints=(constraint,),
        raw_request=(
            "Compare C.A.T.T.U.S and DeepSeek Harness across planning, "
            "repository understanding, execution, evidence, and safety."
        ),
    )
    ordered_subjects = tuple(
        SynthesisSubject(
            subject_id=f"subject-{ordinal}",
            label=label,
            ordinal=ordinal,
        )
        for ordinal, label in enumerate(SUBJECTS, start=1)
    )
    assessments: list[ClaimAssessment] = []
    slots: list[SynthesisSlot] = []
    bindings: list[ClaimSlotBinding] = []
    status_index = 0
    for slot_ordinal, dimension in enumerate(DIMENSIONS, start=1):
        slot_id = f"dimension-{slot_ordinal}"
        proposition_ids = tuple(
            f"P-{slot_ordinal:02d}-{subject.ordinal:02d}"
            for subject in ordered_subjects
        )
        slots.append(
            SynthesisSlot(
                slot_id=slot_id,
                label=dimension,
                ordinal=slot_ordinal,
                required_proposition_ids=proposition_ids,
            )
        )
        for proposition_id, subject in zip(
            proposition_ids, ordered_subjects, strict=True
        ):
            assessment = _claim(proposition_id, statuses[status_index])
            status_index += 1
            assessments.append(assessment)
            bindings.append(
                ClaimSlotBinding(
                    slot_id=slot_id,
                    subject_id=subject.subject_id,
                    proposition_id=proposition_id,
                    expected_assessment_fingerprint=assessment.assessment_fingerprint,
                    provenance=BINDING_PRESERVED_RUBRIC,
                )
            )
    if reverse_bindings:
        bindings.reverse()
    supplied_assessments = [
        assessment
        for assessment in assessments
        if omit_cell
        != (
            DIMENSIONS[int(assessment.proposition_id[2:4]) - 1],
            SUBJECTS[int(assessment.proposition_id[5:7]) - 1],
        )
    ]
    if reverse_assessments:
        supplied_assessments.reverse()
    specification = SynthesisSpecification(
        task_contract_fingerprint=task_contract_fingerprint(contract),
        preservation_fingerprint=task_preservation_fingerprint(contract),
        output_shape=OUTPUT_SHAPE_COMPARISON_MATRIX,
        preserved_output_format="table",
        ordered_subjects=ordered_subjects,
        ordered_slots=tuple(slots),
        constraints=(
            SynthesisConstraint(kind=constraint[0], text=constraint[1], ordinal=1),
        ),
        claim_bindings=tuple(bindings),
        decision_requirement=(
            DecisionRequirement(
                requested=True,
                type=DECISION_COMPARATIVE_SELECTION,
                provenance=BINDING_EXPLICIT_TASK_CONTRACT,
            )
            if decision_requested
            else DecisionRequirement()
        ),
    )
    return (
        _request(contract, specification, tuple(supplied_assessments)),
        tuple(assessments),
    )


@pytest.mark.parametrize(
    ("claim_status", "slot_status", "top_status", "unresolved"),
    (
        (STATUS_SUPPORTED, SLOT_POPULATED, STATUS_COMPOSED, None),
        (STATUS_CONTRADICTED, SLOT_POPULATED, STATUS_COMPOSED, None),
        (
            STATUS_CONFLICTING,
            SLOT_UNRESOLVED_CONFLICT,
            STATUS_COMPOSED_WITH_GAPS,
            UNRESOLVED_CONFLICT,
        ),
        (
            STATUS_INSUFFICIENT,
            SLOT_UNRESOLVED_INSUFFICIENT,
            STATUS_COMPOSED_WITH_GAPS,
            UNRESOLVED_INSUFFICIENCY,
        ),
        (
            STATUS_COVERAGE_INCOMPLETE,
            SLOT_UNRESOLVED_COVERAGE,
            STATUS_COMPOSED_WITH_GAPS,
            UNRESOLVED_COVERAGE,
        ),
        (
            STATUS_CURRENT_STATE_UNESTABLISHED,
            SLOT_UNRESOLVED_CURRENT_STATE,
            STATUS_COMPOSED_WITH_GAPS,
            UNRESOLVED_CURRENT_STATE,
        ),
        (
            STATUS_CURRENT_STATE_INCONSISTENT,
            SLOT_UNRESOLVED_CURRENT_STATE,
            STATUS_COMPOSED_WITH_GAPS,
            UNRESOLVED_CURRENT_STATE,
        ),
        (
            CLAIM_STATUS_INCONSISTENT_INPUT,
            SLOT_INCONSISTENT,
            STATUS_COMPOSED_WITH_GAPS,
            UNRESOLVED_UPSTREAM_INPUT,
        ),
    ),
)
def test_every_claim_status_is_preserved_without_reinterpretation(
    claim_status: str,
    slot_status: str,
    top_status: str,
    unresolved: str | None,
) -> None:
    request, assessment = _single_fixture(claim_status)
    result = compose_structured_synthesis(request)
    assert result.status == top_status
    assert result.slot_results[0].slot_status == slot_status
    assert result.slot_results[0].claim_statuses == (claim_status,)
    assert result.slot_results[0].claim_assessment_refs[0].assessment_fingerprint == (
        assessment.assessment_fingerprint
    )
    assert (unresolved in result.unresolved_requirements) is (unresolved is not None)
    assert result.semantic_basis == (
        BASIS_NOT_ESTABLISHED
        if claim_status == CLAIM_STATUS_INCONSISTENT_INPUT
        else BASIS_ANALYZER_ASSESSED
    )


def test_single_slot_missing_assessment_remains_an_explicit_gap() -> None:
    request, assessment = _single_fixture(assessment_present=False)
    result = compose_structured_synthesis(request)
    slot = result.slot_results[0]
    assert result.status == STATUS_COMPOSED_WITH_GAPS
    assert slot.slot_status == SLOT_MISSING_CLAIM_ASSESSMENT
    assert slot.missing_proposition_ids == (assessment.proposition_id,)
    assert slot.claim_assessment_refs == ()
    assert UNRESOLVED_CLAIM_ASSESSMENT in result.unresolved_requirements


def test_required_slot_without_any_binding_is_incomplete_specification() -> None:
    contract = _task_contract()
    slot = SynthesisSlot(
        slot_id="answer",
        label="answer",
        ordinal=1,
        required_proposition_ids=("P-1",),
    )
    specification = SynthesisSpecification(
        task_contract_fingerprint=task_contract_fingerprint(contract),
        preservation_fingerprint=task_preservation_fingerprint(contract),
        output_shape=OUTPUT_SHAPE_SINGLE_SLOT,
        preserved_output_format="json",
        ordered_subjects=(),
        ordered_slots=(slot,),
        constraints=(),
        claim_bindings=(),
    )
    result = compose_structured_synthesis(_request(contract, specification, ()))
    assert result.status == STATUS_INCOMPLETE_SPECIFICATION
    assert result.slot_results[0].slot_status == SLOT_PROPOSITION_BINDING_REQUIRED
    assert UNRESOLVED_PROPOSITION_BINDING in result.unresolved_requirements


def test_deepseek_dogfood_preserves_the_exact_two_by_five_matrix() -> None:
    request, assessments = _deepseek_fixture()
    result = compose_structured_synthesis(request)
    assert result.status == STATUS_COMPOSED_WITH_GAPS
    assert tuple(item.label for item in result.ordered_subjects) == SUBJECTS
    assert tuple(item.label for item in result.ordered_slots) == DIMENSIONS
    assert len(result.slot_results) == 10
    assert tuple(
        (item.label, item.subject_label) for item in result.slot_results
    ) == tuple(
        (dimension, subject)
        for dimension in DIMENSIONS
        for subject in SUBJECTS
    )
    assert tuple(
        item.claim_statuses[0] for item in result.slot_results
    ) == tuple(item.assessment_status for item in assessments)
    assert result.slot_results[2].slot_status == SLOT_UNRESOLVED_CONFLICT
    assert result.slot_results[7].claim_statuses == (STATUS_CONTRADICTED,)
    assert result.slot_results[8].slot_status == SLOT_UNRESOLVED_INSUFFICIENT
    assert result.preservation is not None and result.preservation.passed


def test_deepseek_missing_cell_is_not_omitted_or_replaced() -> None:
    request, _ = _deepseek_fixture(omit_cell=("safety", "DeepSeek Harness"))
    result = compose_structured_synthesis(request)
    assert len(result.slot_results) == 10
    missing = result.slot_results[-1]
    assert (missing.label, missing.subject_label) == (
        "safety",
        "DeepSeek Harness",
    )
    assert missing.slot_status == SLOT_MISSING_CLAIM_ASSESSMENT
    assert missing.missing_proposition_ids == ("P-05-02",)
    assert UNRESOLVED_CLAIM_ASSESSMENT in result.unresolved_requirements


@pytest.mark.parametrize(
    ("mutation", "expected_inconsistency"),
    (
        ("drop_rubric", INCONSISTENT_STRUCTURE_NARROWED),
        ("add_rubric", INCONSISTENT_STRUCTURE_WIDENED),
        ("reorder_rubric", INCONSISTENT_RUBRIC_REORDERED),
        ("drop_subject", INCONSISTENT_SUBJECT_DROPPED),
        ("rename_subject", INCONSISTENT_SUBJECT_RENAMED),
        ("change_output", INCONSISTENT_OUTPUT_FORMAT),
        ("change_constraint", INCONSISTENT_CONSTRAINTS),
    ),
)
def test_preserved_task_shape_changes_are_rejected(
    mutation: str, expected_inconsistency: str
) -> None:
    request, assessments = _deepseek_fixture()
    specification = request.specification
    assert specification is not None
    if mutation == "drop_rubric":
        kept = specification.ordered_slots[:-1]
        kept_ids = {item.slot_id for item in kept}
        changed = replace(
            specification,
            ordered_slots=kept,
            claim_bindings=tuple(
                item
                for item in specification.claim_bindings
                if item.slot_id in kept_ids
            ),
        )
    elif mutation == "add_rubric":
        changed = replace(
            specification,
            ordered_slots=(
                *specification.ordered_slots,
                SynthesisSlot(
                    slot_id="agent-selected-architecture",
                    label="agent-selected architecture",
                    ordinal=6,
                    required_proposition_ids=(),
                    required=False,
                ),
            ),
        )
    elif mutation == "reorder_rubric":
        reordered = (
            specification.ordered_slots[1],
            specification.ordered_slots[0],
            *specification.ordered_slots[2:],
        )
        changed = replace(
            specification,
            ordered_slots=tuple(
                replace(item, ordinal=ordinal)
                for ordinal, item in enumerate(reordered, start=1)
            ),
        )
    elif mutation == "drop_subject":
        changed = replace(
            specification,
            output_shape=OUTPUT_SHAPE_ORDERED_SECTIONS,
            ordered_subjects=(),
            claim_bindings=(),
        )
    elif mutation == "rename_subject":
        changed = replace(
            specification,
            ordered_subjects=(
                replace(
                    specification.ordered_subjects[0],
                    label="Renamed C.A.T.T.U.S",
                ),
                specification.ordered_subjects[1],
            ),
        )
    elif mutation == "change_output":
        changed = replace(specification, preserved_output_format="json")
    else:
        changed = replace(
            specification,
            constraints=(
                SynthesisConstraint(
                    kind="requirement",
                    text="A different constraint.",
                    ordinal=1,
                ),
            ),
        )
    result = compose_structured_synthesis(
        _request(request.task_contract, changed, assessments)
    )
    assert result.status == STATUS_INCONSISTENT_INPUT
    assert result.slot_results == ()
    assert expected_inconsistency in result.inconsistencies


def test_output_preservation_gate_rejects_a_shape_switched_result() -> None:
    request, _ = _deepseek_fixture()
    result = compose_structured_synthesis(request)
    assert request.specification is not None
    tampered_result = replace(result, output_shape=OUTPUT_SHAPE_ORDERED_SECTIONS)
    report = check_synthesis_preservation(
        request.task_contract,
        request.specification,
        tampered_result,
    )
    assert report.status == PRESERVATION_FAILED_STATUS
    assert PRESERVATION_OUTPUT_SHAPE_CHANGED in report.failures


def test_multiple_claims_in_one_slot_remain_mixed_not_inferred() -> None:
    contract = _task_contract()
    claims = (_claim("P-1", STATUS_SUPPORTED), _claim("P-2", STATUS_CONTRADICTED))
    slot = SynthesisSlot(
        slot_id="answer",
        label="answer",
        ordinal=1,
        required_proposition_ids=("P-1", "P-2"),
    )
    specification = SynthesisSpecification(
        task_contract_fingerprint=task_contract_fingerprint(contract),
        preservation_fingerprint=task_preservation_fingerprint(contract),
        output_shape=OUTPUT_SHAPE_SINGLE_SLOT,
        preserved_output_format="json",
        ordered_subjects=(),
        ordered_slots=(slot,),
        constraints=(),
        claim_bindings=tuple(
            ClaimSlotBinding(
                slot_id=slot.slot_id,
                proposition_id=claim.proposition_id,
                expected_assessment_fingerprint=claim.assessment_fingerprint,
                provenance=BINDING_EXPLICIT_TASK_CONTRACT,
            )
            for claim in claims
        ),
    )
    result = compose_structured_synthesis(_request(contract, specification, claims))
    slot_result = result.slot_results[0]
    assert slot_result.slot_status == SLOT_MIXED_CLAIM_STATES
    assert slot_result.claim_statuses == (STATUS_SUPPORTED, STATUS_CONTRADICTED)
    assert UNRESOLVED_MIXED_CLAIMS in result.unresolved_requirements
    assert result.as_dict()["guardrails"]["claim_invented"] is False


def test_one_assessment_is_reused_only_when_two_slots_bind_it_explicitly() -> None:
    contract = _task_contract(rubric=("first", "second"))
    claim = _claim("P-shared")
    slots = tuple(
        SynthesisSlot(
            slot_id=label,
            label=label,
            ordinal=ordinal,
            required_proposition_ids=("P-shared",),
        )
        for ordinal, label in enumerate(("first", "second"), start=1)
    )
    specification = SynthesisSpecification(
        task_contract_fingerprint=task_contract_fingerprint(contract),
        preservation_fingerprint=task_preservation_fingerprint(contract),
        output_shape=OUTPUT_SHAPE_ORDERED_SECTIONS,
        preserved_output_format="json",
        ordered_subjects=(),
        ordered_slots=slots,
        constraints=(),
        claim_bindings=tuple(
            ClaimSlotBinding(
                slot_id=slot.slot_id,
                proposition_id=claim.proposition_id,
                expected_assessment_fingerprint=claim.assessment_fingerprint,
                provenance=BINDING_EXPLICIT_TASK_CONTRACT,
            )
            for slot in slots
        ),
    )
    result = compose_structured_synthesis(
        _request(contract, specification, (claim,))
    )
    assert result.status == STATUS_COMPOSED
    assert len(result.slot_results) == 2
    assert all(
        item.claim_assessment_refs[0].assessment_fingerprint
        == claim.assessment_fingerprint
        for item in result.slot_results
    )


def test_negative_proposition_insufficiency_stays_insufficiency() -> None:
    request, claim = _single_fixture(
        STATUS_INSUFFICIENT,
        proposition_type=PROPOSITION_NEGATIVE_EXISTENTIAL,
    )
    result = compose_structured_synthesis(request)
    assert claim.proposition_type == PROPOSITION_NEGATIVE_EXISTENTIAL
    assert result.slot_results[0].claim_statuses == (STATUS_INSUFFICIENT,)
    assert result.slot_results[0].slot_status == SLOT_UNRESOLVED_INSUFFICIENT
    assert result.as_dict()["guardrails"]["claim_reinterpreted"] is False


def test_decision_requirement_is_preserved_but_never_executed() -> None:
    request, _ = _deepseek_fixture(
        statuses=(STATUS_SUPPORTED,) * 10,
        decision_requested=True,
    )
    result = compose_structured_synthesis(request)
    assert result.status == STATUS_COMPOSED_WITH_GAPS
    assert result.decision_requirement.requested is True
    assert result.decision_requirement.type == DECISION_COMPARATIVE_SELECTION
    assert result.decision_requirement.decision_performed is False
    assert UNRESOLVED_DOWNSTREAM_DECISION in result.unresolved_requirements
    guardrails = result.as_dict()["guardrails"]
    assert guardrails["decision_performed"] is False
    assert guardrails["winner_selected"] is False
    assert guardrails["score_computed"] is False
    assert guardrails["confidence_computed"] is False


def test_shuffled_assessments_and_bindings_are_byte_deterministic() -> None:
    ordered_request, _ = _deepseek_fixture()
    shuffled_request, _ = _deepseek_fixture(
        reverse_bindings=True,
        reverse_assessments=True,
    )
    ordered = compose_structured_synthesis(ordered_request)
    shuffled = compose_structured_synthesis(shuffled_request)
    assert render_structured_synthesis_json(ordered) == (
        render_structured_synthesis_json(shuffled)
    )
    assert ordered.synthesis_fingerprint == shuffled.synthesis_fingerprint
    assert tuple(item.label for item in shuffled.ordered_slots) == DIMENSIONS


@pytest.mark.parametrize(
    ("tamper", "expected_inconsistency"),
    (
        ("specification_fingerprint", INCONSISTENT_SPECIFICATION_FINGERPRINT),
        ("task_contract", INCONSISTENT_TASK_FINGERPRINT),
        ("assessment", INCONSISTENT_ASSESSMENT_UNBOUND),
    ),
)
def test_fingerprint_boundaries_fail_closed(
    tamper: str, expected_inconsistency: str
) -> None:
    request, assessment = _single_fixture()
    specification = request.specification
    assert specification is not None
    if tamper == "specification_fingerprint":
        changed_request = _request(
            request.task_contract,
            specification,
            (assessment,),
            expected_fingerprint="0" * 64,
        )
    elif tamper == "task_contract":
        changed_contract = replace(
            request.task_contract,
            raw_request=RawRequest(text="Tampered user request."),
        )
        changed_request = _request(changed_contract, specification, (assessment,))
    else:
        object.__setattr__(
            assessment,
            "proposition_text",
            "Tampered proposition text.",
        )
        changed_request = _request(
            request.task_contract,
            specification,
            (assessment,),
        )
    result = compose_structured_synthesis(changed_request)
    assert result.status == STATUS_INCONSISTENT_INPUT
    assert result.slot_results == ()
    assert expected_inconsistency in result.inconsistencies


def test_serialization_has_references_only_and_enforces_authority_guardrails() -> None:
    request, assessments = _deepseek_fixture(statuses=(STATUS_SUPPORTED,) * 10)
    result = compose_structured_synthesis(request)
    payload = result.as_dict()
    serialized = render_structured_synthesis_json(result)
    assert result.status == STATUS_COMPOSED
    assert result.semantic_basis == BASIS_ANALYZER_ASSESSED
    assert all(claim.proposition_text not in serialized for claim in assessments)
    assert "proposition_text" not in serialized
    assert "answer_text" not in serialized
    assert "response_text" not in serialized
    assert "paragraph" not in serialized
    authority = payload["authority"]
    assert authority["structured_synthesis_authority"] is True
    assert authority["human_approval_required"] is True
    assert all(
        authority[key] is False
        for key in authority
        if key
        not in {"structured_synthesis_authority", "human_approval_required"}
    )
    guardrails = payload["guardrails"]
    assert guardrails["claim_assessments_composed"] is True
    assert guardrails["task_shape_preserved"] is True
    assert guardrails["output_structure_preserved"] is True
    assert guardrails["unresolved_states_preserved"] is True
    assert all(
        guardrails[key] is False
        for key in (
            "model_called",
            "repository_read",
            "evidence_acquired",
            "evidence_reverified",
            "claim_invented",
            "claim_reinterpreted",
            "conflict_resolved",
            "decision_performed",
            "winner_selected",
            "confidence_computed",
            "score_computed",
            "final_response_generated",
        )
    )
    assert json.loads(serialized) == payload


def test_unbound_non_matrix_slot_cannot_name_an_unknown_subject() -> None:
    with pytest.raises(ValueError, match="unknown subject"):
        SynthesisSpecification(
            task_contract_fingerprint=_digest("task"),
            preservation_fingerprint=_digest("preservation"),
            output_shape=OUTPUT_SHAPE_ORDERED_SECTIONS,
            preserved_output_format="json",
            ordered_subjects=(
                SynthesisSubject(subject_id="subject-a", label="A", ordinal=1),
            ),
            ordered_slots=(
                SynthesisSlot(
                    slot_id="answer",
                    label="answer",
                    ordinal=1,
                    subject_id="subject-b",
                    required_proposition_ids=("P-1",),
                ),
            ),
            constraints=(),
            claim_bindings=(),
        )


def test_literal_output_format_overrides_inference_and_ambiguity_fails_closed() -> None:
    original_request, assessment = _single_fixture()
    original_specification = original_request.specification
    assert original_specification is not None
    contract = replace(
        original_request.task_contract,
        requested_output=RequestedOutput(
            format="report",
            provenance=PROVENANCE_INFERRED,
            confidence=0.8,
        ),
        explicit_evidence=ExplicitEvidence(
            requested_outputs=(
                ExplicitRequestedOutput(format="table", evidence_text="as a table"),
            ),
        ),
    )
    specification = replace(
        original_specification,
        task_contract_fingerprint=task_contract_fingerprint(contract),
        preservation_fingerprint=task_preservation_fingerprint(contract),
        preserved_output_format="table",
    )
    preserved = compose_structured_synthesis(
        _request(contract, specification, (assessment,))
    )
    assert preserved.status == STATUS_COMPOSED
    assert preserved.preserved_output_format == "table"

    inferred_overwrite = replace(specification, preserved_output_format="report")
    rejected_overwrite = compose_structured_synthesis(
        _request(contract, inferred_overwrite, (assessment,))
    )
    assert rejected_overwrite.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_OUTPUT_FORMAT in rejected_overwrite.inconsistencies

    ambiguous_contract = replace(
        contract,
        explicit_evidence=ExplicitEvidence(
            requested_outputs=(
                ExplicitRequestedOutput(format="table", evidence_text="as a table"),
                ExplicitRequestedOutput(format="json", evidence_text="as JSON"),
            ),
        ),
    )
    ambiguous_specification = replace(
        specification,
        task_contract_fingerprint=task_contract_fingerprint(ambiguous_contract),
        preservation_fingerprint=task_preservation_fingerprint(ambiguous_contract),
    )
    ambiguous = compose_structured_synthesis(
        _request(ambiguous_contract, ambiguous_specification, (assessment,))
    )
    assert ambiguous.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_TASK_OUTPUT_FORMAT_AMBIGUOUS in ambiguous.inconsistencies


def test_preservation_gate_cannot_certify_a_fabricated_claim_reference() -> None:
    request, assessment = _single_fixture(assessment_present=False)
    result = compose_structured_synthesis(request)
    specification = request.specification
    assert specification is not None
    fabricated_reference = ClaimAssessmentReference(
        assessment_fingerprint=assessment.assessment_fingerprint,
        proposition_id=assessment.proposition_id,
        proposition_sha256=assessment.proposition_sha256,
        assessment_status=STATUS_SUPPORTED,
        semantic_basis=BASIS_ANALYZER_ASSESSED,
    )
    fabricated_slot = replace(
        result.slot_results[0],
        claim_assessment_refs=(fabricated_reference,),
        missing_proposition_ids=(),
        slot_status=SLOT_POPULATED,
        claim_statuses=(STATUS_SUPPORTED,),
        unresolved_reasons=(),
        semantic_basis=BASIS_ANALYZER_ASSESSED,
    )
    fabricated = replace(
        result,
        status=STATUS_COMPOSED,
        slot_results=(fabricated_slot,),
        unresolved_requirements=(),
        semantic_basis=BASIS_ANALYZER_ASSESSED,
    )
    report = check_synthesis_preservation(
        request.task_contract,
        specification,
        fabricated,
        (),
    )
    assert report.status == PRESERVATION_FAILED_STATUS
    assert PRESERVATION_CLAIM_REFERENCE_CHANGED in report.failures
    assert PRESERVATION_RESULT_DERIVATION_CHANGED in report.failures
    assert fabricated.structured_synthesis_authority is False


def test_stale_preservation_receipt_revokes_authority_and_positive_guardrails() -> None:
    request, assessment = _single_fixture()
    result = compose_structured_synthesis(request)
    specification = request.specification
    assert specification is not None
    tampered = replace(
        result,
        status=STATUS_COMPOSED_WITH_GAPS,
        unresolved_requirements=(UNRESOLVED_CONFLICT,),
    )
    assert tampered.preservation is not None and tampered.preservation.passed
    assert tampered.preservation_current is False
    assert tampered.structured_synthesis_authority is False
    guardrails = tampered.as_dict()["guardrails"]
    assert guardrails["task_shape_preserved"] is False
    assert guardrails["output_structure_preserved"] is False
    assert guardrails["unresolved_states_preserved"] is False
    report = check_synthesis_preservation(
        request.task_contract,
        specification,
        tampered,
        (assessment,),
    )
    assert report.status == PRESERVATION_FAILED_STATUS
    assert PRESERVATION_RESULT_DERIVATION_CHANGED in report.failures


@pytest.mark.parametrize(
    ("contract_mutation", "expected_inconsistency"),
    (
        ("failed_preservation", INCONSISTENT_TASK_PRESERVATION),
        ("truncated_structure", INCONSISTENT_TASK_STRUCTURE_TRUNCATED),
    ),
)
def test_missing_specification_does_not_hide_invalid_task_contract(
    contract_mutation: str,
    expected_inconsistency: str,
) -> None:
    contract = _task_contract()
    if contract_mutation == "failed_preservation":
        contract = replace(
            contract,
            preservation=PreservationReport(
                status=PRESERVATION_FAILED,
                reasons=("fixture failure",),
            ),
            routing_allowed=False,
        )
    else:
        contract = replace(
            contract,
            explicit_evidence=ExplicitEvidence(truncated_fields=("list_items",)),
        )
    request = SynthesisRequest(
        task_contract=contract,
        specification=None,
        claim_assessments=(),
        expected_synthesis_specification_fingerprint=None,
    )
    result = compose_structured_synthesis(request)
    assert result.status == STATUS_INCONSISTENT_INPUT
    assert expected_inconsistency in result.inconsistencies
    assert result.status != STATUS_INCOMPLETE_SPECIFICATION
