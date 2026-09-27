"""EVIDENCE.2 — evidence set coverage, conflict and independence.

The matrix is organised the way the phase reasons:

1.  basic sets — what one relation, and then two, produce
2.  conflict, and the absence of a winner
3.  duplication and independence
4.  role coverage, which is a different axis from direction
5.  negative existential coverage across a set
6.  current-state coverage across a set
7.  historical, validation and manifest material, preserved as EVIDENCE.1 left it
8.  the DeepSeek dogfood set, end to end
9.  tamper binding, determinism and ordering
10. authority, guardrails and the things this phase never emits

Every record in this file is produced by the real EVIDENCE.1 gate rather than
hand-built, so the set contract is exercised against records that actually
cleared promotion.  Every test runs offline: no model, no network, no
repository read.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

from core.acquisition_request import (
    SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,
    SOURCE_CLASS_DEPENDENCY_MANIFEST,
    SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,
    SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
    SOURCE_CLASS_VALIDATION_TEST,
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
    CONFLICT_NOT_ASSESSED,
    CONFLICT_NO_DIRECTIONAL_EVIDENCE,
    CONFLICT_STATUSES,
    CONFLICT_SUPPORT_ONLY,
    COVERAGE_COMPLETE,
    COVERAGE_INCOMPLETE,
    COVERAGE_INCONSISTENT,
    COVERAGE_NOT_APPLICABLE,
    INCONSISTENT_COVERAGE_RECEIPT_BINDING,
    INCONSISTENT_COVERAGE_RECEIPT_UNSUPPLIED,
    INCONSISTENT_CURRENT_STATE_RECEIPT_BINDING,
    INCONSISTENT_LINEAGE_BINDING,
    INCONSISTENT_MIXED_PROPOSITION,
    INCONSISTENT_NEGATIVE_SUPPORT_UNCOVERED,
    INCONSISTENT_RECORD_IDENTITY_REPEATED,
    INCONSISTENT_RECORD_NOT_ADMISSIBLE,
    INCONSISTENT_REQUIREMENTS_BINDING,
    INCONSISTENT_SOURCE_CONTENT_CONFLICT,
    INDEPENDENCE_DUPLICATE,
    INDEPENDENCE_INDEPENDENT,
    INDEPENDENCE_STATES,
    INDEPENDENCE_UNKNOWN,
    LINEAGE_BASIS_DECLARED_DISTINCT_ORIGIN,
    LINEAGE_BASIS_DECLARED_RESTATEMENT,
    LINEAGE_BASIS_IDENTICAL_CONTENT,
    LINEAGE_BASIS_NO_LINEAGE_METADATA,
    LINEAGE_DISTINCT_ORIGIN,
    LINEAGE_RESTATES,
    MISSING_CURRENT_STATE_COVERAGE,
    MISSING_DIRECTIONAL_EVIDENCE,
    MISSING_INDEPENDENT_CORROBORATION,
    MISSING_NEGATIVE_CLAIM_COVERAGE,
    MISSING_REQUIRED_ROLE,
    MISSING_ROLE_REQUIREMENTS_NOT_SUPPLIED,
    NON_CONFLICTING_STATUSES,
    SET_ASSESSED,
    SET_INCONSISTENT_INPUT,
    EvidenceSetAssessment,
    EvidenceSetRequest,
    EvidenceSetRequirements,
    SourceLineageDeclaration,
    assess_evidence_set,
    evidence_record_fingerprint,
    evidence_set_request_fingerprint,
    render_evidence_set_assessment_json,
    requirements_fingerprint,
)
from core.evidence_verification import (
    CONSTRAINT_CURRENT_STATE_RECEIPT_REQUIRED,
    CONSTRAINT_NEGATIVE_COVERAGE_REQUIRED,
    CONSTRAINT_ROLE_VERIFICATION_REQUIRED,
    COVERAGE_ALL_ELIGIBLE_CANDIDATES_ACQUIRED,
    COVERAGE_ALL_REQUIRED_ROLES_ACQUIRED,
    COVERAGE_INSUFFICIENT,
    COVERAGE_NOT_SUPPLIED,
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
    SCOPE_CONFIGURATION_DECLARATION,
    SCOPE_IMPLEMENTATION_STATE,
    SCOPE_RUNTIME_BEHAVIOUR,
    SCOPE_VALIDATION_EXPECTATION,
    SCOPES_REQUIRING_CURRENT_STATE,
    STATUS_CONTRADICTED,
    STATUS_COVERAGE_REQUIRED,
    STATUS_INSUFFICIENT,
    STATUS_UNRELATED,
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
    binding: SourceBinding | None = None,
) -> tuple[AcquiredSourcePayload, SourceAcquisitionReceipt]:
    bound = binding or _binding(identifier)
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
    candidate_pool_fingerprint: str | None = None,
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
        candidate_pool_fingerprint=(
            candidate_pool_fingerprint
            or first.source_binding.candidate_receipt_fingerprint
        ),
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

DEPENDENCY_MANIFEST = b'''[project]
name = "deepseek-harness"
dependencies = [
    "sqlite-utils==3.35",
]
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
    """Run the real EVIDENCE.1 gate and hand back its result plus its receipt."""
    payload, receipt = _acquire(identifier, content, roles, classes, domain=domain)
    current_state = (
        None
        if current_state_established is None
        else _current_state(claim, receipt, established=current_state_established)
    )
    request = _request(receipt, claim, coverage=coverage, current_state=current_state)
    result = verify_acquired_source(
        request, payload, receipt, analyzer or _analyzer()
    )
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


def _set(claim: Proposition, *records, **kwargs) -> EvidenceSetAssessment:
    return assess_evidence_set(
        EvidenceSetRequest(proposition=claim, records=tuple(records), **kwargs)
    )


_SQLITE_CLAIM_TEXT = "SessionStore writes session state to SQLite."
_NO_PERSISTENCE = "DeepSeek Harness has no session persistence."


#: Field names that would turn a description into a verdict.  Checked as exact
#: keys rather than substrings, because the honest negations —
#: ``no_majority_computed``, ``confidence_computed: false`` — legitimately
#: contain the same words.
_FORBIDDEN_KEYS = frozenset(
    {
        "claim_true",
        "claim_false",
        "claim_verified",
        "claim_proven",
        "conclusion",
        "confidence",
        "final_relation",
        "likelihood",
        "probability",
        "proposition_true",
        "proposition_verified_true",
        "recommendation",
        "score",
        "semantic_truth_verified",
        "semantically_verified",
        "support_score",
        "truth_status",
        "verdict",
        "winning_relation",
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


def _assert_no_verdict_and_no_number(assessment: EvidenceSetAssessment) -> None:
    """No field names a verdict, and no value is a number that could be one."""
    payload = json.loads(render_evidence_set_assessment_json(assessment))
    for key in _keys(payload):
        assert key not in _FORBIDDEN_KEYS, key
    for value in _values(payload):
        assert not isinstance(value, float), value


# =============================================================================
# 1. Basic sets
# =============================================================================

def test_a_one_support_record_is_recorded_and_decides_nothing():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    assert record.status == STATUS_VERIFIED

    assessment = _set(claim, record)

    assert assessment.set_status == SET_ASSESSED
    assert len(assessment.support_records) == 1
    assert assessment.contradiction_records == ()
    assert assessment.conflict_status == CONFLICT_SUPPORT_ONLY
    assert assessment.claim_decision_authority is False
    assert assessment.final_claim_authority is False
    assert not hasattr(assessment, "claim_true")
    assert not hasattr(assessment, "truth_status")


def test_b_one_contradiction_record_is_recorded_and_decides_nothing():
    claim = _proposition("SessionStore keeps session state only in memory.")
    record, _, _ = _contradiction(claim, "core/session_store.py")
    assert record.status == STATUS_CONTRADICTED

    assessment = _set(claim, record)

    assert len(assessment.contradiction_records) == 1
    assert assessment.support_records == ()
    assert assessment.conflict_status == CONFLICT_CONTRADICTION_ONLY
    assert assessment.conflict_status in NON_CONFLICTING_STATUSES
    assert assessment.claim_decision_authority is False


def test_c_one_insufficient_record_is_recorded_as_insufficient():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _insufficient(claim, "core/session_store.py")
    assert record.status == STATUS_INSUFFICIENT

    assessment = _set(claim, record)

    assert len(assessment.insufficient_records) == 1
    assert assessment.support_records == ()
    assert assessment.conflict_status == CONFLICT_NO_DIRECTIONAL_EVIDENCE
    assert MISSING_DIRECTIONAL_EVIDENCE in assessment.missing_requirements


def test_d_one_unrelated_record_is_recorded_as_unrelated():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _unrelated(claim, "web/static/panel.css")
    assert record.status == STATUS_UNRELATED

    assessment = _set(claim, record)

    assert len(assessment.unrelated_records) == 1
    assert assessment.conflict_status == CONFLICT_NO_DIRECTIONAL_EVIDENCE


def test_e_support_plus_contradiction_is_a_conflict():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    supporting, _, _ = _support(claim, "core/session_store.py")
    contradicting, _, _ = _contradiction(claim, "core/legacy_store.py", marker="legacy")

    assessment = _set(claim, supporting, contradicting)

    assert assessment.conflict_status == CONFLICT_CONFLICTING
    assert assessment.conflicting is True
    assert len(assessment.support_records) == 1
    assert len(assessment.contradiction_records) == 1


def test_f_five_supports_and_one_contradiction_is_still_a_conflict():
    """No majority. Counting files is not weighing evidence."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    supports = [
        _support(claim, f"core/session_store_{index}.py", marker=f"v{index}")[0]
        for index in range(5)
    ]
    contradicting, _, _ = _contradiction(claim, "core/legacy_store.py", marker="legacy")

    assessment = _set(claim, *supports, contradicting)

    assert len(assessment.support_records) == 5
    assert len(assessment.contradiction_records) == 1
    assert assessment.conflict_status == CONFLICT_CONFLICTING
    assert assessment.conflict_status not in NON_CONFLICTING_STATUSES

    _assert_no_verdict_and_no_number(assessment)
    payload = json.loads(render_evidence_set_assessment_json(assessment))
    assert payload["guardrails"]["majority_vote_computed"] is False
    assert payload["guardrails"]["confidence_computed"] is False


