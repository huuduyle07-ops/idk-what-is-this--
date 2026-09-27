"""EVIDENCE.1 — the deterministic promotion gate.

    EvidenceVerificationRequest + AcquiredSourcePayload + SourceAcquisitionReceipt
        -> binding gate                     [here, before any analysis]
        -> analyzable-source gate           [here]
        -> analyzer proposal                [core.evidence_analyzer]
        -> proposal gate                    [here]
        -> relation adjudication            [here]
        -> EvidenceVerificationResult

The gate is the authority.  An analyzer proposes what bytes mean; every
contractual fact — which roles verified, which way the evidence points, whether
anything is promoted — is decided here from records the analyzer never touches.

Order matters, and the order is deliberate.

**Bindings first, before a single byte is shown to anybody.**  A tampered
payload, a receipt that no longer fingerprints to the request, a source that was
never acquired, a coverage receipt bound to a different claim: each fails closed
with ``binding_invalid`` and no analyzer is called at all.  Analyzing bytes
whose provenance is already broken would produce a confident answer about
nothing.

**The payload is authoritative for content identity.**  The gate re-hashes the
bytes ACQUIRE.3 handed over and compares them to the receipt.  It never reopens
the path, because the question is what *those* bytes establish, not what happens
to be on disk now.

**A proposal is checked against records, not trusted.**  Proposition identity,
source identity, the expected-role subset and every span digest are re-derived
from the request, the receipt and the payload.  A span the analyzer reasoned
about rather than read has no matching digest and cannot survive.

**Direction is adjudicated last, and downgrades are explicit.**  A supported or
contradicted relation must clear role verification, scope competence,
currentness where the scope is about a running system, and coverage where the
claim is an absence.  Every downgrade names itself with a stable reason instead
of quietly becoming ``insufficient``.

The module is stdlib-only and pure.  It reads no file, reopens no path, walks no
directory, contacts no service, imports no model stack, acquires nothing,
executes nothing, and synthesizes no claim across sources.
"""

from __future__ import annotations

import hashlib

from core.content_acquisition import (
    AUTHORITY_NOT_VERIFIED,
    SOURCE_ACQUIRED,
    VERIFICATION_UNVERIFIED,
    AcquiredSourcePayload,
    SourceAcquisitionReceipt,
)
from core.evidence_analyzer import (
    EvidenceAnalysisError,
    EvidenceAnalyzer,
)
from core.evidence_verification import (
    COVERAGE_NOT_APPLICABLE,
    COVERAGE_NOT_SUPPLIED,
    CONSTRAINT_ROLE_VERIFICATION_REQUIRED,
    DIRECTIONAL_RELATIONS,
    GATE_ANALYZER_PROPOSAL_INVALID,
    GATE_ANALYZER_UNAVAILABLE,
    GATE_EVIDENCE_NOT_PROMOTED,
    GATE_EVIDENCE_PROMOTED,
    GATE_EVIDENCE_SPANS_VERIFIED,
    GATE_NO_CLAIM_SYNTHESIS_PERFORMED,
    GATE_PROMOTION_BLOCKED_CURRENT_STATE,
    GATE_PROMOTION_BLOCKED_NEGATIVE_COVERAGE,
    GATE_PROPOSITION_BINDING_VERIFIED,
    GATE_RELATION_ACCEPTED,
    GATE_RELATION_DOWNGRADED_NO_VERIFIED_ROLE,
    GATE_RELATION_DOWNGRADED_ROLE_NOT_COMPETENT,
    GATE_REQUESTED_ROLE_NOT_EXPECTED,
    GATE_ROLES_WITHIN_EXPECTED,
    GATE_SOURCE_BINDING_VERIFIED,
    GATE_SOURCE_NOT_ANALYZABLE,
    INCONSISTENT_CANDIDATE_IDENTITY,
    INCONSISTENT_COVERAGE_BINDING,
    INCONSISTENT_CURRENT_STATE_BINDING,
    INCONSISTENT_PAYLOAD_BYTE_COUNT,
    INCONSISTENT_PAYLOAD_DIGEST,
    INCONSISTENT_RECEIPT_FINGERPRINT,
    INCONSISTENT_SOURCE_ALREADY_VERIFIED,
    INCONSISTENT_SOURCE_AUTHORITY_CLAIMED,
    INCONSISTENT_SOURCE_BINDING,
    INCONSISTENT_SOURCE_NOT_ACQUIRED,
    LEVEL_ANALYZER_ASSESSED,
    LEVEL_DETERMINISTICALLY_VERIFIED,
    LEVEL_NOT_ESTABLISHED,
    MAX_EVIDENCE_SPANS,
    MAX_SPAN_BYTES,
    MAX_TOTAL_CITED_BYTES,
    PROMOTION_NOT_PROMOTED,
    PROMOTION_PROMOTED,
    RELATION_CONTRADICTS,
    RELATION_INSUFFICIENT,
    RELATION_SPAN_PURPOSE,
    RELATION_SUPPORTS,
    RELATION_UNRELATED,
    ROLE_STATUS_VERIFIED,
    STATUS_ANALYSIS_INVALID,
    STATUS_BINDING_INVALID,
    STATUS_CONTRADICTED,
    STATUS_COVERAGE_REQUIRED,
    STATUS_INSUFFICIENT,
    STATUS_UNRELATED,
    STATUS_UNSUPPORTED_SOURCE,
    STATUS_VERIFIED,
    VERIFICATION_INCONSISTENCIES,
    VERIFICATION_REASONS,
    EvidenceSpanRef,
    EvidenceVerificationProposal,
    EvidenceVerificationRequest,
    EvidenceVerificationResult,
    VerificationLevels,
    VerifiedEvidence,
    bounded_payload_view,
    coverage_fingerprint,
    current_state_fingerprint,
    proposal_fingerprint,
    source_receipt_fingerprint,
    verification_request_fingerprint,
)


