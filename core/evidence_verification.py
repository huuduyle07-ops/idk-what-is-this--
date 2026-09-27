"""EVIDENCE.1 — Acquired Source Verification & Evidence Promotion Contract.

ACQUIRE.3 answered *what bytes were acquired*.  EVIDENCE.1 answers the next
question and only that one:

    what do these exact bytes establish relative to one supplied proposition?

    Proposition + AcquiredSourcePayload + SourceAcquisitionReceipt
        -> source-role verification
        -> proposition-bound relation
        -> VerifiedEvidence, but only through the deterministic gate

Six boundaries hold in every status.

**The proposition arrives; it is never invented.**  A verification request
cannot be built without one, and :class:`Proposition` computes its own SHA-256
over identifier, text, type and scope together — so an analyzer that rewrites a
word, swaps an entity, adds a qualifier or merges two claims produces a digest
that no longer matches the one the gate holds.  There is no field anywhere in
this module in which an analyzer could write a *different* proposition.

**Candidate class, expected role and verified role are three things.**
ACQUIRE.2 said a file was of a kind.  ACQUIRE.3 recorded that as an
*expectation* about why it was acquired.  Only content read here can turn an
expected role into a verified one, verified roles are a subset of expected
roles, and a role nobody requested cannot be invented into existence.

**Role competence and claim direction are separate axes.**  A source may be
verified ``implementation_authority`` and still be ``insufficient`` for the
proposition; a source may be verified ``validation_evidence`` and
``contradicts``.  What a role *is* never decides which way the evidence points.

**A scope is not established by whatever happened to be acquired.**  Each
proposition names the kind of fact it asserts, and :data:`SCOPE_COMPETENT_ROLES`
is the frozen table of which verified role could establish that kind of fact at
all.  A dependency manifest cannot establish runtime use; a test cannot
establish runtime behaviour; a rejected design note cannot establish current
implementation.  Those are not heuristics applied loosely — they are the
absence of a table entry.

**Absence needs coverage; a counterexample does not.**  Supporting a
``negative_existential`` proposition requires a coverage receipt somebody else
minted, bound to this proposition and this acquisition.  Contradicting one needs
a single concrete incompatible source.  This is the exact epistemic step the
DeepSeek Harness dogfood skipped when a partial map became a confident
architectural absence.

**Nothing here is a number.**  The relation vocabulary is four categorical
values.  No record in this module has a confidence, score or probability field,
so a plausible-sounding analyzer cannot launder uncertainty into authority.

**Structural integrity and semantic entailment are different claims, and the
record says which is which.**  Source binding, citation integrity and role
admissibility are re-derived here from bytes and digests: those are
*deterministically verified*.  Whether the cited span actually entails the
proposition is not, and no amount of structural checking makes it so — a real
``sqlite3.connect(...)`` line is a real line whether or not one line establishes
"session state survives process restart".  :class:`VerificationLevels` therefore
travels on every result and every promoted record, naming the semantic relation
``analyzer_assessed`` and refusing, at construction, to be told otherwise.  A
:class:`VerifiedEvidence` record means *tamper-bound, proposition-bound,
citation-bound, role-admissible* — never *proposition proven true*.

The module is stdlib-only and pure.  It reads no file, reopens no path, walks no
directory, contacts no service, calls no language system, acquires nothing,
selects nothing, executes nothing, synthesizes no claim, and is wired into no
live path.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from core.acquisition_request import (
    MAX_INITIAL_SOURCES_CEILING,
    MAX_PER_SOURCE_BYTES_CEILING,
    REQUESTABLE_SOURCE_CLASSES,
)
from core.content_acquisition import (
    AUTHORITY_NOT_VERIFIED,
    SOURCE_ACQUIRED,
    VERIFICATION_UNVERIFIED,
    AcquiredSourcePayload,
    SourceAcquisitionReceipt,
    SourceBinding,
)
from core.evidence_requirements import (
    ACTIVE_TIERS,
    EVIDENCE_ROLES,
    ROLE_ARCHITECTURE_DESCRIPTION,
    ROLE_CONFIGURATION_AUTHORITY,
    ROLE_HISTORICAL_CONTEXT,
    ROLE_IMPLEMENTATION_AUTHORITY,
    ROLE_INTERFACE_CONTRACT,
    ROLE_VALIDATION_EVIDENCE,
)


PHASE_ID = "EVIDENCE.1"
PROPOSITION_SCHEMA_VERSION = "evidence_1_proposition_v1"
REQUEST_SCHEMA_VERSION = "evidence_1_verification_request_v1"
COVERAGE_SCHEMA_VERSION = "evidence_1_negative_claim_coverage_v1"
CURRENT_STATE_SCHEMA_VERSION = "evidence_1_current_state_receipt_v1"
PROPOSAL_SCHEMA_VERSION = "evidence_1_verification_proposal_v1"
VERIFICATION_LEVELS_SCHEMA_VERSION = "evidence_1_verification_levels_v1"
#: Bumped from ``_v1`` when :class:`VerificationLevels` became a mandatory part
#: of a promoted record and of every result.  Nothing was renamed or removed;
#: the serialized shape gained one block, so the two records that carry it say
#: so instead of pretending their old shape still describes them.
VERIFIED_EVIDENCE_SCHEMA_VERSION = "evidence_1_verified_evidence_v2"
RESULT_SCHEMA_VERSION = "evidence_1_verification_result_v2"

# ── Proposition types ─────────────────────────────────────────────────────────
#: Deliberately two.  A larger logic taxonomy buys nothing until the two that
#: behave differently under evidence are handled correctly, and they do behave
#: differently: one is established by an instance, the other only by coverage.
PROPOSITION_POSITIVE = "positive"
PROPOSITION_NEGATIVE_EXISTENTIAL = "negative_existential"

PROPOSITION_TYPES: tuple[str, ...] = (
    PROPOSITION_POSITIVE,
    PROPOSITION_NEGATIVE_EXISTENTIAL,
)

# ── Proposition scopes ────────────────────────────────────────────────────────
#: *What kind of fact* the proposition asserts.  Supplied by the deterministic
#: caller with the proposition itself; never chosen by an analyzer.  A scope
#: earns its place by having a different answer to "which verified role could
#: establish this kind of fact at all?".
SCOPE_IMPLEMENTATION_STATE = "implementation_state"
SCOPE_INTERFACE_CAPABILITY = "interface_capability"
SCOPE_CONFIGURATION_DECLARATION = "configuration_declaration"
SCOPE_VALIDATION_EXPECTATION = "validation_expectation"
SCOPE_DOCUMENTED_ARCHITECTURE = "documented_architecture"
SCOPE_HISTORICAL_INTENT = "historical_intent"
SCOPE_RUNTIME_BEHAVIOUR = "runtime_behaviour"

PROPOSITION_SCOPES: tuple[str, ...] = (
    SCOPE_IMPLEMENTATION_STATE,
    SCOPE_INTERFACE_CAPABILITY,
    SCOPE_CONFIGURATION_DECLARATION,
    SCOPE_VALIDATION_EXPECTATION,
    SCOPE_DOCUMENTED_ARCHITECTURE,
    SCOPE_HISTORICAL_INTENT,
    SCOPE_RUNTIME_BEHAVIOUR,
)

#: The frozen competence table.  A verified role outside a scope's entry cannot
#: move that proposition in *either* direction: a dependency manifest neither
#: proves nor disproves that a running system uses the dependency, and saying so
#: is not modesty, it is the only defensible reading of the bytes.
#:
#: ``supplied_material``, ``hypothesis_support`` and ``current_external_authority``
#: appear in no entry on purpose.  Supplied material and hypotheses corroborate
#: and illustrate; external authority describes the world outside this
#: repository, and ACQUIRE.3 acquires no external bytes to verify.
SCOPE_COMPETENT_ROLES: dict[str, frozenset[str]] = {
    SCOPE_IMPLEMENTATION_STATE: frozenset({ROLE_IMPLEMENTATION_AUTHORITY}),
    SCOPE_INTERFACE_CAPABILITY: frozenset({ROLE_INTERFACE_CONTRACT}),
    SCOPE_CONFIGURATION_DECLARATION: frozenset({ROLE_CONFIGURATION_AUTHORITY}),
    SCOPE_VALIDATION_EXPECTATION: frozenset({ROLE_VALIDATION_EVIDENCE}),
    SCOPE_DOCUMENTED_ARCHITECTURE: frozenset({ROLE_ARCHITECTURE_DESCRIPTION}),
    SCOPE_HISTORICAL_INTENT: frozenset({ROLE_HISTORICAL_CONTEXT}),
    SCOPE_RUNTIME_BEHAVIOUR: frozenset({ROLE_IMPLEMENTATION_AUTHORITY}),
}

#: Scopes whose truth is about a *running* system.  Content that looks like
#: implementation proves that code exists — not that it is reachable,
#: configured, deployed or executed, five facts ACQUIRE.3 did not collapse and
#: EVIDENCE.1 will not collapse either.  Moving one of these needs a receipt
#: from whoever does know, in either direction.
SCOPES_REQUIRING_CURRENT_STATE: frozenset[str] = frozenset({SCOPE_RUNTIME_BEHAVIOUR})

# ── Relation vocabulary ───────────────────────────────────────────────────────
RELATION_SUPPORTS = "supports"
RELATION_CONTRADICTS = "contradicts"
RELATION_INSUFFICIENT = "insufficient"
RELATION_UNRELATED = "unrelated"

RELATIONS: tuple[str, ...] = (
    RELATION_SUPPORTS,
    RELATION_CONTRADICTS,
    RELATION_INSUFFICIENT,
    RELATION_UNRELATED,
)

#: The two relations that point somewhere, and therefore the only two that may
#: produce a :class:`VerifiedEvidence` record.
DIRECTIONAL_RELATIONS: frozenset[str] = frozenset(
    {RELATION_SUPPORTS, RELATION_CONTRADICTS}
)

# ── Verification dimensions ───────────────────────────────────────────────────
#: Four separate questions that a single record answers, kept apart because they
#: are established by different means and a reader who conflates them reads
#: "the bytes are real" as "the claim is true".
#:
#: ``source_binding``
#:     Are these the bytes ACQUIRE.3 acquired, under the identity chain it wrote?
#: ``citation_integrity``
#:     Does every cited span re-hash to the range it names inside those bytes?
#: ``role_admissibility``
#:     Are the roles this record reports within the roles the source was
#:     acquired for, and assessed against the frozen competence table?
#: ``semantic_relation``
#:     Does the cited material actually stand in the stated relation to the
#:     proposition?  Nothing here can answer that; an analyzer proposes it.
DIMENSION_SOURCE_BINDING = "source_binding"
DIMENSION_CITATION_INTEGRITY = "citation_integrity"
DIMENSION_ROLE_ADMISSIBILITY = "role_admissibility"
DIMENSION_SEMANTIC_RELATION = "semantic_relation"

VERIFICATION_DIMENSIONS: tuple[str, ...] = (
    DIMENSION_SOURCE_BINDING,
    DIMENSION_CITATION_INTEGRITY,
    DIMENSION_ROLE_ADMISSIBILITY,
    DIMENSION_SEMANTIC_RELATION,
)

# ── Verification levels ───────────────────────────────────────────────────────
#: *How* a dimension came to be believed.  Three values, and the difference
#: between the first two is the whole point of the vocabulary.
LEVEL_DETERMINISTICALLY_VERIFIED = "deterministically_verified"
LEVEL_ANALYZER_ASSESSED = "analyzer_assessed"
LEVEL_NOT_ESTABLISHED = "not_established"

VERIFICATION_LEVELS: tuple[str, ...] = (
    LEVEL_DETERMINISTICALLY_VERIFIED,
    LEVEL_ANALYZER_ASSESSED,
    LEVEL_NOT_ESTABLISHED,
)

#: The frozen ceiling table.  Each dimension may hold exactly one level besides
#: ``not_established``, so the interesting case is not a rule someone could
#: forget to apply: a record claiming a deterministically verified semantic
#: relation, or an analyzer-assessed source binding, does not construct.
DIMENSION_MAX_LEVEL: dict[str, str] = {
    DIMENSION_SOURCE_BINDING: LEVEL_DETERMINISTICALLY_VERIFIED,
    DIMENSION_CITATION_INTEGRITY: LEVEL_DETERMINISTICALLY_VERIFIED,
    DIMENSION_ROLE_ADMISSIBILITY: LEVEL_DETERMINISTICALLY_VERIFIED,
    DIMENSION_SEMANTIC_RELATION: LEVEL_ANALYZER_ASSESSED,
}

#: The dimensions this module can settle from bytes alone.  ``semantic_relation``
#: is absent, and its absence is the contract.
DETERMINISTIC_DIMENSIONS: frozenset[str] = frozenset(
    {
        DIMENSION_SOURCE_BINDING,
        DIMENSION_CITATION_INTEGRITY,
        DIMENSION_ROLE_ADMISSIBILITY,
    }
)

# ── Semantic assessment attribution ───────────────────────────────────────────
#: *Who* proposed the semantic relation, at the granularity that is honest:
#: the assessment path, identified by the analyzer's proposal fingerprint.
#: Provider and model names are deliberately not part of this — naming a vendor
#: would turn a brand into an epistemic warrant, and the fingerprint already
#: says which exact proposal the relation came from.
SEMANTIC_ASSESSMENT_ANALYZER_PROPOSAL = "analyzer_proposal"
SEMANTIC_ASSESSMENT_NOT_ASSESSED = "not_assessed"

SEMANTIC_ASSESSMENT_SOURCES: tuple[str, ...] = (
    SEMANTIC_ASSESSMENT_ANALYZER_PROPOSAL,
    SEMANTIC_ASSESSMENT_NOT_ASSESSED,
)

# ── Role assessment ───────────────────────────────────────────────────────────
ROLE_STATUS_VERIFIED = "verified"
ROLE_STATUS_REJECTED = "rejected"
ROLE_STATUS_INSUFFICIENT = "insufficient"

ROLE_STATUSES: tuple[str, ...] = (
    ROLE_STATUS_VERIFIED,
    ROLE_STATUS_REJECTED,
    ROLE_STATUS_INSUFFICIENT,
)

# ── Evidence span purposes ────────────────────────────────────────────────────
SPAN_ROLE_EVIDENCE = "role_evidence"
SPAN_SUPPORTING = "supporting"
SPAN_CONTRADICTING = "contradicting"

SPAN_PURPOSES: tuple[str, ...] = (
    SPAN_ROLE_EVIDENCE,
    SPAN_SUPPORTING,
    SPAN_CONTRADICTING,
)

#: Which span purpose a directional relation must actually cite.
RELATION_SPAN_PURPOSE: dict[str, str] = {
    RELATION_SUPPORTS: SPAN_SUPPORTING,
    RELATION_CONTRADICTS: SPAN_CONTRADICTING,
}

# ── Verification constraints ──────────────────────────────────────────────────
#: Caller-declared strictness carried on the request.  Two of them are not
#: optional: a request whose proposition needs coverage or currentness must say
#: so, so the requirement travels with the record instead of living only inside
#: whichever gate happens to read it.
CONSTRAINT_ROLE_VERIFICATION_REQUIRED = "role_verification_required"
CONSTRAINT_EVIDENCE_SPAN_REQUIRED = "evidence_span_required"
CONSTRAINT_NEGATIVE_COVERAGE_REQUIRED = "negative_coverage_required"
CONSTRAINT_CURRENT_STATE_RECEIPT_REQUIRED = "current_state_receipt_required"
CONSTRAINT_LOCAL_ANALYSIS_ONLY = "local_analysis_only"

VERIFICATION_CONSTRAINTS: tuple[str, ...] = (
    CONSTRAINT_ROLE_VERIFICATION_REQUIRED,
    CONSTRAINT_EVIDENCE_SPAN_REQUIRED,
    CONSTRAINT_NEGATIVE_COVERAGE_REQUIRED,
    CONSTRAINT_CURRENT_STATE_RECEIPT_REQUIRED,
    CONSTRAINT_LOCAL_ANALYSIS_ONLY,
)

# ── Coverage ──────────────────────────────────────────────────────────────────
COVERAGE_SUFFICIENT = "coverage_sufficient"
COVERAGE_INSUFFICIENT = "coverage_insufficient"
COVERAGE_UNKNOWN = "coverage_unknown"

COVERAGE_STATUSES: tuple[str, ...] = (
    COVERAGE_SUFFICIENT,
    COVERAGE_INSUFFICIENT,
    COVERAGE_UNKNOWN,
)

#: Result-side values that describe *why there is no coverage claim*, which is a
#: different fact from an insufficient one.
COVERAGE_NOT_APPLICABLE = "coverage_not_applicable"
COVERAGE_NOT_SUPPLIED = "coverage_not_supplied"

RESULT_COVERAGE_STATUSES: tuple[str, ...] = COVERAGE_STATUSES + (
    COVERAGE_NOT_APPLICABLE,
    COVERAGE_NOT_SUPPLIED,
)

COVERAGE_ALL_REQUIRED_ROLES_ACQUIRED = "all_required_roles_acquired"
COVERAGE_ALL_ELIGIBLE_CANDIDATES_ACQUIRED = "all_eligible_candidates_acquired"
COVERAGE_REQUIRED_ROLE_UNACQUIRED = "required_role_unacquired"
COVERAGE_CANDIDATE_POOL_TRUNCATED = "candidate_pool_truncated"
COVERAGE_DOMAIN_EXCLUDED = "domain_excluded"

COVERAGE_REASONS: tuple[str, ...] = (
    COVERAGE_ALL_REQUIRED_ROLES_ACQUIRED,
    COVERAGE_ALL_ELIGIBLE_CANDIDATES_ACQUIRED,
    COVERAGE_REQUIRED_ROLE_UNACQUIRED,
    COVERAGE_CANDIDATE_POOL_TRUNCATED,
    COVERAGE_DOMAIN_EXCLUDED,
)

# ── Current-state receipt ─────────────────────────────────────────────────────
CURRENT_STATE_ESTABLISHED = "current_state_established"
CURRENT_STATE_NOT_ESTABLISHED = "current_state_not_established"

CURRENT_STATE_STATUSES: tuple[str, ...] = (
    CURRENT_STATE_ESTABLISHED,
    CURRENT_STATE_NOT_ESTABLISHED,
)

CURRENT_STATE_DEPLOYED_REVISION_CONFIRMED = "deployed_revision_confirmed"
CURRENT_STATE_RUNTIME_ENTRYPOINT_CONFIRMED = "runtime_entrypoint_confirmed"
CURRENT_STATE_EXECUTION_OBSERVED = "execution_observed"

CURRENT_STATE_BASES: tuple[str, ...] = (
    CURRENT_STATE_DEPLOYED_REVISION_CONFIRMED,
    CURRENT_STATE_RUNTIME_ENTRYPOINT_CONFIRMED,
    CURRENT_STATE_EXECUTION_OBSERVED,
)

# ── Analyzer reason vocabulary ────────────────────────────────────────────────
#: An analyzer states *why* in codes, never in prose.  This is the structural
#: answer to invented symbols: there is nowhere in a proposal to write the words
#: PluginKernel or TrajectoryManager, so a hallucinated identifier cannot ride
#: into a receipt inside a sentence.  It also keeps hidden reasoning out — a
#: chain of thought has no representation here.
ANALYSIS_ROLE_CONTENT_CONSISTENT = "role_content_consistent"
ANALYSIS_ROLE_CONTENT_INCONSISTENT = "role_content_inconsistent"
ANALYSIS_ROLE_CONTENT_INCONCLUSIVE = "role_content_inconclusive"
ANALYSIS_PROPOSITION_TERMS_PRESENT = "proposition_terms_present"
ANALYSIS_PROPOSITION_TERMS_ABSENT = "proposition_terms_absent"
ANALYSIS_MECHANISM_IMPLEMENTED = "mechanism_implemented"
ANALYSIS_INCOMPATIBLE_MECHANISM_PRESENT = "incompatible_mechanism_present"
ANALYSIS_MECHANISM_DECLARED_ONLY = "mechanism_declared_only"
ANALYSIS_SUBJECT_NOT_DISCUSSED = "subject_not_discussed"
ANALYSIS_SCOPE_EXCEEDS_SOURCE = "scope_exceeds_source"

ANALYSIS_REASONS: tuple[str, ...] = (
    ANALYSIS_ROLE_CONTENT_CONSISTENT,
    ANALYSIS_ROLE_CONTENT_INCONSISTENT,
    ANALYSIS_ROLE_CONTENT_INCONCLUSIVE,
    ANALYSIS_PROPOSITION_TERMS_PRESENT,
    ANALYSIS_PROPOSITION_TERMS_ABSENT,
    ANALYSIS_MECHANISM_IMPLEMENTED,
    ANALYSIS_INCOMPATIBLE_MECHANISM_PRESENT,
    ANALYSIS_MECHANISM_DECLARED_ONLY,
    ANALYSIS_SUBJECT_NOT_DISCUSSED,
    ANALYSIS_SCOPE_EXCEEDS_SOURCE,
)

# ── Deterministic gate reasons ────────────────────────────────────────────────
GATE_SOURCE_BINDING_VERIFIED = "source_binding_verified"
GATE_PROPOSITION_BINDING_VERIFIED = "proposition_binding_verified"
GATE_ROLES_WITHIN_EXPECTED = "verified_roles_within_expected"
GATE_EVIDENCE_SPANS_VERIFIED = "evidence_spans_verified"
GATE_RELATION_ACCEPTED = "relation_accepted"
GATE_EVIDENCE_PROMOTED = "verified_evidence_promoted"
GATE_EVIDENCE_NOT_PROMOTED = "verified_evidence_not_promoted"
GATE_RELATION_DOWNGRADED_NO_VERIFIED_ROLE = "relation_downgraded_no_verified_role"
GATE_RELATION_DOWNGRADED_ROLE_NOT_COMPETENT = "relation_downgraded_role_not_competent"
GATE_PROMOTION_BLOCKED_NEGATIVE_COVERAGE = "promotion_blocked_negative_coverage"
GATE_PROMOTION_BLOCKED_CURRENT_STATE = "promotion_blocked_current_state_receipt"
GATE_ANALYZER_PROPOSAL_INVALID = "analyzer_proposal_invalid"
GATE_ANALYZER_UNAVAILABLE = "analyzer_unavailable"
GATE_SOURCE_NOT_ANALYZABLE = "source_not_analyzable"
GATE_REQUESTED_ROLE_NOT_EXPECTED = "requested_role_not_expected"
GATE_NO_CLAIM_SYNTHESIS_PERFORMED = "no_claim_synthesis_performed"

VERIFICATION_REASONS: tuple[str, ...] = (
    GATE_SOURCE_BINDING_VERIFIED,
    GATE_PROPOSITION_BINDING_VERIFIED,
    GATE_ROLES_WITHIN_EXPECTED,
    GATE_EVIDENCE_SPANS_VERIFIED,
    GATE_RELATION_ACCEPTED,
    GATE_EVIDENCE_PROMOTED,
    GATE_EVIDENCE_NOT_PROMOTED,
    GATE_RELATION_DOWNGRADED_NO_VERIFIED_ROLE,
    GATE_RELATION_DOWNGRADED_ROLE_NOT_COMPETENT,
    GATE_PROMOTION_BLOCKED_NEGATIVE_COVERAGE,
    GATE_PROMOTION_BLOCKED_CURRENT_STATE,
    GATE_ANALYZER_PROPOSAL_INVALID,
    GATE_ANALYZER_UNAVAILABLE,
    GATE_SOURCE_NOT_ANALYZABLE,
    GATE_REQUESTED_ROLE_NOT_EXPECTED,
    GATE_NO_CLAIM_SYNTHESIS_PERFORMED,
)

# ── Binding inconsistencies ───────────────────────────────────────────────────
INCONSISTENT_PAYLOAD_DIGEST = "payload_digest_mismatch"
INCONSISTENT_PAYLOAD_BYTE_COUNT = "payload_byte_count_mismatch"
INCONSISTENT_CANDIDATE_IDENTITY = "candidate_identifier_mismatch"
INCONSISTENT_RECEIPT_FINGERPRINT = "acquisition_receipt_fingerprint_mismatch"
INCONSISTENT_SOURCE_BINDING = "source_binding_mismatch"
INCONSISTENT_SOURCE_NOT_ACQUIRED = "source_not_acquired"
INCONSISTENT_SOURCE_ALREADY_VERIFIED = "source_already_verified"
INCONSISTENT_SOURCE_AUTHORITY_CLAIMED = "source_authority_already_claimed"
INCONSISTENT_COVERAGE_BINDING = "coverage_binding_mismatch"
INCONSISTENT_CURRENT_STATE_BINDING = "current_state_binding_mismatch"

VERIFICATION_INCONSISTENCIES: tuple[str, ...] = (
    INCONSISTENT_PAYLOAD_DIGEST,
    INCONSISTENT_PAYLOAD_BYTE_COUNT,
    INCONSISTENT_CANDIDATE_IDENTITY,
    INCONSISTENT_RECEIPT_FINGERPRINT,
    INCONSISTENT_SOURCE_BINDING,
    INCONSISTENT_SOURCE_NOT_ACQUIRED,
    INCONSISTENT_SOURCE_ALREADY_VERIFIED,
    INCONSISTENT_SOURCE_AUTHORITY_CLAIMED,
    INCONSISTENT_COVERAGE_BINDING,
    INCONSISTENT_CURRENT_STATE_BINDING,
)

# ── Overall verification statuses ─────────────────────────────────────────────
STATUS_VERIFIED = "verified"
STATUS_CONTRADICTED = "contradicted"
STATUS_INSUFFICIENT = "insufficient"
STATUS_UNRELATED = "unrelated"
STATUS_COVERAGE_REQUIRED = "coverage_required"
STATUS_ANALYSIS_INVALID = "analysis_invalid"
STATUS_BINDING_INVALID = "binding_invalid"
STATUS_UNSUPPORTED_SOURCE = "unsupported_source"

VERIFICATION_STATUSES: tuple[str, ...] = (
    STATUS_VERIFIED,
    STATUS_CONTRADICTED,
    STATUS_INSUFFICIENT,
    STATUS_UNRELATED,
    STATUS_COVERAGE_REQUIRED,
    STATUS_ANALYSIS_INVALID,
    STATUS_BINDING_INVALID,
    STATUS_UNSUPPORTED_SOURCE,
)

PROMOTION_PROMOTED = "promoted"
PROMOTION_NOT_PROMOTED = "not_promoted"

PROMOTION_STATUSES: tuple[str, ...] = (PROMOTION_PROMOTED, PROMOTION_NOT_PROMOTED)

# ── Bounds ────────────────────────────────────────────────────────────────────
MAX_PROPOSITION_ID_LENGTH = 128
MAX_PROPOSITION_CHARS = 500
MAX_EVIDENCE_SPANS = 8
MAX_SPAN_BYTES = 4_096
MAX_TOTAL_CITED_BYTES = 16_384
MAX_ROLE_ASSESSMENTS = len(EVIDENCE_ROLES)
MAX_ANALYSIS_REASONS = 8
MAX_VERIFICATION_REASONS = len(VERIFICATION_REASONS)
MAX_VERIFICATION_INCONSISTENCIES = len(VERIFICATION_INCONSISTENCIES)
MAX_COVERAGE_RECEIPTS = MAX_INITIAL_SOURCES_CEILING
MAX_COVERAGE_REASONS = len(COVERAGE_REASONS)
MAX_ANALYZER_VIEW_BYTES = MAX_PER_SOURCE_BYTES_CEILING
MAX_SOURCE_IDENTIFIER_LENGTH = 1_024


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


def _ordered_vocabulary(
    values: tuple[str, ...],
    vocabulary: tuple[str, ...],
    label: str,
) -> None:
    """Canonical vocabulary order, each value at most once.

    Ordering is not cosmetic: two records that state the same facts must
    fingerprint identically, and a caller must not be able to encode extra
    meaning in the order it happened to write them down.
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


