"""CLAIM.1 — bounded proposition assessment.

The matrix is organised the way the phase reasons:

1.  basic sets — what one relation, and then two, justify for the claim
2.  conflict, and the absence of a winner at any scale
3.  duplication, independence and corroboration
4.  negative existential coverage
5.  current-state coverage
6.  role coverage, which is a different axis from direction
7.  semantic provenance, preserved through aggregation
8.  the hard entry gate, which fails closed
9.  the DeepSeek dogfood sets, end to end
10. determinism, fingerprint binding, authority, guardrails and the things this
    phase never emits

Every evidence set in this file is produced by the real EVIDENCE.2 aggregator
over records produced by the real EVIDENCE.1 gate, so the claim contract is
exercised against material that actually cleared promotion and admission.  Every
test runs offline: no model, no network, no repository read, no acquisition.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

from core.acquisition_request import (
    SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,
    SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,
    SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
    SOURCE_CLASS_VALIDATION_TEST,
)
from core.claim_assessment import (
    ASSESSMENT_BASIS_GATED_ANALYZER_ASSESSMENTS,
    ASSESSMENT_BASIS_NOT_ASSESSED,
    ASSESSMENT_STATUSES,
    BASIS_ANALYZER_ASSESSED,
    BASIS_NOT_ESTABLISHED,
    CLAIM_CONFLICTING_EVIDENCE,
    CLAIM_CONFLICT_NOT_ADJUDICATED,
    CLAIM_CONTRADICTED_DIRECTIONAL_EVIDENCE,
    CLAIM_CURRENT_STATE_COVERAGE_INCONSISTENT,
    CLAIM_CURRENT_STATE_UNESTABLISHED,
    CLAIM_DUPLICATE_LINEAGE_DOES_NOT_STRENGTHEN,
    CLAIM_INDEPENDENT_CORROBORATION_REQUIRED,
    CLAIM_INPUT_REJECTED,
    CLAIM_INSUFFICIENT_DIRECTIONAL_EVIDENCE,
    CLAIM_NEGATIVE_COVERAGE_INCONSISTENT,
    CLAIM_NEGATIVE_COVERAGE_REQUIRED,
    CLAIM_NO_CONFIDENCE_COMPUTED,
    CLAIM_NO_DIRECTIONAL_EVIDENCE,
    CLAIM_NO_FINAL_RESPONSE_SYNTHESIZED,
    CLAIM_NO_MAJORITY_COMPUTED,
    CLAIM_NO_OBJECTIVE_TRUTH_DETERMINED,
    CLAIM_REQUIRED_ROLE_COVERAGE_INCOMPLETE,
    CLAIM_SEMANTIC_BASIS_PRESERVED,
    CLAIM_SUPPORTED_DIRECTIONAL_EVIDENCE,
    CORROBORATION_DUPLICATE_ONLY,
    CORROBORATION_INDEPENDENCE_UNKNOWN,
    CORROBORATION_INDEPENDENT,
    CORROBORATION_NONE,
    CORROBORATION_NOT_ASSESSED,
    INCONSISTENT_EVIDENCE_SET,
    INCONSISTENT_LINEAGE_MEMBERSHIP,
    INCONSISTENT_PROPOSITION_BINDING,
    INCONSISTENT_RELATION_PARTITION,
    INCONSISTENT_REQUIREMENT_BINDING,
    INCONSISTENT_SET_FINGERPRINT,
    INCONSISTENT_UPSTREAM_CLAIM_AUTHORITY,
    INCONSISTENT_UPSTREAM_GUARDRAIL,
    MISSING_CONFLICT_ADJUDICATION,
    MISSING_CURRENT_STATE_COVERAGE,
    MISSING_DIRECTIONAL_EVIDENCE,
    MISSING_INDEPENDENT_CORROBORATION,
    MISSING_NEGATIVE_CLAIM_COVERAGE,
    MISSING_REQUIRED_ROLE,
    MISSING_ROLE_REQUIREMENTS_NOT_SUPPLIED,
    SEMANTIC_BASES,
    STATUS_CONFLICTING,
    STATUS_CONTRADICTED,
    STATUS_COVERAGE_INCOMPLETE,
    STATUS_CURRENT_STATE_INCONSISTENT,
    STATUS_CURRENT_STATE_UNESTABLISHED,
    STATUS_INCONSISTENT_INPUT,
    STATUS_INSUFFICIENT,
    STATUS_SUPPORTED,
    ClaimAssessment,
    ClaimAssessmentRequest,
    ClaimRequirements,
    assess_claim,
    claim_request_fingerprint,
    render_claim_assessment_json,
)
from core.content_acquisition import (
    MODE_REPOSITORY_READ,
    AcquiredSourcePayload,
    SourceAcquisitionReceipt,
    SourceBinding,
)
from core.evidence_analyzer import StaticEvidenceAnalyzer
from core.evidence_promotion_gate import verify_acquired_source
from core.evidence_requirements import (
    DOMAIN_REPOSITORY,
    DOMAIN_VALIDATION_ARTIFACTS,
    ROLE_ARCHITECTURE_DESCRIPTION,
    ROLE_CONFIGURATION_AUTHORITY,
    ROLE_HISTORICAL_CONTEXT,
    ROLE_IMPLEMENTATION_AUTHORITY,
    ROLE_VALIDATION_EVIDENCE,
    TIER_REQUIRED_PRIMARY,
)
from core.evidence_set_assessment import (
    CONFLICT_CONFLICTING,
    CONFLICT_CONTRADICTION_ONLY,
    CONFLICT_NO_DIRECTIONAL_EVIDENCE,
    CONFLICT_SUPPORT_ONLY,
    COVERAGE_COMPLETE,
    COVERAGE_INCOMPLETE,
    COVERAGE_INCONSISTENT,
    COVERAGE_NOT_APPLICABLE,
    LINEAGE_DISTINCT_ORIGIN,
    MAX_EVIDENCE_SET_RECORDS,
    SET_ASSESSED,
    SET_INCONSISTENT_INPUT,
    EvidenceSetAssessment,
    EvidenceSetRequest,
    EvidenceSetRequirements,
    SourceLineageDeclaration,
    assess_evidence_set,
)
from core.evidence_verification import (
    CONSTRAINT_CURRENT_STATE_RECEIPT_REQUIRED,
    CONSTRAINT_NEGATIVE_COVERAGE_REQUIRED,
    CONSTRAINT_ROLE_VERIFICATION_REQUIRED,
    COVERAGE_ALL_ELIGIBLE_CANDIDATES_ACQUIRED,
    COVERAGE_ALL_REQUIRED_ROLES_ACQUIRED,
    COVERAGE_SUFFICIENT,
    CURRENT_STATE_ESTABLISHED,
    CURRENT_STATE_NOT_ESTABLISHED,
    CURRENT_STATE_RUNTIME_ENTRYPOINT_CONFIRMED,
    LEVEL_ANALYZER_ASSESSED,
    LEVEL_DETERMINISTICALLY_VERIFIED,
    PROPOSITION_NEGATIVE_EXISTENTIAL,
    PROPOSITION_POSITIVE,
    RELATION_CONTRADICTS,
    RELATION_INSUFFICIENT,
    RELATION_SUPPORTS,
    RELATION_UNRELATED,
    SCOPE_IMPLEMENTATION_STATE,
    SCOPE_RUNTIME_BEHAVIOUR,
    SCOPE_VALIDATION_EXPECTATION,
    SCOPES_REQUIRING_CURRENT_STATE,
    STATUS_CONTRADICTED as EVIDENCE_STATUS_CONTRADICTED,
    STATUS_INSUFFICIENT as EVIDENCE_STATUS_INSUFFICIENT,
    STATUS_VERIFIED,
    VERIFICATION_CONSTRAINTS,
    CurrentStateReceipt,
    EvidenceVerificationRequest,
    NegativeClaimCoverage,
    Proposition,
    source_receipt_fingerprint,
)


# ── Fixtures: ACQUIRE.3 artefacts, built without running ACQUIRE.3 ─────────────

def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _binding(identifier: str, **overrides: object) -> SourceBinding:
    values: dict[str, object] = {
        "candidate_identifier": identifier,
        "acquisition_mode": MODE_REPOSITORY_READ,
        "task_contract_fingerprint": _digest("task-contract"),
        "completion_fingerprint": _digest("completion"),
        "waiter_decision_fingerprint": _digest("waiter-decision"),
        "evidence_requirement_fingerprint": _digest("evidence-requirement"),
        "acquisition_request_fingerprint": _digest("acquisition-request"),
        "candidate_receipt_fingerprint": _digest("candidate-pool"),
        "selection_fingerprint": _digest("selection"),
        "authorization_fingerprint": _digest("authorization"),
        "inventory_fingerprint": _digest("inventory"),
        "repository_identity": "repo:deepseek-harness",
    }
    values.update(overrides)
    return SourceBinding(**values)  # type: ignore[arg-type]


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
    identifier: str = "P-1",
) -> Proposition:
    return Proposition(
        proposition_id=identifier,
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
    receipts: tuple[SourceAcquisitionReceipt, ...],
    *,
    status: str = COVERAGE_SUFFICIENT,
    required_roles: tuple[str, ...] = (ROLE_IMPLEMENTATION_AUTHORITY,),
    acquisition_request_fingerprint: str | None = None,
) -> NegativeClaimCoverage:
    first = receipts[0]
    return NegativeClaimCoverage(
        proposition_id=proposition.proposition_id,
        proposition_sha256=proposition.proposition_sha256,
        required_roles=required_roles,
        acquisition_request_fingerprint=(
            acquisition_request_fingerprint
            or first.source_binding.acquisition_request_fingerprint
        ),
        candidate_pool_fingerprint=first.source_binding.candidate_receipt_fingerprint,
        acquired_source_receipt_fingerprints=tuple(
            sorted({source_receipt_fingerprint(item) for item in receipts})
        ),
        coverage_status=status,
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

def _sqlite_implementation(marker: str = "") -> bytes:
    return (
        '"""Session storage backed by SQLite.%s"""\n\n'
        "import sqlite3\n\n\n"
        "class SessionStore:\n"
        "    def __init__(self, path):\n"
        "        self._connection = sqlite3.connect(path)\n\n"
        "    def save_session(self, session_id, state):\n"
        '        self._connection.execute("INSERT INTO sessions VALUES (?, ?)")\n'
        "        self._connection.commit()\n" % (f"  {marker}" if marker else "")
    ).encode("utf-8")


MEMORY_IMPLEMENTATION = b'''"""Session storage held for the lifetime of the process."""


class SessionStore:
    def __init__(self):
        self._sessions = {}

    def save_session(self, session_id, state):
        self._sessions[session_id] = state
'''

NO_PERSISTENCE_DOC = b'''# Session architecture

The harness keeps sessions in memory only. There is no session persistence
anywhere in the runtime.
'''

VALIDATION_TEST = b'''def test_session_state_survives_a_restart(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    store.save_session("abc", b"state")
    assert SessionStore(tmp_path / "sessions.db").load_session("abc") == b"state"
'''

HISTORICAL_NOTE = b'''# Rejected: SQLite session persistence

We considered persisting sessions with sqlite3.connect and decided against it.
This proposal was rejected and was never implemented.
'''

STYLESHEET = b'''.toolbar-panel {
    display: flex;
    gap: 8px;
}
'''


_ROLE_MARKERS = {
    ROLE_IMPLEMENTATION_AUTHORITY: (b"def save_session", b"self._sessions"),
    ROLE_ARCHITECTURE_DESCRIPTION: (b"# Session architecture",),
    ROLE_VALIDATION_EVIDENCE: (b"def test_",),
    ROLE_CONFIGURATION_AUTHORITY: (b"dependencies = [",),
    ROLE_HISTORICAL_CONTEXT: (b"was rejected",),
}


def _analyzer(**overrides: object) -> StaticEvidenceAnalyzer:
    values: dict[str, object] = {
        "role_markers": dict(_ROLE_MARKERS),
        "supporting_markers": (b"sqlite3.connect",),
        "relevance_markers": (b"session", b"sessions"),
        "context_bytes": 40,
    }
    values.update(overrides)
    return StaticEvidenceAnalyzer(**values)  # type: ignore[arg-type]


def _verify(
    identifier: str,
    content: bytes,
    roles: tuple[str, ...],
    classes: tuple[str, ...],
    claim: Proposition,
    *,
    domain: str = DOMAIN_REPOSITORY,
    coverage: NegativeClaimCoverage | None = None,
    current_state_established: bool | None = None,
    analyzer: StaticEvidenceAnalyzer | None = None,
):
    """Run the real EVIDENCE.1 gate and hand back its result plus its receipts."""
    payload, receipt = _acquire(identifier, content, roles, classes, domain=domain)
    current_state = (
        None
        if current_state_established is None
        else _current_state(claim, receipt, established=current_state_established)
    )
    request = _request(receipt, claim, coverage=coverage, current_state=current_state)
    result = verify_acquired_source(request, payload, receipt, analyzer or _analyzer())
    return result, receipt, current_state


def _support(claim: Proposition, identifier: str, marker: str = "", **kwargs):
    return _verify(
        identifier,
        _sqlite_implementation(marker),
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
        claim,
        **kwargs,
    )


def _contradiction(claim: Proposition, identifier: str, marker: str = "", **kwargs):
    return _verify(
        identifier,
        _sqlite_implementation(marker),
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
        claim,
        analyzer=_analyzer(
            supporting_markers=(),
            contradicting_markers=(b"sqlite3.connect",),
        ),
        **kwargs,
    )


def _insufficient(claim: Proposition, identifier: str, **kwargs):
    return _verify(
        identifier,
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
        claim,
        **kwargs,
    )


def _unrelated(claim: Proposition, identifier: str, **kwargs):
    return _verify(
        identifier,
        STYLESHEET,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
        claim,
        **kwargs,
    )


def _covered_absence_support(claim: Proposition, identifier: str, marker: str = ""):
    """A promoted ``supports`` on an absence, with the coverage receipt it needs."""
    content = MEMORY_IMPLEMENTATION + (f"\n# {marker}\n".encode("utf-8") if marker else b"")
    payload, receipt = _acquire(
        identifier,
        content,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    coverage = _coverage(claim, (receipt,))
    result = verify_acquired_source(
        _request(receipt, claim, coverage=coverage),
        payload,
        receipt,
        _analyzer(supporting_markers=(b"self._sessions = {}",)),
    )
    return result, receipt, coverage


def _set(claim: Proposition, *records, **kwargs) -> EvidenceSetAssessment:
    return assess_evidence_set(
        EvidenceSetRequest(proposition=claim, records=tuple(records), **kwargs)
    )


def _set_requirements(
    claim: Proposition, roles: tuple[str, ...]
) -> EvidenceSetRequirements:
    return EvidenceSetRequirements(
        proposition_id=claim.proposition_id,
        proposition_sha256=claim.proposition_sha256,
        required_roles=roles,
        evidence_requirement_fingerprint=_digest("evidence-requirement"),
    )


def _claim_requirements(
    claim: Proposition,
    roles: tuple[str, ...] = (),
    *,
    independent_corroboration_required: bool = False,
) -> ClaimRequirements:
    return ClaimRequirements(
        proposition_id=claim.proposition_id,
        proposition_sha256=claim.proposition_sha256,
        required_roles=roles,
        evidence_requirement_fingerprint=_digest("evidence-requirement"),
        independent_corroboration_required=independent_corroboration_required,
    )


def _assess(
    claim: Proposition,
    evidence_set: EvidenceSetAssessment,
    **kwargs,
) -> ClaimAssessment:
    return assess_claim(
        ClaimAssessmentRequest(
            proposition=claim, evidence_set=evidence_set, **kwargs
        )
    )


_SQLITE_CLAIM_TEXT = "SessionStore writes session state to SQLite."
_NO_PERSISTENCE = "DeepSeek Harness has no session persistence."


def _negative_claim() -> Proposition:
    return _proposition(
        _NO_PERSISTENCE,
        proposition_type=PROPOSITION_NEGATIVE_EXISTENTIAL,
    )


def _runtime_claim() -> Proposition:
    return _proposition(
        "Session state survives a process restart at runtime.",
        scope=SCOPE_RUNTIME_BEHAVIOUR,
    )


#: Field names that would turn a bounded assessment into a truth claim.  Checked
#: as exact keys rather than substrings, because the honest negations —
#: ``no_majority_computed``, ``confidence_computed: false``,
#: ``objective_truth_asserted: false`` — legitimately contain the same words.
_FORBIDDEN_KEYS = frozenset(
    {
        "claim_false",
        "claim_proven",
        "claim_true",
        "claim_verified",
        "conclusion",
        "confidence",
        "deterministic_truth",
        "deterministically_proven_semantics",
        "final_answer",
        "final_claim",
        "final_relation",
        "ground_truth",
        "likelihood",
        "probability",
        "proposition_false",
        "proposition_true",
        "proposition_verified_true",
        "recommendation",
        "score",
        "semantic_truth_verified",
        "semantically_verified",
        "support_score",
        "truth_score",
        "truth_status",
        "verdict",
        "winner",
        "winning_relation",
    }
)

#: String *values* that would smuggle a verdict past a key-name scan.
_FORBIDDEN_VALUES = frozenset(
    {
        "claim_false",
        "claim_true",
        "confidence_high",
        "deterministic_truth",
        "deterministically_proven_semantics",
        "deterministically_verified",
        "false",
        "ground_truth",
        "likely_true",
        "probably_false",
        "proposition_true",
        "semantically_verified",
        "true",
    }
)


def _keys(node) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found.append(key)
            found.extend(_keys(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_keys(item))
    return found


def _values(node) -> list[object]:
    found: list[object] = []
    if isinstance(node, dict):
        for value in node.values():
            found.extend(_values(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_values(item))
    else:
        found.append(node)
    return found


def _assert_no_truth_claim_and_no_number(assessment: ClaimAssessment) -> None:
    """No field names a truth value, and no value is a number or a truth token."""
    text = render_claim_assessment_json(assessment)
    payload = json.loads(text)
    for key in _keys(payload):
        assert key not in _FORBIDDEN_KEYS, key
    for value in _values(payload):
        assert not isinstance(value, float), value
        if isinstance(value, str):
            assert value.casefold() not in _FORBIDDEN_VALUES, value
    for token in (
        "deterministically_proven_semantics",
        "semantically_verified",
        "proposition_true",
        "deterministic_truth",
        "claim_true",
        "claim_false",
    ):
        assert token not in text, token


# =============================================================================
# 1. Basic sets
# =============================================================================

def test_a_one_valid_support_with_sufficient_coverage_is_supported():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    assert record.status == STATUS_VERIFIED
    evidence_set = _set(claim, record)

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_SUPPORTED
    assert assessment.conflict_status == CONFLICT_SUPPORT_ONLY
    assert CLAIM_SUPPORTED_DIRECTIONAL_EVIDENCE in assessment.reasons
    # And what it still is not.
    assert assessment.semantic_basis == BASIS_ANALYZER_ASSESSED
    assert assessment.final_claim_authority is False
    assert assessment.objective_truth_asserted is False
    _assert_no_truth_claim_and_no_number(assessment)


def test_b_one_contradiction_is_contradicted():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _contradiction(claim, "core/session_store.py")
    assert record.status == EVIDENCE_STATUS_CONTRADICTED

    assessment = _assess(claim, _set(claim, record))

    assert assessment.assessment_status == STATUS_CONTRADICTED
    assert assessment.conflict_status == CONFLICT_CONTRADICTION_ONLY
    assert CLAIM_CONTRADICTED_DIRECTIONAL_EVIDENCE in assessment.reasons
    assert assessment.semantic_basis == BASIS_ANALYZER_ASSESSED


def test_c_one_insufficient_record_is_insufficient_evidence():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _insufficient(claim, "core/session_store.py")
    assert record.relation == RELATION_INSUFFICIENT

    assessment = _assess(claim, _set(claim, record))

    assert assessment.assessment_status == STATUS_INSUFFICIENT
    assert assessment.conflict_status == CONFLICT_NO_DIRECTIONAL_EVIDENCE
    assert CLAIM_NO_DIRECTIONAL_EVIDENCE in assessment.reasons
    assert MISSING_DIRECTIONAL_EVIDENCE in assessment.missing_requirements
    assert assessment.directional_record_refs == ()
    assert assessment.corroboration_status == CORROBORATION_NONE


def test_d_one_unrelated_record_is_insufficient_evidence():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _unrelated(claim, "web/static/panel.css")
    assert record.relation == RELATION_UNRELATED

    assessment = _assess(claim, _set(claim, record))

    assert assessment.assessment_status == STATUS_INSUFFICIENT
    assert assessment.non_directional_record_refs != ()


def test_absence_of_support_is_never_read_as_contradiction():
    """B16: nothing said about the claim is not something said against it."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    records = [_insufficient(claim, f"core/module_{index}.py")[0] for index in range(4)]

    assessment = _assess(claim, _set(claim, *records))

    assert assessment.assessment_status == STATUS_INSUFFICIENT
    assert assessment.assessment_status != STATUS_CONTRADICTED


