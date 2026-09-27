"""EVIDENCE.1 closure — semantic assessment provenance.

Everything else in the phase proves that a record is *bound*: to the acquired
bytes, to the supplied proposition, to spans somebody actually read, to roles
the source was acquired for.  None of that establishes that the cited material
entails the claim, and this file exists so that the two can never be read as one
fact.

The failure it forecloses is quiet:

    analyzer proposes "supports"
        -> every deterministic check passes
        -> a record that *looks* like proven semantic truth

A real ``sqlite3.connect("sessions.db")`` line inside a genuine implementation
file is a real line.  It is not, by itself, a proof that session state survives
a process restart.  So the record says which dimensions were settled by
arithmetic and which one was proposed by an analyzer and merely accepted.

Every test runs offline.  No model, no network, no repository read.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from core.acquisition_request import (
    SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
    SOURCE_CLASS_VALIDATION_TEST,
)
from core.content_acquisition import (
    MODE_REPOSITORY_READ,
    AcquiredSourcePayload,
    SourceAcquisitionReceipt,
    SourceBinding,
)
from core.evidence_analyzer import ScriptedEvidenceAnalyzer, StaticEvidenceAnalyzer
from core.evidence_promotion_gate import verify_acquired_source
from core.evidence_requirements import (
    DOMAIN_REPOSITORY,
    DOMAIN_VALIDATION_ARTIFACTS,
    ROLE_IMPLEMENTATION_AUTHORITY,
    ROLE_VALIDATION_EVIDENCE,
    TIER_REQUIRED_PRIMARY,
)
from core.evidence_verification import (
    ANALYSIS_MECHANISM_IMPLEMENTED,
    ANALYSIS_PROPOSITION_TERMS_PRESENT,
    ANALYSIS_ROLE_CONTENT_CONSISTENT,
    CONSTRAINT_CURRENT_STATE_RECEIPT_REQUIRED,
    CONSTRAINT_NEGATIVE_COVERAGE_REQUIRED,
    CONSTRAINT_ROLE_VERIFICATION_REQUIRED,
    COVERAGE_ALL_ELIGIBLE_CANDIDATES_ACQUIRED,
    COVERAGE_ALL_REQUIRED_ROLES_ACQUIRED,
    COVERAGE_SUFFICIENT,
    CURRENT_STATE_ESTABLISHED,
    CURRENT_STATE_NOT_ESTABLISHED,
    CURRENT_STATE_RUNTIME_ENTRYPOINT_CONFIRMED,
    DETERMINISTIC_DIMENSIONS,
    DIMENSION_CITATION_INTEGRITY,
    DIMENSION_MAX_LEVEL,
    DIMENSION_ROLE_ADMISSIBILITY,
    DIMENSION_SEMANTIC_RELATION,
    DIMENSION_SOURCE_BINDING,
    GATE_PROMOTION_BLOCKED_CURRENT_STATE,
    GATE_PROMOTION_BLOCKED_NEGATIVE_COVERAGE,
    LEVEL_ANALYZER_ASSESSED,
    LEVEL_DETERMINISTICALLY_VERIFIED,
    LEVEL_NOT_ESTABLISHED,
    PROMOTION_NOT_PROMOTED,
    PROMOTION_PROMOTED,
    PROPOSITION_NEGATIVE_EXISTENTIAL,
    PROPOSITION_POSITIVE,
    RELATION_CONTRADICTS,
    RELATION_INSUFFICIENT,
    RELATION_SUPPORTS,
    RELATION_UNRELATED,
    ROLE_STATUS_VERIFIED,
    SCOPE_IMPLEMENTATION_STATE,
    SCOPE_RUNTIME_BEHAVIOUR,
    SCOPE_VALIDATION_EXPECTATION,
    SCOPES_REQUIRING_CURRENT_STATE,
    SEMANTIC_ASSESSMENT_ANALYZER_PROPOSAL,
    SEMANTIC_ASSESSMENT_NOT_ASSESSED,
    SPAN_CONTRADICTING,
    SPAN_SUPPORTING,
    STATUS_BINDING_INVALID,
    STATUS_CONTRADICTED,
    STATUS_COVERAGE_REQUIRED,
    STATUS_INSUFFICIENT,
    STATUS_UNRELATED,
    STATUS_VERIFIED,
    VERIFICATION_CONSTRAINTS,
    VERIFICATION_DIMENSIONS,
    VERIFICATION_LEVELS,
    CurrentStateReceipt,
    EvidenceVerificationProposal,
    EvidenceVerificationRequest,
    NegativeClaimCoverage,
    Proposition,
    RoleAssessment,
    VerificationLevels,
    VerifiedEvidence,
    bounded_payload_view,
    render_evidence_verification_result_json,
    render_verification_set_json,
    source_receipt_fingerprint,
    span_from_view,
)


# ── Fixtures: ACQUIRE.3 artefacts, built without running ACQUIRE.3 ─────────────

def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _binding(identifier: str) -> SourceBinding:
    return SourceBinding(
        candidate_identifier=identifier,
        acquisition_mode=MODE_REPOSITORY_READ,
        task_contract_fingerprint=_digest("task-contract"),
        completion_fingerprint=_digest("completion"),
        waiter_decision_fingerprint=_digest("waiter-decision"),
        evidence_requirement_fingerprint=_digest("evidence-requirement"),
        acquisition_request_fingerprint=_digest("acquisition-request"),
        candidate_receipt_fingerprint=_digest("candidate-pool"),
        selection_fingerprint=_digest("selection"),
        authorization_fingerprint=_digest("authorization"),
        inventory_fingerprint=_digest("inventory"),
        repository_identity="repo:deepseek-harness",
    )


def _acquire(
    identifier: str,
    content: bytes,
    roles: tuple[str, ...],
    classes: tuple[str, ...],
    *,
    domain: str = DOMAIN_REPOSITORY,
) -> tuple[AcquiredSourcePayload, SourceAcquisitionReceipt]:
    bound = _binding(identifier)
    digest = hashlib.sha256(content).hexdigest()
    payload = AcquiredSourcePayload(
        candidate_identifier=identifier,
        content=content,
        content_sha256=digest,
        bytes_acquired=len(content),
        source_binding=bound,
    )
    receipt = SourceAcquisitionReceipt(
        candidate_identifier=identifier,
        domain=domain,
        tier=TIER_REQUIRED_PRIMARY,
        expected_roles=roles,
        eligible_source_classes=classes,
        target_artifact=False,
        content_sha256=digest,
        bytes_acquired=len(content),
        source_binding=bound,
    )
    return payload, receipt


def _proposition(
    text: str,
    *,
    scope: str = SCOPE_IMPLEMENTATION_STATE,
    proposition_type: str = PROPOSITION_POSITIVE,
) -> Proposition:
    return Proposition(
        proposition_id="P-1",
        text=text,
        proposition_type=proposition_type,
        scope=scope,
    )


def _request(
    receipt: SourceAcquisitionReceipt,
    proposition: Proposition,
    *,
    coverage: NegativeClaimCoverage | None = None,
    current_state: CurrentStateReceipt | None = None,
) -> EvidenceVerificationRequest:
    declared = {CONSTRAINT_ROLE_VERIFICATION_REQUIRED}
    if proposition.proposition_type == PROPOSITION_NEGATIVE_EXISTENTIAL:
        declared.add(CONSTRAINT_NEGATIVE_COVERAGE_REQUIRED)
    if proposition.scope in SCOPES_REQUIRING_CURRENT_STATE:
        declared.add(CONSTRAINT_CURRENT_STATE_RECEIPT_REQUIRED)
    return EvidenceVerificationRequest(
        proposition=proposition,
        requested_roles=receipt.expected_roles,
        acquisition_receipt_fingerprint=source_receipt_fingerprint(receipt),
        source_content_sha256=receipt.content_sha256,
        source_binding=receipt.source_binding,
        verification_constraints=tuple(
            item for item in VERIFICATION_CONSTRAINTS if item in declared
        ),
        coverage=coverage,
        current_state=current_state,
    )


def _coverage(
    proposition: Proposition,
    receipt: SourceAcquisitionReceipt,
) -> NegativeClaimCoverage:
    return NegativeClaimCoverage(
        proposition_id=proposition.proposition_id,
        proposition_sha256=proposition.proposition_sha256,
        required_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
        acquisition_request_fingerprint=(
            receipt.source_binding.acquisition_request_fingerprint
        ),
        candidate_pool_fingerprint=receipt.source_binding.candidate_receipt_fingerprint,
        acquired_source_receipt_fingerprints=(source_receipt_fingerprint(receipt),),
        coverage_status=COVERAGE_SUFFICIENT,
        source_class_coverage=(SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
        reasons=(
            COVERAGE_ALL_REQUIRED_ROLES_ACQUIRED,
            COVERAGE_ALL_ELIGIBLE_CANDIDATES_ACQUIRED,
        ),
    )


def _current_state(
    proposition: Proposition,
    receipt: SourceAcquisitionReceipt,
    *,
    established: bool = True,
) -> CurrentStateReceipt:
    return CurrentStateReceipt(
        proposition_id=proposition.proposition_id,
        proposition_sha256=proposition.proposition_sha256,
        candidate_identifier=receipt.candidate_identifier,
        source_content_sha256=receipt.content_sha256,
        acquisition_receipt_fingerprint=source_receipt_fingerprint(receipt),
        current_state_status=(
            CURRENT_STATE_ESTABLISHED if established else CURRENT_STATE_NOT_ESTABLISHED
        ),
        basis=(CURRENT_STATE_RUNTIME_ENTRYPOINT_CONFIRMED,) if established else (),
    )


# ── Fixtures: source content ──────────────────────────────────────────────────

SQLITE_IMPLEMENTATION = b'''"""Session storage backed by SQLite."""

import sqlite3


class SessionStore:
    def __init__(self, path):
        self._connection = sqlite3.connect(path)

    def save_session(self, session_id, state):
        self._connection.execute(
            "INSERT OR REPLACE INTO sessions (id, state) VALUES (?, ?)",
            (session_id, state),
        )
        self._connection.commit()
'''

MEMORY_IMPLEMENTATION = b'''"""Session storage held for the lifetime of the process."""


class SessionStore:
    def __init__(self):
        self._sessions = {}

    def save_session(self, session_id, state):
        self._sessions[session_id] = state
'''

VALIDATION_TEST = b'''def test_session_state_survives_a_restart(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    store.save_session("abc", b"state")
    assert SessionStore(tmp_path / "sessions.db").load_session("abc") == b"state"
'''

STYLESHEET = b'''.toolbar-panel {
    display: flex;
    gap: 8px;
}
'''


def _analyzer(**overrides: object) -> StaticEvidenceAnalyzer:
    values: dict[str, object] = {
        "role_markers": {
            ROLE_IMPLEMENTATION_AUTHORITY: (b"def save_session",),
            ROLE_VALIDATION_EVIDENCE: (b"def test_",),
        },
        "supporting_markers": (b"sqlite3.connect",),
        "relevance_markers": (b"save_session", b"session"),
        "context_bytes": 40,
    }
    values.update(overrides)
    return StaticEvidenceAnalyzer(**values)  # type: ignore[arg-type]


def _sqlite_case() -> tuple[
    AcquiredSourcePayload,
    SourceAcquisitionReceipt,
    Proposition,
    EvidenceVerificationRequest,
]:
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition("SessionStore writes session state to SQLite.")
    return payload, receipt, claim, _request(receipt, claim)


_FORBIDDEN_OVERCLAIMS = (
    "claim_proven",
    "semantic_truth_verified",
    "proposition_verified_true",
    "proposition_true",
    "deterministic_semantic_verification",
    "ground_truth",
)


# =============================================================================
# 1. The vocabulary itself refuses the overclaim
# =============================================================================

def test_the_four_dimensions_are_named_and_the_semantic_one_has_a_lower_ceiling():
    assert VERIFICATION_DIMENSIONS == (
        DIMENSION_SOURCE_BINDING,
        DIMENSION_CITATION_INTEGRITY,
        DIMENSION_ROLE_ADMISSIBILITY,
        DIMENSION_SEMANTIC_RELATION,
    )
    assert DIMENSION_MAX_LEVEL[DIMENSION_SEMANTIC_RELATION] == LEVEL_ANALYZER_ASSESSED
    for dimension in DETERMINISTIC_DIMENSIONS:
        assert DIMENSION_MAX_LEVEL[dimension] == LEVEL_DETERMINISTICALLY_VERIFIED
    assert DIMENSION_SEMANTIC_RELATION not in DETERMINISTIC_DIMENSIONS


def test_a_deterministically_verified_semantic_relation_does_not_construct():
    with pytest.raises(ValueError, match="never\\s+deterministically verified"):
        VerificationLevels(semantic_relation=LEVEL_DETERMINISTICALLY_VERIFIED)


def test_a_structural_dimension_may_not_be_merely_analyzer_assessed():
    """The ceiling table runs both ways: an analyzer cannot vouch for a digest."""
    for dimension in DETERMINISTIC_DIMENSIONS:
        with pytest.raises(ValueError, match="deterministically or not at all"):
            VerificationLevels(**{dimension: LEVEL_ANALYZER_ASSESSED})


def test_an_unknown_level_is_refused():
    with pytest.raises(ValueError, match="unsupported verification level"):
        VerificationLevels(semantic_relation="probably_true")
    assert set(VERIFICATION_LEVELS) == {
        LEVEL_DETERMINISTICALLY_VERIFIED,
        LEVEL_ANALYZER_ASSESSED,
        LEVEL_NOT_ESTABLISHED,
    }


# =============================================================================
# 2. A valid supporting record separates the two kinds of claim
# =============================================================================

def test_a_supporting_record_is_structurally_verified_and_semantically_assessed():
    payload, receipt, claim, request = _sqlite_case()

    result = verify_acquired_source(request, payload, receipt, _analyzer())

    assert result.status == STATUS_VERIFIED
    assert result.relation == RELATION_SUPPORTS
    assert result.promotion_status == PROMOTION_PROMOTED

    levels = result.verification_levels
    assert levels.source_binding == LEVEL_DETERMINISTICALLY_VERIFIED
    assert levels.citation_integrity == LEVEL_DETERMINISTICALLY_VERIFIED
    assert levels.role_admissibility == LEVEL_DETERMINISTICALLY_VERIFIED
    assert levels.semantic_relation == LEVEL_ANALYZER_ASSESSED
    assert levels.semantic_relation != LEVEL_DETERMINISTICALLY_VERIFIED
    assert levels.deterministically_verified_dimensions == (
        DIMENSION_SOURCE_BINDING,
        DIMENSION_CITATION_INTEGRITY,
        DIMENSION_ROLE_ADMISSIBILITY,
    )
    assert result.verified_evidence is not None
    assert result.verified_evidence.verification_levels == levels


def test_a_contradicting_record_keeps_exactly_the_same_separation():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition("SessionStore keeps session state only in memory.")
    request = _request(receipt, claim)
    analyzer = _analyzer(
        supporting_markers=(),
        contradicting_markers=(b"sqlite3.connect",),
    )

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.status == STATUS_CONTRADICTED
    assert result.relation == RELATION_CONTRADICTS
    assert result.promotion_status == PROMOTION_PROMOTED

    levels = result.verification_levels
    assert levels.source_binding == LEVEL_DETERMINISTICALLY_VERIFIED
    assert levels.citation_integrity == LEVEL_DETERMINISTICALLY_VERIFIED
    assert levels.role_admissibility == LEVEL_DETERMINISTICALLY_VERIFIED
    assert levels.semantic_relation == LEVEL_ANALYZER_ASSESSED


def test_insufficient_and_unrelated_results_keep_the_distinction_too():
    """Nothing was promoted, and the relation is still an analyzer's judgement."""
    payload, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition("SessionStore writes session state to SQLite.")
    insufficient = verify_acquired_source(
        _request(receipt, claim), payload, receipt, _analyzer()
    )

    assert insufficient.status == STATUS_INSUFFICIENT
    assert insufficient.relation == RELATION_INSUFFICIENT
    assert insufficient.promotion_status == PROMOTION_NOT_PROMOTED
    assert (
        insufficient.verification_levels.semantic_relation == LEVEL_ANALYZER_ASSESSED
    )
    assert (
        insufficient.verification_levels.source_binding
        == LEVEL_DETERMINISTICALLY_VERIFIED
    )

    styles_payload, styles_receipt = _acquire(
        "web/static/session.css",
        STYLESHEET,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    unrelated = verify_acquired_source(
        _request(styles_receipt, claim),
        styles_payload,
        styles_receipt,
        _analyzer(),
    )

    assert unrelated.status == STATUS_UNRELATED
    assert unrelated.relation == RELATION_UNRELATED
    assert unrelated.verification_levels.semantic_relation == LEVEL_ANALYZER_ASSESSED


def test_a_binding_refusal_establishes_nothing_at_all():
    payload, receipt, claim, request = _sqlite_case()
    tampered, _ = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )

    result = verify_acquired_source(request, tampered, receipt, _analyzer())

    assert result.status == STATUS_BINDING_INVALID
    levels = result.verification_levels
    assert levels.source_binding == LEVEL_NOT_ESTABLISHED
    assert levels.citation_integrity == LEVEL_NOT_ESTABLISHED
    assert levels.role_admissibility == LEVEL_NOT_ESTABLISHED
    assert levels.semantic_relation == LEVEL_NOT_ESTABLISHED
    assert levels.semantic_assessment_source == SEMANTIC_ASSESSMENT_NOT_ASSESSED