def test_the_conflict_vocabulary_stays_small_and_states_no_truth():
    assert set(CONFLICT_STATUSES) == {
        CONFLICT_NO_DIRECTIONAL_EVIDENCE,
        CONFLICT_SUPPORT_ONLY,
        CONFLICT_CONTRADICTION_ONLY,
        CONFLICT_CONFLICTING,
        CONFLICT_NOT_ASSESSED,
    }
    assert CONFLICT_CONFLICTING not in NON_CONFLICTING_STATUSES
    for status in CONFLICT_STATUSES:
        assert "true" not in status and "false" not in status


# =============================================================================
# 2. One proposition only
# =============================================================================

def test_a_set_may_not_mix_two_propositions():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    other = _proposition("SessionStore writes session state to Postgres.")
    first, _, _ = _support(claim, "core/session_store.py")
    second, _, _ = _support(other, "core/other_store.py", marker="other")

    assessment = _set(claim, first, second)

    assert assessment.set_status == SET_INCONSISTENT_INPUT
    assert INCONSISTENT_MIXED_PROPOSITION in assessment.inconsistencies
    assert assessment.conflict_status == CONFLICT_NOT_ASSESSED
    assert assessment.members == ()


def test_a_rescoped_proposition_is_a_different_proposition():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    rescoped = _proposition(_SQLITE_CLAIM_TEXT, scope=SCOPE_CONFIGURATION_DECLARATION)
    record, _, _ = _support(claim, "core/session_store.py")

    assessment = assess_evidence_set(
        EvidenceSetRequest(proposition=rescoped, records=(record,))
    )

    assert assessment.set_status == SET_INCONSISTENT_INPUT
    assert INCONSISTENT_MIXED_PROPOSITION in assessment.inconsistencies


