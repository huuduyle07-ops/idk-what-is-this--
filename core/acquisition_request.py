"""ACQUIRE.1 — the Acquisition Request Contract and its bounded vocabularies.

WAITER.2 answered *what evidence will this workflow need*.  ACQUIRE.1 answers
the next question and only that one:

    what bounded requests should a future acquisition engine receive?

It never answers "go and get it".

    EvidenceRequirementContract
        -> AcquisitionRequestContract

The kitchen analogy runs one step further.  WAITER.2 wrote down the ingredients.
ACQUIRE.1 writes the shopping list: which aisles, which kinds of thing on each
aisle, how much of each at most, and what to leave on the shelf.  Nobody has
been to the shop.

Four properties make the record worth having.

**A request is a class and a ceiling, never a shopping trip.**  It names an
evidence domain, the roles it must satisfy, abstract *source classes* and a
bounded budget.  It contains no discovered path, no directory listing, no query,
no host, no retrieval result and no step ordering — not fields it declines to
fill, but fields it does not have.

**Every budget is finite, and there is nowhere to write otherwise.**  A budget
is a named profile; the four numeric ceilings are read out of a frozen table
rather than supplied by a caller.  ``max_candidates`` cannot be ``None``, cannot
be negative, cannot be "all", and cannot exceed the documented ceiling, because
no code path exists that would set it.  This is the structural answer to the
DeepSeek Harness dogfood, in which broad reconnaissance became 6,087 files.

**Source classes are selectors, not filenames.**  ``runtime_implementation``
says what kind of thing may later satisfy a role.  Which files are of that kind
is a question about repository membership, and ACQUIRE.1 has no way to ask it.

**Restated material cannot be requested at all.**  Generated output, snapshots,
scratch artifacts and duplicated renderings are representable only as
exclusions: a request that named one would fail to construct.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no language system, inspects no repository, acquires no evidence, selects
nothing, plans nothing, and grants no authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.evidence_requirements import (
    ACTIVE_TIERS,
    EVIDENCE_DOMAINS,
    EVIDENCE_ROLES,
    EVIDENCE_TIERS,
    EVIDENCE_SCOPES,
    ROLE_ARCHITECTURE_DESCRIPTION,
    ROLE_CONFIGURATION_AUTHORITY,
    ROLE_CURRENT_EXTERNAL_AUTHORITY,
    ROLE_IMPLEMENTATION_AUTHORITY,
    ROLE_INTERFACE_CONTRACT,
    TIER_DEFERRED,
    TIER_EXCLUDED_INITIALLY,
)
from core.execution_waiter import WORKFLOW_TARGETS


PHASE_ID = "ACQUIRE.1"
ACQUISITION_CONTRACT_SCHEMA_VERSION = "acquire_1_acquisition_request_contract_v1"

# ── Source classes ────────────────────────────────────────────────────────────
#: *What kind of thing* may later satisfy a role.  Abstract selectors, never
#: names: nothing here can be resolved to a file without asking the repository,
#: and asking the repository is somebody else's phase.
#:
#: The vocabulary is deliberately short.  A class earns its place by being a
#: distinct answer to "what sort of source is this?" that some upstream role
#: actually asks for; ``target_artifact`` and ``runtime_observation`` were
#: considered and not created, because an explicitly named artifact is carried
#: as a target anchor instead, and no upstream role licenses observing a running
#: system.
SOURCE_CLASS_SUPPLIED_CONTEXT = "supplied_context"
SOURCE_CLASS_RUNTIME_IMPLEMENTATION = "runtime_implementation"
SOURCE_CLASS_SURROUNDING_IMPLEMENTATION = "surrounding_implementation"
SOURCE_CLASS_INTERFACE_DEFINITION = "interface_definition"
SOURCE_CLASS_CONFIGURATION = "configuration"
SOURCE_CLASS_DEPENDENCY_MANIFEST = "dependency_manifest"
SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC = "authoritative_architecture_doc"
SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE = "plugin_or_registration_surface"
SOURCE_CLASS_VALIDATION_TEST = "validation_test"
SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL = "historical_design_material"
SOURCE_CLASS_AUTHORITATIVE_EXTERNAL_SOURCE = "authoritative_external_source"
SOURCE_CLASS_GENERATED_ARTIFACT = "generated_artifact"
SOURCE_CLASS_SNAPSHOT = "snapshot"
SOURCE_CLASS_TEMPORARY_ARTIFACT = "temporary_artifact"
SOURCE_CLASS_DUPLICATE_RENDERING = "duplicate_rendering"

ACQUISITION_SOURCE_CLASSES: tuple[str, ...] = (
    SOURCE_CLASS_SUPPLIED_CONTEXT,
    SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
    SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,
    SOURCE_CLASS_INTERFACE_DEFINITION,
    SOURCE_CLASS_CONFIGURATION,
    SOURCE_CLASS_DEPENDENCY_MANIFEST,
    SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,
    SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE,
    SOURCE_CLASS_VALIDATION_TEST,
    SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,
    SOURCE_CLASS_AUTHORITATIVE_EXTERNAL_SOURCE,
    SOURCE_CLASS_GENERATED_ARTIFACT,
    SOURCE_CLASS_SNAPSHOT,
    SOURCE_CLASS_TEMPORARY_ARTIFACT,
    SOURCE_CLASS_DUPLICATE_RENDERING,
)

#: Classes that restate a source rather than being one.  They are representable
#: *only* as exclusions: :class:`AcquisitionRequest` refuses to name one, so
#: "request the snapshots" is not a thing this schema can express.
NEVER_REQUESTED_SOURCE_CLASSES: tuple[str, ...] = (
    SOURCE_CLASS_GENERATED_ARTIFACT,
    SOURCE_CLASS_SNAPSHOT,
    SOURCE_CLASS_TEMPORARY_ARTIFACT,
    SOURCE_CLASS_DUPLICATE_RENDERING,
)

REQUESTABLE_SOURCE_CLASSES: tuple[str, ...] = tuple(
    item for item in ACQUISITION_SOURCE_CLASSES
    if item not in NEVER_REQUESTED_SOURCE_CLASSES
)

# ── Request scope ─────────────────────────────────────────────────────────────
#: How far one request reaches.  Never a count and never a file set.
#:
#: ``existing_context_reference`` is the honest name for the direct-context
#: request: the material is already in hand, so the "acquisition" is a reference
#: to what INPUT preserved and not a fetch of anything.
REQUEST_SCOPE_EXISTING_CONTEXT = "existing_context_reference"
REQUEST_SCOPE_BOUNDED_REPOSITORY = "bounded_repository"
REQUEST_SCOPE_BROAD_REPOSITORY_RECONNAISSANCE = "broad_repository_reconnaissance"
REQUEST_SCOPE_EXTERNAL_INFORMATION = "external_information"

REQUEST_SCOPES: tuple[str, ...] = (
    REQUEST_SCOPE_EXISTING_CONTEXT,
    REQUEST_SCOPE_BOUNDED_REPOSITORY,
    REQUEST_SCOPE_BROAD_REPOSITORY_RECONNAISSANCE,
    REQUEST_SCOPE_EXTERNAL_INFORMATION,
)

# ── Freshness ─────────────────────────────────────────────────────────────────
#: How current a source has to be at the moment it is used.
#:
#: Three values, and no more.  ``recent`` and ``stable_reference`` were
#: considered and not created: upstream states no fact that could produce
#: either, and a value nothing can reach is decoration rather than honesty.  No
#: day count appears anywhere, because nobody upstream supplied one.
FRESHNESS_NOT_APPLICABLE = "not_applicable"
FRESHNESS_CURRENT = "current"
FRESHNESS_HISTORICAL = "historical"

FRESHNESS_REQUIREMENTS: tuple[str, ...] = (
    FRESHNESS_NOT_APPLICABLE,
    FRESHNESS_CURRENT,
    FRESHNESS_HISTORICAL,
)

# ── Budget profiles ───────────────────────────────────────────────────────────
#: A budget is a *name*.  The numbers below are the whole of what a name means,
#: and a caller cannot supply its own: there is no field in which an unbounded
#: budget could be written.
#:
#: The ordering is smallest first, and the ladder is the policy: existing
#: context is a reference to what is already here; a secondary check is smaller
#: than the primary evidence it checks; broad reconnaissance is larger than a
#: bounded operation and still finite.
BUDGET_NONE = "none"
BUDGET_EXISTING_CONTEXT = "existing_context"
BUDGET_EXTERNAL_BOUNDED = "external_bounded"
BUDGET_SECONDARY_VERIFICATION = "secondary_verification"
BUDGET_BOUNDED = "bounded"
BUDGET_RECONNAISSANCE = "reconnaissance"

BUDGET_PROFILES: tuple[str, ...] = (
    BUDGET_NONE,
    BUDGET_EXISTING_CONTEXT,
    BUDGET_EXTERNAL_BOUNDED,
    BUDGET_SECONDARY_VERIFICATION,
    BUDGET_BOUNDED,
    BUDGET_RECONNAISSANCE,
)

#: The documented upper bound of the whole vocabulary.  Every profile sits at or
#: under it, and the record refuses to construct anything above it.  A future
#: acquisition engine that honours these numbers cannot arrive at six thousand
#: candidates by following this contract.
MAX_CANDIDATES_CEILING = 96
MAX_INITIAL_SOURCES_CEILING = 32
MAX_TOTAL_BYTES_CEILING = 2_097_152
MAX_PER_SOURCE_BYTES_CEILING = 131_072

#: ``profile -> (max_candidates, max_initial_sources, max_total_bytes,
#: max_per_source_bytes)``.  Constants, every one of them.  Not one number here
#: is derived from how many files the repository holds, how much memory the
#: machine has, or anything else that differs between two runs.
BUDGET_PROFILE_LIMITS: dict[str, tuple[int, int, int, int]] = {
    BUDGET_NONE: (0, 0, 0, 0),
    BUDGET_EXISTING_CONTEXT: (1, 1, 65_536, 65_536),
    BUDGET_EXTERNAL_BOUNDED: (8, 4, 262_144, 65_536),
    BUDGET_SECONDARY_VERIFICATION: (12, 4, 262_144, 131_072),
    BUDGET_BOUNDED: (24, 8, 524_288, 131_072),
    BUDGET_RECONNAISSANCE: (96, 32, 2_097_152, 131_072),
}

if tuple(BUDGET_PROFILE_LIMITS) != BUDGET_PROFILES:  # pragma: no cover
    raise RuntimeError("every budget profile must state its limits, in profile order")

for _profile, _limits in BUDGET_PROFILE_LIMITS.items():  # pragma: no cover
    if any(not isinstance(_value, int) or _value < 0 for _value in _limits):
        raise RuntimeError(f"budget profile {_profile!r} is not a finite ceiling")
    if (
        _limits[0] > MAX_CANDIDATES_CEILING
        or _limits[1] > MAX_INITIAL_SOURCES_CEILING
        or _limits[2] > MAX_TOTAL_BYTES_CEILING
        or _limits[3] > MAX_PER_SOURCE_BYTES_CEILING
    ):
        raise RuntimeError(f"budget profile {_profile!r} exceeds the documented ceiling")

# ── Target anchors ────────────────────────────────────────────────────────────
#: The only provenance an anchor may have.  An anchor is an identifier the user
#: wrote and INPUT.1 preserved; ACQUIRE.1 has no other way to obtain one, and no
#: way at all to invent one.
ANCHOR_SOURCE_EXPLICIT_INPUT_EVIDENCE = "explicit_input_evidence"
ANCHOR_SOURCES: tuple[str, ...] = (ANCHOR_SOURCE_EXPLICIT_INPUT_EVIDENCE,)

# ── Reason codes ──────────────────────────────────────────────────────────────
ACQUIRE_SUPPLIED_MATERIAL_ALREADY_IN_HAND = "ACQUIRE_SUPPLIED_MATERIAL_ALREADY_IN_HAND"
ACQUIRE_REPOSITORY_EVIDENCE_REQUESTED = "ACQUIRE_REPOSITORY_EVIDENCE_REQUESTED"
ACQUIRE_ARCHITECTURE_RECONNAISSANCE_REQUESTED = (
    "ACQUIRE_ARCHITECTURE_RECONNAISSANCE_REQUESTED"
)
ACQUIRE_VALIDATION_EVIDENCE_REQUESTED = "ACQUIRE_VALIDATION_EVIDENCE_REQUESTED"
ACQUIRE_UNRELATED_VALIDATION_DEFERRED = "ACQUIRE_UNRELATED_VALIDATION_DEFERRED"
ACQUIRE_HISTORICAL_MATERIAL_DEFERRED = "ACQUIRE_HISTORICAL_MATERIAL_DEFERRED"
ACQUIRE_EXTERNAL_AUTHORITY_REQUESTED = "ACQUIRE_EXTERNAL_AUTHORITY_REQUESTED"
ACQUIRE_RESTATED_MATERIAL_EXCLUDED = "ACQUIRE_RESTATED_MATERIAL_EXCLUDED"
ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED = "ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED"
ACQUIRE_BUDGET_BOUNDED_BY_SCOPE_AND_TIER = "ACQUIRE_BUDGET_BOUNDED_BY_SCOPE_AND_TIER"
ACQUIRE_EVIDENCE_NOT_READY = "ACQUIRE_EVIDENCE_NOT_READY"
ACQUIRE_SOURCE_INTEGRITY_FAILED = "ACQUIRE_SOURCE_INTEGRITY_FAILED"
ACQUIRE_CAPABILITY_ENVELOPE_VIOLATED = "ACQUIRE_CAPABILITY_ENVELOPE_VIOLATED"
ACQUIRE_REQUIRED_CAPABILITY_LOST = "ACQUIRE_REQUIRED_CAPABILITY_LOST"
ACQUIRE_REQUIREMENT_WIDENED = "ACQUIRE_REQUIREMENT_WIDENED"
ACQUIRE_REQUIRED_EVIDENCE_LOST = "ACQUIRE_REQUIRED_EVIDENCE_LOST"
ACQUIRE_ROLE_NOT_MAPPABLE = "ACQUIRE_ROLE_NOT_MAPPABLE"

ACQUISITION_REASONS: tuple[str, ...] = (
    ACQUIRE_SUPPLIED_MATERIAL_ALREADY_IN_HAND,
    ACQUIRE_REPOSITORY_EVIDENCE_REQUESTED,
    ACQUIRE_ARCHITECTURE_RECONNAISSANCE_REQUESTED,
    ACQUIRE_VALIDATION_EVIDENCE_REQUESTED,
    ACQUIRE_UNRELATED_VALIDATION_DEFERRED,
    ACQUIRE_HISTORICAL_MATERIAL_DEFERRED,
    ACQUIRE_EXTERNAL_AUTHORITY_REQUESTED,
    ACQUIRE_RESTATED_MATERIAL_EXCLUDED,
    ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,
    ACQUIRE_BUDGET_BOUNDED_BY_SCOPE_AND_TIER,
    ACQUIRE_EVIDENCE_NOT_READY,
    ACQUIRE_SOURCE_INTEGRITY_FAILED,
    ACQUIRE_CAPABILITY_ENVELOPE_VIOLATED,
    ACQUIRE_REQUIRED_CAPABILITY_LOST,
    ACQUIRE_REQUIREMENT_WIDENED,
    ACQUIRE_REQUIRED_EVIDENCE_LOST,
    ACQUIRE_ROLE_NOT_MAPPABLE,
)

#: A sentence per code, so explainability never rests on an opaque weight.
ACQUISITION_REASON_DESCRIPTIONS: dict[str, str] = {
    ACQUIRE_SUPPLIED_MATERIAL_ALREADY_IN_HAND: (
        "The order carries this material itself. The request references what INPUT "
        "preserved and asks for nothing to be fetched."
    ),
    ACQUIRE_REPOSITORY_EVIDENCE_REQUESTED: (
        "The upstream contract requires repository evidence at a bounded reach, so a "
        "bounded repository request is stated in source classes rather than paths."
    ),
    ACQUIRE_ARCHITECTURE_RECONNAISSANCE_REQUESTED: (
        "The upstream contract requires the repository to be surveyed. The request "
        "names which kinds of source that survey may reach, and how many at most."
    ),
    ACQUIRE_VALIDATION_EVIDENCE_REQUESTED: (
        "Validation artifacts are required evidence at the tier the upstream contract "
        "set, and the request preserves that tier exactly."
    ),
    ACQUIRE_UNRELATED_VALIDATION_DEFERRED: (
        "Validation artifacts unrelated to the primary evidence were deferred "
        "upstream, so this request carries a smaller ceiling than the evidence it "
        "checks."
    ),
    ACQUIRE_HISTORICAL_MATERIAL_DEFERRED: (
        "Historical design material was deferred upstream. The request records it "
        "with no acquisition budget at all and never as current authority."
    ),
    ACQUIRE_EXTERNAL_AUTHORITY_REQUESTED: (
        "The upstream contract requires information from outside the repository that "
        "has to be current when it is used. No engine, host or query is named."
    ),
    ACQUIRE_RESTATED_MATERIAL_EXCLUDED: (
        "Generated output, snapshots, scratch artifacts and duplicated renderings "
        "restate a source rather than being one, and are excluded from the initial set."
    ),
    ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED: (
        "An identifier the user wrote is carried through unchanged. It was preserved, "
        "not discovered, and says nothing about whether it exists."
    ),
    ACQUIRE_BUDGET_BOUNDED_BY_SCOPE_AND_TIER: (
        "The ceiling follows the reach of the evidence and its priority, not the "
        "selected workflow and not the size of anything."
    ),
    ACQUIRE_EVIDENCE_NOT_READY: (
        "The upstream evidence requirement contract is not a specified one, so there "
        "is nothing whose acquisition could be requested."
    ),
    ACQUIRE_SOURCE_INTEGRITY_FAILED: (
        "The supplied upstream records do not describe the same run the evidence "
        "contract was specified over."
    ),
    ACQUIRE_CAPABILITY_ENVELOPE_VIOLATED: (
        "The evidence contract reaches outside the capability envelope WAITER.1 "
        "established. Requests are not written over a widened envelope."
    ),
    ACQUIRE_REQUIRED_CAPABILITY_LOST: (
        "A capability the upstream envelope requires is not represented by any active "
        "requirement, so the evidence contract is already narrower than the order."
    ),
    ACQUIRE_REQUIREMENT_WIDENED: (
        "A request reaches further than the requirement it came from. Refining an "
        "evidence requirement is allowed; enlarging one is refused."
    ),
    ACQUIRE_REQUIRED_EVIDENCE_LOST: (
        "A required evidence requirement is not represented by any request. Dropping "
        "one silently would answer a smaller question than the order asked."
    ),
    ACQUIRE_ROLE_NOT_MAPPABLE: (
        "A required role names no source class this vocabulary can express, so the "
        "request set would be a guess rather than a translation."
    ),
}

# ── Statuses ──────────────────────────────────────────────────────────────────
#: Bounded acquisition requests were written for a specified evidence contract.
#: It remains a request: see :func:`acquisition_authority`.
STATUS_READY = "ready"
#: The upstream evidence contract is not specified, so nothing is described.
STATUS_NOT_EVIDENCE_READY = "not_evidence_ready"
#: The upstream records do not hang together, or the translation would have had
#: to widen or narrow them.  Fail closed rather than proceed on a guess.
STATUS_INCONSISTENT_INPUT = "inconsistent_input"

ACQUISITION_STATUSES: tuple[str, ...] = (
    STATUS_READY,
    STATUS_NOT_EVIDENCE_READY,
    STATUS_INCONSISTENT_INPUT,
)

# ── Inconsistencies ───────────────────────────────────────────────────────────
INCONSISTENT_EVIDENCE_NOT_SPECIFIED = "evidence_contract_not_specified"
INCONSISTENT_WAITER_NOT_ROUTED = "waiter_decision_not_routed"
INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH = "source_fingerprint_mismatch"
INCONSISTENT_WORKFLOW_MISMATCH = "workflow_mismatch"
INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED = "capability_envelope_widened"
INCONSISTENT_REQUIRED_CAPABILITY_DROPPED = "required_capability_dropped"
INCONSISTENT_ACQUISITION_WIDENED = "acquisition_requirement_widened"
INCONSISTENT_REQUIRED_EVIDENCE_DROPPED = "required_evidence_dropped"
INCONSISTENT_UNMAPPABLE_ROLE = "unmappable_evidence_role"

ACQUISITION_INCONSISTENCIES: tuple[str, ...] = (
    INCONSISTENT_EVIDENCE_NOT_SPECIFIED,
    INCONSISTENT_WAITER_NOT_ROUTED,
    INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,
    INCONSISTENT_WORKFLOW_MISMATCH,
    INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED,
    INCONSISTENT_REQUIRED_CAPABILITY_DROPPED,
    INCONSISTENT_ACQUISITION_WIDENED,
    INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,
    INCONSISTENT_UNMAPPABLE_ROLE,
)

#: Roles whose source must be current at the moment it is used.  This is the
#: *expectation attached to a request*, not a verdict about evidence: nothing
#: has been obtained, so nothing has been certified.  It is a superset of
#: WAITER.2's ``CURRENT_AUTHORITY_ROLES`` because the two ask different
#: questions — WAITER.2 asks whether something may state what the system does
#: now, and a request asks whether the source has to be up to date when fetched.
CURRENT_AUTHORITY_EXPECTED_ROLES: frozenset[str] = frozenset({
    ROLE_IMPLEMENTATION_AUTHORITY,
    ROLE_INTERFACE_CONTRACT,
    ROLE_CONFIGURATION_AUTHORITY,
    ROLE_ARCHITECTURE_DESCRIPTION,
    ROLE_CURRENT_EXTERNAL_AUTHORITY,
})

# ── Bounds ────────────────────────────────────────────────────────────────────
MAX_REQUEST_REASONS = 4
MAX_REQUEST_ROLES = len(EVIDENCE_ROLES)
MAX_REQUEST_SOURCE_CLASSES = len(REQUESTABLE_SOURCE_CLASSES)
#: INPUT.1 preserves at most this many literal file paths, so every anchor the
#: order carried fits and none is ever dropped to satisfy a bound.
MAX_TARGET_ANCHORS = 32
MAX_ACTIVE_REQUESTS = len(EVIDENCE_DOMAINS)
MAX_DEFERRED_REQUESTS = len(EVIDENCE_DOMAINS)
MAX_EXCLUSIONS = len(NEVER_REQUESTED_SOURCE_CLASSES)
MAX_ACQUISITION_REASONS = len(ACQUISITION_REASONS)
MAX_ACQUISITION_INCONSISTENCIES = len(ACQUISITION_INCONSISTENCIES)


def acquisition_authority() -> dict[str, bool]:
    """Every authority ACQUIRE.1 declines to hold, in every status.

    Writing down that a future engine may look for runtime implementation is not
    permission to look, and ``status=ready`` is not permission either: it says
    the request set is well formed, and nothing else.  A later phase may consume
    this contract; it must obtain its own authority under its own gates.
    """
    return {
        "evidence_acquisition_authority": False,
        "repository_read_authority": False,
        "repository_traversal_authority": False,
        "repository_write_authority": False,
        "external_search_authority": False,
        "web_fetch_authority": False,
        "context_selection_authority": False,
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


def acquisition_guardrails() -> dict[str, bool]:
    """Every action ACQUIRE.1 did not perform while writing a request set."""
    return {
        "evidence_acquired": False,
        "repository_files_read": False,
        "repository_traversal_performed": False,
        "repository_membership_inspected": False,
        "manifest_consulted": False,
        "graph_consulted": False,
        "index_consulted": False,
        "ctx_select_called": False,
        "context_selection_performed": False,
        "read_set_generated": False,
        "file_paths_discovered": False,
        "network_called": False,
        "web_search_performed": False,
        "search_query_generated": False,
        "files_generated": False,
        "validation_executed": False,
        "command_executed": False,
        "planning_performed": False,
        "workflow_reselected": False,
        "evidence_contract_regenerated": False,
        "language_system_called": False,
        "provider_selected": False,
    }


# ── Records ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class AcquisitionBudget:
    """A finite ceiling, named rather than supplied.

    The four numbers are read out of :data:`BUDGET_PROFILE_LIMITS`.  There is no
    constructor argument for any of them, which is the whole point: a caller
    cannot write "unlimited", cannot write ``None``, and cannot write six
    thousand, because the record has nowhere to put a number.
    """

    profile: str

    def __post_init__(self) -> None:
        if self.profile not in BUDGET_PROFILES:
            raise ValueError(f"unsupported budget profile: {self.profile!r}")

    @property
    def max_candidates(self) -> int:
        return BUDGET_PROFILE_LIMITS[self.profile][0]

    @property
    def max_initial_sources(self) -> int:
        return BUDGET_PROFILE_LIMITS[self.profile][1]

    @property
    def max_total_bytes(self) -> int:
        return BUDGET_PROFILE_LIMITS[self.profile][2]

    @property
    def max_per_source_bytes(self) -> int:
        return BUDGET_PROFILE_LIMITS[self.profile][3]

    @property
    def active(self) -> bool:
        """Does this budget permit any acquisition at all?"""
        return self.max_candidates > 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "max_candidates": self.max_candidates,
            "max_initial_sources": self.max_initial_sources,
            "max_total_bytes": self.max_total_bytes,
            "max_per_source_bytes": self.max_per_source_bytes,
            "bounded": True,
        }


@dataclass(frozen=True, slots=True)
class TargetAnchor:
    """An identifier the user wrote, carried through unchanged.

    An anchor is not a discovered path and not a candidate.  It says the order
    named this thing; it says nothing about whether it exists, whether it can be
    read, whether it can be written, or whether reaching it is safe.  A future
    acquisition phase has to establish every one of those for itself.
    """

    value: str
    source: str = ANCHOR_SOURCE_EXPLICIT_INPUT_EVIDENCE

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("a target anchor must carry the identifier the user wrote")
        if self.source not in ANCHOR_SOURCES:
            raise ValueError(f"unsupported target anchor source: {self.source!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "source": self.source,
            "discovered": False,
            "existence_verified": False,
        }


@dataclass(frozen=True, slots=True)
class AcquisitionRequest:
    """One bounded request a future acquisition engine may be handed.

    Independent of every other request.  There is no ``depends_on``, no
    ``order``, no ``stage`` and no ``after``: the tier is evidence priority, and
    turning priority into a sequence would be a plan.
    """

    domain: str
    required_roles: tuple[str, ...]
    tier: str
    source_classes: tuple[str, ...]
    scope: str
    budget: AcquisitionBudget
    freshness: str
    require_current_authority: bool
    target_anchors: tuple[TargetAnchor, ...] = ()
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.domain not in EVIDENCE_DOMAINS:
            raise ValueError(f"unsupported evidence domain: {self.domain!r}")
        if self.tier not in EVIDENCE_TIERS:
            raise ValueError(f"unsupported evidence tier: {self.tier!r}")
        if self.tier == TIER_EXCLUDED_INITIALLY:
            raise ValueError(
                "an initially excluded class is an exclusion, never a request"
            )
        if self.scope not in REQUEST_SCOPES:
            raise ValueError(f"unsupported request scope: {self.scope!r}")
        if self.freshness not in FRESHNESS_REQUIREMENTS:
            raise ValueError(f"unsupported freshness requirement: {self.freshness!r}")
        if not isinstance(self.budget, AcquisitionBudget):
            raise TypeError("an acquisition request must carry an AcquisitionBudget")
        if not isinstance(self.require_current_authority, bool):
            raise TypeError("require_current_authority must be a bool")

        if not self.required_roles:
            raise ValueError(
                f"request for {self.domain!r} names no role it would satisfy"
            )
        _bounded_vocabulary(
            self.required_roles, EVIDENCE_ROLES, MAX_REQUEST_ROLES, "evidence role"
        )
        if not self.source_classes:
            raise ValueError(
                f"request for {self.domain!r} names no source class it may reach"
            )
        _bounded_vocabulary(
            self.source_classes,
            REQUESTABLE_SOURCE_CLASSES,
            MAX_REQUEST_SOURCE_CLASSES,
            "source class",
        )

        if len(self.target_anchors) > MAX_TARGET_ANCHORS:
            raise ValueError("target anchors exceed the supported bound")
        anchors = [item.value for item in self.target_anchors]
        if len(set(anchors)) != len(anchors):
            raise ValueError("each target anchor may be stated exactly once")

        if len(self.reasons) > MAX_REQUEST_REASONS:
            raise ValueError("acquisition request reasons exceed the supported bound")
        for reason in self.reasons:
            if reason not in ACQUISITION_REASONS:
                raise ValueError(f"unsupported acquisition reason: {reason!r}")
        if not self.reasons:
            raise ValueError(
                f"request for {self.domain!r} names no structured fact it came from"
            )

        # A tier decides whether anything may be obtained at all, and the budget
        # has to agree with it.  "Deferred, with a reconnaissance budget" is the
        # shape of a promotion, so it cannot be built.
        if self.tier in ACTIVE_TIERS and not self.budget.active:
            raise ValueError(
                f"required evidence at {self.tier!r} needs a budget that permits "
                "acquisition"
            )
        if self.tier not in ACTIVE_TIERS and self.budget.active:
            raise ValueError(
                f"{self.tier!r} evidence may not carry an active acquisition budget"
            )

    @property
    def key(self) -> tuple[str, str]:
        return (self.domain, self.tier)

    @property
    def active(self) -> bool:
        return self.tier in ACTIVE_TIERS

    def satisfies(self, domain: str, role: str) -> bool:
        return self.domain == domain and role in self.required_roles

    def as_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "required_roles": list(self.required_roles),
            "tier": self.tier,
            "source_classes": list(self.source_classes),
            "scope": self.scope,
            "budget": self.budget.as_dict(),
            "freshness": self.freshness,
            "require_current_authority": self.require_current_authority,
            "target_anchors": [item.as_dict() for item in self.target_anchors],
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class SourceExclusion:
    """A whole source class kept out of the initial acquisition set.

    Category-level policy, stated once, with no member ever named and no
    directory ever walked to find one.  A future repository selector enforces
    it; ACQUIRE.1 only writes it down.
    """

    source_class: str
    disposition: str
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.source_class not in NEVER_REQUESTED_SOURCE_CLASSES:
            raise ValueError(
                f"only restated material may be excluded, not {self.source_class!r}"
            )
        if self.disposition not in (TIER_DEFERRED, TIER_EXCLUDED_INITIALLY):
            raise ValueError(
                f"a source class may only be deferred or excluded, not {self.disposition!r}"
            )
        if len(self.reasons) > MAX_REQUEST_REASONS:
            raise ValueError("exclusion reasons exceed the supported bound")
        for reason in self.reasons:
            if reason not in ACQUISITION_REASONS:
                raise ValueError(f"unsupported acquisition reason: {reason!r}")
        if not self.reasons:
            raise ValueError(
                f"exclusion of {self.source_class!r} names no reason it was excluded"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_class": self.source_class,
            "disposition": self.disposition,
            "acquisition_budget": AcquisitionBudget(BUDGET_NONE).as_dict(),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class AcquisitionRequestContract:
    """What a future acquisition engine may be asked for, and nothing obtained.

    The record deliberately has no room for a discovered path, a candidate list,
    a query, a host, a retrieval result, a stage, a dependency, a provider or a
    compute choice.  Those are not fields ACQUIRE.1 declines to fill; they are
    fields it does not have.
    """

    status: str
    workflow: str | None = None
    evidence_scope: str | None = None
    requests: tuple[AcquisitionRequest, ...] = ()
    deferred_requests: tuple[AcquisitionRequest, ...] = ()
    exclusions: tuple[SourceExclusion, ...] = ()
    reasons: tuple[str, ...] = ()
    inconsistencies: tuple[str, ...] = ()
    source_evidence_fingerprint: str | None = None
    source_decision_fingerprint: str | None = None
    source_contract_fingerprint: str | None = None
    source_completion_fingerprint: str | None = None
    schema_version: str = ACQUISITION_CONTRACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in ACQUISITION_STATUSES:
            raise ValueError(f"unsupported acquisition status: {self.status!r}")
        if self.workflow is not None and self.workflow not in WORKFLOW_TARGETS:
            raise ValueError(f"unsupported workflow: {self.workflow!r}")
        if self.evidence_scope is not None and self.evidence_scope not in EVIDENCE_SCOPES:
            raise ValueError(f"unsupported evidence scope: {self.evidence_scope!r}")

        if len(self.requests) > MAX_ACTIVE_REQUESTS:
            raise ValueError("acquisition requests exceed the supported bound")
        if len(self.deferred_requests) > MAX_DEFERRED_REQUESTS:
            raise ValueError("deferred requests exceed the supported bound")
        if len(self.exclusions) > MAX_EXCLUSIONS:
            raise ValueError("exclusions exceed the supported bound")
        if len(self.reasons) > MAX_ACQUISITION_REASONS:
            raise ValueError("acquisition reasons exceed the supported bound")
        if len(self.inconsistencies) > MAX_ACQUISITION_INCONSISTENCIES:
            raise ValueError("inconsistencies exceed the supported bound")

        for request in self.requests:
            if not request.active:
                raise ValueError(
                    f"{request.tier!r} evidence belongs in deferred_requests"
                )
        for request in self.deferred_requests:
            if request.active:
                raise ValueError(
                    f"{request.tier!r} evidence is an active request, not a deferred one"
                )

        keys = [item.key for item in self.requests + self.deferred_requests]
        if len(set(keys)) != len(keys):
            raise ValueError(
                "each evidence domain and tier pair may be requested exactly once"
            )
        classes = [item.source_class for item in self.exclusions]
        if len(set(classes)) != len(classes):
            raise ValueError("each excluded source class may be stated exactly once")

        for reason in self.reasons:
            if reason not in ACQUISITION_REASONS:
                raise ValueError(f"unsupported acquisition reason: {reason!r}")
        for item in self.inconsistencies:
            if item not in ACQUISITION_INCONSISTENCIES:
                raise ValueError(f"unsupported inconsistency: {item!r}")
        if not self.reasons:
            raise ValueError("every acquisition contract must state at least one reason")

        if self.status == STATUS_READY:
            if self.workflow is None or self.evidence_scope is None:
                raise ValueError(
                    "a ready contract must name the workflow it was written for and "
                    "the evidence scope its requests were written against"
                )
            if not self.requests:
                raise ValueError("a ready contract must state at least one request")
            if self.inconsistencies:
                raise ValueError("a ready contract may not carry inconsistencies")
            if self.source_evidence_fingerprint is None:
                raise ValueError(
                    "a ready contract must fingerprint the evidence contract it "
                    "translated"
                )
        else:
            if self.workflow is not None or self.evidence_scope is not None:
                raise ValueError(
                    f"status {self.status!r} describes no workflow and no evidence scope"
                )
            if self.requests or self.deferred_requests or self.exclusions:
                raise ValueError(
                    "an order whose evidence could not be requested is not described: "
                    "ACQUIRE.1 does not guess what an unspecified contract would need"
                )
            if not self.inconsistencies:
                raise ValueError("a refused contract must state what did not hang together")

    # ── derived, authority-free facts ────────────────────────────────────────
    @property
    def ready(self) -> bool:
        return self.status == STATUS_READY

    @property
    def human_approval_required(self) -> bool:
        """Always true.  A request is a report, never a go-ahead."""
        return True

    def all_requests(self) -> tuple[AcquisitionRequest, ...]:
        return self.requests + self.deferred_requests

    def domains(self) -> tuple[str, ...]:
        present = {item.domain for item in self.all_requests()}
        return tuple(domain for domain in EVIDENCE_DOMAINS if domain in present)

    def requests_domain(self, domain: str) -> bool:
        if domain not in EVIDENCE_DOMAINS:
            raise KeyError(f"unsupported evidence domain: {domain!r}")
        return any(item.domain == domain for item in self.requests)

    def request_for(self, domain: str, tier: str) -> AcquisitionRequest | None:
        for item in self.all_requests():
            if item.domain == domain and item.tier == tier:
                return item
        return None

    def source_classes(self) -> tuple[str, ...]:
        present = {
            source_class
            for item in self.requests
            for source_class in item.source_classes
        }
        return tuple(item for item in ACQUISITION_SOURCE_CLASSES if item in present)

    def excluded_classes(self) -> tuple[str, ...]:
        return tuple(
            item.source_class
            for item in self.exclusions
            if item.disposition == TIER_EXCLUDED_INITIALLY
        )

    def deferred_classes(self) -> tuple[str, ...]:
        return tuple(
            item.source_class
            for item in self.exclusions
            if item.disposition == TIER_DEFERRED
        )

    def target_anchors(self) -> tuple[str, ...]:
        return tuple(
            anchor.value for item in self.all_requests() for anchor in item.target_anchors
        )

    def budget_summary(self) -> dict[str, Any]:
        """The ceilings added up.  Derived, so it can never disagree with them."""
        return {
            "active_requests": len(self.requests),
            "deferred_requests": len(self.deferred_requests),
            "excluded_source_classes": len(self.exclusions),
            "max_candidates_total": sum(
                item.budget.max_candidates for item in self.requests
            ),
            "max_initial_sources_total": sum(
                item.budget.max_initial_sources for item in self.requests
            ),
            "max_total_bytes_total": sum(
                item.budget.max_total_bytes for item in self.requests
            ),
            "deferred_candidate_budget": sum(
                item.budget.max_candidates for item in self.deferred_requests
            ),
            "excluded_candidate_budget": 0,
            "bounded": True,
            "unbounded_request_present": False,
        }

    def reason_descriptions(self) -> tuple[str, ...]:
        return tuple(ACQUISITION_REASON_DESCRIPTIONS[reason] for reason in self.reasons)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "status": self.status,
            "workflow": self.workflow,
            "evidence_scope": self.evidence_scope,
            "requests": [item.as_dict() for item in self.requests],
            "deferred_requests": [item.as_dict() for item in self.deferred_requests],
            "exclusions": [item.as_dict() for item in self.exclusions],
            "budget_summary": self.budget_summary(),
            "reasons": [
                {"code": reason, "description": ACQUISITION_REASON_DESCRIPTIONS[reason]}
                for reason in self.reasons
            ],
            "inconsistencies": list(self.inconsistencies),
            "source_evidence_fingerprint": self.source_evidence_fingerprint,
            "source_decision_fingerprint": self.source_decision_fingerprint,
            "source_contract_fingerprint": self.source_contract_fingerprint,
            "source_completion_fingerprint": self.source_completion_fingerprint,
            "human_approval_required": self.human_approval_required,
            "note": (
                "These are acquisition requests, not evidence and not permission to "
                "obtain any. Nothing was read, traversed, searched, selected or "
                "retrieved, and no request grants the authority to do so."
            ),
            "authority": acquisition_authority(),
            "guardrails": acquisition_guardrails(),
        }


def _bounded_vocabulary(
    values: tuple[str, ...],
    vocabulary: tuple[str, ...],
    bound: int,
    label: str,
) -> None:
    """Distinct, inside the vocabulary, in canonical order, within the bound."""
    if len(values) > bound:
        raise ValueError(f"{label}s exceed the supported bound")
    if len(set(values)) != len(values):
        raise ValueError(f"each {label} may be stated exactly once")
    for value in values:
        if value not in vocabulary:
            raise ValueError(f"unsupported {label}: {value!r}")
    ordered = tuple(item for item in vocabulary if item in set(values))
    if values != ordered:
        raise ValueError(f"{label}s must be stated in the canonical vocabulary order")


__all__ = [
    "ACQUIRE_ARCHITECTURE_RECONNAISSANCE_REQUESTED",
    "ACQUIRE_BUDGET_BOUNDED_BY_SCOPE_AND_TIER",
    "ACQUIRE_CAPABILITY_ENVELOPE_VIOLATED",
    "ACQUIRE_EVIDENCE_NOT_READY",
    "ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED",
    "ACQUIRE_EXTERNAL_AUTHORITY_REQUESTED",
    "ACQUIRE_HISTORICAL_MATERIAL_DEFERRED",
    "ACQUIRE_REPOSITORY_EVIDENCE_REQUESTED",
    "ACQUIRE_REQUIRED_CAPABILITY_LOST",
    "ACQUIRE_REQUIRED_EVIDENCE_LOST",
    "ACQUIRE_REQUIREMENT_WIDENED",
    "ACQUIRE_RESTATED_MATERIAL_EXCLUDED",
    "ACQUIRE_ROLE_NOT_MAPPABLE",
    "ACQUIRE_SOURCE_INTEGRITY_FAILED",
    "ACQUIRE_SUPPLIED_MATERIAL_ALREADY_IN_HAND",
    "ACQUIRE_UNRELATED_VALIDATION_DEFERRED",
    "ACQUIRE_VALIDATION_EVIDENCE_REQUESTED",
    "ACQUISITION_CONTRACT_SCHEMA_VERSION",
    "ACQUISITION_INCONSISTENCIES",
    "ACQUISITION_REASONS",
    "ACQUISITION_REASON_DESCRIPTIONS",
    "ACQUISITION_SOURCE_CLASSES",
    "ACQUISITION_STATUSES",
    "ANCHOR_SOURCES",
    "ANCHOR_SOURCE_EXPLICIT_INPUT_EVIDENCE",
    "BUDGET_BOUNDED",
    "BUDGET_EXISTING_CONTEXT",
    "BUDGET_EXTERNAL_BOUNDED",
    "BUDGET_NONE",
    "BUDGET_PROFILES",
    "BUDGET_PROFILE_LIMITS",
    "BUDGET_RECONNAISSANCE",
    "BUDGET_SECONDARY_VERIFICATION",
    "CURRENT_AUTHORITY_EXPECTED_ROLES",
    "FRESHNESS_CURRENT",
    "FRESHNESS_HISTORICAL",
    "FRESHNESS_NOT_APPLICABLE",
    "FRESHNESS_REQUIREMENTS",
    "INCONSISTENT_ACQUISITION_WIDENED",
    "INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED",
    "INCONSISTENT_EVIDENCE_NOT_SPECIFIED",
    "INCONSISTENT_REQUIRED_CAPABILITY_DROPPED",
    "INCONSISTENT_REQUIRED_EVIDENCE_DROPPED",
    "INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH",
    "INCONSISTENT_UNMAPPABLE_ROLE",
    "INCONSISTENT_WAITER_NOT_ROUTED",
    "INCONSISTENT_WORKFLOW_MISMATCH",
    "MAX_CANDIDATES_CEILING",
    "MAX_INITIAL_SOURCES_CEILING",
    "MAX_PER_SOURCE_BYTES_CEILING",
    "MAX_TARGET_ANCHORS",
    "MAX_TOTAL_BYTES_CEILING",
    "NEVER_REQUESTED_SOURCE_CLASSES",
    "PHASE_ID",
    "REQUESTABLE_SOURCE_CLASSES",
    "REQUEST_SCOPES",
    "REQUEST_SCOPE_BOUNDED_REPOSITORY",
    "REQUEST_SCOPE_BROAD_REPOSITORY_RECONNAISSANCE",
    "REQUEST_SCOPE_EXISTING_CONTEXT",
    "REQUEST_SCOPE_EXTERNAL_INFORMATION",
    "SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC",
    "SOURCE_CLASS_AUTHORITATIVE_EXTERNAL_SOURCE",
    "SOURCE_CLASS_CONFIGURATION",
    "SOURCE_CLASS_DEPENDENCY_MANIFEST",
    "SOURCE_CLASS_DUPLICATE_RENDERING",
    "SOURCE_CLASS_GENERATED_ARTIFACT",
    "SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL",
    "SOURCE_CLASS_INTERFACE_DEFINITION",
    "SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE",
    "SOURCE_CLASS_RUNTIME_IMPLEMENTATION",
    "SOURCE_CLASS_SNAPSHOT",
    "SOURCE_CLASS_SUPPLIED_CONTEXT",
    "SOURCE_CLASS_SURROUNDING_IMPLEMENTATION",
    "SOURCE_CLASS_TEMPORARY_ARTIFACT",
    "SOURCE_CLASS_VALIDATION_TEST",
    "STATUS_INCONSISTENT_INPUT",
    "STATUS_NOT_EVIDENCE_READY",
    "STATUS_READY",
    "AcquisitionBudget",
    "AcquisitionRequest",
    "AcquisitionRequestContract",
    "SourceExclusion",
    "TargetAnchor",
    "acquisition_authority",
    "acquisition_guardrails",
]