def _bounded_identifier(value: object, label: str, *, maximum: int) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds its finite bound")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{label} may not contain control characters")


def _bounded_digest_tuple(
    values: object,
    *,
    maximum: int,
    label: str,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{label} must be a tuple")
    if len(values) > maximum:
        raise ValueError(f"{label} exceeds its finite bound")
    if len(set(values)) != len(values):
        raise ValueError(f"{label} may name each digest once")
    for item in values:
        _require_sha256(item, label)
    if values != tuple(sorted(values)):
        raise ValueError(f"{label} must be canonically ordered")


def _non_negative_int(value: object, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a finite non-negative integer")


# ── Proposition ───────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Proposition:
    """The claim under test.  EVIDENCE.1 receives it and never writes one.

    :attr:`proposition_sha256` is computed over identifier, text, type and scope
    together, so every way of tampering with the claim — a reworded entity, an
    added qualifier, a widened scope, a flipped type — produces a different
    digest than the one the gate is holding.
    """

    proposition_id: str
    text: str
    proposition_type: str
    scope: str
    schema_version: str = PROPOSITION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _bounded_identifier(
            self.proposition_id,
            "proposition_id",
            maximum=MAX_PROPOSITION_ID_LENGTH,
        )
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("a proposition must carry non-empty text")
        if len(self.text) > MAX_PROPOSITION_CHARS:
            raise ValueError("proposition text exceeds its finite bound")
        if self.proposition_type not in PROPOSITION_TYPES:
            raise ValueError(f"unsupported proposition type: {self.proposition_type!r}")
        if self.scope not in PROPOSITION_SCOPES:
            raise ValueError(f"unsupported proposition scope: {self.scope!r}")
        if self.schema_version != PROPOSITION_SCHEMA_VERSION:
            raise ValueError("unsupported proposition schema version")

    @property
    def proposition_sha256(self) -> str:
        return _fingerprint(
            {
                "schema_version": self.schema_version,
                "proposition_id": self.proposition_id,
                "text": self.text,
                "proposition_type": self.proposition_type,
                "scope": self.scope,
            }
        )

    @property
    def competent_roles(self) -> frozenset[str]:
        """Which verified role could establish this scope at all."""
        return SCOPE_COMPETENT_ROLES[self.scope]

    @property
    def requires_current_state(self) -> bool:
        return self.scope in SCOPES_REQUIRING_CURRENT_STATE

    @property
    def requires_coverage_to_support(self) -> bool:
        return self.proposition_type == PROPOSITION_NEGATIVE_EXISTENTIAL

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "proposition_id": self.proposition_id,
            "text": self.text,
            "proposition_type": self.proposition_type,
            "scope": self.scope,
            "proposition_sha256": self.proposition_sha256,
            "authored_by_evidence_1": False,
        }


# ── Negative-claim coverage ───────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class NegativeClaimCoverage:
    """Somebody else's proof that the search space was covered.

    EVIDENCE.1 consumes one; it has no code path that could build one, because
    building one means knowing what was *not* acquired, and that is an
    acquisition question.
    """

    proposition_id: str
    proposition_sha256: str
    required_roles: tuple[str, ...]
    acquisition_request_fingerprint: str
    candidate_pool_fingerprint: str
    acquired_source_receipt_fingerprints: tuple[str, ...]
    coverage_status: str
    uncovered_requirements: tuple[str, ...] = ()
    source_class_coverage: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    schema_version: str = COVERAGE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _bounded_identifier(
            self.proposition_id,
            "coverage proposition_id",
            maximum=MAX_PROPOSITION_ID_LENGTH,
        )
        _require_sha256(self.proposition_sha256, "coverage proposition digest")
        _ordered_vocabulary(self.required_roles, EVIDENCE_ROLES, "covered role")
        if not self.required_roles:
            raise ValueError("coverage must name the roles it claims to cover")
        _require_sha256(
            self.acquisition_request_fingerprint,
            "coverage acquisition request fingerprint",
        )
        _require_sha256(
            self.candidate_pool_fingerprint,
            "coverage candidate pool fingerprint",
        )
        _bounded_digest_tuple(
            self.acquired_source_receipt_fingerprints,
            maximum=MAX_COVERAGE_RECEIPTS,
            label="coverage source receipt fingerprint",
        )
        if self.coverage_status not in COVERAGE_STATUSES:
            raise ValueError(f"unsupported coverage status: {self.coverage_status!r}")
        _ordered_vocabulary(
            self.uncovered_requirements,
            EVIDENCE_ROLES,
            "uncovered requirement",
        )
        _ordered_vocabulary(
            self.source_class_coverage,
            REQUESTABLE_SOURCE_CLASSES,
            "covered source class",
        )
        _ordered_vocabulary(self.exclusions, REQUESTABLE_SOURCE_CLASSES, "coverage exclusion")
        _ordered_vocabulary(self.reasons, COVERAGE_REASONS, "coverage reason")
        if len(self.reasons) > MAX_COVERAGE_REASONS:
            raise ValueError("coverage reasons exceed their finite bound")
        if set(self.uncovered_requirements) - set(self.required_roles):
            raise ValueError("an uncovered requirement must be one of the covered roles")
        if set(self.source_class_coverage) & set(self.exclusions):
            raise ValueError("a source class is either covered or excluded, never both")
        if self.coverage_status == COVERAGE_SUFFICIENT:
            if self.uncovered_requirements:
                raise ValueError("sufficient coverage may not leave a requirement uncovered")
            if not self.acquired_source_receipt_fingerprints:
                raise ValueError("sufficient coverage must name the sources it covered")
            if not self.source_class_coverage:
                raise ValueError("sufficient coverage must state the classes it reached")
        if self.schema_version != COVERAGE_SCHEMA_VERSION:
            raise ValueError("unsupported negative-claim coverage schema version")

    @property
    def is_sufficient(self) -> bool:
        return self.coverage_status == COVERAGE_SUFFICIENT

    def covers_receipt(self, receipt_fingerprint: str) -> bool:
        return receipt_fingerprint in self.acquired_source_receipt_fingerprints

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "proposition_id": self.proposition_id,
            "proposition_sha256": self.proposition_sha256,
            "required_roles": list(self.required_roles),
            "acquisition_request_fingerprint": self.acquisition_request_fingerprint,
            "candidate_pool_fingerprint": self.candidate_pool_fingerprint,
            "acquired_source_receipt_fingerprints": list(
                self.acquired_source_receipt_fingerprints
            ),
            "coverage_status": self.coverage_status,
            "uncovered_requirements": list(self.uncovered_requirements),
            "source_class_coverage": list(self.source_class_coverage),
            "exclusions": list(self.exclusions),
            "reasons": list(self.reasons),
            "minted_by_evidence_1": False,
            "search_performed_by_evidence_1": False,
        }


