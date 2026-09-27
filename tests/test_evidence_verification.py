"""EVIDENCE.1 — acquired source verification and evidence promotion.

The matrix is organised the way the phase reasons:

1.  bindings, before anything is analyzed
2.  role verification, which is about content and not about classification
3.  proposition relation, which is a separate question from role
4.  positive claims, including the omission-is-not-contradiction rule
5.  negative existential claims, where absence needs coverage
6.  epistemic distinctions between what a role can and cannot establish
7.  spans, which must be bytes somebody actually read
8.  promotion, receipts, determinism and what never reaches a serialization

Every test runs offline.  No model, no network, no repository read.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from core.acquisition_request import (
    SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,
    SOURCE_CLASS_DEPENDENCY_MANIFEST,
    SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,
    SOURCE_CLASS_INTERFACE_DEFINITION,
    SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
    SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,
    SOURCE_CLASS_VALIDATION_TEST,
)
from core.content_acquisition import (
    MODE_EXISTING_CONTEXT,
    MODE_REPOSITORY_READ,
    AcquiredSourcePayload,
    SourceAcquisitionReceipt,
    SourceBinding,
)
from core.evidence_analyzer import (
    EvidenceAnalyzerUnavailable,
    ScriptedEvidenceAnalyzer,
    StaticEvidenceAnalyzer,
)
from core.evidence_promotion_gate import (
    binding_inconsistencies,
    proposal_defects,
    verify_acquired_source,
    verify_with_bounded_repair,
)
from core.evidence_requirements import (
    DOMAIN_REPOSITORY,
    DOMAIN_VALIDATION_ARTIFACTS,
    ROLE_ARCHITECTURE_DESCRIPTION,
    ROLE_CONFIGURATION_AUTHORITY,
    ROLE_HISTORICAL_CONTEXT,
    ROLE_HYPOTHESIS_SUPPORT,
    ROLE_IMPLEMENTATION_AUTHORITY,
    ROLE_INTERFACE_CONTRACT,
    ROLE_VALIDATION_EVIDENCE,
    TIER_REQUIRED_PRIMARY,
)
from core.evidence_verification import (
    ANALYSIS_INCOMPATIBLE_MECHANISM_PRESENT,
    ANALYSIS_MECHANISM_IMPLEMENTED,
    ANALYSIS_PROPOSITION_TERMS_PRESENT,
    ANALYSIS_ROLE_CONTENT_CONSISTENT,
    CONSTRAINT_CURRENT_STATE_RECEIPT_REQUIRED,
    CONSTRAINT_NEGATIVE_COVERAGE_REQUIRED,
    CONSTRAINT_ROLE_VERIFICATION_REQUIRED,
    COVERAGE_ALL_ELIGIBLE_CANDIDATES_ACQUIRED,
    COVERAGE_ALL_REQUIRED_ROLES_ACQUIRED,
    COVERAGE_INSUFFICIENT,
    COVERAGE_NOT_APPLICABLE,
    COVERAGE_NOT_SUPPLIED,
    COVERAGE_REQUIRED_ROLE_UNACQUIRED,
    COVERAGE_SUFFICIENT,
    CURRENT_STATE_ESTABLISHED,
    CURRENT_STATE_NOT_ESTABLISHED,
    CURRENT_STATE_RUNTIME_ENTRYPOINT_CONFIRMED,
    GATE_ANALYZER_PROPOSAL_INVALID,
    GATE_ANALYZER_UNAVAILABLE,
    GATE_EVIDENCE_PROMOTED,
    GATE_PROMOTION_BLOCKED_CURRENT_STATE,
    GATE_PROMOTION_BLOCKED_NEGATIVE_COVERAGE,
    GATE_RELATION_DOWNGRADED_NO_VERIFIED_ROLE,
    GATE_RELATION_DOWNGRADED_ROLE_NOT_COMPETENT,
    GATE_REQUESTED_ROLE_NOT_EXPECTED,
    INCONSISTENT_CANDIDATE_IDENTITY,
    INCONSISTENT_COVERAGE_BINDING,
    INCONSISTENT_CURRENT_STATE_BINDING,
    INCONSISTENT_PAYLOAD_DIGEST,
    INCONSISTENT_RECEIPT_FINGERPRINT,
    INCONSISTENT_SOURCE_BINDING,
    MAX_EVIDENCE_SPANS,
    MAX_SPAN_BYTES,
    MAX_TOTAL_CITED_BYTES,
    PROMOTION_NOT_PROMOTED,
    PROMOTION_PROMOTED,
    PROPOSITION_NEGATIVE_EXISTENTIAL,
    PROPOSITION_POSITIVE,
    RELATION_CONTRADICTS,
    RELATION_INSUFFICIENT,
    RELATION_SUPPORTS,
    RELATION_UNRELATED,
    ROLE_STATUS_REJECTED,
    ROLE_STATUS_VERIFIED,
    SCOPE_COMPETENT_ROLES,
    SCOPE_CONFIGURATION_DECLARATION,
    SCOPE_DOCUMENTED_ARCHITECTURE,
    SCOPE_HISTORICAL_INTENT,
    SCOPE_IMPLEMENTATION_STATE,
    SCOPE_INTERFACE_CAPABILITY,
    SCOPE_RUNTIME_BEHAVIOUR,
    SCOPE_VALIDATION_EXPECTATION,
    SCOPES_REQUIRING_CURRENT_STATE,
    SPAN_CONTRADICTING,
    SPAN_ROLE_EVIDENCE,
    SPAN_SUPPORTING,
    STATUS_ANALYSIS_INVALID,
    STATUS_BINDING_INVALID,
    STATUS_CONTRADICTED,
    STATUS_COVERAGE_REQUIRED,
    STATUS_INSUFFICIENT,
    STATUS_UNRELATED,
    STATUS_UNSUPPORTED_SOURCE,
    STATUS_VERIFIED,
    VERIFICATION_CONSTRAINTS,
    CurrentStateReceipt,
    EvidenceSpan,
    EvidenceVerificationProposal,
    EvidenceVerificationRequest,
    NegativeClaimCoverage,
    Proposition,
    RoleAssessment,
    bounded_payload_view,
    render_evidence_verification_result_json,
    render_verification_set_json,
    source_receipt_fingerprint,
    span_from_view,
    verification_request_fingerprint,
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
    tier: str = TIER_REQUIRED_PRIMARY,
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
        tier=tier,
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
    requested_roles: tuple[str, ...] | None = None,
    coverage: NegativeClaimCoverage | None = None,
    current_state: CurrentStateReceipt | None = None,
    extra_constraints: tuple[str, ...] = (),
    role_verification_required: bool = True,
) -> EvidenceVerificationRequest:
    declared = set(extra_constraints)
    if role_verification_required:
        declared.add(CONSTRAINT_ROLE_VERIFICATION_REQUIRED)
    if proposition.proposition_type == PROPOSITION_NEGATIVE_EXISTENTIAL:
        declared.add(CONSTRAINT_NEGATIVE_COVERAGE_REQUIRED)
    if proposition.scope in SCOPES_REQUIRING_CURRENT_STATE:
        declared.add(CONSTRAINT_CURRENT_STATE_RECEIPT_REQUIRED)
    return EvidenceVerificationRequest(
        proposition=proposition,
        requested_roles=requested_roles or receipt.expected_roles,
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
    *,
    status: str = COVERAGE_SUFFICIENT,
    uncovered: tuple[str, ...] = (),
    reasons: tuple[str, ...] = (
        COVERAGE_ALL_REQUIRED_ROLES_ACQUIRED,
        COVERAGE_ALL_ELIGIBLE_CANDIDATES_ACQUIRED,
    ),
    **overrides: object,
) -> NegativeClaimCoverage:
    values: dict[str, object] = {
        "proposition_id": proposition.proposition_id,
        "proposition_sha256": proposition.proposition_sha256,
        "required_roles": (ROLE_IMPLEMENTATION_AUTHORITY,),
        "acquisition_request_fingerprint": (
            receipt.source_binding.acquisition_request_fingerprint
        ),
        "candidate_pool_fingerprint": receipt.source_binding.candidate_receipt_fingerprint,
        "acquired_source_receipt_fingerprints": (source_receipt_fingerprint(receipt),),
        "coverage_status": status,
        "uncovered_requirements": uncovered,
        "source_class_coverage": (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
        "reasons": reasons,
    }
    values.update(overrides)
    return NegativeClaimCoverage(**values)  # type: ignore[arg-type]


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
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, state BLOB)"
        )

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

    def load_session(self, session_id):
        return self._sessions.get(session_id)
'''

INTERFACE_ONLY = b'''from typing import Protocol


class SessionStore(Protocol):
    def save_session(self, session_id: str, state: bytes) -> None: ...

    def load_session(self, session_id: str) -> bytes | None: ...
'''

DEPENDENCY_MANIFEST = b'''[project]
name = "deepseek-harness"
dependencies = [
    "sqlite-utils==3.35",
    "httpx==0.27.0",
]
'''

VALIDATION_TEST = b'''def test_session_state_survives_a_restart(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    store.save_session("abc", b"state")
    assert SessionStore(tmp_path / "sessions.db").load_session("abc") == b"state"
'''

ARCHITECTURE_DOC = b'''# Session architecture

The SessionStore owns session state. Callers reach it through save_session and
load_session and never touch storage directly.
'''

HISTORICAL_NOTE = b'''# Rejected: SQLite session persistence

We considered persisting sessions with sqlite3.connect and decided against it.
This proposal was rejected and was never implemented.
'''

PLACEHOLDER_MODULE = b'''"""Placeholder module. Nothing is implemented here yet."""

TODO = "decide what this module should do"
'''

STYLESHEET = b'''.session-panel {
    display: flex;
    gap: 8px;
}
'''


# ── Fixtures: analyzers ───────────────────────────────────────────────────────

def _sqlite_analyzer(**overrides: object) -> StaticEvidenceAnalyzer:
    values: dict[str, object] = {
        "role_markers": {
            ROLE_IMPLEMENTATION_AUTHORITY: (b"def save_session", b"self._connection"),
            ROLE_INTERFACE_CONTRACT: (b"Protocol",),
            ROLE_CONFIGURATION_AUTHORITY: (b"dependencies = [",),
            ROLE_VALIDATION_EVIDENCE: (b"def test_",),
            ROLE_ARCHITECTURE_DESCRIPTION: (b"# Session architecture",),
            ROLE_HISTORICAL_CONTEXT: (b"was rejected",),
        },
        "supporting_markers": (b"sqlite3.connect",),
        "relevance_markers": (b"save_session", b"session"),
        "context_bytes": 40,
    }
    values.update(overrides)
    return StaticEvidenceAnalyzer(**values)  # type: ignore[arg-type]


# =============================================================================
# 1. Binding gate
# =============================================================================

def test_a_valid_source_and_matching_proposition_proceeds_to_verification():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    request = _request(
        receipt,
        _proposition("SessionStore writes session state to SQLite."),
    )
    analyzer = _sqlite_analyzer()

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert binding_inconsistencies(request, payload, receipt) == ()
    assert result.status == STATUS_VERIFIED
    assert result.source_content_analyzed is True
    assert analyzer.call_count == 1


def test_b_payload_digest_mismatch_blocks_before_the_analyzer_is_called():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    request = _request(receipt, _proposition("SessionStore writes state to SQLite."))
    tampered, _ = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    analyzer = ScriptedEvidenceAnalyzer([])

    result = verify_acquired_source(request, tampered, receipt, analyzer)

    assert result.status == STATUS_BINDING_INVALID
    assert INCONSISTENT_PAYLOAD_DIGEST in result.inconsistencies
    assert result.source_content_analyzed is False
    assert result.promotion_status == PROMOTION_NOT_PROMOTED
    assert analyzer.call_count == 0


def test_c_receipt_fingerprint_mismatch_is_blocked():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    proposition = _proposition("SessionStore writes state to SQLite.")
    request = EvidenceVerificationRequest(
        proposition=proposition,
        requested_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
        acquisition_receipt_fingerprint=_digest("a-different-receipt"),
        source_content_sha256=receipt.content_sha256,
        source_binding=receipt.source_binding,
        verification_constraints=(CONSTRAINT_ROLE_VERIFICATION_REQUIRED,),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([])
    )

    assert result.status == STATUS_BINDING_INVALID
    assert INCONSISTENT_RECEIPT_FINGERPRINT in result.inconsistencies


def test_d_a_proposition_digest_the_analyzer_changed_is_blocked():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    proposition = _proposition("SessionStore writes session state to SQLite.")
    request = _request(receipt, proposition)
    other = _proposition("SessionStore writes session state to Postgres.")
    view = bounded_payload_view(payload, receipt)
    proposal = EvidenceVerificationProposal(
        proposition_id=proposition.proposition_id,
        proposition_sha256=other.proposition_sha256,
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
        evidence_spans=(span_from_view(view, 0, 40, SPAN_SUPPORTING),),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([proposal])
    )

    assert result.status == STATUS_ANALYSIS_INVALID
    assert GATE_ANALYZER_PROPOSAL_INVALID in result.reasons
    assert result.promotion_status == PROMOTION_NOT_PROMOTED


def test_e_source_identifier_mismatch_is_blocked():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    other_binding = _binding("core/router.py")
    request = EvidenceVerificationRequest(
        proposition=_proposition("SessionStore writes state to SQLite."),
        requested_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
        acquisition_receipt_fingerprint=source_receipt_fingerprint(receipt),
        source_content_sha256=receipt.content_sha256,
        source_binding=other_binding,
        verification_constraints=(CONSTRAINT_ROLE_VERIFICATION_REQUIRED,),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([])
    )

    assert result.status == STATUS_BINDING_INVALID
    assert INCONSISTENT_CANDIDATE_IDENTITY in result.inconsistencies
    assert INCONSISTENT_SOURCE_BINDING in result.inconsistencies


def test_f_a_source_acquired_under_another_provenance_chain_is_blocked():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    widened = _binding(
        "core/session_store.py",
        authorization_fingerprint=_digest("a-wider-authorization"),
    )
    request = EvidenceVerificationRequest(
        proposition=_proposition("SessionStore writes state to SQLite."),
        requested_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
        acquisition_receipt_fingerprint=source_receipt_fingerprint(receipt),
        source_content_sha256=receipt.content_sha256,
        source_binding=widened,
        verification_constraints=(CONSTRAINT_ROLE_VERIFICATION_REQUIRED,),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([])
    )

    assert result.status == STATUS_BINDING_INVALID
    assert INCONSISTENT_SOURCE_BINDING in result.inconsistencies


def test_a_source_acquired_for_another_role_is_an_unsupported_source():
    payload, receipt = _acquire(
        "docs/architecture.md",
        ARCHITECTURE_DOC,
        (ROLE_ARCHITECTURE_DESCRIPTION,),
        (SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,),
    )
    request = _request(
        receipt,
        _proposition("SessionStore writes state to SQLite."),
        requested_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
    )
    analyzer = _sqlite_analyzer()

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.status == STATUS_UNSUPPORTED_SOURCE
    assert GATE_REQUESTED_ROLE_NOT_EXPECTED in result.reasons
    assert result.source_content_analyzed is False
    assert analyzer.call_count == 0


def test_a_coverage_receipt_bound_to_another_claim_is_blocked():
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
    other = _proposition(
        "DeepSeek Harness has no plugin system.",
        proposition_type=PROPOSITION_NEGATIVE_EXISTENTIAL,
        identifier="P-2",
    )
    request = _request(receipt, claim, coverage=_coverage(other, receipt))

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([])
    )

    assert result.status == STATUS_BINDING_INVALID
    assert INCONSISTENT_COVERAGE_BINDING in result.inconsistencies


def test_a_current_state_receipt_bound_to_other_bytes_is_blocked():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    proposition = _proposition(
        "The running harness persists sessions to SQLite.",
        scope=SCOPE_RUNTIME_BEHAVIOUR,
    )
    _, other_receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    stale = CurrentStateReceipt(
        proposition_id=proposition.proposition_id,
        proposition_sha256=proposition.proposition_sha256,
        candidate_identifier=receipt.candidate_identifier,
        source_content_sha256=other_receipt.content_sha256,
        acquisition_receipt_fingerprint=source_receipt_fingerprint(receipt),
        current_state_status=CURRENT_STATE_ESTABLISHED,
        basis=(CURRENT_STATE_RUNTIME_ENTRYPOINT_CONFIRMED,),
    )
    request = _request(receipt, proposition, current_state=stale)

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([])
    )

    assert result.status == STATUS_BINDING_INVALID
    assert INCONSISTENT_CURRENT_STATE_BINDING in result.inconsistencies


def test_the_payload_is_authoritative_and_the_path_is_never_reopened(tmp_path):
    """The receipt binds the verdict to the bytes acquired, not to today's disk."""
    on_disk = tmp_path / "session_store.py"
    on_disk.write_bytes(MEMORY_IMPLEMENTATION)
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    request = _request(
        receipt,
        _proposition("SessionStore writes session state to SQLite."),
    )

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())

    assert result.status == STATUS_VERIFIED
    assert result.source_content_sha256 == hashlib.sha256(SQLITE_IMPLEMENTATION).hexdigest()
    assert on_disk.read_bytes() == MEMORY_IMPLEMENTATION