# =============================================================================
# 3. Role verification and proposition relation stay separate axes
# =============================================================================

def test_a_competent_verified_role_may_still_be_insufficient_for_the_claim():
    """implementation_authority + insufficient remains a valid, ordinary record."""
    payload, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition("SessionStore writes session state to SQLite.")

    result = verify_acquired_source(
        _request(receipt, claim), payload, receipt, _analyzer()
    )

    assert ROLE_IMPLEMENTATION_AUTHORITY in result.verified_roles
    assert result.relation == RELATION_INSUFFICIENT
    assert (
        result.verification_levels.role_admissibility
        == LEVEL_DETERMINISTICALLY_VERIFIED
    )
    assert result.verification_levels.semantic_relation == LEVEL_ANALYZER_ASSESSED


def test_validation_evidence_may_contradict_its_own_scope():
    """validation_evidence + contradicts remains valid; the marker couples nothing."""
    payload, receipt = _acquire(
        "tests/test_sessions.py",
        VALIDATION_TEST,
        (ROLE_VALIDATION_EVIDENCE,),
        (SOURCE_CLASS_VALIDATION_TEST,),
        domain=DOMAIN_VALIDATION_ARTIFACTS,
    )
    claim = _proposition(
        "The test suite expects session state to be discarded on restart.",
        scope=SCOPE_VALIDATION_EXPECTATION,
    )
    analyzer = _analyzer(
        supporting_markers=(),
        contradicting_markers=(b"survives_a_restart",),
        relevance_markers=(b"session",),
    )

    result = verify_acquired_source(
        _request(receipt, claim), payload, receipt, analyzer
    )

    assert result.status == STATUS_CONTRADICTED
    assert result.verified_roles == (ROLE_VALIDATION_EVIDENCE,)
    assert result.relation == RELATION_CONTRADICTS
    assert result.verification_levels.semantic_relation == LEVEL_ANALYZER_ASSESSED
    assert (
        result.verification_levels.role_admissibility
        == LEVEL_DETERMINISTICALLY_VERIFIED
    )