def coverage_fingerprint(coverage: NegativeClaimCoverage) -> str:
    if not isinstance(coverage, NegativeClaimCoverage):
        raise TypeError("coverage_fingerprint requires a NegativeClaimCoverage")
    return _fingerprint(coverage.as_dict())


# ── Current-state receipt ─────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class CurrentStateReceipt:
    """Somebody else's proof that these exact bytes are the current ones.

    Source content that looks like implementation establishes that code exists.
    Whether it is the deployed, reachable, executed code is a different fact,
    and ACQUIRE.3 established none of it.
    """

    proposition_id: str
    proposition_sha256: str
    candidate_identifier: str
    source_content_sha256: str
    acquisition_receipt_fingerprint: str
    current_state_status: str
    basis: tuple[str, ...] = ()
    schema_version: str = CURRENT_STATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _bounded_identifier(
            self.proposition_id,
            "current-state proposition_id",
            maximum=MAX_PROPOSITION_ID_LENGTH,
        )
        _require_sha256(self.proposition_sha256, "current-state proposition digest")
        _bounded_identifier(
            self.candidate_identifier,
            "current-state candidate identifier",
            maximum=MAX_SOURCE_IDENTIFIER_LENGTH,
        )
        _require_sha256(self.source_content_sha256, "current-state content digest")
        _require_sha256(
            self.acquisition_receipt_fingerprint,
            "current-state acquisition receipt fingerprint",
        )
        if self.current_state_status not in CURRENT_STATE_STATUSES:
            raise ValueError(
                f"unsupported current-state status: {self.current_state_status!r}"
            )
        _ordered_vocabulary(self.basis, CURRENT_STATE_BASES, "current-state basis")
        if self.current_state_status == CURRENT_STATE_ESTABLISHED and not self.basis:
            raise ValueError("an established current state must state its basis")
        if self.current_state_status == CURRENT_STATE_NOT_ESTABLISHED and self.basis:
            raise ValueError("an unestablished current state carries no basis")
        if self.schema_version != CURRENT_STATE_SCHEMA_VERSION:
            raise ValueError("unsupported current-state receipt schema version")

    @property
    def is_established(self) -> bool:
        return self.current_state_status == CURRENT_STATE_ESTABLISHED

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "proposition_id": self.proposition_id,
            "proposition_sha256": self.proposition_sha256,
            "candidate_identifier": self.candidate_identifier,
            "source_content_sha256": self.source_content_sha256,
            "acquisition_receipt_fingerprint": self.acquisition_receipt_fingerprint,
            "current_state_status": self.current_state_status,
            "basis": list(self.basis),
            "minted_by_evidence_1": False,
        }