def test_e_support_and_contradiction_together_are_conflicting():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    supporting, _, _ = _support(claim, "core/session_store.py")
    contradicting, _, _ = _contradiction(claim, "core/legacy_store.py", marker="legacy")

    assessment = _assess(claim, _set(claim, supporting, contradicting))

    assert assessment.assessment_status == STATUS_CONFLICTING
    assert assessment.conflict_status == CONFLICT_CONFLICTING
    assert CLAIM_CONFLICTING_EVIDENCE in assessment.reasons
    assert CLAIM_CONFLICT_NOT_ADJUDICATED in assessment.reasons
    assert MISSING_CONFLICT_ADJUDICATION in assessment.missing_requirements


def test_f_five_supports_and_one_contradiction_are_conflicting():
    """The original failure class: 5 > 1 is not an epistemic argument."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    supports = [
        _support(claim, f"core/store_{index}.py", marker=f"v{index}")[0]
        for index in range(5)
    ]
    contradicting, _, _ = _contradiction(claim, "core/legacy_store.py", marker="legacy")
    evidence_set = _set(claim, *supports, contradicting)
    assert len(evidence_set.support_records) == 5
    assert len(evidence_set.contradiction_records) == 1

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_CONFLICTING
    assert assessment.assessment_status != STATUS_SUPPORTED


# =============================================================================
# 2. No voting at any scale
# =============================================================================

def test_g_a_full_set_of_supports_and_one_contradiction_is_still_conflicting():
    """The bounded equivalent of "100 supports": the set ceiling, minus one."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    supports = [
        _support(claim, f"core/store_{index}.py", marker=f"v{index}")[0]
        for index in range(MAX_EVIDENCE_SET_RECORDS - 1)
    ]
    contradicting, _, _ = _contradiction(claim, "core/legacy_store.py", marker="legacy")
    evidence_set = _set(claim, *supports, contradicting)
    assert len(evidence_set.support_records) == MAX_EVIDENCE_SET_RECORDS - 1

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_CONFLICTING
    assert CLAIM_NO_MAJORITY_COMPUTED in assessment.reasons


