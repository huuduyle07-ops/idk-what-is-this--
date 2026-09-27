"""ACQUIRE.1 — deterministic acquisition policy.

Given one specified Evidence Requirement Contract, this module decides which
bounded requests describe it:

    EvidenceRequirementContract + TaskContract
        -> AcquisitionPolicy

Three tables do the real work, and all three are frozen constants.

**Role decides source class.**  ``implementation_authority`` is satisfied by
runtime and surrounding implementation; ``interface_contract`` by interface
definitions; ``configuration_authority`` by configuration and dependency
manifests; ``architecture_description`` by authoritative architecture material
and the registration surfaces that make a system's shape visible.  The mapping
is total over the frozen WAITER.2 role vocabulary, so a role nobody has decided
about cannot slip through unmapped — it fails closed instead.

**Reach and tier decide the ceiling.**  A budget follows the evidence: what kind
of source, how far it reaches, and how urgently it is needed.  It deliberately
does *not* follow the selected workflow.  "Commander" is not a budget, and a
Commander order whose evidence is entirely direct context produces no repository
request at all.

**Priority survives translation.**  ``required_primary`` becomes an initial
request, ``required_secondary`` a smaller one, ``deferred`` a request with no
acquisition budget whatsoever, and ``excluded_initially`` an exclusion rather
than a request.  Nothing is promoted: there is no rule in this module that can
raise a tier, and the closure checks below refuse a request set that did.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no language system, inspects no repository, obtains no evidence, plans
nothing, and grants no authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.acquisition_request import (
    ACQUIRE_ARCHITECTURE_RECONNAISSANCE_REQUESTED,
    ACQUIRE_BUDGET_BOUNDED_BY_SCOPE_AND_TIER,
    ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,
    ACQUIRE_EXTERNAL_AUTHORITY_REQUESTED,
    ACQUIRE_HISTORICAL_MATERIAL_DEFERRED,
    ACQUIRE_REPOSITORY_EVIDENCE_REQUESTED,
    ACQUIRE_RESTATED_MATERIAL_EXCLUDED,
    ACQUIRE_SUPPLIED_MATERIAL_ALREADY_IN_HAND,
    ACQUIRE_UNRELATED_VALIDATION_DEFERRED,
    ACQUIRE_VALIDATION_EVIDENCE_REQUESTED,
    ACQUISITION_REASONS,
    BUDGET_BOUNDED,
    BUDGET_EXISTING_CONTEXT,
    BUDGET_EXTERNAL_BOUNDED,
    BUDGET_NONE,
    BUDGET_RECONNAISSANCE,
    BUDGET_SECONDARY_VERIFICATION,
    CURRENT_AUTHORITY_EXPECTED_ROLES,
    FRESHNESS_CURRENT,
    FRESHNESS_HISTORICAL,
    FRESHNESS_NOT_APPLICABLE,
    INCONSISTENT_ACQUISITION_WIDENED,
    INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,
    MAX_TARGET_ANCHORS,
    NEVER_REQUESTED_SOURCE_CLASSES,
    REQUEST_SCOPE_BOUNDED_REPOSITORY,
    REQUEST_SCOPE_BROAD_REPOSITORY_RECONNAISSANCE,
    REQUEST_SCOPE_EXISTING_CONTEXT,
    REQUEST_SCOPE_EXTERNAL_INFORMATION,
    REQUESTABLE_SOURCE_CLASSES,
    SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,
    SOURCE_CLASS_AUTHORITATIVE_EXTERNAL_SOURCE,
    SOURCE_CLASS_CONFIGURATION,
    SOURCE_CLASS_DEPENDENCY_MANIFEST,
    SOURCE_CLASS_DUPLICATE_RENDERING,
    SOURCE_CLASS_GENERATED_ARTIFACT,
    SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,
    SOURCE_CLASS_INTERFACE_DEFINITION,
    SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE,
    SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
    SOURCE_CLASS_SNAPSHOT,
    SOURCE_CLASS_SUPPLIED_CONTEXT,
    SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,
    SOURCE_CLASS_TEMPORARY_ARTIFACT,
    SOURCE_CLASS_VALIDATION_TEST,
    AcquisitionBudget,
    AcquisitionRequest,
    SourceExclusion,
    TargetAnchor,
)
from core.evidence_policy import names_validation_artifact
from core.evidence_requirements import (
    ACTIVE_TIERS,
    DEFERRED_SOURCE_CLASSES,
    DOMAIN_DIRECT_CONTEXT,
    DOMAIN_EXTERNAL_INFORMATION,
    DOMAIN_HISTORICAL_CONTEXT,
    DOMAIN_REPOSITORY,
    DOMAIN_VALIDATION_ARTIFACTS,
    EVIDENCE_ARCHITECTURE_RECON_REQUIRED,
    EVIDENCE_DOMAINS,
    EVIDENCE_ROLES,
    ROLE_ARCHITECTURE_DESCRIPTION,
    ROLE_CONFIGURATION_AUTHORITY,
    ROLE_CURRENT_EXTERNAL_AUTHORITY,
    ROLE_HISTORICAL_CONTEXT,
    ROLE_HYPOTHESIS_SUPPORT,
    ROLE_IMPLEMENTATION_AUTHORITY,
    ROLE_INTERFACE_CONTRACT,
    ROLE_SUPPLIED_MATERIAL,
    ROLE_VALIDATION_EVIDENCE,
    SOURCE_CLASS_DUPLICATE_RENDERINGS,
    SOURCE_CLASS_GENERATED_ARTIFACTS,
    SOURCE_CLASS_SNAPSHOTS,
    SOURCE_CLASS_TEMPORARY_ARTIFACTS,
    SOURCE_CLASS_UNRELATED_VALIDATION_ARTIFACTS,
    TIER_DEFERRED,
    TIER_REQUIRED_PRIMARY,
    TIER_REQUIRED_SECONDARY,
    EvidenceRequirementContract,
)
from core.task_contract import TaskContract


PHASE_ID = "ACQUIRE.1"

# ── Role -> source class ──────────────────────────────────────────────────────
#: What kind of source can satisfy each role.  Total over the frozen WAITER.2
#: role vocabulary; the totality is checked at import so a role added upstream
#: cannot arrive here unconsidered.
#:
#: ``hypothesis_support`` maps to nothing on purpose.  A hypothesis is something
#: a reader forms about evidence, not a class of source anyone can go and find,
#: and WAITER.2 never derives it.  Were it ever required, the honest answer is
#: that this vocabulary cannot express the request — so the contract fails closed
#: instead of quietly inventing a class for it.
SOURCE_CLASSES_BY_ROLE: dict[str, tuple[str, ...]] = {
    ROLE_SUPPLIED_MATERIAL: (SOURCE_CLASS_SUPPLIED_CONTEXT,),
    ROLE_IMPLEMENTATION_AUTHORITY: (
        SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
        SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,
    ),
    ROLE_INTERFACE_CONTRACT: (SOURCE_CLASS_INTERFACE_DEFINITION,),
    ROLE_CONFIGURATION_AUTHORITY: (
        SOURCE_CLASS_CONFIGURATION,
        SOURCE_CLASS_DEPENDENCY_MANIFEST,
    ),
    ROLE_ARCHITECTURE_DESCRIPTION: (
        SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,
        SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE,
    ),
    ROLE_VALIDATION_EVIDENCE: (SOURCE_CLASS_VALIDATION_TEST,),
    ROLE_HYPOTHESIS_SUPPORT: (),
    ROLE_HISTORICAL_CONTEXT: (SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,),
    ROLE_CURRENT_EXTERNAL_AUTHORITY: (SOURCE_CLASS_AUTHORITATIVE_EXTERNAL_SOURCE,),
}

if tuple(SOURCE_CLASSES_BY_ROLE) != EVIDENCE_ROLES:  # pragma: no cover
    raise RuntimeError(
        "every evidence role must state the source classes that satisfy it, in the "
        "canonical order"
    )
for _role, _classes in SOURCE_CLASSES_BY_ROLE.items():  # pragma: no cover
    for _class in _classes:
        if _class not in REQUESTABLE_SOURCE_CLASSES:
            raise RuntimeError(f"role {_role!r} maps to a class that may not be requested")

# ── Domain -> request scope ───────────────────────────────────────────────────
#: How far a request for each domain reaches.  Repository is the only domain
#: whose reach varies, and it varies with what WAITER.2 already recorded rather
#: than with anything measured here.
#:
#: Validation artifacts and historical material are repository-resident and
#: always bounded: a check is not a survey, and deferred material is not
#: acquired at all, so neither can ever become reconnaissance.
_SCOPE_BY_DOMAIN: dict[str, str] = {
    DOMAIN_DIRECT_CONTEXT: REQUEST_SCOPE_EXISTING_CONTEXT,
    DOMAIN_REPOSITORY: REQUEST_SCOPE_BOUNDED_REPOSITORY,
    DOMAIN_VALIDATION_ARTIFACTS: REQUEST_SCOPE_BOUNDED_REPOSITORY,
    DOMAIN_HISTORICAL_CONTEXT: REQUEST_SCOPE_BOUNDED_REPOSITORY,
    DOMAIN_EXTERNAL_INFORMATION: REQUEST_SCOPE_EXTERNAL_INFORMATION,
}

if tuple(_SCOPE_BY_DOMAIN) != EVIDENCE_DOMAINS:  # pragma: no cover
    raise RuntimeError("every evidence domain must state the reach of its request")

# ── Domain -> freshness ───────────────────────────────────────────────────────
#: Material already in hand has no currency question to answer.  Historical
#: material is historical by definition — that is what makes it non-authoritative
#: about the present.  Everything else has to be current when it is used, because
#: evidence about what a system does now is worthless if it describes last month.
_FRESHNESS_BY_DOMAIN: dict[str, str] = {
    DOMAIN_DIRECT_CONTEXT: FRESHNESS_NOT_APPLICABLE,
    DOMAIN_REPOSITORY: FRESHNESS_CURRENT,
    DOMAIN_VALIDATION_ARTIFACTS: FRESHNESS_CURRENT,
    DOMAIN_HISTORICAL_CONTEXT: FRESHNESS_HISTORICAL,
    DOMAIN_EXTERNAL_INFORMATION: FRESHNESS_CURRENT,
}

if tuple(_FRESHNESS_BY_DOMAIN) != EVIDENCE_DOMAINS:  # pragma: no cover
    raise RuntimeError("every evidence domain must state how fresh its sources must be")

#: The active tiers in priority order, so a request set always reads primary
#: first.  Order is a property of the schema, never of how a caller happened to
#: build the requirements.
ACTIVE_TIERS_ORDER: tuple[str, ...] = (TIER_REQUIRED_PRIMARY, TIER_REQUIRED_SECONDARY)

if set(ACTIVE_TIERS_ORDER) != set(ACTIVE_TIERS):  # pragma: no cover
    raise RuntimeError("the active tier order must cover exactly the active tiers")

# ── WAITER.2 deferred class -> acquisition class ──────────────────────────────
#: Total over WAITER.2's deferred source classes, so a class it defers cannot be
#: forgotten here.
#:
#: ``unrelated_validation_artifacts`` maps to ``None`` deliberately.  It is not a
#: kind of source — a test is a test — it is a statement that validation material
#: beyond what the primary evidence needs is not part of the initial set.  That
#: is carried as a smaller ceiling and an explicit reason on the validation
#: request instead, and :func:`check_deferred_source_coverage` refuses a contract
#: in which neither representation is present.
EVIDENCE_CLASS_ACQUISITION_CLASSES: dict[str, str | None] = {
    SOURCE_CLASS_GENERATED_ARTIFACTS: SOURCE_CLASS_GENERATED_ARTIFACT,
    SOURCE_CLASS_SNAPSHOTS: SOURCE_CLASS_SNAPSHOT,
    SOURCE_CLASS_TEMPORARY_ARTIFACTS: SOURCE_CLASS_TEMPORARY_ARTIFACT,
    SOURCE_CLASS_DUPLICATE_RENDERINGS: SOURCE_CLASS_DUPLICATE_RENDERING,
    SOURCE_CLASS_UNRELATED_VALIDATION_ARTIFACTS: None,
}

if tuple(EVIDENCE_CLASS_ACQUISITION_CLASSES) != DEFERRED_SOURCE_CLASSES:  # pragma: no cover
    raise RuntimeError(
        "every deferred evidence source class must state how it is represented here"
    )
for _value in EVIDENCE_CLASS_ACQUISITION_CLASSES.values():  # pragma: no cover
    if _value is not None and _value not in NEVER_REQUESTED_SOURCE_CLASSES:
        raise RuntimeError("a deferred class may only map onto material never requested")


@dataclass(frozen=True, slots=True)
class AcquisitionPolicy:
    """The requests one evidence contract translates into."""

    requests: tuple[AcquisitionRequest, ...]
    deferred_requests: tuple[AcquisitionRequest, ...] = ()
    exclusions: tuple[SourceExclusion, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "requests": [item.as_dict() for item in self.requests],
            "deferred_requests": [item.as_dict() for item in self.deferred_requests],
            "exclusions": [item.as_dict() for item in self.exclusions],
        }


def unmappable_roles(evidence: EvidenceRequirementContract) -> tuple[str, ...]:
    """Required roles this vocabulary cannot express, in canonical order.

    An empty tuple is the normal answer.  Anything else means a request set
    would have to be invented rather than translated, and the caller fails
    closed instead.
    """
    if not isinstance(evidence, EvidenceRequirementContract):
        raise TypeError("unmappable_roles requires an EvidenceRequirementContract")
    present = {
        requirement.role
        for requirement in evidence.requirements
        if not SOURCE_CLASSES_BY_ROLE[requirement.role]
    }
    return tuple(role for role in EVIDENCE_ROLES if role in present)


def repository_reach(evidence: EvidenceRequirementContract) -> str:
    """Bounded, or a survey?  Read from what WAITER.2 already recorded.

    The evidence scope alone cannot answer this — ``mixed_sources`` covers a
    bounded edit that also needs an external fact as well as an architectural
    survey that does — so the answer comes from the reason WAITER.2 attached to
    the repository requirement itself.  Nothing is measured, and no repository is
    consulted.
    """
    if not isinstance(evidence, EvidenceRequirementContract):
        raise TypeError("repository_reach requires an EvidenceRequirementContract")
    for requirement in evidence.requirements:
        if (
            requirement.domain == DOMAIN_REPOSITORY
            and EVIDENCE_ARCHITECTURE_RECON_REQUIRED in requirement.reasons
        ):
            return REQUEST_SCOPE_BROAD_REPOSITORY_RECONNAISSANCE
    return REQUEST_SCOPE_BOUNDED_REPOSITORY


def request_scope_for(domain: str, evidence: EvidenceRequirementContract) -> str:
    """The reach of one domain's request."""
    if domain not in EVIDENCE_DOMAINS:
        raise KeyError(f"unsupported evidence domain: {domain!r}")
    if domain == DOMAIN_REPOSITORY:
        return repository_reach(evidence)
    return _SCOPE_BY_DOMAIN[domain]