def current_state_fingerprint(receipt: CurrentStateReceipt) -> str:
    if not isinstance(receipt, CurrentStateReceipt):
        raise TypeError("current_state_fingerprint requires a CurrentStateReceipt")
    return _fingerprint(receipt.as_dict())


# ── ACQUIRE.3 receipt identity ────────────────────────────────────────────────

def source_receipt_fingerprint(receipt: SourceAcquisitionReceipt) -> str:
    """Fingerprint one ACQUIRE.3 source receipt.

    Defined here rather than upstream because EVIDENCE.1 is the first phase that
    needs to bind *to* an acquisition receipt; ACQUIRE.3 is frozen and is not
    modified to add it.
    """
    if not isinstance(receipt, SourceAcquisitionReceipt):
        raise TypeError("source_receipt_fingerprint requires a SourceAcquisitionReceipt")
    return _fingerprint(receipt.as_dict())


# ── Verification request ──────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class EvidenceVerificationRequest:
    """One proposition against one acquired source.  Both arrive; neither is made."""

    proposition: Proposition
    requested_roles: tuple[str, ...]
    acquisition_receipt_fingerprint: str
    source_content_sha256: str
    source_binding: SourceBinding
    verification_constraints: tuple[str, ...] = ()
    coverage: NegativeClaimCoverage | None = None
    current_state: CurrentStateReceipt | None = None
    schema_version: str = REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.proposition, Proposition):
            raise TypeError("a verification request requires a Proposition")
        _ordered_vocabulary(self.requested_roles, EVIDENCE_ROLES, "requested role")
        if not self.requested_roles:
            raise ValueError("a verification request must name the roles it tests")
        _require_sha256(
            self.acquisition_receipt_fingerprint,
            "acquisition receipt fingerprint",
        )
        _require_sha256(self.source_content_sha256, "source content digest")
        if not isinstance(self.source_binding, SourceBinding):
            raise TypeError("a verification request requires an ACQUIRE.3 SourceBinding")
        _ordered_vocabulary(
            self.verification_constraints,
            VERIFICATION_CONSTRAINTS,
            "verification constraint",
        )
        needs_coverage = self.proposition.requires_coverage_to_support
        declares_coverage = (
            CONSTRAINT_NEGATIVE_COVERAGE_REQUIRED in self.verification_constraints
        )
        if needs_coverage != declares_coverage:
            raise ValueError(
                "a negative existential request must declare negative_coverage_required, "
                "and no other request may"
            )
        needs_current_state = self.proposition.requires_current_state
        declares_current_state = (
            CONSTRAINT_CURRENT_STATE_RECEIPT_REQUIRED in self.verification_constraints
        )
        if needs_current_state != declares_current_state:
            raise ValueError(
                "a runtime-behaviour request must declare current_state_receipt_required, "
                "and no other request may"
            )
        if self.coverage is not None:
            if not isinstance(self.coverage, NegativeClaimCoverage):
                raise TypeError("coverage must be a NegativeClaimCoverage or None")
            if not needs_coverage:
                raise ValueError(
                    "coverage is only meaningful for a negative existential proposition"
                )
        if self.current_state is not None:
            if not isinstance(self.current_state, CurrentStateReceipt):
                raise TypeError("current_state must be a CurrentStateReceipt or None")
            if not needs_current_state:
                raise ValueError(
                    "a current-state receipt is only meaningful for a runtime-behaviour scope"
                )
        if self.schema_version != REQUEST_SCHEMA_VERSION:
            raise ValueError("unsupported verification request schema version")

    @property
    def source_identifier(self) -> str:
        return self.source_binding.candidate_identifier

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "proposition": self.proposition.as_dict(),
            "requested_roles": list(self.requested_roles),
            "acquisition_receipt_fingerprint": self.acquisition_receipt_fingerprint,
            "source_content_sha256": self.source_content_sha256,
            "source_binding": self.source_binding.as_dict(),
            "verification_constraints": list(self.verification_constraints),
            "coverage": None if self.coverage is None else self.coverage.as_dict(),
            "current_state": (
                None if self.current_state is None else self.current_state.as_dict()
            ),
            "source_content_serialized": False,
        }