# =============================================================================
# 3. Duplication and independence
# =============================================================================

def test_g_the_same_evidence_record_twice_is_rejected():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")

    assessment = _set(claim, record, record)

    assert assessment.set_status == SET_INCONSISTENT_INPUT
    assert INCONSISTENT_RECORD_IDENTITY_REPEATED in assessment.inconsistencies


def test_h_two_identifiers_with_identical_content_are_one_lineage():
    """README.md and README-copy.md are one reading, whatever the paths say."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    first, _, _ = _support(claim, "docs/README.md")
    second, _, _ = _support(claim, "docs/README-copy.md")
    assert first.source_content_sha256 == second.source_content_sha256

    assessment = _set(claim, first, second)

    assert assessment.set_status == SET_ASSESSED
    assert len(assessment.support_records) == 2
    independence = assessment.independence
    assert independence is not None
    assert independence.record_count == 2
    assert independence.lineage_group_count == 1
    assert independence.duplicate_group_count == 1
    assert independence.exact_duplicates_present is True
    group = independence.lineage_groups[0]
    assert group.independence_state == INDEPENDENCE_DUPLICATE
    assert LINEAGE_BASIS_IDENTICAL_CONTENT in group.basis
    assert all(
        member.independence_state == INDEPENDENCE_DUPLICATE
        for member in assessment.members
    )


def test_i_different_hashes_with_no_lineage_metadata_are_independence_unknown():
    """A different path and a different digest prove nothing about origin."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    first, _, _ = _support(claim, "core/session_store.py", marker="a")
    second, _, _ = _support(claim, "core/other_store.py", marker="b")
    assert first.source_content_sha256 != second.source_content_sha256

    assessment = _set(claim, first, second)

    independence = assessment.independence
    assert independence is not None
    assert independence.lineage_group_count == 2
    assert independence.independent_group_count == 0
    assert independence.unknown_independence_group_count == 2
    for group in independence.lineage_groups:
        assert group.independence_state == INDEPENDENCE_UNKNOWN
        assert group.basis == (LINEAGE_BASIS_NO_LINEAGE_METADATA,)
    assert MISSING_INDEPENDENT_CORROBORATION in assessment.missing_requirements


def test_j_a_supplied_restatement_declaration_collapses_two_lineages():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    first, _, _ = _support(claim, "docs/architecture.md", marker="original")
    second, _, _ = _support(claim, "docs/architecture.fr.md", marker="translated")
    assert first.source_content_sha256 != second.source_content_sha256

    declaration = SourceLineageDeclaration(
        proposition_id=claim.proposition_id,
        proposition_sha256=claim.proposition_sha256,
        source_identifier="docs/architecture.fr.md",
        source_content_sha256=second.source_content_sha256,
        related_source_identifier="docs/architecture.md",
        related_source_content_sha256=first.source_content_sha256,
        lineage_relation=LINEAGE_RESTATES,
    )

    assessment = _set(claim, first, second, lineage_declarations=(declaration,))

    independence = assessment.independence
    assert independence is not None
    assert independence.lineage_group_count == 1
    assert independence.duplicate_group_count == 1
    assert independence.exact_duplicates_present is False
    assert LINEAGE_BASIS_DECLARED_RESTATEMENT in independence.lineage_groups[0].basis


def test_k_independence_is_reachable_only_through_a_supplied_declaration():
    """Nothing EVIDENCE.2 computes can produce `independent`; a declarer can."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    first, _, _ = _support(claim, "core/session_store.py", marker="a")
    second, _, _ = _support(claim, "core/other_store.py", marker="b")

    without = _set(claim, first, second)
    assert without.independence is not None
    assert without.independence.independent_group_count == 0

    declaration = SourceLineageDeclaration(
        proposition_id=claim.proposition_id,
        proposition_sha256=claim.proposition_sha256,
        source_identifier="core/other_store.py",
        source_content_sha256=second.source_content_sha256,
        related_source_identifier="core/session_store.py",
        related_source_content_sha256=first.source_content_sha256,
        lineage_relation=LINEAGE_DISTINCT_ORIGIN,
    )
    with_declaration = _set(claim, first, second, lineage_declarations=(declaration,))

    independence = with_declaration.independence
    assert independence is not None
    assert independence.independent_group_count == 2
    for group in independence.lineage_groups:
        assert group.independence_state == INDEPENDENCE_INDEPENDENT
        assert group.basis == (LINEAGE_BASIS_DECLARED_DISTINCT_ORIGIN,)
    assert MISSING_INDEPENDENT_CORROBORATION not in (
        with_declaration.missing_requirements
    )


def test_a_lineage_declaration_about_a_source_outside_the_set_is_refused():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    declaration = SourceLineageDeclaration(
        proposition_id=claim.proposition_id,
        proposition_sha256=claim.proposition_sha256,
        source_identifier="core/absent.py",
        source_content_sha256=_digest("absent"),
        related_source_identifier="core/session_store.py",
        related_source_content_sha256=record.source_content_sha256,
        lineage_relation=LINEAGE_RESTATES,
    )

    assessment = _set(claim, record, lineage_declarations=(declaration,))

    assert assessment.set_status == SET_INCONSISTENT_INPUT
    assert INCONSISTENT_LINEAGE_BINDING in assessment.inconsistencies


def test_a_lineage_declaration_names_its_pair_in_canonical_order():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    with pytest.raises(ValueError, match="canonical order"):
        SourceLineageDeclaration(
            proposition_id=claim.proposition_id,
            proposition_sha256=claim.proposition_sha256,
            source_identifier="b.md",
            source_content_sha256=_digest("b"),
            related_source_identifier="a.md",
            related_source_content_sha256=_digest("a"),
            lineage_relation=LINEAGE_RESTATES,
        )


def test_the_independence_vocabulary_holds_no_score():
    assert set(INDEPENDENCE_STATES) == {
        INDEPENDENCE_DUPLICATE,
        INDEPENDENCE_INDEPENDENT,
        INDEPENDENCE_UNKNOWN,
    }


def test_two_records_of_one_source_are_one_lineage_and_two_records():
    """Two analyzer readings of one file corroborate nothing."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    first, _, _ = _support(claim, "core/session_store.py")
    second, _, _ = _verify(
        "core/session_store.py",
        _sqlite_implementation(),
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
        claim,
        analyzer=_analyzer(context_bytes=20),
    )
    assert first.analyzer_proposal_fingerprint != second.analyzer_proposal_fingerprint

    assessment = _set(claim, first, second)

    assert assessment.set_status == SET_ASSESSED
    assert len(assessment.support_records) == 2
    assert assessment.independence is not None
    assert assessment.independence.source_count == 1
    assert assessment.independence.lineage_group_count == 1