def budget_profile_for(domain: str, tier: str, scope: str) -> str:
    """The ceiling for one request, from the evidence and never the workflow.

    Deferred and initially excluded material gets ``none``: not a small budget,
    no budget, because deferring something and then funding its acquisition
    would be a promotion written in numbers.
    """
    if domain not in EVIDENCE_DOMAINS:
        raise KeyError(f"unsupported evidence domain: {domain!r}")
    if tier not in ACTIVE_TIERS:
        return BUDGET_NONE
    if domain == DOMAIN_DIRECT_CONTEXT:
        return BUDGET_EXISTING_CONTEXT
    if domain == DOMAIN_EXTERNAL_INFORMATION:
        return BUDGET_EXTERNAL_BOUNDED
    if tier == TIER_REQUIRED_SECONDARY:
        return BUDGET_SECONDARY_VERIFICATION
    if scope == REQUEST_SCOPE_BROAD_REPOSITORY_RECONNAISSANCE:
        return BUDGET_RECONNAISSANCE
    return BUDGET_BOUNDED


def source_classes_for(roles: tuple[str, ...]) -> tuple[str, ...]:
    """Every class that satisfies any of these roles, in canonical order."""
    present: set[str] = set()
    for role in roles:
        if role not in SOURCE_CLASSES_BY_ROLE:
            raise KeyError(f"unsupported evidence role: {role!r}")
        present.update(SOURCE_CLASSES_BY_ROLE[role])
    return tuple(item for item in REQUESTABLE_SOURCE_CLASSES if item in present)