PHASE_ID = "EVIDENCE.1"


def _ordered_reasons(codes: set[str]) -> tuple[str, ...]:
    return tuple(item for item in VERIFICATION_REASONS if item in codes)


def _ordered_inconsistencies(codes: set[str]) -> tuple[str, ...]:
    return tuple(item for item in VERIFICATION_INCONSISTENCIES if item in codes)


# ── What the gate established, and by what means ──────────────────────────────

def _refusal_levels(*, binding_verified: bool) -> VerificationLevels:
    """Levels for an outcome that never reached content analysis.

    Nothing was cited, no role was assessed and no relation was proposed, so
    three dimensions are honestly ``not_established``.  Whether the binding gate
    itself passed is a real fact and is recorded either way.
    """
    return VerificationLevels(
        source_binding=(
            LEVEL_DETERMINISTICALLY_VERIFIED
            if binding_verified
            else LEVEL_NOT_ESTABLISHED
        ),
    )


def _analysis_levels(proposal: EvidenceVerificationProposal) -> VerificationLevels:
    """Levels for an outcome that survived the binding and proposal gates.

    Bindings, citations and role admissibility were re-derived here from bytes
    and digests.  The relation was not: it is what the analyzer proposed, and
    the gate accepted it after checking everything *around* it.  That is
    ``analyzer_assessed``, and no combination of passing structural checks
    promotes it further.
    """
    return VerificationLevels(
        source_binding=LEVEL_DETERMINISTICALLY_VERIFIED,
        citation_integrity=(
            LEVEL_DETERMINISTICALLY_VERIFIED
            if proposal.evidence_spans
            else LEVEL_NOT_ESTABLISHED
        ),
        role_admissibility=(
            LEVEL_DETERMINISTICALLY_VERIFIED
            if proposal.role_assessments
            else LEVEL_NOT_ESTABLISHED
        ),
        semantic_relation=LEVEL_ANALYZER_ASSESSED,
    )


# ── Binding gate ──────────────────────────────────────────────────────────────

