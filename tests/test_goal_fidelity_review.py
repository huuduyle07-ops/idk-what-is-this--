"""Focused CHECK.2 post-run goal-fidelity verification regressions.

Every fact in these tests is constructed directly.  No repository is traversed,
no source or diff is read, no validation is executed, no evidence is acquired
and no model is called.  The static authority boundary lives in
``test_goal_fidelity_review_boundaries``.

The CHECK.1 reconciliations are produced by CHECK.1 itself rather than
hand-built, so the entry gate is exercised against real reconciliation output
and the ``blocked`` cases really are blocked for the reason they claim.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from core.claim_assessment import (
    ASSESSMENT_BASIS_GATED_ANALYZER_ASSESSMENTS,
    ASSESSMENT_BASIS_NOT_ASSESSED,
    BASIS_ANALYZER_ASSESSED,
    BASIS_NOT_ESTABLISHED,
    CORROBORATION_INDEPENDENCE_UNKNOWN,
    CORROBORATION_NOT_ASSESSED,
    INCONSISTENT_PROPOSITION_BINDING,
    MAX_PROPOSITION_CHARS,
    STATUS_CONFLICTING,
    STATUS_CONTRADICTED,
    STATUS_COVERAGE_INCOMPLETE,
    STATUS_CURRENT_STATE_INCONSISTENT,
    STATUS_CURRENT_STATE_UNESTABLISHED,
    STATUS_INCONSISTENT_INPUT as CLAIM_INCONSISTENT_INPUT,
    STATUS_INSUFFICIENT,
    STATUS_SUPPORTED,
    ClaimAssessment,
)
from core.evidence_set_assessment import (
    CONFLICT_CONFLICTING,
    CONFLICT_CONTRADICTION_ONLY,
    CONFLICT_NOT_ASSESSED,
    CONFLICT_NO_DIRECTIONAL_EVIDENCE,
    CONFLICT_SUPPORT_ONLY,
)
from core.goal_fidelity_review import (
    CHECK2_CHECK_1_GATE_EVALUATED,
    CHECK2_EXECUTION_SEVERITY_PRESERVED,
    CHECK2_INPUT_REJECTED,
    CHECK2_NO_CONFLICT_ADJUDICATED,
    CHECK2_NO_MAJORITY_COMPUTED,
    CHECK2_NO_RUN_VERDICT_PRODUCED,
    CHECK2_NO_SEMANTIC_REANALYSIS_PERFORMED,
    CHECK2_PRESERVATION_OBLIGATIONS_RECONCILED,
    CHECK2_UNBOUND_CLAIM_ASSESSMENTS_IGNORED,
    CHECK_1_ENTRY_POLICY,
    GOAL_FIDELITY_STATUSES,
    INCONSISTENT_BINDING_UNKNOWN_OBLIGATION,
    INCONSISTENT_CHECK_1_INPUT_UNUSABLE,
    INCONSISTENT_CLAIM_DUPLICATE,
    INCONSISTENT_CLAIM_EVIDENCE_SET_BINDING,
    INCONSISTENT_CLAIM_FINGERPRINT,
    INCONSISTENT_CLAIM_PROPOSITION_BINDING,
    INCONSISTENT_GOAL_OBLIGATION_DROPPED,
    INCONSISTENT_LEDGER_FINGERPRINT,
    INCONSISTENT_LEDGER_TASK_BINDING,
    INCONSISTENT_OBLIGATION_SOURCE_KIND,
    INCONSISTENT_OBLIGATION_SOURCE_TEXT,
    INCONSISTENT_OBLIGATION_WIDENED,
    INCONSISTENT_POST_RUN_STATE_BINDING,
    INCONSISTENT_PRESERVATION_OBLIGATION_DROPPED,
    INCONSISTENT_RECONCILIATION_FINGERPRINT,
    INCONSISTENT_SPECIFICATION_FINGERPRINT,
    INCONSISTENT_SPECIFICATION_RUN_BINDING,
    INCONSISTENT_SPECIFICATION_TASK_BINDING,
    INCONSISTENT_TASK_CONTRACT_FINGERPRINT,
    MAX_PROPOSITION_TEXT_CHARS,
    OBLIGATION_BINDING_INVALID,
    OBLIGATION_BLOCKED_BY_RECONCILIATION,
    OBLIGATION_COMPOSITE_UNSUPPORTED,
    OBLIGATION_CONFLICTING,
    OBLIGATION_COVERAGE_INCOMPLETE,
    OBLIGATION_CURRENT_STATE_INCONSISTENT,
    OBLIGATION_CURRENT_STATE_UNESTABLISHED,
    OBLIGATION_INSUFFICIENT,
    OBLIGATION_KIND_CONSTRAINT,
    OBLIGATION_KIND_GOAL,
    OBLIGATION_KIND_PRESERVATION,
    OBLIGATION_MISSING_CLAIM,
    OBLIGATION_REASON_CLAIM_ABSENT,
    OBLIGATION_REASON_CLAIM_REFUSED,
    OBLIGATION_REASON_DIAGNOSTIC_ONLY,
    OBLIGATION_REASON_FINAL_STATE_BOUND,
    OBLIGATION_REASON_FINAL_STATE_UNBOUND,
    OBLIGATION_REASON_MULTIPLE_BINDINGS,
    OBLIGATION_REASON_NO_BINDING,
    OBLIGATION_REASON_OPTIONAL,
    OBLIGATION_REASON_POLARITY_ABSENT,
    OBLIGATION_REASON_POLARITY_PROVENANCE_ABSENT,
    OBLIGATION_REASON_RECONCILIATION_BLOCKED,
    OBLIGATION_SATISFIED,
    OBLIGATION_STATUSES,
    OBLIGATION_VIOLATED,
    POLARITY_CONTRADICTION_MEANS_SATISFIED,
    POLARITY_PROVENANCE_GOAL_PROJECTION,
    POLARITY_PROVENANCE_PRESERVED_REQUIREMENT,
    POLARITY_SUPPORT_MEANS_SATISFIED,
    REQUIREMENT_PROVENANCE_TASK_CONTRACT,
    REVIEW_ASSESSABLE,
    REVIEW_BLOCKED,
    REVIEW_DIAGNOSTIC_ONLY,
    REVIEW_MODE_MEANING,
    SATISFIED_MEANING,
    STATE_BINDING_BOUND,
    STATE_BINDING_PROVENANCE_RECEIPT,
    STATE_BINDING_UNAVAILABLE,
    STATUS_ASSESSED,
    STATUS_ASSESSED_WITH_GAPS,
    STATUS_BLOCKED,
    STATUS_DIAGNOSTIC_ONLY,
    STATUS_INCONSISTENT_INPUT,
    ExplicitRequirementLedger,
    ExplicitRequirementSource,
    GoalFidelityReviewRequest,
    GoalVerificationObligation,
    GoalVerificationSpecification,
    ObligationClaimBinding,
    PostRunStateBinding,
    explicit_requirement_ledger_fingerprint,
    goal_fidelity_authority,
    goal_fidelity_guardrails,
    goal_verification_specification_fingerprint,
    render_goal_fidelity_assessment_json,
    review_goal_fidelity,
)
from core.post_run_reconciliation import (
    CHANGE_MODIFIED,
    DECLARED_VALIDATION_PASSED,
    FORBIDDEN_SENSITIVE,
    OBLIGATION_BEHAVIOR_PRESERVATION,
    OBLIGATION_INTERFACE_PRESERVATION,
    PATH_AUTHORITY_FORBIDDEN,
    PATH_AUTHORITY_WRITABLE,
    RECEIPT_PASSED,
    STATUS_BLOCKED as CHECK_1_BLOCKED,
    STATUS_INCOMPLETE as CHECK_1_INCOMPLETE,
    STATUS_INCONSISTENT_INPUT as CHECK_1_INCONSISTENT_INPUT,
    STATUS_RECONCILED as CHECK_1_RECONCILED,
    STATUS_RECONCILED_WITH_WARNINGS as CHECK_1_WARNINGS,
    STATUS_SUSPICIOUS as CHECK_1_SUSPICIOUS,
    VALIDATION_UNIT_TESTS,
    WORKER_CLAIM_SUCCESS,
    AuthorizedPath,
    DeclaredChange,
    DeclaredValidationAction,
    ExecutionAuthorization,
    ObservedChange,
    ObservedPostRunFacts,
    PostRunReconciliationRequest,
    PreservationObligation,
    ValidationExpectation,
    ValidationReceipt,
    WorkerReport,
    execution_authorization_fingerprint,
    observed_post_run_facts_fingerprint,
    reconcile_post_run,
    worker_report_fingerprint,
)


# ── Fixture helpers ───────────────────────────────────────────────────────────

RUN = "RUN-1"
REPO = "REPO-1"
TASK = "TASK-CONTRACT-A"

INDEXER = "core/indexer.py"
EMBEDDINGS = "core/embeddings.py"
CONFIG = "core/config.py"
TEST_SCOPE = "tests/test_indexer.py"


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


S0 = digest("state-0")
S1 = digest("state-1")
S2 = digest("state-2")

TMP_TEXT = "exclude .tmp files from indexing"
EMBED_TEXT = "do not change embedding behavior"


def check1(
    *,
    variant: str = "reconciled",
    preservation: tuple[PreservationObligation, ...] = (),
    task_label: str = TASK,
):
    """Build one real CHECK.1 reconciliation in the requested state."""
    authorized = [AuthorizedPath(path=INDEXER, authority=PATH_AUTHORITY_WRITABLE)]
    observed = [
        ObservedChange(
            path=INDEXER,
            change_kind=CHANGE_MODIFIED,
            before_sha256=digest("indexer-0"),
            after_sha256=digest("indexer-1"),
        )
    ]
    declared = [DeclaredChange(path=INDEXER, change_kind=CHANGE_MODIFIED)]
    final_state = S1
    receipt_state = S1

    if variant == "suspicious":
        authorized.append(
            AuthorizedPath(path=EMBEDDINGS, authority=PATH_AUTHORITY_WRITABLE)
        )
        observed.append(
            ObservedChange(
                path=EMBEDDINGS,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("embed-0"),
                after_sha256=digest("embed-1"),
            )
        )
    if variant == "blocked":
        authorized.append(
            AuthorizedPath(
                path=CONFIG,
                authority=PATH_AUTHORITY_FORBIDDEN,
                forbidden_reason=FORBIDDEN_SENSITIVE,
            )
        )
        observed.append(
            ObservedChange(
                path=CONFIG,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("config-0"),
                after_sha256=digest("config-1"),
            )
        )
        declared.append(DeclaredChange(path=CONFIG, change_kind=CHANGE_MODIFIED))
    if variant == "incomplete":
        final_state = S2

    authorization = ExecutionAuthorization(
        authorization_id="AUTH-1",
        execution_run_id=RUN,
        repository_id=REPO,
        task_contract_fingerprint=digest(task_label),
        pre_execution_state_fingerprint=S0,
        authorized_paths=tuple(authorized),
        validation_expectations=(
            ValidationExpectation(
                validation_id="V-unit",
                validation_kind=VALIDATION_UNIT_TESTS,
                required=True,
                target_scope=(TEST_SCOPE,),
            ),
        ),
        preservation_obligations=preservation,
    )
    report = WorkerReport(
        report_id="REPORT-1",
        execution_run_id=RUN,
        declared_status=WORKER_CLAIM_SUCCESS,
        declared_changes=tuple(declared),
        declared_validation_actions=(
            DeclaredValidationAction(
                validation_id="V-unit",
                validation_kind=VALIDATION_UNIT_TESTS,
                declared_result=DECLARED_VALIDATION_PASSED,
            ),
        ),
    )
    facts = ObservedPostRunFacts(
        facts_id="FACTS-1",
        execution_run_id=RUN,
        repository_id=REPO,
        pre_execution_state_fingerprint=S0,
        post_execution_state_fingerprint=S1,
        final_state_fingerprint=final_state,
        observed_changes=tuple(observed),
        validation_receipts=(
            ValidationReceipt(
                receipt_id="RECEIPT-1",
                validation_id="V-unit",
                execution_run_id=RUN,
                repository_id=REPO,
                validation_kind=VALIDATION_UNIT_TESTS,
                result=RECEIPT_PASSED,
                state_fingerprint=receipt_state,
                target_scope=(TEST_SCOPE,),
            ),
        ),
    )
    expected_task = authorization.task_contract_fingerprint
    if variant == "inconsistent":
        expected_task = digest("some-other-task-contract")
    return reconcile_post_run(
        PostRunReconciliationRequest(
            authorization=authorization,
            worker_report=report,
            observed_facts=facts,
            expected_task_contract_fingerprint=expected_task,
            expected_authorization_fingerprint=(
                execution_authorization_fingerprint(authorization)
            ),
            expected_worker_report_fingerprint=worker_report_fingerprint(report),
            expected_observed_facts_fingerprint=(
                observed_post_run_facts_fingerprint(facts)
            ),
        )
    )


def claim(
    *,
    proposition_id: str,
    text: str,
    status: str = STATUS_SUPPORTED,
    conflict: str | None = None,
    scope: str = "implementation_state",
    proposition_type: str = "positive",
    evidence_set: str = "set-1",
) -> ClaimAssessment:
    """Build one frozen CLAIM.1 record directly, exactly as CLAIM.1 emits it."""
    if status == CLAIM_INCONSISTENT_INPUT:
        return ClaimAssessment(
            assessment_status=status,
            proposition_id=proposition_id,
            proposition_sha256=digest(text),
            proposition_text=text,
            proposition_type=proposition_type,
            proposition_scope=scope,
            evidence_set_fingerprint=digest(evidence_set),
            evidence_set_request_fingerprint=digest("set-request"),
            request_fingerprint=digest(f"claim-request-{proposition_id}"),
            semantic_basis=BASIS_NOT_ESTABLISHED,
            assessment_basis=ASSESSMENT_BASIS_NOT_ASSESSED,
            conflict_status=CONFLICT_NOT_ASSESSED,
            corroboration_status=CORROBORATION_NOT_ASSESSED,
            inconsistencies=(INCONSISTENT_PROPOSITION_BINDING,),
        )
    if conflict is None:
        conflict = {
            STATUS_SUPPORTED: CONFLICT_SUPPORT_ONLY,
            STATUS_CONTRADICTED: CONFLICT_CONTRADICTION_ONLY,
            STATUS_CONFLICTING: CONFLICT_CONFLICTING,
            STATUS_INSUFFICIENT: CONFLICT_NO_DIRECTIONAL_EVIDENCE,
            STATUS_COVERAGE_INCOMPLETE: CONFLICT_SUPPORT_ONLY,
            STATUS_CURRENT_STATE_UNESTABLISHED: CONFLICT_SUPPORT_ONLY,
            STATUS_CURRENT_STATE_INCONSISTENT: CONFLICT_SUPPORT_ONLY,
        }[status]
    directional = ()
    if conflict != CONFLICT_NO_DIRECTIONAL_EVIDENCE:
        directional = (digest(f"record-{proposition_id}"),)
    return ClaimAssessment(
        assessment_status=status,
        proposition_id=proposition_id,
        proposition_sha256=digest(text),
        proposition_text=text,
        proposition_type=proposition_type,
        proposition_scope=scope,
        evidence_set_fingerprint=digest(evidence_set),
        evidence_set_request_fingerprint=digest("set-request"),
        request_fingerprint=digest(f"claim-request-{proposition_id}"),
        semantic_basis=BASIS_ANALYZER_ASSESSED,
        assessment_basis=ASSESSMENT_BASIS_GATED_ANALYZER_ASSESSMENTS,
        conflict_status=conflict,
        corroboration_status=CORROBORATION_INDEPENDENCE_UNKNOWN,
        directional_record_refs=directional,
    )


def ledger(
    reconciliation, *requirements: ExplicitRequirementSource
) -> ExplicitRequirementLedger:
    return ExplicitRequirementLedger(
        task_contract_fingerprint=reconciliation.task_contract_fingerprint,
        requirements=requirements,
    )


def goal_requirement(
    requirement_id: str,
    text: str,
    *,
    kind: str = OBLIGATION_KIND_GOAL,
    required: bool = True,
    ordinal: int | None = None,
) -> ExplicitRequirementSource:
    return ExplicitRequirementSource(
        requirement_id=requirement_id,
        requirement_kind=kind,
        requirement_text_sha256=digest(text),
        provenance=REQUIREMENT_PROVENANCE_TASK_CONTRACT,
        required=required,
        ordinal=ordinal,
    )


def goal_obligation(
    obligation_id: str,
    source_id: str,
    text: str,
    *,
    kind: str = OBLIGATION_KIND_GOAL,
    required: bool = True,
    ordinal: int | None = None,
) -> GoalVerificationObligation:
    return GoalVerificationObligation(
        obligation_id=obligation_id,
        obligation_kind=kind,
        obligation_text_sha256=digest(text),
        source_requirement_id=source_id,
        required=required,
        ordinal=ordinal,
    )


def preservation_obligation(
    obligation_id: str,
    source_id: str,
    text: str,
    *,
    kind: str = OBLIGATION_BEHAVIOR_PRESERVATION,
    ordinal: int | None = None,
) -> GoalVerificationObligation:
    return GoalVerificationObligation(
        obligation_id=obligation_id,
        obligation_kind=OBLIGATION_KIND_PRESERVATION,
        obligation_text_sha256=digest(text),
        source_requirement_id=source_id,
        preservation_obligation_kind=kind,
        ordinal=ordinal,
    )


def binding(
    obligation_id: str,
    assessment: ClaimAssessment,
    *,
    polarity: str | None = POLARITY_SUPPORT_MEANS_SATISFIED,
    provenance: str | None = POLARITY_PROVENANCE_GOAL_PROJECTION,
    state_binding: PostRunStateBinding | None = None,
    evidence_set_fingerprint: str | None = None,
    fingerprint_override: str | None = None,
    proposition_digest_override: str | None = None,
) -> ObligationClaimBinding:
    return ObligationClaimBinding(
        obligation_id=obligation_id,
        proposition_id=assessment.proposition_id,
        proposition_sha256=(
            proposition_digest_override or assessment.proposition_sha256
        ),
        expected_claim_assessment_fingerprint=(
            fingerprint_override or assessment.assessment_fingerprint
        ),
        satisfaction_polarity=polarity,
        polarity_provenance=provenance,
        expected_evidence_set_fingerprint=evidence_set_fingerprint,
        post_run_state_binding=state_binding,
    )


def state_binding_for(reconciliation) -> PostRunStateBinding:
    return PostRunStateBinding(
        final_state_fingerprint=(
            reconciliation.final_state_binding.final_state_fingerprint
        ),
        state_receipt_sha256=digest("final-state-receipt"),
        provenance=STATE_BINDING_PROVENANCE_RECEIPT,
    )


def specification(
    reconciliation,
    requirement_ledger: ExplicitRequirementLedger,
    obligations: tuple[GoalVerificationObligation, ...],
    bindings: tuple[ObligationClaimBinding, ...],
    *,
    ledger_fingerprint_override: str | None = None,
    task_fingerprint_override: str | None = None,
    reconciliation_fingerprint_override: str | None = None,
) -> GoalVerificationSpecification:
    return GoalVerificationSpecification(
        task_contract_fingerprint=(
            task_fingerprint_override or reconciliation.task_contract_fingerprint
        ),
        check_1_reconciliation_fingerprint=(
            reconciliation_fingerprint_override
            or reconciliation.reconciliation_fingerprint
        ),
        requirement_ledger_fingerprint=(
            ledger_fingerprint_override
            or explicit_requirement_ledger_fingerprint(requirement_ledger)
        ),
        obligations=obligations,
        bindings=bindings,
    )


def review(
    reconciliation,
    requirement_ledger: ExplicitRequirementLedger,
    spec: GoalVerificationSpecification,
    claims: tuple[ClaimAssessment, ...] = (),
    **overrides: object,
):
    payload: dict[str, object] = {
        "expected_task_contract_fingerprint": (
            reconciliation.task_contract_fingerprint
        ),
        "expected_reconciliation_fingerprint": (
            reconciliation.reconciliation_fingerprint
        ),
        "expected_specification_fingerprint": (
            goal_verification_specification_fingerprint(spec)
        ),
        "expected_requirement_ledger_fingerprint": (
            explicit_requirement_ledger_fingerprint(requirement_ledger)
        ),
    }
    payload.update(overrides)
    return review_goal_fidelity(
        GoalFidelityReviewRequest(
            reconciliation=reconciliation,
            specification=spec,
            requirement_ledger=requirement_ledger,
            claim_assessments=claims,
            **payload,
        )
    )


def single_goal_case(
    *,
    variant: str = "reconciled",
    claim_status: str = STATUS_SUPPORTED,
    polarity: str | None = POLARITY_SUPPORT_MEANS_SATISFIED,
    provenance: str | None = POLARITY_PROVENANCE_GOAL_PROJECTION,
    bind_claim: bool = True,
    supply_claim: bool = True,
    bind_final_state: bool = False,
):
    """The recurring shape: one explicit goal, one bound proposition."""
    reconciliation = check1(variant=variant)
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    assessment = claim(
        proposition_id="P-tmp",
        text=(
            "Final implementation excludes .tmp files from repository indexing."
        ),
        status=claim_status,
    )
    bindings: tuple[ObligationClaimBinding, ...] = ()
    if bind_claim:
        bindings = (
            binding(
                "G1",
                assessment,
                polarity=polarity,
                provenance=provenance,
                state_binding=(
                    state_binding_for(reconciliation) if bind_final_state else None
                ),
            ),
        )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        bindings,
    )
    claims = (assessment,) if supply_claim else ()
    return reconciliation, review(reconciliation, requirement_ledger, spec, claims)


def result_for(assessment, obligation_id: str):
    found = assessment.result_for(obligation_id)
    assert found is not None, f"no obligation result for {obligation_id}"
    return found


# ── A–F: the CHECK.1 entry gate ───────────────────────────────────────────────

def test_a_reconciled_execution_is_assessable():
    reconciliation, result = single_goal_case(variant="reconciled")

    assert reconciliation.status == CHECK_1_RECONCILED
    assert result.review_mode == REVIEW_ASSESSABLE
    assert result.status == STATUS_ASSESSED_WITH_GAPS
    assert result.semantic_goal_review_authority is True


def test_b_reconciled_with_warnings_is_assessable():
    reconciliation = check1(
        variant="reconciled",
        preservation=(
            PreservationObligation(
                obligation_id="P1",
                kind=OBLIGATION_BEHAVIOR_PRESERVATION,
                text_sha256=digest(EMBED_TEXT),
            ),
        ),
    )
    assert reconciliation.status == CHECK_1_WARNINGS

    requirement_ledger = ledger(reconciliation)
    preserved = claim(
        proposition_id="P-embed",
        text="Final implementation preserves the previous embedding behaviour.",
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (preservation_obligation("O-P1", "P1", EMBED_TEXT),),
        (
            binding(
                "O-P1",
                preserved,
                provenance=POLARITY_PROVENANCE_PRESERVED_REQUIREMENT,
            ),
        ),
    )
    result = review(reconciliation, requirement_ledger, spec, (preserved,))

    assert result.review_mode == REVIEW_ASSESSABLE
    assert result.satisfied_obligations == ("O-P1",)
    assert CHECK2_PRESERVATION_OBLIGATIONS_RECONCILED in result.reasons


def test_c_suspicious_execution_is_diagnostic_only():
    reconciliation, result = single_goal_case(variant="suspicious")

    assert reconciliation.status == CHECK_1_SUSPICIOUS
    assert result.review_mode == REVIEW_DIAGNOSTIC_ONLY
    assert result.status == STATUS_DIAGNOSTIC_ONLY
    assert result.semantic_goal_review_authority is False


def test_d_incomplete_execution_is_diagnostic_only():
    reconciliation, result = single_goal_case(variant="incomplete")

    assert reconciliation.status == CHECK_1_INCOMPLETE
    assert result.review_mode == REVIEW_DIAGNOSTIC_ONLY
    assert result.status == STATUS_DIAGNOSTIC_ONLY


def test_e_blocked_execution_blocks_the_review():
    reconciliation, result = single_goal_case(variant="blocked")

    assert reconciliation.status == CHECK_1_BLOCKED
    assert result.review_mode == REVIEW_BLOCKED
    assert result.status == STATUS_BLOCKED
    assert result.semantic_goal_review_authority is False


def test_f_an_unusable_reconciliation_is_refused_outright():
    reconciliation = check1(variant="inconsistent")
    assert reconciliation.status == CHECK_1_INCONSISTENT_INPUT

    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (),
    )
    result = review(reconciliation, requirement_ledger, spec)

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert result.review_mode == REVIEW_BLOCKED
    assert INCONSISTENT_CHECK_1_INPUT_UNUSABLE in result.inconsistencies
    assert result.obligation_results == ()
    assert CHECK2_INPUT_REJECTED in result.reasons


def test_the_entry_policy_covers_every_check_1_status():
    from core.post_run_reconciliation import RECONCILIATION_STATUSES

    assert set(CHECK_1_ENTRY_POLICY) == set(RECONCILIATION_STATUSES)


# ── G: a blocked execution cannot be rescued ──────────────────────────────────

def test_g_supporting_semantic_evidence_cannot_rescue_a_blocked_execution():
    """The primary acceptance regression for this phase."""
    preservation = (
        PreservationObligation(
            obligation_id="P1",
            kind=OBLIGATION_BEHAVIOR_PRESERVATION,
            text_sha256=digest(EMBED_TEXT),
        ),
    )
    reconciliation = check1(variant="blocked", preservation=preservation)
    assert reconciliation.status == CHECK_1_BLOCKED
    assert "forbidden_path_changed" in reconciliation.inconsistencies

    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    goal_claim = claim(
        proposition_id="P-tmp",
        text="Final implementation excludes .tmp files from repository indexing.",
    )
    preserved = claim(
        proposition_id="P-embed",
        text="Final implementation preserves the previous embedding behaviour.",
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (
            goal_obligation("G1", "R-G1", TMP_TEXT),
            preservation_obligation("O-P1", "P1", EMBED_TEXT),
        ),
        (
            binding("G1", goal_claim),
            binding(
                "O-P1",
                preserved,
                provenance=POLARITY_PROVENANCE_PRESERVED_REQUIREMENT,
            ),
        ),
    )
    result = review(
        reconciliation, requirement_ledger, spec, (goal_claim, preserved)
    )

    assert result.status == STATUS_BLOCKED
    assert result.review_mode == REVIEW_BLOCKED
    assert result.satisfied_obligations == ()
    assert result.violated_obligations == ()
    assert result.unresolved_obligations == ("G1", "O-P1")
    for obligation_id in ("G1", "O-P1"):
        found = result_for(result, obligation_id)
        assert found.obligation_status == OBLIGATION_BLOCKED_BY_RECONCILIATION
        assert OBLIGATION_REASON_RECONCILIATION_BLOCKED in found.reasons
        # The upstream claim is still visible; it just certifies nothing here.
        assert found.claim_status == STATUS_SUPPORTED
    # The CHECK.1 blocking reason survives verbatim.
    assert (
        "forbidden_path_changed"
        in result.execution_reconciliation.check_1_inconsistencies
    )
    assert result.final_success_authority is False
    assert result.run_verdict_authority is False


def test_g_no_serialized_field_reads_as_recovered_after_a_block():
    _, result = single_goal_case(variant="blocked")
    payload = json.loads(render_goal_fidelity_assessment_json(result))

    assert payload["status"] == STATUS_BLOCKED
    assert payload["satisfied_obligations"] == []
    assert payload["authority"]["semantic_goal_review_authority"] is False
    assert payload["authority"]["final_success_authority"] is False
    assert payload["execution_reconciliation"]["check_1_severity_weakened"] is False
    assert REVIEW_MODE_MEANING[REVIEW_BLOCKED] == payload["review_mode_meaning"]


# ── H–K: goal and preservation outcomes ───────────────────────────────────────

def test_h_a_supported_goal_proposition_satisfies_its_obligation():
    _, result = single_goal_case(claim_status=STATUS_SUPPORTED)
    found = result_for(result, "G1")

    assert found.obligation_status == OBLIGATION_SATISFIED
    assert found.claim_status == STATUS_SUPPORTED
    assert found.semantic_basis == BASIS_ANALYZER_ASSESSED
    assert result.satisfied_obligations == ("G1",)


def test_i_a_contradicted_goal_proposition_violates_its_obligation():
    _, result = single_goal_case(claim_status=STATUS_CONTRADICTED)
    found = result_for(result, "G1")

    assert found.obligation_status == OBLIGATION_VIOLATED
    assert found.claim_status == STATUS_CONTRADICTED
    assert result.violated_obligations == ("G1",)
    assert "violated_obligation_review_required" in result.unresolved_requirements


def _preservation_case(claim_status: str):
    preservation = (
        PreservationObligation(
            obligation_id="P1",
            kind=OBLIGATION_BEHAVIOR_PRESERVATION,
            text_sha256=digest(EMBED_TEXT),
        ),
    )
    reconciliation = check1(variant="reconciled", preservation=preservation)
    requirement_ledger = ledger(reconciliation)
    preserved = claim(
        proposition_id="P-embed",
        text="Final implementation preserves the previous embedding behaviour.",
        status=claim_status,
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (preservation_obligation("O-P1", "P1", EMBED_TEXT),),
        (
            binding(
                "O-P1",
                preserved,
                provenance=POLARITY_PROVENANCE_PRESERVED_REQUIREMENT,
            ),
        ),
    )
    return review(reconciliation, requirement_ledger, spec, (preserved,))


def test_j_a_supported_preservation_proposition_satisfies_its_obligation():
    result = _preservation_case(STATUS_SUPPORTED)
    found = result_for(result, "O-P1")

    assert found.obligation_status == OBLIGATION_SATISFIED
    assert found.obligation_kind == OBLIGATION_KIND_PRESERVATION
    assert found.preservation_obligation_kind == OBLIGATION_BEHAVIOR_PRESERVATION
    assert found.semantic_basis == BASIS_ANALYZER_ASSESSED


def test_k_a_contradicted_preservation_proposition_violates_its_obligation():
    result = _preservation_case(STATUS_CONTRADICTED)
    found = result_for(result, "O-P1")

    assert found.obligation_status == OBLIGATION_VIOLATED
    assert result.violated_obligations == ("O-P1",)


# ── L–N: satisfaction polarity ────────────────────────────────────────────────

def test_l_support_means_satisfied_maps_forward():
    _, supported = single_goal_case(
        claim_status=STATUS_SUPPORTED, polarity=POLARITY_SUPPORT_MEANS_SATISFIED
    )
    _, contradicted = single_goal_case(
        claim_status=STATUS_CONTRADICTED, polarity=POLARITY_SUPPORT_MEANS_SATISFIED
    )

    assert result_for(supported, "G1").obligation_status == OBLIGATION_SATISFIED
    assert result_for(contradicted, "G1").obligation_status == OBLIGATION_VIOLATED


def test_m_contradiction_means_satisfied_maps_in_reverse():
    _, supported = single_goal_case(
        claim_status=STATUS_SUPPORTED,
        polarity=POLARITY_CONTRADICTION_MEANS_SATISFIED,
    )
    _, contradicted = single_goal_case(
        claim_status=STATUS_CONTRADICTED,
        polarity=POLARITY_CONTRADICTION_MEANS_SATISFIED,
    )

    assert result_for(supported, "G1").obligation_status == OBLIGATION_VIOLATED
    assert result_for(contradicted, "G1").obligation_status == OBLIGATION_SATISFIED


def test_n_a_binding_without_polarity_is_invalid_rather_than_guessed():
    _, missing_polarity = single_goal_case(polarity=None)
    found = result_for(missing_polarity, "G1")

    assert found.obligation_status == OBLIGATION_BINDING_INVALID
    assert OBLIGATION_REASON_POLARITY_ABSENT in found.reasons
    assert found.satisfaction_polarity is None

    _, missing_provenance = single_goal_case(provenance=None)
    other = result_for(missing_provenance, "G1")
    assert other.obligation_status == OBLIGATION_BINDING_INVALID
    assert OBLIGATION_REASON_POLARITY_PROVENANCE_ABSENT in other.reasons


def test_ab_one_claim_read_under_two_orientations_gives_two_readings():
    """Proof that CHECK.2 never assumes claim direction is obligation direction."""
    reconciliation = check1()
    requirement_ledger = ledger(
        reconciliation,
        goal_requirement("R-A", TMP_TEXT),
        goal_requirement("R-B", EMBED_TEXT),
    )
    shared = claim(
        proposition_id="P-shared",
        text="Final implementation changes the embedding behaviour.",
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (
            goal_obligation("O-A", "R-A", TMP_TEXT),
            goal_obligation("O-B", "R-B", EMBED_TEXT),
        ),
        (
            binding("O-A", shared, polarity=POLARITY_SUPPORT_MEANS_SATISFIED),
            binding(
                "O-B", shared, polarity=POLARITY_CONTRADICTION_MEANS_SATISFIED
            ),
        ),
    )
    result = review(reconciliation, requirement_ledger, spec, (shared,))

    assert result_for(result, "O-A").obligation_status == OBLIGATION_SATISFIED
    assert result_for(result, "O-B").obligation_status == OBLIGATION_VIOLATED
    assert result_for(result, "O-A").claim_status == STATUS_SUPPORTED
    assert result_for(result, "O-B").claim_status == STATUS_SUPPORTED


# ── O–S: unresolved claim states are never laundered ──────────────────────────

@pytest.mark.parametrize(
    "claim_status, obligation_status",
    [
        (STATUS_CONFLICTING, OBLIGATION_CONFLICTING),
        (STATUS_INSUFFICIENT, OBLIGATION_INSUFFICIENT),
        (STATUS_COVERAGE_INCOMPLETE, OBLIGATION_COVERAGE_INCOMPLETE),
        (
            STATUS_CURRENT_STATE_UNESTABLISHED,
            OBLIGATION_CURRENT_STATE_UNESTABLISHED,
        ),
        (
            STATUS_CURRENT_STATE_INCONSISTENT,
            OBLIGATION_CURRENT_STATE_INCONSISTENT,
        ),
    ],
)
def test_o_through_s_unresolved_claim_states_survive(
    claim_status, obligation_status
):
    _, result = single_goal_case(claim_status=claim_status)
    found = result_for(result, "G1")

    assert found.obligation_status == obligation_status
    assert found.claim_status == claim_status
    assert result.satisfied_obligations == ()
    assert result.violated_obligations == ()
    assert result.status == STATUS_ASSESSED_WITH_GAPS


@pytest.mark.parametrize(
    "claim_status",
    [
        STATUS_CONFLICTING,
        STATUS_INSUFFICIENT,
        STATUS_COVERAGE_INCOMPLETE,
        STATUS_CURRENT_STATE_UNESTABLISHED,
        STATUS_CURRENT_STATE_INCONSISTENT,
    ],
)
def test_reversing_the_polarity_cannot_resolve_an_unresolved_claim(claim_status):
    _, forward = single_goal_case(
        claim_status=claim_status, polarity=POLARITY_SUPPORT_MEANS_SATISFIED
    )
    _, reversed_case = single_goal_case(
        claim_status=claim_status,
        polarity=POLARITY_CONTRADICTION_MEANS_SATISFIED,
    )

    assert (
        result_for(forward, "G1").obligation_status
        == result_for(reversed_case, "G1").obligation_status
    )


def test_o_conflicting_evidence_is_not_adjudicated_here():
    _, result = single_goal_case(claim_status=STATUS_CONFLICTING)

    assert "conflict_adjudication_unavailable" in result.unresolved_requirements
    assert CHECK2_NO_CONFLICT_ADJUDICATED in result.reasons
    payload = json.loads(render_goal_fidelity_assessment_json(result))
    assert payload["guardrails"]["conflict_resolved"] is False


def test_a_claim_that_refused_its_own_input_invalidates_the_binding():
    _, result = single_goal_case(claim_status=CLAIM_INCONSISTENT_INPUT)
    found = result_for(result, "G1")

    assert found.obligation_status == OBLIGATION_BINDING_INVALID
    assert OBLIGATION_REASON_CLAIM_REFUSED in found.reasons


# ── T / AA: a missing claim stays missing ─────────────────────────────────────

def test_t_a_required_obligation_with_no_binding_is_missing_not_dropped():
    _, result = single_goal_case(bind_claim=False, supply_claim=False)
    found = result_for(result, "G1")

    assert found.obligation_status == OBLIGATION_MISSING_CLAIM
    assert OBLIGATION_REASON_NO_BINDING in found.reasons
    assert result.unresolved_obligations == ("G1",)
    assert "semantic_obligation_evidence_required" in result.unresolved_requirements


def test_t_a_bound_but_unsupplied_claim_is_missing_too():
    _, result = single_goal_case(bind_claim=True, supply_claim=False)
    found = result_for(result, "G1")

    assert found.obligation_status == OBLIGATION_MISSING_CLAIM
    assert OBLIGATION_REASON_CLAIM_ABSENT in found.reasons


def test_aa_a_passing_validation_receipt_is_not_semantic_evidence():
    """CHECK.1 says ``test_tmp_ignore`` passed and binds the final state.

    That establishes the execution of a validation, not the meaning of a goal.
    """
    reconciliation = check1()
    assert reconciliation.final_state_binding.validation_coverage_complete is True
    assert reconciliation.final_state_binding.validated_state_current is True

    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (),
    )
    result = review(reconciliation, requirement_ledger, spec)
    found = result_for(result, "G1")

    assert found.obligation_status == OBLIGATION_MISSING_CLAIM
    assert found.obligation_status != OBLIGATION_SATISFIED
    assert result.satisfied_obligations == ()
    assert result.status == STATUS_ASSESSED_WITH_GAPS


# ── U / V: no obligation loss, no obligation widening ─────────────────────────

def _five_obligation_case(
    *, drop: str | None = None, widen: bool = False
):
    preservation = (
        PreservationObligation(
            obligation_id="P1",
            kind=OBLIGATION_BEHAVIOR_PRESERVATION,
            text_sha256=digest(EMBED_TEXT),
        ),
        PreservationObligation(
            obligation_id="P2",
            kind=OBLIGATION_INTERFACE_PRESERVATION,
            text_sha256=digest("keep the public indexer interface"),
        ),
    )
    reconciliation = check1(variant="reconciled", preservation=preservation)
    requirement_ledger = ledger(
        reconciliation,
        goal_requirement("R-G1", TMP_TEXT, ordinal=1),
        goal_requirement("R-G2", "index markdown files", ordinal=2),
        goal_requirement(
            "R-G3", "record an index summary", kind=OBLIGATION_KIND_CONSTRAINT
        ),
    )
    obligations = [
        goal_obligation("G1", "R-G1", TMP_TEXT),
        goal_obligation("G2", "R-G2", "index markdown files"),
        goal_obligation(
            "G3",
            "R-G3",
            "record an index summary",
            kind=OBLIGATION_KIND_CONSTRAINT,
        ),
        preservation_obligation("O-P1", "P1", EMBED_TEXT),
        preservation_obligation(
            "O-P2",
            "P2",
            "keep the public indexer interface",
            kind=OBLIGATION_INTERFACE_PRESERVATION,
        ),
    ]
    if drop is not None:
        obligations = [item for item in obligations if item.obligation_id != drop]
    if widen:
        obligations.append(
            goal_obligation("G-PERF", "R-PERF", "improve indexing performance")
        )
    spec = specification(
        reconciliation, requirement_ledger, tuple(obligations), ()
    )
    return review(reconciliation, requirement_ledger, spec)


def test_u_three_goals_and_two_preservation_constraints_give_five_results():
    result = _five_obligation_case()

    assert len(result.obligation_results) == 5
    assert {item.obligation_id for item in result.obligation_results} == {
        "G1",
        "G2",
        "G3",
        "O-P1",
        "O-P2",
    }
    for item in result.obligation_results:
        assert item.obligation_status == OBLIGATION_MISSING_CLAIM


def test_u_dropping_a_preservation_obligation_is_refused():
    result = _five_obligation_case(drop="O-P1")

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_PRESERVATION_OBLIGATION_DROPPED in result.inconsistencies
    assert result.obligation_results == ()


def test_u_dropping_a_goal_obligation_is_refused():
    result = _five_obligation_case(drop="G2")

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_GOAL_OBLIGATION_DROPPED in result.inconsistencies


def test_v_an_obligation_the_task_never_requested_is_structural_widening():
    result = _five_obligation_case(widen=True)

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_OBLIGATION_WIDENED in result.inconsistencies


def test_v_a_preservation_obligation_check_1_never_carried_is_widening():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation)
    spec = specification(
        reconciliation,
        requirement_ledger,
        (preservation_obligation("O-P1", "P1", EMBED_TEXT),),
        (),
    )
    result = review(reconciliation, requirement_ledger, spec)

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_OBLIGATION_WIDENED in result.inconsistencies


def test_an_obligation_whose_text_differs_from_its_source_is_refused():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", "quietly exclude everything"),),
        (),
    )
    result = review(reconciliation, requirement_ledger, spec)

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_OBLIGATION_SOURCE_TEXT in result.inconsistencies


def test_an_obligation_whose_kind_differs_from_its_source_is_refused():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    spec = specification(
        reconciliation,
        requirement_ledger,
        (
            goal_obligation(
                "G1", "R-G1", TMP_TEXT, kind=OBLIGATION_KIND_CONSTRAINT
            ),
        ),
        (),
    )
    result = review(reconciliation, requirement_ledger, spec)

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_OBLIGATION_SOURCE_KIND in result.inconsistencies


def test_two_obligations_cannot_share_one_explicit_requirement():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    spec = specification(
        reconciliation,
        requirement_ledger,
        (
            goal_obligation("G1", "R-G1", TMP_TEXT),
            goal_obligation("G1-again", "R-G1", TMP_TEXT),
        ),
        (),
    )
    result = review(reconciliation, requirement_ledger, spec)

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_OBLIGATION_WIDENED in result.inconsistencies


def test_the_ledger_cannot_carry_a_preservation_requirement():
    with pytest.raises(ValueError):
        ExplicitRequirementSource(
            requirement_id="R-P1",
            requirement_kind=OBLIGATION_KIND_PRESERVATION,
            requirement_text_sha256=digest(EMBED_TEXT),
            provenance=REQUIREMENT_PROVENANCE_TASK_CONTRACT,
        )


def test_an_optional_requirement_may_be_omitted_without_loss():
    reconciliation = check1()
    requirement_ledger = ledger(
        reconciliation,
        goal_requirement("R-G1", TMP_TEXT),
        goal_requirement("R-G2", "index markdown files", required=False),
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (),
    )
    result = review(reconciliation, requirement_ledger, spec)

    assert result.status != STATUS_INCONSISTENT_INPUT
    assert len(result.obligation_results) == 1


def test_an_optional_obligation_gap_is_not_a_required_gap():
    reconciliation = check1()
    requirement_ledger = ledger(
        reconciliation,
        goal_requirement("R-G1", TMP_TEXT),
        goal_requirement("R-G2", "index markdown files", required=False),
    )
    goal_claim = claim(
        proposition_id="P-tmp",
        text="Final implementation excludes .tmp files from repository indexing.",
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (
            goal_obligation("G1", "R-G1", TMP_TEXT),
            goal_obligation(
                "G2", "R-G2", "index markdown files", required=False
            ),
        ),
        (
            binding(
                "G1",
                goal_claim,
                state_binding=state_binding_for(reconciliation),
            ),
        ),
    )
    result = review(reconciliation, requirement_ledger, spec, (goal_claim,))

    assert result.status == STATUS_ASSESSED
    assert "optional_obligation_evidence_absent" in result.unresolved_requirements
    assert OBLIGATION_REASON_OPTIONAL in result_for(result, "G2").reasons


# ── W / X: independent visibility, no majority ────────────────────────────────

def _mixed_case(preservation_status: str):
    preservation = (
        PreservationObligation(
            obligation_id="P1",
            kind=OBLIGATION_BEHAVIOR_PRESERVATION,
            text_sha256=digest(EMBED_TEXT),
        ),
    )
    reconciliation = check1(variant="reconciled", preservation=preservation)
    requirement_ledger = ledger(
        reconciliation,
        goal_requirement("R-G1", TMP_TEXT),
        goal_requirement("R-G2", "index markdown files"),
    )
    first = claim(
        proposition_id="P-tmp",
        text="Final implementation excludes .tmp files from repository indexing.",
    )
    second = claim(
        proposition_id="P-md",
        text="Final implementation indexes markdown files.",
        evidence_set="set-2",
    )
    preserved = claim(
        proposition_id="P-embed",
        text="Final implementation preserves the previous embedding behaviour.",
        status=preservation_status,
        evidence_set="set-3",
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (
            goal_obligation("G1", "R-G1", TMP_TEXT),
            goal_obligation("G2", "R-G2", "index markdown files"),
            preservation_obligation("O-P1", "P1", EMBED_TEXT),
        ),
        (
            binding("G1", first),
            binding("G2", second),
            binding(
                "O-P1",
                preserved,
                provenance=POLARITY_PROVENANCE_PRESERVED_REQUIREMENT,
            ),
        ),
    )
    return review(
        reconciliation, requirement_ledger, spec, (first, second, preserved)
    )


def test_w_two_satisfied_goals_do_not_resolve_one_conflicting_constraint():
    result = _mixed_case(STATUS_CONFLICTING)

    assert result.satisfied_obligations == ("G1", "G2")
    assert result.unresolved_obligations == ("O-P1",)
    assert result_for(result, "O-P1").obligation_status == OBLIGATION_CONFLICTING
    assert result.status == STATUS_ASSESSED_WITH_GAPS
    assert result.final_success_authority is False


def test_x_a_satisfied_goal_cannot_hide_a_violated_preservation_constraint():
    result = _mixed_case(STATUS_CONTRADICTED)

    assert result.satisfied_obligations == ("G1", "G2")
    assert result.violated_obligations == ("O-P1",)
    payload = json.loads(render_goal_fidelity_assessment_json(result))
    assert payload["violated_obligations"] == ["O-P1"]
    assert "violated_obligation_review_required" in result.unresolved_requirements


def test_x_no_serialized_field_counts_or_scores_the_obligations():
    """The honest denials live in the guardrail block; nothing else counts."""
    result = _mixed_case(STATUS_CONTRADICTED)
    payload = json.loads(render_goal_fidelity_assessment_json(result))
    guardrails = payload.pop("guardrails")
    payload.pop("authority")
    body = json.dumps(payload)

    for banned in (
        "satisfied_count",
        "violated_count",
        "percent",
        "score",
        "confidence",
        "probability",
        "majority",
        "mostly",
        "weight",
        "outweigh",
        "tally",
    ):
        assert banned not in body, banned
    assert guardrails["majority_computed"] is False
    assert guardrails["confidence_computed"] is False


# ── Y / Z: diagnostic-only behaviour ──────────────────────────────────────────

def test_y_a_suspicious_run_shows_semantic_states_without_certifying_them():
    _, result = single_goal_case(variant="suspicious", claim_status=STATUS_SUPPORTED)
    found = result_for(result, "G1")

    assert result.review_mode == REVIEW_DIAGNOSTIC_ONLY
    assert result.status == STATUS_DIAGNOSTIC_ONLY
    assert found.obligation_status == OBLIGATION_SATISFIED
    assert OBLIGATION_REASON_DIAGNOSTIC_ONLY in found.reasons
    assert result.semantic_goal_review_authority is False
    assert "execution_reconciliation_unresolved" in result.unresolved_requirements
    payload = json.loads(render_goal_fidelity_assessment_json(result))
    assert payload["review_mode_meaning"] == REVIEW_MODE_MEANING[
        REVIEW_DIAGNOSTIC_ONLY
    ]


def test_z_stale_validation_survives_supporting_semantic_evidence():
    reconciliation, result = single_goal_case(
        variant="incomplete", claim_status=STATUS_SUPPORTED
    )

    assert "validation_stale_for_final_state" in reconciliation.inconsistencies
    assert result.review_mode == REVIEW_DIAGNOSTIC_ONLY
    assert (
        "validation_stale_for_final_state"
        in result.execution_reconciliation.check_1_inconsistencies
    )
    assert result.execution_reconciliation.validated_state_current is False
    assert result_for(result, "G1").obligation_status == OBLIGATION_SATISFIED
    assert result.status == STATUS_DIAGNOSTIC_ONLY


# ── AC / AD: semantic provenance ──────────────────────────────────────────────

def test_ac_a_satisfied_obligation_still_rests_on_analyzer_assessment():
    _, result = single_goal_case()
    found = result_for(result, "G1")

    assert found.semantic_basis == BASIS_ANALYZER_ASSESSED
    assert result.semantic_basis == BASIS_ANALYZER_ASSESSED
    payload = render_goal_fidelity_assessment_json(result)
    for banned in (
        "deterministic_semantic_truth",
        "semantically_verified",
        "deterministically_verified",
        "goal_satisfied",
    ):
        assert banned not in payload, banned


def test_ad_many_satisfied_obligations_do_not_upgrade_the_semantic_basis():
    reconciliation = check1()
    requirements = tuple(
        goal_requirement(f"R-{index}", f"explicit requirement {index}")
        for index in range(10)
    )
    requirement_ledger = ledger(reconciliation, *requirements)
    claims = tuple(
        claim(
            proposition_id=f"P-{index}",
            text=f"Final implementation satisfies explicit requirement {index}.",
            evidence_set=f"set-{index}",
        )
        for index in range(10)
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        tuple(
            goal_obligation(
                f"G-{index}", f"R-{index}", f"explicit requirement {index}"
            )
            for index in range(10)
        ),
        tuple(binding(f"G-{index}", claims[index]) for index in range(10)),
    )
    result = review(reconciliation, requirement_ledger, spec, claims)

    assert len(result.satisfied_obligations) == 10
    assert result.semantic_basis == BASIS_ANALYZER_ASSESSED
    for item in result.obligation_results:
        assert item.semantic_basis == BASIS_ANALYZER_ASSESSED
        assert item.goal_proven is False
    assert result.goal_proven is False
    assert result.final_success_authority is False


def test_the_stated_meaning_of_satisfied_denies_deterministic_proof():
    assert "does not mean" in SATISFIED_MEANING
    assert "analyzer-assessed" in SATISFIED_MEANING
    _, result = single_goal_case()
    payload = json.loads(render_goal_fidelity_assessment_json(result))
    assert payload["satisfied_meaning"] == SATISFIED_MEANING


# ── AE / AF: post-run final-state binding ─────────────────────────────────────

def test_af_an_unbound_claim_is_a_recorded_gap_not_a_proven_final_state():
    _, result = single_goal_case(bind_final_state=False)
    found = result_for(result, "G1")

    assert found.post_run_state_binding == STATE_BINDING_UNAVAILABLE
    assert OBLIGATION_REASON_FINAL_STATE_UNBOUND in found.reasons
    assert (
        "post_run_semantic_state_binding_unavailable"
        in result.unresolved_requirements
    )
    assert result.status == STATUS_ASSESSED_WITH_GAPS


def test_a_final_state_bound_claim_reaches_assessed():
    _, result = single_goal_case(bind_final_state=True)
    found = result_for(result, "G1")

    assert found.post_run_state_binding == STATE_BINDING_BOUND
    assert OBLIGATION_REASON_FINAL_STATE_BOUND in found.reasons
    assert (
        "post_run_semantic_state_binding_unavailable"
        not in result.unresolved_requirements
    )
    assert result.status == STATUS_ASSESSED


def test_ae_a_binding_naming_the_wrong_final_state_is_refused():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    goal_claim = claim(
        proposition_id="P-tmp",
        text="Final implementation excludes .tmp files from repository indexing.",
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (
            binding(
                "G1",
                goal_claim,
                state_binding=PostRunStateBinding(
                    final_state_fingerprint=digest("a-different-final-state"),
                    state_receipt_sha256=digest("final-state-receipt"),
                    provenance=STATE_BINDING_PROVENANCE_RECEIPT,
                ),
            ),
        ),
    )
    result = review(reconciliation, requirement_ledger, spec, (goal_claim,))

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_POST_RUN_STATE_BINDING in result.inconsistencies


# ── Composite and reuse rules ─────────────────────────────────────────────────

def test_two_bindings_for_one_obligation_are_unsupported_not_aggregated():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    first = claim(
        proposition_id="P-a",
        text="The patch adds a .tmp exclusion rule.",
    )
    second = claim(
        proposition_id="P-b",
        text="The final indexing behaviour excludes .tmp files.",
        evidence_set="set-2",
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (binding("G1", first), binding("G1", second)),
    )
    result = review(reconciliation, requirement_ledger, spec, (first, second))
    found = result_for(result, "G1")

    assert found.obligation_status == OBLIGATION_COMPOSITE_UNSUPPORTED
    assert OBLIGATION_REASON_MULTIPLE_BINDINGS in found.reasons
    assert (
        "composite_obligation_projection_required" in result.unresolved_requirements
    )


def test_an_unbound_claim_assessment_is_recorded_and_never_reused():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    lying_around = claim(
        proposition_id="P-loose",
        text="The final indexing behaviour excludes .tmp files.",
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (),
    )
    result = review(reconciliation, requirement_ledger, spec, (lying_around,))

    assert result_for(result, "G1").obligation_status == OBLIGATION_MISSING_CLAIM
    assert result.unbound_claim_assessments == ("P-loose",)
    assert CHECK2_UNBOUND_CLAIM_ASSESSMENTS_IGNORED in result.reasons


def test_a_binding_for_an_unknown_obligation_is_refused():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    goal_claim = claim(
        proposition_id="P-tmp",
        text="Final implementation excludes .tmp files from repository indexing.",
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (binding("G-nope", goal_claim),),
    )
    result = review(reconciliation, requirement_ledger, spec, (goal_claim,))

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_BINDING_UNKNOWN_OBLIGATION in result.inconsistencies


def test_diff_intent_and_final_state_propositions_are_not_collapsed():
    """Two obligations, two propositions; neither is inferred from the other."""
    reconciliation = check1()
    requirement_ledger = ledger(
        reconciliation,
        goal_requirement("R-patch", "add a .tmp exclusion rule"),
        goal_requirement("R-final", TMP_TEXT),
    )
    patch_claim = claim(
        proposition_id="P-patch",
        text="The patch adds a .tmp exclusion rule.",
    )
    final_claim = claim(
        proposition_id="P-final",
        text="The final indexing behaviour excludes .tmp files.",
        status=STATUS_CURRENT_STATE_UNESTABLISHED,
        scope="runtime_behaviour",
        evidence_set="set-2",
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (
            goal_obligation("G-patch", "R-patch", "add a .tmp exclusion rule"),
            goal_obligation("G-final", "R-final", TMP_TEXT),
        ),
        (binding("G-patch", patch_claim), binding("G-final", final_claim)),
    )
    result = review(
        reconciliation, requirement_ledger, spec, (patch_claim, final_claim)
    )

    assert result_for(result, "G-patch").obligation_status == OBLIGATION_SATISFIED
    assert (
        result_for(result, "G-final").obligation_status
        == OBLIGATION_CURRENT_STATE_UNESTABLISHED
    )
    assert result_for(result, "G-final").proposition_scope == "runtime_behaviour"


# ── Fingerprint and tamper binding ────────────────────────────────────────────

def test_a_specification_prepared_for_another_task_is_refused():
    reconciliation = check1()
    other = check1(task_label="TASK-CONTRACT-B")
    requirement_ledger = ledger(other, goal_requirement("R-G1", TMP_TEXT))
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (),
        task_fingerprint_override=other.task_contract_fingerprint,
    )
    result = review(
        reconciliation,
        requirement_ledger,
        spec,
        (),
        expected_task_contract_fingerprint=reconciliation.task_contract_fingerprint,
    )

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_SPECIFICATION_TASK_BINDING in result.inconsistencies
    assert INCONSISTENT_LEDGER_TASK_BINDING in result.inconsistencies


def test_a_specification_bound_to_another_execution_is_refused():
    reconciliation = check1()
    other = check1(variant="suspicious")
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (),
        reconciliation_fingerprint_override=other.reconciliation_fingerprint,
    )
    result = review(reconciliation, requirement_ledger, spec)

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_SPECIFICATION_RUN_BINDING in result.inconsistencies


def test_an_edited_expected_reconciliation_fingerprint_is_refused():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (),
    )
    result = review(
        reconciliation,
        requirement_ledger,
        spec,
        (),
        expected_reconciliation_fingerprint=digest("not-this-reconciliation"),
    )

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_RECONCILIATION_FINGERPRINT in result.inconsistencies


def test_an_edited_expected_specification_fingerprint_is_refused():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (),
    )
    result = review(
        reconciliation,
        requirement_ledger,
        spec,
        (),
        expected_specification_fingerprint=digest("some-other-specification"),
    )

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_SPECIFICATION_FINGERPRINT in result.inconsistencies


def test_a_ledger_the_specification_did_not_name_is_refused():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (),
        ledger_fingerprint_override=digest("another-ledger"),
    )
    result = review(reconciliation, requirement_ledger, spec)

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_LEDGER_FINGERPRINT in result.inconsistencies


def test_an_edited_claim_assessment_breaks_its_binding():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    supported = claim(
        proposition_id="P-tmp",
        text="Final implementation excludes .tmp files from repository indexing.",
    )
    contradicted = claim(
        proposition_id="P-tmp",
        text="Final implementation excludes .tmp files from repository indexing.",
        status=STATUS_CONTRADICTED,
    )
    # The binding names the supported record; the contradicted one is supplied.
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (
            binding(
                "G1",
                supported,
                fingerprint_override=supported.assessment_fingerprint,
            ),
        ),
    )
    result = review(reconciliation, requirement_ledger, spec, (contradicted,))

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_CLAIM_FINGERPRINT in result.inconsistencies


def test_a_binding_whose_proposition_digest_drifted_is_refused():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    goal_claim = claim(
        proposition_id="P-tmp",
        text="Final implementation excludes .tmp files from repository indexing.",
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (
            binding(
                "G1",
                goal_claim,
                proposition_digest_override=digest("a slightly reworded claim"),
            ),
        ),
    )
    result = review(reconciliation, requirement_ledger, spec, (goal_claim,))

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_CLAIM_PROPOSITION_BINDING in result.inconsistencies


def test_a_binding_naming_another_evidence_set_is_refused():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    goal_claim = claim(
        proposition_id="P-tmp",
        text="Final implementation excludes .tmp files from repository indexing.",
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (
            binding(
                "G1",
                goal_claim,
                evidence_set_fingerprint=digest("some-other-evidence-set"),
            ),
        ),
    )
    result = review(reconciliation, requirement_ledger, spec, (goal_claim,))

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_CLAIM_EVIDENCE_SET_BINDING in result.inconsistencies


def test_two_claim_assessments_for_one_proposition_are_refused():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    first = claim(proposition_id="P-tmp", text="First reading.")
    second = claim(
        proposition_id="P-tmp", text="Second reading.", evidence_set="set-2"
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (),
    )
    result = review(reconciliation, requirement_ledger, spec, (first, second))

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_CLAIM_DUPLICATE in result.inconsistencies


def test_the_optional_claim_fingerprint_binding_is_enforced():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-G1", TMP_TEXT))
    goal_claim = claim(
        proposition_id="P-tmp",
        text="Final implementation excludes .tmp files from repository indexing.",
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (goal_obligation("G1", "R-G1", TMP_TEXT),),
        (binding("G1", goal_claim),),
    )
    result = review(
        reconciliation,
        requirement_ledger,
        spec,
        (goal_claim,),
        expected_claim_assessment_fingerprints=(digest("not-this-claim"),),
    )

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_CLAIM_FINGERPRINT in result.inconsistencies


def test_the_result_fingerprint_moves_with_every_semantic_input():
    _, baseline = single_goal_case()
    _, other_polarity = single_goal_case(
        polarity=POLARITY_CONTRADICTION_MEANS_SATISFIED
    )
    _, other_claim = single_goal_case(claim_status=STATUS_CONTRADICTED)
    _, other_mode = single_goal_case(variant="suspicious")

    fingerprints = {
        baseline.assessment_fingerprint,
        other_polarity.assessment_fingerprint,
        other_claim.assessment_fingerprint,
        other_mode.assessment_fingerprint,
    }
    assert len(fingerprints) == 4


def test_the_same_inputs_produce_a_byte_identical_assessment():
    _, first = single_goal_case()
    _, second = single_goal_case()

    assert first.assessment_fingerprint == second.assessment_fingerprint
    assert render_goal_fidelity_assessment_json(first) == (
        render_goal_fidelity_assessment_json(second)
    )


def test_obligation_input_order_does_not_change_the_result():
    reconciliation = check1()
    requirement_ledger = ledger(
        reconciliation,
        goal_requirement("R-G1", TMP_TEXT),
        goal_requirement("R-G2", "index markdown files"),
    )
    first = goal_obligation("G1", "R-G1", TMP_TEXT)
    second = goal_obligation("G2", "R-G2", "index markdown files")
    forward = specification(
        reconciliation, requirement_ledger, (first, second), ()
    )
    backward = specification(
        reconciliation, requirement_ledger, (second, first), ()
    )

    assert review(
        reconciliation, requirement_ledger, forward
    ).assessment_fingerprint == review(
        reconciliation, requirement_ledger, backward
    ).assessment_fingerprint


def test_explicit_obligation_order_is_preserved_when_it_is_stated():
    reconciliation = check1()
    requirement_ledger = ledger(
        reconciliation,
        goal_requirement("R-A", "first stated requirement", ordinal=1),
        goal_requirement("R-B", "second stated requirement", ordinal=2),
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (
            goal_obligation("Z-second", "R-B", "second stated requirement", ordinal=2),
            goal_obligation("A-first", "R-A", "first stated requirement", ordinal=1),
        ),
        (),
    )
    result = review(reconciliation, requirement_ledger, spec)

    assert [item.obligation_id for item in result.obligation_results] == [
        "A-first",
        "Z-second",
    ]


def test_partly_ordered_obligations_are_refused_at_construction():
    reconciliation = check1()
    requirement_ledger = ledger(reconciliation, goal_requirement("R-A", "a"))
    with pytest.raises(ValueError):
        specification(
            reconciliation,
            requirement_ledger,
            (
                goal_obligation("G1", "R-A", "a", ordinal=1),
                goal_obligation("G2", "R-A", "a"),
            ),
            (),
        )


# ── The DeepSeek-style regressions ────────────────────────────────────────────

def _session_persistence_case(variant: str):
    preservation = (
        PreservationObligation(
            obligation_id="P-auth",
            kind=OBLIGATION_BEHAVIOR_PRESERVATION,
            text_sha256=digest("do not weaken authorization checks"),
        ),
    )
    reconciliation = check1(variant=variant, preservation=preservation)
    requirement_ledger = ledger(
        reconciliation, goal_requirement("R-session", "add session persistence")
    )
    persistence = claim(
        proposition_id="P-session",
        text="Final implementation persists sessions across restarts.",
    )
    authorization_claim = claim(
        proposition_id="P-authz",
        text="Final implementation preserves the previous authorization checks.",
        status=STATUS_CONTRADICTED,
        evidence_set="set-2",
    )
    spec = specification(
        reconciliation,
        requirement_ledger,
        (
            goal_obligation("G-session", "R-session", "add session persistence"),
            preservation_obligation(
                "O-auth", "P-auth", "do not weaken authorization checks"
            ),
        ),
        (
            binding("G-session", persistence),
            binding(
                "O-auth",
                authorization_claim,
                provenance=POLARITY_PROVENANCE_PRESERVED_REQUIREMENT,
            ),
        ),
    )
    return review(
        reconciliation,
        requirement_ledger,
        spec,
        (persistence, authorization_claim),
    )


def test_the_deepseek_style_goal_and_preservation_regression():
    result = _session_persistence_case("reconciled")

    assert result.review_mode == REVIEW_ASSESSABLE
    assert (
        result_for(result, "G-session").obligation_status == OBLIGATION_SATISFIED
    )
    assert result_for(result, "O-auth").obligation_status == OBLIGATION_VIOLATED
    assert result.status in {STATUS_ASSESSED, STATUS_ASSESSED_WITH_GAPS}
    assert result.final_success_authority is False
    payload = render_goal_fidelity_assessment_json(result)
    assert "primary goal" not in payload
    assert '"run_success"' not in payload


def test_the_same_semantic_claims_stay_blocked_under_an_authority_violation():
    result = _session_persistence_case("blocked")

    assert result.status == STATUS_BLOCKED
    assert result.satisfied_obligations == ()
    assert result.violated_obligations == ()
    assert (
        "forbidden_path_changed"
        in result.execution_reconciliation.check_1_inconsistencies
    )


# ── Contract shape ────────────────────────────────────────────────────────────

def test_every_assessment_leaves_the_run_verdict_and_human_review_outstanding():
    for variant in ("reconciled", "suspicious", "incomplete", "blocked"):
        _, result = single_goal_case(variant=variant)
        assert "run_verdict_required" in result.unresolved_requirements
        assert "human_review_required" in result.unresolved_requirements
        assert result.check_3_required is True


def test_the_authority_block_denies_every_power_but_the_narrow_one():
    granted = goal_fidelity_authority(semantic_goal_review_authority=True)
    assert granted["semantic_goal_review_authority"] is True
    assert granted["human_approval_required"] is True
    for key, value in granted.items():
        if key in {"semantic_goal_review_authority", "human_approval_required"}:
            continue
        assert value is False, key


def test_the_guardrail_block_denies_every_side_effect():
    guardrails = goal_fidelity_guardrails(
        check_1_gate_evaluated=True,
        semantic_obligations_reconciled=True,
        claim_assessments_consumed=True,
        preservation_obligations_checked=True,
        semantic_provenance_preserved=True,
        post_run_state_binding_checked=True,
    )
    for key in (
        "source_content_read",
        "diff_content_read",
        "repository_traversed",
        "evidence_acquired",
        "evidence_reassessed",
        "validation_executed",
        "model_called",
        "network_called",
        "proposition_invented",
        "obligation_invented",
        "obligation_dropped",
        "polarity_inferred",
        "conflict_resolved",
        "majority_computed",
        "confidence_computed",
        "worker_repaired",
        "patch_modified",
        "merge_performed",
        "final_success_declared",
        "run_verdict_declared",
        "objective_truth_asserted",
    ):
        assert guardrails[key] is False, key


def test_the_vocabularies_hold_no_verdict_value():
    for banned in ("success", "failure", "correct", "incorrect", "merge_ready"):
        assert banned not in GOAL_FIDELITY_STATUSES, banned
        assert banned not in OBLIGATION_STATUSES, banned
    assert len(GOAL_FIDELITY_STATUSES) == 5
    assert len(OBLIGATION_STATUSES) == 11


def test_the_proposition_text_bound_tracks_claim_1():
    assert MAX_PROPOSITION_TEXT_CHARS == MAX_PROPOSITION_CHARS


def test_the_renderer_requires_an_exact_assessment():
    with pytest.raises(TypeError):
        render_goal_fidelity_assessment_json({"status": STATUS_ASSESSED})


def test_the_review_requires_an_exact_request():
    with pytest.raises(TypeError):
        review_goal_fidelity({"reconciliation": None})


def test_the_result_is_reported_with_its_stated_reasons():
    _, result = single_goal_case()

    for reason in (
        CHECK2_CHECK_1_GATE_EVALUATED,
        CHECK2_EXECUTION_SEVERITY_PRESERVED,
        CHECK2_NO_SEMANTIC_REANALYSIS_PERFORMED,
        CHECK2_NO_CONFLICT_ADJUDICATED,
        CHECK2_NO_MAJORITY_COMPUTED,
        CHECK2_NO_RUN_VERDICT_PRODUCED,
    ):
        assert reason in result.reasons