def preserved_target_anchors(contract: TaskContract) -> tuple[TargetAnchor, ...]:
    """The identifiers the user wrote, carried through unchanged.

    Read from INPUT.1's literal explicit evidence.  Nothing is resolved, nothing
    is completed, nothing is checked for existence, and nothing is discovered:
    if the order did not name it, it is not here.
    """
    if not isinstance(contract, TaskContract):
        raise TypeError("preserved_target_anchors requires a TaskContract")
    seen: list[str] = []
    for value in contract.explicit_evidence.file_paths:
        if value and value not in seen:
            seen.append(value)
    return tuple(TargetAnchor(value=value) for value in seen[:MAX_TARGET_ANCHORS])


def _ordered_reasons(codes: list[str]) -> tuple[str, ...]:
    present = set(codes)
    return tuple(code for code in ACQUISITION_REASONS if code in present)


def _domain_reason(domain: str, scope: str) -> str:
    if domain == DOMAIN_DIRECT_CONTEXT:
        return ACQUIRE_SUPPLIED_MATERIAL_ALREADY_IN_HAND
    if domain == DOMAIN_EXTERNAL_INFORMATION:
        return ACQUIRE_EXTERNAL_AUTHORITY_REQUESTED
    if domain == DOMAIN_VALIDATION_ARTIFACTS:
        return ACQUIRE_VALIDATION_EVIDENCE_REQUESTED
    if domain == DOMAIN_HISTORICAL_CONTEXT:
        return ACQUIRE_HISTORICAL_MATERIAL_DEFERRED
    if scope == REQUEST_SCOPE_BROAD_REPOSITORY_RECONNAISSANCE:
        return ACQUIRE_ARCHITECTURE_RECONNAISSANCE_REQUESTED
    return ACQUIRE_REPOSITORY_EVIDENCE_REQUESTED