def test_one_identifier_with_two_different_digests_is_refused():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    first, _, _ = _support(claim, "core/session_store.py", marker="a")
    second, _, _ = _support(claim, "core/session_store.py", marker="b")

    assessment = _set(claim, first, second)

    assert assessment.set_status == SET_INCONSISTENT_INPUT
    assert INCONSISTENT_SOURCE_CONTENT_CONFLICT in assessment.inconsistencies


# =============================================================================
# 4. Role coverage
# =============================================================================

def _requirements(claim: Proposition, roles: tuple[str, ...]) -> EvidenceSetRequirements:
    return EvidenceSetRequirements(
        proposition_id=claim.proposition_id,
        proposition_sha256=claim.proposition_sha256,
        required_roles=roles,
        evidence_requirement_fingerprint=_digest("evidence-requirement"),
    )


def _role_entry(assessment: EvidenceSetAssessment, role: str):
    for entry in assessment.role_coverage:
        if entry.role == role:
            return entry
    return None


def test_l_a_verified_role_with_an_insufficient_relation_covers_the_role_only():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _insufficient(claim, "core/session_store.py")
    assert ROLE_IMPLEMENTATION_AUTHORITY in record.verified_roles
    assert record.relation == RELATION_INSUFFICIENT

    assessment = _set(
        claim,
        record,
        requirements=_requirements(claim, (ROLE_IMPLEMENTATION_AUTHORITY,)),
    )

    entry = _role_entry(assessment, ROLE_IMPLEMENTATION_AUTHORITY)
    assert entry is not None
    assert entry.present is True
    assert entry.directional_present is False
    assert assessment.role_coverage_status == COVERAGE_COMPLETE
    assert assessment.support_records == ()


def test_m_validation_support_and_implementation_insufficiency_cover_both_roles():
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

    assessment = _set(
        claim,
        validation,
        implementation,
        requirements=_requirements(
            claim,
            (ROLE_IMPLEMENTATION_AUTHORITY, ROLE_VALIDATION_EVIDENCE),
        ),
    )

    assert assessment.role_coverage_status == COVERAGE_COMPLETE
    validation_entry = _role_entry(assessment, ROLE_VALIDATION_EVIDENCE)
    implementation_entry = _role_entry(assessment, ROLE_IMPLEMENTATION_AUTHORITY)
    assert validation_entry is not None and implementation_entry is not None
    assert validation_entry.directional_present is True
    assert implementation_entry.present is True
    assert implementation_entry.directional_present is False
    assert len(assessment.support_records) == 1
    supporting = next(
        member
        for member in assessment.members
        if member.record_fingerprint in assessment.support_records
    )
    assert supporting.verified_roles == (ROLE_VALIDATION_EVIDENCE,)


def test_n_a_missing_required_role_leaves_coverage_incomplete():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")

    assessment = _set(
        claim,
        record,
        requirements=_requirements(
            claim,
            (ROLE_IMPLEMENTATION_AUTHORITY, ROLE_CONFIGURATION_AUTHORITY),
        ),
    )

    assert assessment.role_coverage_status == COVERAGE_INCOMPLETE
    assert MISSING_REQUIRED_ROLE in assessment.missing_requirements
    configuration = _role_entry(assessment, ROLE_CONFIGURATION_AUTHORITY)
    assert configuration is not None
    assert configuration.required is True
    assert configuration.present is False


def test_role_requirements_are_never_invented():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")

    assessment = _set(claim, record)

    assert assessment.role_coverage_status == COVERAGE_NOT_APPLICABLE
    assert MISSING_ROLE_REQUIREMENTS_NOT_SUPPLIED in assessment.missing_requirements


def test_requirements_bound_to_another_proposition_are_refused():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    other = _proposition("Something else entirely.")
    record, _, _ = _support(claim, "core/session_store.py")

    assessment = _set(
        claim,
        record,
        requirements=_requirements(other, (ROLE_IMPLEMENTATION_AUTHORITY,)),
    )

    assert assessment.set_status == SET_INCONSISTENT_INPUT
    assert INCONSISTENT_REQUIREMENTS_BINDING in assessment.inconsistencies