# =============================================================================
# 4. Nothing serialized claims the proposition was proven
# =============================================================================

@pytest.mark.parametrize("promote", [True, False])
def test_a_serialized_result_never_claims_proven_semantic_truth(promote: bool):
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION if promote else MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition("SessionStore writes session state to SQLite.")

    result = verify_acquired_source(
        _request(receipt, claim), payload, receipt, _analyzer()
    )
    text = render_evidence_verification_result_json(result)

    assert result.promoted is promote
    for token in _FORBIDDEN_OVERCLAIMS:
        assert token not in text, token
    payload_dict = json.loads(text)
    assert payload_dict["guardrails"]["semantic_relation_proved_deterministically"] is False
    assert payload_dict["guardrails"]["semantic_relation_analyzer_assessed"] is True
    assert payload_dict["claim_synthesized"] is False


def test_a_promoted_record_serializes_its_semantic_status_and_no_truth_claim():
    payload, receipt, claim, request = _sqlite_case()
    result = verify_acquired_source(request, payload, receipt, _analyzer())
    evidence = result.verified_evidence
    assert evidence is not None

    text = json.dumps(evidence.as_dict(), ensure_ascii=False)
    for token in _FORBIDDEN_OVERCLAIMS:
        assert token not in text, token

    serialized = evidence.as_dict()
    assert serialized["verification_levels"]["semantic_relation"] == (
        LEVEL_ANALYZER_ASSESSED
    )
    assert serialized["verification_levels"][
        "semantic_relation_proved_deterministically"
    ] is False
    assert serialized["guardrails"]["semantic_relation_analyzer_assessed"] is True
    assert serialized["authority"]["claim_synthesis_authority"] is False
    assert serialized["authority"]["final_claim_authority"] is False