def derive_acquisition_policy(
    evidence: EvidenceRequirementContract,
    contract: TaskContract,
) -> AcquisitionPolicy:
    """Translate one specified evidence contract into bounded requests.

    Every input is a structured fact WAITER.2 or INPUT already established.  Two
    runs over the same evidence contract and the same task contract always
    produce the same requests, on any machine, at any time, with any repository
    state and no network.

    The selected workflow is deliberately not consulted for anything except the
    traceability field the orchestrator copies.  There is no rule here that
    reads it, so there is no rule here that could size a request by it.
    """
    if not isinstance(evidence, EvidenceRequirementContract):
        raise TypeError("derive_acquisition_policy requires an EvidenceRequirementContract")
    if not isinstance(contract, TaskContract):
        raise TypeError("derive_acquisition_policy requires a TaskContract")
    if not evidence.specified:
        raise ValueError("only a specified evidence contract can be translated")
    unmappable = unmappable_roles(evidence)
    if unmappable:
        raise ValueError(f"no source class expresses the role {unmappable[0]!r}")

    # ── group the requirements: one request per domain and tier ──────────────
    grouped: dict[tuple[str, str], list[str]] = {}
    for requirement in evidence.requirements:
        grouped.setdefault((requirement.domain, requirement.tier), []).append(
            requirement.role
        )

    unrelated_validation_deferred = (
        SOURCE_CLASS_UNRELATED_VALIDATION_ARTIFACTS in evidence.deferred_classes()
    )
    anchors = preserved_target_anchors(contract)
    anchor_domain = (
        DOMAIN_VALIDATION_ARTIFACTS
        if names_validation_artifact(contract)
        and any(key[0] == DOMAIN_VALIDATION_ARTIFACTS for key in grouped)
        else DOMAIN_REPOSITORY
    )

    requests: list[AcquisitionRequest] = []
    deferred: list[AcquisitionRequest] = []

    # Iterate the vocabularies rather than a dict, so the order of the requests
    # is a property of the schema and not of how the requirements were built.
    for domain in EVIDENCE_DOMAINS:
        for tier in (*ACTIVE_TIERS_ORDER, TIER_DEFERRED):
            roles = grouped.get((domain, tier))
            if not roles:
                continue
            ordered_roles = tuple(role for role in EVIDENCE_ROLES if role in set(roles))
            scope = request_scope_for(domain, evidence)
            budget = AcquisitionBudget(budget_profile_for(domain, tier, scope))

            reasons = [_domain_reason(domain, scope)]
            if budget.active:
                reasons.append(ACQUIRE_BUDGET_BOUNDED_BY_SCOPE_AND_TIER)
            if (
                domain == DOMAIN_VALIDATION_ARTIFACTS
                and unrelated_validation_deferred
                and tier in ACTIVE_TIERS
            ):
                reasons.append(ACQUIRE_UNRELATED_VALIDATION_DEFERRED)

            attached: tuple[TargetAnchor, ...] = ()
            if anchors and domain == anchor_domain and tier in ACTIVE_TIERS:
                attached = anchors
                reasons.append(ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED)

            request = AcquisitionRequest(
                domain=domain,
                required_roles=ordered_roles,
                tier=tier,
                source_classes=source_classes_for(ordered_roles),
                scope=scope,
                budget=budget,
                freshness=_FRESHNESS_BY_DOMAIN[domain],
                require_current_authority=any(
                    role in CURRENT_AUTHORITY_EXPECTED_ROLES for role in ordered_roles
                ),
                target_anchors=attached,
                reasons=_ordered_reasons(reasons),
            )
            (requests if request.active else deferred).append(request)

    # ── classes that restate a source rather than being one ─────────────────
    exclusions: list[SourceExclusion] = []
    for source in evidence.deferred_sources:
        acquisition_class = EVIDENCE_CLASS_ACQUISITION_CLASSES[source.source_class]
        if acquisition_class is None:
            continue
        exclusions.append(
            SourceExclusion(
                source_class=acquisition_class,
                # Copied verbatim.  Softening an exclusion into a deferral, or
                # hardening a deferral into an exclusion, would both be edits to
                # a decision this phase did not make.
                disposition=source.disposition,
                reasons=(ACQUIRE_RESTATED_MATERIAL_EXCLUDED,),
            )
        )

    return AcquisitionPolicy(
        requests=tuple(requests),
        deferred_requests=tuple(deferred),
        exclusions=tuple(exclusions),
    )