def test_an_unrelated_record_does_not_discharge_role_coverage():
    """A file was acquired and verified its role; it still says nothing here."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _unrelated(claim, "web/static/panel.css")
    assert record.relation == RELATION_UNRELATED

    assessment = _set(
        claim,
        record,
        requirements=_requirements(claim, (ROLE_IMPLEMENTATION_AUTHORITY,)),
    )

    entry = _role_entry(assessment, ROLE_IMPLEMENTATION_AUTHORITY)
    assert entry is not None
    assert entry.present is False
    assert assessment.role_coverage_status == COVERAGE_INCOMPLETE


# =============================================================================
# 5. Negative existential claims
# =============================================================================

def _negative_claim() -> Proposition:
    return _proposition(
        _NO_PERSISTENCE,
        proposition_type=PROPOSITION_NEGATIVE_EXISTENTIAL,
    )


def test_o_many_insufficient_sources_do_not_cover_an_absence():
    claim = _negative_claim()
    records = [
        _insufficient(claim, f"core/module_{index}.py")[0] for index in range(3)
    ]
    records.append(_unrelated(claim, "web/static/panel.css")[0])

    assessment = _set(claim, *records)

    assert assessment.negative_claim_coverage == COVERAGE_INCOMPLETE
    assert assessment.support_records == ()
    assert MISSING_NEGATIVE_CLAIM_COVERAGE in assessment.missing_requirements
    assert assessment.claim_decision_authority is False


def test_p_a_hand_built_uncovered_negative_support_is_refused():
    """EVIDENCE.1 would never emit this; a caller that fabricates it is rejected.

    The gate downgrades an uncovered ``supports`` on an absence to
    ``insufficient``, so the only way to hold one is to build it by hand.  This
    forges a genuinely promoted, genuinely covered record and then strips the
    coverage off it — exactly the shape a careless caller would assemble.
    """
    claim = _negative_claim()
    payload, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    coverage = _coverage(claim, (receipt,))
    covered = verify_acquired_source(
        _request(receipt, claim, coverage=coverage),
        payload,
        receipt,
        _analyzer(supporting_markers=(b"self._sessions = {}",)),
    )
    assert covered.status == STATUS_VERIFIED

    forged = dataclasses.replace(
        covered,
        coverage_status=COVERAGE_NOT_SUPPLIED,
        coverage_receipt_fingerprint=None,
        verified_evidence=dataclasses.replace(
            covered.verified_evidence,
            coverage_status=COVERAGE_NOT_SUPPLIED,
        ),
    )

    assessment = _set(claim, forged)

    assert assessment.set_status == SET_INCONSISTENT_INPUT
    assert INCONSISTENT_NEGATIVE_SUPPORT_UNCOVERED in assessment.inconsistencies


def test_a_covered_negative_support_whose_receipt_is_not_supplied_is_refused():
    """The set cannot check coverage it was not given, so it does not pretend to."""
    claim = _negative_claim()
    payload, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    coverage = _coverage(claim, (receipt,))
    covered = verify_acquired_source(
        _request(receipt, claim, coverage=coverage),
        payload,
        receipt,
        _analyzer(supporting_markers=(b"self._sessions = {}",)),
    )

    assessment = _set(claim, covered)

    assert assessment.set_status == SET_INCONSISTENT_INPUT
    assert INCONSISTENT_COVERAGE_RECEIPT_UNSUPPLIED in assessment.inconsistencies


def test_q_a_support_bound_to_sufficient_coverage_is_accepted_and_decides_nothing():
    claim = _negative_claim()
    payload, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
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
    assert result.status == STATUS_VERIFIED

    assessment = _set(claim, result, coverage_receipts=(coverage,))

    assert assessment.set_status == SET_ASSESSED
    assert len(assessment.support_records) == 1
    assert assessment.negative_claim_coverage == COVERAGE_COMPLETE
    assert assessment.conflict_status == CONFLICT_SUPPORT_ONLY
    assert assessment.claim_decision_authority is False
    assert MISSING_NEGATIVE_CLAIM_COVERAGE not in assessment.missing_requirements


def test_r_one_counterexample_contradicts_an_absence_with_no_coverage_at_all():
    claim = _negative_claim()
    contradicting, _, _ = _contradiction(claim, "core/session_store.py")
    assert contradicting.status == STATUS_CONTRADICTED

    assessment = _set(claim, contradicting)

    assert len(assessment.contradiction_records) == 1
    assert assessment.negative_claim_coverage == COVERAGE_INCOMPLETE
    assert assessment.conflict_status == CONFLICT_CONTRADICTION_ONLY
    assert assessment.claim_decision_authority is False


def test_s_covered_support_plus_a_counterexample_is_a_conflict_with_no_winner():
    claim = _negative_claim()
    payload, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    coverage = _coverage(claim, (receipt,))
    supporting = verify_acquired_source(
        _request(receipt, claim, coverage=coverage),
        payload,
        receipt,
        _analyzer(supporting_markers=(b"self._sessions = {}",)),
    )
    contradicting, _, _ = _contradiction(claim, "core/legacy_store.py", marker="legacy")

    assessment = _set(claim, supporting, contradicting, coverage_receipts=(coverage,))

    assert assessment.conflict_status == CONFLICT_CONFLICTING
    assert assessment.negative_claim_coverage == COVERAGE_COMPLETE
    assert len(assessment.support_records) == 1
    assert len(assessment.contradiction_records) == 1
    assert assessment.claim_decision_authority is False


def test_incompatible_coverage_receipts_are_never_merged_into_complete_coverage():
    claim = _negative_claim()
    first, receipt_one, _ = _insufficient(claim, "core/module_one.py")
    second, receipt_two, _ = _verify(
        "core/module_two.py",
        MEMORY_IMPLEMENTATION + b"\n# second\n",
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
        claim,
    )
    wide = _coverage(claim, (receipt_one,))
    narrow = _coverage(
        claim,
        (receipt_two,),
        acquisition_request_fingerprint=_digest("another-acquisition-request"),
    )

    assessment = _set(claim, first, second, coverage_receipts=(wide, narrow))

    assert assessment.negative_claim_coverage == COVERAGE_INCONSISTENT
    assert MISSING_NEGATIVE_CLAIM_COVERAGE in assessment.missing_requirements


def test_an_insufficient_coverage_receipt_does_not_complete_coverage():
    claim = _negative_claim()
    record, receipt, _ = _insufficient(claim, "core/session_store.py")
    partial = _coverage(claim, (receipt,), status=COVERAGE_INSUFFICIENT)

    assessment = _set(claim, record, coverage_receipts=(partial,))

    assert assessment.negative_claim_coverage == COVERAGE_INCOMPLETE


def test_a_coverage_receipt_supplied_for_a_positive_claim_is_refused():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, receipt, _ = _support(claim, "core/session_store.py")
    coverage = _coverage(claim, (receipt,))

    assessment = _set(claim, record, coverage_receipts=(coverage,))

    assert assessment.set_status == SET_INCONSISTENT_INPUT
    assert INCONSISTENT_COVERAGE_RECEIPT_BINDING in assessment.inconsistencies


def test_negative_coverage_is_not_applicable_to_a_positive_claim():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")

    assessment = _set(claim, record)

    assert assessment.negative_claim_coverage == COVERAGE_NOT_APPLICABLE


# =============================================================================
# 6. Current-state coverage
# =============================================================================

def _runtime_claim() -> Proposition:
    return _proposition(
        "Session state survives a process restart at runtime.",
        scope=SCOPE_RUNTIME_BEHAVIOUR,
    )


def test_t_records_without_current_state_receipts_leave_coverage_incomplete():
    claim = _runtime_claim()
    record, _, _ = _support(claim, "core/session_store.py")
    assert record.status == STATUS_INSUFFICIENT
    assert record.current_state_fingerprint is None

    assessment = _set(claim, record)

    assert assessment.current_state_coverage == COVERAGE_INCOMPLETE
    assert MISSING_CURRENT_STATE_COVERAGE in assessment.missing_requirements


def test_u_compatible_established_receipts_complete_current_state_coverage():
    claim = _runtime_claim()
    record, _, receipt = _support(
        claim, "core/session_store.py", current_state_established=True
    )
    assert record.status == STATUS_VERIFIED
    assert receipt is not None

    assessment = _set(claim, record, current_state_receipts=(receipt,))

    assert assessment.current_state_coverage == COVERAGE_COMPLETE
    assert MISSING_CURRENT_STATE_COVERAGE not in assessment.missing_requirements


def test_v_disagreeing_current_state_receipts_are_inconsistent():
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
    assert unestablished.status == STATUS_INSUFFICIENT

    assessment = _set(
        claim,
        established,
        unestablished,
        current_state_receipts=(established_receipt, denied),
    )

    assert assessment.current_state_coverage == COVERAGE_INCONSISTENT
    assert MISSING_CURRENT_STATE_COVERAGE in assessment.missing_requirements


def test_a_current_state_receipt_for_another_source_is_refused():
    claim = _runtime_claim()
    record, _, established = _support(
        claim, "core/session_store.py", current_state_established=True
    )
    _, foreign_receipt = _acquire(
        "core/absent.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    foreign = _current_state(claim, foreign_receipt)
    assert established is not None

    assessment = _set(claim, record, current_state_receipts=(established, foreign))

    assert assessment.set_status == SET_INCONSISTENT_INPUT
    assert INCONSISTENT_CURRENT_STATE_RECEIPT_BINDING in assessment.inconsistencies


def test_current_state_coverage_is_not_applicable_outside_runtime_scopes():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")

    assessment = _set(claim, record)

    assert assessment.current_state_coverage == COVERAGE_NOT_APPLICABLE


# =============================================================================
# 7. Historical, validation and manifest material
# =============================================================================

def test_w_ten_historical_documents_do_not_outweigh_anything():
    """EVIDENCE.1 already made them insufficient; EVIDENCE.2 keeps them there."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    records = []
    for index in range(10):
        content = HISTORICAL_NOTE + f"\n<!-- revision {index} -->\n".encode("utf-8")
        record, _, _ = _verify(
            f"docs/history/note_{index}.md",
            content,
            (ROLE_HISTORICAL_CONTEXT,),
            (SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,),
            claim,
        )
        records.append(record)

    assessment = _set(claim, *records)

    assert all(record.relation == RELATION_INSUFFICIENT for record in records)
    assert len(assessment.insufficient_records) == 10
    assert assessment.support_records == ()
    assert assessment.conflict_status == CONFLICT_NO_DIRECTIONAL_EVIDENCE
    assert assessment.scope_coverage == COVERAGE_INCOMPLETE