def test_serializing_several_results_side_by_side_upgrades_nothing():
    payload, receipt, claim, request = _sqlite_case()
    first = verify_acquired_source(request, payload, receipt, _analyzer())
    second = verify_acquired_source(request, payload, receipt, _analyzer())

    text = render_verification_set_json((first, second))
    parsed = json.loads(text)

    assert parsed["aggregated"] is False
    assert parsed["majority_computed"] is False
    assert parsed["confidence_computed"] is False
    assert parsed["semantic_relations_proved_deterministically"] is False
    for entry in parsed["results"]:
        assert entry["verification_levels"]["semantic_relation"] == (
            LEVEL_ANALYZER_ASSESSED
        )
    for token in _FORBIDDEN_OVERCLAIMS:
        assert token not in text, token


# =============================================================================
# 5. Semantics are attributed to the proposal, never to a vendor
# =============================================================================

def _support_proposal(
    claim: Proposition,
    receipt: SourceAcquisitionReceipt,
    payload: AcquiredSourcePayload,
    spans: tuple[object, ...],
    reasons: tuple[str, ...],
) -> EvidenceVerificationProposal:
    return EvidenceVerificationProposal(
        proposition_id=claim.proposition_id,
        proposition_sha256=claim.proposition_sha256,
        source_identifier=receipt.candidate_identifier,
        source_content_sha256=payload.content_sha256,
        relation=RELATION_SUPPORTS,
        role_assessments=(
            RoleAssessment(
                role=ROLE_IMPLEMENTATION_AUTHORITY,
                status=ROLE_STATUS_VERIFIED,
                reasons=(ANALYSIS_ROLE_CONTENT_CONSISTENT,),
            ),
        ),
        evidence_spans=spans,  # type: ignore[arg-type]
        reasons=reasons,
    )