# ── The closure checks ────────────────────────────────────────────────────────

def check_request_monotonicity(
    policy: AcquisitionPolicy,
    evidence: EvidenceRequirementContract,
) -> tuple[str, ...]:
    """May every request point back at a requirement that licensed it?

    Refining an evidence requirement is the job.  Enlarging one is refused: a
    repository request where the contract named no repository domain, a
    historical request promoted to primary, or a request for a class the
    contract excluded are all the same failure wearing different clothes.
    """
    if not isinstance(policy, AcquisitionPolicy):
        raise TypeError("check_request_monotonicity requires an AcquisitionPolicy")
    if not isinstance(evidence, EvidenceRequirementContract):
        raise TypeError("check_request_monotonicity requires an EvidenceRequirementContract")

    excluded = set(evidence.deferred_classes()) | set(evidence.excluded_classes())
    forbidden = {
        acquisition_class
        for evidence_class, acquisition_class in EVIDENCE_CLASS_ACQUISITION_CLASSES.items()
        if acquisition_class is not None and evidence_class in excluded
    }
    for request in policy.requests + policy.deferred_requests:
        if not evidence.requires_domain(request.domain):
            return (INCONSISTENT_ACQUISITION_WIDENED,)
        for role in request.required_roles:
            # Same domain, same role, same tier.  A tier that moved is a
            # promotion whatever else it is called.
            if evidence.tier_of(request.domain, role) != request.tier:
                return (INCONSISTENT_ACQUISITION_WIDENED,)
        if set(request.source_classes) & forbidden:
            return (INCONSISTENT_ACQUISITION_WIDENED,)
        if set(request.source_classes) & set(NEVER_REQUESTED_SOURCE_CLASSES):
            return (INCONSISTENT_ACQUISITION_WIDENED,)
    return ()