def test_historical_material_never_outranks_one_current_implementation():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    historical = [
        _verify(
            f"docs/history/note_{index}.md",
            HISTORICAL_NOTE + f"\n<!-- revision {index} -->\n".encode("utf-8"),
            (ROLE_HISTORICAL_CONTEXT,),
            (SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,),
            claim,
        )[0]
        for index in range(10)
    ]
    implementation, _, _ = _contradiction(claim, "core/session_store.py")

    assessment = _set(claim, *historical, implementation)

    assert len(assessment.contradiction_records) == 1
    assert len(assessment.insufficient_records) == 10
    assert assessment.conflict_status == CONFLICT_CONTRADICTION_ONLY
    assert assessment.claim_decision_authority is False


def test_x_several_agreeing_tests_do_not_establish_runtime_behaviour():
    claim = _runtime_claim()
    records = []
    for index in range(3):
        content = VALIDATION_TEST + f"\n# case {index}\n".encode("utf-8")
        record, _, _ = _verify(
            f"tests/test_sessions_{index}.py",
            content,
            (ROLE_VALIDATION_EVIDENCE,),
            (SOURCE_CLASS_VALIDATION_TEST,),
            claim,
            domain=DOMAIN_VALIDATION_ARTIFACTS,
            analyzer=_analyzer(supporting_markers=(b"survives_a_restart",)),
        )
        records.append(record)

    assessment = _set(claim, *records)

    assert all(record.relation == RELATION_INSUFFICIENT for record in records)
    assert assessment.support_records == ()
    assert assessment.conflict_status == CONFLICT_NO_DIRECTIONAL_EVIDENCE
    validation = _role_entry(assessment, ROLE_VALIDATION_EVIDENCE)
    assert validation is not None
    assert validation.present is True
    assert validation.directional_present is False