def verification_request_fingerprint(request: EvidenceVerificationRequest) -> str:
    if not isinstance(request, EvidenceVerificationRequest):
        raise TypeError(
            "verification_request_fingerprint requires an EvidenceVerificationRequest"
        )
    return _fingerprint(request.as_dict())


# ── Bounded payload view ──────────────────────────────────────────────────────

class BoundedPayloadView:
    """The only thing an analyzer is given of the acquired source.

    It exposes exact bytes and the identity that binds them, and nothing that
    could be used to reach further: no path, no directory, no handle, no way to
    reopen the file.  ACQUIRE.3's payload is authoritative for content identity,
    so a view is built from the payload and never from disk.
    """

    __slots__ = (
        "_content",
        "_candidate_identifier",
        "_content_sha256",
        "_expected_roles",
        "_eligible_source_classes",
        "_tier",
    )

    def __init__(
        self,
        *,
        candidate_identifier: str,
        content: bytes,
        content_sha256: str,
        expected_roles: tuple[str, ...],
        eligible_source_classes: tuple[str, ...],
        tier: str,
    ) -> None:
        if not isinstance(content, bytes):
            raise TypeError("a bounded payload view is exact bytes")
        if len(content) > MAX_ANALYZER_VIEW_BYTES:
            raise ValueError("a bounded payload view exceeds the per-source ceiling")
        _require_sha256(content_sha256, "view content digest")
        if hashlib.sha256(content).hexdigest() != content_sha256:
            raise ValueError("view content does not match its SHA-256")
        _bounded_identifier(
            candidate_identifier,
            "view candidate identifier",
            maximum=MAX_SOURCE_IDENTIFIER_LENGTH,
        )
        _ordered_vocabulary(expected_roles, EVIDENCE_ROLES, "expected role")
        _ordered_vocabulary(
            eligible_source_classes,
            REQUESTABLE_SOURCE_CLASSES,
            "eligible source class",
        )
        if tier not in ACTIVE_TIERS:
            raise ValueError("a bounded payload view requires an active tier")
        self._content = content
        self._candidate_identifier = candidate_identifier
        self._content_sha256 = content_sha256
        self._expected_roles = expected_roles
        self._eligible_source_classes = eligible_source_classes
        self._tier = tier

    def __repr__(self) -> str:  # pragma: no cover - defensive, content never printed
        return (
            f"BoundedPayloadView(candidate_identifier={self._candidate_identifier!r}, "
            f"byte_count={len(self._content)})"
        )

    @property
    def candidate_identifier(self) -> str:
        return self._candidate_identifier

    @property
    def content_sha256(self) -> str:
        return self._content_sha256

    @property
    def byte_count(self) -> int:
        return len(self._content)

    @property
    def expected_roles(self) -> tuple[str, ...]:
        return self._expected_roles

    @property
    def eligible_source_classes(self) -> tuple[str, ...]:
        return self._eligible_source_classes

    @property
    def tier(self) -> str:
        return self._tier

    @property
    def content(self) -> bytes:
        return self._content

    def slice(self, start: int, end: int) -> bytes:
        _non_negative_int(start, "span start")
        _non_negative_int(end, "span end")
        if start >= end or end > len(self._content):
            raise ValueError("a span must be a non-empty range inside the payload")
        return self._content[start:end]

    def locate(self, needle: bytes, *, start: int = 0) -> tuple[int, int] | None:
        """First literal byte occurrence, as a half-open range."""
        if not isinstance(needle, bytes) or not needle:
            raise ValueError("locate requires a non-empty byte needle")
        index = self._content.find(needle, start)
        if index < 0:
            return None
        return index, index + len(needle)

    def line_offsets(self) -> tuple[int, ...]:
        """Byte offset of every line start, for rendering offset-anchored text."""
        offsets = [0]
        for index, value in enumerate(self._content):
            if value == 0x0A and index + 1 < len(self._content):
                offsets.append(index + 1)
        return tuple(offsets)


def bounded_payload_view(
    payload: AcquiredSourcePayload,
    receipt: SourceAcquisitionReceipt,
) -> BoundedPayloadView:
    """Build the analyzer's view from ACQUIRE.3's own payload and receipt."""
    if not isinstance(payload, AcquiredSourcePayload):
        raise TypeError("bounded_payload_view requires an AcquiredSourcePayload")
    if not isinstance(receipt, SourceAcquisitionReceipt):
        raise TypeError("bounded_payload_view requires a SourceAcquisitionReceipt")
    if payload.candidate_identifier != receipt.candidate_identifier:
        raise ValueError("payload and receipt name different candidates")
    if payload.content_sha256 != receipt.content_sha256:
        raise ValueError("payload and receipt describe different bytes")
    return BoundedPayloadView(
        candidate_identifier=payload.candidate_identifier,
        content=payload.content,
        content_sha256=payload.content_sha256,
        expected_roles=receipt.expected_roles,
        eligible_source_classes=receipt.eligible_source_classes,
        tier=receipt.tier,
    )


# ── Evidence spans ────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class EvidenceSpanRef:
    """The serializable half of a span: identity, never content."""

    start_byte: int
    end_byte: int
    span_sha256: str
    purpose: str
    source_content_sha256: str

    def __post_init__(self) -> None:
        _non_negative_int(self.start_byte, "span start_byte")
        _non_negative_int(self.end_byte, "span end_byte")
        if self.start_byte >= self.end_byte:
            raise ValueError("a span must cite at least one byte")
        if self.end_byte - self.start_byte > MAX_SPAN_BYTES:
            raise ValueError("a span exceeds the per-span byte ceiling")
        _require_sha256(self.span_sha256, "span digest")
        if self.purpose not in SPAN_PURPOSES:
            raise ValueError(f"unsupported span purpose: {self.purpose!r}")
        _require_sha256(self.source_content_sha256, "span source content digest")

    @property
    def byte_count(self) -> int:
        return self.end_byte - self.start_byte

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_byte": self.start_byte,
            "end_byte": self.end_byte,
            "byte_count": self.byte_count,
            "span_sha256": self.span_sha256,
            "purpose": self.purpose,
            "source_content_sha256": self.source_content_sha256,
            "excerpt_serialized": False,
        }


@dataclass(frozen=True, slots=True)
class EvidenceSpan:
    """A span as an analyzer proposes it.

    ``quoted_text`` is optional and adversarial: if an analyzer supplies it, the
    gate requires it to be byte-exactly the cited range, which is a second way
    of catching a citation that was reasoned about rather than read.  It is
    verified and then discarded — it never reaches a receipt.
    """

    start_byte: int
    end_byte: int
    span_sha256: str
    purpose: str
    source_content_sha256: str
    quoted_text: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _non_negative_int(self.start_byte, "span start_byte")
        _non_negative_int(self.end_byte, "span end_byte")
        if self.start_byte >= self.end_byte:
            raise ValueError("a span must cite at least one byte")
        if self.end_byte - self.start_byte > MAX_SPAN_BYTES:
            raise ValueError("a span exceeds the per-span byte ceiling")
        _require_sha256(self.span_sha256, "span digest")
        if self.purpose not in SPAN_PURPOSES:
            raise ValueError(f"unsupported span purpose: {self.purpose!r}")
        _require_sha256(self.source_content_sha256, "span source content digest")
        if self.quoted_text is not None and not isinstance(self.quoted_text, str):
            raise TypeError("quoted_text must be a string or None")

    @property
    def byte_count(self) -> int:
        return self.end_byte - self.start_byte

    def as_ref(self) -> EvidenceSpanRef:
        return EvidenceSpanRef(
            start_byte=self.start_byte,
            end_byte=self.end_byte,
            span_sha256=self.span_sha256,
            purpose=self.purpose,
            source_content_sha256=self.source_content_sha256,
        )


def span_from_view(
    view: BoundedPayloadView,
    start: int,
    end: int,
    purpose: str,
    *,
    quote: bool = False,
) -> EvidenceSpan:
    """Build a span whose digest is computed from the acquired bytes themselves."""
    payload = view.slice(start, end)
    quoted: str | None = None
    if quote:
        quoted = payload.decode("utf-8")
    return EvidenceSpan(
        start_byte=start,
        end_byte=end,
        span_sha256=hashlib.sha256(payload).hexdigest(),
        purpose=purpose,
        source_content_sha256=view.content_sha256,
        quoted_text=quoted,
    )


# ── Role assessment ───────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class RoleAssessment:
    """Whether the content actually satisfies one role it was acquired for."""

    role: str
    status: str
    span_indexes: tuple[int, ...] = ()
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.role not in EVIDENCE_ROLES:
            raise ValueError(f"unsupported evidence role: {self.role!r}")
        if self.status not in ROLE_STATUSES:
            raise ValueError(f"unsupported role status: {self.status!r}")
        if not isinstance(self.span_indexes, tuple):
            raise TypeError("span_indexes must be a tuple")
        if len(self.span_indexes) > MAX_EVIDENCE_SPANS:
            raise ValueError("role span references exceed their finite bound")
        for index in self.span_indexes:
            _non_negative_int(index, "role span index")
        if len(set(self.span_indexes)) != len(self.span_indexes):
            raise ValueError("a role may cite each span once")
        if self.span_indexes != tuple(sorted(self.span_indexes)):
            raise ValueError("role span indexes must be canonically ordered")
        _ordered_vocabulary(self.reasons, ANALYSIS_REASONS, "role reason")
        if len(self.reasons) > MAX_ANALYSIS_REASONS:
            raise ValueError("role reasons exceed their finite bound")

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "status": self.status,
            "span_indexes": list(self.span_indexes),
            "reasons": list(self.reasons),
            "expected_role": True,
        }