# =============================================================================
# 2. Role verification
# =============================================================================

def test_g_implementation_content_verifies_the_implementation_role():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    request = _request(receipt, _proposition("SessionStore writes state to SQLite."))

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())

    assert result.verified_roles == (ROLE_IMPLEMENTATION_AUTHORITY,)
    assert result.rejected_roles == ()


def test_h_a_classified_implementation_with_placeholder_content_fails_its_role():
    payload, receipt = _acquire(
        "core/router.py",
        PLACEHOLDER_MODULE,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    request = _request(receipt, _proposition("SessionStore writes state to SQLite."))

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())

    assert result.verified_roles == ()
    assert result.rejected_roles == (ROLE_IMPLEMENTATION_AUTHORITY,)
    assert result.promotion_status == PROMOTION_NOT_PROMOTED


def test_i_a_test_verifies_validation_evidence_and_gains_no_implementation_role():
    payload, receipt = _acquire(
        "tests/test_session_store.py",
        VALIDATION_TEST,
        (ROLE_VALIDATION_EVIDENCE,),
        (SOURCE_CLASS_VALIDATION_TEST,),
        domain=DOMAIN_VALIDATION_ARTIFACTS,
    )
    request = _request(
        receipt,
        _proposition(
            "The session-store tests expect state to survive a restart.",
            scope=SCOPE_VALIDATION_EXPECTATION,
        ),
    )

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())

    assert result.verified_roles == (ROLE_VALIDATION_EVIDENCE,)
    assert ROLE_IMPLEMENTATION_AUTHORITY not in result.verified_roles
    assert ROLE_IMPLEMENTATION_AUTHORITY not in [
        item.role for item in result.role_assessments
    ]