def test_the_record_attributes_semantics_to_a_proposal_not_to_a_provider():
    payload, receipt, claim, request = _sqlite_case()
    result = verify_acquired_source(request, payload, receipt, _analyzer())

    serialized = result.as_dict()
    analyzer_block = serialized["analyzer"]
    assert analyzer_block["semantic_relation_status"] == LEVEL_ANALYZER_ASSESSED
    assert analyzer_block["semantic_relation_assessed_by"] == (
        SEMANTIC_ASSESSMENT_ANALYZER_PROPOSAL
    )
    assert analyzer_block["analyzer_proposal_fingerprint"] == (
        result.analyzer_proposal_fingerprint
    )
    # No field anywhere demands, or accepts, a provider or model identity.
    text = json.dumps(serialized, ensure_ascii=False).casefold()
    for vendor_token in ("provider_name", "model_name", "model_id", "vendor"):
        assert vendor_token not in text, vendor_token


def test_a_different_proposal_rebinds_the_semantics_and_moves_no_source_identity():
    """The same bytes and the same span, assessed by two different proposals."""
    payload, receipt, claim, request = _sqlite_case()
    view = bounded_payload_view(payload, receipt)
    start, end = view.locate(b"sqlite3.connect")
    span = span_from_view(view, start, end, SPAN_SUPPORTING)

    first = verify_acquired_source(
        request,
        payload,
        receipt,
        ScriptedEvidenceAnalyzer(
            [
                _support_proposal(
                    claim, receipt, payload, (span,), (ANALYSIS_PROPOSITION_TERMS_PRESENT,)
                )
            ]
        ),
    )
    second = verify_acquired_source(
        request,
        payload,
        receipt,
        ScriptedEvidenceAnalyzer(
            [
                _support_proposal(
                    claim, receipt, payload, (span,), (ANALYSIS_MECHANISM_IMPLEMENTED,)
                )
            ]
        ),
    )

    # The semantic assessment is bound to a different proposal ...
    assert first.analyzer_proposal_fingerprint != second.analyzer_proposal_fingerprint
    assert first.verified_evidence is not None and second.verified_evidence is not None
    assert first.verified_evidence.evidence_id != second.verified_evidence.evidence_id

    # ... while every deterministic identity is byte-for-byte the same.
    assert first.source_identifier == second.source_identifier
    assert first.source_content_sha256 == second.source_content_sha256
    assert first.acquisition_receipt_fingerprint == (
        second.acquisition_receipt_fingerprint
    )
    assert first.request_fingerprint == second.request_fingerprint
    assert first.evidence_span_refs == second.evidence_span_refs

    # ... and the epistemic status of the relation did not move either way.
    assert first.verification_levels == second.verification_levels
    assert first.verification_levels.semantic_relation == LEVEL_ANALYZER_ASSESSED