# ── Analyzer proposal ─────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class EvidenceVerificationProposal:
    """What an analyzer may say.  It has no field that could claim authority.

    There is no ``verified``, ``promoted``, ``authority``, ``provider``,
    ``confidence`` or ``acquire_more`` here — not values it is forbidden to set,
    but fields that do not exist, so a proposal cannot be written that promotes
    itself.
    """

    proposition_id: str
    proposition_sha256: str
    source_identifier: str
    source_content_sha256: str
    relation: str
    role_assessments: tuple[RoleAssessment, ...] = ()
    evidence_spans: tuple[EvidenceSpan, ...] = ()
    reasons: tuple[str, ...] = ()
    schema_version: str = PROPOSAL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _bounded_identifier(
            self.proposition_id,
            "proposal proposition_id",
            maximum=MAX_PROPOSITION_ID_LENGTH,
        )
        _require_sha256(self.proposition_sha256, "proposal proposition digest")
        _bounded_identifier(
            self.source_identifier,
            "proposal source identifier",
            maximum=MAX_SOURCE_IDENTIFIER_LENGTH,
        )
        _require_sha256(self.source_content_sha256, "proposal source content digest")
        if self.relation not in RELATIONS:
            raise ValueError(f"unsupported proposition relation: {self.relation!r}")
        if not isinstance(self.role_assessments, tuple):
            raise TypeError("role_assessments must be a tuple")
        if len(self.role_assessments) > MAX_ROLE_ASSESSMENTS:
            raise ValueError("role assessments exceed their finite bound")
        if any(
            not isinstance(item, RoleAssessment) for item in self.role_assessments
        ):
            raise TypeError("role_assessments must contain RoleAssessment records")
        roles = [item.role for item in self.role_assessments]
        if len(set(roles)) != len(roles):
            raise ValueError("a role may be assessed exactly once")
        expected_order = tuple(item for item in EVIDENCE_ROLES if item in set(roles))
        if tuple(roles) != expected_order:
            raise ValueError("role assessments must use canonical role order")
        if not isinstance(self.evidence_spans, tuple):
            raise TypeError("evidence_spans must be a tuple")
        if len(self.evidence_spans) > MAX_EVIDENCE_SPANS:
            raise ValueError("evidence spans exceed their finite bound")
        if any(not isinstance(item, EvidenceSpan) for item in self.evidence_spans):
            raise TypeError("evidence_spans must contain EvidenceSpan records")
        total = sum(item.byte_count for item in self.evidence_spans)
        if total > MAX_TOTAL_CITED_BYTES:
            raise ValueError("total cited bytes exceed their finite bound")
        for assessment in self.role_assessments:
            for index in assessment.span_indexes:
                if index >= len(self.evidence_spans):
                    raise ValueError("a role cites a span the proposal does not carry")
        _ordered_vocabulary(self.reasons, ANALYSIS_REASONS, "analysis reason")
        if len(self.reasons) > MAX_ANALYSIS_REASONS:
            raise ValueError("analysis reasons exceed their finite bound")
        if self.schema_version != PROPOSAL_SCHEMA_VERSION:
            raise ValueError("unsupported verification proposal schema version")

    @property
    def verified_roles(self) -> tuple[str, ...]:
        return tuple(
            item.role
            for item in self.role_assessments
            if item.status == ROLE_STATUS_VERIFIED
        )

    @property
    def rejected_roles(self) -> tuple[str, ...]:
        return tuple(
            item.role
            for item in self.role_assessments
            if item.status == ROLE_STATUS_REJECTED
        )

    def spans_for(self, purpose: str) -> tuple[EvidenceSpan, ...]:
        return tuple(item for item in self.evidence_spans if item.purpose == purpose)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "proposition_id": self.proposition_id,
            "proposition_sha256": self.proposition_sha256,
            "source_identifier": self.source_identifier,
            "source_content_sha256": self.source_content_sha256,
            "relation": self.relation,
            "role_assessments": [item.as_dict() for item in self.role_assessments],
            "evidence_spans": [item.as_ref().as_dict() for item in self.evidence_spans],
            "reasons": list(self.reasons),
            "authority_claimed": False,
            "promoted_by_analyzer": False,
        }


def proposal_fingerprint(proposal: EvidenceVerificationProposal) -> str:
    if not isinstance(proposal, EvidenceVerificationProposal):
        raise TypeError("proposal_fingerprint requires an EvidenceVerificationProposal")
    return _fingerprint(proposal.as_dict())


# ── Verification levels ───────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class VerificationLevels:
    """How each of the four dimensions came to be believed, per record.

    This exists because a structurally impeccable record is easy to misread.
    Every deterministic check in this module can pass — the bytes are the
    acquired bytes, the span re-hashes, the role was expected and is competent
    for the scope — while the cited material still fails to establish the
    proposition.  ``sqlite3.connect("sessions.db")`` is a real line in a real
    implementation file, and one real line is not a proof that session state
    survives a process restart.

    So the record refuses to be ambiguous.  ``semantic_relation`` is
    ``analyzer_assessed``: a semantic judgement that was *accepted through* a
    deterministic gate, which is a different fact from a semantic judgement that
    was *produced by* one.  The distinction is enforced at construction rather
    than documented — :data:`DIMENSION_MAX_LEVEL` gives each dimension exactly
    one level it may hold besides ``not_established``, so a record asserting a
    deterministically verified semantic relation does not exist to be read.

    ``not_established`` is not a failure.  It is the honest value for a
    dimension nothing settled: a binding refusal never cited a span, and a
    result with no relation assessed no semantics.
    """

    source_binding: str = LEVEL_NOT_ESTABLISHED
    citation_integrity: str = LEVEL_NOT_ESTABLISHED
    role_admissibility: str = LEVEL_NOT_ESTABLISHED
    semantic_relation: str = LEVEL_NOT_ESTABLISHED
    schema_version: str = VERIFICATION_LEVELS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for dimension in VERIFICATION_DIMENSIONS:
            level = getattr(self, dimension)
            if level not in VERIFICATION_LEVELS:
                raise ValueError(
                    f"unsupported verification level for {dimension}: {level!r}"
                )
            if level == LEVEL_NOT_ESTABLISHED:
                continue
            permitted = DIMENSION_MAX_LEVEL[dimension]
            if level != permitted:
                if dimension == DIMENSION_SEMANTIC_RELATION:
                    raise ValueError(
                        "a semantic relation is analyzer-assessed and accepted "
                        "through a deterministic gate; it is never "
                        "deterministically verified"
                    )
                raise ValueError(
                    f"{dimension} is established deterministically or not at all"
                )
        if self.schema_version != VERIFICATION_LEVELS_SCHEMA_VERSION:
            raise ValueError("unsupported verification levels schema version")

    @property
    def semantic_relation_assessed(self) -> bool:
        return self.semantic_relation == LEVEL_ANALYZER_ASSESSED

    @property
    def semantic_assessment_source(self) -> str:
        return (
            SEMANTIC_ASSESSMENT_ANALYZER_PROPOSAL
            if self.semantic_relation_assessed
            else SEMANTIC_ASSESSMENT_NOT_ASSESSED
        )

    @property
    def deterministically_verified_dimensions(self) -> tuple[str, ...]:
        return tuple(
            dimension
            for dimension in VERIFICATION_DIMENSIONS
            if getattr(self, dimension) == LEVEL_DETERMINISTICALLY_VERIFIED
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_binding": self.source_binding,
            "citation_integrity": self.citation_integrity,
            "role_admissibility": self.role_admissibility,
            "semantic_relation": self.semantic_relation,
            "semantic_relation_assessed_by": self.semantic_assessment_source,
            "semantic_relation_proved_deterministically": False,
        }


def verification_levels_fingerprint(levels: VerificationLevels) -> str:
    if not isinstance(levels, VerificationLevels):
        raise TypeError("verification_levels_fingerprint requires a VerificationLevels")
    return _fingerprint(levels.as_dict())


# ── Authority and guardrails ──────────────────────────────────────────────────

def verification_authority(
    *,
    verification_performed: bool,
    promotion_performed: bool,
) -> dict[str, bool]:
    """Two narrow authorities, conditional on a valid operation; everything else false.

    ``evidence_promotion_authority`` is true only when the deterministic gate
    actually promoted, so the flag is a record of what happened rather than a
    permission the phase carries around.
    """
    return {
        "evidence_verification_authority": verification_performed,
        "evidence_promotion_authority": promotion_performed,
        "repository_read_authority": False,
        "repository_traversal_authority": False,
        "external_search_authority": False,
        "web_fetch_authority": False,
        "acquisition_authority": False,
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
        "provider_selection_authority": False,
        "model_selection_authority": False,
        "project_evolution_authority": False,
        "claim_synthesis_authority": False,
        "final_claim_authority": False,
        "human_approval_required": True,
    }


def verification_guardrails(
    *,
    source_content_analyzed: bool,
    evidence_verification_performed: bool,
    model_called: bool,
    semantic_relation_analyzer_assessed: bool = False,
) -> dict[str, bool]:
    """Honest performed-state, kept separate from what the phase is allowed to do.

    The last two entries are the ones a downstream reader needs most:  a
    relation in this record was *assessed* by an analyzer, and no part of this
    phase proved it.  Both are stated positively so that "we never checked" and
    "we checked and it holds" cannot be confused with each other.
    """
    return {
        "source_content_analyzed": source_content_analyzed,
        "evidence_verification_performed": evidence_verification_performed,
        "model_called": model_called,
        "semantic_relation_analyzer_assessed": semantic_relation_analyzer_assessed,
        "semantic_relation_proved_deterministically": False,
        "provider_selected_by_evidence_layer": False,
        "repository_files_read": False,
        "repository_traversal_performed": False,
        "acquisition_performed": False,
        "candidate_selection_performed": False,
        "network_called": False,
        "web_search_performed": False,
        "index_consulted": False,
        "graph_consulted": False,
        "validation_executed": False,
        "repository_written": False,
        "patch_created": False,
        "planning_performed": False,
        "claim_synthesis_performed": False,
        "final_claim_emitted": False,
        "source_content_serialized": False,
        "analyzer_reasoning_stored": False,
    }