def test_conflict_does_not_prefer_implementation_over_validation():
    """No role outranks another when the set disagrees with itself."""
    claim = _proposition(
        "The test suite expects session state to survive a restart.",
        scope=SCOPE_VALIDATION_EXPECTATION,
    )
    validation, _, _ = _verify(
        "tests/test_sessions.py",
        VALIDATION_TEST,
        (ROLE_VALIDATION_EVIDENCE,),
        (SOURCE_CLASS_VALIDATION_TEST,),
        claim,
        domain=DOMAIN_VALIDATION_ARTIFACTS,
        analyzer=_analyzer(supporting_markers=(b"survives_a_restart",)),
    )
    counter, _, _ = _verify(
        "tests/test_sessions_memory.py",
        VALIDATION_TEST.replace(b"survives_a_restart", b"survives_a_restart_not"),
        (ROLE_VALIDATION_EVIDENCE,),
        (SOURCE_CLASS_VALIDATION_TEST,),
        claim,
        domain=DOMAIN_VALIDATION_ARTIFACTS,
        analyzer=_analyzer(
            supporting_markers=(),
            contradicting_markers=(b"survives_a_restart_not",),
        ),
    )
    assert validation.relation == RELATION_SUPPORTS
    assert counter.relation == RELATION_CONTRADICTS

    assessment = _assess(claim, _set(claim, validation, counter))

    assert assessment.assessment_status == STATUS_CONFLICTING