def test_j_an_architecture_doc_verifies_description_and_not_implementation():
    payload, receipt = _acquire(
        "docs/architecture.md",
        ARCHITECTURE_DOC,
        (ROLE_ARCHITECTURE_DESCRIPTION,),
        (SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,),
    )
    documented = _request(
        receipt,
        _proposition(
            "The architecture document states that SessionStore owns session state.",
            scope=SCOPE_DOCUMENTED_ARCHITECTURE,
        ),
    )

    result = verify_acquired_source(documented, payload, receipt, _sqlite_analyzer())

    assert result.verified_roles == (ROLE_ARCHITECTURE_DESCRIPTION,)
    assert ROLE_IMPLEMENTATION_AUTHORITY not in result.verified_roles


def test_k_a_rejected_design_note_verifies_history_and_holds_no_current_authority():
    payload, receipt = _acquire(
        "docs/designs/rejected-sqlite.md",
        HISTORICAL_NOTE,
        (ROLE_HISTORICAL_CONTEXT,),
        (SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,),
    )
    request = _request(
        receipt,
        _proposition(
            "A rejected design proposed persisting sessions with SQLite.",
            scope=SCOPE_HISTORICAL_INTENT,
        ),
    )

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())

    assert result.verified_roles == (ROLE_HISTORICAL_CONTEXT,)
    assert ROLE_IMPLEMENTATION_AUTHORITY not in SCOPE_COMPETENT_ROLES[SCOPE_HISTORICAL_INTENT]
    assert ROLE_HISTORICAL_CONTEXT not in SCOPE_COMPETENT_ROLES[SCOPE_IMPLEMENTATION_STATE]


def test_expected_role_is_a_hypothesis_and_never_a_verified_role_by_itself():
    payload, receipt = _acquire(
        "web/static/app.css",
        STYLESHEET,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,),
    )
    request = _request(receipt, _proposition("SessionStore writes state to SQLite."))
    analyzer = _sqlite_analyzer(relevance_markers=(b"save_session",))

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert receipt.expected_roles == (ROLE_IMPLEMENTATION_AUTHORITY,)
    assert result.verified_roles == ()
    assert result.relation == RELATION_UNRELATED


# =============================================================================
# 3. Proposition relation
# =============================================================================

def test_l_implementation_content_supports_a_concrete_implementation_claim():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    request = _request(
        receipt,
        _proposition("SessionStore writes session state to SQLite."),
    )

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())

    assert result.status == STATUS_VERIFIED
    assert result.relation == RELATION_SUPPORTS
    assert result.promotion_status == PROMOTION_PROMOTED
    assert result.evidence_span_refs
    assert any(item.purpose == SPAN_SUPPORTING for item in result.evidence_span_refs)


def test_m_an_interface_alone_is_insufficient_for_a_concrete_implementation_claim():
    payload, receipt = _acquire(
        "core/session_store_protocol.py",
        INTERFACE_ONLY,
        (ROLE_INTERFACE_CONTRACT,),
        (SOURCE_CLASS_INTERFACE_DEFINITION,),
    )
    request = _request(
        receipt,
        _proposition("SessionStore writes session state to SQLite."),
    )
    # Even a maximally generous analyzer cannot promote this.
    analyzer = _sqlite_analyzer(supporting_markers=(b"def save_session",))

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.verified_roles == (ROLE_INTERFACE_CONTRACT,)
    assert result.status == STATUS_INSUFFICIENT
    assert result.relation == RELATION_INSUFFICIENT
    assert GATE_RELATION_DOWNGRADED_ROLE_NOT_COMPETENT in result.reasons
    assert result.promotion_status == PROMOTION_NOT_PROMOTED


def test_n_a_dependency_manifest_is_insufficient_for_a_session_persistence_claim():
    payload, receipt = _acquire(
        "pyproject.toml",
        DEPENDENCY_MANIFEST,
        (ROLE_CONFIGURATION_AUTHORITY,),
        (SOURCE_CLASS_DEPENDENCY_MANIFEST,),
    )
    request = _request(
        receipt,
        _proposition("SessionStore writes session state to SQLite."),
    )
    analyzer = _sqlite_analyzer(supporting_markers=(b"sqlite-utils",))

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.verified_roles == (ROLE_CONFIGURATION_AUTHORITY,)
    assert result.status == STATUS_INSUFFICIENT
    assert GATE_RELATION_DOWNGRADED_ROLE_NOT_COMPETENT in result.reasons


def test_n_the_same_manifest_supports_a_declaration_claim():
    payload, receipt = _acquire(
        "pyproject.toml",
        DEPENDENCY_MANIFEST,
        (ROLE_CONFIGURATION_AUTHORITY,),
        (SOURCE_CLASS_DEPENDENCY_MANIFEST,),
    )
    request = _request(
        receipt,
        _proposition(
            "The repository declares a dependency on sqlite-utils.",
            scope=SCOPE_CONFIGURATION_DECLARATION,
        ),
    )
    analyzer = _sqlite_analyzer(supporting_markers=(b"sqlite-utils",))

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.status == STATUS_VERIFIED
    assert result.relation == RELATION_SUPPORTS