# =============================================================================
# 6. A promoted record cannot be hand-built around the distinction
# =============================================================================

def _promoted_kwargs(result) -> dict[str, object]:
    evidence = result.verified_evidence
    assert evidence is not None
    return {
        "proposition_id": evidence.proposition_id,
        "proposition_sha256": evidence.proposition_sha256,
        "source_identifier": evidence.source_identifier,
        "source_content_sha256": evidence.source_content_sha256,
        "acquisition_receipt_fingerprint": evidence.acquisition_receipt_fingerprint,
        "verified_roles": evidence.verified_roles,
        "rejected_roles": evidence.rejected_roles,
        "relation": evidence.relation,
        "evidence_span_refs": evidence.evidence_span_refs,
        "coverage_status": evidence.coverage_status,
        "verification_reasons": evidence.verification_reasons,
        "analyzer_proposal_fingerprint": evidence.analyzer_proposal_fingerprint,
    }


def test_promoted_evidence_without_an_assessed_semantic_relation_does_not_construct():
    payload, receipt, claim, request = _sqlite_case()
    result = verify_acquired_source(request, payload, receipt, _analyzer())
    fields = _promoted_kwargs(result)

    with pytest.raises(ValueError, match="analyzer-assessed semantic relation"):
        VerifiedEvidence(
            **fields,  # type: ignore[arg-type]
            verification_levels=VerificationLevels(
                source_binding=LEVEL_DETERMINISTICALLY_VERIFIED,
                citation_integrity=LEVEL_DETERMINISTICALLY_VERIFIED,
                role_admissibility=LEVEL_DETERMINISTICALLY_VERIFIED,
            ),
        )