def test_h_duplicate_copies_do_not_change_the_status_of_one_lineage():
    """B45: five copies of one reading justify exactly what one reading does."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    single, _, _ = _support(claim, "core/session_store.py")
    copies = [
        _support(claim, f"core/session_store_copy_{index}.py")[0] for index in range(5)
    ]

    alone = _assess(claim, _set(claim, single))
    duplicated = _assess(claim, _set(claim, single, *copies))

    assert alone.assessment_status == STATUS_SUPPORTED
    assert duplicated.assessment_status == alone.assessment_status
    assert duplicated.corroboration_status == CORROBORATION_DUPLICATE_ONLY
    assert CLAIM_DUPLICATE_LINEAGE_DOES_NOT_STRENGTHEN in duplicated.reasons


def test_the_status_vocabulary_holds_no_truth_value_and_no_strength_scale():
    for banned in (
        "true",
        "false",
        "likely_true",
        "probably_false",
        "confidence_high",
        "stronger_support",
        "highly_supported",
        "weak_support",
    ):
        assert banned not in ASSESSMENT_STATUSES, banned
    assert LEVEL_DETERMINISTICALLY_VERIFIED not in SEMANTIC_BASES


# =============================================================================
# 3. Duplication, independence and corroboration
# =============================================================================

def test_i_exact_duplicate_supports_are_duplicate_only_corroboration():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    first, _, _ = _support(claim, "docs/a.md")
    second, _, _ = _support(claim, "docs/b.md")
    evidence_set = _set(claim, first, second)
    assert evidence_set.independence is not None
    assert evidence_set.independence.lineage_group_count == 1

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_SUPPORTED
    assert assessment.corroboration_status == CORROBORATION_DUPLICATE_ONLY
    assert assessment.corroboration_status != CORROBORATION_INDEPENDENT
    assert MISSING_INDEPENDENT_CORROBORATION in assessment.missing_requirements
    assert assessment.lineage_group_refs != ()


def test_j_different_digests_leave_independence_unknown_and_block_nothing():
    """B12: a different hash proves nothing about how two sources came to be."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    first, _, _ = _support(claim, "core/session_store.py", marker="a")
    second, _, _ = _support(claim, "core/other_store.py", marker="b")

    assessment = _assess(claim, _set(claim, first, second))

    assert assessment.assessment_status == STATUS_SUPPORTED
    assert assessment.corroboration_status == CORROBORATION_INDEPENDENCE_UNKNOWN
    assert MISSING_INDEPENDENT_CORROBORATION in assessment.missing_requirements


def test_a_single_support_reports_independence_unknown_rather_than_independent():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")

    assessment = _assess(claim, _set(claim, record))

    assert assessment.corroboration_status == CORROBORATION_INDEPENDENCE_UNKNOWN


def test_k_a_trusted_distinct_origin_declaration_reaches_corroboration():
    """Reachable only through a supplied declaration; nothing here mints one."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    first, _, _ = _support(claim, "core/session_store.py", marker="a")
    second, _, _ = _support(claim, "core/other_store.py", marker="b")
    declaration = SourceLineageDeclaration(
        proposition_id=claim.proposition_id,
        proposition_sha256=claim.proposition_sha256,
        source_identifier="core/other_store.py",
        source_content_sha256=second.source_content_sha256,
        related_source_identifier="core/session_store.py",
        related_source_content_sha256=first.source_content_sha256,
        lineage_relation=LINEAGE_DISTINCT_ORIGIN,
    )

    assessment = _assess(
        claim, _set(claim, first, second, lineage_declarations=(declaration,))
    )

    assert assessment.assessment_status == STATUS_SUPPORTED
    assert assessment.corroboration_status == CORROBORATION_INDEPENDENT
    assert MISSING_INDEPENDENT_CORROBORATION not in assessment.missing_requirements


def test_independence_unknown_does_not_block_a_positive_assessment():
    """B12: unestablished independence is a gap, not a veto."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")

    assessment = _assess(claim, _set(claim, record))

    assert assessment.assessment_status == STATUS_SUPPORTED
    assert MISSING_INDEPENDENT_CORROBORATION in assessment.missing_requirements


def test_independent_corroboration_blocks_only_where_it_was_demanded():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    evidence_set = _set(claim, record)

    demanded = _assess(
        claim,
        evidence_set,
        requirements=_claim_requirements(
            claim, independent_corroboration_required=True
        ),
    )

    assert demanded.assessment_status == STATUS_INSUFFICIENT
    assert CLAIM_INDEPENDENT_CORROBORATION_REQUIRED in demanded.reasons
    assert _assess(claim, evidence_set).assessment_status == STATUS_SUPPORTED


# =============================================================================
# 4. Negative existential claims
# =============================================================================