def test_o_an_incompatible_implementation_contradicts_the_claim():
    payload, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    request = _request(
        receipt,
        _proposition("SessionStore writes session state to SQLite."),
    )
    analyzer = _sqlite_analyzer(
        contradicting_markers=(b"self._sessions[session_id] = state",),
    )

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.status == STATUS_CONTRADICTED
    assert result.relation == RELATION_CONTRADICTS
    assert result.promotion_status == PROMOTION_PROMOTED
    assert result.verified_evidence is not None
    assert any(item.purpose == SPAN_CONTRADICTING for item in result.evidence_span_refs)


def test_p_a_source_that_never_mentions_the_mechanism_does_not_contradict():
    payload, receipt = _acquire(
        "docs/architecture.md",
        ARCHITECTURE_DOC,
        (ROLE_ARCHITECTURE_DESCRIPTION,),
        (SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,),
    )
    request = _request(
        receipt,
        _proposition("SessionStore writes session state to SQLite."),
    )

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())

    assert b"sqlite" not in ARCHITECTURE_DOC.lower()
    assert result.relation != RELATION_CONTRADICTS
    assert result.status in {STATUS_INSUFFICIENT, STATUS_UNRELATED}


def test_p_the_deterministic_analyzer_has_no_absence_as_contradiction_rule():
    payload, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    request = _request(receipt, _proposition("SessionStore writes state to SQLite."))
    # No contradicting marker is configured: omission alone must not produce one.
    analyzer = _sqlite_analyzer()

    proposal = analyzer.analyze(request, bounded_payload_view(payload, receipt))

    assert proposal.relation != RELATION_CONTRADICTS


def test_insufficient_and_unrelated_are_different_findings():
    interface_payload, interface_receipt = _acquire(
        "core/session_store_protocol.py",
        INTERFACE_ONLY,
        (ROLE_INTERFACE_CONTRACT,),
        (SOURCE_CLASS_INTERFACE_DEFINITION,),
    )
    css_payload, css_receipt = _acquire(
        "web/static/app.css",
        STYLESHEET,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,),
    )
    claim = _proposition("SessionStore writes session state to SQLite.")

    relevant = verify_acquired_source(
        _request(interface_receipt, claim),
        interface_payload,
        interface_receipt,
        _sqlite_analyzer(),
    )
    irrelevant = verify_acquired_source(
        _request(css_receipt, claim),
        css_payload,
        css_receipt,
        _sqlite_analyzer(relevance_markers=(b"save_session",)),
    )

    assert relevant.status == STATUS_INSUFFICIENT
    assert irrelevant.status == STATUS_UNRELATED


# =============================================================================
# 4. Negative existential claims
# =============================================================================

_NO_PERSISTENCE = "DeepSeek Harness has no session persistence."


def _negative_claim() -> Proposition:
    return _proposition(
        _NO_PERSISTENCE,
        proposition_type=PROPOSITION_NEGATIVE_EXISTENTIAL,
    )


def test_q_one_source_lacking_persistence_cannot_support_a_repository_wide_absence():
    payload, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _negative_claim()
    request = _request(receipt, claim)
    analyzer = _sqlite_analyzer(supporting_markers=(b"self._sessions = {}",))

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.status == STATUS_COVERAGE_REQUIRED
    assert result.relation == RELATION_INSUFFICIENT
    assert GATE_PROMOTION_BLOCKED_NEGATIVE_COVERAGE in result.reasons
    assert result.coverage_status == COVERAGE_NOT_SUPPLIED
    assert result.promotion_status == PROMOTION_NOT_PROMOTED


def test_r_an_analyzer_asserting_supports_without_coverage_is_downgraded():
    payload, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _negative_claim()
    request = _request(receipt, claim)
    view = bounded_payload_view(payload, receipt)
    proposal = EvidenceVerificationProposal(
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
        evidence_spans=(span_from_view(view, 0, 60, SPAN_SUPPORTING),),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([proposal])
    )

    assert result.status == STATUS_COVERAGE_REQUIRED
    assert result.relation == RELATION_INSUFFICIENT
    assert GATE_PROMOTION_BLOCKED_NEGATIVE_COVERAGE in result.reasons


def test_r_insufficient_coverage_is_still_not_coverage():
    payload, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _negative_claim()
    coverage = _coverage(
        claim,
        receipt,
        status=COVERAGE_INSUFFICIENT,
        uncovered=(ROLE_IMPLEMENTATION_AUTHORITY,),
        reasons=(COVERAGE_REQUIRED_ROLE_UNACQUIRED,),
    )
    request = _request(receipt, claim, coverage=coverage)
    analyzer = _sqlite_analyzer(supporting_markers=(b"self._sessions = {}",))

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.status == STATUS_COVERAGE_REQUIRED
    assert result.coverage_status == COVERAGE_INSUFFICIENT
    assert GATE_PROMOTION_BLOCKED_NEGATIVE_COVERAGE in result.reasons


def test_r_coverage_that_does_not_cover_this_source_is_not_coverage_for_it():
    payload, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _negative_claim()
    request = _request(
        receipt,
        claim,
        coverage=_coverage(
            claim,
            receipt,
            acquired_source_receipt_fingerprints=(_digest("a-different-source"),),
        ),
    )
    analyzer = _sqlite_analyzer(supporting_markers=(b"self._sessions = {}",))

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.status == STATUS_COVERAGE_REQUIRED
    assert GATE_PROMOTION_BLOCKED_NEGATIVE_COVERAGE in result.reasons


def test_s_one_concrete_counterexample_contradicts_an_absence_without_coverage():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _negative_claim()
    request = _request(receipt, claim)
    analyzer = _sqlite_analyzer(contradicting_markers=(b"sqlite3.connect",))

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert request.coverage is None
    assert result.status == STATUS_CONTRADICTED
    assert result.relation == RELATION_CONTRADICTS
    assert result.promotion_status == PROMOTION_PROMOTED
    assert GATE_PROMOTION_BLOCKED_NEGATIVE_COVERAGE not in result.reasons


def test_t_valid_coverage_makes_supporting_an_absence_eligible():
    payload, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _negative_claim()
    request = _request(receipt, claim, coverage=_coverage(claim, receipt))
    analyzer = _sqlite_analyzer(supporting_markers=(b"self._sessions = {}",))

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.status == STATUS_VERIFIED
    assert result.relation == RELATION_SUPPORTS
    assert result.coverage_status == COVERAGE_SUFFICIENT
    assert result.promotion_status == PROMOTION_PROMOTED
    assert result.verified_evidence is not None
    assert result.verified_evidence.coverage_status == COVERAGE_SUFFICIENT


def test_evidence_1_cannot_mint_the_coverage_it_needs():
    """There is no constructor path from a payload to a coverage receipt."""
    import inspect

    from core import evidence_promotion_gate, evidence_verification

    for module in (evidence_promotion_gate, evidence_verification):
        source = inspect.getsource(module)
        assert "NegativeClaimCoverage(" not in source.replace(
            "class NegativeClaimCoverage(", ""
        ), module.__name__


def test_a_negative_request_must_declare_that_it_needs_coverage():
    _, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    with pytest.raises(ValueError, match="negative_coverage_required"):
        EvidenceVerificationRequest(
            proposition=_negative_claim(),
            requested_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
            acquisition_receipt_fingerprint=source_receipt_fingerprint(receipt),
            source_content_sha256=receipt.content_sha256,
            source_binding=receipt.source_binding,
            verification_constraints=(CONSTRAINT_ROLE_VERIFICATION_REQUIRED,),
        )


# =============================================================================
# 5. Epistemic distinctions
# =============================================================================