def test_promoted_evidence_must_have_cleared_every_deterministic_dimension():
    payload, receipt, claim, request = _sqlite_case()
    result = verify_acquired_source(request, payload, receipt, _analyzer())
    fields = _promoted_kwargs(result)

    with pytest.raises(ValueError, match="citation_integrity verified"):
        VerifiedEvidence(
            **fields,  # type: ignore[arg-type]
            verification_levels=VerificationLevels(
                source_binding=LEVEL_DETERMINISTICALLY_VERIFIED,
                role_admissibility=LEVEL_DETERMINISTICALLY_VERIFIED,
                semantic_relation=LEVEL_ANALYZER_ASSESSED,
            ),
        )


# =============================================================================
# 7. The frozen EVIDENCE.1 epistemic rules are unchanged
# =============================================================================

def test_negative_existential_coverage_rules_are_unchanged():
    """Absence still needs coverage; the new marker changed no gate."""
    payload, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition(
        "DeepSeek Harness has no session persistence.",
        proposition_type=PROPOSITION_NEGATIVE_EXISTENTIAL,
    )
    analyzer = _analyzer(supporting_markers=(b"self._sessions = {}",))

    uncovered = verify_acquired_source(
        _request(receipt, claim), payload, receipt, analyzer
    )
    assert uncovered.status == STATUS_COVERAGE_REQUIRED
    assert uncovered.relation == RELATION_INSUFFICIENT
    assert uncovered.promotion_status == PROMOTION_NOT_PROMOTED
    assert GATE_PROMOTION_BLOCKED_NEGATIVE_COVERAGE in uncovered.reasons
    assert uncovered.verification_levels.semantic_relation == LEVEL_ANALYZER_ASSESSED

    covered = verify_acquired_source(
        _request(receipt, claim, coverage=_coverage(claim, receipt)),
        payload,
        receipt,
        analyzer,
    )
    assert covered.status == STATUS_VERIFIED
    assert covered.promotion_status == PROMOTION_PROMOTED
    assert covered.verification_levels.semantic_relation == LEVEL_ANALYZER_ASSESSED


