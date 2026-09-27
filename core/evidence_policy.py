"""WAITER.2 — deterministic evidence policy.

Given what an order *is* and what a workflow would have to be *able to do*, this
module decides what classes of evidence that work will need, in what order of
priority, and what should be pushed out of the initial set.

    TaskShape + CapabilityRequirements + TaskContract
        -> EvidencePolicy

The derivation deliberately never sees the selected workflow.  It cannot, then,
tune the evidence set to a workflow, and — more importantly — it cannot tune the
workflow to the evidence set.  Whatever comes out of here is attached to the
route WAITER.1 already chose, unchanged.  Escalating chat to commander is not a
thing this layer declines to do; it is a thing it has no argument for.

Three policies do the real work.

**Priority, not sweep.**  The DeepSeek Harness dogfood considered roughly six
thousand files with no notion of which mattered.  For a broad architectural
survey this module states that runtime implementation, interfaces, configuration
and authoritative architecture description come first, that validation artifacts
come second, and that history comes later still.  It states this in classes, and
names not one file.

**History explains, it does not testify.**  Proposed, rejected and superseded
material is required at a deferred tier with the role ``historical_context`` and
a verification rule that current implementation outranks it.  It can say why
something was built; it can never say what is built.

**Tests are not noise, and they are not the default subject.**  Validation
artifacts are secondary for a survey and primary when the order is about them —
decided from what INPUT.1 already preserved, never from prose.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no language system, inspects no repository, retrieves nothing, plans
nothing, selects no workflow, and grants no authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.capability_requirements import (
    CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE,
    CAPABILITY_CODE_CHANGE,
    CAPABILITY_CROSS_SOURCE_SYNTHESIS,
    CAPABILITY_EXTERNAL_INFORMATION,
    CAPABILITY_REPOSITORY_READ,
    CapabilityRequirements,
)
from core.evidence_requirements import (
    DOMAIN_DIRECT_CONTEXT,
    DOMAIN_EXTERNAL_INFORMATION,
    DOMAIN_HISTORICAL_CONTEXT,
    DOMAIN_REPOSITORY,
    DOMAIN_VALIDATION_ARTIFACTS,
    EVIDENCE_ARCHITECTURE_RECON_REQUIRED,
    EVIDENCE_CHANGE_REQUIRES_VALIDATION,
    EVIDENCE_CROSS_SOURCE_RECONCILIATION_REQUIRED,
    EVIDENCE_DIRECT_CONTEXT_FROM_TASK,
    EVIDENCE_EXTERNAL_CURRENT_INFO_REQUIRED,
    EVIDENCE_GENERATED_MATERIAL_NOT_INITIAL_AUTHORITY,
    EVIDENCE_HISTORY_NON_AUTHORITATIVE,
    EVIDENCE_REPOSITORY_REQUIRED,
    EVIDENCE_TESTS_ARE_THE_SUBJECT,
    EVIDENCE_TESTS_FOR_VERIFICATION,
    ROLE_ARCHITECTURE_DESCRIPTION,
    ROLE_CONFIGURATION_AUTHORITY,
    ROLE_CURRENT_EXTERNAL_AUTHORITY,
    ROLE_HISTORICAL_CONTEXT,
    ROLE_IMPLEMENTATION_AUTHORITY,
    ROLE_INTERFACE_CONTRACT,
    ROLE_SUPPLIED_MATERIAL,
    ROLE_VALIDATION_EVIDENCE,
    SCOPE_BOUNDED_REPOSITORY,
    SCOPE_BROAD_REPOSITORY_RECONNAISSANCE,
    SCOPE_DIRECT_CONTEXT_ONLY,
    SCOPE_EXTERNAL_ONLY,
    SCOPE_MIXED_SOURCES,
    SOURCE_CLASS_DUPLICATE_RENDERINGS,
    SOURCE_CLASS_GENERATED_ARTIFACTS,
    SOURCE_CLASS_SNAPSHOTS,
    SOURCE_CLASS_TEMPORARY_ARTIFACTS,
    SOURCE_CLASS_UNRELATED_VALIDATION_ARTIFACTS,
    TIER_DEFERRED,
    TIER_EXCLUDED_INITIALLY,
    TIER_REQUIRED_PRIMARY,
    TIER_REQUIRED_SECONDARY,
    VERIFY_CURRENT_IMPLEMENTATION_OVER_HISTORY,
    VERIFY_EXTERNAL_INFORMATION_CURRENCY,
    VERIFY_SUPPLIED_MATERIAL_IS_THE_WHOLE_SET,
    VERIFY_VALIDATION_EVIDENCE_BEFORE_BEHAVIOUR_CLAIMS,
    DeferredSource,
    EvidenceRequirement,
)
from core.task_contract import TaskContract
from core.task_shape import (
    EVIDENCE_BOUNDED_REPOSITORY,
    EVIDENCE_BROAD_REPOSITORY,
    EVIDENCE_EXTERNAL_INFORMATION,
    EVIDENCE_MIXED_SOURCES,
    TaskShape,
)


PHASE_ID = "WAITER.2"

#: ``TaskShape.evidence_scope`` -> evidence reach.  Total over the frozen
#: WAITER.1 vocabulary; ``none`` and ``direct_context`` both mean the order
#: already carries everything it needs.
_SCOPE_BY_EVIDENCE_SCOPE: dict[str, str] = {
    EVIDENCE_BOUNDED_REPOSITORY: SCOPE_BOUNDED_REPOSITORY,
    EVIDENCE_BROAD_REPOSITORY: SCOPE_BROAD_REPOSITORY_RECONNAISSANCE,
    EVIDENCE_EXTERNAL_INFORMATION: SCOPE_EXTERNAL_ONLY,
    EVIDENCE_MIXED_SOURCES: SCOPE_MIXED_SOURCES,
}

# ── Recognising a validation artifact the user named ──────────────────────────
#: Literal markers only, applied to strings INPUT.1 already preserved.  Nothing
#: is looked up, no directory is walked, and no path is resolved: this decides
#: whether the *order* is about validation artifacts, not whether any file
#: exists.
_VALIDATION_DIRECTORY_SEGMENTS: frozenset[str] = frozenset({"test", "tests"})
_VALIDATION_NAME_PREFIX = "test_"
_VALIDATION_NAME_MARKER = "_test."


@dataclass(frozen=True, slots=True)
class EvidencePolicy:
    """The evidence one order needs, before any workflow is attached to it."""

    scope: str
    requirements: tuple[EvidenceRequirement, ...]
    deferred_sources: tuple[DeferredSource, ...] = ()
    verification_requirements: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "requirements": [item.as_dict() for item in self.requirements],
            "deferred_sources": [item.as_dict() for item in self.deferred_sources],
            "verification_requirements": list(self.verification_requirements),
        }


def carries_direct_context_material(contract: TaskContract) -> bool:
    """Did the order hand over the material the answer works on?

    The same question WAITER.1 asks when it derives an evidence scope, read from
    the same preserved fields: quoted spans, list items and a supplied framework
    are content the order carries with it.  A named entity is a name and a URL is
    a pointer somewhere else, and neither is material in hand.

    WAITER.1 asks it to *choose between* scopes and answers external first, so an
    order that pastes a snippet and also needs a current external fact arrives
    here labelled ``external_information`` with the direct-context half of its
    evidence no longer visible in the shape.  WAITER.2 has the contract in front
    of it and can say so without re-reading a word of the request.
    """
    if not isinstance(contract, TaskContract):
        raise TypeError("carries_direct_context_material requires a TaskContract")
    evidence = contract.explicit_evidence
    return bool(evidence.quoted_terms or evidence.list_items or evidence.framework)


def evidence_scope_for(shape: TaskShape, contract: TaskContract | None = None) -> str:
    """How far this order's evidence reaches, in bounded words.

    Never a count.  WAITER.2 does not know what the repository contains, and a
    scope expressed as a number would be a claim about membership it has no way
    to make.

    ``contract`` is optional and refines exactly one case.  An order that carries
    its own material *and* needs current external information reaches both, and
    calling that reach ``external_only`` while a required-primary
    ``supplied_material`` requirement sits in the same contract would be a label
    contradicting its own record.  It is ``mixed_sources``: more than one kind of
    source, to be reconciled rather than concatenated.  Nothing else moves —
    external-only stays external-only, and no repository scope is reachable from
    here, so the refinement can never widen the work.
    """
    if not isinstance(shape, TaskShape):
        raise TypeError("evidence_scope_for requires a TaskShape")
    if contract is not None and not isinstance(contract, TaskContract):
        raise TypeError("evidence_scope_for requires a TaskContract or None")

    scope = _SCOPE_BY_EVIDENCE_SCOPE.get(shape.evidence_scope, SCOPE_DIRECT_CONTEXT_ONLY)
    if (
        scope == SCOPE_EXTERNAL_ONLY
        and contract is not None
        and carries_direct_context_material(contract)
    ):
        return SCOPE_MIXED_SOURCES
    return scope


def _is_validation_path(value: str) -> bool:
    """Does this literal string name a validation artifact?

    Purely lexical, and deliberately narrow: a leading directory segment the
    user wrote as ``test``/``tests``, or a final segment that starts with
    ``test_`` or contains ``_test.``.  ``core/text_utils.py`` is not a test, and
    "the tests are slow" names no artifact at all.
    """
    normalised = value.replace("\\", "/").casefold()
    parts = [part for part in normalised.split("/") if part]
    if not parts:
        return False
    if any(part in _VALIDATION_DIRECTORY_SEGMENTS for part in parts[:-1]):
        return True
    final = parts[-1]
    return final.startswith(_VALIDATION_NAME_PREFIX) or _VALIDATION_NAME_MARKER in final


def names_validation_artifact(contract: TaskContract) -> bool:
    """Is this order *about* validation artifacts?

    Read from INPUT.1's literal file paths and the surviving subjects — facts
    already established upstream — so the answer is the same whatever language
    the request was written in and whatever the repository currently holds.
    """
    if not isinstance(contract, TaskContract):
        raise TypeError("names_validation_artifact requires a TaskContract")
    candidates = tuple(contract.explicit_evidence.file_paths) + contract.subject_values()
    return any(_is_validation_path(value) for value in candidates)


def derive_evidence_policy(
    shape: TaskShape,
    capabilities: CapabilityRequirements,
    contract: TaskContract,
) -> EvidencePolicy:
    """Decide what evidence this order needs, deterministically.

    Every input is a structured fact WAITER.1 or INPUT already established.  Two
    runs over the same shape, the same capabilities and the same contract always
    produce the same policy, on any machine, at any time, with any repository
    state and no network.

    The selected workflow is deliberately not a parameter.
    """
    if not isinstance(shape, TaskShape):
        raise TypeError("derive_evidence_policy requires a TaskShape")
    if not isinstance(capabilities, CapabilityRequirements):
        raise TypeError("derive_evidence_policy requires CapabilityRequirements")
    if not isinstance(contract, TaskContract):
        raise TypeError("derive_evidence_policy requires a TaskContract")

    scope = evidence_scope_for(shape, contract)
    repository = capabilities.requires(CAPABILITY_REPOSITORY_READ)
    broad = capabilities.requires(CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE)
    external = capabilities.requires(CAPABILITY_EXTERNAL_INFORMATION)
    change = capabilities.requires(CAPABILITY_CODE_CHANGE)
    cross_source = capabilities.requires(CAPABILITY_CROSS_SOURCE_SYNTHESIS)
    tests_are_the_subject = names_validation_artifact(contract)

    requirements: list[EvidenceRequirement] = []
    deferred: list[DeferredSource] = []
    verification: list[str] = []

    # ── what the order carried with it ───────────────────────────────────────
    # Always required and always free: the preserved request *is* evidence, and
    # no acquisition step stands between the work and it.
    requirements.append(
        EvidenceRequirement(
            domain=DOMAIN_DIRECT_CONTEXT,
            role=ROLE_SUPPLIED_MATERIAL,
            tier=TIER_REQUIRED_PRIMARY,
            reasons=(EVIDENCE_DIRECT_CONTEXT_FROM_TASK,),
        )
    )
    if scope == SCOPE_DIRECT_CONTEXT_ONLY:
        verification.append(VERIFY_SUPPLIED_MATERIAL_IS_THE_WHOLE_SET)

    # ── the repository, in priority order ────────────────────────────────────
    if repository:
        primary_reason = (
            EVIDENCE_ARCHITECTURE_RECON_REQUIRED if broad else EVIDENCE_REPOSITORY_REQUIRED
        )
        requirements.append(
            EvidenceRequirement(
                domain=DOMAIN_REPOSITORY,
                role=ROLE_IMPLEMENTATION_AUTHORITY,
                tier=TIER_REQUIRED_PRIMARY,
                reasons=(primary_reason,),
            )
        )
        if broad:
            # A survey needs the seams as much as the code: what the parts
            # promise each other, what configuration binds them, and what the
            # repository itself claims its architecture is.
            for role in (
                ROLE_INTERFACE_CONTRACT,
                ROLE_CONFIGURATION_AUTHORITY,
                ROLE_ARCHITECTURE_DESCRIPTION,
            ):
                requirements.append(
                    EvidenceRequirement(
                        domain=DOMAIN_REPOSITORY,
                        role=role,
                        tier=TIER_REQUIRED_PRIMARY,
                        reasons=(EVIDENCE_ARCHITECTURE_RECON_REQUIRED,),
                    )
                )

        # ── validation artifacts, at a tier the task decides ─────────────────
        if tests_are_the_subject:
            requirements.append(
                EvidenceRequirement(
                    domain=DOMAIN_VALIDATION_ARTIFACTS,
                    role=ROLE_VALIDATION_EVIDENCE,
                    tier=TIER_REQUIRED_PRIMARY,
                    reasons=(EVIDENCE_TESTS_ARE_THE_SUBJECT,),
                )
            )
            verification.append(VERIFY_VALIDATION_EVIDENCE_BEFORE_BEHAVIOUR_CLAIMS)
        elif broad or change:
            reasons = [EVIDENCE_TESTS_FOR_VERIFICATION]
            if change:
                reasons.append(EVIDENCE_CHANGE_REQUIRES_VALIDATION)
            requirements.append(
                EvidenceRequirement(
                    domain=DOMAIN_VALIDATION_ARTIFACTS,
                    role=ROLE_VALIDATION_EVIDENCE,
                    tier=TIER_REQUIRED_SECONDARY,
                    reasons=tuple(reasons),
                )
            )
            verification.append(VERIFY_VALIDATION_EVIDENCE_BEFORE_BEHAVIOUR_CLAIMS)

        # ── history, which explains and never testifies ─────────────────────
        if broad:
            requirements.append(
                EvidenceRequirement(
                    domain=DOMAIN_HISTORICAL_CONTEXT,
                    role=ROLE_HISTORICAL_CONTEXT,
                    tier=TIER_DEFERRED,
                    reasons=(EVIDENCE_HISTORY_NON_AUTHORITATIVE,),
                )
            )
            verification.append(VERIFY_CURRENT_IMPLEMENTATION_OVER_HISTORY)

        # ── classes that restate a source rather than being one ─────────────
        for source_class in (
            SOURCE_CLASS_GENERATED_ARTIFACTS,
            SOURCE_CLASS_SNAPSHOTS,
            SOURCE_CLASS_TEMPORARY_ARTIFACTS,
        ):
            deferred.append(
                DeferredSource(
                    source_class=source_class,
                    disposition=TIER_EXCLUDED_INITIALLY,
                    reasons=(EVIDENCE_GENERATED_MATERIAL_NOT_INITIAL_AUTHORITY,),
                )
            )
        deferred.append(
            DeferredSource(
                source_class=SOURCE_CLASS_DUPLICATE_RENDERINGS,
                disposition=TIER_DEFERRED,
                reasons=(EVIDENCE_GENERATED_MATERIAL_NOT_INITIAL_AUTHORITY,),
            )
        )
        if broad and not tests_are_the_subject:
            deferred.append(
                DeferredSource(
                    source_class=SOURCE_CLASS_UNRELATED_VALIDATION_ARTIFACTS,
                    disposition=TIER_DEFERRED,
                    reasons=(EVIDENCE_TESTS_FOR_VERIFICATION,),
                )
            )

    # ── information from outside the repository ──────────────────────────────
    if external:
        reasons = [EVIDENCE_EXTERNAL_CURRENT_INFO_REQUIRED]
        if cross_source:
            reasons.append(EVIDENCE_CROSS_SOURCE_RECONCILIATION_REQUIRED)
        requirements.append(
            EvidenceRequirement(
                domain=DOMAIN_EXTERNAL_INFORMATION,
                role=ROLE_CURRENT_EXTERNAL_AUTHORITY,
                tier=TIER_REQUIRED_PRIMARY,
                reasons=tuple(reasons),
            )
        )
        verification.append(VERIFY_EXTERNAL_INFORMATION_CURRENCY)

    return EvidencePolicy(
        scope=scope,
        requirements=tuple(requirements),
        deferred_sources=tuple(deferred),
        verification_requirements=tuple(dict.fromkeys(verification)),
    )


__all__ = [
    "PHASE_ID",
    "EvidencePolicy",
    "carries_direct_context_material",
    "derive_evidence_policy",
    "evidence_scope_for",
    "names_validation_artifact",
]