def test_u_a_verified_implementation_role_may_still_be_insufficient():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition("SessionStore encrypts session state at rest.")
    request = _request(receipt, claim)
    view = bounded_payload_view(payload, receipt)
    proposal = EvidenceVerificationProposal(
        proposition_id=claim.proposition_id,
        proposition_sha256=claim.proposition_sha256,
        source_identifier=receipt.candidate_identifier,
        source_content_sha256=payload.content_sha256,
        relation=RELATION_INSUFFICIENT,
        role_assessments=(
            RoleAssessment(
                role=ROLE_IMPLEMENTATION_AUTHORITY,
                status=ROLE_STATUS_VERIFIED,
                span_indexes=(0,),
                reasons=(ANALYSIS_ROLE_CONTENT_CONSISTENT,),
            ),
        ),
        evidence_spans=(span_from_view(view, 0, 60, SPAN_ROLE_EVIDENCE),),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([proposal])
    )

    assert result.verified_roles == (ROLE_IMPLEMENTATION_AUTHORITY,)
    assert result.status == STATUS_INSUFFICIENT
    assert result.relation == RELATION_INSUFFICIENT


def test_v_verified_validation_evidence_may_contradict():
    payload, receipt = _acquire(
        "tests/test_session_store.py",
        VALIDATION_TEST,
        (ROLE_VALIDATION_EVIDENCE,),
        (SOURCE_CLASS_VALIDATION_TEST,),
        domain=DOMAIN_VALIDATION_ARTIFACTS,
    )
    request = _request(
        receipt,
        _proposition(
            "The session-store tests expect state to be discarded on restart.",
            scope=SCOPE_VALIDATION_EXPECTATION,
        ),
    )
    analyzer = _sqlite_analyzer(
        contradicting_markers=(b"survives_a_restart",),
    )

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.verified_roles == (ROLE_VALIDATION_EVIDENCE,)
    assert result.relation == RELATION_CONTRADICTS
    assert result.status == STATUS_CONTRADICTED
    assert result.promotion_status == PROMOTION_PROMOTED


def test_w_a_historical_note_is_insufficient_for_a_current_implementation_claim():
    payload, receipt = _acquire(
        "docs/designs/rejected-sqlite.md",
        HISTORICAL_NOTE,
        (ROLE_HISTORICAL_CONTEXT,),
        (SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,),
    )
    request = _request(
        receipt,
        _proposition("SessionStore writes session state to SQLite."),
    )
    analyzer = _sqlite_analyzer()

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert b"sqlite3.connect" in HISTORICAL_NOTE
    assert result.verified_roles == (ROLE_HISTORICAL_CONTEXT,)
    assert result.status == STATUS_INSUFFICIENT
    assert GATE_RELATION_DOWNGRADED_ROLE_NOT_COMPETENT in result.reasons


def test_w_the_same_note_supports_a_historical_proposition():
    payload, receipt = _acquire(
        "docs/designs/rejected-sqlite.md",
        HISTORICAL_NOTE,
        (ROLE_HISTORICAL_CONTEXT,),
        (SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,),
    )
    request = _request(
        receipt,
        _proposition(
            "A rejected design proposed persisting sessions with SQLite.",
            scope=SCOPE_HISTORICAL_INTENT,
        ),
    )

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())

    assert result.status == STATUS_VERIFIED
    assert result.relation == RELATION_SUPPORTS


def test_x_a_manifest_declaration_is_insufficient_for_a_runtime_use_claim():
    payload, receipt = _acquire(
        "pyproject.toml",
        DEPENDENCY_MANIFEST,
        (ROLE_CONFIGURATION_AUTHORITY,),
        (SOURCE_CLASS_DEPENDENCY_MANIFEST,),
    )
    claim = _proposition(
        "The running harness persists sessions with sqlite-utils.",
        scope=SCOPE_RUNTIME_BEHAVIOUR,
    )
    request = _request(
        receipt,
        claim,
        current_state=_current_state(claim, receipt),
    )
    analyzer = _sqlite_analyzer(supporting_markers=(b"sqlite-utils",))

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.status == STATUS_INSUFFICIENT
    assert GATE_RELATION_DOWNGRADED_ROLE_NOT_COMPETENT in result.reasons


def test_y_a_test_expectation_is_insufficient_for_a_runtime_behaviour_claim():
    payload, receipt = _acquire(
        "tests/test_session_store.py",
        VALIDATION_TEST,
        (ROLE_VALIDATION_EVIDENCE,),
        (SOURCE_CLASS_VALIDATION_TEST,),
        domain=DOMAIN_VALIDATION_ARTIFACTS,
    )
    claim = _proposition(
        "The running harness persists session state across restarts.",
        scope=SCOPE_RUNTIME_BEHAVIOUR,
    )
    request = _request(
        receipt,
        claim,
        current_state=_current_state(claim, receipt),
    )
    analyzer = _sqlite_analyzer(supporting_markers=(b"survives_a_restart",))

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.status == STATUS_INSUFFICIENT
    assert GATE_RELATION_DOWNGRADED_ROLE_NOT_COMPETENT in result.reasons


def test_implementation_content_alone_does_not_establish_runtime_behaviour():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition(
        "The running harness persists sessions to SQLite.",
        scope=SCOPE_RUNTIME_BEHAVIOUR,
    )
    request = _request(receipt, claim)

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())

    assert result.status == STATUS_INSUFFICIENT
    assert GATE_PROMOTION_BLOCKED_CURRENT_STATE in result.reasons


def test_a_current_state_receipt_unlocks_a_runtime_behaviour_claim():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition(
        "The running harness persists sessions to SQLite.",
        scope=SCOPE_RUNTIME_BEHAVIOUR,
    )
    request = _request(receipt, claim, current_state=_current_state(claim, receipt))

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())

    assert result.status == STATUS_VERIFIED
    assert result.current_state_fingerprint is not None


def test_an_unestablished_current_state_receipt_still_blocks():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition(
        "The running harness persists sessions to SQLite.",
        scope=SCOPE_RUNTIME_BEHAVIOUR,
    )
    request = _request(
        receipt,
        claim,
        current_state=_current_state(claim, receipt, established=False),
    )

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())

    assert result.status == STATUS_INSUFFICIENT
    assert GATE_PROMOTION_BLOCKED_CURRENT_STATE in result.reasons