def binding_inconsistencies(
    request: EvidenceVerificationRequest,
    payload: AcquiredSourcePayload,
    receipt: SourceAcquisitionReceipt,
) -> tuple[str, ...]:
    """Every reason this material may not be analyzed, re-derived from scratch.

    Nothing here trusts a stored flag.  The payload bytes are re-hashed, the
    receipt is re-fingerprinted, and the identity chain ACQUIRE.3 wrote is
    compared field by field to the one the request carries.
    """
    found: set[str] = set()

    identifier = request.source_binding.candidate_identifier
    if (
        payload.candidate_identifier != identifier
        or receipt.candidate_identifier != identifier
    ):
        found.add(INCONSISTENT_CANDIDATE_IDENTITY)

    actual_digest = hashlib.sha256(payload.content).hexdigest()
    if (
        actual_digest != payload.content_sha256
        or payload.content_sha256 != receipt.content_sha256
        or payload.content_sha256 != request.source_content_sha256
    ):
        found.add(INCONSISTENT_PAYLOAD_DIGEST)

    if (
        payload.bytes_acquired != len(payload.content)
        or payload.bytes_acquired != receipt.bytes_acquired
    ):
        found.add(INCONSISTENT_PAYLOAD_BYTE_COUNT)

    if (
        payload.source_binding != request.source_binding
        or receipt.source_binding != request.source_binding
    ):
        found.add(INCONSISTENT_SOURCE_BINDING)

    if source_receipt_fingerprint(receipt) != request.acquisition_receipt_fingerprint:
        found.add(INCONSISTENT_RECEIPT_FINGERPRINT)

    if receipt.acquisition_status != SOURCE_ACQUIRED:
        found.add(INCONSISTENT_SOURCE_NOT_ACQUIRED)
    if receipt.verification_status != VERIFICATION_UNVERIFIED:
        found.add(INCONSISTENT_SOURCE_ALREADY_VERIFIED)
    if receipt.authority_status != AUTHORITY_NOT_VERIFIED:
        found.add(INCONSISTENT_SOURCE_AUTHORITY_CLAIMED)

    coverage = request.coverage
    if coverage is not None:
        binding = request.source_binding
        if (
            coverage.proposition_id != request.proposition.proposition_id
            or coverage.proposition_sha256 != request.proposition.proposition_sha256
            or coverage.acquisition_request_fingerprint
            != binding.acquisition_request_fingerprint
            or coverage.candidate_pool_fingerprint != binding.candidate_receipt_fingerprint
        ):
            found.add(INCONSISTENT_COVERAGE_BINDING)

    current_state = request.current_state
    if current_state is not None:
        if (
            current_state.proposition_id != request.proposition.proposition_id
            or current_state.proposition_sha256 != request.proposition.proposition_sha256
            or current_state.candidate_identifier != identifier
            or current_state.source_content_sha256 != request.source_content_sha256
            or current_state.acquisition_receipt_fingerprint
            != request.acquisition_receipt_fingerprint
        ):
            found.add(INCONSISTENT_CURRENT_STATE_BINDING)

    return _ordered_inconsistencies(found)


# ── Proposal gate ─────────────────────────────────────────────────────────────

def proposal_defects(
    request: EvidenceVerificationRequest,
    payload: AcquiredSourcePayload,
    receipt: SourceAcquisitionReceipt,
    proposal: EvidenceVerificationProposal,
) -> tuple[str, ...]:
    """Bounded, human-readable defects in one proposal.

    These strings are diagnostic, not a receipt vocabulary: they name the exact
    structural failure so an optional single repair can be aimed at it, and they
    never reach a serialized result.
    """
    defects: list[str] = []

    if proposal.proposition_id != request.proposition.proposition_id:
        defects.append(
            "proposition_id does not match the supplied proposition; the analyzer "
            "may not rename, replace or invent the claim under test"
        )
    if proposal.proposition_sha256 != request.proposition.proposition_sha256:
        defects.append(
            "proposition_sha256 does not match the supplied proposition; the claim "
            "text, type or scope was altered"
        )
    if proposal.source_identifier != receipt.candidate_identifier:
        defects.append(
            "source_identifier names a source that was not the one acquired; the "
            "analyzer may not introduce another source"
        )
    if proposal.source_content_sha256 != payload.content_sha256:
        defects.append(
            "source_content_sha256 does not match the acquired payload digest"
        )

    expected = set(receipt.expected_roles)
    for assessment in proposal.role_assessments:
        if assessment.role not in expected:
            defects.append(
                f"role {assessment.role!r} was never an expected role for this source; "
                "verified roles are a subset of expected roles"
            )

    if len(proposal.evidence_spans) > MAX_EVIDENCE_SPANS:
        defects.append("more evidence spans than the contract permits")
    total = 0
    for position, span in enumerate(proposal.evidence_spans):
        if span.source_content_sha256 != payload.content_sha256:
            defects.append(f"span {position} does not belong to the acquired payload")
            continue
        if span.start_byte >= span.end_byte:
            defects.append(f"span {position} cites no bytes")
            continue
        if span.end_byte > payload.bytes_acquired:
            defects.append(
                f"span {position} reaches past the end of the acquired payload"
            )
            continue
        if span.byte_count > MAX_SPAN_BYTES:
            defects.append(f"span {position} exceeds the per-span byte ceiling")
            continue
        cited = payload.content[span.start_byte : span.end_byte]
        if hashlib.sha256(cited).hexdigest() != span.span_sha256:
            defects.append(
                f"span {position} digest does not match the bytes it cites; the "
                "citation was not read out of this payload"
            )
            continue
        if span.quoted_text is not None:
            try:
                decoded = cited.decode("utf-8")
            except UnicodeDecodeError:
                decoded = None
            if decoded is None or decoded != span.quoted_text:
                defects.append(
                    f"span {position} quotes text that is not byte-exactly the range "
                    "it cites"
                )
                continue
        total += span.byte_count
    if total > MAX_TOTAL_CITED_BYTES:
        defects.append("total cited bytes exceed the contract ceiling")

    if proposal.relation in DIRECTIONAL_RELATIONS:
        required_purpose = RELATION_SPAN_PURPOSE[proposal.relation]
        if not proposal.spans_for(required_purpose):
            defects.append(
                f"a {proposal.relation!r} relation must cite at least one "
                f"{required_purpose!r} span"
            )

    return tuple(defects)


