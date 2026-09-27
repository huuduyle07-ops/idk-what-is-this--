"""EVIDENCE.1 — the evidence analyzer boundary.

An analyzer reads bounded acquired bytes and *proposes* what they mean:

    Proposition + BoundedPayloadView -> EvidenceVerificationProposal

That is the whole job.  The pattern is the one INPUT.2 already validated:

    analyzer proposes -> deterministic gate validates -> promotion or refusal

An analyzer may propose that an expected role is verified, rejected or
inconclusive; that the source supports, contradicts, is insufficient for, or is
unrelated to the proposition; which bounded byte spans carry that evidence; and
why, in codes.

An analyzer may not change the proposition, invent a different one, name a
different source, request another file, select a candidate, search anything,
call a tool, execute code, choose a provider or model, set an authority flag, or
promote its own conclusion.  Most of those are not rules it is asked to follow:
:class:`~core.evidence_verification.EvidenceVerificationProposal` has no field in
which any of them could be written, and the deterministic gate re-derives the
rest from bindings the analyzer never sees.

Two analyzers ship here and neither needs a model:

:class:`StaticEvidenceAnalyzer`
    Literal byte markers in, real spans out.  Every span it cites is a range it
    actually found, so its digests match by construction.  Enough to drive the
    whole promotion gate offline.

:class:`ScriptedEvidenceAnalyzer`
    Replays prepared proposals, including deliberately hostile ones, so the gate
    can be tested against an analyzer that lies.

The module is stdlib-only and pure.  It opens no file, contacts no service,
imports no model stack, and holds no authority.
"""

from __future__ import annotations

import hashlib
from typing import Iterable, Protocol, runtime_checkable

from core.evidence_verification import (
    ANALYSIS_INCOMPATIBLE_MECHANISM_PRESENT,
    ANALYSIS_MECHANISM_IMPLEMENTED,
    ANALYSIS_PROPOSITION_TERMS_ABSENT,
    ANALYSIS_PROPOSITION_TERMS_PRESENT,
    ANALYSIS_REASONS,
    ANALYSIS_ROLE_CONTENT_CONSISTENT,
    ANALYSIS_ROLE_CONTENT_INCONCLUSIVE,
    ANALYSIS_ROLE_CONTENT_INCONSISTENT,
    ANALYSIS_SUBJECT_NOT_DISCUSSED,
    MAX_EVIDENCE_SPANS,
    MAX_SPAN_BYTES,
    MAX_TOTAL_CITED_BYTES,
    RELATION_CONTRADICTS,
    RELATION_INSUFFICIENT,
    RELATION_SUPPORTS,
    RELATION_UNRELATED,
    ROLE_STATUS_INSUFFICIENT,
    ROLE_STATUS_REJECTED,
    ROLE_STATUS_VERIFIED,
    SPAN_CONTRADICTING,
    SPAN_ROLE_EVIDENCE,
    SPAN_SUPPORTING,
    BoundedPayloadView,
    EvidenceSpan,
    EvidenceVerificationProposal,
    EvidenceVerificationRequest,
    RoleAssessment,
)
from core.evidence_requirements import EVIDENCE_ROLES


PHASE_ID = "EVIDENCE.1"

STATIC_ANALYZER_NAME = "static_evidence_analyzer"
SCRIPTED_ANALYZER_NAME = "scripted_evidence_analyzer"

#: Hard ceiling on how much of one marker may be cited as a span.  A marker that
#: needs more context than this is describing a whole file, not a citation.
MAX_MARKER_CONTEXT_BYTES = 240


class EvidenceAnalysisError(Exception):
    """Base class for every analyzer failure."""


class EvidenceAnalyzerUnavailable(EvidenceAnalysisError):
    """The configured analyzer could not be reached or produced nothing.

    The gate records ``analysis_invalid`` and promotes nothing.  It never
    substitutes another analyzer, and never falls back to a stronger model.
    """


class EvidenceAnalysisRejected(EvidenceAnalysisError):
    """The analyzer produced something that is not a valid proposal."""


@runtime_checkable
class EvidenceAnalyzer(Protocol):
    """The narrow content-semantics boundary.

    ``analyze`` receives the proposition, its type, the expected roles, a
    bounded view of the acquired payload and the verification constraints — all
    carried on ``request`` and ``view`` — and returns one bounded proposal.
    """

    @property
    def name(self) -> str:
        """A stable name for telemetry.  Never an authority claim."""
        ...

    def analyze(
        self,
        request: EvidenceVerificationRequest,
        view: BoundedPayloadView,
    ) -> EvidenceVerificationProposal:
        """Propose what these exact bytes mean for this exact proposition."""
        ...


# ── Span construction from real occurrences ───────────────────────────────────