def test_role_verification_may_be_required_before_any_direction_is_accepted():
    payload, receipt = _acquire(
        "core/router.py",
        PLACEHOLDER_MODULE,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition("The router module implements SQLite persistence.")
    request = _request(receipt, claim)
    view = bounded_payload_view(payload, receipt)
    proposal = EvidenceVerificationProposal(
        proposition_id=claim.proposition_id,
        proposition_sha256=claim.proposition_sha256,
        source_identifier=receipt.candidate_identifier,
        source_content_sha256=payload.content_sha256,
        relation=RELATION_SUPPORTS,
        role_assessments=(
            RoleAssessment(
                role=ROLE_IMPLEMENTATION_AUTHORITY,
                status=ROLE_STATUS_REJECTED,
            ),
        ),
        evidence_spans=(span_from_view(view, 0, 30, SPAN_SUPPORTING),),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([proposal])
    )

    assert result.status == STATUS_INSUFFICIENT
    assert GATE_RELATION_DOWNGRADED_NO_VERIFIED_ROLE in result.reasons


def test_hypothesis_support_can_never_establish_any_scope():
    for scope, roles in SCOPE_COMPETENT_ROLES.items():
        assert ROLE_HYPOTHESIS_SUPPORT not in roles, scope


# =============================================================================
# 6. Evidence spans
# =============================================================================

def _support_proposal(
    claim: Proposition,
    receipt: SourceAcquisitionReceipt,
    payload: AcquiredSourcePayload,
    spans: tuple[EvidenceSpan, ...],
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
        evidence_spans=spans,
        reasons=(ANALYSIS_PROPOSITION_TERMS_PRESENT,),
    )


def _sqlite_case() -> tuple[
    AcquiredSourcePayload, SourceAcquisitionReceipt, Proposition, EvidenceVerificationRequest
]:
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition("SessionStore writes session state to SQLite.")
    return payload, receipt, claim, _request(receipt, claim)


def test_z_a_span_that_matches_the_acquired_bytes_is_accepted():
    payload, receipt, claim, request = _sqlite_case()
    view = bounded_payload_view(payload, receipt)
    start, end = view.locate(b"sqlite3.connect")
    proposal = _support_proposal(
        claim,
        receipt,
        payload,
        (span_from_view(view, start, end, SPAN_SUPPORTING, quote=True),),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([proposal])
    )

    assert result.status == STATUS_VERIFIED
    assert result.evidence_span_refs[0].start_byte == start
    assert result.evidence_span_refs[0].end_byte == end


def test_aa_a_span_outside_the_payload_is_rejected():
    payload, receipt, claim, request = _sqlite_case()
    beyond = payload.bytes_acquired + 64
    proposal = _support_proposal(
        claim,
        receipt,
        payload,
        (
            EvidenceSpan(
                start_byte=payload.bytes_acquired,
                end_byte=beyond,
                span_sha256=hashlib.sha256(b"invented").hexdigest(),
                purpose=SPAN_SUPPORTING,
                source_content_sha256=payload.content_sha256,
            ),
        ),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([proposal])
    )

    assert result.status == STATUS_ANALYSIS_INVALID
    assert GATE_ANALYZER_PROPOSAL_INVALID in result.reasons


def test_ab_a_span_with_the_wrong_digest_is_rejected():
    payload, receipt, claim, request = _sqlite_case()
    proposal = _support_proposal(
        claim,
        receipt,
        payload,
        (
            EvidenceSpan(
                start_byte=0,
                end_byte=32,
                span_sha256=hashlib.sha256(b"PluginKernel").hexdigest(),
                purpose=SPAN_SUPPORTING,
                source_content_sha256=payload.content_sha256,
            ),
        ),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([proposal])
    )

    assert result.status == STATUS_ANALYSIS_INVALID


def test_ac_a_zero_length_span_cannot_be_constructed():
    payload, receipt, _, _ = _sqlite_case()
    with pytest.raises(ValueError, match="at least one byte"):
        EvidenceSpan(
            start_byte=10,
            end_byte=10,
            span_sha256=hashlib.sha256(b"").hexdigest(),
            purpose=SPAN_SUPPORTING,
            source_content_sha256=payload.content_sha256,
        )


def test_ad_too_many_spans_cannot_be_constructed():
    payload, receipt, claim, _ = _sqlite_case()
    view = bounded_payload_view(payload, receipt)
    spans = tuple(
        span_from_view(view, index, index + 4, SPAN_SUPPORTING)
        for index in range(MAX_EVIDENCE_SPANS + 1)
    )
    with pytest.raises(ValueError, match="exceed their finite bound"):
        _support_proposal(claim, receipt, payload, spans)


def test_ae_total_cited_bytes_are_bounded():
    big = b"x" * (MAX_SPAN_BYTES * (MAX_EVIDENCE_SPANS - 1))
    payload, receipt = _acquire(
        "core/large_module.py",
        big,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _proposition("The large module writes session state to SQLite.")
    view = bounded_payload_view(payload, receipt)
    spans = tuple(
        span_from_view(
            view,
            index * MAX_SPAN_BYTES,
            (index + 1) * MAX_SPAN_BYTES,
            SPAN_SUPPORTING,
        )
        for index in range(MAX_EVIDENCE_SPANS - 1)
    )
    assert sum(item.byte_count for item in spans) > MAX_TOTAL_CITED_BYTES
    with pytest.raises(ValueError, match="total cited bytes"):
        _support_proposal(claim, receipt, payload, spans)


def test_af_a_supporting_relation_with_no_span_is_rejected():
    payload, receipt, claim, request = _sqlite_case()
    proposal = _support_proposal(claim, receipt, payload, ())

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([proposal])
    )

    assert result.status == STATUS_ANALYSIS_INVALID
    defects = proposal_defects(request, payload, receipt, proposal)
    assert any("supporting" in item for item in defects)


def test_ag_a_contradicting_relation_with_no_contradicting_span_is_rejected():
    payload, receipt, claim, request = _sqlite_case()
    view = bounded_payload_view(payload, receipt)
    proposal = EvidenceVerificationProposal(
        proposition_id=claim.proposition_id,
        proposition_sha256=claim.proposition_sha256,
        source_identifier=receipt.candidate_identifier,
        source_content_sha256=payload.content_sha256,
        relation=RELATION_CONTRADICTS,
        role_assessments=(
            RoleAssessment(
                role=ROLE_IMPLEMENTATION_AUTHORITY,
                status=ROLE_STATUS_VERIFIED,
            ),
        ),
        evidence_spans=(span_from_view(view, 0, 20, SPAN_ROLE_EVIDENCE),),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([proposal])
    )

    assert result.status == STATUS_ANALYSIS_INVALID


def test_a_quoted_span_must_be_byte_exact():
    payload, receipt, claim, request = _sqlite_case()
    view = bounded_payload_view(payload, receipt)
    honest = span_from_view(view, 0, 40, SPAN_SUPPORTING, quote=True)
    lying = EvidenceSpan(
        start_byte=honest.start_byte,
        end_byte=honest.end_byte,
        span_sha256=honest.span_sha256,
        purpose=honest.purpose,
        source_content_sha256=honest.source_content_sha256,
        quoted_text="class PluginKernel:  # not in this file",
    )

    result = verify_acquired_source(
        request,
        payload,
        receipt,
        ScriptedEvidenceAnalyzer([_support_proposal(claim, receipt, payload, (lying,))]),
    )

    assert result.status == STATUS_ANALYSIS_INVALID


def test_an_invented_symbol_cannot_be_cited_as_a_span():
    """The DeepSeek invented-symbol failure, reproduced and refused."""
    payload, receipt, claim, request = _sqlite_case()
    for invented in (b"PluginKernel", b"TrajectoryManager", b"StorageProvider"):
        assert invented not in payload.content
    forged = hashlib.sha256(b"class PluginKernel: ...").hexdigest()
    proposal = _support_proposal(
        claim,
        receipt,
        payload,
        (
            EvidenceSpan(
                start_byte=0,
                end_byte=24,
                span_sha256=forged,
                purpose=SPAN_SUPPORTING,
                source_content_sha256=payload.content_sha256,
            ),
        ),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([proposal])
    )

    assert result.status == STATUS_ANALYSIS_INVALID
    assert result.promotion_status == PROMOTION_NOT_PROMOTED


def test_an_invented_source_cannot_be_named():
    payload, receipt, claim, request = _sqlite_case()
    view = bounded_payload_view(payload, receipt)
    proposal = EvidenceVerificationProposal(
        proposition_id=claim.proposition_id,
        proposition_sha256=claim.proposition_sha256,
        source_identifier="core/plugin_kernel.py",
        source_content_sha256=payload.content_sha256,
        relation=RELATION_SUPPORTS,
        role_assessments=(
            RoleAssessment(
                role=ROLE_IMPLEMENTATION_AUTHORITY,
                status=ROLE_STATUS_VERIFIED,
            ),
        ),
        evidence_spans=(span_from_view(view, 0, 24, SPAN_SUPPORTING),),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([proposal])
    )

    assert result.status == STATUS_ANALYSIS_INVALID


def test_an_invented_role_cannot_be_assessed():
    payload, receipt, claim, request = _sqlite_case()
    view = bounded_payload_view(payload, receipt)
    proposal = EvidenceVerificationProposal(
        proposition_id=claim.proposition_id,
        proposition_sha256=claim.proposition_sha256,
        source_identifier=receipt.candidate_identifier,
        source_content_sha256=payload.content_sha256,
        relation=RELATION_SUPPORTS,
        role_assessments=(
            RoleAssessment(
                role=ROLE_IMPLEMENTATION_AUTHORITY,
                status=ROLE_STATUS_VERIFIED,
            ),
            RoleAssessment(
                role=ROLE_ARCHITECTURE_DESCRIPTION,
                status=ROLE_STATUS_VERIFIED,
            ),
        ),
        evidence_spans=(span_from_view(view, 0, 24, SPAN_SUPPORTING),),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([proposal])
    )

    assert ROLE_ARCHITECTURE_DESCRIPTION not in receipt.expected_roles
    assert result.status == STATUS_ANALYSIS_INVALID


def test_an_unavailable_analyzer_promotes_nothing():
    payload, receipt, _, request = _sqlite_case()
    analyzer = ScriptedEvidenceAnalyzer(
        [EvidenceAnalyzerUnavailable("the local model is not running")]
    )

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.status == STATUS_ANALYSIS_INVALID
    assert GATE_ANALYZER_UNAVAILABLE in result.reasons
    assert result.promotion_status == PROMOTION_NOT_PROMOTED


# =============================================================================
# 7. Promotion, receipts, determinism
# =============================================================================

def test_promotion_produces_a_verified_evidence_record_bound_to_everything():
    payload, receipt, claim, request = _sqlite_case()

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())
    evidence = result.verified_evidence

    assert evidence is not None
    assert evidence.proposition_sha256 == claim.proposition_sha256
    assert evidence.source_content_sha256 == payload.content_sha256
    assert evidence.acquisition_receipt_fingerprint == source_receipt_fingerprint(receipt)
    assert evidence.analyzer_proposal_fingerprint == result.analyzer_proposal_fingerprint
    assert GATE_EVIDENCE_PROMOTED in evidence.verification_reasons
    assert result.request_fingerprint == verification_request_fingerprint(request)