# ── Result builders ───────────────────────────────────────────────────────────

def _refusal(
    request: EvidenceVerificationRequest,
    receipt: SourceAcquisitionReceipt,
    *,
    status: str,
    reasons: set[str],
    inconsistencies: set[str] | None = None,
    relation: str | None = None,
    coverage_status: str = COVERAGE_NOT_APPLICABLE,
    analyzer_name: str | None = None,
    analyzer_proposal_fingerprint: str | None = None,
) -> EvidenceVerificationResult:
    binding_verified = GATE_SOURCE_BINDING_VERIFIED in reasons
    reasons = set(reasons) | {GATE_NO_CLAIM_SYNTHESIS_PERFORMED, GATE_EVIDENCE_NOT_PROMOTED}
    return EvidenceVerificationResult(
        status=status,
        proposition_id=request.proposition.proposition_id,
        proposition_sha256=request.proposition.proposition_sha256,
        proposition_type=request.proposition.proposition_type,
        proposition_scope=request.proposition.scope,
        source_identifier=receipt.candidate_identifier,
        source_content_sha256=request.source_content_sha256,
        acquisition_receipt_fingerprint=request.acquisition_receipt_fingerprint,
        request_fingerprint=verification_request_fingerprint(request),
        relation=relation,
        verification_levels=_refusal_levels(binding_verified=binding_verified),
        coverage_status=coverage_status,
        promotion_status=PROMOTION_NOT_PROMOTED,
        analyzer_name=analyzer_name,
        analyzer_proposal_fingerprint=analyzer_proposal_fingerprint,
        coverage_receipt_fingerprint=(
            None if request.coverage is None else coverage_fingerprint(request.coverage)
        ),
        current_state_fingerprint=(
            None
            if request.current_state is None
            else current_state_fingerprint(request.current_state)
        ),
        reasons=_ordered_reasons(reasons),
        inconsistencies=_ordered_inconsistencies(inconsistencies or set()),
        source_content_analyzed=False,
        model_called=False,
    )


def _coverage_status_for(request: EvidenceVerificationRequest) -> str:
    if not request.proposition.requires_coverage_to_support:
        return COVERAGE_NOT_APPLICABLE
    if request.coverage is None:
        return COVERAGE_NOT_SUPPLIED
    return request.coverage.coverage_status


# ── The entry point ───────────────────────────────────────────────────────────