def _marker_span(
    view: BoundedPayloadView,
    needle: bytes,
    purpose: str,
    *,
    context_bytes: int,
) -> EvidenceSpan | None:
    """Cite the first literal occurrence of ``needle``, with bounded context.

    The digest is computed from the bytes the view actually holds, so a marker
    that is not in the payload produces no span at all rather than a span the
    gate would have to catch later.
    """
    located = view.locate(needle)
    if located is None:
        return None
    start, end = located
    padding = min(context_bytes, MAX_MARKER_CONTEXT_BYTES)
    start = max(0, start - padding)
    end = min(view.byte_count, end + padding)
    if end - start > MAX_SPAN_BYTES:
        end = start + MAX_SPAN_BYTES
    payload = view.slice(start, end)
    return EvidenceSpan(
        start_byte=start,
        end_byte=end,
        span_sha256=hashlib.sha256(payload).hexdigest(),
        purpose=purpose,
        source_content_sha256=view.content_sha256,
    )


def _first_marker_span(
    view: BoundedPayloadView,
    markers: Iterable[bytes],
    purpose: str,
    *,
    context_bytes: int,
) -> EvidenceSpan | None:
    for marker in markers:
        span = _marker_span(view, marker, purpose, context_bytes=context_bytes)
        if span is not None:
            return span
    return None


def _bounded_spans(spans: list[EvidenceSpan]) -> tuple[EvidenceSpan, ...]:
    """Drop exact duplicates and stop at the span and total-byte ceilings."""
    kept: list[EvidenceSpan] = []
    seen: set[tuple[int, int, str]] = set()
    total = 0
    for span in spans:
        key = (span.start_byte, span.end_byte, span.purpose)
        if key in seen:
            continue
        if len(kept) >= MAX_EVIDENCE_SPANS:
            break
        if total + span.byte_count > MAX_TOTAL_CITED_BYTES:
            continue
        seen.add(key)
        total += span.byte_count
        kept.append(span)
    return tuple(kept)


# ── Deterministic analyzer ────────────────────────────────────────────────────

class StaticEvidenceAnalyzer:
    """A deterministic analyzer driven by literal byte markers.

    It is not a semantic model and does not pretend to be one.  It exists so the
    complete promotion gate — bindings, role subset, span digests, competence,
    coverage, promotion — can be exercised offline with proposals whose spans
    are genuinely present in the acquired bytes.

    ``unmarked_role_status`` decides what a missing role marker means.
    ``rejected`` is the default because a source acquired *as* implementation
    authority that contains no implementation has failed the expectation, which
    is a finding rather than a shrug.
    """

    def __init__(
        self,
        *,
        role_markers: dict[str, tuple[bytes, ...]] | None = None,
        supporting_markers: tuple[bytes, ...] = (),
        contradicting_markers: tuple[bytes, ...] = (),
        relevance_markers: tuple[bytes, ...] = (),
        unmarked_role_status: str = ROLE_STATUS_REJECTED,
        context_bytes: int = 60,
        name: str = STATIC_ANALYZER_NAME,
    ) -> None:
        markers = dict(role_markers or {})
        for role in markers:
            if role not in EVIDENCE_ROLES:
                raise ValueError(f"unsupported evidence role: {role!r}")
        for group in (supporting_markers, contradicting_markers, relevance_markers):
            if not isinstance(group, tuple):
                raise TypeError("marker groups must be tuples of bytes")
            if any(not isinstance(item, bytes) or not item for item in group):
                raise ValueError("every marker must be non-empty bytes")
        if unmarked_role_status not in {ROLE_STATUS_REJECTED, ROLE_STATUS_INSUFFICIENT}:
            raise ValueError(
                "an unmarked role is rejected or insufficient, never verified"
            )
        if isinstance(context_bytes, bool) or not isinstance(context_bytes, int):
            raise TypeError("context_bytes must be an integer")
        if context_bytes < 0 or context_bytes > MAX_MARKER_CONTEXT_BYTES:
            raise ValueError("context_bytes exceeds its finite bound")
        self._role_markers = markers
        self._supporting = supporting_markers
        self._contradicting = contradicting_markers
        self._relevance = relevance_markers
        self._unmarked_role_status = unmarked_role_status
        self._context_bytes = context_bytes
        self._name = name
        self._call_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def call_count(self) -> int:
        return self._call_count

    def analyze(
        self,
        request: EvidenceVerificationRequest,
        view: BoundedPayloadView,
    ) -> EvidenceVerificationProposal:
        self._call_count += 1

        # Only roles the source was actually acquired for may be assessed.  A
        # role the request wants but ACQUIRE.3 never expected is not smuggled in
        # here; the gate refuses that request before analysis anyway.
        assessable = tuple(
            role
            for role in EVIDENCE_ROLES
            if role in set(request.requested_roles) & set(view.expected_roles)
        )

        spans: list[EvidenceSpan] = []
        pending: list[tuple[str, str, tuple[str, ...], EvidenceSpan | None]] = []
        for role in assessable:
            span = _first_marker_span(
                view,
                self._role_markers.get(role, ()),
                SPAN_ROLE_EVIDENCE,
                context_bytes=self._context_bytes,
            )
            if span is not None:
                pending.append(
                    (role, ROLE_STATUS_VERIFIED, (ANALYSIS_ROLE_CONTENT_CONSISTENT,), span)
                )
            else:
                reason = (
                    ANALYSIS_ROLE_CONTENT_INCONSISTENT
                    if self._unmarked_role_status == ROLE_STATUS_REJECTED
                    else ANALYSIS_ROLE_CONTENT_INCONCLUSIVE
                )
                pending.append((role, self._unmarked_role_status, (reason,), None))

        contradicting = _first_marker_span(
            view,
            self._contradicting,
            SPAN_CONTRADICTING,
            context_bytes=self._context_bytes,
        )
        supporting = _first_marker_span(
            view,
            self._supporting,
            SPAN_SUPPORTING,
            context_bytes=self._context_bytes,
        )
        relevant = _first_marker_span(
            view,
            self._relevance,
            SPAN_ROLE_EVIDENCE,
            context_bytes=self._context_bytes,
        )

        if contradicting is not None:
            relation = RELATION_CONTRADICTS
            relation_span: EvidenceSpan | None = contradicting
            reasons: tuple[str, ...] = (ANALYSIS_INCOMPATIBLE_MECHANISM_PRESENT,)
        elif supporting is not None:
            relation = RELATION_SUPPORTS
            relation_span = supporting
            reasons = (
                ANALYSIS_PROPOSITION_TERMS_PRESENT,
                ANALYSIS_MECHANISM_IMPLEMENTED,
            )
        elif relevant is not None:
            relation = RELATION_INSUFFICIENT
            relation_span = relevant
            reasons = (ANALYSIS_PROPOSITION_TERMS_ABSENT,)
        else:
            relation = RELATION_UNRELATED
            relation_span = None
            reasons = (ANALYSIS_SUBJECT_NOT_DISCUSSED,)

        for _, _, _, span in pending:
            if span is not None:
                spans.append(span)
        if relation_span is not None:
            spans.append(relation_span)
        ordered_spans = _bounded_spans(spans)
        index_of = {
            (span.start_byte, span.end_byte, span.purpose): position
            for position, span in enumerate(ordered_spans)
        }

        assessments: list[RoleAssessment] = []
        for role, status, role_reasons, span in pending:
            indexes: tuple[int, ...] = ()
            if span is not None:
                position = index_of.get((span.start_byte, span.end_byte, span.purpose))
                if position is not None:
                    indexes = (position,)
            assessments.append(
                RoleAssessment(
                    role=role,
                    status=status,
                    span_indexes=indexes,
                    reasons=role_reasons,
                )
            )

        canonical_reasons = tuple(
            item for item in ANALYSIS_REASONS if item in set(reasons)
        )
        return EvidenceVerificationProposal(
            proposition_id=request.proposition.proposition_id,
            proposition_sha256=request.proposition.proposition_sha256,
            source_identifier=view.candidate_identifier,
            source_content_sha256=view.content_sha256,
            relation=relation,
            role_assessments=tuple(assessments),
            evidence_spans=ordered_spans,
            reasons=canonical_reasons,
        )