def check_requirement_coverage(
    policy: AcquisitionPolicy,
    evidence: EvidenceRequirementContract,
) -> tuple[str, ...]:
    """Does every requirement still have a request that carries it?

    The mirror of :func:`check_request_monotonicity`, and the reason the pair is
    worth having: not wider, and not narrower.  A required domain, a required
    role, a primary tier or the currency of an external source may not go
    missing between one contract and the next.
    """
    if not isinstance(policy, AcquisitionPolicy):
        raise TypeError("check_requirement_coverage requires an AcquisitionPolicy")
    if not isinstance(evidence, EvidenceRequirementContract):
        raise TypeError("check_requirement_coverage requires an EvidenceRequirementContract")

    everything = policy.requests + policy.deferred_requests
    for requirement in evidence.requirements:
        carriers = [
            request
            for request in everything
            if request.satisfies(requirement.domain, requirement.role)
        ]
        if len(carriers) != 1:
            return (INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,)
        carrier = carriers[0]
        if carrier.tier != requirement.tier:
            return (INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,)
        if requirement.tier in ACTIVE_TIERS and not carrier.budget.active:
            return (INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,)
        if not carrier.source_classes:
            return (INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,)
        if (
            requirement.domain == DOMAIN_EXTERNAL_INFORMATION
            and carrier.freshness != FRESHNESS_CURRENT
        ):
            return (INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,)
    return ()