def verify_acquired_source(
    request: EvidenceVerificationRequest,
    payload: AcquiredSourcePayload,
    receipt: SourceAcquisitionReceipt,
    analyzer: EvidenceAnalyzer,
    *,
    model_called: bool = False,
) -> EvidenceVerificationResult:
    """Verify one acquired source against one supplied proposition.

    ``model_called`` is telemetry the caller reports about its own analyzer; it
    changes no decision and grants nothing.  The gate itself contacts nothing.
    """
    if not isinstance(request, EvidenceVerificationRequest):
        raise TypeError("verify_acquired_source requires an EvidenceVerificationRequest")
    if not isinstance(payload, AcquiredSourcePayload):
        raise TypeError("verify_acquired_source requires an AcquiredSourcePayload")
    if not isinstance(receipt, SourceAcquisitionReceipt):
        raise TypeError("verify_acquired_source requires a SourceAcquisitionReceipt")
    if analyzer is None or not hasattr(analyzer, "analyze"):
        raise TypeError("verify_acquired_source requires an EvidenceAnalyzer")
    if not isinstance(model_called, bool):
        raise TypeError("model_called must be a bool")

    analyzer_name = str(getattr(analyzer, "name", "unnamed_evidence_analyzer"))

    # 1 ── bindings, before anything is analyzed.
    inconsistencies = binding_inconsistencies(request, payload, receipt)
    if inconsistencies:
        return _refusal(
            request,
            receipt,
            status=STATUS_BINDING_INVALID,
            reasons=set(),
            inconsistencies=set(inconsistencies),
            analyzer_name=None,
        )

    # 2 ── is this source even the kind of thing the request asks about?
    if not set(request.requested_roles) <= set(receipt.expected_roles):
        return _refusal(
            request,
            receipt,
            status=STATUS_UNSUPPORTED_SOURCE,
            reasons={GATE_SOURCE_BINDING_VERIFIED, GATE_REQUESTED_ROLE_NOT_EXPECTED},
            analyzer_name=None,
        )
    if not receipt.expected_roles:
        return _refusal(
            request,
            receipt,
            status=STATUS_UNSUPPORTED_SOURCE,
            reasons={GATE_SOURCE_BINDING_VERIFIED, GATE_SOURCE_NOT_ANALYZABLE},
            analyzer_name=None,
        )

    view = bounded_payload_view(payload, receipt)

    # 3 ── the one analyzer call.  No retry, no second provider, no escalation.
    try:
        proposal = analyzer.analyze(request, view)
    except EvidenceAnalysisError:
        return _refusal(
            request,
            receipt,
            status=STATUS_ANALYSIS_INVALID,
            reasons={GATE_SOURCE_BINDING_VERIFIED, GATE_ANALYZER_UNAVAILABLE},
            analyzer_name=analyzer_name,
        )
    if not isinstance(proposal, EvidenceVerificationProposal):
        return _refusal(
            request,
            receipt,
            status=STATUS_ANALYSIS_INVALID,
            reasons={GATE_SOURCE_BINDING_VERIFIED, GATE_ANALYZER_PROPOSAL_INVALID},
            analyzer_name=analyzer_name,
        )

    defects = proposal_defects(request, payload, receipt, proposal)
    if defects:
        return _refusal(
            request,
            receipt,
            status=STATUS_ANALYSIS_INVALID,
            reasons={GATE_SOURCE_BINDING_VERIFIED, GATE_ANALYZER_PROPOSAL_INVALID},
            analyzer_name=analyzer_name,
            analyzer_proposal_fingerprint=proposal_fingerprint(proposal),
        )

    return adjudicate(
        request,
        receipt,
        proposal,
        analyzer_name=analyzer_name,
        model_called=model_called,
    )


# ── Relation adjudication ─────────────────────────────────────────────────────