# ── Scripted analyzer ─────────────────────────────────────────────────────────

class ScriptedEvidenceAnalyzer:
    """Replays prepared proposals in order, including hostile ones.

    The gate must behave identically whether the proposal came from a careful
    analyzer or from one trying to promote itself, so the adversarial matrix
    drives this rather than a model.
    """

    def __init__(
        self,
        proposals: list[EvidenceVerificationProposal | Exception | object],
        *,
        name: str = SCRIPTED_ANALYZER_NAME,
    ) -> None:
        self._proposals = list(proposals)
        self._name = name
        self._calls: list[tuple[str, str]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def call_count(self) -> int:
        return len(self._calls)

    @property
    def calls(self) -> tuple[tuple[str, str], ...]:
        return tuple(self._calls)

    def analyze(
        self,
        request: EvidenceVerificationRequest,
        view: BoundedPayloadView,
    ) -> EvidenceVerificationProposal:
        if not self._proposals:
            raise EvidenceAnalyzerUnavailable(
                "the scripted evidence analyzer ran out of proposals"
            )
        self._calls.append(
            (request.proposition.proposition_id, view.content_sha256)
        )
        nxt = self._proposals.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        if not isinstance(nxt, EvidenceVerificationProposal):
            raise EvidenceAnalysisRejected(
                "the scripted evidence analyzer produced a non-proposal"
            )
        return nxt


__all__ = [
    "EvidenceAnalysisError",
    "EvidenceAnalysisRejected",
    "EvidenceAnalyzer",
    "EvidenceAnalyzerUnavailable",
    "MAX_MARKER_CONTEXT_BYTES",
    "PHASE_ID",
    "SCRIPTED_ANALYZER_NAME",
    "STATIC_ANALYZER_NAME",
    "ScriptedEvidenceAnalyzer",
    "StaticEvidenceAnalyzer",
]