# ── Verified evidence ─────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class VerifiedEvidence:
    """A promoted record.  Only the deterministic gate builds one.

    *VerifiedEvidence* means exactly four things, and they are the four
    dimensions :class:`VerificationLevels` names:

        tamper-bound, proposition-bound, citation-bound, role-admissible
        evidence assessment.

    It does **not** mean the proposition was proven true.  ``relation`` is an
    analyzer-assessed semantic judgement that cleared a deterministic gate;
    ``verified`` describes the quality and binding of the *assessment*, not the
    truth of the claim.  This record is not ground truth, and a reader who
    treats it as ground truth has recreated the failure the whole track exists
    to prevent.

    ``verified`` is likewise not "supports the claim": a contradiction that
    survived every gate is exactly as verified as a supporting one, and
    conflating the two is how a skeptical analysis quietly becomes a confirming
    one.
    """

    proposition_id: str
    proposition_sha256: str
    source_identifier: str
    source_content_sha256: str
    acquisition_receipt_fingerprint: str
    verified_roles: tuple[str, ...]
    rejected_roles: tuple[str, ...]
    relation: str
    evidence_span_refs: tuple[EvidenceSpanRef, ...]
    coverage_status: str
    verification_reasons: tuple[str, ...]
    analyzer_proposal_fingerprint: str
    verification_levels: VerificationLevels
    promotion_status: str = PROMOTION_PROMOTED
    schema_version: str = VERIFIED_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _bounded_identifier(
            self.proposition_id,
            "evidence proposition_id",
            maximum=MAX_PROPOSITION_ID_LENGTH,
        )
        _require_sha256(self.proposition_sha256, "evidence proposition digest")
        _bounded_identifier(
            self.source_identifier,
            "evidence source identifier",
            maximum=MAX_SOURCE_IDENTIFIER_LENGTH,
        )
        _require_sha256(self.source_content_sha256, "evidence source content digest")
        _require_sha256(
            self.acquisition_receipt_fingerprint,
            "evidence acquisition receipt fingerprint",
        )
        _ordered_vocabulary(self.verified_roles, EVIDENCE_ROLES, "verified role")
        _ordered_vocabulary(self.rejected_roles, EVIDENCE_ROLES, "rejected role")
        if set(self.verified_roles) & set(self.rejected_roles):
            raise ValueError("a role is either verified or rejected, never both")
        if not self.verified_roles:
            raise ValueError("promoted evidence must carry at least one verified role")
        if self.relation not in DIRECTIONAL_RELATIONS:
            raise ValueError("only supports or contradicts may be promoted")
        if not isinstance(self.evidence_span_refs, tuple):
            raise TypeError("evidence_span_refs must be a tuple")
        if not self.evidence_span_refs:
            raise ValueError("promoted evidence must cite bounded content")
        if len(self.evidence_span_refs) > MAX_EVIDENCE_SPANS:
            raise ValueError("evidence spans exceed their finite bound")
        if any(
            not isinstance(item, EvidenceSpanRef) for item in self.evidence_span_refs
        ):
            raise TypeError("evidence_span_refs must contain EvidenceSpanRef records")
        if sum(item.byte_count for item in self.evidence_span_refs) > MAX_TOTAL_CITED_BYTES:
            raise ValueError("total cited bytes exceed their finite bound")
        if any(
            item.source_content_sha256 != self.source_content_sha256
            for item in self.evidence_span_refs
        ):
            raise ValueError("every promoted span must belong to the verified source")
        if self.coverage_status not in RESULT_COVERAGE_STATUSES:
            raise ValueError(f"unsupported coverage status: {self.coverage_status!r}")
        _ordered_vocabulary(
            self.verification_reasons,
            VERIFICATION_REASONS,
            "verification reason",
        )
        _require_sha256(
            self.analyzer_proposal_fingerprint,
            "analyzer proposal fingerprint",
        )
        if not isinstance(self.verification_levels, VerificationLevels):
            raise TypeError("verification_levels must be a VerificationLevels")
        # A promoted record has cleared all three deterministic dimensions and
        # carries exactly one analyzer-assessed one.  Anything else is a record
        # that would read as more, or less, than the gate actually established.
        for dimension in DETERMINISTIC_DIMENSIONS:
            if getattr(self.verification_levels, dimension) != (
                LEVEL_DETERMINISTICALLY_VERIFIED
            ):
                raise ValueError(
                    f"promoted evidence must be {dimension} verified"
                )
        if not self.verification_levels.semantic_relation_assessed:
            raise ValueError(
                "a promoted record states an analyzer-assessed semantic relation"
            )
        if self.promotion_status != PROMOTION_PROMOTED:
            raise ValueError("a VerifiedEvidence record is always promoted")
        if self.schema_version != VERIFIED_EVIDENCE_SCHEMA_VERSION:
            raise ValueError("unsupported verified-evidence schema version")

    def _identity(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "proposition_id": self.proposition_id,
            "proposition_sha256": self.proposition_sha256,
            "source_identifier": self.source_identifier,
            "source_content_sha256": self.source_content_sha256,
            "acquisition_receipt_fingerprint": self.acquisition_receipt_fingerprint,
            "verified_roles": list(self.verified_roles),
            "rejected_roles": list(self.rejected_roles),
            "relation": self.relation,
            "evidence_span_refs": [item.as_dict() for item in self.evidence_span_refs],
            "coverage_status": self.coverage_status,
            "verification_reasons": list(self.verification_reasons),
            "analyzer_proposal_fingerprint": self.analyzer_proposal_fingerprint,
            "verification_levels": self.verification_levels.as_dict(),
            "promotion_status": self.promotion_status,
        }

    @property
    def evidence_id(self) -> str:
        """Deterministic identity.  No timestamp, no counter, no random token."""
        return _fingerprint(self._identity())

    def as_dict(self) -> dict[str, Any]:
        payload = dict(self._identity())
        payload["evidence_id"] = self.evidence_id
        payload["authority"] = verification_authority(
            verification_performed=True,
            promotion_performed=True,
        )
        payload["guardrails"] = verification_guardrails(
            source_content_analyzed=True,
            evidence_verification_performed=True,
            model_called=False,
            semantic_relation_analyzer_assessed=True,
        )
        payload["source_content_serialized"] = False
        return payload


