"""EVIDENCE.2 — Evidence Set Coverage, Conflict & Independence Contract.

EVIDENCE.1 answered *what does one acquired source establish about one
proposition*.  EVIDENCE.2 answers the next question and only that one:

    Proposition + several EVIDENCE.1 results
        -> what does this evidence set actually contain?

It does **not** answer whether the proposition is true.  There is no verdict
field, no confidence, no probability, no score, no winner and no vote anywhere
in this module, and CLAIM.1 — which does not exist yet — owns proposition
assessment.

Eight boundaries hold in every outcome.

**Counting is not weighing.**  Five supporting records and one contradicting
record is ``conflicting``, not "supported".  The set reports what it holds and
stops.  There is no majority rule, no weighted majority, no support score, no
Bayesian confidence and no averaged analyzer opinion, because the number of
files that agree is not evidence about the world — it is evidence about what was
acquired.

**Four copies of one file are one lineage.**  Identical content digests collapse
into a single lineage group before anything is described, and a supplied
restatement declaration collapses more.  Two records restating one upstream
hypothesis are not two independent readings, and the mirror-tunnel failure this
prevents is exactly the one where a guess written into three derivative
documents came back looking like corroboration.

**A different path is not independence.**  Identical content proves duplication;
different content proves nothing at all about whether two sources were produced
independently.  So a non-duplicate record is ``independence_unknown`` — never
``independent`` — unless somebody with the authority to know says otherwise in a
supplied lineage declaration, which nothing upstream currently mints.

**Aggregation cannot upgrade epistemic status.**  Every member relation is
``analyzer_assessed`` and stays ``analyzer_assessed``.  Ten agreeing
analyzer-assessed support records are ten analyzer-assessed support records.
The set-level :class:`~core.evidence_verification.VerificationLevels` is
structurally incapable of saying otherwise.

**Absence still needs coverage.**  Twenty files that say nothing about
persistence do not establish that no persistence exists.  A negative existential
reaches ``complete`` coverage only through a supplied, mutually compatible
coverage receipt, and no number of ``insufficient`` records substitutes for one.
One concrete counterexample still contradicts an absence with no coverage at
all, and stays visible.

**Roles, relations and independence are three axes.**  A source may verify as
``implementation_authority`` and be ``insufficient``: it discharges role
presence and discharges no directional support.  Role diversity is not
independence, and neither is truth.

**Nothing is reinterpreted.**  Relations arrive decided and leave decided.  No
span is re-read, no test is promoted because several tests agree, no manifest
becomes runtime behaviour, no historical document outweighs a current
implementation.  EVIDENCE.2 groups records; it does not grade them.

**Receipts are consumed, never minted.**  ``NegativeClaimCoverage`` and
``CurrentStateReceipt`` come from whoever can establish them.  A missing one is
recorded as a coverage gap, and there is no code path here that could
manufacture one.

The module is stdlib-only and pure.  It reads no file, opens no path, walks no
directory, contacts no service, calls no language system, acquires nothing,
selects nothing, executes nothing, decides no claim, and is wired into no live
path.  It does not even import the EVIDENCE.1 promotion gate, because reaching
the gate means reaching an analyzer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from core.acquisition_request import MAX_INITIAL_SOURCES_CEILING
from core.evidence_requirements import EVIDENCE_ROLES
from core.evidence_verification import (
    COVERAGE_SUFFICIENT,
    DIRECTIONAL_RELATIONS,
    LEVEL_ANALYZER_ASSESSED,
    LEVEL_DETERMINISTICALLY_VERIFIED,
    LEVEL_NOT_ESTABLISHED,
    MAX_PROPOSITION_ID_LENGTH,
    MAX_SOURCE_IDENTIFIER_LENGTH,
    PROMOTION_NOT_PROMOTED,
    PROMOTION_PROMOTED,
    PROPOSITION_NEGATIVE_EXISTENTIAL,
    PROPOSITION_SCOPES,
    PROPOSITION_TYPES,
    RELATION_CONTRADICTS,
    RELATION_INSUFFICIENT,
    RELATION_SUPPORTS,
    RELATION_UNRELATED,
    SCOPE_COMPETENT_ROLES,
    SCOPES_REQUIRING_CURRENT_STATE,
    STATUS_CONTRADICTED,
    STATUS_COVERAGE_REQUIRED,
    STATUS_INSUFFICIENT,
    STATUS_UNRELATED,
    STATUS_VERIFIED,
    CurrentStateReceipt,
    EvidenceVerificationResult,
    NegativeClaimCoverage,
    Proposition,
    VerificationLevels,
    coverage_fingerprint,
    current_state_fingerprint,
)


PHASE_ID = "EVIDENCE.2"

REQUIREMENTS_SCHEMA_VERSION = "evidence_2_set_requirements_v1"
LINEAGE_SCHEMA_VERSION = "evidence_2_source_lineage_declaration_v1"
REQUEST_SCHEMA_VERSION = "evidence_2_evidence_set_request_v1"
MEMBER_SCHEMA_VERSION = "evidence_2_evidence_set_member_v1"
ROLE_COVERAGE_SCHEMA_VERSION = "evidence_2_role_coverage_v1"
LINEAGE_GROUP_SCHEMA_VERSION = "evidence_2_lineage_group_v1"
INDEPENDENCE_SCHEMA_VERSION = "evidence_2_independence_assessment_v1"
ASSESSMENT_SCHEMA_VERSION = "evidence_2_evidence_set_assessment_v1"

# ── Set statuses ──────────────────────────────────────────────────────────────
#: Two, and neither is a verdict about the proposition.  ``assessed`` means the
#: set was describable; ``inconsistent_input`` means it was not, and describing
#: it anyway would have produced a confident picture of incoherent material.
SET_ASSESSED = "assessed"
SET_INCONSISTENT_INPUT = "inconsistent_input"

SET_STATUSES: tuple[str, ...] = (SET_ASSESSED, SET_INCONSISTENT_INPUT)

# ── Admissible member statuses ────────────────────────────────────────────────
#: EVIDENCE.1 statuses that describe a *reading of content*.  ``binding_invalid``,
#: ``analysis_invalid`` and ``unsupported_source`` are absent on purpose: those
#: records establish nothing about the proposition, and admitting one would let a
#: broken record discharge coverage.
ADMISSIBLE_MEMBER_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_VERIFIED,
        STATUS_CONTRADICTED,
        STATUS_INSUFFICIENT,
        STATUS_UNRELATED,
        STATUS_COVERAGE_REQUIRED,
    }
)

#: Relations that say something *about the proposition*, whether or not they
#: point anywhere.  ``unrelated`` is deliberately outside: a source that has
#: nothing to do with the claim discharges no proposition coverage, however
#: competently it verified its role.
ADDRESSING_RELATIONS: frozenset[str] = frozenset(
    {RELATION_SUPPORTS, RELATION_CONTRADICTS, RELATION_INSUFFICIENT}
)

# ── Conflict ──────────────────────────────────────────────────────────────────
#: A description of *composition*, never of truth.  ``support_only`` means the
#: set contains directional support and no directional contradiction.  It does
#: not mean the proposition holds, and no field in this module says it does.
#: The coarse "none" a reader might expect is the union of the three
#: non-conflicting values, exposed as :data:`NON_CONFLICTING_STATUSES`.
CONFLICT_NO_DIRECTIONAL_EVIDENCE = "no_directional_evidence"
CONFLICT_SUPPORT_ONLY = "support_only"
CONFLICT_CONTRADICTION_ONLY = "contradiction_only"
CONFLICT_CONFLICTING = "conflicting"
CONFLICT_NOT_ASSESSED = "not_assessed"

CONFLICT_STATUSES: tuple[str, ...] = (
    CONFLICT_NO_DIRECTIONAL_EVIDENCE,
    CONFLICT_SUPPORT_ONLY,
    CONFLICT_CONTRADICTION_ONLY,
    CONFLICT_CONFLICTING,
    CONFLICT_NOT_ASSESSED,
)

NON_CONFLICTING_STATUSES: frozenset[str] = frozenset(
    {
        CONFLICT_NO_DIRECTIONAL_EVIDENCE,
        CONFLICT_SUPPORT_ONLY,
        CONFLICT_CONTRADICTION_ONLY,
    }
)

# ── Coverage ──────────────────────────────────────────────────────────────────
#: One vocabulary for all four coverage questions, so a reader never has to
#: learn which kind of "incomplete" they are looking at.
COVERAGE_COMPLETE = "complete"
COVERAGE_INCOMPLETE = "incomplete"
COVERAGE_INCONSISTENT = "inconsistent"
COVERAGE_NOT_APPLICABLE = "not_applicable"
COVERAGE_NOT_ASSESSED = "not_assessed"

SET_COVERAGE_STATUSES: tuple[str, ...] = (
    COVERAGE_COMPLETE,
    COVERAGE_INCOMPLETE,
    COVERAGE_INCONSISTENT,
    COVERAGE_NOT_APPLICABLE,
    COVERAGE_NOT_ASSESSED,
)

# ── Independence ──────────────────────────────────────────────────────────────
#: Three states, and the asymmetry between them is the contract.  Identical
#: content *proves* duplication.  Nothing EVIDENCE.2 can compute proves
#: independence, so ``independent`` is reachable only through a supplied
#: :class:`SourceLineageDeclaration` asserting distinct origin — never from a
#: different path, a different digest, a different role or a different domain.
INDEPENDENCE_DUPLICATE = "duplicate"
INDEPENDENCE_INDEPENDENT = "independent"
INDEPENDENCE_UNKNOWN = "independence_unknown"

INDEPENDENCE_STATES: tuple[str, ...] = (
    INDEPENDENCE_DUPLICATE,
    INDEPENDENCE_INDEPENDENT,
    INDEPENDENCE_UNKNOWN,
)

# ── Lineage ───────────────────────────────────────────────────────────────────
#: What a supplied declaration may assert about two sources.  ``restates`` is
#: the one an authorized inventory builder can already establish (it records a
#: translated or rendered copy); ``distinct_origin`` has no producer anywhere in
#: the pipeline today and is consumed only so that a future one has somewhere to
#: land.
LINEAGE_RESTATES = "restates"
LINEAGE_DISTINCT_ORIGIN = "distinct_origin"

LINEAGE_RELATIONS: tuple[str, ...] = (LINEAGE_RESTATES, LINEAGE_DISTINCT_ORIGIN)

LINEAGE_BASIS_IDENTICAL_CONTENT = "identical_content_digest"
LINEAGE_BASIS_DECLARED_RESTATEMENT = "declared_restatement"
LINEAGE_BASIS_DECLARED_DISTINCT_ORIGIN = "declared_distinct_origin"
LINEAGE_BASIS_NO_LINEAGE_METADATA = "no_lineage_metadata"

LINEAGE_BASES: tuple[str, ...] = (
    LINEAGE_BASIS_IDENTICAL_CONTENT,
    LINEAGE_BASIS_DECLARED_RESTATEMENT,
    LINEAGE_BASIS_DECLARED_DISTINCT_ORIGIN,
    LINEAGE_BASIS_NO_LINEAGE_METADATA,
)

# ── Reasons ───────────────────────────────────────────────────────────────────
SET_PROPOSITION_BINDING_VERIFIED = "proposition_binding_verified"
SET_RECORD_IDENTITIES_REDERIVED = "record_identities_rederived"
SET_RELATIONS_PARTITIONED = "relations_partitioned"
SET_ROLE_COVERAGE_ASSESSED = "role_coverage_assessed"
SET_SCOPE_COVERAGE_ASSESSED = "scope_coverage_assessed"
SET_CONFLICT_ASSESSED = "conflict_assessed"
SET_DUPLICATE_ANALYSIS_PERFORMED = "duplicate_analysis_performed"
SET_NEGATIVE_COVERAGE_ASSESSED = "negative_claim_coverage_assessed"
SET_CURRENT_STATE_COVERAGE_ASSESSED = "current_state_coverage_assessed"
SET_SEMANTIC_STATUS_PRESERVED = "semantic_relation_status_preserved"
SET_INPUT_REJECTED = "inconsistent_input_rejected"
SET_NO_MAJORITY_COMPUTED = "no_majority_computed"
SET_NO_CONFIDENCE_COMPUTED = "no_confidence_computed"
SET_NO_CLAIM_DECISION_PERFORMED = "no_claim_decision_performed"

SET_REASONS: tuple[str, ...] = (
    SET_PROPOSITION_BINDING_VERIFIED,
    SET_RECORD_IDENTITIES_REDERIVED,
    SET_RELATIONS_PARTITIONED,
    SET_ROLE_COVERAGE_ASSESSED,
    SET_SCOPE_COVERAGE_ASSESSED,
    SET_CONFLICT_ASSESSED,
    SET_DUPLICATE_ANALYSIS_PERFORMED,
    SET_NEGATIVE_COVERAGE_ASSESSED,
    SET_CURRENT_STATE_COVERAGE_ASSESSED,
    SET_SEMANTIC_STATUS_PRESERVED,
    SET_INPUT_REJECTED,
    SET_NO_MAJORITY_COMPUTED,
    SET_NO_CONFIDENCE_COMPUTED,
    SET_NO_CLAIM_DECISION_PERFORMED,
)

# ── Inconsistencies ───────────────────────────────────────────────────────────
#: Every one of these is fatal.  A set that cannot be described coherently is
#: refused whole, the way EVIDENCE.1 refuses a source whose provenance is
#: already broken.  Coverage *gaps* are a different thing entirely and live in
#: the coverage fields.
INCONSISTENT_MIXED_PROPOSITION = "mixed_proposition_binding"
INCONSISTENT_RECORD_IDENTITY_REPEATED = "record_identity_repeated"
INCONSISTENT_RECORD_NOT_ADMISSIBLE = "record_not_admissible"
INCONSISTENT_SOURCE_CONTENT_CONFLICT = "source_identity_content_conflict"
INCONSISTENT_SEMANTIC_STATUS_ABSENT = "semantic_relation_status_absent"
INCONSISTENT_NEGATIVE_SUPPORT_UNCOVERED = "negative_support_without_coverage"
INCONSISTENT_COVERAGE_RECEIPT_UNSUPPLIED = "coverage_receipt_not_supplied"
INCONSISTENT_COVERAGE_RECEIPT_BINDING = "coverage_receipt_binding_mismatch"
INCONSISTENT_CURRENT_STATE_RECEIPT_BINDING = "current_state_receipt_binding_mismatch"
INCONSISTENT_LINEAGE_BINDING = "lineage_declaration_binding_mismatch"
INCONSISTENT_REQUIREMENTS_BINDING = "requirements_binding_mismatch"

SET_INCONSISTENCIES: tuple[str, ...] = (
    INCONSISTENT_MIXED_PROPOSITION,
    INCONSISTENT_RECORD_IDENTITY_REPEATED,
    INCONSISTENT_RECORD_NOT_ADMISSIBLE,
    INCONSISTENT_SOURCE_CONTENT_CONFLICT,
    INCONSISTENT_SEMANTIC_STATUS_ABSENT,
    INCONSISTENT_NEGATIVE_SUPPORT_UNCOVERED,
    INCONSISTENT_COVERAGE_RECEIPT_UNSUPPLIED,
    INCONSISTENT_COVERAGE_RECEIPT_BINDING,
    INCONSISTENT_CURRENT_STATE_RECEIPT_BINDING,
    INCONSISTENT_LINEAGE_BINDING,
    INCONSISTENT_REQUIREMENTS_BINDING,
)

# ── Missing requirements ──────────────────────────────────────────────────────
#: Gaps, stated as gaps.  None of these is a judgement about the proposition;
#: each names something the set does not contain and cannot acquire.
MISSING_ROLE_REQUIREMENTS_NOT_SUPPLIED = "role_requirements_not_supplied"
MISSING_REQUIRED_ROLE = "required_role_absent"
MISSING_SCOPE_COMPETENT_ROLE = "scope_competent_role_absent"
MISSING_DIRECTIONAL_EVIDENCE = "directional_evidence_absent"
MISSING_NEGATIVE_CLAIM_COVERAGE = "negative_claim_coverage_absent"
MISSING_CURRENT_STATE_COVERAGE = "current_state_coverage_absent"
MISSING_INDEPENDENT_CORROBORATION = "independent_corroboration_unestablished"

MISSING_REQUIREMENTS: tuple[str, ...] = (
    MISSING_ROLE_REQUIREMENTS_NOT_SUPPLIED,
    MISSING_REQUIRED_ROLE,
    MISSING_SCOPE_COMPETENT_ROLE,
    MISSING_DIRECTIONAL_EVIDENCE,
    MISSING_NEGATIVE_CLAIM_COVERAGE,
    MISSING_CURRENT_STATE_COVERAGE,
    MISSING_INDEPENDENT_CORROBORATION,
)

# ── Bounds ────────────────────────────────────────────────────────────────────
MAX_EVIDENCE_SET_RECORDS = MAX_INITIAL_SOURCES_CEILING
MAX_SET_COVERAGE_RECEIPTS = MAX_INITIAL_SOURCES_CEILING
MAX_SET_CURRENT_STATE_RECEIPTS = MAX_INITIAL_SOURCES_CEILING
MAX_LINEAGE_DECLARATIONS = 256
MAX_SET_REASONS = len(SET_REASONS)
MAX_SET_INCONSISTENCIES = len(SET_INCONSISTENCIES)
MAX_MISSING_REQUIREMENTS = len(MISSING_REQUIREMENTS)
MAX_ROLE_COVERAGE_ENTRIES = len(EVIDENCE_ROLES)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _require_sha256(value: str | None, label: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    if any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _bounded_identifier(value: object, label: str, *, maximum: int) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds its finite bound")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{label} may not contain control characters")


def _ordered_vocabulary(
    values: tuple[str, ...],
    vocabulary: tuple[str, ...],
    label: str,
) -> None:
    """Canonical vocabulary order, each value at most once.

    Two sets that hold the same facts must fingerprint identically, so the order
    a caller happened to write things down carries no meaning.
    """
    if not isinstance(values, tuple):
        raise TypeError(f"{label}s must be a tuple")
    if len(set(values)) != len(values):
        raise ValueError(f"each {label} may be stated exactly once")
    for value in values:
        if value not in vocabulary:
            raise ValueError(f"unsupported {label}: {value!r}")
    expected = tuple(item for item in vocabulary if item in set(values))
    if values != expected:
        raise ValueError(f"{label}s must use canonical vocabulary order")


def _ordered_reasons(codes: set[str]) -> tuple[str, ...]:
    return tuple(item for item in SET_REASONS if item in codes)


def _ordered_inconsistencies(codes: set[str]) -> tuple[str, ...]:
    return tuple(item for item in SET_INCONSISTENCIES if item in codes)


def _ordered_missing(codes: set[str]) -> tuple[str, ...]:
    return tuple(item for item in MISSING_REQUIREMENTS if item in codes)


def _ordered_roles(roles: set[str]) -> tuple[str, ...]:
    return tuple(item for item in EVIDENCE_ROLES if item in roles)


# ── EVIDENCE.1 record identity ────────────────────────────────────────────────

def evidence_record_fingerprint(record: EvidenceVerificationResult) -> str:
    """Re-derive one EVIDENCE.1 record's identity from its own canonical form.

    Defined here rather than upstream because EVIDENCE.2 is the first phase that
    needs to bind *to* a verification result; EVIDENCE.1 is closed and is not
    modified to add it.  Nothing in this module trusts a caller-supplied
    fingerprint field: the digest is computed over the record's serialization,
    which covers the proposition binding, the source content digest, every
    evidence span, the relation, the role assessments and the semantic
    assessment marker.  A record altered in any of those hashes differently and
    cannot be smuggled into a set as the one that was gated.
    """
    if not isinstance(record, EvidenceVerificationResult):
        raise TypeError(
            "evidence_record_fingerprint requires an EvidenceVerificationResult"
        )
    return _fingerprint(record.as_dict())


# ── Supplied role requirements ────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class EvidenceSetRequirements:
    """Somebody else's statement of which roles this proposition needs.

    Consumed, never derived.  EVIDENCE.2 has no idea which roles a claim
    *ought* to have and will not guess: with no requirements supplied, role
    coverage is ``not_applicable`` rather than silently ``complete``.
    """

    proposition_id: str
    proposition_sha256: str
    required_roles: tuple[str, ...]
    evidence_requirement_fingerprint: str
    schema_version: str = REQUIREMENTS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _bounded_identifier(
            self.proposition_id,
            "requirements proposition_id",
            maximum=MAX_PROPOSITION_ID_LENGTH,
        )
        _require_sha256(self.proposition_sha256, "requirements proposition digest")
        _ordered_vocabulary(self.required_roles, EVIDENCE_ROLES, "required role")
        if not self.required_roles:
            raise ValueError("supplied requirements must name at least one role")
        _require_sha256(
            self.evidence_requirement_fingerprint,
            "upstream evidence requirement fingerprint",
        )
        if self.schema_version != REQUIREMENTS_SCHEMA_VERSION:
            raise ValueError("unsupported set requirements schema version")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "proposition_id": self.proposition_id,
            "proposition_sha256": self.proposition_sha256,
            "required_roles": list(self.required_roles),
            "evidence_requirement_fingerprint": self.evidence_requirement_fingerprint,
            "derived_by_evidence_2": False,
        }


def requirements_fingerprint(requirements: EvidenceSetRequirements) -> str:
    if not isinstance(requirements, EvidenceSetRequirements):
        raise TypeError("requirements_fingerprint requires an EvidenceSetRequirements")
    return _fingerprint(requirements.as_dict())


# ── Supplied source lineage ───────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SourceLineageDeclaration:
    """Somebody else's statement about how two sources are related.

    EVIDENCE.2 consumes one; it has no code path that could build one, because
    building one means knowing how a file came to exist, and that is not a
    question a digest answers.

    The pair is canonically ordered — ``source_identifier`` sorts before
    ``related_source_identifier`` — so the same relationship has exactly one
    spelling and cannot be declared twice to look like two facts.
    """

    proposition_id: str
    proposition_sha256: str
    source_identifier: str
    source_content_sha256: str
    related_source_identifier: str
    related_source_content_sha256: str
    lineage_relation: str
    schema_version: str = LINEAGE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _bounded_identifier(
            self.proposition_id,
            "lineage proposition_id",
            maximum=MAX_PROPOSITION_ID_LENGTH,
        )
        _require_sha256(self.proposition_sha256, "lineage proposition digest")
        for name in ("source_identifier", "related_source_identifier"):
            _bounded_identifier(
                getattr(self, name),
                f"lineage {name}",
                maximum=MAX_SOURCE_IDENTIFIER_LENGTH,
            )
        _require_sha256(self.source_content_sha256, "lineage source content digest")
        _require_sha256(
            self.related_source_content_sha256,
            "lineage related source content digest",
        )
        if self.source_identifier == self.related_source_identifier:
            raise ValueError("a lineage declaration relates two different sources")
        if self.source_identifier > self.related_source_identifier:
            raise ValueError(
                "a lineage declaration names its sources in canonical order"
            )
        if self.lineage_relation not in LINEAGE_RELATIONS:
            raise ValueError(
                f"unsupported lineage relation: {self.lineage_relation!r}"
            )
        if self.schema_version != LINEAGE_SCHEMA_VERSION:
            raise ValueError("unsupported source lineage schema version")

    @property
    def pair(self) -> tuple[str, str]:
        return (self.source_identifier, self.related_source_identifier)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "proposition_id": self.proposition_id,
            "proposition_sha256": self.proposition_sha256,
            "source_identifier": self.source_identifier,
            "source_content_sha256": self.source_content_sha256,
            "related_source_identifier": self.related_source_identifier,
            "related_source_content_sha256": self.related_source_content_sha256,
            "lineage_relation": self.lineage_relation,
            "minted_by_evidence_2": False,
            "inferred_from_paths": False,
        }


def lineage_fingerprint(declaration: SourceLineageDeclaration) -> str:
    if not isinstance(declaration, SourceLineageDeclaration):
        raise TypeError("lineage_fingerprint requires a SourceLineageDeclaration")
    return _fingerprint(declaration.as_dict())


# ── The set request ───────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class EvidenceSetRequest:
    """One proposition and the EVIDENCE.1 records said to be about it.

    Records arrive; they are never produced here.  Coverage receipts,
    current-state receipts, lineage declarations and role requirements all
    arrive too, and each is re-fingerprinted and re-bound before it is used.
    """

    proposition: Proposition
    records: tuple[EvidenceVerificationResult, ...]
    coverage_receipts: tuple[NegativeClaimCoverage, ...] = ()
    current_state_receipts: tuple[CurrentStateReceipt, ...] = ()
    lineage_declarations: tuple[SourceLineageDeclaration, ...] = ()
    requirements: EvidenceSetRequirements | None = None
    schema_version: str = REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.proposition, Proposition):
            raise TypeError("an evidence set request requires a Proposition")
        _typed_tuple(
            self.records,
            EvidenceVerificationResult,
            maximum=MAX_EVIDENCE_SET_RECORDS,
            label="evidence record",
        )
        if not self.records:
            raise ValueError("an evidence set contains at least one record")
        _typed_tuple(
            self.coverage_receipts,
            NegativeClaimCoverage,
            maximum=MAX_SET_COVERAGE_RECEIPTS,
            label="coverage receipt",
        )
        _typed_tuple(
            self.current_state_receipts,
            CurrentStateReceipt,
            maximum=MAX_SET_CURRENT_STATE_RECEIPTS,
            label="current-state receipt",
        )
        _typed_tuple(
            self.lineage_declarations,
            SourceLineageDeclaration,
            maximum=MAX_LINEAGE_DECLARATIONS,
            label="lineage declaration",
        )
        pairs = [item.pair for item in self.lineage_declarations]
        if len(set(pairs)) != len(pairs):
            raise ValueError("a source pair may carry at most one lineage declaration")
        if self.requirements is not None and not isinstance(
            self.requirements, EvidenceSetRequirements
        ):
            raise TypeError("requirements must be an EvidenceSetRequirements or None")
        if self.schema_version != REQUEST_SCHEMA_VERSION:
            raise ValueError("unsupported evidence set request schema version")

    def as_dict(self) -> dict[str, Any]:
        """Canonical, order-independent identity for the supplied material.

        Member order is a property of the caller's loop, not of the evidence, so
        every collection is fingerprinted and sorted.  ``[A, B, C]`` and
        ``[C, A, B]`` produce the same request identity and therefore the same
        assessment, byte for byte.
        """
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "proposition": self.proposition.as_dict(),
            "record_fingerprints": sorted(
                evidence_record_fingerprint(item) for item in self.records
            ),
            "coverage_receipt_fingerprints": sorted(
                coverage_fingerprint(item) for item in self.coverage_receipts
            ),
            "current_state_receipt_fingerprints": sorted(
                current_state_fingerprint(item) for item in self.current_state_receipts
            ),
            "lineage_declaration_fingerprints": sorted(
                lineage_fingerprint(item) for item in self.lineage_declarations
            ),
            "requirements_fingerprint": (
                None
                if self.requirements is None
                else requirements_fingerprint(self.requirements)
            ),
            "source_content_supplied": False,
        }


def _typed_tuple(values: object, kind: type, *, maximum: int, label: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{label}s must be a tuple")
    if len(values) > maximum:
        raise ValueError(f"{label}s exceed their finite bound")
    if any(not isinstance(item, kind) for item in values):
        raise TypeError(f"{label}s must contain {kind.__name__} records")


def evidence_set_request_fingerprint(request: EvidenceSetRequest) -> str:
    if not isinstance(request, EvidenceSetRequest):
        raise TypeError(
            "evidence_set_request_fingerprint requires an EvidenceSetRequest"
        )
    return _fingerprint(request.as_dict())


# ── Set members ───────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class EvidenceSetMember:
    """One admitted EVIDENCE.1 record, as the set sees it.

    Every field is copied from the record or derived from lineage grouping.
    Nothing is reinterpreted: ``relation`` is the relation EVIDENCE.1 decided,
    and ``semantic_relation_status`` is the epistemic status it decided with.
    """

    record_fingerprint: str
    status: str
    relation: str
    source_identifier: str
    source_content_sha256: str
    acquisition_receipt_fingerprint: str
    verified_roles: tuple[str, ...]
    rejected_roles: tuple[str, ...]
    promotion_status: str
    semantic_relation_status: str
    evidence_span_fingerprints: tuple[str, ...]
    coverage_status: str
    lineage_group_id: str
    independence_state: str
    analyzer_proposal_fingerprint: str | None = None
    coverage_receipt_fingerprint: str | None = None
    current_state_receipt_fingerprint: str | None = None
    schema_version: str = MEMBER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_sha256(self.record_fingerprint, "record fingerprint")
        if self.status not in ADMISSIBLE_MEMBER_STATUSES:
            raise ValueError(f"unsupported admitted member status: {self.status!r}")
        if self.relation not in (
            RELATION_SUPPORTS,
            RELATION_CONTRADICTS,
            RELATION_INSUFFICIENT,
            RELATION_UNRELATED,
        ):
            raise ValueError(f"unsupported member relation: {self.relation!r}")
        if self.promotion_status not in (PROMOTION_PROMOTED, PROMOTION_NOT_PROMOTED):
            raise ValueError(
                f"unsupported member promotion status: {self.promotion_status!r}"
            )
        _bounded_identifier(
            self.source_identifier,
            "member source identifier",
            maximum=MAX_SOURCE_IDENTIFIER_LENGTH,
        )
        _require_sha256(self.source_content_sha256, "member source content digest")
        _require_sha256(
            self.acquisition_receipt_fingerprint,
            "member acquisition receipt fingerprint",
        )
        _ordered_vocabulary(self.verified_roles, EVIDENCE_ROLES, "verified role")
        _ordered_vocabulary(self.rejected_roles, EVIDENCE_ROLES, "rejected role")
        if self.semantic_relation_status != LEVEL_ANALYZER_ASSESSED:
            raise ValueError(
                "an admitted member states an analyzer-assessed semantic relation"
            )
        _require_sha256(self.lineage_group_id, "lineage group id")
        if self.independence_state not in INDEPENDENCE_STATES:
            raise ValueError(
                f"unsupported independence state: {self.independence_state!r}"
            )
        for name in (
            "analyzer_proposal_fingerprint",
            "coverage_receipt_fingerprint",
            "current_state_receipt_fingerprint",
        ):
            _require_sha256(getattr(self, name), name.replace("_", " "), optional=True)
        if self.schema_version != MEMBER_SCHEMA_VERSION:
            raise ValueError("unsupported evidence set member schema version")

    @property
    def directional(self) -> bool:
        return self.relation in DIRECTIONAL_RELATIONS

    @property
    def addresses_proposition(self) -> bool:
        return self.relation in ADDRESSING_RELATIONS

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "record_fingerprint": self.record_fingerprint,
            "status": self.status,
            "relation": self.relation,
            "source_identifier": self.source_identifier,
            "source_content_sha256": self.source_content_sha256,
            "acquisition_receipt_fingerprint": self.acquisition_receipt_fingerprint,
            "verified_roles": list(self.verified_roles),
            "rejected_roles": list(self.rejected_roles),
            "promotion_status": self.promotion_status,
            "semantic_relation_status": self.semantic_relation_status,
            "semantic_relation_proved_deterministically": False,
            "evidence_span_fingerprints": list(self.evidence_span_fingerprints),
            "coverage_status": self.coverage_status,
            "coverage_receipt_fingerprint": self.coverage_receipt_fingerprint,
            "current_state_receipt_fingerprint": self.current_state_receipt_fingerprint,
            "analyzer_proposal_fingerprint": self.analyzer_proposal_fingerprint,
            "lineage_group_id": self.lineage_group_id,
            "independence_state": self.independence_state,
            "relation_reinterpreted": False,
        }


# ── Role coverage ─────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class RoleCoverage:
    """What the set holds for one evidence role.

    ``present`` and ``directional_present`` are separate on purpose.  A source
    verified as ``implementation_authority`` whose relation is ``insufficient``
    discharges role *presence* — the set does contain an implementation-authority
    reading — and discharges no directional support whatsoever.  Collapsing the
    two is how "we looked at the implementation" becomes "the implementation
    says yes".

    ``unrelated_only`` is the third case: the role appears in the set but only
    on records that have nothing to do with the proposition, which discharges
    nothing at all.
    """

    role: str
    required: bool
    present: bool
    directional_present: bool
    unrelated_only: bool
    schema_version: str = ROLE_COVERAGE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.role not in EVIDENCE_ROLES:
            raise ValueError(f"unsupported evidence role: {self.role!r}")
        for name in ("required", "present", "directional_present", "unrelated_only"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        if self.directional_present and not self.present:
            raise ValueError("a directional record is a present record")
        if self.unrelated_only and self.present:
            raise ValueError("a role is either present or unrelated-only, never both")
        if self.schema_version != ROLE_COVERAGE_SCHEMA_VERSION:
            raise ValueError("unsupported role coverage schema version")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "role": self.role,
            "required": self.required,
            "present": self.present,
            "directional_present": self.directional_present,
            "unrelated_only": self.unrelated_only,
            "role_presence_discharges_proposition_assessment": False,
        }


# ── Lineage groups and independence ───────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class LineageGroup:
    """One epistemic lineage: sources that are, or may be, the same reading."""

    lineage_group_id: str
    source_identifiers: tuple[str, ...]
    content_sha256_digests: tuple[str, ...]
    record_fingerprints: tuple[str, ...]
    independence_state: str
    basis: tuple[str, ...]
    schema_version: str = LINEAGE_GROUP_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_sha256(self.lineage_group_id, "lineage group id")
        if not isinstance(self.source_identifiers, tuple) or not self.source_identifiers:
            raise ValueError("a lineage group names at least one source")
        if self.source_identifiers != tuple(sorted(self.source_identifiers)):
            raise ValueError("lineage group sources must be canonically ordered")
        for identifier in self.source_identifiers:
            _bounded_identifier(
                identifier,
                "lineage group source identifier",
                maximum=MAX_SOURCE_IDENTIFIER_LENGTH,
            )
        if self.content_sha256_digests != tuple(sorted(self.content_sha256_digests)):
            raise ValueError("lineage group digests must be canonically ordered")
        for digest in self.content_sha256_digests:
            _require_sha256(digest, "lineage group content digest")
        if self.record_fingerprints != tuple(sorted(self.record_fingerprints)):
            raise ValueError("lineage group records must be canonically ordered")
        for digest in self.record_fingerprints:
            _require_sha256(digest, "lineage group record fingerprint")
        if self.independence_state not in INDEPENDENCE_STATES:
            raise ValueError(
                f"unsupported independence state: {self.independence_state!r}"
            )
        _ordered_vocabulary(self.basis, LINEAGE_BASES, "lineage basis")
        if not self.basis:
            raise ValueError("a lineage group states the basis of its state")
        if self.independence_state == INDEPENDENCE_INDEPENDENT and (
            LINEAGE_BASIS_DECLARED_DISTINCT_ORIGIN not in self.basis
        ):
            raise ValueError(
                "independence is established only by a supplied distinct-origin "
                "declaration, never by differing paths or digests"
            )
        if self.schema_version != LINEAGE_GROUP_SCHEMA_VERSION:
            raise ValueError("unsupported lineage group schema version")

    @property
    def source_count(self) -> int:
        return len(self.source_identifiers)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "lineage_group_id": self.lineage_group_id,
            "source_identifiers": list(self.source_identifiers),
            "content_sha256_digests": list(self.content_sha256_digests),
            "record_fingerprints": list(self.record_fingerprints),
            "independence_state": self.independence_state,
            "basis": list(self.basis),
            "independence_inferred_from_paths": False,
        }


@dataclass(frozen=True, slots=True)
class IndependenceAssessment:
    """How many distinct lineages the set actually holds, and how sure that is.

    Group counts are structural facts about the material, not weights.  Two
    independent groups is not "twice as true" as one; it is two lineages.
    """

    record_count: int
    source_count: int
    lineage_groups: tuple[LineageGroup, ...]
    duplicate_group_count: int
    independent_group_count: int
    unknown_independence_group_count: int
    exact_duplicates_present: bool
    schema_version: str = INDEPENDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "record_count",
            "source_count",
            "duplicate_group_count",
            "independent_group_count",
            "unknown_independence_group_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a finite non-negative integer")
        if not isinstance(self.lineage_groups, tuple):
            raise TypeError("lineage_groups must be a tuple")
        if any(not isinstance(item, LineageGroup) for item in self.lineage_groups):
            raise TypeError("lineage_groups must contain LineageGroup records")
        identifiers = [item.lineage_group_id for item in self.lineage_groups]
        if identifiers != sorted(identifiers):
            raise ValueError("lineage groups must be canonically ordered")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("a lineage group appears exactly once")
        counted = (
            self.duplicate_group_count
            + self.independent_group_count
            + self.unknown_independence_group_count
        )
        if counted != len(self.lineage_groups):
            raise ValueError("every lineage group is counted exactly once")
        if not isinstance(self.exact_duplicates_present, bool):
            raise TypeError("exact_duplicates_present must be a bool")
        if self.schema_version != INDEPENDENCE_SCHEMA_VERSION:
            raise ValueError("unsupported independence assessment schema version")

    @property
    def lineage_group_count(self) -> int:
        return len(self.lineage_groups)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "record_count": self.record_count,
            "source_count": self.source_count,
            "lineage_group_count": self.lineage_group_count,
            "lineage_groups": [item.as_dict() for item in self.lineage_groups],
            "duplicate_group_count": self.duplicate_group_count,
            "independent_group_count": self.independent_group_count,
            "unknown_independence_group_count": self.unknown_independence_group_count,
            "exact_duplicates_present": self.exact_duplicates_present,
            "independence_scored": False,
            "record_count_is_evidence_weight": False,
        }


# ── Authority and guardrails ──────────────────────────────────────────────────

def evidence_set_authority(*, assessment_performed: bool) -> dict[str, bool]:
    """One narrow authority, conditional on a describable set; everything else false.

    ``claim_decision_authority`` and ``final_claim_authority`` are false in every
    outcome, including the ones a reader would most like to treat as a verdict:
    support-only, coverage complete, no contradiction, several lineages.
    """
    return {
        "evidence_set_assessment_authority": assessment_performed,
        "evidence_acquisition_authority": False,
        "evidence_verification_authority": False,
        "evidence_promotion_authority": False,
        "repository_read_authority": False,
        "repository_traversal_authority": False,
        "external_search_authority": False,
        "web_fetch_authority": False,
        "context_selection_authority": False,
        "indexing_authority": False,
        "graph_authority": False,
        "validation_execution_authority": False,
        "command_execution_authority": False,
        "worker_launch_authority": False,
        "repository_write_authority": False,
        "patch_authority": False,
        "planning_authority": False,
        "routing_authority": False,
        "model_selection_authority": False,
        "provider_selection_authority": False,
        "project_evolution_authority": False,
        "claim_decision_authority": False,
        "final_claim_authority": False,
        "human_approval_required": True,
    }


def evidence_set_guardrails(
    *,
    evidence_records_aggregated: bool,
    duplicate_analysis_performed: bool,
    role_coverage_assessed: bool,
    conflict_assessed: bool,
) -> dict[str, bool]:
    """Honest performed-state: what was done, and the long list of what was not."""
    return {
        "evidence_records_aggregated": evidence_records_aggregated,
        "duplicate_analysis_performed": duplicate_analysis_performed,
        "role_coverage_assessed": role_coverage_assessed,
        "conflict_assessed": conflict_assessed,
        "source_content_read": False,
        "evidence_acquired": False,
        "repository_traversed": False,
        "repository_files_read": False,
        "network_called": False,
        "web_search_performed": False,
        "index_consulted": False,
        "graph_consulted": False,
        "validation_executed": False,
        "repository_written": False,
        "patch_created": False,
        "model_called": False,
        "claim_decision_performed": False,
        "final_claim_emitted": False,
        "confidence_computed": False,
        "majority_vote_computed": False,
        "relations_reinterpreted": False,
        "semantic_status_upgraded": False,
        "coverage_receipts_minted": False,
        "current_state_receipts_minted": False,
        "lineage_inferred_from_paths": False,
    }


# ── The assessment ────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class EvidenceSetAssessment:
    """What one evidence set contains.  Never whether the proposition holds.

    Read the four coverage fields and the conflict status as *descriptions of
    the material*.  ``support_only`` says the set holds directional support and
    no directional contradiction; it does not say the claim is true, and there
    is no field in this record that does.
    """

    set_status: str
    proposition_id: str
    proposition_sha256: str
    proposition_type: str
    proposition_scope: str
    request_fingerprint: str
    members: tuple[EvidenceSetMember, ...] = ()
    support_records: tuple[str, ...] = ()
    contradiction_records: tuple[str, ...] = ()
    insufficient_records: tuple[str, ...] = ()
    unrelated_records: tuple[str, ...] = ()
    role_coverage: tuple[RoleCoverage, ...] = ()
    role_coverage_status: str = COVERAGE_NOT_ASSESSED
    scope_coverage: str = COVERAGE_NOT_ASSESSED
    negative_claim_coverage: str = COVERAGE_NOT_ASSESSED
    current_state_coverage: str = COVERAGE_NOT_ASSESSED
    conflict_status: str = CONFLICT_NOT_ASSESSED
    independence: IndependenceAssessment | None = None
    verification_levels: VerificationLevels | None = None
    missing_requirements: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    inconsistencies: tuple[str, ...] = ()
    schema_version: str = ASSESSMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.set_status not in SET_STATUSES:
            raise ValueError(f"unsupported set status: {self.set_status!r}")
        _bounded_identifier(
            self.proposition_id,
            "assessment proposition_id",
            maximum=MAX_PROPOSITION_ID_LENGTH,
        )
        _require_sha256(self.proposition_sha256, "assessment proposition digest")
        if self.proposition_type not in PROPOSITION_TYPES:
            raise ValueError(f"unsupported proposition type: {self.proposition_type!r}")
        if self.proposition_scope not in PROPOSITION_SCOPES:
            raise ValueError(
                f"unsupported proposition scope: {self.proposition_scope!r}"
            )
        _require_sha256(self.request_fingerprint, "assessment request fingerprint")
        _typed_tuple(
            self.members,
            EvidenceSetMember,
            maximum=MAX_EVIDENCE_SET_RECORDS,
            label="assessed member",
        )
        fingerprints = [item.record_fingerprint for item in self.members]
        if fingerprints != sorted(fingerprints):
            raise ValueError("assessed members must be canonically ordered")
        if len(set(fingerprints)) != len(fingerprints):
            raise ValueError("a record is assessed exactly once")
        known = set(fingerprints)
        grouped: list[str] = []
        for group in (
            self.support_records,
            self.contradiction_records,
            self.insufficient_records,
            self.unrelated_records,
        ):
            if not isinstance(group, tuple):
                raise TypeError("relation groups must be tuples")
            if list(group) != sorted(group):
                raise ValueError("relation groups must be canonically ordered")
            for item in group:
                _require_sha256(item, "grouped record fingerprint")
                if item not in known:
                    raise ValueError("a relation group names an unassessed record")
            grouped.extend(group)
        if len(set(grouped)) != len(grouped):
            raise ValueError("a record belongs to exactly one relation group")
        if self.set_status == SET_ASSESSED and set(grouped) != known:
            raise ValueError("every assessed member belongs to a relation group")
        _typed_tuple(
            self.role_coverage,
            RoleCoverage,
            maximum=MAX_ROLE_COVERAGE_ENTRIES,
            label="role coverage entry",
        )
        roles = [item.role for item in self.role_coverage]
        if roles != [item for item in EVIDENCE_ROLES if item in set(roles)]:
            raise ValueError("role coverage must use canonical role order")
        for name in (
            "role_coverage_status",
            "scope_coverage",
            "negative_claim_coverage",
            "current_state_coverage",
        ):
            if getattr(self, name) not in SET_COVERAGE_STATUSES:
                raise ValueError(f"unsupported {name}: {getattr(self, name)!r}")
        if self.conflict_status not in CONFLICT_STATUSES:
            raise ValueError(f"unsupported conflict status: {self.conflict_status!r}")
        if self.independence is not None and not isinstance(
            self.independence, IndependenceAssessment
        ):
            raise TypeError("independence must be an IndependenceAssessment or None")
        if self.verification_levels is not None and not isinstance(
            self.verification_levels, VerificationLevels
        ):
            raise TypeError("verification_levels must be a VerificationLevels or None")
        _ordered_vocabulary(
            self.missing_requirements,
            MISSING_REQUIREMENTS,
            "missing requirement",
        )
        _ordered_vocabulary(self.reasons, SET_REASONS, "set reason")
        _ordered_vocabulary(self.inconsistencies, SET_INCONSISTENCIES, "set inconsistency")

        if self.set_status == SET_INCONSISTENT_INPUT:
            if not self.inconsistencies:
                raise ValueError("inconsistent input must state its inconsistency")
            if self.conflict_status != CONFLICT_NOT_ASSESSED:
                raise ValueError("an unusable set is not partitioned")
            if self.members or grouped:
                raise ValueError("an unusable set admits no members")
        else:
            if self.inconsistencies:
                raise ValueError("an assessed set carries no inconsistency")
            if self.conflict_status == CONFLICT_NOT_ASSESSED:
                raise ValueError("an assessed set states its conflict status")
            if self.independence is None or self.verification_levels is None:
                raise ValueError(
                    "an assessed set states independence and verification levels"
                )
            if self.verification_levels.semantic_relation != LEVEL_ANALYZER_ASSESSED:
                raise ValueError(
                    "aggregating analyzer-assessed relations leaves them "
                    "analyzer-assessed"
                )
        if self.schema_version != ASSESSMENT_SCHEMA_VERSION:
            raise ValueError("unsupported evidence set assessment schema version")

    # -- The two answers this phase never gives ------------------------------

    @property
    def claim_decision_authority(self) -> bool:
        """Always false.  CLAIM.1 owns proposition assessment; this is a property
        rather than a field so that no construction path can set it."""
        return False

    @property
    def final_claim_authority(self) -> bool:
        return False

    @property
    def conflicting(self) -> bool:
        return self.conflict_status == CONFLICT_CONFLICTING

    @property
    def record_count(self) -> int:
        return len(self.members)

    def _identity(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "set_status": self.set_status,
            "proposition_id": self.proposition_id,
            "proposition_sha256": self.proposition_sha256,
            "proposition_type": self.proposition_type,
            "proposition_scope": self.proposition_scope,
            "request_fingerprint": self.request_fingerprint,
            "members": [item.as_dict() for item in self.members],
            "support_records": list(self.support_records),
            "contradiction_records": list(self.contradiction_records),
            "insufficient_records": list(self.insufficient_records),
            "unrelated_records": list(self.unrelated_records),
            "role_coverage": [item.as_dict() for item in self.role_coverage],
            "role_coverage_status": self.role_coverage_status,
            "scope_coverage": self.scope_coverage,
            "negative_claim_coverage": self.negative_claim_coverage,
            "current_state_coverage": self.current_state_coverage,
            "conflict_status": self.conflict_status,
            "independence": (
                None if self.independence is None else self.independence.as_dict()
            ),
            "verification_levels": (
                None
                if self.verification_levels is None
                else self.verification_levels.as_dict()
            ),
            "missing_requirements": list(self.missing_requirements),
            "reasons": list(self.reasons),
            "inconsistencies": list(self.inconsistencies),
        }

    @property
    def assessment_fingerprint(self) -> str:
        """Deterministic identity.  No timestamp, no counter, no random token."""
        return _fingerprint(self._identity())

    def as_dict(self) -> dict[str, Any]:
        payload = dict(self._identity())
        payload["assessment_fingerprint"] = self.assessment_fingerprint
        payload["record_count"] = self.record_count
        payload["claim_decision_authority"] = self.claim_decision_authority
        payload["final_claim_authority"] = self.final_claim_authority
        payload["authority"] = evidence_set_authority(
            assessment_performed=self.set_status == SET_ASSESSED,
        )
        payload["guardrails"] = evidence_set_guardrails(
            evidence_records_aggregated=self.set_status == SET_ASSESSED,
            duplicate_analysis_performed=self.set_status == SET_ASSESSED,
            role_coverage_assessed=self.set_status == SET_ASSESSED,
            conflict_assessed=self.set_status == SET_ASSESSED,
        )
        payload["source_content_read"] = False
        payload["claim_decided"] = False
        return payload


def render_evidence_set_assessment_json(assessment: EvidenceSetAssessment) -> str:
    if not isinstance(assessment, EvidenceSetAssessment):
        raise TypeError(
            "render_evidence_set_assessment_json requires an EvidenceSetAssessment"
        )
    return json.dumps(assessment.as_dict(), indent=2, ensure_ascii=False, sort_keys=False)


# ── Lineage grouping ──────────────────────────────────────────────────────────

def _group_sources(
    sources: dict[str, str],
    declarations: tuple[SourceLineageDeclaration, ...],
) -> tuple[dict[str, str], dict[str, set[str]]]:
    """Collapse sources into lineage groups, then name each group.

    Two collapses happen, and only two.  Sources whose content digests are
    identical are the same reading — that is arithmetic, not judgement.  Sources
    a supplied declaration marks as restating each other are the same reading
    too, on the declarer's authority.  Nothing else collapses anything, and in
    particular a shared directory, a similar name or a similar role does not.
    """
    parent: dict[str, str] = {identifier: identifier for identifier in sources}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return
        if left_root < right_root:
            parent[right_root] = left_root
        else:
            parent[left_root] = right_root

    by_digest: dict[str, list[str]] = {}
    for identifier, digest in sources.items():
        by_digest.setdefault(digest, []).append(identifier)
    for identifiers in by_digest.values():
        for other in identifiers[1:]:
            union(identifiers[0], other)

    for declaration in declarations:
        if declaration.lineage_relation != LINEAGE_RESTATES:
            continue
        union(declaration.source_identifier, declaration.related_source_identifier)

    members: dict[str, set[str]] = {}
    for identifier in sources:
        members.setdefault(find(identifier), set()).add(identifier)
    return {identifier: find(identifier) for identifier in sources}, members


def _lineage_group_id(identifiers: tuple[str, ...], sources: dict[str, str]) -> str:
    return _fingerprint(
        {
            "phase_id": PHASE_ID,
            "schema_version": LINEAGE_GROUP_SCHEMA_VERSION,
            "sources": [
                {"source_identifier": item, "source_content_sha256": sources[item]}
                for item in identifiers
            ],
        }
    )


# ── The entry point ───────────────────────────────────────────────────────────

def assess_evidence_set(request: EvidenceSetRequest) -> EvidenceSetAssessment:
    """Describe one evidence set for one proposition.  Decide nothing about it.

    The order is deliberate: admission before description, because describing an
    incoherent set produces a confident picture of nothing.  Every fatal problem
    is collected rather than raised, so a caller gets the whole list at once.
    """
    if not isinstance(request, EvidenceSetRequest):
        raise TypeError("assess_evidence_set requires an EvidenceSetRequest")

    proposition = request.proposition
    fingerprint = evidence_set_request_fingerprint(request)
    inconsistencies: set[str] = set()

    # 1 ── every record is about *this* proposition, and no other.
    for record in request.records:
        if (
            record.proposition_id != proposition.proposition_id
            or record.proposition_sha256 != proposition.proposition_sha256
            or record.proposition_type != proposition.proposition_type
            or record.proposition_scope != proposition.scope
        ):
            inconsistencies.add(INCONSISTENT_MIXED_PROPOSITION)

    # 2 ── identities are re-derived here, never read off the caller's record.
    record_fingerprints = [evidence_record_fingerprint(item) for item in request.records]
    if len(set(record_fingerprints)) != len(record_fingerprints):
        inconsistencies.add(INCONSISTENT_RECORD_IDENTITY_REPEATED)

    # 3 ── a record that established nothing about the claim is not evidence.
    for record in request.records:
        if record.status not in ADMISSIBLE_MEMBER_STATUSES:
            inconsistencies.add(INCONSISTENT_RECORD_NOT_ADMISSIBLE)
            continue
        if record.relation is None:
            inconsistencies.add(INCONSISTENT_RECORD_NOT_ADMISSIBLE)
            continue
        if not record.verification_levels.semantic_relation_assessed:
            inconsistencies.add(INCONSISTENT_SEMANTIC_STATUS_ABSENT)

    # 4 ── one identifier names one set of bytes, or the set is ambiguous.
    sources: dict[str, str] = {}
    for record in request.records:
        existing = sources.get(record.source_identifier)
        if existing is not None and existing != record.source_content_sha256:
            inconsistencies.add(INCONSISTENT_SOURCE_CONTENT_CONFLICT)
        sources[record.source_identifier] = record.source_content_sha256

    # 5 ── absence is supported only through coverage; a hand-built record that
    #      says otherwise is refused rather than counted.
    supplied_coverage = {
        coverage_fingerprint(item): item for item in request.coverage_receipts
    }
    negative = proposition.proposition_type == PROPOSITION_NEGATIVE_EXISTENTIAL
    for record in request.records:
        if record.relation != RELATION_SUPPORTS or not negative:
            continue
        if (
            record.promotion_status != PROMOTION_PROMOTED
            or record.coverage_status != COVERAGE_SUFFICIENT
            or record.coverage_receipt_fingerprint is None
        ):
            inconsistencies.add(INCONSISTENT_NEGATIVE_SUPPORT_UNCOVERED)
        elif record.coverage_receipt_fingerprint not in supplied_coverage:
            inconsistencies.add(INCONSISTENT_COVERAGE_RECEIPT_UNSUPPLIED)

    # 6 ── supplied receipts describe this proposition, this scope, these sources.
    for receipt in request.coverage_receipts:
        if not negative or (
            receipt.proposition_id != proposition.proposition_id
            or receipt.proposition_sha256 != proposition.proposition_sha256
        ):
            inconsistencies.add(INCONSISTENT_COVERAGE_RECEIPT_BINDING)

    needs_current_state = proposition.scope in SCOPES_REQUIRING_CURRENT_STATE
    supplied_current_state = {
        current_state_fingerprint(item): item for item in request.current_state_receipts
    }
    for receipt in request.current_state_receipts:
        if not needs_current_state or (
            receipt.proposition_id != proposition.proposition_id
            or receipt.proposition_sha256 != proposition.proposition_sha256
        ):
            inconsistencies.add(INCONSISTENT_CURRENT_STATE_RECEIPT_BINDING)
            continue
        if sources.get(receipt.candidate_identifier) != receipt.source_content_sha256:
            inconsistencies.add(INCONSISTENT_CURRENT_STATE_RECEIPT_BINDING)

    # 7 ── lineage is about sources this set actually holds.
    for declaration in request.lineage_declarations:
        if (
            declaration.proposition_id != proposition.proposition_id
            or declaration.proposition_sha256 != proposition.proposition_sha256
            or sources.get(declaration.source_identifier)
            != declaration.source_content_sha256
            or sources.get(declaration.related_source_identifier)
            != declaration.related_source_content_sha256
        ):
            inconsistencies.add(INCONSISTENT_LINEAGE_BINDING)

    # 8 ── requirements are about this proposition.
    requirements = request.requirements
    if requirements is not None and (
        requirements.proposition_id != proposition.proposition_id
        or requirements.proposition_sha256 != proposition.proposition_sha256
    ):
        inconsistencies.add(INCONSISTENT_REQUIREMENTS_BINDING)

    if inconsistencies:
        return EvidenceSetAssessment(
            set_status=SET_INCONSISTENT_INPUT,
            proposition_id=proposition.proposition_id,
            proposition_sha256=proposition.proposition_sha256,
            proposition_type=proposition.proposition_type,
            proposition_scope=proposition.scope,
            request_fingerprint=fingerprint,
            reasons=_ordered_reasons(
                {
                    SET_RECORD_IDENTITIES_REDERIVED,
                    SET_INPUT_REJECTED,
                    SET_NO_MAJORITY_COMPUTED,
                    SET_NO_CONFIDENCE_COMPUTED,
                    SET_NO_CLAIM_DECISION_PERFORMED,
                }
            ),
            inconsistencies=_ordered_inconsistencies(inconsistencies),
        )

    return _describe(
        request,
        fingerprint=fingerprint,
        record_fingerprints=record_fingerprints,
        sources=sources,
        supplied_coverage=supplied_coverage,
        supplied_current_state=supplied_current_state,
        negative=negative,
        needs_current_state=needs_current_state,
    )


def _describe(
    request: EvidenceSetRequest,
    *,
    fingerprint: str,
    record_fingerprints: list[str],
    sources: dict[str, str],
    supplied_coverage: dict[str, NegativeClaimCoverage],
    supplied_current_state: dict[str, CurrentStateReceipt],
    negative: bool,
    needs_current_state: bool,
) -> EvidenceSetAssessment:
    """Describe an admitted set.  Called only after every admission check passed."""
    proposition = request.proposition

    # -- lineage first: membership decides how everything else is reported ----
    group_of, group_members = _group_sources(sources, request.lineage_declarations)
    records_by_source: dict[str, list[str]] = {}
    for record, digest in zip(request.records, record_fingerprints):
        records_by_source.setdefault(record.source_identifier, []).append(digest)

    declared_restatements = {
        declaration.pair
        for declaration in request.lineage_declarations
        if declaration.lineage_relation == LINEAGE_RESTATES
    }
    distinct_origin_pairs = {
        declaration.pair
        for declaration in request.lineage_declarations
        if declaration.lineage_relation == LINEAGE_DISTINCT_ORIGIN
    }

    group_ids: dict[str, str] = {}
    group_identifiers: dict[str, tuple[str, ...]] = {}
    for root, identifiers in group_members.items():
        ordered = tuple(sorted(identifiers))
        group_identifiers[root] = ordered
        group_ids[root] = _lineage_group_id(ordered, sources)

    def _independence_for(root: str) -> tuple[str, set[str]]:
        identifiers = group_identifiers[root]
        basis: set[str] = set()
        digests = {sources[item] for item in identifiers}
        if len(identifiers) > 1:
            # Identical content collapses whatever anyone declares: two sources
            # with the same digest are the same reading, and a distinct-origin
            # note about them describes authorship, not epistemic independence.
            if len(digests) < len(identifiers):
                basis.add(LINEAGE_BASIS_IDENTICAL_CONTENT)
            if any(
                pair[0] in identifiers and pair[1] in identifiers
                for pair in declared_restatements
            ):
                basis.add(LINEAGE_BASIS_DECLARED_RESTATEMENT)
            if not basis:  # pragma: no cover - defensive; a group has a cause
                basis.add(LINEAGE_BASIS_IDENTICAL_CONTENT)
            return INDEPENDENCE_DUPLICATE, basis

        others = [other for other in group_identifiers if other != root]
        only = identifiers[0]
        if others and all(
            any(
                tuple(sorted((only, candidate))) in distinct_origin_pairs
                for candidate in group_identifiers[other]
            )
            for other in others
        ):
            return INDEPENDENCE_INDEPENDENT, {LINEAGE_BASIS_DECLARED_DISTINCT_ORIGIN}
        return INDEPENDENCE_UNKNOWN, {LINEAGE_BASIS_NO_LINEAGE_METADATA}

    group_states: dict[str, tuple[str, set[str]]] = {
        root: _independence_for(root) for root in group_identifiers
    }

    groups: list[LineageGroup] = []
    for root, identifiers in group_identifiers.items():
        state, basis = group_states[root]
        fingerprints: set[str] = set()
        for identifier in identifiers:
            fingerprints.update(records_by_source.get(identifier, ()))
        groups.append(
            LineageGroup(
                lineage_group_id=group_ids[root],
                source_identifiers=identifiers,
                content_sha256_digests=tuple(
                    sorted({sources[item] for item in identifiers})
                ),
                record_fingerprints=tuple(sorted(fingerprints)),
                independence_state=state,
                basis=tuple(item for item in LINEAGE_BASES if item in basis),
            )
        )
    groups.sort(key=lambda item: item.lineage_group_id)

    exact_duplicates = any(
        LINEAGE_BASIS_IDENTICAL_CONTENT in group.basis for group in groups
    )
    independence = IndependenceAssessment(
        record_count=len(request.records),
        source_count=len(sources),
        lineage_groups=tuple(groups),
        duplicate_group_count=sum(
            1 for item in groups if item.independence_state == INDEPENDENCE_DUPLICATE
        ),
        independent_group_count=sum(
            1 for item in groups if item.independence_state == INDEPENDENCE_INDEPENDENT
        ),
        unknown_independence_group_count=sum(
            1 for item in groups if item.independence_state == INDEPENDENCE_UNKNOWN
        ),
        exact_duplicates_present=exact_duplicates,
    )

    # -- members --------------------------------------------------------------
    members: list[EvidenceSetMember] = []
    for record, digest in zip(request.records, record_fingerprints):
        root = group_of[record.source_identifier]
        state, _ = group_states[root]
        assert record.relation is not None  # admission proved it
        members.append(
            EvidenceSetMember(
                record_fingerprint=digest,
                status=record.status,
                relation=record.relation,
                source_identifier=record.source_identifier,
                source_content_sha256=record.source_content_sha256,
                acquisition_receipt_fingerprint=record.acquisition_receipt_fingerprint,
                verified_roles=record.verified_roles,
                rejected_roles=record.rejected_roles,
                promotion_status=record.promotion_status,
                semantic_relation_status=record.verification_levels.semantic_relation,
                evidence_span_fingerprints=tuple(
                    sorted({ref.span_sha256 for ref in record.evidence_span_refs})
                ),
                coverage_status=record.coverage_status,
                lineage_group_id=group_ids[root],
                independence_state=state,
                analyzer_proposal_fingerprint=record.analyzer_proposal_fingerprint,
                coverage_receipt_fingerprint=record.coverage_receipt_fingerprint,
                current_state_receipt_fingerprint=record.current_state_fingerprint,
            )
        )
    members.sort(key=lambda item: item.record_fingerprint)

    # -- relation grouping: partition, never reinterpretation ------------------
    def _group_for(relation: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                item.record_fingerprint
                for item in members
                if item.relation == relation
            )
        )

    support_records = _group_for(RELATION_SUPPORTS)
    contradiction_records = _group_for(RELATION_CONTRADICTS)
    insufficient_records = _group_for(RELATION_INSUFFICIENT)
    unrelated_records = _group_for(RELATION_UNRELATED)

    # -- conflict: composition, with no winner --------------------------------
    if support_records and contradiction_records:
        conflict_status = CONFLICT_CONFLICTING
    elif support_records:
        conflict_status = CONFLICT_SUPPORT_ONLY
    elif contradiction_records:
        conflict_status = CONFLICT_CONTRADICTION_ONLY
    else:
        conflict_status = CONFLICT_NO_DIRECTIONAL_EVIDENCE

    # -- role coverage --------------------------------------------------------
    requirements = request.requirements
    required_roles = set(requirements.required_roles) if requirements else set()
    addressing_roles: set[str] = set()
    directional_roles: set[str] = set()
    unrelated_roles: set[str] = set()
    for member in members:
        if member.addresses_proposition:
            addressing_roles.update(member.verified_roles)
            if member.directional:
                directional_roles.update(member.verified_roles)
        else:
            unrelated_roles.update(member.verified_roles)

    reported_roles = required_roles | addressing_roles | unrelated_roles
    role_coverage = tuple(
        RoleCoverage(
            role=role,
            required=role in required_roles,
            present=role in addressing_roles,
            directional_present=role in directional_roles,
            unrelated_only=role in unrelated_roles and role not in addressing_roles,
        )
        for role in _ordered_roles(reported_roles)
    )
    if requirements is None:
        role_coverage_status = COVERAGE_NOT_APPLICABLE
    elif required_roles <= addressing_roles:
        role_coverage_status = COVERAGE_COMPLETE
    else:
        role_coverage_status = COVERAGE_INCOMPLETE

    competent = SCOPE_COMPETENT_ROLES[proposition.scope]
    scope_coverage = (
        COVERAGE_COMPLETE
        if addressing_roles & competent
        else COVERAGE_INCOMPLETE
    )

    # -- negative-claim coverage ----------------------------------------------
    negative_claim_coverage = _negative_coverage_status(
        negative=negative,
        receipts=tuple(supplied_coverage.values()),
    )

    # -- current-state coverage -----------------------------------------------
    current_state_coverage = _current_state_coverage_status(
        needs_current_state=needs_current_state,
        members=tuple(members),
        supplied=supplied_current_state,
    )

    # -- what the set does not contain ----------------------------------------
    missing: set[str] = set()
    if requirements is None:
        missing.add(MISSING_ROLE_REQUIREMENTS_NOT_SUPPLIED)
    if role_coverage_status == COVERAGE_INCOMPLETE:
        missing.add(MISSING_REQUIRED_ROLE)
    if scope_coverage != COVERAGE_COMPLETE:
        missing.add(MISSING_SCOPE_COMPETENT_ROLE)
    if conflict_status == CONFLICT_NO_DIRECTIONAL_EVIDENCE:
        missing.add(MISSING_DIRECTIONAL_EVIDENCE)
    if negative_claim_coverage in {COVERAGE_INCOMPLETE, COVERAGE_INCONSISTENT}:
        missing.add(MISSING_NEGATIVE_CLAIM_COVERAGE)
    if current_state_coverage in {COVERAGE_INCOMPLETE, COVERAGE_INCONSISTENT}:
        missing.add(MISSING_CURRENT_STATE_COVERAGE)
    if support_records:
        supporting_groups = {
            item.lineage_group_id for item in members
            if item.record_fingerprint in set(support_records)
        }
        independent_ids = {
            group.lineage_group_id
            for group in groups
            if group.independence_state == INDEPENDENCE_INDEPENDENT
        }
        if len(supporting_groups & independent_ids) < 2:
            missing.add(MISSING_INDEPENDENT_CORROBORATION)

    # -- set-level levels: the weakest structural link, and no upgrade --------
    levels = _set_levels(tuple(members), request.records)

    reasons = {
        SET_PROPOSITION_BINDING_VERIFIED,
        SET_RECORD_IDENTITIES_REDERIVED,
        SET_RELATIONS_PARTITIONED,
        SET_ROLE_COVERAGE_ASSESSED,
        SET_SCOPE_COVERAGE_ASSESSED,
        SET_CONFLICT_ASSESSED,
        SET_DUPLICATE_ANALYSIS_PERFORMED,
        SET_SEMANTIC_STATUS_PRESERVED,
        SET_NO_MAJORITY_COMPUTED,
        SET_NO_CONFIDENCE_COMPUTED,
        SET_NO_CLAIM_DECISION_PERFORMED,
    }
    if negative:
        reasons.add(SET_NEGATIVE_COVERAGE_ASSESSED)
    if needs_current_state:
        reasons.add(SET_CURRENT_STATE_COVERAGE_ASSESSED)

    return EvidenceSetAssessment(
        set_status=SET_ASSESSED,
        proposition_id=proposition.proposition_id,
        proposition_sha256=proposition.proposition_sha256,
        proposition_type=proposition.proposition_type,
        proposition_scope=proposition.scope,
        request_fingerprint=fingerprint,
        members=tuple(members),
        support_records=support_records,
        contradiction_records=contradiction_records,
        insufficient_records=insufficient_records,
        unrelated_records=unrelated_records,
        role_coverage=role_coverage,
        role_coverage_status=role_coverage_status,
        scope_coverage=scope_coverage,
        negative_claim_coverage=negative_claim_coverage,
        current_state_coverage=current_state_coverage,
        conflict_status=conflict_status,
        independence=independence,
        verification_levels=levels,
        missing_requirements=_ordered_missing(missing),
        reasons=_ordered_reasons(reasons),
    )


def _negative_coverage_status(
    *,
    negative: bool,
    receipts: tuple[NegativeClaimCoverage, ...],
) -> str:
    """Coverage across a *set*, which is not the union of coverage per source.

    Two receipts that describe different acquisition universes cannot be added
    together into a wider one.  Merging them would manufacture exactly the
    confident absence the whole track exists to prevent, so a mismatch is
    ``inconsistent`` and never ``complete``.
    """
    if not negative:
        return COVERAGE_NOT_APPLICABLE
    if not receipts:
        return COVERAGE_INCOMPLETE
    universes = {
        (
            item.acquisition_request_fingerprint,
            item.candidate_pool_fingerprint,
            item.required_roles,
        )
        for item in receipts
    }
    if len(universes) > 1:
        return COVERAGE_INCONSISTENT
    statuses = {item.coverage_status for item in receipts}
    if len(statuses) > 1:
        return COVERAGE_INCONSISTENT
    return COVERAGE_COMPLETE if any(item.is_sufficient for item in receipts) else (
        COVERAGE_INCOMPLETE
    )


def _current_state_coverage_status(
    *,
    needs_current_state: bool,
    members: tuple[EvidenceSetMember, ...],
    supplied: dict[str, CurrentStateReceipt],
) -> str:
    """Currentness across a set, from supplied receipts only.

    Nothing here inspects a runtime, and nothing mints a receipt.  A member with
    no receipt leaves the set incomplete; two receipts that disagree about one
    source leave it inconsistent, because "it is deployed" and "it is not" are
    not two pieces of partial coverage.
    """
    if not needs_current_state:
        return COVERAGE_NOT_APPLICABLE
    by_source: dict[str, set[tuple[str, str]]] = {}
    for receipt in supplied.values():
        by_source.setdefault(receipt.candidate_identifier, set()).add(
            (receipt.source_content_sha256, receipt.current_state_status)
        )
    if any(len(values) > 1 for values in by_source.values()):
        return COVERAGE_INCONSISTENT
    if not members:
        return COVERAGE_INCOMPLETE
    for member in members:
        cited = member.current_state_receipt_fingerprint
        if cited is None or cited not in supplied:
            return COVERAGE_INCOMPLETE
        if not supplied[cited].is_established:
            return COVERAGE_INCOMPLETE
    return COVERAGE_COMPLETE


def _set_levels(
    members: tuple[EvidenceSetMember, ...],
    records: tuple[EvidenceVerificationResult, ...],
) -> VerificationLevels:
    """The set is only as structurally verified as its weakest member.

    And no more semantically established than one member, however many agree:
    ``semantic_relation`` is ``analyzer_assessed`` here for the same reason it is
    ``analyzer_assessed`` there.  Agreement between analyzers is agreement
    between analyzers.
    """
    def _floor(dimension: str) -> str:
        if not records:
            return LEVEL_NOT_ESTABLISHED
        if all(
            getattr(item.verification_levels, dimension)
            == LEVEL_DETERMINISTICALLY_VERIFIED
            for item in records
        ):
            return LEVEL_DETERMINISTICALLY_VERIFIED
        return LEVEL_NOT_ESTABLISHED

    return VerificationLevels(
        source_binding=_floor("source_binding"),
        citation_integrity=_floor("citation_integrity"),
        role_admissibility=_floor("role_admissibility"),
        semantic_relation=(
            LEVEL_ANALYZER_ASSESSED if members else LEVEL_NOT_ESTABLISHED
        ),
    )


__all__ = [
    "ADDRESSING_RELATIONS",
    "ADMISSIBLE_MEMBER_STATUSES",
    "ASSESSMENT_SCHEMA_VERSION",
    "CONFLICT_CONFLICTING",
    "CONFLICT_CONTRADICTION_ONLY",
    "CONFLICT_NOT_ASSESSED",
    "CONFLICT_NO_DIRECTIONAL_EVIDENCE",
    "CONFLICT_STATUSES",
    "CONFLICT_SUPPORT_ONLY",
    "COVERAGE_COMPLETE",
    "COVERAGE_INCOMPLETE",
    "COVERAGE_INCONSISTENT",
    "COVERAGE_NOT_APPLICABLE",
    "COVERAGE_NOT_ASSESSED",
    "INCONSISTENT_COVERAGE_RECEIPT_BINDING",
    "INCONSISTENT_COVERAGE_RECEIPT_UNSUPPLIED",
    "INCONSISTENT_CURRENT_STATE_RECEIPT_BINDING",
    "INCONSISTENT_LINEAGE_BINDING",
    "INCONSISTENT_MIXED_PROPOSITION",
    "INCONSISTENT_NEGATIVE_SUPPORT_UNCOVERED",
    "INCONSISTENT_RECORD_IDENTITY_REPEATED",
    "INCONSISTENT_RECORD_NOT_ADMISSIBLE",
    "INCONSISTENT_REQUIREMENTS_BINDING",
    "INCONSISTENT_SEMANTIC_STATUS_ABSENT",
    "INCONSISTENT_SOURCE_CONTENT_CONFLICT",
    "INDEPENDENCE_DUPLICATE",
    "INDEPENDENCE_INDEPENDENT",
    "INDEPENDENCE_STATES",
    "INDEPENDENCE_UNKNOWN",
    "LINEAGE_BASES",
    "LINEAGE_BASIS_DECLARED_DISTINCT_ORIGIN",
    "LINEAGE_BASIS_DECLARED_RESTATEMENT",
    "LINEAGE_BASIS_IDENTICAL_CONTENT",
    "LINEAGE_BASIS_NO_LINEAGE_METADATA",
    "LINEAGE_DISTINCT_ORIGIN",
    "LINEAGE_RELATIONS",
    "LINEAGE_RESTATES",
    "MAX_EVIDENCE_SET_RECORDS",
    "MAX_LINEAGE_DECLARATIONS",
    "MISSING_CURRENT_STATE_COVERAGE",
    "MISSING_DIRECTIONAL_EVIDENCE",
    "MISSING_INDEPENDENT_CORROBORATION",
    "MISSING_NEGATIVE_CLAIM_COVERAGE",
    "MISSING_REQUIREMENTS",
    "MISSING_REQUIRED_ROLE",
    "MISSING_ROLE_REQUIREMENTS_NOT_SUPPLIED",
    "MISSING_SCOPE_COMPETENT_ROLE",
    "NON_CONFLICTING_STATUSES",
    "PHASE_ID",
    "SET_ASSESSED",
    "SET_COVERAGE_STATUSES",
    "SET_INCONSISTENCIES",
    "SET_INCONSISTENT_INPUT",
    "SET_REASONS",
    "SET_STATUSES",
    "EvidenceSetAssessment",
    "EvidenceSetMember",
    "EvidenceSetRequest",
    "EvidenceSetRequirements",
    "IndependenceAssessment",
    "LineageGroup",
    "RoleCoverage",
    "SourceLineageDeclaration",
    "assess_evidence_set",
    "evidence_record_fingerprint",
    "evidence_set_authority",
    "evidence_set_guardrails",
    "evidence_set_request_fingerprint",
    "lineage_fingerprint",
    "render_evidence_set_assessment_json",
    "requirements_fingerprint",
]
