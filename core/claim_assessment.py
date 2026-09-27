"""CLAIM.1 — Bounded Proposition Assessment Contract.

EVIDENCE.1 answered *what does one acquired source establish about one
proposition*.  EVIDENCE.2 answered *what does this evidence set contain*.
CLAIM.1 owns the next transition and only that one:

    one EVIDENCE.2 EvidenceSetAssessment
        -> what categorical epistemic status is justified for this proposition?

It does **not** answer *what is ultimately true*.  The distinction the whole
module exists to hold is four-way and is never collapsed:

    evidence assessment != proposition assessment != final truth
                                                  != final user-facing answer

``supported_by_assessed_evidence`` means *the currently admitted,
analyzer-assessed evidence set supports P*.  It does not mean P is proven, and
there is no field in this module that could say it was.  There is no
``claim_true``, no ``proposition_true``, no ``ground_truth``, no
``semantically_verified``, no confidence, no probability, no score and no float
anywhere in the contract.

Ten boundaries hold in every outcome.

**Aggregation cannot upgrade semantic epistemic level.**  Every member relation
arrived ``analyzer_assessed`` from EVIDENCE.1 and stays ``analyzer_assessed``
here.  Thirty-one agreeing support records are thirty-one analyzer-assessed
support records.  :data:`SEMANTIC_BASES` holds two values and
``deterministically_verified`` is not one of them, so a ClaimAssessment
asserting deterministic semantics does not construct — the invariant is
structural rather than a rule someone could forget to apply.

**Conflict is terminal.**  ``conflict_status == conflicting`` produces
``conflicting_evidence`` and stops.  Five supports and one contradiction is
conflicting.  Thirty-one supports and one contradiction is conflicting.  There
is no counting of supports against contradictions, no role weight, no source
weight, no analyzer weight, no recency rule and no "implementation beats tests"
tiebreak.  A future human adjudication phase may resolve a conflict; CLAIM.1
does not.

**Duplicates do not strengthen anything.**  Four byte-identical support records
are one lineage.  The claim status a set produces is the status its one real
lineage produces, and ``corroboration_status`` records ``duplicate_only``
descriptively rather than as a quantity.  There is no ``stronger_support`` and
no strength scale to put it on.

**A different digest is not independence.**  EVIDENCE.2 reports
``independence_unknown`` for anything it cannot prove duplicated, and CLAIM.1
preserves that.  ``independently_corroborated`` is reachable only where the set
carries a trusted distinct-origin declaration.  Because nothing upstream mints
one, most non-duplicate evidence stays ``independence_unknown`` — which is
recorded as a gap and, on its own, blocks nothing.

**Absence still needs coverage.**  A ``negative_existential`` proposition
reaches ``supported_by_assessed_evidence`` only through
``negative_claim_coverage == complete``.  No number of support records
substitutes for the receipt.  One concrete counterexample still contradicts an
absence with no coverage at all, because acknowledging a counterexample and
proving an absence are different questions.

**Code existing is not code running.**  A proposition whose scope is about a
running system reaches support only through
``current_state_coverage == complete``.  Incomplete is
``current_state_unestablished``; receipts that disagree are
``current_state_inconsistent``.  Nothing here inspects a runtime.

**Role presence is not directional support.**  EVIDENCE.2 kept the two apart and
CLAIM.1 does not merge them.  A source verified as ``implementation_authority``
whose relation is ``insufficient`` discharges required-role coverage and
discharges no support.

**Nothing is reinterpreted.**  A relation EVIDENCE.1 decided is a relation
CLAIM.1 reads.  No span is re-read, no test is promoted because several tests
agree, no dependency declaration becomes runtime use, no historical note is
upgraded.  CLAIM.1 applies set-level policy and never member-level judgement.

**The proposition is preserved exactly.**  Not narrowed, not broadened, not
requalified, not split, not merged.  Changing what a claim says requires a new
proposition and a new evidence path.

**No model.**  EVIDENCE.1 already supplied bounded semantic relations through a
deterministic gate.  CLAIM.1 adjudicates set conditions with a rule table and
calls nothing.

The module is stdlib-only and pure.  It reads no file, opens no path, walks no
directory, contacts no service, calls no language system, acquires nothing,
selects nothing, executes nothing, synthesizes no response, and is wired into no
live path.  It does not import the acquisition payload contract, the EVIDENCE.1
analyzer, the promotion gate or the model adapter, because reaching any of them
means reaching a way to decide a relation that has already been decided.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from core.evidence_requirements import EVIDENCE_ROLES
from core.evidence_set_assessment import (
    CONFLICT_CONFLICTING,
    CONFLICT_CONTRADICTION_ONLY,
    CONFLICT_NOT_ASSESSED,
    CONFLICT_NO_DIRECTIONAL_EVIDENCE,
    CONFLICT_STATUSES,
    CONFLICT_SUPPORT_ONLY,
    COVERAGE_COMPLETE,
    COVERAGE_INCONSISTENT,
    COVERAGE_NOT_APPLICABLE,
    COVERAGE_NOT_ASSESSED,
    INDEPENDENCE_DUPLICATE,
    INDEPENDENCE_INDEPENDENT,
    MAX_EVIDENCE_SET_RECORDS,
    SET_ASSESSED,
    SET_COVERAGE_STATUSES,
    EvidenceSetAssessment,
)
from core.evidence_verification import (
    LEVEL_ANALYZER_ASSESSED,
    LEVEL_NOT_ESTABLISHED,
    MAX_PROPOSITION_CHARS,
    MAX_PROPOSITION_ID_LENGTH,
    PROPOSITION_NEGATIVE_EXISTENTIAL,
    PROPOSITION_SCOPES,
    PROPOSITION_TYPES,
    RELATION_CONTRADICTS,
    RELATION_INSUFFICIENT,
    RELATION_SUPPORTS,
    RELATION_UNRELATED,
    SCOPES_REQUIRING_CURRENT_STATE,
    Proposition,
)


PHASE_ID = "CLAIM.1"

REQUIREMENTS_SCHEMA_VERSION = "claim_1_claim_requirements_v1"
REQUEST_SCHEMA_VERSION = "claim_1_claim_assessment_request_v1"
ASSESSMENT_SCHEMA_VERSION = "claim_1_claim_assessment_v1"


# ── Assessment status vocabulary ──────────────────────────────────────────────
#: Eight categorical values, and every one of them names a *state of the
#: evidence*, never a state of the world.  ``true``, ``false``, ``likely_true``,
#: ``probably_false`` and ``confidence_high`` are absent on purpose: each would
#: assert something CLAIM.1 has no way to establish, and a reader who saw one
#: would be right to believe it.
#:
#: There is deliberately no separate ``no_directional_evidence`` status.  A set
#: holding one ``insufficient`` record and a set holding one ``unrelated``
#: record both mean the same thing for the proposition — nothing directional was
#: established — and splitting them would invite a reader to treat one as closer
#: to an answer.  The distinction survives in ``conflict_status`` and in the
#: reason codes, where it describes the material rather than the claim.
STATUS_SUPPORTED = "supported_by_assessed_evidence"
STATUS_CONTRADICTED = "contradicted_by_assessed_evidence"
STATUS_CONFLICTING = "conflicting_evidence"
STATUS_INSUFFICIENT = "insufficient_evidence"
STATUS_COVERAGE_INCOMPLETE = "coverage_incomplete"
STATUS_CURRENT_STATE_UNESTABLISHED = "current_state_unestablished"
STATUS_CURRENT_STATE_INCONSISTENT = "current_state_inconsistent"
STATUS_INCONSISTENT_INPUT = "inconsistent_input"

ASSESSMENT_STATUSES: tuple[str, ...] = (
    STATUS_SUPPORTED,
    STATUS_CONTRADICTED,
    STATUS_CONFLICTING,
    STATUS_INSUFFICIENT,
    STATUS_COVERAGE_INCOMPLETE,
    STATUS_CURRENT_STATE_UNESTABLISHED,
    STATUS_CURRENT_STATE_INCONSISTENT,
    STATUS_INCONSISTENT_INPUT,
)

#: The two statuses that point somewhere.  Both are bounded by the assessed
#: evidence and neither is a truth value.
DIRECTIONAL_STATUSES: frozenset[str] = frozenset(
    {STATUS_SUPPORTED, STATUS_CONTRADICTED}
)


# ── Semantic basis ────────────────────────────────────────────────────────────
#: How the underlying semantic relationships came to be believed.  Two values,
#: and ``deterministically_verified`` is not one of them.  An assessed
#: ClaimAssessment must state :data:`BASIS_ANALYZER_ASSESSED`, so aggregation
#: has nowhere to write an upgrade even if a caller wanted one.
BASIS_ANALYZER_ASSESSED = LEVEL_ANALYZER_ASSESSED
BASIS_NOT_ESTABLISHED = LEVEL_NOT_ESTABLISHED

SEMANTIC_BASES: tuple[str, ...] = (BASIS_ANALYZER_ASSESSED, BASIS_NOT_ESTABLISHED)

#: What the *set-level* policy was applied to: analyzer assessments that already
#: cleared EVIDENCE.1's deterministic gate.  Naming it separately keeps the
#: honest reading available to a human reviewer — a judgement accepted through a
#: deterministic gate is not a judgement produced by one.
ASSESSMENT_BASIS_GATED_ANALYZER_ASSESSMENTS = "gated_analyzer_assessments"
ASSESSMENT_BASIS_NOT_ASSESSED = "not_assessed"

ASSESSMENT_BASES: tuple[str, ...] = (
    ASSESSMENT_BASIS_GATED_ANALYZER_ASSESSMENTS,
    ASSESSMENT_BASIS_NOT_ASSESSED,
)


# ── Corroboration ─────────────────────────────────────────────────────────────
#: A description of the *lineage shape* behind the directional records, never a
#: quantity and never a probability.  ``duplicate_only`` says the directional
#: evidence collapses to one duplicated lineage; ``independence_unknown`` says
#: nothing established whether two readings were produced independently;
#: ``independently_corroborated`` is reachable only where EVIDENCE.2 holds a
#: trusted distinct-origin declaration, which nothing upstream currently mints.
CORROBORATION_NONE = "none"
CORROBORATION_DUPLICATE_ONLY = "duplicate_only"
CORROBORATION_INDEPENDENCE_UNKNOWN = "independence_unknown"
CORROBORATION_INDEPENDENT = "independently_corroborated"
CORROBORATION_NOT_ASSESSED = "not_assessed"

CORROBORATION_STATUSES: tuple[str, ...] = (
    CORROBORATION_NONE,
    CORROBORATION_DUPLICATE_ONLY,
    CORROBORATION_INDEPENDENCE_UNKNOWN,
    CORROBORATION_INDEPENDENT,
    CORROBORATION_NOT_ASSESSED,
)


# ── Reasons ───────────────────────────────────────────────────────────────────
#: Bounded, stable, and stated in canonical order so two assessments holding the
#: same facts fingerprint identically.  There is no free-form reasoning field
#: anywhere in this module, because a sentence is where a verdict hides.
CLAIM_PROPOSITION_BINDING_VERIFIED = "CLAIM_PROPOSITION_BINDING_VERIFIED"
CLAIM_EVIDENCE_SET_BINDING_VERIFIED = "CLAIM_EVIDENCE_SET_BINDING_VERIFIED"
CLAIM_SET_PARTITION_REDERIVED = "CLAIM_SET_PARTITION_REDERIVED"
CLAIM_SUPPORTED_DIRECTIONAL_EVIDENCE = "CLAIM_SUPPORTED_DIRECTIONAL_EVIDENCE"
CLAIM_CONTRADICTED_DIRECTIONAL_EVIDENCE = "CLAIM_CONTRADICTED_DIRECTIONAL_EVIDENCE"
CLAIM_CONFLICTING_EVIDENCE = "CLAIM_CONFLICTING_EVIDENCE"
CLAIM_CONFLICT_NOT_ADJUDICATED = "CLAIM_CONFLICT_NOT_ADJUDICATED"
CLAIM_INSUFFICIENT_DIRECTIONAL_EVIDENCE = "CLAIM_INSUFFICIENT_DIRECTIONAL_EVIDENCE"
CLAIM_NO_DIRECTIONAL_EVIDENCE = "CLAIM_NO_DIRECTIONAL_EVIDENCE"
CLAIM_REQUIRED_ROLE_COVERAGE_INCOMPLETE = "CLAIM_REQUIRED_ROLE_COVERAGE_INCOMPLETE"
CLAIM_SCOPE_COMPETENT_ROLE_ABSENT = "CLAIM_SCOPE_COMPETENT_ROLE_ABSENT"
CLAIM_NEGATIVE_COVERAGE_REQUIRED = "CLAIM_NEGATIVE_COVERAGE_REQUIRED"
CLAIM_NEGATIVE_COVERAGE_INCONSISTENT = "CLAIM_NEGATIVE_COVERAGE_INCONSISTENT"
CLAIM_CURRENT_STATE_UNESTABLISHED = "CLAIM_CURRENT_STATE_UNESTABLISHED"
CLAIM_CURRENT_STATE_COVERAGE_INCONSISTENT = "CLAIM_CURRENT_STATE_COVERAGE_INCONSISTENT"
CLAIM_INDEPENDENT_CORROBORATION_REQUIRED = "CLAIM_INDEPENDENT_CORROBORATION_REQUIRED"
CLAIM_INDEPENDENT_CORROBORATION_UNESTABLISHED = (
    "CLAIM_INDEPENDENT_CORROBORATION_UNESTABLISHED"
)
CLAIM_DUPLICATE_LINEAGE_DOES_NOT_STRENGTHEN = (
    "CLAIM_DUPLICATE_LINEAGE_DOES_NOT_STRENGTHEN"
)
CLAIM_SEMANTIC_BASIS_PRESERVED = "CLAIM_SEMANTIC_BASIS_PRESERVED"
CLAIM_RELATIONS_NOT_REINTERPRETED = "CLAIM_RELATIONS_NOT_REINTERPRETED"
CLAIM_PROPOSITION_NOT_REWRITTEN = "CLAIM_PROPOSITION_NOT_REWRITTEN"
CLAIM_INPUT_REJECTED = "CLAIM_INPUT_REJECTED"
CLAIM_NO_MAJORITY_COMPUTED = "CLAIM_NO_MAJORITY_COMPUTED"
CLAIM_NO_CONFIDENCE_COMPUTED = "CLAIM_NO_CONFIDENCE_COMPUTED"
CLAIM_NO_OBJECTIVE_TRUTH_DETERMINED = "CLAIM_NO_OBJECTIVE_TRUTH_DETERMINED"
CLAIM_NO_FINAL_RESPONSE_SYNTHESIZED = "CLAIM_NO_FINAL_RESPONSE_SYNTHESIZED"

CLAIM_REASONS: tuple[str, ...] = (
    CLAIM_PROPOSITION_BINDING_VERIFIED,
    CLAIM_EVIDENCE_SET_BINDING_VERIFIED,
    CLAIM_SET_PARTITION_REDERIVED,
    CLAIM_SUPPORTED_DIRECTIONAL_EVIDENCE,
    CLAIM_CONTRADICTED_DIRECTIONAL_EVIDENCE,
    CLAIM_CONFLICTING_EVIDENCE,
    CLAIM_CONFLICT_NOT_ADJUDICATED,
    CLAIM_INSUFFICIENT_DIRECTIONAL_EVIDENCE,
    CLAIM_NO_DIRECTIONAL_EVIDENCE,
    CLAIM_REQUIRED_ROLE_COVERAGE_INCOMPLETE,
    CLAIM_SCOPE_COMPETENT_ROLE_ABSENT,
    CLAIM_NEGATIVE_COVERAGE_REQUIRED,
    CLAIM_NEGATIVE_COVERAGE_INCONSISTENT,
    CLAIM_CURRENT_STATE_UNESTABLISHED,
    CLAIM_CURRENT_STATE_COVERAGE_INCONSISTENT,
    CLAIM_INDEPENDENT_CORROBORATION_REQUIRED,
    CLAIM_INDEPENDENT_CORROBORATION_UNESTABLISHED,
    CLAIM_DUPLICATE_LINEAGE_DOES_NOT_STRENGTHEN,
    CLAIM_SEMANTIC_BASIS_PRESERVED,
    CLAIM_RELATIONS_NOT_REINTERPRETED,
    CLAIM_PROPOSITION_NOT_REWRITTEN,
    CLAIM_INPUT_REJECTED,
    CLAIM_NO_MAJORITY_COMPUTED,
    CLAIM_NO_CONFIDENCE_COMPUTED,
    CLAIM_NO_OBJECTIVE_TRUTH_DETERMINED,
    CLAIM_NO_FINAL_RESPONSE_SYNTHESIZED,
)


# ── Inconsistencies ───────────────────────────────────────────────────────────
#: Every one of these is fatal and produces ``inconsistent_input`` with no
#: assessment at all.  CLAIM.1 does not repair a malformed evidence set, does
#: not reacquire evidence and does not fall back to a weaker reading: a set that
#: cannot be trusted to say what it contains cannot be adjudicated.
#:
#: Coverage *gaps* are a different thing entirely.  They are not listed here;
#: they live in the coverage fields and in ``missing_requirements``.
INCONSISTENT_EVIDENCE_SET = "evidence_set_inconsistent"
INCONSISTENT_PROPOSITION_BINDING = "proposition_binding_mismatch"
INCONSISTENT_SET_FINGERPRINT = "evidence_set_fingerprint_mismatch"
INCONSISTENT_MEMBER_FINGERPRINT = "member_fingerprint_invalid"
INCONSISTENT_RELATION_PARTITION = "relation_partition_mismatch"
INCONSISTENT_LINEAGE_MEMBERSHIP = "lineage_membership_mismatch"
INCONSISTENT_SEMANTIC_BASIS_UPGRADED = "semantic_basis_upgraded"
INCONSISTENT_UPSTREAM_CLAIM_AUTHORITY = "upstream_claim_authority_asserted"
INCONSISTENT_UPSTREAM_GUARDRAIL = "upstream_guardrail_violated"
INCONSISTENT_REQUIREMENT_BINDING = "evidence_requirement_binding_mismatch"

CLAIM_INCONSISTENCIES: tuple[str, ...] = (
    INCONSISTENT_EVIDENCE_SET,
    INCONSISTENT_PROPOSITION_BINDING,
    INCONSISTENT_SET_FINGERPRINT,
    INCONSISTENT_MEMBER_FINGERPRINT,
    INCONSISTENT_RELATION_PARTITION,
    INCONSISTENT_LINEAGE_MEMBERSHIP,
    INCONSISTENT_SEMANTIC_BASIS_UPGRADED,
    INCONSISTENT_UPSTREAM_CLAIM_AUTHORITY,
    INCONSISTENT_UPSTREAM_GUARDRAIL,
    INCONSISTENT_REQUIREMENT_BINDING,
)


# ── Missing requirements ──────────────────────────────────────────────────────
#: Gaps, stated as gaps.  None of these is a judgement about the proposition;
#: each names something the evidence set does not contain and CLAIM.1 cannot
#: acquire.  Several appear alongside a positive assessment on purpose:
#: ``independent_corroboration_unestablished`` is the normal state of the
#: pipeline today and blocks nothing unless an upstream requirement asks it to.
MISSING_ROLE_REQUIREMENTS_NOT_SUPPLIED = "role_requirements_not_supplied"
MISSING_REQUIRED_ROLE = "required_role_absent"
MISSING_SCOPE_COMPETENT_ROLE = "scope_competent_role_absent"
MISSING_DIRECTIONAL_EVIDENCE = "directional_evidence_absent"
MISSING_NEGATIVE_CLAIM_COVERAGE = "negative_claim_coverage_absent"
MISSING_CURRENT_STATE_COVERAGE = "current_state_coverage_absent"
MISSING_INDEPENDENT_CORROBORATION = "independent_corroboration_unestablished"
MISSING_CONFLICT_ADJUDICATION = "conflict_adjudication_unavailable"

CLAIM_MISSING_REQUIREMENTS: tuple[str, ...] = (
    MISSING_ROLE_REQUIREMENTS_NOT_SUPPLIED,
    MISSING_REQUIRED_ROLE,
    MISSING_SCOPE_COMPETENT_ROLE,
    MISSING_DIRECTIONAL_EVIDENCE,
    MISSING_NEGATIVE_CLAIM_COVERAGE,
    MISSING_CURRENT_STATE_COVERAGE,
    MISSING_INDEPENDENT_CORROBORATION,
    MISSING_CONFLICT_ADJUDICATION,
)


# ── Bounds ────────────────────────────────────────────────────────────────────
MAX_CLAIM_RECORD_REFS = MAX_EVIDENCE_SET_RECORDS
MAX_CLAIM_LINEAGE_REFS = MAX_EVIDENCE_SET_RECORDS
MAX_CLAIM_REASONS = len(CLAIM_REASONS)
MAX_CLAIM_INCONSISTENCIES = len(CLAIM_INCONSISTENCIES)
MAX_CLAIM_MISSING_REQUIREMENTS = len(CLAIM_MISSING_REQUIREMENTS)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _require_sha256(value: str | None, label: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not _is_sha256(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _bounded_identifier(value: object, label: str, *, maximum: int) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds its finite bound")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{label} may not contain control characters")


def _repeats(values: tuple[str, ...]) -> bool:
    """Duplicate detection without arithmetic on either side of a comparison."""
    seen: set[str] = set()
    for value in values:
        if value in seen:
            return True
        seen.add(value)
    return False


def _ordered_vocabulary(
    values: tuple[str, ...],
    vocabulary: tuple[str, ...],
    label: str,
) -> None:
    """Canonical vocabulary order, each value at most once.

    Two assessments that hold the same facts must fingerprint identically, so
    the order a caller happened to write things down carries no meaning.
    """
    if not isinstance(values, tuple):
        raise TypeError(f"{label}s must be a tuple")
    if _repeats(values):
        raise ValueError(f"each {label} may be stated exactly once")
    for value in values:
        if value not in vocabulary:
            raise ValueError(f"unsupported {label}: {value!r}")
    expected = tuple(item for item in vocabulary if item in set(values))
    if values != expected:
        raise ValueError(f"{label}s must use canonical vocabulary order")


def _ordered_reasons(codes: set[str]) -> tuple[str, ...]:
    return tuple(item for item in CLAIM_REASONS if item in codes)


def _ordered_inconsistencies(codes: set[str]) -> tuple[str, ...]:
    return tuple(item for item in CLAIM_INCONSISTENCIES if item in codes)


def _ordered_missing(codes: set[str]) -> tuple[str, ...]:
    return tuple(item for item in CLAIM_MISSING_REQUIREMENTS if item in codes)


def _digest_refs(values: object, label: str, *, maximum: int) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{label}s must be a tuple")
    if len(values) > maximum:
        raise ValueError(f"{label}s exceed their finite bound")
    if list(values) != sorted(values):
        raise ValueError(f"{label}s must be canonically ordered")
    if _repeats(values):
        raise ValueError(f"a {label} appears exactly once")
    for value in values:
        _require_sha256(value, label)


# ── Supplied claim requirements ───────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ClaimRequirements:
    """Somebody else's statement of what this proposition's evidence must hold.

    Consumed, never derived.  CLAIM.1 has no opinion about which roles a claim
    *ought* to have and will not guess one: with nothing supplied, role coverage
    is whatever EVIDENCE.2 said, and a set assessed without role requirements
    records ``role_requirements_not_supplied`` as a gap rather than silently
    reading as complete.

    ``independent_corroboration_required`` is the one place a caller may demand
    more than the default.  It exists because "two independent sources agree" is
    a real requirement for some claims and a fantasy for most: nothing in the
    pipeline currently mints a distinct-origin declaration, so switching it on
    means most positive assessments come back ``insufficient_evidence``.  That
    is the honest outcome, and it is opt-in rather than imposed.
    """

    proposition_id: str
    proposition_sha256: str
    required_roles: tuple[str, ...]
    evidence_requirement_fingerprint: str
    independent_corroboration_required: bool = False
    schema_version: str = REQUIREMENTS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _bounded_identifier(
            self.proposition_id,
            "requirements proposition_id",
            maximum=MAX_PROPOSITION_ID_LENGTH,
        )
        _require_sha256(self.proposition_sha256, "requirements proposition digest")
        _ordered_vocabulary(self.required_roles, EVIDENCE_ROLES, "required role")
        _require_sha256(
            self.evidence_requirement_fingerprint,
            "upstream evidence requirement fingerprint",
        )
        if not isinstance(self.independent_corroboration_required, bool):
            raise TypeError("independent_corroboration_required must be a bool")
        if self.schema_version != REQUIREMENTS_SCHEMA_VERSION:
            raise ValueError("unsupported claim requirements schema version")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "proposition_id": self.proposition_id,
            "proposition_sha256": self.proposition_sha256,
            "required_roles": list(self.required_roles),
            "evidence_requirement_fingerprint": self.evidence_requirement_fingerprint,
            "independent_corroboration_required": (
                self.independent_corroboration_required
            ),
            "derived_by_claim_1": False,
        }


def claim_requirements_fingerprint(requirements: ClaimRequirements) -> str:
    if not isinstance(requirements, ClaimRequirements):
        raise TypeError("claim_requirements_fingerprint requires a ClaimRequirements")
    return _fingerprint(requirements.as_dict())


# ── The claim request ─────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ClaimAssessmentRequest:
    """One proposition and the one assessed evidence set said to be about it.

    The proposition arrives separately from the set because
    :class:`~core.evidence_set_assessment.EvidenceSetAssessment` carries the
    claim's *identity* — id, digest, type, scope — and not its text.  CLAIM.1
    needs the text in order to preserve it, and re-binds the supplied claim to
    the set by digest before reading anything: a proposition whose wording
    drifted produces a different ``proposition_sha256`` than the one the set was
    assessed over, and is refused rather than quietly assessed.

    ``expected_evidence_set_fingerprint`` is optional and is the caller's own
    tamper binding.  Supplying one that does not match the set is fatal.
    """

    proposition: Proposition
    evidence_set: EvidenceSetAssessment
    requirements: ClaimRequirements | None = None
    expected_evidence_set_fingerprint: str | None = None
    schema_version: str = REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.proposition, Proposition):
            raise TypeError("a claim assessment request requires a Proposition")
        if not isinstance(self.evidence_set, EvidenceSetAssessment):
            raise TypeError(
                "a claim assessment request requires one EvidenceSetAssessment"
            )
        if self.requirements is not None and not isinstance(
            self.requirements, ClaimRequirements
        ):
            raise TypeError("requirements must be a ClaimRequirements or None")
        _require_sha256(
            self.expected_evidence_set_fingerprint,
            "expected evidence set fingerprint",
            optional=True,
        )
        if self.schema_version != REQUEST_SCHEMA_VERSION:
            raise ValueError("unsupported claim assessment request schema version")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "proposition": self.proposition.as_dict(),
            "evidence_set_fingerprint": self.evidence_set.assessment_fingerprint,
            "expected_evidence_set_fingerprint": (
                self.expected_evidence_set_fingerprint
            ),
            "requirements_fingerprint": (
                None
                if self.requirements is None
                else claim_requirements_fingerprint(self.requirements)
            ),
            "source_content_supplied": False,
            "additional_propositions_supplied": False,
        }


def claim_request_fingerprint(request: ClaimAssessmentRequest) -> str:
    if not isinstance(request, ClaimAssessmentRequest):
        raise TypeError("claim_request_fingerprint requires a ClaimAssessmentRequest")
    return _fingerprint(request.as_dict())


# ── Authority and guardrails ──────────────────────────────────────────────────

def claim_authority(*, assessment_performed: bool) -> dict[str, bool]:
    """One narrow authority, conditional on a usable set; everything else false.

    ``final_claim_authority`` is false in every outcome, including the one a
    reader would most like to treat as an answer: support-only, coverage
    complete, roles complete, no contradiction.  So is
    ``response_synthesis_authority`` — combining several proposition assessments
    into a task answer is SYNTHESIS.1's job, and SYNTHESIS.1 does not exist.
    """
    return {
        "claim_assessment_authority": assessment_performed,
        "evidence_set_assessment_authority": False,
        "evidence_acquisition_authority": False,
        "evidence_verification_authority": False,
        "evidence_promotion_authority": False,
        "conflict_adjudication_authority": False,
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
        "response_synthesis_authority": False,
        "final_claim_authority": False,
        "human_approval_required": True,
    }


def claim_guardrails(
    *,
    evidence_set_consumed: bool,
    claim_policy_applied: bool,
    conflict_assessed: bool,
    coverage_gates_applied: bool,
) -> dict[str, bool]:
    """Honest performed-state: what was done, and the long list of what was not."""
    return {
        "evidence_set_consumed": evidence_set_consumed,
        "claim_policy_applied": claim_policy_applied,
        "conflict_assessed": conflict_assessed,
        "coverage_gates_applied": coverage_gates_applied,
        "evidence_records_reinterpreted": False,
        "relations_reinterpreted": False,
        "evidence_spans_reinterpreted": False,
        "source_roles_reinterpreted": False,
        "proposition_rewritten": False,
        "semantic_status_upgraded": False,
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
        "majority_vote_computed": False,
        "confidence_computed": False,
        "evidence_weighted": False,
        "conflict_resolved": False,
        "objective_truth_determined": False,
        "final_claim_emitted": False,
        "final_response_synthesized": False,
        "multiple_propositions_combined": False,
        "coverage_receipts_minted": False,
        "current_state_receipts_minted": False,
        "independence_inferred": False,
    }


# ── The assessment ────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ClaimAssessment:
    """What status the assessed evidence justifies for one proposition.

    Read ``assessment_status`` as a statement about *the evidence set*, and read
    ``semantic_basis`` next to it every time.  ``supported_by_assessed_evidence``
    plus ``analyzer_assessed`` says: the admitted records point one way, and the
    reason they point that way is an analyzer's reading that cleared a
    deterministic gate.  It does not say the proposition is true, and no field
    here does.

    No source bytes, no excerpts, no file paths and no spans are copied in.  The
    evidence is referenced by fingerprint; the material stays in EVIDENCE.1 and
    EVIDENCE.2, where it was verified.
    """

    assessment_status: str
    proposition_id: str
    proposition_sha256: str
    proposition_text: str
    proposition_type: str
    proposition_scope: str
    evidence_set_fingerprint: str
    evidence_set_request_fingerprint: str
    request_fingerprint: str
    semantic_basis: str = BASIS_NOT_ESTABLISHED
    assessment_basis: str = ASSESSMENT_BASIS_NOT_ASSESSED
    conflict_status: str = CONFLICT_NOT_ASSESSED
    role_coverage_status: str = COVERAGE_NOT_ASSESSED
    scope_coverage: str = COVERAGE_NOT_ASSESSED
    negative_claim_coverage: str = COVERAGE_NOT_ASSESSED
    current_state_coverage: str = COVERAGE_NOT_ASSESSED
    corroboration_status: str = CORROBORATION_NOT_ASSESSED
    directional_record_refs: tuple[str, ...] = ()
    non_directional_record_refs: tuple[str, ...] = ()
    lineage_group_refs: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    inconsistencies: tuple[str, ...] = ()
    schema_version: str = ASSESSMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.assessment_status not in ASSESSMENT_STATUSES:
            raise ValueError(
                f"unsupported assessment status: {self.assessment_status!r}"
            )
        _bounded_identifier(
            self.proposition_id,
            "assessment proposition_id",
            maximum=MAX_PROPOSITION_ID_LENGTH,
        )
        _require_sha256(self.proposition_sha256, "assessment proposition digest")
        if (
            not isinstance(self.proposition_text, str)
            or not self.proposition_text.strip()
        ):
            raise ValueError("an assessed proposition carries non-empty text")
        if len(self.proposition_text) > MAX_PROPOSITION_CHARS:
            raise ValueError("proposition text exceeds its finite bound")
        if self.proposition_type not in PROPOSITION_TYPES:
            raise ValueError(f"unsupported proposition type: {self.proposition_type!r}")
        if self.proposition_scope not in PROPOSITION_SCOPES:
            raise ValueError(
                f"unsupported proposition scope: {self.proposition_scope!r}"
            )
        for name in (
            "evidence_set_fingerprint",
            "evidence_set_request_fingerprint",
            "request_fingerprint",
        ):
            _require_sha256(getattr(self, name), name.replace("_", " "))
        if self.semantic_basis not in SEMANTIC_BASES:
            raise ValueError(
                "a proposition assessment rests on analyzer-assessed semantic "
                "relations; it is never deterministically verified"
            )
        if self.assessment_basis not in ASSESSMENT_BASES:
            raise ValueError(f"unsupported assessment basis: {self.assessment_basis!r}")
        if self.conflict_status not in CONFLICT_STATUSES:
            raise ValueError(f"unsupported conflict status: {self.conflict_status!r}")
        for name in (
            "role_coverage_status",
            "scope_coverage",
            "negative_claim_coverage",
            "current_state_coverage",
        ):
            if getattr(self, name) not in SET_COVERAGE_STATUSES:
                raise ValueError(f"unsupported {name}: {getattr(self, name)!r}")
        if self.corroboration_status not in CORROBORATION_STATUSES:
            raise ValueError(
                f"unsupported corroboration status: {self.corroboration_status!r}"
            )
        _digest_refs(
            self.directional_record_refs,
            "directional record ref",
            maximum=MAX_CLAIM_RECORD_REFS,
        )
        _digest_refs(
            self.non_directional_record_refs,
            "non-directional record ref",
            maximum=MAX_CLAIM_RECORD_REFS,
        )
        _digest_refs(
            self.lineage_group_refs,
            "lineage group ref",
            maximum=MAX_CLAIM_LINEAGE_REFS,
        )
        if set(self.directional_record_refs) & set(self.non_directional_record_refs):
            raise ValueError("a record is directional or it is not, never both")
        _ordered_vocabulary(
            self.missing_requirements,
            CLAIM_MISSING_REQUIREMENTS,
            "missing requirement",
        )
        _ordered_vocabulary(self.reasons, CLAIM_REASONS, "claim reason")
        _ordered_vocabulary(
            self.inconsistencies, CLAIM_INCONSISTENCIES, "claim inconsistency"
        )

        if self.assessment_status == STATUS_INCONSISTENT_INPUT:
            if not self.inconsistencies:
                raise ValueError("inconsistent input must state its inconsistency")
            if self.conflict_status != CONFLICT_NOT_ASSESSED:
                raise ValueError("an unusable set is not adjudicated")
            if (
                self.directional_record_refs
                or self.non_directional_record_refs
                or self.lineage_group_refs
            ):
                raise ValueError("an unusable set contributes no evidence references")
            if self.semantic_basis != BASIS_NOT_ESTABLISHED:
                raise ValueError("a refused set establishes no semantic basis")
            if self.assessment_basis != ASSESSMENT_BASIS_NOT_ASSESSED:
                raise ValueError("a refused set was not assessed")
            if self.corroboration_status != CORROBORATION_NOT_ASSESSED:
                raise ValueError("a refused set has no corroboration state")
        else:
            if self.inconsistencies:
                raise ValueError("an assessed claim carries no inconsistency")
            if self.conflict_status == CONFLICT_NOT_ASSESSED:
                raise ValueError("an assessed claim states its conflict status")
            if self.semantic_basis != BASIS_ANALYZER_ASSESSED:
                raise ValueError(
                    "every proposition assessment rests on analyzer-assessed "
                    "semantic relations, and aggregation does not change that"
                )
            if self.assessment_basis != ASSESSMENT_BASIS_GATED_ANALYZER_ASSESSMENTS:
                raise ValueError(
                    "an assessed claim was adjudicated over gated analyzer "
                    "assessments"
                )
            if self.corroboration_status == CORROBORATION_NOT_ASSESSED:
                raise ValueError("an assessed claim states its corroboration state")
            if (
                self.assessment_status in DIRECTIONAL_STATUSES
                and not self.directional_record_refs
            ):
                raise ValueError(
                    "a directional assessment names the directional records it "
                    "rests on"
                )
            if (
                self.assessment_status == STATUS_CONFLICTING
                and self.conflict_status != CONFLICT_CONFLICTING
            ):
                raise ValueError("a conflicting claim states a conflicting set")
        if self.schema_version != ASSESSMENT_SCHEMA_VERSION:
            raise ValueError("unsupported claim assessment schema version")

    # -- The answers this phase never gives ----------------------------------

    @property
    def final_claim_authority(self) -> bool:
        """Always false.  A bounded evidence-based assessment is not an answer,
        and this is a property rather than a field so nothing can set it."""
        return False

    @property
    def objective_truth_asserted(self) -> bool:
        """Always false, including for ``supported_by_assessed_evidence``."""
        return False

    @property
    def response_synthesis_performed(self) -> bool:
        return False

    @property
    def claim_assessment_authority(self) -> bool:
        return self.assessment_status != STATUS_INCONSISTENT_INPUT

    @property
    def conflicting(self) -> bool:
        return self.assessment_status == STATUS_CONFLICTING

    @property
    def directional(self) -> bool:
        return self.assessment_status in DIRECTIONAL_STATUSES

    def _identity(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "assessment_status": self.assessment_status,
            "proposition_id": self.proposition_id,
            "proposition_sha256": self.proposition_sha256,
            "proposition_text": self.proposition_text,
            "proposition_type": self.proposition_type,
            "proposition_scope": self.proposition_scope,
            "evidence_set_fingerprint": self.evidence_set_fingerprint,
            "evidence_set_request_fingerprint": self.evidence_set_request_fingerprint,
            "request_fingerprint": self.request_fingerprint,
            "semantic_basis": self.semantic_basis,
            "assessment_basis": self.assessment_basis,
            "conflict_status": self.conflict_status,
            "role_coverage_status": self.role_coverage_status,
            "scope_coverage": self.scope_coverage,
            "negative_claim_coverage": self.negative_claim_coverage,
            "current_state_coverage": self.current_state_coverage,
            "corroboration_status": self.corroboration_status,
            "directional_record_refs": list(self.directional_record_refs),
            "non_directional_record_refs": list(self.non_directional_record_refs),
            "lineage_group_refs": list(self.lineage_group_refs),
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
        payload["claim_assessment_authority"] = self.claim_assessment_authority
        payload["final_claim_authority"] = self.final_claim_authority
        payload["objective_truth_asserted"] = self.objective_truth_asserted
        payload["response_synthesis_performed"] = self.response_synthesis_performed
        payload["semantic_relations_proved_deterministically"] = False
        payload["evidence_relations_reinterpreted"] = False
        payload["proposition_rewritten"] = False
        payload["source_content_read"] = False
        payload["authority"] = claim_authority(
            assessment_performed=self.claim_assessment_authority,
        )
        payload["guardrails"] = claim_guardrails(
            evidence_set_consumed=True,
            claim_policy_applied=self.claim_assessment_authority,
            conflict_assessed=self.claim_assessment_authority,
            coverage_gates_applied=self.claim_assessment_authority,
        )
        return payload


def render_claim_assessment_json(assessment: ClaimAssessment) -> str:
    if not isinstance(assessment, ClaimAssessment):
        raise TypeError("render_claim_assessment_json requires a ClaimAssessment")
    return json.dumps(
        assessment.as_dict(), indent=2, ensure_ascii=False, sort_keys=False
    )


# ── Corroboration ─────────────────────────────────────────────────────────────

def _corroboration_status(
    assessment: EvidenceSetAssessment,
    directional_refs: tuple[str, ...],
) -> str:
    """Describe the lineage shape behind the directional evidence.

    Nothing here is a quantity.  The two tests are structural — *is there more
    than one lineage*, *is the single lineage a duplicate group* — and are
    written with tuple slicing rather than arithmetic, so there is no number to
    compare against another number.
    """
    if not directional_refs:
        return CORROBORATION_NONE
    refs = set(directional_refs)
    states: dict[str, str] = {}
    for member in assessment.members:
        if member.record_fingerprint in refs:
            states[member.lineage_group_id] = member.independence_state
    if not states:  # pragma: no cover - defensive; refs come from the members
        return CORROBORATION_NONE
    lineages = tuple(sorted(states))
    independent = tuple(
        item for item in lineages if states[item] == INDEPENDENCE_INDEPENDENT
    )
    if independent[1:]:
        return CORROBORATION_INDEPENDENT
    if not lineages[1:] and states[lineages[0]] == INDEPENDENCE_DUPLICATE:
        return CORROBORATION_DUPLICATE_ONLY
    return CORROBORATION_INDEPENDENCE_UNKNOWN


# ── The entry point ───────────────────────────────────────────────────────────

def assess_claim(request: ClaimAssessmentRequest) -> ClaimAssessment:
    """Assess one proposition against one already-assessed evidence set.

    Admission before adjudication, because adjudicating a set that cannot be
    trusted to say what it contains produces a confident status over nothing.
    Every fatal problem is collected rather than raised, so a caller gets the
    whole list at once, and none of them is repaired here.
    """
    if not isinstance(request, ClaimAssessmentRequest):
        raise TypeError("assess_claim requires a ClaimAssessmentRequest")

    proposition = request.proposition
    evidence_set = request.evidence_set
    fingerprint = claim_request_fingerprint(request)
    inconsistencies: set[str] = set()

    # 1 ── a set that refused itself is never adjudicated into a claim.
    assessed = evidence_set.set_status == SET_ASSESSED
    if not assessed:
        inconsistencies.add(INCONSISTENT_EVIDENCE_SET)

    # 2 ── the supplied claim is the claim the set was assessed over, exactly.
    #      A reworded, narrowed, broadened or requalified proposition hashes
    #      differently and is a different claim needing a different evidence path.
    if (
        proposition.proposition_id != evidence_set.proposition_id
        or proposition.proposition_sha256 != evidence_set.proposition_sha256
        or proposition.proposition_type != evidence_set.proposition_type
        or proposition.scope != evidence_set.proposition_scope
    ):
        inconsistencies.add(INCONSISTENT_PROPOSITION_BINDING)

    # 3 ── the caller's own tamper binding, when one was supplied.
    set_fingerprint = evidence_set.assessment_fingerprint
    expected = request.expected_evidence_set_fingerprint
    if expected is not None and expected != set_fingerprint:
        inconsistencies.add(INCONSISTENT_SET_FINGERPRINT)
    if not _is_sha256(set_fingerprint) or not _is_sha256(
        evidence_set.request_fingerprint
    ):  # pragma: no cover - defensive; upstream construction enforces both
        inconsistencies.add(INCONSISTENT_SET_FINGERPRINT)

    # 4 ── member identities, checked rather than assumed.
    members = evidence_set.members
    seen: set[str] = set()
    for member in members:
        digest = member.record_fingerprint
        if not _is_sha256(digest) or digest in seen:
            inconsistencies.add(INCONSISTENT_MEMBER_FINGERPRINT)
        seen.add(digest)

    # 5 ── the relation partition is recomputed from the members themselves, so
    #      a summary that disagrees with the records it summarises is refused
    #      rather than trusted.  CLAIM.1 reads relations; it never assigns one.
    if (
        _partition_for(members, RELATION_SUPPORTS) != evidence_set.support_records
        or _partition_for(members, RELATION_CONTRADICTS)
        != evidence_set.contradiction_records
        or _partition_for(members, RELATION_INSUFFICIENT)
        != evidence_set.insufficient_records
        or _partition_for(members, RELATION_UNRELATED) != evidence_set.unrelated_records
    ):
        inconsistencies.add(INCONSISTENT_RELATION_PARTITION)

    # 6 ── every member belongs to the lineage group it names, in the state that
    #      group reports.  Duplication and independence are consumed facts, and a
    #      set whose members disagree with its own grouping cannot be read.
    independence = evidence_set.independence
    if assessed and independence is None:  # pragma: no cover - defensive
        inconsistencies.add(INCONSISTENT_LINEAGE_MEMBERSHIP)
    elif independence is not None:
        group_state = {
            group.lineage_group_id: group.independence_state
            for group in independence.lineage_groups
        }
        group_records = {
            group.lineage_group_id: set(group.record_fingerprints)
            for group in independence.lineage_groups
        }
        for member in members:
            identifier = member.lineage_group_id
            if identifier not in group_state:
                inconsistencies.add(INCONSISTENT_LINEAGE_MEMBERSHIP)
                continue
            if (
                member.record_fingerprint not in group_records[identifier]
                or member.independence_state != group_state[identifier]
            ):
                inconsistencies.add(INCONSISTENT_LINEAGE_MEMBERSHIP)

    # 7 ── the semantic basis arrived analyzer-assessed and must still be.
    levels = evidence_set.verification_levels
    if assessed and (
        levels is None or levels.semantic_relation != BASIS_ANALYZER_ASSESSED
    ):
        inconsistencies.add(INCONSISTENT_SEMANTIC_BASIS_UPGRADED)
    for member in members:
        if member.semantic_relation_status != BASIS_ANALYZER_ASSESSED:
            inconsistencies.add(INCONSISTENT_SEMANTIC_BASIS_UPGRADED)

    # 8 ── an upstream that already decided the claim, or that interpreted
    #      anything on the way, is not a set CLAIM.1 may adjudicate.
    inconsistencies |= _upstream_declaration_defects(evidence_set)

    # 9 ── supplied requirements describe this proposition and these roles.
    requirements = request.requirements
    if requirements is not None and (
        requirements.proposition_id != proposition.proposition_id
        or requirements.proposition_sha256 != proposition.proposition_sha256
        or requirements.required_roles != _required_roles(evidence_set)
    ):
        inconsistencies.add(INCONSISTENT_REQUIREMENT_BINDING)

    if inconsistencies:
        return ClaimAssessment(
            assessment_status=STATUS_INCONSISTENT_INPUT,
            proposition_id=proposition.proposition_id,
            proposition_sha256=proposition.proposition_sha256,
            proposition_text=proposition.text,
            proposition_type=proposition.proposition_type,
            proposition_scope=proposition.scope,
            evidence_set_fingerprint=set_fingerprint,
            evidence_set_request_fingerprint=evidence_set.request_fingerprint,
            request_fingerprint=fingerprint,
            reasons=_ordered_reasons(
                {
                    CLAIM_INPUT_REJECTED,
                    CLAIM_RELATIONS_NOT_REINTERPRETED,
                    CLAIM_PROPOSITION_NOT_REWRITTEN,
                    CLAIM_NO_MAJORITY_COMPUTED,
                    CLAIM_NO_CONFIDENCE_COMPUTED,
                    CLAIM_NO_OBJECTIVE_TRUTH_DETERMINED,
                    CLAIM_NO_FINAL_RESPONSE_SYNTHESIZED,
                }
            ),
            inconsistencies=_ordered_inconsistencies(inconsistencies),
        )

    return _adjudicate(
        request,
        fingerprint=fingerprint,
        set_fingerprint=set_fingerprint,
    )


def _partition_for(members: tuple[Any, ...], relation: str) -> tuple[str, ...]:
    return tuple(
        sorted(item.record_fingerprint for item in members if item.relation == relation)
    )


def _required_roles(assessment: EvidenceSetAssessment) -> tuple[str, ...]:
    """Which roles the *set* was told to require, in canonical role order."""
    required = {item.role for item in assessment.role_coverage if item.required}
    return tuple(item for item in EVIDENCE_ROLES if item in required)


def _upstream_declaration_defects(assessment: EvidenceSetAssessment) -> set[str]:
    """Read the set's own declaration of what it did, and refuse a liar.

    EVIDENCE.2 serialises ``claim_decision_authority``, ``final_claim_authority``
    and a guardrail block stating that it reinterpreted nothing, weighed nothing
    and called no model.  Those are exactly the properties CLAIM.1 depends on, so
    it checks them rather than assuming them.  A set arriving with claim-decision
    authority already asserted is not an input; it is a phase that overstepped,
    and adjudicating its output would launder that overstep into a claim.
    """
    defects: set[str] = set()
    payload = assessment.as_dict()
    authority = payload.get("authority") or {}
    guardrails = payload.get("guardrails") or {}
    if (
        payload.get("claim_decision_authority")
        or payload.get("final_claim_authority")
        or payload.get("claim_decided")
        or authority.get("claim_decision_authority")
        or authority.get("final_claim_authority")
        or guardrails.get("claim_decision_performed")
        or guardrails.get("final_claim_emitted")
    ):
        defects.add(INCONSISTENT_UPSTREAM_CLAIM_AUTHORITY)
    if guardrails.get("semantic_status_upgraded"):
        defects.add(INCONSISTENT_SEMANTIC_BASIS_UPGRADED)
    if (
        guardrails.get("relations_reinterpreted")
        or guardrails.get("model_called")
        or guardrails.get("confidence_computed")
        or guardrails.get("majority_vote_computed")
        or guardrails.get("source_content_read")
        or guardrails.get("coverage_receipts_minted")
        or guardrails.get("current_state_receipts_minted")
        or guardrails.get("lineage_inferred_from_paths")
    ):
        defects.add(INCONSISTENT_UPSTREAM_GUARDRAIL)
    return defects


def _adjudicate(
    request: ClaimAssessmentRequest,
    *,
    fingerprint: str,
    set_fingerprint: str,
) -> ClaimAssessment:
    """Apply the deterministic rule table.  Called only after admission passed."""
    proposition = request.proposition
    evidence_set = request.evidence_set
    requirements = request.requirements

    negative = proposition.proposition_type == PROPOSITION_NEGATIVE_EXISTENTIAL
    needs_current_state = proposition.scope in SCOPES_REQUIRING_CURRENT_STATE
    conflict = evidence_set.conflict_status

    directional_refs = tuple(
        sorted(
            set(evidence_set.support_records) | set(evidence_set.contradiction_records)
        )
    )
    non_directional_refs = tuple(
        sorted(
            set(evidence_set.insufficient_records) | set(evidence_set.unrelated_records)
        )
    )
    corroboration = _corroboration_status(evidence_set, directional_refs)
    directional = set(directional_refs)
    lineage_refs = tuple(
        sorted(
            {
                member.lineage_group_id
                for member in evidence_set.members
                if member.record_fingerprint in directional
            }
        )
    )

    reasons: set[str] = {
        CLAIM_PROPOSITION_BINDING_VERIFIED,
        CLAIM_EVIDENCE_SET_BINDING_VERIFIED,
        CLAIM_SET_PARTITION_REDERIVED,
        CLAIM_SEMANTIC_BASIS_PRESERVED,
        CLAIM_RELATIONS_NOT_REINTERPRETED,
        CLAIM_PROPOSITION_NOT_REWRITTEN,
        CLAIM_NO_MAJORITY_COMPUTED,
        CLAIM_NO_CONFIDENCE_COMPUTED,
        CLAIM_NO_OBJECTIVE_TRUTH_DETERMINED,
        CLAIM_NO_FINAL_RESPONSE_SYNTHESIZED,
    }
    if corroboration == CORROBORATION_DUPLICATE_ONLY:
        reasons.add(CLAIM_DUPLICATE_LINEAGE_DOES_NOT_STRENGTHEN)

    # -- the rule table, in precedence order ---------------------------------
    if conflict == CONFLICT_CONFLICTING:
        # Terminal.  No count, no role rank, no recency, no source quantity, no
        # winner.  Adjudication is a human question and is out of scope here.
        status = STATUS_CONFLICTING
        reasons.add(CLAIM_CONFLICTING_EVIDENCE)
        reasons.add(CLAIM_CONFLICT_NOT_ADJUDICATED)
    elif conflict == CONFLICT_CONTRADICTION_ONLY:
        # EVIDENCE.1 already decided each of these was a competent,
        # proposition-bound contradiction.  Recording one needs no
        # repository-wide coverage, and CLAIM.1 does not reinterpret it.
        status = STATUS_CONTRADICTED
        reasons.add(CLAIM_CONTRADICTED_DIRECTIONAL_EVIDENCE)
    elif conflict == CONFLICT_SUPPORT_ONLY:
        status, gate_reasons = _support_gates(
            evidence_set,
            negative=negative,
            needs_current_state=needs_current_state,
            requirements=requirements,
            corroboration=corroboration,
        )
        reasons |= gate_reasons
    else:
        # Absence of support is not contradiction, and never becomes one.
        status = STATUS_INSUFFICIENT
        reasons.add(CLAIM_INSUFFICIENT_DIRECTIONAL_EVIDENCE)
        reasons.add(CLAIM_NO_DIRECTIONAL_EVIDENCE)

    missing = _missing_requirements(
        evidence_set,
        conflict=conflict,
        negative=negative,
        needs_current_state=needs_current_state,
        corroboration=corroboration,
        directional_present=bool(directional_refs),
    )

    return ClaimAssessment(
        assessment_status=status,
        proposition_id=proposition.proposition_id,
        proposition_sha256=proposition.proposition_sha256,
        proposition_text=proposition.text,
        proposition_type=proposition.proposition_type,
        proposition_scope=proposition.scope,
        evidence_set_fingerprint=set_fingerprint,
        evidence_set_request_fingerprint=evidence_set.request_fingerprint,
        request_fingerprint=fingerprint,
        semantic_basis=BASIS_ANALYZER_ASSESSED,
        assessment_basis=ASSESSMENT_BASIS_GATED_ANALYZER_ASSESSMENTS,
        conflict_status=conflict,
        role_coverage_status=evidence_set.role_coverage_status,
        scope_coverage=evidence_set.scope_coverage,
        negative_claim_coverage=evidence_set.negative_claim_coverage,
        current_state_coverage=evidence_set.current_state_coverage,
        corroboration_status=corroboration,
        directional_record_refs=directional_refs,
        non_directional_record_refs=non_directional_refs,
        lineage_group_refs=lineage_refs,
        missing_requirements=missing,
        reasons=_ordered_reasons(reasons),
    )


def _support_gates(
    evidence_set: EvidenceSetAssessment,
    *,
    negative: bool,
    needs_current_state: bool,
    requirements: ClaimRequirements | None,
    corroboration: str,
) -> tuple[str, set[str]]:
    """The gates a support-only set passes before it reads as support.

    Order matters and is fixed: absence coverage, then currentness, then role
    coverage, then scope competence, then any explicitly demanded independent
    corroboration.  Each gate names something the set does *not* contain, so a
    set failing two of them reports the first — the earlier gap is the one that
    has to be closed first, and stacking them would suggest a
    distance-to-truth this phase does not measure.
    """
    reasons: set[str] = set()

    if negative and evidence_set.negative_claim_coverage != COVERAGE_COMPLETE:
        # No number of support records substitutes for a coverage receipt, and
        # coverage cannot be repaired by counting files.
        reasons.add(CLAIM_NEGATIVE_COVERAGE_REQUIRED)
        if evidence_set.negative_claim_coverage == COVERAGE_INCONSISTENT:
            reasons.add(CLAIM_NEGATIVE_COVERAGE_INCONSISTENT)
        return STATUS_COVERAGE_INCOMPLETE, reasons

    if needs_current_state:
        if evidence_set.current_state_coverage == COVERAGE_INCONSISTENT:
            # "It is deployed" and "it is not" are not two pieces of partial
            # coverage, and averaging them is not available here.
            reasons.add(CLAIM_CURRENT_STATE_COVERAGE_INCONSISTENT)
            return STATUS_CURRENT_STATE_INCONSISTENT, reasons
        if evidence_set.current_state_coverage != COVERAGE_COMPLETE:
            # Static implementation content never becomes runtime truth here.
            reasons.add(CLAIM_CURRENT_STATE_UNESTABLISHED)
            return STATUS_CURRENT_STATE_UNESTABLISHED, reasons

    if evidence_set.role_coverage_status not in {
        COVERAGE_COMPLETE,
        COVERAGE_NOT_APPLICABLE,
    }:
        # Supplied requirements, unmet.  Nothing is invented where none were
        # supplied: ``not_applicable`` passes and is recorded as a gap instead.
        reasons.add(CLAIM_REQUIRED_ROLE_COVERAGE_INCOMPLETE)
        reasons.add(CLAIM_INSUFFICIENT_DIRECTIONAL_EVIDENCE)
        return STATUS_INSUFFICIENT, reasons

    if evidence_set.scope_coverage != COVERAGE_COMPLETE:
        reasons.add(CLAIM_SCOPE_COMPETENT_ROLE_ABSENT)
        reasons.add(CLAIM_INSUFFICIENT_DIRECTIONAL_EVIDENCE)
        return STATUS_INSUFFICIENT, reasons

    if (
        requirements is not None
        and requirements.independent_corroboration_required
        and corroboration != CORROBORATION_INDEPENDENT
    ):
        reasons.add(CLAIM_INDEPENDENT_CORROBORATION_REQUIRED)
        reasons.add(CLAIM_INDEPENDENT_CORROBORATION_UNESTABLISHED)
        reasons.add(CLAIM_INSUFFICIENT_DIRECTIONAL_EVIDENCE)
        return STATUS_INSUFFICIENT, reasons

    reasons.add(CLAIM_SUPPORTED_DIRECTIONAL_EVIDENCE)
    return STATUS_SUPPORTED, reasons


def _missing_requirements(
    evidence_set: EvidenceSetAssessment,
    *,
    conflict: str,
    negative: bool,
    needs_current_state: bool,
    corroboration: str,
    directional_present: bool,
) -> tuple[str, ...]:
    """What the set does not contain, stated whatever status was reached.

    A supported claim still reports its gaps.  That is the point: a human
    reviewer needs to see that independence was never established even when the
    evidence pointed one way, because the alternative is a positive status that
    reads as more settled than it is.
    """
    missing: set[str] = set()
    if evidence_set.role_coverage_status == COVERAGE_NOT_APPLICABLE:
        missing.add(MISSING_ROLE_REQUIREMENTS_NOT_SUPPLIED)
    elif evidence_set.role_coverage_status != COVERAGE_COMPLETE:
        missing.add(MISSING_REQUIRED_ROLE)
    if evidence_set.scope_coverage != COVERAGE_COMPLETE:
        missing.add(MISSING_SCOPE_COMPETENT_ROLE)
    if conflict == CONFLICT_NO_DIRECTIONAL_EVIDENCE:
        missing.add(MISSING_DIRECTIONAL_EVIDENCE)
    if negative and evidence_set.negative_claim_coverage != COVERAGE_COMPLETE:
        missing.add(MISSING_NEGATIVE_CLAIM_COVERAGE)
    if needs_current_state and evidence_set.current_state_coverage != COVERAGE_COMPLETE:
        missing.add(MISSING_CURRENT_STATE_COVERAGE)
    if directional_present and corroboration != CORROBORATION_INDEPENDENT:
        missing.add(MISSING_INDEPENDENT_CORROBORATION)
    if conflict == CONFLICT_CONFLICTING:
        missing.add(MISSING_CONFLICT_ADJUDICATION)
    return _ordered_missing(missing)


__all__ = [
    "ASSESSMENT_BASES",
    "ASSESSMENT_BASIS_GATED_ANALYZER_ASSESSMENTS",
    "ASSESSMENT_BASIS_NOT_ASSESSED",
    "ASSESSMENT_SCHEMA_VERSION",
    "ASSESSMENT_STATUSES",
    "BASIS_ANALYZER_ASSESSED",
    "BASIS_NOT_ESTABLISHED",
    "CLAIM_CONFLICTING_EVIDENCE",
    "CLAIM_CONFLICT_NOT_ADJUDICATED",
    "CLAIM_CONTRADICTED_DIRECTIONAL_EVIDENCE",
    "CLAIM_CURRENT_STATE_COVERAGE_INCONSISTENT",
    "CLAIM_CURRENT_STATE_UNESTABLISHED",
    "CLAIM_DUPLICATE_LINEAGE_DOES_NOT_STRENGTHEN",
    "CLAIM_EVIDENCE_SET_BINDING_VERIFIED",
    "CLAIM_INCONSISTENCIES",
    "CLAIM_INDEPENDENT_CORROBORATION_REQUIRED",
    "CLAIM_INDEPENDENT_CORROBORATION_UNESTABLISHED",
    "CLAIM_INPUT_REJECTED",
    "CLAIM_INSUFFICIENT_DIRECTIONAL_EVIDENCE",
    "CLAIM_MISSING_REQUIREMENTS",
    "CLAIM_NEGATIVE_COVERAGE_INCONSISTENT",
    "CLAIM_NEGATIVE_COVERAGE_REQUIRED",
    "CLAIM_NO_CONFIDENCE_COMPUTED",
    "CLAIM_NO_DIRECTIONAL_EVIDENCE",
    "CLAIM_NO_FINAL_RESPONSE_SYNTHESIZED",
    "CLAIM_NO_MAJORITY_COMPUTED",
    "CLAIM_NO_OBJECTIVE_TRUTH_DETERMINED",
    "CLAIM_PROPOSITION_BINDING_VERIFIED",
    "CLAIM_PROPOSITION_NOT_REWRITTEN",
    "CLAIM_REASONS",
    "CLAIM_RELATIONS_NOT_REINTERPRETED",
    "CLAIM_REQUIRED_ROLE_COVERAGE_INCOMPLETE",
    "CLAIM_SCOPE_COMPETENT_ROLE_ABSENT",
    "CLAIM_SEMANTIC_BASIS_PRESERVED",
    "CLAIM_SET_PARTITION_REDERIVED",
    "CLAIM_SUPPORTED_DIRECTIONAL_EVIDENCE",
    "CORROBORATION_DUPLICATE_ONLY",
    "CORROBORATION_INDEPENDENCE_UNKNOWN",
    "CORROBORATION_INDEPENDENT",
    "CORROBORATION_NONE",
    "CORROBORATION_NOT_ASSESSED",
    "CORROBORATION_STATUSES",
    "DIRECTIONAL_STATUSES",
    "INCONSISTENT_EVIDENCE_SET",
    "INCONSISTENT_LINEAGE_MEMBERSHIP",
    "INCONSISTENT_MEMBER_FINGERPRINT",
    "INCONSISTENT_PROPOSITION_BINDING",
    "INCONSISTENT_RELATION_PARTITION",
    "INCONSISTENT_REQUIREMENT_BINDING",
    "INCONSISTENT_SEMANTIC_BASIS_UPGRADED",
    "INCONSISTENT_SET_FINGERPRINT",
    "INCONSISTENT_UPSTREAM_CLAIM_AUTHORITY",
    "INCONSISTENT_UPSTREAM_GUARDRAIL",
    "MAX_CLAIM_LINEAGE_REFS",
    "MAX_CLAIM_RECORD_REFS",
    "MISSING_CONFLICT_ADJUDICATION",
    "MISSING_CURRENT_STATE_COVERAGE",
    "MISSING_DIRECTIONAL_EVIDENCE",
    "MISSING_INDEPENDENT_CORROBORATION",
    "MISSING_NEGATIVE_CLAIM_COVERAGE",
    "MISSING_REQUIRED_ROLE",
    "MISSING_ROLE_REQUIREMENTS_NOT_SUPPLIED",
    "MISSING_SCOPE_COMPETENT_ROLE",
    "PHASE_ID",
    "SEMANTIC_BASES",
    "STATUS_CONFLICTING",
    "STATUS_CONTRADICTED",
    "STATUS_COVERAGE_INCOMPLETE",
    "STATUS_CURRENT_STATE_INCONSISTENT",
    "STATUS_CURRENT_STATE_UNESTABLISHED",
    "STATUS_INCONSISTENT_INPUT",
    "STATUS_INSUFFICIENT",
    "STATUS_SUPPORTED",
    "ClaimAssessment",
    "ClaimAssessmentRequest",
    "ClaimRequirements",
    "assess_claim",
    "claim_authority",
    "claim_guardrails",
    "claim_request_fingerprint",
    "claim_requirements_fingerprint",
    "render_claim_assessment_json",
]