def test_insufficient_and_unrelated_record_an_assessment_without_promoting():
    payload, receipt = _acquire(
        "core/session_store_protocol.py",
        INTERFACE_ONLY,
        (ROLE_INTERFACE_CONTRACT,),
        (SOURCE_CLASS_INTERFACE_DEFINITION,),
    )
    request = _request(receipt, _proposition("SessionStore writes state to SQLite."))

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())

    assert result.status == STATUS_INSUFFICIENT
    assert result.verified_evidence is None
    assert result.promotion_status == PROMOTION_NOT_PROMOTED
    assert result.role_assessments


def test_contradiction_is_verified_evidence_of_the_same_standing():
    supporting_payload, supporting_receipt, claim, supporting_request = _sqlite_case()
    supporting = verify_acquired_source(
        supporting_request, supporting_payload, supporting_receipt, _sqlite_analyzer()
    )

    memory_payload, memory_receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    contradicting = verify_acquired_source(
        _request(memory_receipt, claim),
        memory_payload,
        memory_receipt,
        _sqlite_analyzer(contradicting_markers=(b"self._sessions[session_id] = state",)),
    )

    assert supporting.promoted is True
    assert contradicting.promoted is True
    assert supporting.relation == RELATION_SUPPORTS
    assert contradicting.relation == RELATION_CONTRADICTS
    assert supporting.verified_evidence is not None
    assert contradicting.verified_evidence is not None


def test_the_same_inputs_always_produce_the_same_result():
    payload, receipt, _, request = _sqlite_case()

    first = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())
    second = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())

    assert first.as_dict() == second.as_dict()
    assert first.verified_evidence is not None and second.verified_evidence is not None
    assert first.verified_evidence.evidence_id == second.verified_evidence.evidence_id
    assert render_evidence_verification_result_json(
        first
    ) == render_evidence_verification_result_json(second)


def test_a_different_proposition_produces_a_different_evidence_identity():
    payload, receipt, _, request = _sqlite_case()
    other_claim = _proposition(
        "SessionStore writes session state to SQLite, transactionally.",
        identifier="P-9",
    )
    other_request = _request(receipt, other_claim)

    first = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())
    second = verify_acquired_source(
        other_request, payload, receipt, _sqlite_analyzer()
    )

    assert first.verified_evidence is not None and second.verified_evidence is not None
    assert first.verified_evidence.evidence_id != second.verified_evidence.evidence_id


def test_a_serialized_result_never_reproduces_source_content():
    secret = b"CATTUS_EVIDENCE_CANARY_9d41ab"
    content = (
        b'"""Session storage backed by SQLite."""\n\nimport sqlite3\n\n'
        b"API_TOKEN = b'" + secret + b"'\n\n"
        b"def save_session(session_id, state):\n"
        b"    sqlite3.connect('sessions.db').execute('INSERT INTO sessions VALUES (?, ?)')\n"
    )
    payload, receipt = _acquire(
        "core/session_store.py",
        content,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    request = _request(
        receipt,
        _proposition("SessionStore writes session state to SQLite."),
    )

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())
    rendered = render_evidence_verification_result_json(result)

    assert result.status == STATUS_VERIFIED
    assert secret.decode() not in rendered
    assert "sqlite3.connect" not in rendered
    assert "save_session" not in rendered
    assert json.loads(rendered)["source_content_serialized"] is False
    assert result.verified_evidence is not None
    assert secret.decode() not in json.dumps(result.verified_evidence.as_dict())


def test_authority_and_guardrails_are_honest_and_narrow():
    payload, receipt, _, request = _sqlite_case()

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())
    rendered = json.loads(render_evidence_verification_result_json(result))

    authority = rendered["authority"]
    assert authority["evidence_verification_authority"] is True
    assert authority["evidence_promotion_authority"] is True
    assert authority["human_approval_required"] is True
    for denied in (
        "repository_read_authority",
        "repository_traversal_authority",
        "external_search_authority",
        "web_fetch_authority",
        "acquisition_authority",
        "context_selection_authority",
        "indexing_authority",
        "graph_authority",
        "validation_execution_authority",
        "command_execution_authority",
        "worker_launch_authority",
        "repository_write_authority",
        "patch_authority",
        "planning_authority",
        "routing_authority",
        "provider_selection_authority",
        "model_selection_authority",
        "project_evolution_authority",
        "claim_synthesis_authority",
        "final_claim_authority",
    ):
        assert authority[denied] is False, denied

    guardrails = rendered["guardrails"]
    assert guardrails["source_content_analyzed"] is True
    assert guardrails["evidence_verification_performed"] is True
    assert guardrails["model_called"] is False
    for never in (
        "repository_files_read",
        "repository_traversal_performed",
        "acquisition_performed",
        "candidate_selection_performed",
        "network_called",
        "web_search_performed",
        "validation_executed",
        "repository_written",
        "patch_created",
        "planning_performed",
        "claim_synthesis_performed",
        "final_claim_emitted",
        "source_content_serialized",
        "analyzer_reasoning_stored",
        "provider_selected_by_evidence_layer",
    ):
        assert guardrails[never] is False, never


def test_a_blocked_result_claims_no_verification_authority():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    request = _request(receipt, _proposition("SessionStore writes state to SQLite."))
    tampered, _ = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )

    result = verify_acquired_source(
        request, tampered, receipt, ScriptedEvidenceAnalyzer([])
    )
    rendered = json.loads(render_evidence_verification_result_json(result))

    assert rendered["authority"]["evidence_verification_authority"] is False
    assert rendered["authority"]["evidence_promotion_authority"] is False


def test_there_is_no_confidence_anywhere_in_a_result():
    payload, receipt, _, request = _sqlite_case()

    result = verify_acquired_source(request, payload, receipt, _sqlite_analyzer())
    rendered = render_evidence_verification_result_json(result).lower()

    for forbidden in ("confidence", "probability", "support_score", "likelihood"):
        assert forbidden not in rendered, forbidden


# =============================================================================
# 8. Multiple sources are recorded, never synthesized
# =============================================================================