def test_a_counterexample_still_contradicts_an_absence_without_coverage():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition(
        "DeepSeek Harness has no session persistence.",
        proposition_type=PROPOSITION_NEGATIVE_EXISTENTIAL,
    )
    analyzer = _analyzer(
        supporting_markers=(),
        contradicting_markers=(b"sqlite3.connect",),
    )

    result = verify_acquired_source(
        _request(receipt, claim), payload, receipt, analyzer
    )

    assert result.status == STATUS_CONTRADICTED
    assert result.promotion_status == PROMOTION_PROMOTED
    assert result.verification_levels.semantic_relation == LEVEL_ANALYZER_ASSESSED


def test_current_state_rules_are_unchanged():
    """Code existing is still not code running, in either direction."""
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition(
        "Session state survives a process restart at runtime.",
        scope=SCOPE_RUNTIME_BEHAVIOUR,
    )

    without_receipt = verify_acquired_source(
        _request(receipt, claim), payload, receipt, _analyzer()
    )
    assert without_receipt.status == STATUS_INSUFFICIENT
    assert GATE_PROMOTION_BLOCKED_CURRENT_STATE in without_receipt.reasons
    assert (
        without_receipt.verification_levels.semantic_relation == LEVEL_ANALYZER_ASSESSED
    )

    unestablished = verify_acquired_source(
        _request(
            receipt,
            claim,
            current_state=_current_state(claim, receipt, established=False),
        ),
        payload,
        receipt,
        _analyzer(),
    )
    assert unestablished.status == STATUS_INSUFFICIENT
    assert GATE_PROMOTION_BLOCKED_CURRENT_STATE in unestablished.reasons

    established = verify_acquired_source(
        _request(receipt, claim, current_state=_current_state(claim, receipt)),
        payload,
        receipt,
        _analyzer(),
    )
    assert established.status == STATUS_VERIFIED
    assert established.promotion_status == PROMOTION_PROMOTED
    assert established.verification_levels.semantic_relation == LEVEL_ANALYZER_ASSESSED


def test_the_span_purposes_and_relation_vocabulary_did_not_move():
    assert SPAN_SUPPORTING != SPAN_CONTRADICTING
    payload, receipt, claim, request = _sqlite_case()
    result = verify_acquired_source(request, payload, receipt, _analyzer())
    assert {ref.purpose for ref in result.evidence_span_refs} <= {
        SPAN_SUPPORTING,
        "role_evidence",
    }
