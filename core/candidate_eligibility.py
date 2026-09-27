"""ACQUIRE.2 — the Candidate Eligibility Receipt and its bounded vocabularies.

ACQUIRE.1 wrote the shopping list.  ACQUIRE.2 answers the next question and only
that one:

    given an authorized inventory, which concrete candidates are *eligible* to
    be considered by the selector machinery that already exists?

It never answers "read these", and it never answers "these prove it".

    AcquisitionRequestContract + CandidateInventory
        -> CandidateEligibilityReceipt

One distinction carries this whole phase, and every record here exists to keep
it:

    a **candidate** may satisfy an acquisition request
    **evidence** has been acquired and can support a claim

ACQUIRE.2 outputs candidates.  Never evidence.  ``content_read`` is false on
every candidate in every status, ``evidence_status`` is ``not_acquired``, and
the role a candidate is eligible for is an *expectation* — nothing has been
opened, so nothing has been verified.

Three further properties make the record worth having.

**Membership is the only door.**  A candidate exists because the supplied
snapshot says it exists.  A path that merely looks valid, a path the user typed
that the inventory does not contain, a path from a different repository: none of
them enter, and none of them is invented.

**A class is assigned only when something justifies it.**  Every assignment
records the basis it came from.  ``.py`` does not mean implementation authority
and ``.md`` does not mean architecture authority; where nothing justifies a
class, the answer is ``unknown``, and unknown never satisfies a required role.

**Exclusions win.**  A class ACQUIRE.1 excluded cannot enter the active pool,
and no downstream score can readmit it.  Deferred material stays deferred.

The module is stdlib-only and pure.  It reads no files, walks no directory,
contacts no service, calls no language system, executes no selector, acquires no
evidence, and grants no authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.acquisition_request import (
    ACQUISITION_SOURCE_CLASSES,
    NEVER_REQUESTED_SOURCE_CLASSES,
    REQUESTABLE_SOURCE_CLASSES,
    FRESHNESS_REQUIREMENTS,
)
from core.evidence_requirements import (
    ACTIVE_TIERS,
    EVIDENCE_DOMAINS,
    EVIDENCE_ROLES,
    EVIDENCE_SCOPES,
    EVIDENCE_TIERS,
    TIER_DEFERRED,
    TIER_REQUIRED_PRIMARY,
    TIER_REQUIRED_SECONDARY,
)
from core.execution_waiter import WORKFLOW_TARGETS


PHASE_ID = "ACQUIRE.2"
CANDIDATE_RECEIPT_SCHEMA_VERSION = "acquire_2_candidate_eligibility_receipt_v1"

# ── Classification basis ──────────────────────────────────────────────────────
#: *Why* a source class was assigned.  A bounded vocabulary of facts already
#: established somewhere else, never a sentence of reasoning invented here.
BASIS_EXPLICIT_TARGET_ANCHOR = "explicit_target_anchor"
BASIS_INVENTORY_DECLARED_CLASS = "inventory_declared_class"
BASIS_INVENTORY_PARSER_SUPPORT = "inventory_parser_support"
BASIS_INVENTORY_GENERATED_MARKER = "inventory_generated_marker"
BASIS_INVENTORY_VENDOR_MARKER = "inventory_vendor_marker"
BASIS_INVENTORY_DUPLICATE_MARKER = "inventory_duplicate_marker"
BASIS_INVENTORY_HARD_EXCLUSION = "inventory_hard_exclusion"
BASIS_KNOWN_TEST_LOCATION = "known_test_location"
BASIS_KNOWN_MANIFEST_NAME = "known_manifest_name"
BASIS_KNOWN_CONFIGURATION_NAME = "known_configuration_name"
BASIS_KNOWN_SNAPSHOT_LOCATION = "known_snapshot_location"
BASIS_KNOWN_TEMPORARY_LOCATION = "known_temporary_location"
BASIS_KNOWN_HISTORICAL_LOCATION = "known_historical_location"

CLASSIFICATION_BASES: tuple[str, ...] = (
    BASIS_EXPLICIT_TARGET_ANCHOR,
    BASIS_INVENTORY_DECLARED_CLASS,
    BASIS_INVENTORY_PARSER_SUPPORT,
    BASIS_INVENTORY_GENERATED_MARKER,
    BASIS_INVENTORY_VENDOR_MARKER,
    BASIS_INVENTORY_DUPLICATE_MARKER,
    BASIS_INVENTORY_HARD_EXCLUSION,
    BASIS_KNOWN_TEST_LOCATION,
    BASIS_KNOWN_MANIFEST_NAME,
    BASIS_KNOWN_CONFIGURATION_NAME,
    BASIS_KNOWN_SNAPSHOT_LOCATION,
    BASIS_KNOWN_TEMPORARY_LOCATION,
    BASIS_KNOWN_HISTORICAL_LOCATION,
)

# ── Classification status ─────────────────────────────────────────────────────
#: A member whose kind nothing justifies is ``unknown``, and unknown is a safe
#: first-class answer rather than a failure.  It simply cannot discharge a
#: required role.
CLASSIFICATION_CLASSIFIED = "classified"
CLASSIFICATION_UNKNOWN = "unknown"

CLASSIFICATION_STATUSES: tuple[str, ...] = (
    CLASSIFICATION_CLASSIFIED,
    CLASSIFICATION_UNKNOWN,
)

# ── Epistemic status ──────────────────────────────────────────────────────────
#: The whole point of the phase, written into every candidate.
EVIDENCE_STATUS_NOT_ACQUIRED = "not_acquired"
#: A role a candidate *may* be able to satisfy once somebody reads it.  Not a
#: verdict.  There is deliberately no ``verified`` value in this vocabulary,
#: because ACQUIRE.2 has no way to reach one.
AUTHORITY_EXPECTED_NOT_VERIFIED = "expected_not_verified"

# ── Ineligibility reasons ─────────────────────────────────────────────────────
INELIGIBLE_NOT_IN_INVENTORY = "not_in_inventory"
INELIGIBLE_SOURCE_CLASS_NOT_REQUESTED = "source_class_not_requested"
INELIGIBLE_SOURCE_CLASS_EXCLUDED = "source_class_excluded"
INELIGIBLE_CLASSIFICATION_UNKNOWN = "classification_unknown"
INELIGIBLE_HARD_EXCLUDED_BY_INVENTORY = "hard_excluded_by_inventory"
INELIGIBLE_OUTSIDE_REPOSITORY = "outside_repository"
INELIGIBLE_PER_SOURCE_BYTES_EXCEEDED = "per_source_bytes_exceeded"
INELIGIBLE_TOTAL_BYTES_EXHAUSTED = "total_bytes_exhausted"
INELIGIBLE_SIZE_UNKNOWN = "size_unverifiable"
INELIGIBLE_CANDIDATE_CEILING_REACHED = "candidate_ceiling_reached"

#: Ordered most specific first, because a member evaluated against several
#: requests collects several reasons and the receipt reports one.  "This class
#: was excluded" says more than "this request did not ask for this class", and
#: "nobody recorded its size" says more than either — so the weakest statement,
#: ``source_class_not_requested``, sits last and only wins when nothing else
#: applies.
INELIGIBILITY_REASONS: tuple[str, ...] = (
    INELIGIBLE_NOT_IN_INVENTORY,
    INELIGIBLE_OUTSIDE_REPOSITORY,
    INELIGIBLE_HARD_EXCLUDED_BY_INVENTORY,
    INELIGIBLE_SOURCE_CLASS_EXCLUDED,
    INELIGIBLE_CLASSIFICATION_UNKNOWN,
    INELIGIBLE_PER_SOURCE_BYTES_EXCEEDED,
    INELIGIBLE_SIZE_UNKNOWN,
    INELIGIBLE_TOTAL_BYTES_EXHAUSTED,
    INELIGIBLE_CANDIDATE_CEILING_REACHED,
    INELIGIBLE_SOURCE_CLASS_NOT_REQUESTED,
)

# ── Candidate reason codes ────────────────────────────────────────────────────
CANDIDATE_INVENTORY_MEMBER = "CANDIDATE_INVENTORY_MEMBER"
CANDIDATE_EXPLICIT_TARGET_MATCHED = "CANDIDATE_EXPLICIT_TARGET_MATCHED"
CANDIDATE_SUPPLIED_CONTEXT_REFERENCE = "CANDIDATE_SUPPLIED_CONTEXT_REFERENCE"
CANDIDATE_TIER_PRESERVED = "CANDIDATE_TIER_PRESERVED"
CANDIDATE_DEFERRED_UPSTREAM = "CANDIDATE_DEFERRED_UPSTREAM"

CANDIDATE_REASONS: tuple[str, ...] = (
    CANDIDATE_INVENTORY_MEMBER,
    CANDIDATE_EXPLICIT_TARGET_MATCHED,
    CANDIDATE_SUPPLIED_CONTEXT_REFERENCE,
    CANDIDATE_TIER_PRESERVED,
    CANDIDATE_DEFERRED_UPSTREAM,
)

# ── Receipt reason codes ──────────────────────────────────────────────────────
ELIGIBILITY_CANDIDATES_BOUNDED = "ELIGIBILITY_CANDIDATES_BOUNDED"
ELIGIBILITY_EXCLUSIONS_ENFORCED = "ELIGIBILITY_EXCLUSIONS_ENFORCED"
ELIGIBILITY_DEFERRED_KEPT_SEPARATE = "ELIGIBILITY_DEFERRED_KEPT_SEPARATE"
ELIGIBILITY_DIRECT_CONTEXT_REFERENCED = "ELIGIBILITY_DIRECT_CONTEXT_REFERENCED"
ELIGIBILITY_EXTERNAL_ENVELOPE_ONLY = "ELIGIBILITY_EXTERNAL_ENVELOPE_ONLY"
ELIGIBILITY_TARGET_ANCHOR_MATCHED = "ELIGIBILITY_TARGET_ANCHOR_MATCHED"
ELIGIBILITY_TARGET_ANCHOR_UNMATCHED = "ELIGIBILITY_TARGET_ANCHOR_UNMATCHED"
ELIGIBILITY_REQUIRED_ROLE_UNSATISFIED = "ELIGIBILITY_REQUIRED_ROLE_UNSATISFIED"
ELIGIBILITY_ACQUISITION_NOT_READY = "ELIGIBILITY_ACQUISITION_NOT_READY"
ELIGIBILITY_INVENTORY_REQUIRED = "ELIGIBILITY_INVENTORY_REQUIRED"
ELIGIBILITY_SOURCE_INTEGRITY_FAILED = "ELIGIBILITY_SOURCE_INTEGRITY_FAILED"
ELIGIBILITY_INVENTORY_IDENTITY_MISMATCH = "ELIGIBILITY_INVENTORY_IDENTITY_MISMATCH"
ELIGIBILITY_ENVELOPE_WIDENED = "ELIGIBILITY_ENVELOPE_WIDENED"

ELIGIBILITY_REASONS: tuple[str, ...] = (
    ELIGIBILITY_CANDIDATES_BOUNDED,
    ELIGIBILITY_EXCLUSIONS_ENFORCED,
    ELIGIBILITY_DEFERRED_KEPT_SEPARATE,
    ELIGIBILITY_DIRECT_CONTEXT_REFERENCED,
    ELIGIBILITY_EXTERNAL_ENVELOPE_ONLY,
    ELIGIBILITY_TARGET_ANCHOR_MATCHED,
    ELIGIBILITY_TARGET_ANCHOR_UNMATCHED,
    ELIGIBILITY_REQUIRED_ROLE_UNSATISFIED,
    ELIGIBILITY_ACQUISITION_NOT_READY,
    ELIGIBILITY_INVENTORY_REQUIRED,
    ELIGIBILITY_SOURCE_INTEGRITY_FAILED,
    ELIGIBILITY_INVENTORY_IDENTITY_MISMATCH,
    ELIGIBILITY_ENVELOPE_WIDENED,
)

ELIGIBILITY_REASON_DESCRIPTIONS: dict[str, str] = {
    ELIGIBILITY_CANDIDATES_BOUNDED: (
        "The candidate pool was narrowed deterministically to the ceiling the "
        "acquisition request set. Nothing beyond it is offered for consideration."
    ),
    ELIGIBILITY_EXCLUSIONS_ENFORCED: (
        "Source classes the acquisition request excluded were filtered out of the "
        "active pool, and no later score can readmit them."
    ),
    ELIGIBILITY_DEFERRED_KEPT_SEPARATE: (
        "Deferred material is listed in its own pool with no acquisition budget. It "
        "is on the record and out of the initial work."
    ),
    ELIGIBILITY_DIRECT_CONTEXT_REFERENCED: (
        "The order carries its own material. The candidate is a reference to what "
        "INPUT preserved, by fingerprint, with no content copied."
    ),
    ELIGIBILITY_EXTERNAL_ENVELOPE_ONLY: (
        "External information needs a network-enabled phase to discover anything at "
        "all, so ACQUIRE.2 states the envelope and finds no concrete candidate."
    ),
    ELIGIBILITY_TARGET_ANCHOR_MATCHED: (
        "An identifier the user wrote corresponds to a member of the supplied "
        "inventory. That is all it establishes."
    ),
    ELIGIBILITY_TARGET_ANCHOR_UNMATCHED: (
        "An identifier the user wrote is not in the supplied inventory. It is "
        "reported unmatched rather than invented."
    ),
    ELIGIBILITY_REQUIRED_ROLE_UNSATISFIED: (
        "A role the acquisition request requires has no confidently eligible "
        "candidate. Widening a classification to force success is refused."
    ),
    ELIGIBILITY_ACQUISITION_NOT_READY: (
        "The upstream acquisition request contract is not ready, so there is nothing "
        "whose candidates could be enumerated."
    ),
    ELIGIBILITY_INVENTORY_REQUIRED: (
        "A repository request needs an authorized inventory snapshot and none was "
        "supplied. ACQUIRE.2 does not go and build one."
    ),
    ELIGIBILITY_SOURCE_INTEGRITY_FAILED: (
        "The supplied upstream records do not describe the same run the acquisition "
        "request was written over."
    ),
    ELIGIBILITY_INVENTORY_IDENTITY_MISMATCH: (
        "The inventory snapshot does not describe the repository, or does not "
        "fingerprint to what its builder claimed."
    ),
    ELIGIBILITY_ENVELOPE_WIDENED: (
        "The derived pool reaches further than the acquisition request licensed. "
        "Narrowing is the job; enlarging is refused."
    ),
}

# ── Statuses ──────────────────────────────────────────────────────────────────
#: A bounded eligible pool was derived for a ready acquisition request.  It
#: remains a pool of candidates: see :func:`eligibility_authority`.
STATUS_READY = "ready"
#: The upstream acquisition contract is not ready.
STATUS_NOT_ACQUISITION_READY = "not_acquisition_ready"
#: A repository request arrived with no authorized inventory.
STATUS_INVENTORY_REQUIRED = "inventory_required"
#: The inventory was supplied and a required role has no eligible candidate.
#: A factual result, and not a green light.
STATUS_INSUFFICIENT_CANDIDATES = "insufficient_candidates"
#: The upstream records do not hang together, or the pool would have widened.
STATUS_INCONSISTENT_INPUT = "inconsistent_input"

ELIGIBILITY_STATUSES: tuple[str, ...] = (
    STATUS_READY,
    STATUS_NOT_ACQUISITION_READY,
    STATUS_INVENTORY_REQUIRED,
    STATUS_INSUFFICIENT_CANDIDATES,
    STATUS_INCONSISTENT_INPUT,
)

#: Statuses in which the receipt describes a pool at all.
DESCRIBING_STATUSES: frozenset[str] = frozenset(
    {STATUS_READY, STATUS_INSUFFICIENT_CANDIDATES}
)

# ── Inconsistencies ───────────────────────────────────────────────────────────
INCONSISTENT_ACQUISITION_NOT_READY = "acquisition_contract_not_ready"
INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH = "source_fingerprint_mismatch"
INCONSISTENT_INVENTORY_ABSENT = "inventory_absent"
INCONSISTENT_INVENTORY_IDENTITY_MISMATCH = "inventory_identity_mismatch"
INCONSISTENT_INVENTORY_FINGERPRINT_MISMATCH = "inventory_fingerprint_mismatch"
INCONSISTENT_ELIGIBILITY_WIDENED = "eligibility_envelope_widened"

ELIGIBILITY_INCONSISTENCIES: tuple[str, ...] = (
    INCONSISTENT_ACQUISITION_NOT_READY,
    INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,
    INCONSISTENT_INVENTORY_ABSENT,
    INCONSISTENT_INVENTORY_IDENTITY_MISMATCH,
    INCONSISTENT_INVENTORY_FINGERPRINT_MISMATCH,
    INCONSISTENT_ELIGIBILITY_WIDENED,
)

# ── Selector-envelope violations ──────────────────────────────────────────────
#: What a selector may get wrong, checked rather than trusted.
VIOLATION_OUTSIDE_ENVELOPE = "candidate_outside_envelope"
VIOLATION_EXCLUDED_SOURCE_CLASS = "candidate_in_excluded_source_class"
VIOLATION_WRONG_TIER = "candidate_from_wrong_tier"
VIOLATION_BUDGET_EXCEEDED = "candidate_budget_exceeded"
VIOLATION_WRONG_INVENTORY = "candidate_from_wrong_inventory"
VIOLATION_DUPLICATE_CANDIDATE = "candidate_repeated"

ENVELOPE_VIOLATIONS: tuple[str, ...] = (
    VIOLATION_OUTSIDE_ENVELOPE,
    VIOLATION_EXCLUDED_SOURCE_CLASS,
    VIOLATION_WRONG_TIER,
    VIOLATION_BUDGET_EXCEEDED,
    VIOLATION_WRONG_INVENTORY,
    VIOLATION_DUPLICATE_CANDIDATE,
)

# ── Bounds ────────────────────────────────────────────────────────────────────
MAX_CANDIDATE_REASONS = len(CANDIDATE_REASONS)
MAX_CANDIDATE_SOURCE_CLASSES = len(REQUESTABLE_SOURCE_CLASSES)
MAX_CANDIDATE_ROLES = len(EVIDENCE_ROLES)
MAX_CLASSIFICATION_BASES = len(CLASSIFICATION_BASES)
MAX_ELIGIBILITY_REASONS = len(ELIGIBILITY_REASONS)
MAX_ELIGIBILITY_INCONSISTENCIES = len(ELIGIBILITY_INCONSISTENCIES)
MAX_EXCLUSION_SUMMARIES = len(INELIGIBILITY_REASONS)
MAX_SELECTOR_ENVELOPES = len(EVIDENCE_DOMAINS) * len(EVIDENCE_TIERS)
MAX_UNMATCHED_ANCHORS = 32


def eligibility_authority() -> dict[str, bool]:
    """Every authority ACQUIRE.2 declines to hold, in every status.

    Note ``selector_bridge_authority`` in particular.  ACQUIRE.2 *produces* a
    selector envelope; producing one is not permission to run a selector against
    live sources, and ``status=ready`` is not permission either.
    """
    return {
        "evidence_acquisition_authority": False,
        "candidate_content_read_authority": False,
        "repository_read_authority": False,
        "repository_traversal_authority": False,
        "repository_write_authority": False,
        "external_search_authority": False,
        "web_fetch_authority": False,
        "context_selection_execution_authority": False,
        "selector_bridge_authority": False,
        "indexing_authority": False,
        "graph_authority": False,
        "retrieval_authority": False,
        "validation_authority": False,
        "command_execution_authority": False,
        "execution_authority": False,
        "work" + "er_launch_authority": False,
        "patch_authority": False,
        "planning_authority": False,
        "routing_authority": False,
        "provider_selection_authority": False,
        "model_selection_authority": False,
        "dream_authority": False,
        "project_evolution_authority": False,
        "human_approval_required": True,
    }


def eligibility_guardrails() -> dict[str, bool]:
    """Every action ACQUIRE.2 did not perform while deciding eligibility."""
    return {
        "evidence_acquired": False,
        "evidence_promoted": False,
        "repository_files_read": False,
        "candidate_contents_read": False,
        "repository_traversal_performed": False,
        "new_inventory_built": False,
        "manifest_refreshed": False,
        "index_consulted": False,
        "graph_consulted": False,
        "ctx_select_executed": False,
        "read_set_generated": False,
        "file_paths_discovered": False,
        "network_called": False,
        "web_search_performed": False,
        "external_sources_fetched": False,
        "search_query_generated": False,
        "validation_executed": False,
        "command_executed": False,
        "planning_performed": False,
        "language_system_called": False,
        "provider_selected": False,
    }


def _bounded_vocabulary(
    values: tuple[str, ...],
    vocabulary: tuple[str, ...],
    label: str,
) -> None:
    """Distinct, inside the vocabulary, in canonical order."""
    if len(set(values)) != len(values):
        raise ValueError(f"each {label} may be stated exactly once")
    for value in values:
        if value not in vocabulary:
            raise ValueError(f"unsupported {label}: {value!r}")
    ordered = tuple(item for item in vocabulary if item in set(values))
    if values != ordered:
        raise ValueError(f"{label}s must be stated in the canonical vocabulary order")


# ── Records ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class CandidateClassification:
    """One source class a candidate may belong to, and why it was assigned.

    The ``basis`` is the whole justification.  There is no field for a sentence
    of reasoning, because a sentence of reasoning is what "``.md`` is probably
    architecture documentation" looks like once it is written down.
    """

    source_class: str
    basis: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.source_class not in ACQUISITION_SOURCE_CLASSES:
            raise ValueError(f"unsupported source class: {self.source_class!r}")
        if not self.basis:
            raise ValueError(
                f"classification {self.source_class!r} names no basis it came from"
            )
        _bounded_vocabulary(self.basis, CLASSIFICATION_BASES, "classification basis")

    def as_dict(self) -> dict[str, Any]:
        return {"source_class": self.source_class, "basis": list(self.basis)}


@dataclass(frozen=True, slots=True)
class EligibleCandidate:
    """One concrete inventory member that may satisfy an acquisition request.

    Not evidence.  ``content_read`` is false, ``evidence_status`` is
    ``not_acquired``, and ``authority_status`` is ``expected_not_verified`` —
    all three unconditionally, because there is no code path in this phase that
    could make any of them anything else.
    """

    identifier: str
    domain: str
    tier: str
    eligible_source_classes: tuple[str, ...]
    eligible_roles: tuple[str, ...]
    classifications: tuple[CandidateClassification, ...]
    size_bytes: int | None = None
    target_anchor_match: bool = False
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.identifier, str) or not self.identifier:
            raise ValueError("a candidate must carry an identifier")
        if self.domain not in EVIDENCE_DOMAINS:
            raise ValueError(f"unsupported evidence domain: {self.domain!r}")
        if self.tier not in EVIDENCE_TIERS:
            raise ValueError(f"unsupported evidence tier: {self.tier!r}")
        # One candidate may carry no class and no role at all: the one the user
        # named by hand.  Its presence is a fact about the inventory, its
        # emptiness is a fact about what nobody has established, and it stays
        # empty rather than borrowing a class from the request it arrived on.
        anchor_only = (
            self.target_anchor_match
            and not self.classifications
            and not self.eligible_source_classes
            and not self.eligible_roles
        )
        if not anchor_only:
            if not self.eligible_source_classes:
                raise ValueError(
                    f"candidate {self.identifier!r} is eligible for no source class"
                )
            if not self.eligible_roles:
                raise ValueError(f"candidate {self.identifier!r} is eligible for no role")
            if not self.classifications:
                raise ValueError(
                    f"candidate {self.identifier!r} states no classification basis"
                )
        _bounded_vocabulary(
            self.eligible_source_classes, ACQUISITION_SOURCE_CLASSES, "source class"
        )
        if set(self.eligible_source_classes) & set(NEVER_REQUESTED_SOURCE_CLASSES):
            raise ValueError(
                "restated material is an exclusion, never an eligible candidate"
            )
        _bounded_vocabulary(self.eligible_roles, EVIDENCE_ROLES, "evidence role")
        stated = tuple(item.source_class for item in self.classifications)
        if len(set(stated)) != len(stated):
            raise ValueError("each source class may be classified exactly once")
        if set(stated) != set(self.eligible_source_classes):
            raise ValueError(
                "every eligible source class must carry the basis it was assigned from"
            )
        if self.size_bytes is not None:
            if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int):
                raise TypeError("size_bytes must be an integer or None")
            if self.size_bytes < 0:
                raise ValueError("size_bytes must be non-negative or None")
        if not isinstance(self.target_anchor_match, bool):
            raise TypeError("target_anchor_match must be a bool")
        _bounded_vocabulary(self.reasons, CANDIDATE_REASONS, "candidate reason")
        if not self.reasons:
            raise ValueError(
                f"candidate {self.identifier!r} names no structured fact it came from"
            )

    @property
    def classification_status(self) -> str:
        """``classified``, or ``unknown`` when nothing established what this is."""
        return (
            CLASSIFICATION_CLASSIFIED if self.classifications else CLASSIFICATION_UNKNOWN
        )

    @property
    def satisfies_a_role(self) -> bool:
        """Can this candidate discharge anything the request required?

        An unknown candidate cannot, and saying so plainly is the point: it is
        in the pool because the user named it, not because anybody knows what it
        is.
        """
        return bool(self.eligible_roles)

    @property
    def content_read(self) -> bool:
        """Always false.  There is no code path in ACQUIRE.2 that reads a file."""
        return False

    @property
    def evidence_status(self) -> str:
        """Always ``not_acquired``.  A candidate is not evidence."""
        return EVIDENCE_STATUS_NOT_ACQUIRED

    @property
    def authority_status(self) -> str:
        """Always ``expected_not_verified``.  Nothing was opened, so nothing is known."""
        return AUTHORITY_EXPECTED_NOT_VERIFIED

    @property
    def active(self) -> bool:
        return self.tier in ACTIVE_TIERS

    def eligible_for_role(self, role: str) -> bool:
        return role in self.eligible_roles

    def as_dict(self) -> dict[str, Any]:
        return {
            "identifier": self.identifier,
            "domain": self.domain,
            "tier": self.tier,
            "eligible_source_classes": list(self.eligible_source_classes),
            "eligible_roles": list(self.eligible_roles),
            "classifications": [item.as_dict() for item in self.classifications],
            "classification_status": self.classification_status,
            "size_bytes": self.size_bytes,
            "target_anchor_match": self.target_anchor_match,
            "inventory_member": True,
            "content_read": self.content_read,
            "evidence_status": self.evidence_status,
            "authority_status": self.authority_status,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class ExclusionSummary:
    """How many members were kept out of a pool, and on what ground.

    Counts, never lists.  A named exclusion list of six thousand identifiers is
    the same failure as a named inclusion list of six thousand identifiers.
    """

    reason: str
    count: int

    def __post_init__(self) -> None:
        if self.reason not in INELIGIBILITY_REASONS:
            raise ValueError(f"unsupported ineligibility reason: {self.reason!r}")
        if isinstance(self.count, bool) or not isinstance(self.count, int):
            raise TypeError("an exclusion summary counts members")
        if self.count < 0:
            raise ValueError("an exclusion count may not be negative")

    def as_dict(self) -> dict[str, Any]:
        return {"reason": self.reason, "count": self.count}


@dataclass(frozen=True, slots=True)
class SelectorEnvelope:
    """What a selector may later consider, and the bounds it may not leave.

    Not a read set.  It names identifiers a selector may *rank*; whether any of
    them is ever opened is a later phase's decision under a later phase's gate.
    """

    domain: str
    tier: str
    allowed_candidate_identifiers: tuple[str, ...]
    allowed_roles: tuple[str, ...]
    allowed_source_classes: tuple[str, ...]
    excluded_source_classes: tuple[str, ...]
    candidate_budget_remaining: int
    source_budget_reserved: int
    byte_budget_remaining: int
    acquisition_request_fingerprint: str
    inventory_fingerprint: str | None = None
    repository_identity: str | None = None

    def __post_init__(self) -> None:
        if self.domain not in EVIDENCE_DOMAINS:
            raise ValueError(f"unsupported evidence domain: {self.domain!r}")
        if self.tier not in EVIDENCE_TIERS:
            raise ValueError(f"unsupported evidence tier: {self.tier!r}")
        identifiers = self.allowed_candidate_identifiers
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("each allowed identifier may be stated exactly once")
        if tuple(sorted(identifiers, key=lambda item: (item.casefold(), item))) != tuple(
            sorted(identifiers, key=lambda item: (item.casefold(), item))
        ):  # pragma: no cover - defensive, sort is total
            raise ValueError("allowed identifiers must be deterministically ordered")
        _bounded_vocabulary(self.allowed_roles, EVIDENCE_ROLES, "evidence role")
        _bounded_vocabulary(
            self.allowed_source_classes, REQUESTABLE_SOURCE_CLASSES, "source class"
        )
        _bounded_vocabulary(
            self.excluded_source_classes,
            NEVER_REQUESTED_SOURCE_CLASSES,
            "excluded source class",
        )
        for name in (
            "candidate_budget_remaining",
            "source_budget_reserved",
            "byte_budget_remaining",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a finite non-negative integer")
        if not self.acquisition_request_fingerprint:
            raise ValueError("a selector envelope must bind to its acquisition request")

    def permits(self, identifier: str) -> bool:
        return identifier in set(self.allowed_candidate_identifiers)

    def as_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "tier": self.tier,
            "allowed_candidate_identifiers": list(self.allowed_candidate_identifiers),
            "allowed_roles": list(self.allowed_roles),
            "allowed_source_classes": list(self.allowed_source_classes),
            "excluded_source_classes": list(self.excluded_source_classes),
            "candidate_budget_remaining": self.candidate_budget_remaining,
            "source_budget_reserved": self.source_budget_reserved,
            "byte_budget_remaining": self.byte_budget_remaining,
            "acquisition_request_fingerprint": self.acquisition_request_fingerprint,
            "inventory_fingerprint": self.inventory_fingerprint,
            "repository_identity": self.repository_identity,
            "is_read_set": False,
            "selector_executed": False,
        }


@dataclass(frozen=True, slots=True)
class ExternalCandidateEnvelope:
    """What a future network-enabled phase may look for, in the abstract.

    There is no host, no address, no query and no engine — not fields this
    record declines to fill, but fields it does not have.  Zero concrete
    candidates is the expected and correct result: discovery needs a capability
    ACQUIRE.2 does not have.
    """

    required_role: str
    allowed_source_classes: tuple[str, ...]
    freshness: str
    candidate_budget: int
    source_budget_reserved: int
    acquisition_request_fingerprint: str

    def __post_init__(self) -> None:
        if self.required_role not in EVIDENCE_ROLES:
            raise ValueError(f"unsupported evidence role: {self.required_role!r}")
        _bounded_vocabulary(
            self.allowed_source_classes, REQUESTABLE_SOURCE_CLASSES, "source class"
        )
        if not self.allowed_source_classes:
            raise ValueError("an external envelope must name a source class")
        if self.freshness not in FRESHNESS_REQUIREMENTS:
            raise ValueError(f"unsupported freshness requirement: {self.freshness!r}")
        for name in ("candidate_budget", "source_budget_reserved"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a finite non-negative integer")
        if not self.acquisition_request_fingerprint:
            raise ValueError("an external envelope must bind to its acquisition request")

    def as_dict(self) -> dict[str, Any]:
        return {
            "required_role": self.required_role,
            "allowed_source_classes": list(self.allowed_source_classes),
            "freshness": self.freshness,
            "candidate_budget": self.candidate_budget,
            "source_budget_reserved": self.source_budget_reserved,
            "acquisition_request_fingerprint": self.acquisition_request_fingerprint,
            "concrete_candidates": [],
            "discovery_requires_later_authorized_phase": True,
            "network_called": False,
        }


@dataclass(frozen=True, slots=True)
class CandidateEligibilityReceipt:
    """Which candidates are eligible, and nothing acquired.

    The record has no room for content, a read set, a retrieval result, a
    ranking score, a proof, a claim or a compute choice.  Those are not fields
    ACQUIRE.2 declines to fill; they are fields it does not have.
    """

    status: str
    workflow: str | None = None
    evidence_scope: str | None = None
    active_candidates: tuple[EligibleCandidate, ...] = ()
    secondary_candidates: tuple[EligibleCandidate, ...] = ()
    deferred_candidates: tuple[EligibleCandidate, ...] = ()
    exclusion_summary: tuple[ExclusionSummary, ...] = ()
    selector_envelopes: tuple[SelectorEnvelope, ...] = ()
    external_envelopes: tuple[ExternalCandidateEnvelope, ...] = ()
    unmatched_target_anchors: tuple[str, ...] = ()
    unsatisfied_required_roles: tuple[str, ...] = ()
    candidate_limit: int = 0
    source_limit_reserved: int = 0
    byte_limit: int = 0
    byte_eligible_total: int = 0
    reasons: tuple[str, ...] = ()
    inconsistencies: tuple[str, ...] = ()
    acquisition_request_fingerprint: str | None = None
    evidence_contract_fingerprint: str | None = None
    inventory_fingerprint: str | None = None
    repository_identity: str | None = None
    schema_version: str = CANDIDATE_RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in ELIGIBILITY_STATUSES:
            raise ValueError(f"unsupported eligibility status: {self.status!r}")
        if self.workflow is not None and self.workflow not in WORKFLOW_TARGETS:
            raise ValueError(f"unsupported workflow: {self.workflow!r}")
        if self.evidence_scope is not None and self.evidence_scope not in EVIDENCE_SCOPES:
            raise ValueError(f"unsupported evidence scope: {self.evidence_scope!r}")

        for pool, expected in (
            (self.active_candidates, TIER_REQUIRED_PRIMARY),
            (self.secondary_candidates, TIER_REQUIRED_SECONDARY),
            (self.deferred_candidates, TIER_DEFERRED),
        ):
            for candidate in pool:
                if candidate.tier != expected:
                    raise ValueError(
                        f"{candidate.tier!r} candidate is in the {expected!r} pool"
                    )
        for candidate in self.deferred_candidates:
            if candidate.active:
                raise ValueError("a deferred candidate may not be active")

        seen = [
            candidate.identifier.casefold()
            for candidate in self.active_candidates
            + self.secondary_candidates
            + self.deferred_candidates
        ]
        if len(set(seen)) != len(seen):
            raise ValueError(
                "a candidate identifier may appear in exactly one pool, exactly once"
            )

        summaries = [item.reason for item in self.exclusion_summary]
        if len(set(summaries)) != len(summaries):
            raise ValueError("each ineligibility reason may be summarised once")
        if len(self.exclusion_summary) > MAX_EXCLUSION_SUMMARIES:
            raise ValueError("exclusion summaries exceed the supported bound")
        if len(self.selector_envelopes) > MAX_SELECTOR_ENVELOPES:
            raise ValueError("selector envelopes exceed the supported bound")
        if len(self.unmatched_target_anchors) > MAX_UNMATCHED_ANCHORS:
            raise ValueError("unmatched target anchors exceed the supported bound")

        _bounded_vocabulary(
            self.unsatisfied_required_roles, EVIDENCE_ROLES, "evidence role"
        )
        _bounded_vocabulary(self.reasons, ELIGIBILITY_REASONS, "eligibility reason")
        _bounded_vocabulary(
            self.inconsistencies, ELIGIBILITY_INCONSISTENCIES, "inconsistency"
        )
        if not self.reasons:
            raise ValueError("every eligibility receipt must state at least one reason")

        for name in (
            "candidate_limit",
            "source_limit_reserved",
            "byte_limit",
            "byte_eligible_total",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a finite non-negative integer")
        if self.byte_eligible_total > self.byte_limit:
            raise ValueError("eligible bytes may never exceed the byte ceiling")

        if self.status in DESCRIBING_STATUSES:
            if self.workflow is None or self.evidence_scope is None:
                raise ValueError(
                    "a receipt that describes a pool must name the workflow and the "
                    "evidence scope it was derived under"
                )
            if self.inconsistencies:
                raise ValueError("a described pool may not carry inconsistencies")
            if self.acquisition_request_fingerprint is None:
                raise ValueError(
                    "a described pool must fingerprint the request it was derived from"
                )
            if self.candidate_used > self.candidate_limit:
                raise ValueError(
                    "the candidate pool may never exceed the upstream ceiling"
                )
            if (self.status == STATUS_READY) != (not self.unsatisfied_required_roles):
                raise ValueError(
                    "a ready receipt satisfies every required role, and one that does "
                    "not says so"
                )
        else:
            if self.workflow is not None or self.evidence_scope is not None:
                raise ValueError(
                    f"status {self.status!r} describes no workflow and no evidence scope"
                )
            if (
                self.active_candidates
                or self.secondary_candidates
                or self.deferred_candidates
                or self.selector_envelopes
                or self.external_envelopes
            ):
                raise ValueError(
                    "an order whose candidates could not be enumerated is not "
                    "described: ACQUIRE.2 does not guess what a pool would contain"
                )
            if not self.inconsistencies:
                raise ValueError("a refused receipt must state what did not hang together")

    # ── derived, authority-free facts ────────────────────────────────────────
    @property
    def ready(self) -> bool:
        return self.status == STATUS_READY

    @property
    def human_approval_required(self) -> bool:
        """Always true.  A candidate pool is a report, never a go-ahead."""
        return True

    @property
    def candidate_used(self) -> int:
        """Candidates counted once each, across the pools that consume budget."""
        return len(self.active_candidates) + len(self.secondary_candidates)

    @property
    def source_budget_consumed(self) -> int:
        """Always zero.  Nothing was acquired, so no source budget was spent."""
        return 0

    def all_candidates(self) -> tuple[EligibleCandidate, ...]:
        return (
            self.active_candidates + self.secondary_candidates + self.deferred_candidates
        )

    def identifiers(self) -> tuple[str, ...]:
        return tuple(candidate.identifier for candidate in self.all_candidates())

    def active_identifiers(self) -> tuple[str, ...]:
        return tuple(
            candidate.identifier
            for candidate in self.active_candidates + self.secondary_candidates
        )

    def candidate(self, identifier: str) -> EligibleCandidate | None:
        for item in self.all_candidates():
            if item.identifier == identifier:
                return item
        return None

    def envelope_for(self, domain: str, tier: str) -> SelectorEnvelope | None:
        for envelope in self.selector_envelopes:
            if envelope.domain == domain and envelope.tier == tier:
                return envelope
        return None

    def source_classes(self) -> tuple[str, ...]:
        present = {
            source_class
            for candidate in self.active_candidates + self.secondary_candidates
            for source_class in candidate.eligible_source_classes
        }
        return tuple(item for item in ACQUISITION_SOURCE_CLASSES if item in present)

    def budget_summary(self) -> dict[str, Any]:
        """The ceilings and what was used, derived so they cannot disagree."""
        return {
            "candidate_limit": self.candidate_limit,
            "candidate_used": self.candidate_used,
            "candidate_remaining": self.candidate_limit - self.candidate_used,
            "source_limit_reserved": self.source_limit_reserved,
            "source_budget_consumed": self.source_budget_consumed,
            "byte_limit": self.byte_limit,
            "byte_eligible_total": self.byte_eligible_total,
            "deferred_candidate_budget": 0,
            "bounded": True,
            "within_upstream_ceiling": self.candidate_used <= self.candidate_limit,
        }

    def reason_descriptions(self) -> tuple[str, ...]:
        return tuple(ELIGIBILITY_REASON_DESCRIPTIONS[reason] for reason in self.reasons)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "status": self.status,
            "workflow": self.workflow,
            "evidence_scope": self.evidence_scope,
            "active_candidates": [item.as_dict() for item in self.active_candidates],
            "secondary_candidates": [
                item.as_dict() for item in self.secondary_candidates
            ],
            "deferred_candidates": [item.as_dict() for item in self.deferred_candidates],
            "exclusion_summary": [item.as_dict() for item in self.exclusion_summary],
            "selector_envelopes": [item.as_dict() for item in self.selector_envelopes],
            "external_envelopes": [item.as_dict() for item in self.external_envelopes],
            "unmatched_target_anchors": list(self.unmatched_target_anchors),
            "unsatisfied_required_roles": list(self.unsatisfied_required_roles),
            "budget": self.budget_summary(),
            "reasons": [
                {"code": reason, "description": ELIGIBILITY_REASON_DESCRIPTIONS[reason]}
                for reason in self.reasons
            ],
            "inconsistencies": list(self.inconsistencies),
            "acquisition_request_fingerprint": self.acquisition_request_fingerprint,
            "evidence_contract_fingerprint": self.evidence_contract_fingerprint,
            "inventory_fingerprint": self.inventory_fingerprint,
            "repository_identity": self.repository_identity,
            "human_approval_required": self.human_approval_required,
            "note": (
                "These are candidates, not evidence. Nothing was traversed, opened, "
                "ranked, selected, fetched or acquired, and eligibility for a role is "
                "an expectation about a source nobody has looked at yet."
            ),
            "authority": eligibility_authority(),
            "guardrails": eligibility_guardrails(),
        }


__all__ = [
    "AUTHORITY_EXPECTED_NOT_VERIFIED",
    "BASIS_EXPLICIT_TARGET_ANCHOR",
    "BASIS_INVENTORY_DECLARED_CLASS",
    "BASIS_INVENTORY_DUPLICATE_MARKER",
    "BASIS_INVENTORY_GENERATED_MARKER",
    "BASIS_INVENTORY_HARD_EXCLUSION",
    "BASIS_INVENTORY_PARSER_SUPPORT",
    "BASIS_INVENTORY_VENDOR_MARKER",
    "BASIS_KNOWN_CONFIGURATION_NAME",
    "BASIS_KNOWN_HISTORICAL_LOCATION",
    "BASIS_KNOWN_MANIFEST_NAME",
    "BASIS_KNOWN_SNAPSHOT_LOCATION",
    "BASIS_KNOWN_TEMPORARY_LOCATION",
    "BASIS_KNOWN_TEST_LOCATION",
    "CANDIDATE_DEFERRED_UPSTREAM",
    "CANDIDATE_EXPLICIT_TARGET_MATCHED",
    "CANDIDATE_INVENTORY_MEMBER",
    "CANDIDATE_REASONS",
    "CANDIDATE_RECEIPT_SCHEMA_VERSION",
    "CANDIDATE_SUPPLIED_CONTEXT_REFERENCE",
    "CANDIDATE_TIER_PRESERVED",
    "CLASSIFICATION_BASES",
    "CLASSIFICATION_CLASSIFIED",
    "CLASSIFICATION_STATUSES",
    "CLASSIFICATION_UNKNOWN",
    "DESCRIBING_STATUSES",
    "ELIGIBILITY_ACQUISITION_NOT_READY",
    "ELIGIBILITY_CANDIDATES_BOUNDED",
    "ELIGIBILITY_DEFERRED_KEPT_SEPARATE",
    "ELIGIBILITY_DIRECT_CONTEXT_REFERENCED",
    "ELIGIBILITY_ENVELOPE_WIDENED",
    "ELIGIBILITY_EXCLUSIONS_ENFORCED",
    "ELIGIBILITY_EXTERNAL_ENVELOPE_ONLY",
    "ELIGIBILITY_INCONSISTENCIES",
    "ELIGIBILITY_INVENTORY_IDENTITY_MISMATCH",
    "ELIGIBILITY_INVENTORY_REQUIRED",
    "ELIGIBILITY_REASONS",
    "ELIGIBILITY_REASON_DESCRIPTIONS",
    "ELIGIBILITY_REQUIRED_ROLE_UNSATISFIED",
    "ELIGIBILITY_SOURCE_INTEGRITY_FAILED",
    "ELIGIBILITY_STATUSES",
    "ELIGIBILITY_TARGET_ANCHOR_MATCHED",
    "ELIGIBILITY_TARGET_ANCHOR_UNMATCHED",
    "ENVELOPE_VIOLATIONS",
    "EVIDENCE_STATUS_NOT_ACQUIRED",
    "INCONSISTENT_ACQUISITION_NOT_READY",
    "INCONSISTENT_ELIGIBILITY_WIDENED",
    "INCONSISTENT_INVENTORY_ABSENT",
    "INCONSISTENT_INVENTORY_FINGERPRINT_MISMATCH",
    "INCONSISTENT_INVENTORY_IDENTITY_MISMATCH",
    "INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH",
    "INELIGIBILITY_REASONS",
    "INELIGIBLE_CANDIDATE_CEILING_REACHED",
    "INELIGIBLE_CLASSIFICATION_UNKNOWN",
    "INELIGIBLE_HARD_EXCLUDED_BY_INVENTORY",
    "INELIGIBLE_NOT_IN_INVENTORY",
    "INELIGIBLE_OUTSIDE_REPOSITORY",
    "INELIGIBLE_PER_SOURCE_BYTES_EXCEEDED",
    "INELIGIBLE_SIZE_UNKNOWN",
    "INELIGIBLE_SOURCE_CLASS_EXCLUDED",
    "INELIGIBLE_SOURCE_CLASS_NOT_REQUESTED",
    "INELIGIBLE_TOTAL_BYTES_EXHAUSTED",
    "PHASE_ID",
    "STATUS_INCONSISTENT_INPUT",
    "STATUS_INSUFFICIENT_CANDIDATES",
    "STATUS_INVENTORY_REQUIRED",
    "STATUS_NOT_ACQUISITION_READY",
    "STATUS_READY",
    "VIOLATION_BUDGET_EXCEEDED",
    "VIOLATION_DUPLICATE_CANDIDATE",
    "VIOLATION_EXCLUDED_SOURCE_CLASS",
    "VIOLATION_OUTSIDE_ENVELOPE",
    "VIOLATION_WRONG_INVENTORY",
    "VIOLATION_WRONG_TIER",
    "CandidateClassification",
    "CandidateEligibilityReceipt",
    "EligibleCandidate",
    "ExclusionSummary",
    "ExternalCandidateEnvelope",
    "SelectorEnvelope",
    "eligibility_authority",
    "eligibility_guardrails",
]