def test_l_a_negative_claim_without_complete_coverage_is_coverage_incomplete():
    """Support exists, and coverage across the set does not.  Absence needs both."""
    claim = _negative_claim()
    record, receipt, coverage = _covered_absence_support(claim, "core/session_store.py")
    assert record.status == STATUS_VERIFIED
    _, other_receipt = _acquire(
        "core/other_store.py",
        MEMORY_IMPLEMENTATION + b"\n# other\n",
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    foreign_universe = _coverage(
        claim,
        (other_receipt,),
        acquisition_request_fingerprint=_digest("another-acquisition-request"),
    )
    evidence_set = _set(
        claim, record, coverage_receipts=(coverage, foreign_universe)
    )
    assert evidence_set.negative_claim_coverage == COVERAGE_INCONSISTENT
    assert evidence_set.support_records != ()

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_COVERAGE_INCOMPLETE
    assert assessment.assessment_status != STATUS_SUPPORTED
    assert CLAIM_NEGATIVE_COVERAGE_REQUIRED in assessment.reasons
    assert CLAIM_NEGATIVE_COVERAGE_INCONSISTENT in assessment.reasons
    assert MISSING_NEGATIVE_CLAIM_COVERAGE in assessment.missing_requirements


def test_l_support_records_never_substitute_for_an_absence_receipt():
    """A hand-stripped coverage field is refused rather than counted."""
    claim = _negative_claim()
    record, _, coverage = _covered_absence_support(claim, "core/session_store.py")
    covered = _set(claim, record, coverage_receipts=(coverage,))
    uncovered = dataclasses.replace(
        covered, negative_claim_coverage=COVERAGE_INCOMPLETE
    )

    assessment = _assess(claim, uncovered)

    assert assessment.assessment_status == STATUS_COVERAGE_INCOMPLETE
    assert CLAIM_NEGATIVE_COVERAGE_REQUIRED in assessment.reasons


def test_many_absence_documents_never_become_complete_coverage():
    """B17: coverage cannot be repaired by counting files."""
    claim = _negative_claim()
    documents = [
        _verify(
            f"docs/notes/no_persistence_{index}.md",
            NO_PERSISTENCE_DOC + f"\n<!-- {index} -->\n".encode("utf-8"),
            (ROLE_ARCHITECTURE_DESCRIPTION,),
            (SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,),
            claim,
            analyzer=_analyzer(supporting_markers=(b"no session persistence",)),
        )[0]
        for index in range(6)
    ]
    evidence_set = _set(claim, *documents)
    assert evidence_set.support_records == ()

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_INSUFFICIENT
    assert assessment.assessment_status != STATUS_SUPPORTED
    assert MISSING_NEGATIVE_CLAIM_COVERAGE in assessment.missing_requirements


def test_m_a_coverage_backed_support_only_absence_is_supported():
    claim = _negative_claim()
    record, _, coverage = _covered_absence_support(claim, "core/session_store.py")
    evidence_set = _set(claim, record, coverage_receipts=(coverage,))
    assert evidence_set.negative_claim_coverage == COVERAGE_COMPLETE

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_SUPPORTED
    # And the reason it is supported is still an analyzer's reading.
    assert assessment.semantic_basis == BASIS_ANALYZER_ASSESSED
    assert assessment.assessment_basis == ASSESSMENT_BASIS_GATED_ANALYZER_ASSESSMENTS
    _assert_no_truth_claim_and_no_number(assessment)


def test_n_one_counterexample_contradicts_an_absence_with_no_coverage():
    """B18: acknowledging a counterexample is not proving an absence."""
    claim = _negative_claim()
    counterexample, _, _ = _contradiction(claim, "core/session_store.py")
    evidence_set = _set(claim, counterexample)
    assert evidence_set.negative_claim_coverage == COVERAGE_INCOMPLETE

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_CONTRADICTED
    assert assessment.negative_claim_coverage == COVERAGE_INCOMPLETE
    assert MISSING_NEGATIVE_CLAIM_COVERAGE in assessment.missing_requirements


def test_o_coverage_backed_support_plus_a_counterexample_is_conflicting():
    """The receipt does not erase the counterexample, and neither erases the other."""
    claim = _negative_claim()
    supporting, _, coverage = _covered_absence_support(claim, "core/session_store.py")
    contradicting, _, _ = _contradiction(claim, "core/legacy_store.py", marker="legacy")
    evidence_set = _set(
        claim, supporting, contradicting, coverage_receipts=(coverage,)
    )
    assert evidence_set.negative_claim_coverage == COVERAGE_COMPLETE

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_CONFLICTING
    assert assessment.assessment_status not in {STATUS_SUPPORTED, STATUS_CONTRADICTED}


# =============================================================================
# 5. Current-state claims
# =============================================================================

def test_p_a_runtime_claim_without_complete_current_state_is_unestablished():
    claim = _runtime_claim()
    supported, _, receipt = _support(
        claim, "core/session_store.py", current_state_established=True
    )
    assert supported.status == STATUS_VERIFIED
    unreceipted, _, _ = _unrelated(claim, "web/static/panel.css")
    evidence_set = _set(claim, supported, unreceipted, current_state_receipts=(receipt,))
    assert evidence_set.current_state_coverage == COVERAGE_INCOMPLETE
    assert evidence_set.conflict_status == CONFLICT_SUPPORT_ONLY

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_CURRENT_STATE_UNESTABLISHED
    assert CLAIM_CURRENT_STATE_UNESTABLISHED in assessment.reasons
    assert MISSING_CURRENT_STATE_COVERAGE in assessment.missing_requirements


def test_static_implementation_never_becomes_runtime_support():
    """B20: code existing is not code running, at any number of files."""
    claim = _runtime_claim()
    records = [
        _support(claim, f"core/store_{index}.py", marker=f"v{index}")[0]
        for index in range(4)
    ]
    evidence_set = _set(claim, *records)
    # EVIDENCE.1 already downgraded every one of them for want of a receipt.
    assert evidence_set.support_records == ()

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_INSUFFICIENT


def test_q_a_runtime_claim_with_complete_current_state_is_supported():
    claim = _runtime_claim()
    record, _, receipt = _support(
        claim, "core/session_store.py", current_state_established=True
    )
    evidence_set = _set(claim, record, current_state_receipts=(receipt,))
    assert evidence_set.current_state_coverage == COVERAGE_COMPLETE

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_SUPPORTED
    assert assessment.current_state_coverage == COVERAGE_COMPLETE
    assert assessment.semantic_basis == BASIS_ANALYZER_ASSESSED


def test_r_disagreeing_current_state_receipts_are_their_own_bounded_state():
    claim = _runtime_claim()
    established, _, established_receipt = _support(
        claim, "core/session_store.py", current_state_established=True
    )
    payload, receipt = _acquire(
        "core/session_store.py",
        _sqlite_implementation(),
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    denied = _current_state(claim, receipt, established=False)
    unestablished = verify_acquired_source(
        _request(receipt, claim, current_state=denied),
        payload,
        receipt,
        _analyzer(context_bytes=20),
    )
    assert established_receipt is not None
    assert unestablished.status == EVIDENCE_STATUS_INSUFFICIENT
    evidence_set = _set(
        claim,
        established,
        unestablished,
        current_state_receipts=(established_receipt, denied),
    )
    assert evidence_set.current_state_coverage == COVERAGE_INCONSISTENT

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_CURRENT_STATE_INCONSISTENT
    assert CLAIM_CURRENT_STATE_COVERAGE_INCONSISTENT in assessment.reasons
    assert assessment.assessment_status != STATUS_SUPPORTED


def test_a_runtime_contradiction_survives_incomplete_set_coverage():
    """B21: EVIDENCE.1 already required a receipt for the record itself."""
    claim = _runtime_claim()
    contradicting, _, receipt = _contradiction(
        claim, "core/session_store.py", current_state_established=True
    )
    assert contradicting.status == EVIDENCE_STATUS_CONTRADICTED
    unreceipted, _, _ = _unrelated(claim, "web/static/panel.css")
    evidence_set = _set(
        claim, contradicting, unreceipted, current_state_receipts=(receipt,)
    )
    assert evidence_set.current_state_coverage == COVERAGE_INCOMPLETE

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_CONTRADICTED
    assert MISSING_CURRENT_STATE_COVERAGE in assessment.missing_requirements


def test_current_state_coverage_is_not_applicable_outside_runtime_scopes():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")

    assessment = _assess(claim, _set(claim, record))

    assert assessment.current_state_coverage == COVERAGE_NOT_APPLICABLE
    assert assessment.assessment_status == STATUS_SUPPORTED
    assert MISSING_CURRENT_STATE_COVERAGE not in assessment.missing_requirements


# =============================================================================
# 6. Role coverage
# =============================================================================

def test_s_a_missing_required_role_leaves_a_support_set_insufficient():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    evidence_set = _set(
        claim,
        record,
        requirements=_set_requirements(
            claim, (ROLE_IMPLEMENTATION_AUTHORITY, ROLE_CONFIGURATION_AUTHORITY)
        ),
    )
    assert evidence_set.role_coverage_status == COVERAGE_INCOMPLETE

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_INSUFFICIENT
    assert CLAIM_REQUIRED_ROLE_COVERAGE_INCOMPLETE in assessment.reasons
    assert MISSING_REQUIRED_ROLE in assessment.missing_requirements


def test_t_a_role_covered_by_an_insufficient_record_still_discharges_the_role():
    """B23: role presence and directional support are different dimensions."""
    claim = _proposition(
        "The test suite expects session state to survive a restart.",
        scope=SCOPE_VALIDATION_EXPECTATION,
    )
    validation, _, _ = _verify(
        "tests/test_sessions.py",
        VALIDATION_TEST,
        (ROLE_VALIDATION_EVIDENCE,),
        (SOURCE_CLASS_VALIDATION_TEST,),
        claim,
        domain=DOMAIN_VALIDATION_ARTIFACTS,
        analyzer=_analyzer(supporting_markers=(b"survives_a_restart",)),
    )
    implementation, _, _ = _verify(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
        claim,
        analyzer=_analyzer(supporting_markers=(b"self._sessions[session_id]",)),
    )
    assert validation.relation == RELATION_SUPPORTS
    assert implementation.relation == RELATION_INSUFFICIENT
    evidence_set = _set(
        claim,
        validation,
        implementation,
        requirements=_set_requirements(
            claim, (ROLE_IMPLEMENTATION_AUTHORITY, ROLE_VALIDATION_EVIDENCE)
        ),
    )
    assert evidence_set.role_coverage_status == COVERAGE_COMPLETE

    assessment = _assess(claim, evidence_set)

    # EVIDENCE.2's role semantics are preserved exactly, not tightened here.
    assert assessment.assessment_status == STATUS_SUPPORTED
    assert assessment.role_coverage_status == COVERAGE_COMPLETE
    assert len(assessment.directional_record_refs) == 1


def test_role_requirements_are_never_invented_when_none_were_supplied():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    evidence_set = _set(claim, record)
    assert evidence_set.role_coverage_status == COVERAGE_NOT_APPLICABLE

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_SUPPORTED
    assert MISSING_ROLE_REQUIREMENTS_NOT_SUPPLIED in assessment.missing_requirements


def test_role_presence_alone_does_not_make_a_claim_supported():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _insufficient(claim, "core/session_store.py")
    evidence_set = _set(
        claim,
        record,
        requirements=_set_requirements(claim, (ROLE_IMPLEMENTATION_AUTHORITY,)),
    )
    assert evidence_set.role_coverage_status == COVERAGE_COMPLETE

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_INSUFFICIENT


# =============================================================================
# 7. Preserved upstream semantics
# =============================================================================

def test_u_a_supported_claim_still_reports_an_analyzer_assessed_basis():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")

    assessment = _assess(claim, _set(claim, record))

    assert assessment.assessment_status == STATUS_SUPPORTED
    assert assessment.semantic_basis == LEVEL_ANALYZER_ASSESSED
    assert CLAIM_SEMANTIC_BASIS_PRESERVED in assessment.reasons


def test_v_a_contradicted_claim_still_reports_an_analyzer_assessed_basis():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _contradiction(claim, "core/session_store.py")

    assessment = _assess(claim, _set(claim, record))

    assert assessment.assessment_status == STATUS_CONTRADICTED
    assert assessment.semantic_basis == LEVEL_ANALYZER_ASSESSED


def test_w_many_agreeing_supports_stay_analyzer_assessed():
    """B45: aggregation cannot upgrade semantic epistemic level."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    records = [
        _support(claim, f"core/store_{index}.py", marker=f"v{index}")[0]
        for index in range(20)
    ]
    evidence_set = _set(claim, *records)
    assert len(evidence_set.support_records) == 20

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_SUPPORTED
    assert assessment.semantic_basis == BASIS_ANALYZER_ASSESSED
    assert assessment.assessment_basis == ASSESSMENT_BASIS_GATED_ANALYZER_ASSESSMENTS
    _assert_no_truth_claim_and_no_number(assessment)


def test_x_an_assessment_cannot_be_built_claiming_deterministic_semantics():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    assessment = _assess(claim, _set(claim, record))

    with pytest.raises(ValueError, match="never deterministically verified"):
        dataclasses.replace(
            assessment, semantic_basis=LEVEL_DETERMINISTICALLY_VERIFIED
        )


def test_historical_material_is_not_upgraded_by_quantity():
    """B24: ten rejected proposals do not implement anything."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    records = [
        _verify(
            f"docs/history/rejected_{index}.md",
            HISTORICAL_NOTE + f"\n<!-- {index} -->\n".encode("utf-8"),
            (ROLE_HISTORICAL_CONTEXT,),
            (SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,),
            claim,
            analyzer=_analyzer(supporting_markers=(b"sqlite3.connect",)),
        )[0]
        for index in range(10)
    ]
    evidence_set = _set(claim, *records)
    assert evidence_set.support_records == ()

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_INSUFFICIENT


def test_a_claim_relation_is_never_reinterpreted_by_the_claim_phase():
    """What EVIDENCE.1 called insufficient stays insufficient in every field."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _insufficient(claim, "core/session_store.py")
    evidence_set = _set(claim, record)

    assessment = _assess(claim, evidence_set)

    assert assessment.directional_record_refs == ()
    assert assessment.non_directional_record_refs == evidence_set.insufficient_records
    payload = assessment.as_dict()
    assert payload["evidence_relations_reinterpreted"] is False
    assert payload["guardrails"]["relations_reinterpreted"] is False


# =============================================================================
# 8. The hard entry gate
# =============================================================================

def test_an_inconsistent_evidence_set_is_refused_and_not_repaired():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    other = _proposition("Something else entirely.", identifier="P-2")
    record, _, _ = _support(other, "core/session_store.py")
    broken = _set(claim, record)
    assert broken.set_status == SET_INCONSISTENT_INPUT

    assessment = _assess(claim, broken)

    assert assessment.assessment_status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_EVIDENCE_SET in assessment.inconsistencies
    assert CLAIM_INPUT_REJECTED in assessment.reasons
    assert assessment.semantic_basis == BASIS_NOT_ESTABLISHED
    assert assessment.assessment_basis == ASSESSMENT_BASIS_NOT_ASSESSED
    assert assessment.corroboration_status == CORROBORATION_NOT_ASSESSED
    assert assessment.claim_assessment_authority is False


def test_a_proposition_whose_wording_drifted_is_refused():
    """B4: narrowing, broadening or requalifying a claim makes a new claim."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    evidence_set = _set(claim, record)
    requalified = _proposition(
        _SQLITE_CLAIM_TEXT + " (in most configurations)",
    )
    assert requalified.proposition_sha256 != claim.proposition_sha256

    assessment = _assess(requalified, evidence_set)

    assert assessment.assessment_status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_PROPOSITION_BINDING in assessment.inconsistencies


def test_a_mismatched_expected_set_fingerprint_is_refused():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    evidence_set = _set(claim, record)

    assessment = _assess(
        claim,
        evidence_set,
        expected_evidence_set_fingerprint=_digest("a different set"),
    )

    assert assessment.assessment_status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_SET_FINGERPRINT in assessment.inconsistencies
    matching = _assess(
        claim,
        evidence_set,
        expected_evidence_set_fingerprint=evidence_set.assessment_fingerprint,
    )
    assert matching.assessment_status == STATUS_SUPPORTED


def test_a_relation_summary_that_disagrees_with_its_members_is_refused():
    """The partition is recomputed from the records, never read off the summary."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    supporting, _, _ = _support(claim, "core/session_store.py")
    insufficient, _, _ = _insufficient(claim, "core/other_store.py")
    evidence_set = _set(claim, supporting, insufficient)
    swapped = dataclasses.replace(
        evidence_set,
        support_records=evidence_set.insufficient_records,
        insufficient_records=evidence_set.support_records,
    )

    assessment = _assess(claim, swapped)

    assert assessment.assessment_status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_RELATION_PARTITION in assessment.inconsistencies


def test_a_set_whose_members_do_not_match_its_lineage_groups_is_refused():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    first, _, _ = _support(claim, "core/session_store.py", marker="a")
    second, _, _ = _support(claim, "core/other_store.py", marker="b")
    mine = _set(claim, first)
    theirs = _set(claim, second)
    grafted = dataclasses.replace(mine, independence=theirs.independence)

    assessment = _assess(claim, grafted)

    assert assessment.assessment_status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_LINEAGE_MEMBERSHIP in assessment.inconsistencies


class _OversteppingSet(EvidenceSetAssessment):
    """An upstream that claims claim-decision authority it does not have."""

    def as_dict(self):  # noqa: D102 - behaviour is the whole point
        payload = super().as_dict()
        payload["claim_decision_authority"] = True
        return payload


class _InterpretingSet(EvidenceSetAssessment):
    """An upstream that admits it called a model on the way."""

    def as_dict(self):  # noqa: D102
        payload = super().as_dict()
        payload["guardrails"] = dict(payload["guardrails"])
        payload["guardrails"]["model_called"] = True
        return payload


def _retyped(assessment: EvidenceSetAssessment, kind: type) -> EvidenceSetAssessment:
    values = {
        field.name: getattr(assessment, field.name)
        for field in dataclasses.fields(assessment)
    }
    return kind(**values)


def test_an_upstream_that_already_decided_the_claim_is_refused():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    overstepping = _retyped(_set(claim, record), _OversteppingSet)

    assessment = _assess(claim, overstepping)

    assert assessment.assessment_status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_UPSTREAM_CLAIM_AUTHORITY in assessment.inconsistencies


def test_an_upstream_that_interpreted_its_records_is_refused():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    interpreting = _retyped(_set(claim, record), _InterpretingSet)

    assessment = _assess(claim, interpreting)

    assert assessment.assessment_status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_UPSTREAM_GUARDRAIL in assessment.inconsistencies


def test_requirements_bound_to_another_proposition_are_refused():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    other = _proposition("Something else entirely.", identifier="P-2")
    record, _, _ = _support(claim, "core/session_store.py")

    assessment = _assess(
        claim, _set(claim, record), requirements=_claim_requirements(other)
    )

    assert assessment.assessment_status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_REQUIREMENT_BINDING in assessment.inconsistencies


def test_requirements_naming_roles_the_set_never_assessed_are_refused():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    evidence_set = _set(claim, record)

    assessment = _assess(
        claim,
        evidence_set,
        requirements=_claim_requirements(claim, (ROLE_IMPLEMENTATION_AUTHORITY,)),
    )

    assert assessment.assessment_status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_REQUIREMENT_BINDING in assessment.inconsistencies


def test_requirements_matching_the_sets_own_roles_are_accepted():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    evidence_set = _set(
        claim,
        record,
        requirements=_set_requirements(claim, (ROLE_IMPLEMENTATION_AUTHORITY,)),
    )

    assessment = _assess(
        claim,
        evidence_set,
        requirements=_claim_requirements(claim, (ROLE_IMPLEMENTATION_AUTHORITY,)),
    )

    assert assessment.assessment_status == STATUS_SUPPORTED


def test_assess_claim_refuses_anything_that_is_not_a_request():
    with pytest.raises(TypeError, match="ClaimAssessmentRequest"):
        assess_claim({"proposition": "anything"})  # type: ignore[arg-type]


def test_a_request_refuses_a_raw_evidence_record():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    with pytest.raises(TypeError, match="EvidenceSetAssessment"):
        ClaimAssessmentRequest(proposition=claim, evidence_set=record)  # type: ignore[arg-type]


# =============================================================================
# 9. The DeepSeek dogfood sets
# =============================================================================

def test_deepseek_set_a_unrelated_and_insufficient_sources_support_nothing():
    claim = _negative_claim()
    records = [
        _insufficient(claim, f"core/module_{index}.py")[0] for index in range(3)
    ]
    records.append(_unrelated(claim, "web/static/panel.css")[0])

    assessment = _assess(claim, _set(claim, *records))

    assert assessment.assessment_status == STATUS_INSUFFICIENT
    assert assessment.assessment_status != STATUS_SUPPORTED
    assert MISSING_NEGATIVE_CLAIM_COVERAGE in assessment.missing_requirements
    _assert_no_truth_claim_and_no_number(assessment)


def test_deepseek_set_b_duplicated_absence_documents_support_nothing():
    """Four copies of one guess are one lineage, and one lineage of guesses."""
    claim = _negative_claim()
    duplicates = [
        _verify(
            f"docs/notes/no_persistence_{index}.md",
            NO_PERSISTENCE_DOC,
            (ROLE_ARCHITECTURE_DESCRIPTION,),
            (SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,),
            claim,
            analyzer=_analyzer(supporting_markers=(b"no session persistence",)),
        )[0]
        for index in range(4)
    ]
    evidence_set = _set(claim, *duplicates)
    assert evidence_set.independence is not None
    assert evidence_set.independence.lineage_group_count == 1

    assessment = _assess(claim, evidence_set)

    assert assessment.assessment_status == STATUS_INSUFFICIENT
    assert assessment.assessment_status != STATUS_SUPPORTED
    assert MISSING_NEGATIVE_CLAIM_COVERAGE in assessment.missing_requirements


def test_deepseek_set_c_the_sqlite_counterexample_contradicts_the_absence():
    claim = _negative_claim()
    records = [
        _insufficient(claim, f"core/module_{index}.py")[0] for index in range(3)
    ]
    counterexample, _, _ = _contradiction(claim, "core/session_store.py")

    assessment = _assess(claim, _set(claim, *records, counterexample))

    assert assessment.assessment_status == STATUS_CONTRADICTED
    assert assessment.negative_claim_coverage == COVERAGE_INCOMPLETE
    _assert_no_truth_claim_and_no_number(assessment)


def test_deepseek_set_d_coverage_backed_support_and_the_counterexample_conflict():
    claim = _negative_claim()
    supporting, _, coverage = _covered_absence_support(claim, "core/session_store.py")
    counterexample, _, _ = _contradiction(claim, "core/legacy_store.py", marker="legacy")

    assessment = _assess(
        claim,
        _set(claim, supporting, counterexample, coverage_receipts=(coverage,)),
    )

    assert assessment.assessment_status == STATUS_CONFLICTING
    assert MISSING_CONFLICT_ADJUDICATION in assessment.missing_requirements
    assert assessment.final_claim_authority is False
    _assert_no_truth_claim_and_no_number(assessment)


def test_deepseek_duplicated_documents_never_outvote_the_counterexample():
    claim = _negative_claim()
    duplicates = [
        _verify(
            f"docs/notes/no_persistence_{index}.md",
            NO_PERSISTENCE_DOC,
            (ROLE_ARCHITECTURE_DESCRIPTION,),
            (SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,),
            claim,
            analyzer=_analyzer(supporting_markers=(b"no session persistence",)),
        )[0]
        for index in range(4)
    ]
    counterexample, _, _ = _contradiction(claim, "core/session_store.py")

    assessment = _assess(claim, _set(claim, *duplicates, counterexample))

    assert assessment.assessment_status == STATUS_CONTRADICTED


# =============================================================================
# 10. Determinism, binding, authority, guardrails
# =============================================================================

def test_the_same_evidence_set_yields_the_same_claim_assessment():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    first, _, _ = _support(claim, "core/a.py", marker="a")
    second, _, _ = _support(claim, "core/b.py", marker="b")
    third, _, _ = _insufficient(claim, "core/c.py")

    forward = _assess(claim, _set(claim, first, second, third))
    shuffled = _assess(claim, _set(claim, third, first, second))

    assert forward.assessment_fingerprint == shuffled.assessment_fingerprint
    assert render_claim_assessment_json(forward) == render_claim_assessment_json(
        shuffled
    )


def test_repeated_assessment_of_one_set_is_byte_identical():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    evidence_set = _set(claim, record)

    assert (
        _assess(claim, evidence_set).assessment_fingerprint
        == _assess(claim, evidence_set).assessment_fingerprint
    )


def test_the_assessment_binds_the_evidence_set_it_was_made_over():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    other, _, _ = _support(claim, "core/other_store.py", marker="b")
    narrow = _set(claim, record)
    wide = _set(claim, record, other)

    assert _assess(claim, narrow).evidence_set_fingerprint == (
        narrow.assessment_fingerprint
    )
    assert _assess(claim, narrow).assessment_fingerprint != (
        _assess(claim, wide).assessment_fingerprint
    )


def test_supplied_requirements_change_the_assessment_identity():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    evidence_set = _set(claim, record)

    plain = _assess(claim, evidence_set)
    demanded = _assess(
        claim,
        evidence_set,
        requirements=_claim_requirements(
            claim, independent_corroboration_required=True
        ),
    )

    assert plain.request_fingerprint != demanded.request_fingerprint
    assert claim_request_fingerprint(
        ClaimAssessmentRequest(proposition=claim, evidence_set=evidence_set)
    ) == plain.request_fingerprint


def test_the_proposition_is_preserved_exactly():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")

    assessment = _assess(claim, _set(claim, record))

    assert assessment.proposition_id == claim.proposition_id
    assert assessment.proposition_sha256 == claim.proposition_sha256
    assert assessment.proposition_text == claim.text
    assert assessment.proposition_type == claim.proposition_type
    assert assessment.proposition_scope == claim.scope


def test_no_source_identifier_or_content_reaches_the_assessment():
    """B29: evidence is referenced by fingerprint, never copied."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    evidence_set = _set(claim, record)

    text = render_claim_assessment_json(_assess(claim, evidence_set))

    assert "core/session_store.py" not in text
    assert "sqlite3.connect" not in text
    for member in evidence_set.members:
        assert member.source_identifier not in text
        assert member.source_content_sha256 not in text


def test_the_authority_boundary_is_narrow_and_final_claim_is_always_false():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    assessment = _assess(claim, _set(claim, record))

    authority = assessment.as_dict()["authority"]
    assert authority["claim_assessment_authority"] is True
    assert authority["human_approval_required"] is True
    for name, value in authority.items():
        if name in {"claim_assessment_authority", "human_approval_required"}:
            continue
        assert value is False, name


def test_a_refused_set_carries_no_claim_assessment_authority():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    other = _proposition("Something else entirely.", identifier="P-2")
    record, _, _ = _support(other, "core/session_store.py")

    assessment = _assess(claim, _set(claim, record))

    authority = assessment.as_dict()["authority"]
    assert authority["claim_assessment_authority"] is False
    assert authority["human_approval_required"] is True


def test_the_guardrails_are_honest_about_what_was_and_was_not_done():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    guardrails = _assess(claim, _set(claim, record)).as_dict()["guardrails"]

    for performed in (
        "evidence_set_consumed",
        "claim_policy_applied",
        "conflict_assessed",
        "coverage_gates_applied",
    ):
        assert guardrails[performed] is True, performed
    for refused in (
        "evidence_records_reinterpreted",
        "relations_reinterpreted",
        "evidence_spans_reinterpreted",
        "source_roles_reinterpreted",
        "proposition_rewritten",
        "semantic_status_upgraded",
        "source_content_read",
        "evidence_acquired",
        "repository_traversed",
        "repository_files_read",
        "network_called",
        "index_consulted",
        "graph_consulted",
        "validation_executed",
        "repository_written",
        "patch_created",
        "model_called",
        "majority_vote_computed",
        "confidence_computed",
        "evidence_weighted",
        "conflict_resolved",
        "objective_truth_determined",
        "final_claim_emitted",
        "final_response_synthesized",
        "multiple_propositions_combined",
        "coverage_receipts_minted",
        "current_state_receipts_minted",
        "independence_inferred",
    ):
        assert guardrails[refused] is False, refused


def test_no_serialized_assessment_carries_a_truth_claim_or_a_number():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    supporting, _, _ = _support(claim, "core/session_store.py")
    contradicting, _, _ = _contradiction(claim, "core/legacy_store.py", marker="legacy")

    for evidence_set in (
        _set(claim, supporting),
        _set(claim, contradicting),
        _set(claim, supporting, contradicting),
    ):
        assessment = _assess(claim, evidence_set)
        _assert_no_truth_claim_and_no_number(assessment)
        payload = assessment.as_dict()
        assert payload["final_claim_authority"] is False
        assert payload["objective_truth_asserted"] is False
        assert payload["response_synthesis_performed"] is False
        assert payload["semantic_relations_proved_deterministically"] is False
        assert payload["proposition_rewritten"] is False
        assert payload["source_content_read"] is False


def test_the_supported_status_never_serializes_as_a_proven_proposition():
    """B45, the primary acceptance criterion, stated as one assertion."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    records = [
        _support(claim, f"core/store_{index}.py", marker=f"v{index}")[0]
        for index in range(10)
    ]

    assessment = _assess(claim, _set(claim, *records))
    text = render_claim_assessment_json(assessment)

    assert assessment.assessment_status == STATUS_SUPPORTED
    assert '"semantic_basis": "analyzer_assessed"' in text
    assert '"semantic_basis": "deterministically_verified"' not in text
    assert "proposition_true" not in text
    # Every occurrence of "final_claim" anywhere in the page is a denial.
    assert '"final_claim_authority": false' in text
    assert '"final_claim_emitted": false' in text
    assert '"final_claim":' not in text
    denials = text.count('"final_claim_authority": false') + text.count(
        '"final_claim_emitted": false'
    )
    assert text.count("final_claim") == denials


def test_a_claim_assessment_cannot_be_built_asserting_final_claim_authority():
    """No construction path can flip it, because there is no field to flip."""
    field_names = {item.name for item in dataclasses.fields(ClaimAssessment)}
    assert "final_claim_authority" not in field_names
    assert "objective_truth_asserted" not in field_names
    assert "claim_assessment_authority" not in field_names
    assert isinstance(ClaimAssessment.final_claim_authority, property)
    assert isinstance(ClaimAssessment.objective_truth_asserted, property)


def test_an_assessed_claim_may_not_declare_an_unassessed_basis():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    assessment = _assess(claim, _set(claim, record))

    with pytest.raises(ValueError, match="analyzer-assessed"):
        dataclasses.replace(assessment, semantic_basis=BASIS_NOT_ESTABLISHED)


def test_the_reason_and_gap_vocabularies_stay_bounded():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    assessment = _assess(claim, _set(claim, record))

    for honest in (
        CLAIM_NO_MAJORITY_COMPUTED,
        CLAIM_NO_CONFIDENCE_COMPUTED,
        CLAIM_NO_OBJECTIVE_TRUTH_DETERMINED,
        CLAIM_NO_FINAL_RESPONSE_SYNTHESIZED,
    ):
        assert honest in assessment.reasons, honest
    assert CLAIM_INSUFFICIENT_DIRECTIONAL_EVIDENCE not in assessment.reasons