def adjudicate(
    request: EvidenceVerificationRequest,
    receipt: SourceAcquisitionReceipt,
    proposal: EvidenceVerificationProposal,
    *,
    analyzer_name: str,
    model_called: bool = False,
) -> EvidenceVerificationResult:
    """Turn a structurally valid proposal into a contractual outcome.

    Called only after the binding and proposal gates have passed; separated so
    the adjudication rules can be exercised directly.
    """
    proposition = request.proposition
    reasons: set[str] = {
        GATE_SOURCE_BINDING_VERIFIED,
        GATE_PROPOSITION_BINDING_VERIFIED,
        GATE_ROLES_WITHIN_EXPECTED,
        GATE_NO_CLAIM_SYNTHESIS_PERFORMED,
    }
    if proposal.evidence_spans:
        reasons.add(GATE_EVIDENCE_SPANS_VERIFIED)

    verified_roles = proposal.verified_roles
    relation = proposal.relation
    coverage_status = _coverage_status_for(request)
    levels = _analysis_levels(proposal)

    if relation in DIRECTIONAL_RELATIONS:
        blocked: set[str] = set()

        role_required = (
            CONSTRAINT_ROLE_VERIFICATION_REQUIRED in request.verification_constraints
        )
        if role_required and not verified_roles:
            blocked.add(GATE_RELATION_DOWNGRADED_NO_VERIFIED_ROLE)

        # Scope competence: what a verified role *is* decides whether it could
        # establish this kind of fact at all, in either direction.  It never
        # decides which direction the evidence points.
        if not (set(verified_roles) & proposition.competent_roles):
            blocked.add(GATE_RELATION_DOWNGRADED_ROLE_NOT_COMPETENT)

        # Currentness: code existing is not code running.
        if proposition.requires_current_state:
            current_state = request.current_state
            if current_state is None or not current_state.is_established:
                blocked.add(GATE_PROMOTION_BLOCKED_CURRENT_STATE)

        # Coverage: absence needs the space searched; a counterexample does not.
        if relation == RELATION_SUPPORTS and proposition.requires_coverage_to_support:
            coverage = request.coverage
            if (
                coverage is None
                or not coverage.is_sufficient
                or not coverage.covers_receipt(request.acquisition_receipt_fingerprint)
            ):
                blocked.add(GATE_PROMOTION_BLOCKED_NEGATIVE_COVERAGE)

        if blocked:
            reasons |= blocked
            reasons.add(GATE_EVIDENCE_NOT_PROMOTED)
            status = (
                STATUS_COVERAGE_REQUIRED
                if GATE_PROMOTION_BLOCKED_NEGATIVE_COVERAGE in blocked
                else STATUS_INSUFFICIENT
            )
            return _decided(
                request,
                receipt,
                proposal,
                status=status,
                relation=RELATION_INSUFFICIENT,
                reasons=reasons,
                levels=levels,
                coverage_status=coverage_status,
                analyzer_name=analyzer_name,
                model_called=model_called,
                evidence=None,
            )

        reasons.add(GATE_RELATION_ACCEPTED)
        reasons.add(GATE_EVIDENCE_PROMOTED)
        span_refs = tuple(span.as_ref() for span in proposal.evidence_spans)
        evidence = VerifiedEvidence(
            proposition_id=proposition.proposition_id,
            proposition_sha256=proposition.proposition_sha256,
            source_identifier=receipt.candidate_identifier,
            source_content_sha256=request.source_content_sha256,
            acquisition_receipt_fingerprint=request.acquisition_receipt_fingerprint,
            verified_roles=verified_roles,
            rejected_roles=proposal.rejected_roles,
            relation=relation,
            evidence_span_refs=span_refs,
            coverage_status=coverage_status,
            verification_reasons=_ordered_reasons(reasons),
            analyzer_proposal_fingerprint=proposal_fingerprint(proposal),
            verification_levels=levels,
        )
        status = STATUS_VERIFIED if relation == RELATION_SUPPORTS else STATUS_CONTRADICTED
        return _decided(
            request,
            receipt,
            proposal,
            status=status,
            relation=relation,
            reasons=reasons,
            levels=levels,
            coverage_status=coverage_status,
            analyzer_name=analyzer_name,
            model_called=model_called,
            evidence=evidence,
        )

    reasons.add(GATE_RELATION_ACCEPTED)
    reasons.add(GATE_EVIDENCE_NOT_PROMOTED)
    status = STATUS_UNRELATED if relation == RELATION_UNRELATED else STATUS_INSUFFICIENT
    return _decided(
        request,
        receipt,
        proposal,
        status=status,
        relation=relation,
        reasons=reasons,
        levels=levels,
        coverage_status=coverage_status,
        analyzer_name=analyzer_name,
        model_called=model_called,
        evidence=None,
    )