def test_several_sources_are_independent_records_with_no_aggregate():
    claim = _proposition("SessionStore writes session state to SQLite.")

    sqlite_payload, sqlite_receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    memory_payload, memory_receipt = _acquire(
        "core/memory_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    interface_payload, interface_receipt = _acquire(
        "core/session_store_protocol.py",
        INTERFACE_ONLY,
        (ROLE_INTERFACE_CONTRACT,),
        (SOURCE_CLASS_INTERFACE_DEFINITION,),
    )

    results = (
        verify_acquired_source(
            _request(sqlite_receipt, claim),
            sqlite_payload,
            sqlite_receipt,
            _sqlite_analyzer(),
        ),
        verify_acquired_source(
            _request(memory_receipt, claim),
            memory_payload,
            memory_receipt,
            _sqlite_analyzer(
                contradicting_markers=(b"self._sessions[session_id] = state",)
            ),
        ),
        verify_acquired_source(
            _request(interface_receipt, claim),
            interface_payload,
            interface_receipt,
            _sqlite_analyzer(),
        ),
    )

    assert [item.relation for item in results] == [
        RELATION_SUPPORTS,
        RELATION_CONTRADICTS,
        RELATION_INSUFFICIENT,
    ]
    rendered = json.loads(render_verification_set_json(results))
    assert rendered["aggregated"] is False
    assert rendered["claim_synthesized"] is False
    assert rendered["majority_computed"] is False
    assert rendered["confidence_computed"] is False
    assert len(rendered["results"]) == 3


# =============================================================================
# 9. Anti-DeepSeek regression
# =============================================================================

def test_the_deepseek_negative_architecture_claim_cannot_be_confirmed_from_one_file():
    """One partial reading must not become a confident architectural absence."""
    payload, receipt = _acquire(
        "core/router.py",
        PLACEHOLDER_MODULE,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _negative_claim()
    request = _request(receipt, claim)
    view = bounded_payload_view(payload, receipt)
    over_confident = EvidenceVerificationProposal(
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
        evidence_spans=(span_from_view(view, 0, 40, SPAN_SUPPORTING),),
    )

    result = verify_acquired_source(
        request, payload, receipt, ScriptedEvidenceAnalyzer([over_confident])
    )

    assert result.status == STATUS_COVERAGE_REQUIRED
    assert result.relation != RELATION_SUPPORTS
    assert result.promotion_status == PROMOTION_NOT_PROMOTED
    assert GATE_PROMOTION_BLOCKED_NEGATIVE_COVERAGE in result.reasons


def test_the_deepseek_negative_claim_is_contradicted_by_one_real_implementation():
    payload, receipt = _acquire(
        "core/session_store.py",
        SQLITE_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _negative_claim()
    request = _request(receipt, claim)
    analyzer = _sqlite_analyzer(contradicting_markers=(b"sqlite3.connect",))

    result = verify_acquired_source(request, payload, receipt, analyzer)

    assert result.status == STATUS_CONTRADICTED
    assert result.promotion_status == PROMOTION_PROMOTED
    assert result.verified_evidence is not None
    assert result.verified_evidence.relation == RELATION_CONTRADICTS


# =============================================================================
# 10. Bounded repair
# =============================================================================

class _RepairingAnalyzer:
    """An analyzer whose first answer is malformed and whose second is not."""

    name = "repairing_test_analyzer"

    def __init__(self, first: EvidenceVerificationProposal, second: EvidenceVerificationProposal):
        self._answers = [first, second]
        self.last_proposal: EvidenceVerificationProposal | None = None
        self.analyze_calls = 0
        self.repair_calls = 0
        self.repair_defects: tuple[str, ...] = ()

    def analyze(self, request, view):
        self.analyze_calls += 1
        self.last_proposal = self._answers[0]
        return self._answers[0]

    def repair(self, request, view, defects):
        self.repair_calls += 1
        self.repair_defects = defects
        self.last_proposal = self._answers[1]
        return self._answers[1]


def test_a_single_bounded_repair_may_fix_a_structural_defect():
    payload, receipt, claim, request = _sqlite_case()
    view = bounded_payload_view(payload, receipt)
    broken = _support_proposal(claim, receipt, payload, ())
    fixed = _support_proposal(
        claim,
        receipt,
        payload,
        (span_from_view(view, 0, 48, SPAN_SUPPORTING),),
    )
    analyzer = _RepairingAnalyzer(broken, fixed)

    result = verify_with_bounded_repair(request, payload, receipt, analyzer)

    assert analyzer.analyze_calls == 1
    assert analyzer.repair_calls == 1
    assert analyzer.repair_defects
    assert result.status == STATUS_VERIFIED


def test_repair_happens_at_most_once():
    payload, receipt, claim, request = _sqlite_case()
    broken = _support_proposal(claim, receipt, payload, ())
    analyzer = _RepairingAnalyzer(broken, broken)

    result = verify_with_bounded_repair(request, payload, receipt, analyzer)

    assert analyzer.analyze_calls == 1
    assert analyzer.repair_calls == 1
    assert result.status == STATUS_ANALYSIS_INVALID
    assert result.promotion_status == PROMOTION_NOT_PROMOTED


def test_repair_is_never_attempted_for_a_binding_failure():
    payload, receipt, claim, request = _sqlite_case()
    tampered, _ = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    broken = _support_proposal(claim, receipt, payload, ())
    analyzer = _RepairingAnalyzer(broken, broken)

    result = verify_with_bounded_repair(request, tampered, receipt, analyzer)

    assert result.status == STATUS_BINDING_INVALID
    assert analyzer.analyze_calls == 0
    assert analyzer.repair_calls == 0


# =============================================================================
# 11. Contract construction guards
# =============================================================================

def test_a_proposition_digest_covers_text_type_and_scope():
    base = _proposition("SessionStore writes session state to SQLite.")
    reworded = _proposition("SessionStore writes session state to SQLite databases.")
    rescoped = _proposition(
        "SessionStore writes session state to SQLite.",
        scope=SCOPE_RUNTIME_BEHAVIOUR,
    )
    retyped = _proposition(
        "SessionStore writes session state to SQLite.",
        proposition_type=PROPOSITION_NEGATIVE_EXISTENTIAL,
    )

    digests = {
        base.proposition_sha256,
        reworded.proposition_sha256,
        rescoped.proposition_sha256,
        retyped.proposition_sha256,
    }
    assert len(digests) == 4


def test_an_unknown_proposition_type_is_refused():
    with pytest.raises(ValueError, match="unsupported proposition type"):
        Proposition(
            proposition_id="P-1",
            text="Something is probably true.",
            proposition_type="probably_true",
            scope=SCOPE_IMPLEMENTATION_STATE,
        )


def test_an_unknown_relation_is_refused():
    payload, receipt, claim, _ = _sqlite_case()
    with pytest.raises(ValueError, match="unsupported proposition relation"):
        EvidenceVerificationProposal(
            proposition_id=claim.proposition_id,
            proposition_sha256=claim.proposition_sha256,
            source_identifier=receipt.candidate_identifier,
            source_content_sha256=payload.content_sha256,
            relation="probably_supports",
        )


def test_sufficient_coverage_may_not_leave_a_requirement_uncovered():
    _, receipt = _acquire(
        "core/session_store.py",
        MEMORY_IMPLEMENTATION,
        (ROLE_IMPLEMENTATION_AUTHORITY,),
        (SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
    )
    claim = _negative_claim()
    with pytest.raises(ValueError, match="may not leave a requirement uncovered"):
        _coverage(claim, receipt, uncovered=(ROLE_IMPLEMENTATION_AUTHORITY,))


def test_direct_context_has_no_bytes_to_verify():
    """ACQUIRE.3 direct context is a reference, not a payload, by construction."""
    with pytest.raises(ValueError, match="repository-read binding"):
        binding = _binding(
            "supplied_context:" + _digest("prompt"),
            acquisition_mode=MODE_EXISTING_CONTEXT,
            inventory_fingerprint=None,
            repository_identity=None,
        )
        AcquiredSourcePayload(
            candidate_identifier=binding.candidate_identifier,
            content=b"pasted text",
            content_sha256=hashlib.sha256(b"pasted text").hexdigest(),
            bytes_acquired=len(b"pasted text"),
            source_binding=binding,
        )


def test_every_scope_names_at_least_one_competent_role():
    from core.evidence_verification import PROPOSITION_SCOPES

    for scope in PROPOSITION_SCOPES:
        assert SCOPE_COMPETENT_ROLES[scope], scope