def test_y_a_manifest_declaration_stays_insufficient_for_runtime_behaviour():
    claim = _runtime_claim()
    record, _, _ = _verify(
        "pyproject.toml",
        DEPENDENCY_MANIFEST,
        (ROLE_CONFIGURATION_AUTHORITY,),
        (SOURCE_CLASS_DEPENDENCY_MANIFEST,),
        claim,
        analyzer=_analyzer(
            supporting_markers=(b"sqlite-utils",),
            relevance_markers=(b"sqlite",),
        ),
    )

    assessment = _set(claim, record)

    assert record.relation == RELATION_INSUFFICIENT
    assert assessment.support_records == ()
    assert len(assessment.insufficient_records) == 1


# =============================================================================
# 8. The DeepSeek dogfood set
# =============================================================================

def test_deepseek_set_one_holds_no_support_and_no_coverage():
    claim = _negative_claim()
    records = [
        _insufficient(claim, f"core/module_{index}.py")[0] for index in range(3)
    ]
    records.append(_unrelated(claim, "web/static/panel.css")[0])

    assessment = _set(claim, *records)

    assert assessment.set_status == SET_ASSESSED
    assert assessment.support_records == ()
    assert assessment.negative_claim_coverage == COVERAGE_INCOMPLETE
    assert assessment.conflict_status == CONFLICT_NO_DIRECTIONAL_EVIDENCE
    assert assessment.claim_decision_authority is False


def test_deepseek_set_two_surfaces_the_sqlite_counterexample():
    claim = _negative_claim()
    records = [
        _insufficient(claim, f"core/module_{index}.py")[0] for index in range(3)
    ]
    counterexample, _, _ = _contradiction(claim, "core/session_store.py")
    records.append(counterexample)

    assessment = _set(claim, *records)

    assert len(assessment.contradiction_records) == 1
    assert assessment.conflict_status == CONFLICT_CONTRADICTION_ONLY
    assert assessment.negative_claim_coverage == COVERAGE_INCOMPLETE
    assert assessment.claim_decision_authority is False


def test_deepseek_set_three_identifies_duplicated_hypothesis_documents():
    """Four copies of one guess are one lineage, and outvote nothing."""
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

    assessment = _set(claim, *duplicates, counterexample)

    assert assessment.set_status == SET_ASSESSED
    # The four documents never became support: EVIDENCE.1 downgraded them.
    assert assessment.support_records == ()
    assert len(assessment.contradiction_records) == 1
    assert assessment.conflict_status == CONFLICT_CONTRADICTION_ONLY

    independence = assessment.independence
    assert independence is not None
    assert independence.record_count == 5
    assert independence.source_count == 5
    # Four identical documents collapse to one lineage; the implementation is its own.
    assert independence.lineage_group_count == 2
    assert independence.duplicate_group_count == 1
    assert independence.exact_duplicates_present is True
    duplicate_group = next(
        group
        for group in independence.lineage_groups
        if group.independence_state == INDEPENDENCE_DUPLICATE
    )
    assert len(duplicate_group.source_identifiers) == 4
    assert assessment.negative_claim_coverage == COVERAGE_INCOMPLETE
    assert assessment.claim_decision_authority is False