def _decided(
    request: EvidenceVerificationRequest,
    receipt: SourceAcquisitionReceipt,
    proposal: EvidenceVerificationProposal,
    *,
    status: str,
    relation: str,
    reasons: set[str],
    levels: VerificationLevels,
    coverage_status: str,
    analyzer_name: str,
    model_called: bool,
    evidence: VerifiedEvidence | None,
) -> EvidenceVerificationResult:
    span_refs: tuple[EvidenceSpanRef, ...] = tuple(
        span.as_ref() for span in proposal.evidence_spans
    )
    return EvidenceVerificationResult(
        status=status,
        proposition_id=request.proposition.proposition_id,
        proposition_sha256=request.proposition.proposition_sha256,
        proposition_type=request.proposition.proposition_type,
        proposition_scope=request.proposition.scope,
        source_identifier=receipt.candidate_identifier,
        source_content_sha256=request.source_content_sha256,
        acquisition_receipt_fingerprint=request.acquisition_receipt_fingerprint,
        request_fingerprint=verification_request_fingerprint(request),
        relation=relation,
        role_assessments=proposal.role_assessments,
        evidence_span_refs=span_refs,
        verification_levels=levels,
        coverage_status=coverage_status,
        promotion_status=(
            PROMOTION_PROMOTED if evidence is not None else PROMOTION_NOT_PROMOTED
        ),
        verified_evidence=evidence,
        analyzer_proposal_fingerprint=proposal_fingerprint(proposal),
        coverage_receipt_fingerprint=(
            None if request.coverage is None else coverage_fingerprint(request.coverage)
        ),
        current_state_fingerprint=(
            None
            if request.current_state is None
            else current_state_fingerprint(request.current_state)
        ),
        analyzer_name=analyzer_name,
        reasons=_ordered_reasons(reasons),
        source_content_analyzed=True,
        model_called=model_called,
    )


# ── Optional single bounded repair ────────────────────────────────────────────

def verify_with_bounded_repair(
    request: EvidenceVerificationRequest,
    payload: AcquiredSourcePayload,
    receipt: SourceAcquisitionReceipt,
    analyzer: EvidenceAnalyzer,
    *,
    model_called: bool = False,
) -> EvidenceVerificationResult:
    """Verify, and on a *structural* defect allow exactly one repair attempt.

    The repair is not "think harder".  The analyzer is handed the exact defects
    the gate found and nothing else, is called once, and its second answer is
    gated identically.  There is no third attempt, no provider escalation, and a
    still-invalid answer promotes nothing.

    An analyzer that does not implement ``repair`` simply gets the first result.
    """
    first = verify_acquired_source(
        request,
        payload,
        receipt,
        analyzer,
        model_called=model_called,
    )
    if first.status != STATUS_ANALYSIS_INVALID:
        return first
    repair = getattr(analyzer, "repair", None)
    if repair is None or not callable(repair):
        return first

    analyzer_name = str(getattr(analyzer, "name", "unnamed_evidence_analyzer"))
    view = bounded_payload_view(payload, receipt)
    try:
        proposal = repair(request, view, _last_defects(request, payload, receipt, analyzer))
    except EvidenceAnalysisError:
        return _refusal(
            request,
            receipt,
            status=STATUS_ANALYSIS_INVALID,
            reasons={GATE_SOURCE_BINDING_VERIFIED, GATE_ANALYZER_UNAVAILABLE},
            analyzer_name=analyzer_name,
        )
    if not isinstance(proposal, EvidenceVerificationProposal):
        return _refusal(
            request,
            receipt,
            status=STATUS_ANALYSIS_INVALID,
            reasons={GATE_SOURCE_BINDING_VERIFIED, GATE_ANALYZER_PROPOSAL_INVALID},
            analyzer_name=analyzer_name,
        )
    defects = proposal_defects(request, payload, receipt, proposal)
    if defects:
        return _refusal(
            request,
            receipt,
            status=STATUS_ANALYSIS_INVALID,
            reasons={GATE_SOURCE_BINDING_VERIFIED, GATE_ANALYZER_PROPOSAL_INVALID},
            analyzer_name=analyzer_name,
            analyzer_proposal_fingerprint=proposal_fingerprint(proposal),
        )
    return adjudicate(
        request,
        receipt,
        proposal,
        analyzer_name=analyzer_name,
        model_called=model_called,
    )


def _last_defects(
    request: EvidenceVerificationRequest,
    payload: AcquiredSourcePayload,
    receipt: SourceAcquisitionReceipt,
    analyzer: EvidenceAnalyzer,
) -> tuple[str, ...]:
    """Defects from the analyzer's most recent proposal, if it kept one.

    An analyzer that records its last proposal gets a precise repair brief; one
    that does not is told only that the answer was structurally invalid.
    """
    previous = getattr(analyzer, "last_proposal", None)
    if isinstance(previous, EvidenceVerificationProposal):
        return proposal_defects(request, payload, receipt, previous)
    return ("the previous proposal was structurally invalid",)


__all__ = [
    "PHASE_ID",
    "adjudicate",
    "binding_inconsistencies",
    "proposal_defects",
    "verify_acquired_source",
    "verify_with_bounded_repair",
]