def check_deferred_source_coverage(
    policy: AcquisitionPolicy,
    evidence: EvidenceRequirementContract,
) -> tuple[str, ...]:
    """Is every class WAITER.2 pushed back still accounted for?

    A class with an acquisition counterpart has to appear as an exclusion with
    the disposition it was given.  The one class with no counterpart —
    validation material unrelated to the primary evidence — has to appear as an
    explicit reason on a validation request instead.  Either way it is written
    down; neither way is it forgotten.
    """
    if not isinstance(policy, AcquisitionPolicy):
        raise TypeError("check_deferred_source_coverage requires an AcquisitionPolicy")
    if not isinstance(evidence, EvidenceRequirementContract):
        raise TypeError(
            "check_deferred_source_coverage requires an EvidenceRequirementContract"
        )

    stated = {item.source_class: item.disposition for item in policy.exclusions}
    carried = {
        reason
        for request in policy.requests + policy.deferred_requests
        for reason in request.reasons
    }
    for source in evidence.deferred_sources:
        acquisition_class = EVIDENCE_CLASS_ACQUISITION_CLASSES[source.source_class]
        if acquisition_class is None:
            if ACQUIRE_UNRELATED_VALIDATION_DEFERRED not in carried:
                return (INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,)
            continue
        if stated.get(acquisition_class) != source.disposition:
            return (INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,)
    return ()


def check_bounded_reconnaissance(policy: AcquisitionPolicy) -> tuple[str, ...]:
    """Is "broad" still bounded?

    A future executor must never be able to read ``broad_repository_reconnaissance``
    as "read everything".  A broad request therefore has to name which classes it
    may reach — strictly fewer than all of them — carry a finite ceiling, and sit
    in a contract that also says what is being kept out.  This is the invariant
    the DeepSeek Harness dogfood violated, stated so it can fail rather than
    merely be regretted.
    """
    if not isinstance(policy, AcquisitionPolicy):
        raise TypeError("check_bounded_reconnaissance requires an AcquisitionPolicy")

    for request in policy.requests:
        if request.scope != REQUEST_SCOPE_BROAD_REPOSITORY_RECONNAISSANCE:
            continue
        if not request.budget.active:
            return (INCONSISTENT_ACQUISITION_WIDENED,)
        if set(request.source_classes) >= set(REQUESTABLE_SOURCE_CLASSES):
            return (INCONSISTENT_ACQUISITION_WIDENED,)
        if not policy.exclusions:
            return (INCONSISTENT_ACQUISITION_WIDENED,)
    return ()


__all__ = [
    "ACTIVE_TIERS_ORDER",
    "EVIDENCE_CLASS_ACQUISITION_CLASSES",
    "PHASE_ID",
    "SOURCE_CLASSES_BY_ROLE",
    "AcquisitionPolicy",
    "budget_profile_for",
    "check_bounded_reconnaissance",
    "check_deferred_source_coverage",
    "check_request_monotonicity",
    "check_requirement_coverage",
    "derive_acquisition_policy",
    "preserved_target_anchors",
    "repository_reach",
    "request_scope_for",
    "source_classes_for",
    "unmappable_roles",
]