def test_anti_self_corroboration_duplicate_supports_are_one_lineage():
    """B45: one hypothesis copied into three artefacts is not three witnesses."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    first, _, _ = _support(claim, "docs/a.md")
    second, _, _ = _support(claim, "docs/b.md")
    third, _, _ = _support(claim, "docs/c.md", marker="distinct")

    assessment = _set(claim, first, second, third)

    assert len(assessment.support_records) == 3
    independence = assessment.independence
    assert independence is not None
    assert independence.record_count == 3
    assert independence.lineage_group_count == 2
    assert independence.duplicate_group_count == 1
    assert independence.independent_group_count == 0
    assert MISSING_INDEPENDENT_CORROBORATION in assessment.missing_requirements


# =============================================================================
# 9. Tamper binding, determinism and ordering
# =============================================================================

def test_the_assessment_is_independent_of_member_order():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    first, _, _ = _support(claim, "core/a.py", marker="a")
    second, _, _ = _support(claim, "core/b.py", marker="b")
    third, _, _ = _insufficient(claim, "core/c.py")

    forward = _set(claim, first, second, third)
    shuffled = _set(claim, third, first, second)

    assert forward.assessment_fingerprint == shuffled.assessment_fingerprint
    assert render_evidence_set_assessment_json(forward) == (
        render_evidence_set_assessment_json(shuffled)
    )


def test_the_same_set_assessed_twice_is_byte_identical():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")

    assert render_evidence_set_assessment_json(_set(claim, record)) == (
        render_evidence_set_assessment_json(_set(claim, record))
    )


@pytest.mark.parametrize(
    "mutation",
    [
        {"relation": RELATION_CONTRADICTS, "status": STATUS_CONTRADICTED},
        {"source_content_sha256": _digest("other-bytes")},
        {"proposition_sha256": _digest("other-proposition")},
        {"analyzer_proposal_fingerprint": _digest("other-proposal")},
    ],
)
def test_tampering_with_a_record_changes_its_rederived_identity(mutation):
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    original = evidence_record_fingerprint(record)

    try:
        tampered = dataclasses.replace(record, **mutation)
    except ValueError:
        return  # the EVIDENCE.1 record refused the mutation outright, which is stronger
    assert evidence_record_fingerprint(tampered) != original


def test_a_tampered_span_changes_the_set_identity():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    baseline = _set(claim, record).assessment_fingerprint

    spans = record.evidence_span_refs
    widened = dataclasses.replace(spans[0], end_byte=spans[0].end_byte - 1)
    tampered = dataclasses.replace(
        record,
        evidence_span_refs=(widened,) + spans[1:],
        promotion_status="not_promoted",
        status=STATUS_INSUFFICIENT,
        relation=RELATION_INSUFFICIENT,
        verified_evidence=None,
    )

    assert _set(claim, tampered).assessment_fingerprint != baseline


def test_a_record_that_established_nothing_is_not_evidence():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    payload, receipt = _acquire(
        "core/session_store.py",
        _sqlite_implementation(),
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    other_payload, _ = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    broken = verify_acquired_source(
        _request(receipt, claim), other_payload, receipt, _analyzer()
    )
    assert broken.status not in {STATUS_VERIFIED, STATUS_INSUFFICIENT}

    assessment = _set(claim, broken)

    assert assessment.set_status == SET_INCONSISTENT_INPUT
    assert INCONSISTENT_RECORD_NOT_ADMISSIBLE in assessment.inconsistencies


def test_the_request_fingerprint_is_order_independent():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    first, _, _ = _support(claim, "core/a.py", marker="a")
    second, _, _ = _support(claim, "core/b.py", marker="b")

    forward = EvidenceSetRequest(proposition=claim, records=(first, second))
    reverse = EvidenceSetRequest(proposition=claim, records=(second, first))

    assert evidence_set_request_fingerprint(forward) == (
        evidence_set_request_fingerprint(reverse)
    )


def test_the_assessment_fingerprint_covers_supplied_receipts():
    claim = _negative_claim()
    record, receipt, _ = _insufficient(claim, "core/session_store.py")
    coverage = _coverage(claim, (receipt,))

    without = _set(claim, record)
    with_coverage = _set(claim, record, coverage_receipts=(coverage,))

    assert without.assessment_fingerprint != with_coverage.assessment_fingerprint


def test_the_assessment_fingerprint_covers_supplied_requirements():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    requirements = _requirements(claim, (ROLE_IMPLEMENTATION_AUTHORITY,))

    plain = _set(claim, record)
    required = _set(claim, record, requirements=requirements)

    assert plain.assessment_fingerprint != required.assessment_fingerprint
    assert requirements_fingerprint(requirements) == requirements_fingerprint(
        requirements
    )


# =============================================================================
# 10. Semantic status, authority, guardrails
# =============================================================================

def test_ten_agreeing_supports_stay_analyzer_assessed():
    """B30/B31: aggregation cannot upgrade epistemic status."""
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    records = [
        _support(claim, f"core/store_{index}.py", marker=f"v{index}")[0]
        for index in range(10)
    ]

    assessment = _set(claim, *records)

    assert len(assessment.support_records) == 10
    assert assessment.verification_levels is not None
    assert assessment.verification_levels.semantic_relation == LEVEL_ANALYZER_ASSESSED
    assert assessment.verification_levels.source_binding == (
        LEVEL_DETERMINISTICALLY_VERIFIED
    )
    for member in assessment.members:
        assert member.semantic_relation_status == LEVEL_ANALYZER_ASSESSED
    _assert_no_verdict_and_no_number(assessment)
    text = render_evidence_set_assessment_json(assessment)
    assert "deterministic_semantic_verification" not in text
    assert '"semantic_relation": "deterministically_verified"' not in text


def test_an_assessment_cannot_be_built_claiming_deterministic_semantics():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    assessment = _set(claim, record)

    with pytest.raises(ValueError, match="never\\s+deterministically verified"):
        dataclasses.replace(
            assessment,
            verification_levels=dataclasses.replace(
                assessment.verification_levels,
                semantic_relation=LEVEL_DETERMINISTICALLY_VERIFIED,
            ),
        )


def test_the_authority_boundary_is_narrow_and_claim_decision_is_always_false():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    assessment = _set(claim, record)

    authority = assessment.as_dict()["authority"]
    assert authority["evidence_set_assessment_authority"] is True
    assert authority["human_approval_required"] is True
    for name, value in authority.items():
        if name in {"evidence_set_assessment_authority", "human_approval_required"}:
            continue
        assert value is False, name


def test_the_guardrails_are_honest_about_what_was_and_was_not_done():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    guardrails = _set(claim, record).as_dict()["guardrails"]

    for performed in (
        "evidence_records_aggregated",
        "duplicate_analysis_performed",
        "role_coverage_assessed",
        "conflict_assessed",
    ):
        assert guardrails[performed] is True, performed
    for refused in (
        "source_content_read",
        "evidence_acquired",
        "repository_traversed",
        "repository_files_read",
        "network_called",
        "model_called",
        "validation_executed",
        "repository_written",
        "claim_decision_performed",
        "final_claim_emitted",
        "confidence_computed",
        "majority_vote_computed",
        "relations_reinterpreted",
        "semantic_status_upgraded",
        "coverage_receipts_minted",
        "current_state_receipts_minted",
        "lineage_inferred_from_paths",
    ):
        assert guardrails[refused] is False, refused


def test_no_serialized_assessment_carries_a_verdict_or_a_number():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    supporting, _, _ = _support(claim, "core/session_store.py")
    contradicting, _, _ = _contradiction(claim, "core/legacy_store.py", marker="legacy")

    assessment = _set(claim, supporting, contradicting)
    _assert_no_verdict_and_no_number(assessment)

    payload = json.loads(render_evidence_set_assessment_json(assessment))
    assert payload["claim_decision_authority"] is False
    assert payload["final_claim_authority"] is False
    assert payload["claim_decided"] is False
    assert payload["source_content_read"] is False


def test_an_empty_set_does_not_construct():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    with pytest.raises(ValueError, match="at least one record"):
        EvidenceSetRequest(proposition=claim, records=())


def test_a_set_beyond_the_record_ceiling_does_not_construct():
    claim = _proposition(_SQLITE_CLAIM_TEXT)
    record, _, _ = _support(claim, "core/session_store.py")
    with pytest.raises(ValueError, match="finite bound"):
        EvidenceSetRequest(proposition=claim, records=(record,) * 64)
