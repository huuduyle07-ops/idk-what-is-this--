"""ACQUIRE.2 — deterministic candidate eligibility policy.

Given one ready acquisition request and one authorized inventory snapshot, this
module decides which members are eligible, at which tier, and where the pool
stops:

    AcquisitionRequestContract + CandidateInventory
        -> EligibilityOutcome

Four rules do the real work, and every one of them is a constant.

**Classification is metadata, never inference.**  A member becomes a source
class because something already established says so: a generated marker, a hard
exclusion, a known test location, a known manifest name, the canonical parser's
verdict that this is code, or a class an authorized inventory builder declared.
Anything else is ``unknown``, and unknown never discharges a required role.
``.py`` is not implementation authority and ``.md`` is not architecture
authority — those are claims about *relevance* and *currency*, and nobody here
has opened a file to check either.

**Exclusions and deferrals are hard.**  A class the request excluded cannot
reach the active pool, and there is no score, hint or anchor that readmits it.
A deferred class stays in the deferred pool with no budget.

**Narrowing only.**  A class the request did not ask for makes a member
ineligible.  There is no rule here that invents a class, promotes a tier, or
reaches a domain the request never named.

**The ceiling is the ceiling.**  Ordering is deterministic — anchors first, then
the request's own source-class priority, then canonical identifier — and the
pool stops at the number ACQUIRE.1 wrote down.  Byte ceilings are enforced from
supplied size metadata; a member whose size nobody recorded is refused rather
than assumed small.

The module is stdlib-only and pure.  It reads no files, walks no directory,
contacts no service, calls no language system, executes no selector, ranks
nothing by relevance, acquires no evidence, and grants no authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.acquisition_request import (
    ACQUISITION_SOURCE_CLASSES,
    NEVER_REQUESTED_SOURCE_CLASSES,
    REQUESTABLE_SOURCE_CLASSES,
    SOURCE_CLASS_AUTHORITATIVE_EXTERNAL_SOURCE,
    SOURCE_CLASS_CONFIGURATION,
    SOURCE_CLASS_DEPENDENCY_MANIFEST,
    SOURCE_CLASS_DUPLICATE_RENDERING,
    SOURCE_CLASS_GENERATED_ARTIFACT,
    SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,
    SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
    SOURCE_CLASS_SNAPSHOT,
    SOURCE_CLASS_SUPPLIED_CONTEXT,
    SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,
    SOURCE_CLASS_TEMPORARY_ARTIFACT,
    SOURCE_CLASS_VALIDATION_TEST,
    AcquisitionRequest,
    AcquisitionRequestContract,
)
from core.acquisition_policy import SOURCE_CLASSES_BY_ROLE
from core.candidate_eligibility import (
    CANDIDATE_SUPPLIED_CONTEXT_REFERENCE,
    CLASSIFICATION_BASES,
    ENVELOPE_VIOLATIONS,
    INCONSISTENT_ELIGIBILITY_WIDENED,
    INELIGIBILITY_REASONS,
    BASIS_EXPLICIT_TARGET_ANCHOR,
    BASIS_INVENTORY_DECLARED_CLASS,
    BASIS_INVENTORY_DUPLICATE_MARKER,
    BASIS_INVENTORY_GENERATED_MARKER,
    BASIS_INVENTORY_HARD_EXCLUSION,
    BASIS_INVENTORY_PARSER_SUPPORT,
    BASIS_INVENTORY_VENDOR_MARKER,
    BASIS_KNOWN_CONFIGURATION_NAME,
    BASIS_KNOWN_HISTORICAL_LOCATION,
    BASIS_KNOWN_MANIFEST_NAME,
    BASIS_KNOWN_SNAPSHOT_LOCATION,
    BASIS_KNOWN_TEMPORARY_LOCATION,
    BASIS_KNOWN_TEST_LOCATION,
    CANDIDATE_DEFERRED_UPSTREAM,
    CANDIDATE_EXPLICIT_TARGET_MATCHED,
    CANDIDATE_INVENTORY_MEMBER,
    CANDIDATE_REASONS,
    CANDIDATE_TIER_PRESERVED,
    CLASSIFICATION_CLASSIFIED,
    CLASSIFICATION_UNKNOWN,
    INELIGIBLE_CANDIDATE_CEILING_REACHED,
    INELIGIBLE_CLASSIFICATION_UNKNOWN,
    INELIGIBLE_HARD_EXCLUDED_BY_INVENTORY,
    INELIGIBLE_OUTSIDE_REPOSITORY,
    INELIGIBLE_PER_SOURCE_BYTES_EXCEEDED,
    INELIGIBLE_SIZE_UNKNOWN,
    INELIGIBLE_SOURCE_CLASS_EXCLUDED,
    INELIGIBLE_SOURCE_CLASS_NOT_REQUESTED,
    INELIGIBLE_TOTAL_BYTES_EXHAUSTED,
    VIOLATION_BUDGET_EXCEEDED,
    VIOLATION_DUPLICATE_CANDIDATE,
    VIOLATION_EXCLUDED_SOURCE_CLASS,
    VIOLATION_OUTSIDE_ENVELOPE,
    VIOLATION_WRONG_INVENTORY,
    VIOLATION_WRONG_TIER,
    CandidateClassification,
    EligibleCandidate,
    ExclusionSummary,
    ExternalCandidateEnvelope,
    SelectorEnvelope,
)
from core.candidate_inventory import CandidateInventory, InventoryMember
from core.evidence_requirements import (
    ACTIVE_TIERS,
    TIER_REQUIRED_PRIMARY,
    TIER_REQUIRED_SECONDARY,
    DOMAIN_DIRECT_CONTEXT,
    DOMAIN_EXTERNAL_INFORMATION,
    DOMAIN_HISTORICAL_CONTEXT,
    DOMAIN_REPOSITORY,
    DOMAIN_VALIDATION_ARTIFACTS,
    EVIDENCE_ROLES,
    TIER_DEFERRED,
)


PHASE_ID = "ACQUIRE.2"

#: How many deferred members the receipt will name.
#:
#: Deferred material has an *acquisition* budget of zero — that is what deferred
#: means, and ACQUIRE.1 wrote it down that way.  It does not follow that the
#: deferred pool is empty: knowing which members were set aside is the whole
#: value of setting them aside deliberately rather than losing them.  So the
#: pool is listed and separately bounded, and not one byte of it may be fetched.
MAX_DEFERRED_CANDIDATES = 64

# ── Repository-location policy ────────────────────────────────────────────────
#: Deliberately small, deliberately conservative, and deliberately about
#: *location and name* rather than extension.  Every entry names a convention
#: strong enough that treating it as fact costs nothing when it is wrong: a test
#: mistaken for a test is still a test, and a snapshot mistaken for a snapshot is
#: still kept out of the initial set.
#:
#: Nothing here promotes anything into authority.  The rules that could —
#: interface definition, authoritative architecture description, registration
#: surface — have no location policy at all, because no directory name has ever
#: made a document authoritative.
_TEST_DIRECTORY_SEGMENTS: frozenset[str] = frozenset({"test", "tests", "testing"})
_TEST_NAME_PREFIX = "test_"
_TEST_NAME_MARKER = "_test."

_SNAPSHOT_DIRECTORY_SEGMENTS: frozenset[str] = frozenset(
    {"snapshot", "snapshots", "__snapshots__"}
)
_SNAPSHOT_NAME_SUFFIXES: tuple[str, ...] = (".snap", ".snapshot")

_TEMPORARY_DIRECTORY_SEGMENTS: frozenset[str] = frozenset(
    {"tmp", ".tmp", "temp", ".temp", "scratch", "tmp_tests"}
)

#: Historical location is a *demotion*, so a conservative rule is safe here in a
#: way it would not be anywhere else.  ``docs/designs`` is deliberately absent:
#: a current design note is not history.
_HISTORICAL_DIRECTORY_SEGMENTS: frozenset[str] = frozenset(
    {"archive", "archived", "history", "proposals", "rejected", "superseded", "deprecated"}
)

#: Dependency manifests, by the names package ecosystems actually use.
_MANIFEST_NAMES: frozenset[str] = frozenset(
    {
        "cargo.toml",
        "go.mod",
        "go.sum",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "poetry.lock",
        "pyproject.toml",
        "requirements.txt",
        "yarn.lock",
    }
)

#: Configuration, by name.  Kept apart from manifests because the roles differ:
#: a manifest states what the system depends on, configuration states how it is
#: wired.
_CONFIGURATION_NAMES: frozenset[str] = frozenset(
    {
        ".env.example",
        ".env.sample",
        ".env.template",
        "docker-compose.yaml",
        "docker-compose.yml",
        "dockerfile",
        "pytest.ini",
        "setup.cfg",
        "tox.ini",
    }
)

#: Classes a location or a name may establish on its own.  Everything outside
#: this set needs an inventory declaration, and gets ``unknown`` without one.
LOCATION_ASSIGNABLE_CLASSES: frozenset[str] = frozenset(
    {
        SOURCE_CLASS_VALIDATION_TEST,
        SOURCE_CLASS_DEPENDENCY_MANIFEST,
        SOURCE_CLASS_CONFIGURATION,
        SOURCE_CLASS_SNAPSHOT,
        SOURCE_CLASS_TEMPORARY_ARTIFACT,
        SOURCE_CLASS_GENERATED_ARTIFACT,
        SOURCE_CLASS_DUPLICATE_RENDERING,
        SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,
        SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
        SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,
    }
)

#: Which domain each source class belongs to, so a class never lands in a pool
#: whose domain the request did not license.  Total over the acquisition
#: vocabulary, checked at import.
SOURCE_CLASS_DOMAINS: dict[str, str] = {
    SOURCE_CLASS_SUPPLIED_CONTEXT: DOMAIN_DIRECT_CONTEXT,
    SOURCE_CLASS_RUNTIME_IMPLEMENTATION: DOMAIN_REPOSITORY,
    SOURCE_CLASS_SURROUNDING_IMPLEMENTATION: DOMAIN_REPOSITORY,
    "interface_definition": DOMAIN_REPOSITORY,
    SOURCE_CLASS_CONFIGURATION: DOMAIN_REPOSITORY,
    SOURCE_CLASS_DEPENDENCY_MANIFEST: DOMAIN_REPOSITORY,
    "authoritative_architecture_doc": DOMAIN_REPOSITORY,
    "plugin_or_registration_surface": DOMAIN_REPOSITORY,
    SOURCE_CLASS_VALIDATION_TEST: DOMAIN_VALIDATION_ARTIFACTS,
    SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL: DOMAIN_HISTORICAL_CONTEXT,
    SOURCE_CLASS_AUTHORITATIVE_EXTERNAL_SOURCE: DOMAIN_EXTERNAL_INFORMATION,
    SOURCE_CLASS_GENERATED_ARTIFACT: DOMAIN_REPOSITORY,
    SOURCE_CLASS_SNAPSHOT: DOMAIN_REPOSITORY,
    SOURCE_CLASS_TEMPORARY_ARTIFACT: DOMAIN_REPOSITORY,
    SOURCE_CLASS_DUPLICATE_RENDERING: DOMAIN_REPOSITORY,
}

if tuple(SOURCE_CLASS_DOMAINS) != ACQUISITION_SOURCE_CLASSES:  # pragma: no cover
    raise RuntimeError("every source class must state the domain it belongs to")

#: The inverse of ACQUIRE.1's role table: which roles a class can serve.
ROLES_BY_SOURCE_CLASS: dict[str, tuple[str, ...]] = {
    source_class: tuple(
        role
        for role in EVIDENCE_ROLES
        if source_class in SOURCE_CLASSES_BY_ROLE.get(role, ())
    )
    for source_class in ACQUISITION_SOURCE_CLASSES
}


def _segments(identifier: str) -> tuple[str, ...]:
    return tuple(part for part in identifier.casefold().split("/") if part)


def _basename(identifier: str) -> str:
    segments = _segments(identifier)
    return segments[-1] if segments else ""


def is_test_location(identifier: str) -> bool:
    """Does this identifier sit where a project puts its tests?

    Purely lexical, and narrow on purpose: a directory segment the inventory
    spells ``test``/``tests``/``testing``, or a final segment starting
    ``test_`` or containing ``_test.``.  ``core/text_utils.py`` is not a test.
    """
    segments = _segments(identifier)
    if not segments:
        return False
    if any(part in _TEST_DIRECTORY_SEGMENTS for part in segments[:-1]):
        return True
    final = segments[-1]
    return final.startswith(_TEST_NAME_PREFIX) or _TEST_NAME_MARKER in final


def is_snapshot_location(identifier: str) -> bool:
    segments = _segments(identifier)
    if any(part in _SNAPSHOT_DIRECTORY_SEGMENTS for part in segments[:-1]):
        return True
    final = _basename(identifier)
    return final.endswith(_SNAPSHOT_NAME_SUFFIXES)


def is_temporary_location(identifier: str) -> bool:
    return any(part in _TEMPORARY_DIRECTORY_SEGMENTS for part in _segments(identifier))


def is_historical_location(identifier: str) -> bool:
    return any(part in _HISTORICAL_DIRECTORY_SEGMENTS for part in _segments(identifier))


def is_manifest_name(identifier: str) -> bool:
    return _basename(identifier) in _MANIFEST_NAMES


def is_configuration_name(identifier: str) -> bool:
    return _basename(identifier) in _CONFIGURATION_NAMES


def classify_member(
    member: InventoryMember,
    *,
    target_anchor: bool = False,
) -> tuple[CandidateClassification, ...]:
    """Which source classes this member belongs to, each with its basis.

    Ordered by the canonical source-class vocabulary, so two runs over the same
    member always produce the same tuple.  An empty tuple means ``unknown``, and
    unknown is a safe answer: it simply cannot discharge a required role.

    Exclusion-bearing classes are returned alongside everything else.  Deciding
    that an excluded class *wins* is the caller's job, and it is done in one
    place — :func:`derive_eligibility` — so the rule cannot be forgotten in a
    second one.
    """
    if not isinstance(member, InventoryMember):
        raise TypeError("classify_member requires an InventoryMember")

    assigned: dict[str, list[str]] = {}

    def assign(source_class: str, basis: str) -> None:
        bases = assigned.setdefault(source_class, [])
        if basis not in bases:
            bases.append(basis)

    # ── what keeps a member out, established first ───────────────────────────
    if member.hard_excluded:
        assign(SOURCE_CLASS_TEMPORARY_ARTIFACT, BASIS_INVENTORY_HARD_EXCLUSION)
    if is_temporary_location(member.identifier):
        assign(SOURCE_CLASS_TEMPORARY_ARTIFACT, BASIS_KNOWN_TEMPORARY_LOCATION)
    if member.generated:
        assign(SOURCE_CLASS_GENERATED_ARTIFACT, BASIS_INVENTORY_GENERATED_MARKER)
    if is_snapshot_location(member.identifier):
        assign(SOURCE_CLASS_SNAPSHOT, BASIS_KNOWN_SNAPSHOT_LOCATION)
    if member.restates_another_member:
        assign(SOURCE_CLASS_DUPLICATE_RENDERING, BASIS_INVENTORY_DUPLICATE_MARKER)
    # A vendored copy is code somebody else wrote.  It gets no implementation
    # class below, and the marker is the reason why — recorded, not inferred.
    _ = BASIS_INVENTORY_VENDOR_MARKER

    # ── what a location or a name may establish ──────────────────────────────
    if is_test_location(member.identifier):
        assign(SOURCE_CLASS_VALIDATION_TEST, BASIS_KNOWN_TEST_LOCATION)
    if is_manifest_name(member.identifier):
        assign(SOURCE_CLASS_DEPENDENCY_MANIFEST, BASIS_KNOWN_MANIFEST_NAME)
    if is_configuration_name(member.identifier):
        assign(SOURCE_CLASS_CONFIGURATION, BASIS_KNOWN_CONFIGURATION_NAME)
    if is_historical_location(member.identifier):
        assign(SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL, BASIS_KNOWN_HISTORICAL_LOCATION)

    # ── code, as the canonical parser already classified it ──────────────────
    # A vendored copy is code somebody else wrote; treating it as this system's
    # runtime implementation would be a claim about the system, not about the
    # file.  A test is code too, and it is already classed as a test.
    if (
        member.is_code
        and not member.vendor
        and not member.generated
        and not is_test_location(member.identifier)
    ):
        assign(SOURCE_CLASS_RUNTIME_IMPLEMENTATION, BASIS_INVENTORY_PARSER_SUPPORT)
        assign(SOURCE_CLASS_SURROUNDING_IMPLEMENTATION, BASIS_INVENTORY_PARSER_SUPPORT)

    # ── what an authorized inventory builder asserted ────────────────────────
    # The only route to interface definitions, authoritative architecture
    # description and registration surfaces.  No filename implies any of them.
    if member.declared_source_class is not None:
        assign(member.declared_source_class, BASIS_INVENTORY_DECLARED_CLASS)

    if target_anchor and assigned:
        for bases in assigned.values():
            if BASIS_EXPLICIT_TARGET_ANCHOR not in bases:
                bases.append(BASIS_EXPLICIT_TARGET_ANCHOR)

    return tuple(
        CandidateClassification(
            source_class=source_class,
            basis=_ordered_basis(assigned[source_class]),
        )
        for source_class in ACQUISITION_SOURCE_CLASSES
        if source_class in assigned
    )


def _ordered_basis(values: list[str]) -> tuple[str, ...]:
    present = set(values)
    return tuple(item for item in CLASSIFICATION_BASES if item in present)


def classification_status(
    classifications: tuple[CandidateClassification, ...],
) -> str:
    return CLASSIFICATION_CLASSIFIED if classifications else CLASSIFICATION_UNKNOWN


def roles_for_classes(source_classes: tuple[str, ...]) -> tuple[str, ...]:
    """Every role these classes may serve, in canonical order."""
    present: set[str] = set()
    for source_class in source_classes:
        present.update(ROLES_BY_SOURCE_CLASS.get(source_class, ()))
    return tuple(role for role in EVIDENCE_ROLES if role in present)


@dataclass(frozen=True, slots=True)
class EligibilityOutcome:
    """The pools one acquisition request and one inventory produce."""

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

    def all_candidates(self) -> tuple[EligibleCandidate, ...]:
        return (
            self.active_candidates + self.secondary_candidates + self.deferred_candidates
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "active_candidates": [item.as_dict() for item in self.active_candidates],
            "secondary_candidates": [
                item.as_dict() for item in self.secondary_candidates
            ],
            "deferred_candidates": [item.as_dict() for item in self.deferred_candidates],
            "exclusion_summary": [item.as_dict() for item in self.exclusion_summary],
        }


def requires_inventory(contract: AcquisitionRequestContract) -> bool:
    """Does this request need somebody to have described a repository first?"""
    if not isinstance(contract, AcquisitionRequestContract):
        raise TypeError("requires_inventory requires an AcquisitionRequestContract")
    return any(
        SOURCE_CLASS_DOMAINS[source_class] != DOMAIN_DIRECT_CONTEXT
        and SOURCE_CLASS_DOMAINS[source_class] != DOMAIN_EXTERNAL_INFORMATION
        for request in contract.all_requests()
        for source_class in request.source_classes
    )


def _candidate_sort_key(
    identifier: str,
    classes: tuple[str, ...],
    anchor: bool,
    request: AcquisitionRequest,
) -> tuple[int, int, str, str]:
    """Deterministic, and made only of things the request already decided.

    Anchors the user wrote come first.  Then the request's own source-class
    order, which ACQUIRE.1 already fixed canonically.  Then the identifier.
    There is no relevance in here, no score, and nothing that could differ
    between two machines.
    """
    requested = tuple(request.source_classes)
    priority = min(
        (requested.index(item) for item in classes if item in requested),
        default=len(requested),
    )
    return (0 if anchor else 1, priority, identifier.casefold(), identifier)


def derive_eligibility(
    contract: AcquisitionRequestContract,
    inventory: CandidateInventory | None,
) -> EligibilityOutcome:
    """Decide which inventory members are eligible, deterministically.

    Every input is a structured fact ACQUIRE.1 or an authorized inventory
    builder already established.  Two runs over the same request and the same
    snapshot always produce the same pools, on any machine, at any time, with
    any repository state and no network.

    Nothing is opened.  Nothing is ranked by relevance.  Nothing is acquired.
    """
    if not isinstance(contract, AcquisitionRequestContract):
        raise TypeError("derive_eligibility requires an AcquisitionRequestContract")
    if inventory is not None and not isinstance(inventory, CandidateInventory):
        raise TypeError("derive_eligibility requires a CandidateInventory or None")
    if not contract.ready:
        raise ValueError("only a ready acquisition request can be enumerated")

    excluded_classes = set(contract.excluded_classes()) | set(contract.deferred_classes())
    anchors = {anchor.value for anchor in _all_anchors(contract)}
    matched_anchors: set[str] = set()

    pools: dict[str, list[EligibleCandidate]] = {}
    envelopes: list[SelectorEnvelope] = []
    external: list[ExternalCandidateEnvelope] = []
    # One member, one verdict.  A member the repository request declined and the
    # validation request accepted is eligible, not excluded, so ineligibility is
    # settled once at the end rather than counted per request.
    rejections: dict[str, set[str]] = {}
    admitted: set[str] = set()
    candidate_limit = 0
    source_limit = 0
    byte_limit = 0
    byte_total = 0
    unsatisfied: set[str] = set()

    for request in contract.all_requests():
        candidate_limit += request.budget.max_candidates
        source_limit += request.budget.max_initial_sources
        byte_limit += request.budget.max_total_bytes

        if request.domain == DOMAIN_DIRECT_CONTEXT:
            pools.setdefault(request.tier, []).append(
                _direct_context_candidate(contract, request)
            )
            continue

        if request.domain == DOMAIN_EXTERNAL_INFORMATION:
            external.append(
                ExternalCandidateEnvelope(
                    required_role=request.required_roles[0],
                    allowed_source_classes=request.source_classes,
                    freshness=request.freshness,
                    candidate_budget=request.budget.max_candidates,
                    source_budget_reserved=request.budget.max_initial_sources,
                    acquisition_request_fingerprint=(
                        contract.source_evidence_fingerprint or ""
                    ),
                )
            )
            continue

        selected, consumed_bytes, request_unsatisfied = _repository_candidates(
            request,
            contract,
            inventory,
            excluded_classes=excluded_classes,
            # ACQUIRE.1 attached each anchor to one request. Letting it act as
            # an anchor for the others would put the same identifier in two
            # pools and give the user's README a role in the test request.
            anchors={item.value for item in request.target_anchors},
            matched_anchors=matched_anchors,
            rejections=rejections,
        )
        byte_total += consumed_bytes
        admitted.update(item.identifier for item in selected)
        # Only an *active* tier states a need. Deferred material is on the
        # record and out of the work, so its roles are not owed by anybody yet.
        if request.tier in ACTIVE_TIERS:
            unsatisfied.update(request_unsatisfied)
        pools.setdefault(request.tier, []).extend(selected)
        envelopes.append(
            SelectorEnvelope(
                domain=request.domain,
                tier=request.tier,
                allowed_candidate_identifiers=tuple(
                    sorted(
                        (item.identifier for item in selected),
                        key=lambda value: (value.casefold(), value),
                    )
                ),
                allowed_roles=request.required_roles,
                allowed_source_classes=request.source_classes,
                excluded_source_classes=tuple(
                    item
                    for item in NEVER_REQUESTED_SOURCE_CLASSES
                    if item in excluded_classes
                ),
                candidate_budget_remaining=max(
                    request.budget.max_candidates - len(selected), 0
                ),
                source_budget_reserved=request.budget.max_initial_sources,
                byte_budget_remaining=max(
                    request.budget.max_total_bytes - consumed_bytes, 0
                ),
                acquisition_request_fingerprint=(
                    contract.source_evidence_fingerprint or ""
                ),
                inventory_fingerprint=(
                    inventory.fingerprint() if inventory is not None else None
                ),
                repository_identity=(
                    inventory.repository_identity if inventory is not None else None
                ),
            )
        )

    counts: dict[str, int] = {}
    for identifier, reasons in rejections.items():
        if identifier in admitted:
            continue
        for reason in INELIGIBILITY_REASONS:
            if reason in reasons:
                counts[reason] = counts.get(reason, 0) + 1
                break

    return EligibilityOutcome(
        active_candidates=tuple(pools.get(TIER_REQUIRED_PRIMARY, ())),
        secondary_candidates=tuple(pools.get(TIER_REQUIRED_SECONDARY, ())),
        deferred_candidates=tuple(pools.get(TIER_DEFERRED, ())),
        exclusion_summary=tuple(
            ExclusionSummary(reason=reason, count=counts[reason])
            for reason in _ordered_ineligibility(counts)
        ),
        selector_envelopes=tuple(envelopes),
        external_envelopes=tuple(external),
        unmatched_target_anchors=tuple(sorted(anchors - matched_anchors)),
        unsatisfied_required_roles=tuple(
            role for role in EVIDENCE_ROLES if role in unsatisfied
        ),
        candidate_limit=candidate_limit,
        source_limit_reserved=source_limit,
        byte_limit=byte_limit,
        byte_eligible_total=byte_total,
    )


def _ordered_ineligibility(counts: dict[str, int]) -> tuple[str, ...]:
    return tuple(reason for reason in INELIGIBILITY_REASONS if reason in counts)


def _all_anchors(contract: AcquisitionRequestContract):
    for request in contract.all_requests():
        for anchor in request.target_anchors:
            yield anchor


def _direct_context_candidate(
    contract: AcquisitionRequestContract,
    request: AcquisitionRequest,
) -> EligibleCandidate:
    """A reference to material the order already carries, by fingerprint.

    No content is copied and nothing is re-acquired: the identifier *is* the
    fingerprint of the record INPUT preserved, which is enough for a later phase
    to find the material it already has.
    """
    fingerprint = contract.source_contract_fingerprint or ""
    return EligibleCandidate(
        identifier=f"supplied_context:{fingerprint}",
        domain=DOMAIN_DIRECT_CONTEXT,
        tier=request.tier,
        eligible_source_classes=(SOURCE_CLASS_SUPPLIED_CONTEXT,),
        eligible_roles=request.required_roles,
        classifications=(
            CandidateClassification(
                source_class=SOURCE_CLASS_SUPPLIED_CONTEXT,
                basis=(BASIS_INVENTORY_DECLARED_CLASS,),
            ),
        ),
        size_bytes=None,
        target_anchor_match=False,
        reasons=(CANDIDATE_SUPPLIED_CONTEXT_REFERENCE, CANDIDATE_TIER_PRESERVED),
    )


def _repository_candidates(
    request: AcquisitionRequest,
    contract: AcquisitionRequestContract,
    inventory: CandidateInventory | None,
    *,
    excluded_classes: set[str],
    anchors: set[str],
    matched_anchors: set[str],
    rejections: dict[str, set[str]],
) -> tuple[tuple[EligibleCandidate, ...], int, set[str]]:
    """One repository-resident request's eligible members, bounded.

    An *active* request spends a candidate ceiling and a byte ceiling.  A
    deferred request spends neither, because nothing about it will be fetched:
    its members are listed under a separate bound so that "we set this aside"
    stays a fact somebody can check rather than a silence.
    """
    if inventory is None:
        return (), 0, set(request.required_roles)

    active = request.tier in ACTIVE_TIERS
    requested = set(request.source_classes)
    scored: list[tuple[tuple[int, int, str, str], EligibleCandidate, int]] = []

    def reject(identifier: str, reason: str) -> None:
        rejections.setdefault(identifier, set()).add(reason)

    for member in inventory.members:
        if not member.repository_contained or member.symlink_escape:
            reject(member.identifier, INELIGIBLE_OUTSIDE_REPOSITORY)
            continue

        anchor = member.identifier in anchors
        if anchor:
            matched_anchors.add(member.identifier)

        classifications = classify_member(member, target_anchor=anchor)
        classes = tuple(item.source_class for item in classifications)
        if not classes and not anchor:
            reject(member.identifier, INELIGIBLE_CLASSIFICATION_UNKNOWN)
            continue

        # Exclusions win, before anything else is considered.  An anchor the
        # user wrote does not readmit a snapshot, and neither does a second
        # class the same member happens to carry.
        if set(classes) & excluded_classes:
            reject(member.identifier, INELIGIBLE_SOURCE_CLASS_EXCLUDED)
            continue
        if member.hard_excluded:
            reject(member.identifier, INELIGIBLE_HARD_EXCLUDED_BY_INVENTORY)
            continue

        eligible_classes = tuple(
            item
            for item in ACQUISITION_SOURCE_CLASSES
            if item in requested and item in set(classes)
        )
        if not eligible_classes and not anchor:
            reject(member.identifier, INELIGIBLE_SOURCE_CLASS_NOT_REQUESTED)
            continue

        if active:
            if not member.size_known:
                # Conservative and documented: an unmeasured member is refused
                # rather than assumed small.  Assuming would let an unknown
                # quantity through a ceiling that exists precisely to stop
                # unknown quantities.
                reject(member.identifier, INELIGIBLE_SIZE_UNKNOWN)
                continue
            if member.size_bytes > request.budget.max_per_source_bytes:
                reject(member.identifier, INELIGIBLE_PER_SOURCE_BYTES_EXCEEDED)
                continue

        roles = tuple(
            role
            for role in roles_for_classes(eligible_classes)
            if role in set(request.required_roles)
        )
        if not roles and not anchor:
            reject(member.identifier, INELIGIBLE_SOURCE_CLASS_NOT_REQUESTED)
            continue

        # The user named this one by hand.  It is in the pool because the
        # inventory contains it and the order pointed at it, and it carries no
        # class and no role because nothing established either.  Borrowing the
        # request's classes to fill the gap would be the widening this whole
        # phase exists to refuse.
        if not roles:
            eligible_classes = ()

        candidate = EligibleCandidate(
            identifier=member.identifier,
            domain=request.domain,
            tier=request.tier,
            eligible_source_classes=eligible_classes,
            eligible_roles=roles,
            classifications=tuple(
                item
                for item in classifications
                if item.source_class in set(eligible_classes)
            ),
            size_bytes=member.size_bytes,
            target_anchor_match=anchor,
            reasons=_candidate_reasons(request, anchor),
        )
        scored.append(
            (
                _candidate_sort_key(member.identifier, eligible_classes, anchor, request),
                candidate,
                member.size_bytes or 0,
            )
        )

    scored.sort(key=lambda item: item[0])

    ceiling = request.budget.max_candidates if active else MAX_DEFERRED_CANDIDATES
    selected: list[EligibleCandidate] = []
    taken: set[str] = set()
    consumed = 0

    def take(candidate: EligibleCandidate, size: int) -> bool:
        nonlocal consumed
        if candidate.identifier in taken:
            return False
        if len(selected) >= ceiling:
            reject(candidate.identifier, INELIGIBLE_CANDIDATE_CEILING_REACHED)
            return False
        if active and consumed + size > request.budget.max_total_bytes:
            reject(candidate.identifier, INELIGIBLE_TOTAL_BYTES_EXHAUSTED)
            taken.add(candidate.identifier)
            return False
        selected.append(candidate)
        taken.add(candidate.identifier)
        if active:
            consumed += size
        return True

    # The user's own anchors first.  Precedence inside the pool, never a bypass
    # of the filters above — an anchor that was excluded never reached here.
    for _, candidate, size in scored:
        if candidate.target_anchor_match:
            take(candidate, size)

    # Then one candidate per required role, in the order the request states
    # them, cycling until the ceiling or the pool runs out.
    #
    # Ordering by class priority alone starves the rare roles: a repository with
    # nine hundred implementation modules and one architecture document spends
    # the whole ceiling on modules and reports the architecture unsatisfied — a
    # smaller, quieter version of the failure this line of phases exists to fix.
    # Round-robin is still deterministic, still metadata-only, and still carries
    # no notion of relevance; it just refuses to let one class crowd out the
    # others the request explicitly asked for.
    by_role: dict[str, list[tuple[EligibleCandidate, int]]] = {
        role: [
            (candidate, size)
            for _, candidate, size in scored
            if role in candidate.eligible_roles
        ]
        for role in request.required_roles
    }
    cursors = {role: 0 for role in request.required_roles}
    progressing = True
    while progressing and len(selected) < ceiling:
        progressing = False
        for role in request.required_roles:
            if len(selected) >= ceiling:
                break
            queue = by_role[role]
            while cursors[role] < len(queue):
                candidate, size = queue[cursors[role]]
                cursors[role] += 1
                if candidate.identifier in taken:
                    continue
                if take(candidate, size):
                    progressing = True
                break

    for _, candidate, size in scored:
        if candidate.identifier not in taken:
            reject(candidate.identifier, INELIGIBLE_CANDIDATE_CEILING_REACHED)

    satisfied = {role for candidate in selected for role in candidate.eligible_roles}
    return tuple(selected), consumed, set(request.required_roles) - satisfied


def _candidate_reasons(request: AcquisitionRequest, anchor: bool) -> tuple[str, ...]:
    codes = [CANDIDATE_INVENTORY_MEMBER, CANDIDATE_TIER_PRESERVED]
    if anchor:
        codes.append(CANDIDATE_EXPLICIT_TARGET_MATCHED)
    if request.tier not in ACTIVE_TIERS:
        codes.append(CANDIDATE_DEFERRED_UPSTREAM)
    present = set(codes)
    return tuple(code for code in CANDIDATE_REASONS if code in present)


# ── The closure checks ────────────────────────────────────────────────────────

def check_eligibility_monotonicity(
    outcome: EligibilityOutcome,
    contract: AcquisitionRequestContract,
) -> tuple[str, ...]:
    """Does the pool stay inside everything the acquisition request licensed?

    Narrowing is the job.  A candidate in a domain the request never named, at a
    tier it never set, of a class it excluded, or beyond the ceiling it wrote
    down is the same failure wearing four different coats.
    """
    if not isinstance(outcome, EligibilityOutcome):
        raise TypeError("check_eligibility_monotonicity requires an EligibilityOutcome")
    if not isinstance(contract, AcquisitionRequestContract):
        raise TypeError(
            "check_eligibility_monotonicity requires an AcquisitionRequestContract"
        )

    excluded = set(contract.excluded_classes()) | set(contract.deferred_classes())
    licensed: dict[tuple[str, str], AcquisitionRequest] = {
        request.key: request for request in contract.all_requests()
    }
    active_used = len(outcome.active_candidates) + len(outcome.secondary_candidates)
    if active_used > outcome.candidate_limit:
        return (INCONSISTENT_ELIGIBILITY_WIDENED,)

    for candidate in outcome.all_candidates():
        request = licensed.get((candidate.domain, candidate.tier))
        if request is None:
            return (INCONSISTENT_ELIGIBILITY_WIDENED,)
        if not set(candidate.eligible_source_classes) <= set(request.source_classes):
            return (INCONSISTENT_ELIGIBILITY_WIDENED,)
        if not candidate.eligible_source_classes and not candidate.target_anchor_match:
            return (INCONSISTENT_ELIGIBILITY_WIDENED,)
        if set(candidate.eligible_source_classes) & excluded:
            return (INCONSISTENT_ELIGIBILITY_WIDENED,)
        if set(candidate.eligible_source_classes) & set(NEVER_REQUESTED_SOURCE_CLASSES):
            return (INCONSISTENT_ELIGIBILITY_WIDENED,)
        if not set(candidate.eligible_roles) <= set(request.required_roles):
            return (INCONSISTENT_ELIGIBILITY_WIDENED,)
        # A byte ceiling bounds what may be *fetched*.  Deferred material will
        # not be fetched at all, so measuring it against an acquisition ceiling
        # of zero would refuse the very listing that makes deferral checkable.
        if (
            candidate.active
            and candidate.size_bytes is not None
            and candidate.size_bytes > request.budget.max_per_source_bytes
        ):
            return (INCONSISTENT_ELIGIBILITY_WIDENED,)
    if outcome.byte_eligible_total > outcome.byte_limit:
        return (INCONSISTENT_ELIGIBILITY_WIDENED,)
    if outcome.external_envelopes and not any(
        request.domain == DOMAIN_EXTERNAL_INFORMATION
        for request in contract.all_requests()
    ):
        return (INCONSISTENT_ELIGIBILITY_WIDENED,)
    return ()


def validate_selector_output(
    envelope: SelectorEnvelope,
    identifiers: tuple[str, ...],
    *,
    inventory: CandidateInventory | None = None,
) -> tuple[str, ...]:
    """Is what a selector produced still inside the envelope it was given?

    The selector is not trusted, and this is not an insult to it: an envelope
    that nobody checks is a comment.  Returns every violation found, in the
    canonical order, and an empty tuple when the output is a subset.

    Nothing is executed here.  The caller runs whatever selector it likes,
    however it likes, and hands the identifiers back for checking.
    """
    if not isinstance(envelope, SelectorEnvelope):
        raise TypeError("validate_selector_output requires a SelectorEnvelope")
    if not isinstance(identifiers, tuple):
        raise TypeError("validate_selector_output requires a tuple of identifiers")

    found: set[str] = set()
    allowed = set(envelope.allowed_candidate_identifiers)
    if len(set(identifiers)) != len(identifiers):
        found.add(VIOLATION_DUPLICATE_CANDIDATE)
    if len(identifiers) > len(allowed):
        found.add(VIOLATION_BUDGET_EXCEEDED)

    for identifier in identifiers:
        if identifier not in allowed:
            found.add(VIOLATION_OUTSIDE_ENVELOPE)
            if inventory is not None and inventory.member(identifier) is None:
                found.add(VIOLATION_WRONG_INVENTORY)
            continue
        if inventory is None:
            continue
        member = inventory.member(identifier)
        if member is None:
            found.add(VIOLATION_WRONG_INVENTORY)
            continue
        classes = {item.source_class for item in classify_member(member)}
        if classes & set(envelope.excluded_source_classes):
            found.add(VIOLATION_EXCLUDED_SOURCE_CLASS)
        if not classes & set(envelope.allowed_source_classes):
            found.add(VIOLATION_WRONG_TIER)
    return tuple(item for item in ENVELOPE_VIOLATIONS if item in found)


__all__ = [
    "LOCATION_ASSIGNABLE_CLASSES",
    "MAX_DEFERRED_CANDIDATES",
    "PHASE_ID",
    "ROLES_BY_SOURCE_CLASS",
    "SOURCE_CLASS_DOMAINS",
    "EligibilityOutcome",
    "check_eligibility_monotonicity",
    "classification_status",
    "classify_member",
    "derive_eligibility",
    "is_configuration_name",
    "is_historical_location",
    "is_manifest_name",
    "is_snapshot_location",
    "is_temporary_location",
    "is_test_location",
    "requires_inventory",
    "roles_for_classes",
    "validate_selector_output",
]