# ── Verification result ───────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class EvidenceVerificationResult:
    """Every outcome, including the ones that promote nothing.

    ``insufficient`` and ``unrelated`` are recorded here without producing a
    :class:`VerifiedEvidence` record, so "we looked and it did not establish
    this" is a first-class result rather than a missing one.
    """

    status: str
    proposition_id: str
    proposition_sha256: str
    proposition_type: str
    proposition_scope: str
    source_identifier: str
    source_content_sha256: str
    acquisition_receipt_fingerprint: str
    request_fingerprint: str
    relation: str | None = None
    role_assessments: tuple[RoleAssessment, ...] = ()
    evidence_span_refs: tuple[EvidenceSpanRef, ...] = ()
    verification_levels: VerificationLevels = field(default_factory=VerificationLevels)
    coverage_status: str = COVERAGE_NOT_APPLICABLE
    promotion_status: str = PROMOTION_NOT_PROMOTED
    verified_evidence: VerifiedEvidence | None = None
    analyzer_proposal_fingerprint: str | None = None
    coverage_receipt_fingerprint: str | None = None
    current_state_fingerprint: str | None = None
    analyzer_name: str | None = None
    reasons: tuple[str, ...] = ()
    inconsistencies: tuple[str, ...] = ()
    source_content_analyzed: bool = False
    model_called: bool = False
    schema_version: str = RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in VERIFICATION_STATUSES:
            raise ValueError(f"unsupported verification status: {self.status!r}")
        _bounded_identifier(
            self.proposition_id,
            "result proposition_id",
            maximum=MAX_PROPOSITION_ID_LENGTH,
        )
        _require_sha256(self.proposition_sha256, "result proposition digest")
        if self.proposition_type not in PROPOSITION_TYPES:
            raise ValueError(f"unsupported proposition type: {self.proposition_type!r}")
        if self.proposition_scope not in PROPOSITION_SCOPES:
            raise ValueError(f"unsupported proposition scope: {self.proposition_scope!r}")
        _bounded_identifier(
            self.source_identifier,
            "result source identifier",
            maximum=MAX_SOURCE_IDENTIFIER_LENGTH,
        )
        _require_sha256(self.source_content_sha256, "result source content digest")
        _require_sha256(
            self.acquisition_receipt_fingerprint,
            "result acquisition receipt fingerprint",
        )
        _require_sha256(self.request_fingerprint, "result request fingerprint")
        if self.relation is not None and self.relation not in RELATIONS:
            raise ValueError(f"unsupported proposition relation: {self.relation!r}")
        if not isinstance(self.role_assessments, tuple):
            raise TypeError("role_assessments must be a tuple")
        if any(
            not isinstance(item, RoleAssessment) for item in self.role_assessments
        ):
            raise TypeError("role_assessments must contain RoleAssessment records")
        if len(self.role_assessments) > MAX_ROLE_ASSESSMENTS:
            raise ValueError("role assessments exceed their finite bound")
        if not isinstance(self.evidence_span_refs, tuple):
            raise TypeError("evidence_span_refs must be a tuple")
        if any(
            not isinstance(item, EvidenceSpanRef) for item in self.evidence_span_refs
        ):
            raise TypeError("evidence_span_refs must contain EvidenceSpanRef records")
        if len(self.evidence_span_refs) > MAX_EVIDENCE_SPANS:
            raise ValueError("evidence spans exceed their finite bound")
        if sum(item.byte_count for item in self.evidence_span_refs) > MAX_TOTAL_CITED_BYTES:
            raise ValueError("total cited bytes exceed their finite bound")
        if not isinstance(self.verification_levels, VerificationLevels):
            raise TypeError("verification_levels must be a VerificationLevels")
        if self.coverage_status not in RESULT_COVERAGE_STATUSES:
            raise ValueError(f"unsupported coverage status: {self.coverage_status!r}")
        if self.promotion_status not in PROMOTION_STATUSES:
            raise ValueError(f"unsupported promotion status: {self.promotion_status!r}")
        if self.verified_evidence is not None and not isinstance(
            self.verified_evidence, VerifiedEvidence
        ):
            raise TypeError("verified_evidence must be a VerifiedEvidence or None")
        for name in (
            "analyzer_proposal_fingerprint",
            "coverage_receipt_fingerprint",
            "current_state_fingerprint",
        ):
            _require_sha256(getattr(self, name), name.replace("_", " "), optional=True)
        if self.analyzer_name is not None:
            _bounded_identifier(self.analyzer_name, "analyzer name", maximum=128)
        _ordered_vocabulary(self.reasons, VERIFICATION_REASONS, "verification reason")
        _ordered_vocabulary(
            self.inconsistencies,
            VERIFICATION_INCONSISTENCIES,
            "verification inconsistency",
        )
        if len(self.reasons) > MAX_VERIFICATION_REASONS:
            raise ValueError("verification reasons exceed their finite bound")
        if len(self.inconsistencies) > MAX_VERIFICATION_INCONSISTENCIES:
            raise ValueError("verification inconsistencies exceed their finite bound")
        for name in ("source_content_analyzed", "model_called"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")

        # A relation *is* the semantic judgement.  A result that states one must
        # say it was assessed; a result that states none must not imply it was.
        if (self.relation is None) == self.verification_levels.semantic_relation_assessed:
            raise ValueError(
                "a stated relation is an analyzer-assessed semantic relation, and a "
                "result carrying no relation assessed no semantic relation"
            )
        if not self.source_content_analyzed and (
            self.verification_levels.semantic_relation_assessed
        ):
            raise ValueError(
                "a semantic relation cannot be assessed without analyzing content"
            )
        if not self.source_content_analyzed and (
            self.verification_levels.citation_integrity != LEVEL_NOT_ESTABLISHED
            or self.verification_levels.role_admissibility != LEVEL_NOT_ESTABLISHED
        ):
            raise ValueError(
                "citations and roles are verified during analysis, not before it"
            )

        promoted = self.promotion_status == PROMOTION_PROMOTED
        if promoted != (self.verified_evidence is not None):
            raise ValueError("promotion status must match the presence of a record")
        if promoted:
            evidence = self.verified_evidence
            assert evidence is not None
            if self.status not in {STATUS_VERIFIED, STATUS_CONTRADICTED}:
                raise ValueError("only verified or contradicted results may promote")
            if self.relation not in DIRECTIONAL_RELATIONS:
                raise ValueError("a promoted result must carry a directional relation")
            expected_status = (
                STATUS_VERIFIED
                if self.relation == RELATION_SUPPORTS
                else STATUS_CONTRADICTED
            )
            if self.status != expected_status:
                raise ValueError("promoted status must match the promoted relation")
            if (
                evidence.proposition_id != self.proposition_id
                or evidence.proposition_sha256 != self.proposition_sha256
                or evidence.source_identifier != self.source_identifier
                or evidence.source_content_sha256 != self.source_content_sha256
                or evidence.acquisition_receipt_fingerprint
                != self.acquisition_receipt_fingerprint
                or evidence.relation != self.relation
                or evidence.evidence_span_refs != self.evidence_span_refs
                or evidence.coverage_status != self.coverage_status
                or evidence.verification_levels != self.verification_levels
            ):
                raise ValueError("promoted evidence contradicts its own result")
            if not self.source_content_analyzed:
                raise ValueError("promotion requires that content was actually analyzed")
        else:
            if self.status in {STATUS_VERIFIED, STATUS_CONTRADICTED}:
                raise ValueError("a verified or contradicted status must promote")
        if self.status == STATUS_BINDING_INVALID:
            if not self.inconsistencies:
                raise ValueError("binding_invalid must state its inconsistency")
            if self.source_content_analyzed or self.relation is not None:
                raise ValueError("binding_invalid precedes any content analysis")
        if self.status == STATUS_UNSUPPORTED_SOURCE and self.source_content_analyzed:
            raise ValueError("an unsupported source is refused before analysis")
        if self.status == STATUS_COVERAGE_REQUIRED and (
            self.relation != RELATION_INSUFFICIENT
        ):
            raise ValueError("coverage_required downgrades the relation to insufficient")
        if self.status == STATUS_UNRELATED and self.relation != RELATION_UNRELATED:
            raise ValueError("an unrelated status carries the unrelated relation")
        if self.status == STATUS_INSUFFICIENT and self.relation != RELATION_INSUFFICIENT:
            raise ValueError("an insufficient status carries the insufficient relation")
        if self.model_called and not self.source_content_analyzed:
            raise ValueError("a model call without analysis is not a truthful result")
        if self.schema_version != RESULT_SCHEMA_VERSION:
            raise ValueError("unsupported verification result schema version")

    @property
    def verified_roles(self) -> tuple[str, ...]:
        return tuple(
            item.role
            for item in self.role_assessments
            if item.status == ROLE_STATUS_VERIFIED
        )

    @property
    def rejected_roles(self) -> tuple[str, ...]:
        return tuple(
            item.role
            for item in self.role_assessments
            if item.status == ROLE_STATUS_REJECTED
        )

    @property
    def promoted(self) -> bool:
        return self.promotion_status == PROMOTION_PROMOTED

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "status": self.status,
            "proposition_id": self.proposition_id,
            "proposition_sha256": self.proposition_sha256,
            "proposition_type": self.proposition_type,
            "proposition_scope": self.proposition_scope,
            "source_identifier": self.source_identifier,
            "source_content_sha256": self.source_content_sha256,
            "acquisition_receipt_fingerprint": self.acquisition_receipt_fingerprint,
            "request_fingerprint": self.request_fingerprint,
            "relation": self.relation,
            "role_assessments": [item.as_dict() for item in self.role_assessments],
            "verified_roles": list(self.verified_roles),
            "rejected_roles": list(self.rejected_roles),
            "evidence_span_refs": [item.as_dict() for item in self.evidence_span_refs],
            "verification_levels": self.verification_levels.as_dict(),
            "coverage_status": self.coverage_status,
            "promotion": {
                "promotion_status": self.promotion_status,
                "verified_evidence_fingerprint": (
                    None
                    if self.verified_evidence is None
                    else self.verified_evidence.evidence_id
                ),
            },
            "analyzer": {
                "analyzer_name": self.analyzer_name,
                "analyzer_proposal_fingerprint": self.analyzer_proposal_fingerprint,
                "model_called": self.model_called,
                "reasoning_trace_stored": False,
                # The relation is attributable to *this proposal*, not to a
                # vendor.  Provider and model names are not required anywhere in
                # the record, and naming one would grant it authority it has not
                # got.
                "semantic_relation_status": self.verification_levels.semantic_relation,
                "semantic_relation_assessed_by": (
                    self.verification_levels.semantic_assessment_source
                ),
            },
            "coverage_receipt_fingerprint": self.coverage_receipt_fingerprint,
            "current_state_fingerprint": self.current_state_fingerprint,
            "reasons": list(self.reasons),
            "inconsistencies": list(self.inconsistencies),
            "authority": verification_authority(
                verification_performed=self.source_content_analyzed,
                promotion_performed=self.promoted,
            ),
            "guardrails": verification_guardrails(
                source_content_analyzed=self.source_content_analyzed,
                evidence_verification_performed=self.source_content_analyzed,
                model_called=self.model_called,
                semantic_relation_analyzer_assessed=(
                    self.verification_levels.semantic_relation_assessed
                ),
            ),
            "source_content_serialized": False,
            "claim_synthesized": False,
        }


def render_evidence_verification_result_json(result: EvidenceVerificationResult) -> str:
    if not isinstance(result, EvidenceVerificationResult):
        raise TypeError(
            "render_evidence_verification_result_json requires an "
            "EvidenceVerificationResult"
        )
    return json.dumps(result.as_dict(), indent=2, ensure_ascii=False, sort_keys=False)


# ── Independent records, never a synthesis ────────────────────────────────────

def render_verification_set_json(
    results: tuple[EvidenceVerificationResult, ...],
) -> str:
    """Serialize several independent results side by side.

    There is deliberately no aggregate here — no majority, no weighted support,
    no overall truth value.  Combining independently verified records is a later
    phase's job, and doing it badly is precisely how three partial readings
    became one confident architectural claim.
    """
    if not isinstance(results, tuple):
        raise TypeError("render_verification_set_json requires a tuple of results")
    if any(not isinstance(item, EvidenceVerificationResult) for item in results):
        raise TypeError("every member must be an EvidenceVerificationResult")
    payload = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "results": [item.as_dict() for item in results],
        "aggregated": False,
        "claim_synthesized": False,
        "majority_computed": False,
        "confidence_computed": False,
        # Putting records next to each other is not evidence of anything.  Each
        # relation stays exactly as analyzer-assessed as it was alone.
        "semantic_relations_proved_deterministically": False,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False)


__all__ = [
    "ANALYSIS_REASONS",
    "AUTHORITY_NOT_VERIFIED",
    "COVERAGE_NOT_APPLICABLE",
    "COVERAGE_NOT_SUPPLIED",
    "COVERAGE_REASONS",
    "COVERAGE_STATUSES",
    "COVERAGE_SUFFICIENT",
    "CURRENT_STATE_BASES",
    "CURRENT_STATE_ESTABLISHED",
    "CURRENT_STATE_NOT_ESTABLISHED",
    "CURRENT_STATE_STATUSES",
    "DETERMINISTIC_DIMENSIONS",
    "DIMENSION_CITATION_INTEGRITY",
    "DIMENSION_MAX_LEVEL",
    "DIMENSION_ROLE_ADMISSIBILITY",
    "DIMENSION_SEMANTIC_RELATION",
    "DIMENSION_SOURCE_BINDING",
    "DIRECTIONAL_RELATIONS",
    "LEVEL_ANALYZER_ASSESSED",
    "LEVEL_DETERMINISTICALLY_VERIFIED",
    "LEVEL_NOT_ESTABLISHED",
    "MAX_EVIDENCE_SPANS",
    "MAX_SPAN_BYTES",
    "MAX_TOTAL_CITED_BYTES",
    "PHASE_ID",
    "PROMOTION_NOT_PROMOTED",
    "PROMOTION_PROMOTED",
    "PROPOSITION_SCOPES",
    "PROPOSITION_TYPES",
    "RELATIONS",
    "RELATION_CONTRADICTS",
    "RELATION_INSUFFICIENT",
    "RELATION_SUPPORTS",
    "RELATION_UNRELATED",
    "ROLE_STATUSES",
    "SCOPE_COMPETENT_ROLES",
    "SCOPES_REQUIRING_CURRENT_STATE",
    "SEMANTIC_ASSESSMENT_ANALYZER_PROPOSAL",
    "SEMANTIC_ASSESSMENT_NOT_ASSESSED",
    "SEMANTIC_ASSESSMENT_SOURCES",
    "SOURCE_ACQUIRED",
    "SPAN_PURPOSES",
    "VERIFICATION_CONSTRAINTS",
    "VERIFICATION_DIMENSIONS",
    "VERIFICATION_INCONSISTENCIES",
    "VERIFICATION_LEVELS",
    "VERIFICATION_LEVELS_SCHEMA_VERSION",
    "VERIFICATION_REASONS",
    "VERIFICATION_STATUSES",
    "VERIFICATION_UNVERIFIED",
    "BoundedPayloadView",
    "CurrentStateReceipt",
    "EvidenceSpan",
    "EvidenceSpanRef",
    "EvidenceVerificationProposal",
    "EvidenceVerificationRequest",
    "EvidenceVerificationResult",
    "NegativeClaimCoverage",
    "Proposition",
    "RoleAssessment",
    "VerificationLevels",
    "VerifiedEvidence",
    "bounded_payload_view",
    "coverage_fingerprint",
    "current_state_fingerprint",
    "proposal_fingerprint",
    "render_evidence_verification_result_json",
    "render_verification_set_json",
    "source_receipt_fingerprint",
    "span_from_view",
    "verification_authority",
    "verification_guardrails",
    "verification_levels_fingerprint",
    "verification_request_fingerprint",
]
