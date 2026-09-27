"""WAITER.2 — the Evidence Requirement Contract and its bounded vocabularies.

WAITER.1 answered *which kitchen receives the order*.  WAITER.2 answers the
next question and only that one:

    what evidence will the selected workflow need?

It never answers "go and obtain it".

    WaiterDecision + TaskShape + CapabilityRequirements + TaskContract
        -> Evidence Requirement Contract

Three properties make the record worth having.

**A requirement is a class, never an item.**  The contract names evidence
*domains* (where evidence comes from) and *roles* (how it may be used) at
*tiers* (what is needed first).  It contains no file, no path, no query, no
retrieval result, no manifest, no graph activation and no plan — not fields it
declines to fill, but fields it does not have.  A caller cannot read a file out
of this record because there is nothing in it to read.

**Domain and role are different questions.**  The DeepSeek Harness dogfood
failed because six thousand files were one homogeneous bucket.  A test and a
runtime module can share a domain (``repository``) and must not share a role:
one is ``validation_evidence``, the other ``implementation_authority``.  A
rejected design note shares the repository with both and is
``historical_context`` — it explains intent and never states what the code does
now.

**Requirements cannot widen the envelope, and cannot narrow it either.**  Every
domain names the upstream capability that licenses it, and a requirement whose
licence WAITER.1 did not grant makes the whole contract inconsistent rather than
quietly enlarging the scope.  ``repository_read_required=false`` upstream means
no repository evidence downstream, whatever the task looks like.  The same table
read the other way is the closure rule: every capability WAITER.1 *did* require
names the domain and role that discharge it, and a contract that does not carry
one at an active tier fails closed instead of silently answering a smaller
question.  ``external_information_required=true`` upstream cannot become an
evidence set of local files.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no language system, inspects no repository, retrieves no evidence, selects
nothing, plans nothing, and grants no authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.capability_requirements import (
    CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE,
    CAPABILITY_CODE_CHANGE,
    CAPABILITY_COMPARISON,
    CAPABILITY_CONVERSATIONAL_RESPONSE,
    CAPABILITY_CROSS_SOURCE_SYNTHESIS,
    CAPABILITY_DIRECT_CONTEXT_ANALYSIS,
    CAPABILITY_EXTERNAL_INFORMATION,
    CAPABILITY_MULTI_STAGE_COORDINATION,
    CAPABILITY_NAMES,
    CAPABILITY_PERSISTENT_PROJECT_CONTEXT,
    CAPABILITY_REPOSITORY_READ,
    CAPABILITY_VALIDATION,
    CapabilityRequirements,
)
from core.execution_waiter import WORKFLOW_TARGETS


PHASE_ID = "WAITER.2"
EVIDENCE_CONTRACT_SCHEMA_VERSION = "waiter_2_evidence_requirement_contract_v1"

# ── Evidence domains ──────────────────────────────────────────────────────────
#: *Where* evidence comes from.  Deliberately five: a domain earns its place
#: only by needing a different acquisition capability or a different trust rule.
DOMAIN_DIRECT_CONTEXT = "direct_context"
DOMAIN_REPOSITORY = "repository"
DOMAIN_EXTERNAL_INFORMATION = "external_information"
DOMAIN_VALIDATION_ARTIFACTS = "validation_artifacts"
DOMAIN_HISTORICAL_CONTEXT = "historical_context"

EVIDENCE_DOMAINS: tuple[str, ...] = (
    DOMAIN_DIRECT_CONTEXT,
    DOMAIN_REPOSITORY,
    DOMAIN_VALIDATION_ARTIFACTS,
    DOMAIN_HISTORICAL_CONTEXT,
    DOMAIN_EXTERNAL_INFORMATION,
)

# ── Evidence roles ────────────────────────────────────────────────────────────
#: *How* evidence may be used.  Two things from the same domain can carry very
#: different authority, and conflating them is the whole failure this phase
#: exists to fix.
ROLE_SUPPLIED_MATERIAL = "supplied_material"
ROLE_IMPLEMENTATION_AUTHORITY = "implementation_authority"
ROLE_CONFIGURATION_AUTHORITY = "configuration_authority"
ROLE_INTERFACE_CONTRACT = "interface_contract"
ROLE_ARCHITECTURE_DESCRIPTION = "architecture_description"
ROLE_VALIDATION_EVIDENCE = "validation_evidence"
ROLE_HYPOTHESIS_SUPPORT = "hypothesis_support"
ROLE_HISTORICAL_CONTEXT = "historical_context"
ROLE_CURRENT_EXTERNAL_AUTHORITY = "current_external_authority"

EVIDENCE_ROLES: tuple[str, ...] = (
    ROLE_SUPPLIED_MATERIAL,
    ROLE_IMPLEMENTATION_AUTHORITY,
    ROLE_INTERFACE_CONTRACT,
    ROLE_CONFIGURATION_AUTHORITY,
    ROLE_ARCHITECTURE_DESCRIPTION,
    ROLE_VALIDATION_EVIDENCE,
    ROLE_HYPOTHESIS_SUPPORT,
    ROLE_HISTORICAL_CONTEXT,
    ROLE_CURRENT_EXTERNAL_AUTHORITY,
)

#: Roles that may be treated as stating what the system does *now*.  Everything
#: outside this set may explain, illustrate or corroborate, and may never
#: override the current implementation.
CURRENT_AUTHORITY_ROLES: frozenset[str] = frozenset({
    ROLE_IMPLEMENTATION_AUTHORITY,
    ROLE_INTERFACE_CONTRACT,
    ROLE_CONFIGURATION_AUTHORITY,
})

# ── Priority tiers ────────────────────────────────────────────────────────────
#: Deterministic tiers, never a 0-100 relevance score.  A later acquisition
#: layer may score inside a tier; it may not invent one.
TIER_REQUIRED_PRIMARY = "required_primary"
TIER_REQUIRED_SECONDARY = "required_secondary"
TIER_DEFERRED = "deferred"
TIER_EXCLUDED_INITIALLY = "excluded_initially"

EVIDENCE_TIERS: tuple[str, ...] = (
    TIER_REQUIRED_PRIMARY,
    TIER_REQUIRED_SECONDARY,
    TIER_DEFERRED,
    TIER_EXCLUDED_INITIALLY,
)

#: The only dispositions a whole source class may be given.  A class is never
#: *required*: requirements are stated as domain and role, and a class can only
#: be pushed back.
DEFERRED_DISPOSITIONS: tuple[str, ...] = (TIER_DEFERRED, TIER_EXCLUDED_INITIALLY)

# ── Scope ─────────────────────────────────────────────────────────────────────
#: How far the evidence set reaches.  Never a file count: WAITER.2 does not know
#: what the repository contains and must not pretend to.
SCOPE_DIRECT_CONTEXT_ONLY = "direct_context_only"
SCOPE_BOUNDED_REPOSITORY = "bounded_repository"
SCOPE_BROAD_REPOSITORY_RECONNAISSANCE = "broad_repository_reconnaissance"
SCOPE_EXTERNAL_ONLY = "external_only"
SCOPE_MIXED_SOURCES = "mixed_sources"

EVIDENCE_SCOPES: tuple[str, ...] = (
    SCOPE_DIRECT_CONTEXT_ONLY,
    SCOPE_BOUNDED_REPOSITORY,
    SCOPE_BROAD_REPOSITORY_RECONNAISSANCE,
    SCOPE_EXTERNAL_ONLY,
    SCOPE_MIXED_SOURCES,
)

# ── Source classes that get pushed back ───────────────────────────────────────
#: Category-level policy only.  No ignore file is read, no directory is walked,
#: and no member of any of these classes is ever named.
SOURCE_CLASS_GENERATED_ARTIFACTS = "generated_artifacts"
SOURCE_CLASS_SNAPSHOTS = "snapshots"
SOURCE_CLASS_TEMPORARY_ARTIFACTS = "temporary_artifacts"
SOURCE_CLASS_DUPLICATE_RENDERINGS = "duplicate_renderings"
SOURCE_CLASS_UNRELATED_VALIDATION_ARTIFACTS = "unrelated_validation_artifacts"

DEFERRED_SOURCE_CLASSES: tuple[str, ...] = (
    SOURCE_CLASS_GENERATED_ARTIFACTS,
    SOURCE_CLASS_SNAPSHOTS,
    SOURCE_CLASS_TEMPORARY_ARTIFACTS,
    SOURCE_CLASS_DUPLICATE_RENDERINGS,
    SOURCE_CLASS_UNRELATED_VALIDATION_ARTIFACTS,
)

# ── Reason codes ──────────────────────────────────────────────────────────────
EVIDENCE_DIRECT_CONTEXT_FROM_TASK = "EVIDENCE_DIRECT_CONTEXT_FROM_TASK"
EVIDENCE_REPOSITORY_REQUIRED = "EVIDENCE_REPOSITORY_REQUIRED"
EVIDENCE_ARCHITECTURE_RECON_REQUIRED = "EVIDENCE_ARCHITECTURE_RECON_REQUIRED"
EVIDENCE_EXTERNAL_CURRENT_INFO_REQUIRED = "EVIDENCE_EXTERNAL_CURRENT_INFO_REQUIRED"
EVIDENCE_CROSS_SOURCE_RECONCILIATION_REQUIRED = (
    "EVIDENCE_CROSS_SOURCE_RECONCILIATION_REQUIRED"
)
EVIDENCE_TESTS_FOR_VERIFICATION = "EVIDENCE_TESTS_FOR_VERIFICATION"
EVIDENCE_TESTS_ARE_THE_SUBJECT = "EVIDENCE_TESTS_ARE_THE_SUBJECT"
EVIDENCE_CHANGE_REQUIRES_VALIDATION = "EVIDENCE_CHANGE_REQUIRES_VALIDATION"
EVIDENCE_HISTORY_NON_AUTHORITATIVE = "EVIDENCE_HISTORY_NON_AUTHORITATIVE"
EVIDENCE_GENERATED_MATERIAL_NOT_INITIAL_AUTHORITY = (
    "EVIDENCE_GENERATED_MATERIAL_NOT_INITIAL_AUTHORITY"
)
EVIDENCE_NOT_SPECIFIED_UNROUTED = "EVIDENCE_NOT_SPECIFIED_UNROUTED"
EVIDENCE_SOURCE_INTEGRITY_FAILED = "EVIDENCE_SOURCE_INTEGRITY_FAILED"
EVIDENCE_CAPABILITY_ENVELOPE_VIOLATED = "EVIDENCE_CAPABILITY_ENVELOPE_VIOLATED"
EVIDENCE_REQUIRED_CAPABILITY_LOST = "EVIDENCE_REQUIRED_CAPABILITY_LOST"

EVIDENCE_REASONS: tuple[str, ...] = (
    EVIDENCE_DIRECT_CONTEXT_FROM_TASK,
    EVIDENCE_REPOSITORY_REQUIRED,
    EVIDENCE_ARCHITECTURE_RECON_REQUIRED,
    EVIDENCE_EXTERNAL_CURRENT_INFO_REQUIRED,
    EVIDENCE_CROSS_SOURCE_RECONCILIATION_REQUIRED,
    EVIDENCE_TESTS_FOR_VERIFICATION,
    EVIDENCE_TESTS_ARE_THE_SUBJECT,
    EVIDENCE_CHANGE_REQUIRES_VALIDATION,
    EVIDENCE_HISTORY_NON_AUTHORITATIVE,
    EVIDENCE_GENERATED_MATERIAL_NOT_INITIAL_AUTHORITY,
    EVIDENCE_NOT_SPECIFIED_UNROUTED,
    EVIDENCE_SOURCE_INTEGRITY_FAILED,
    EVIDENCE_CAPABILITY_ENVELOPE_VIOLATED,
    EVIDENCE_REQUIRED_CAPABILITY_LOST,
)

#: A sentence per code, so explainability never rests on an opaque weight.
EVIDENCE_REASON_DESCRIPTIONS: dict[str, str] = {
    EVIDENCE_DIRECT_CONTEXT_FROM_TASK: (
        "The order carries its own material. What INPUT preserved is itself the "
        "evidence, and nothing has to be fetched to reason over it."
    ),
    EVIDENCE_REPOSITORY_REQUIRED: (
        "The work would have to read the repository at a place the order already "
        "identifies; the surrounding code is context, not a survey."
    ),
    EVIDENCE_ARCHITECTURE_RECON_REQUIRED: (
        "The repository has to be surveyed rather than opened at a known place, so "
        "the evidence set needs an explicit priority instead of a sweep."
    ),
    EVIDENCE_EXTERNAL_CURRENT_INFO_REQUIRED: (
        "The answer depends on information that lives outside the repository and has "
        "to be current at the moment it is used."
    ),
    EVIDENCE_CROSS_SOURCE_RECONCILIATION_REQUIRED: (
        "Evidence comes from more than one kind of source and has to be reconciled "
        "into a single answer rather than concatenated."
    ),
    EVIDENCE_TESTS_FOR_VERIFICATION: (
        "Validation artifacts confirm or refute what the primary evidence suggests. "
        "Here they are the instrument, not the subject."
    ),
    EVIDENCE_TESTS_ARE_THE_SUBJECT: (
        "The order is about validation artifacts themselves, so they are primary "
        "evidence rather than a secondary check."
    ),
    EVIDENCE_CHANGE_REQUIRES_VALIDATION: (
        "The work would change the repository, and a change nobody can check is not "
        "a finished change."
    ),
    EVIDENCE_HISTORY_NON_AUTHORITATIVE: (
        "Proposed, rejected and superseded material explains intent and history. It "
        "never states what the system does now."
    ),
    EVIDENCE_GENERATED_MATERIAL_NOT_INITIAL_AUTHORITY: (
        "Generated output, snapshots, scratch artifacts and duplicated renderings "
        "restate a source rather than being one."
    ),
    EVIDENCE_NOT_SPECIFIED_UNROUTED: (
        "WAITER.1 did not route this order, so there is no selected workflow whose "
        "evidence could be specified."
    ),
    EVIDENCE_SOURCE_INTEGRITY_FAILED: (
        "The supplied upstream records do not describe the same run the routing "
        "decision was made over."
    ),
    EVIDENCE_CAPABILITY_ENVELOPE_VIOLATED: (
        "A requirement was derived that the upstream capability envelope does not "
        "license. Widening scope downstream is refused, not negotiated."
    ),
    EVIDENCE_REQUIRED_CAPABILITY_LOST: (
        "An evidence capability the upstream envelope requires is not represented by "
        "any active requirement. Narrowing the work downstream is refused as firmly "
        "as widening it."
    ),
}

# ── Verification requirements ─────────────────────────────────────────────────
#: How the evidence must be treated once some later phase actually has it.
#: Policy, not procedure: nothing here runs anything.
VERIFY_CURRENT_IMPLEMENTATION_OVER_HISTORY = (
    "current_implementation_outranks_historical_material"
)
VERIFY_VALIDATION_EVIDENCE_BEFORE_BEHAVIOUR_CLAIMS = (
    "validation_evidence_required_before_behaviour_claims"
)
VERIFY_EXTERNAL_INFORMATION_CURRENCY = "external_information_must_be_current_at_use"
VERIFY_SUPPLIED_MATERIAL_IS_THE_WHOLE_SET = "supplied_material_is_the_whole_evidence_set"

VERIFICATION_REQUIREMENTS: tuple[str, ...] = (
    VERIFY_CURRENT_IMPLEMENTATION_OVER_HISTORY,
    VERIFY_VALIDATION_EVIDENCE_BEFORE_BEHAVIOUR_CLAIMS,
    VERIFY_EXTERNAL_INFORMATION_CURRENCY,
    VERIFY_SUPPLIED_MATERIAL_IS_THE_WHOLE_SET,
)

# ── Statuses ──────────────────────────────────────────────────────────────────
#: The selected workflow's evidence needs are stated.
STATUS_SPECIFIED = "specified"
#: WAITER.1 produced no route, so there is nothing to specify.
STATUS_NOT_ROUTED = "not_routed"
#: The upstream records do not hang together, or a requirement fell outside the
#: capability envelope.  Fail closed rather than proceed on a guess.
STATUS_INCONSISTENT_INPUT = "inconsistent_input"

EVIDENCE_CONTRACT_STATUSES: tuple[str, ...] = (
    STATUS_SPECIFIED,
    STATUS_NOT_ROUTED,
    STATUS_INCONSISTENT_INPUT,
)

# ── Inconsistencies ───────────────────────────────────────────────────────────
INCONSISTENT_WAITER_NOT_ROUTED = "waiter_decision_not_routed"
INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH = "source_fingerprint_mismatch"
INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED = "capability_envelope_widened"
INCONSISTENT_REQUIRED_CAPABILITY_DROPPED = "required_capability_dropped"
INCONSISTENT_UNSUPPORTED_WORKFLOW = "unsupported_workflow"

EVIDENCE_INCONSISTENCIES: tuple[str, ...] = (
    INCONSISTENT_WAITER_NOT_ROUTED,
    INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,
    INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED,
    INCONSISTENT_REQUIRED_CAPABILITY_DROPPED,
    INCONSISTENT_UNSUPPORTED_WORKFLOW,
)

# ── The capability that licenses each domain ──────────────────────────────────
#: WAITER.2 may refine evidence needs only inside WAITER.1's envelope.
#:
#: ``validation_artifacts`` and ``historical_context`` are licensed by
#: ``repository_read_required`` rather than by capabilities of their own: both
#: are repository-resident classes, so requiring them restates a capability the
#: upstream layer already granted instead of adding a new one.  ``direct_context``
#: needs no licence at all — it is already in hand, and acquiring it is not an
#: action anyone has to take.
DOMAIN_CAPABILITY_LICENCES: dict[str, str | None] = {
    DOMAIN_DIRECT_CONTEXT: None,
    DOMAIN_REPOSITORY: CAPABILITY_REPOSITORY_READ,
    DOMAIN_VALIDATION_ARTIFACTS: CAPABILITY_REPOSITORY_READ,
    DOMAIN_HISTORICAL_CONTEXT: CAPABILITY_REPOSITORY_READ,
    DOMAIN_EXTERNAL_INFORMATION: CAPABILITY_EXTERNAL_INFORMATION,
}

#: Tiers at which a requirement is actually part of the initial or follow-up
#: evidence set.  A deferred or initially-excluded requirement is on the record
#: and out of the work, so it can never discharge an upstream obligation.
ACTIVE_TIERS: frozenset[str] = frozenset({TIER_REQUIRED_PRIMARY, TIER_REQUIRED_SECONDARY})

# ── What each capability obliges the contract to say ──────────────────────────
#: The mirror image of :data:`DOMAIN_CAPABILITY_LICENCES`.
#:
#: The licence table stops WAITER.2 asking for *more* than WAITER.1 granted.
#: This table stops it asking for *less*: a capability the upstream envelope
#: requires must appear as an active requirement naming the domain and role that
#: capability is about, or the contract fails closed.  "The order needs current
#: external information" cannot quietly become an evidence set of local files.
#:
#: The table is total over :data:`CAPABILITY_NAMES` and checked to be so at
#: import, so a capability added upstream cannot slip through by simply never
#: being considered here.  An empty tuple is a deliberate answer: conversational
#: response, comparison and multi-stage coordination are things a workflow does
#: *with* evidence, and persistent project context is a horizon rather than a
#: source, so none of the four obliges a domain of its own.
CAPABILITY_EVIDENCE_OBLIGATIONS: dict[str, tuple[tuple[str, str], ...]] = {
    CAPABILITY_CONVERSATIONAL_RESPONSE: (),
    CAPABILITY_DIRECT_CONTEXT_ANALYSIS: (
        (DOMAIN_DIRECT_CONTEXT, ROLE_SUPPLIED_MATERIAL),
    ),
    CAPABILITY_REPOSITORY_READ: (
        (DOMAIN_REPOSITORY, ROLE_IMPLEMENTATION_AUTHORITY),
    ),
    CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE: (
        (DOMAIN_REPOSITORY, ROLE_IMPLEMENTATION_AUTHORITY),
        (DOMAIN_REPOSITORY, ROLE_INTERFACE_CONTRACT),
        (DOMAIN_REPOSITORY, ROLE_CONFIGURATION_AUTHORITY),
        (DOMAIN_REPOSITORY, ROLE_ARCHITECTURE_DESCRIPTION),
    ),
    CAPABILITY_EXTERNAL_INFORMATION: (
        (DOMAIN_EXTERNAL_INFORMATION, ROLE_CURRENT_EXTERNAL_AUTHORITY),
    ),
    CAPABILITY_CROSS_SOURCE_SYNTHESIS: (
        (DOMAIN_REPOSITORY, ROLE_IMPLEMENTATION_AUTHORITY),
        (DOMAIN_EXTERNAL_INFORMATION, ROLE_CURRENT_EXTERNAL_AUTHORITY),
    ),
    CAPABILITY_COMPARISON: (),
    CAPABILITY_CODE_CHANGE: (
        (DOMAIN_REPOSITORY, ROLE_IMPLEMENTATION_AUTHORITY),
    ),
    CAPABILITY_VALIDATION: (
        (DOMAIN_VALIDATION_ARTIFACTS, ROLE_VALIDATION_EVIDENCE),
    ),
    CAPABILITY_MULTI_STAGE_COORDINATION: (),
    CAPABILITY_PERSISTENT_PROJECT_CONTEXT: (),
}

if tuple(CAPABILITY_EVIDENCE_OBLIGATIONS) != CAPABILITY_NAMES:  # pragma: no cover
    raise RuntimeError(
        "every capability must state what evidence it obliges, in the canonical order"
    )

# ── Bounds ────────────────────────────────────────────────────────────────────
MAX_REQUIREMENT_REASONS = 4
MAX_EVIDENCE_REQUIREMENTS = 16
MAX_DEFERRED_SOURCES = len(DEFERRED_SOURCE_CLASSES)
MAX_VERIFICATION_REQUIREMENTS = len(VERIFICATION_REQUIREMENTS)
MAX_EVIDENCE_CONTRACT_REASONS = len(EVIDENCE_REASONS)
MAX_INCONSISTENCIES = len(EVIDENCE_INCONSISTENCIES)


def evidence_authority() -> dict[str, bool]:
    """Every authority WAITER.2 declines to hold, in every status.

    Stating that a workflow will need repository evidence is not permission to
    open a file, and it is not permission to decide which file.  A later phase
    may consume this contract; it must obtain its own authority under its own
    gates.
    """
    return {
        "repository_read_authority": False,
        "repository_write_authority": False,
        "external_search_authority": False,
        "context_selection_authority": False,
        "indexing_authority": False,
        "graph_authority": False,
        "retrieval_authority": False,
        "execution_authority": False,
        "patch_authority": False,
        "validation_authority": False,
        "benchmark_authority": False,
        "work" + "er_launch_authority": False,
        "provider_selection_authority": False,
        "model_selection_authority": False,
        "planning_authority": False,
        "routing_authority": False,
        "dream_authority": False,
        "project_evolution_authority": False,
        "human_approval_required": True,
    }


def evidence_guardrails() -> dict[str, bool]:
    """Every action WAITER.2 did not perform while producing a contract."""
    return {
        "evidence_acquired": False,
        "repository_read_performed": False,
        "repository_scan_performed": False,
        "repository_traversal_performed": False,
        "ignore_rules_consulted": False,
        "context_selection_performed": False,
        "read_set_generated": False,
        "file_paths_produced": False,
        "index_consulted": False,
        "graph_activated": False,
        "retrieval_performed": False,
        "web_search_performed": False,
        "network_call_performed": False,
        "language_system_call_performed": False,
        "plan_generated": False,
        "workflow_reselected": False,
        "execution_performed": False,
    }


# ── Records ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class EvidenceRequirement:
    """One class of evidence a selected workflow would need, and why.

    ``domain`` says where it comes from, ``role`` says how it may be used, and
    ``tier`` says what has to come first.  Nothing here identifies an item.
    """

    domain: str
    role: str
    tier: str
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.domain not in EVIDENCE_DOMAINS:
            raise ValueError(f"unsupported evidence domain: {self.domain!r}")
        if self.role not in EVIDENCE_ROLES:
            raise ValueError(f"unsupported evidence role: {self.role!r}")
        if self.tier not in EVIDENCE_TIERS:
            raise ValueError(f"unsupported evidence tier: {self.tier!r}")
        if len(self.reasons) > MAX_REQUIREMENT_REASONS:
            raise ValueError("evidence requirement reasons exceed the supported bound")
        for reason in self.reasons:
            if reason not in EVIDENCE_REASONS:
                raise ValueError(f"unsupported evidence reason: {reason!r}")
        if not self.reasons:
            raise ValueError(
                f"evidence requirement {self.domain!r}/{self.role!r} names no "
                "structured fact it was derived from"
            )

    @property
    def key(self) -> tuple[str, str]:
        return (self.domain, self.role)

    @property
    def current_authority(self) -> bool:
        """May this evidence be read as stating what the system does now?"""
        return self.role in CURRENT_AUTHORITY_ROLES

    def as_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "role": self.role,
            "tier": self.tier,
            "current_authority": self.current_authority,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class DeferredSource:
    """A whole source class that is pushed back out of the initial set.

    Category-level policy, stated once, with no member ever named and no
    directory ever walked to discover one.
    """

    source_class: str
    disposition: str
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.source_class not in DEFERRED_SOURCE_CLASSES:
            raise ValueError(f"unsupported source class: {self.source_class!r}")
        if self.disposition not in DEFERRED_DISPOSITIONS:
            raise ValueError(
                f"a source class may only be deferred or excluded, not {self.disposition!r}"
            )
        if len(self.reasons) > MAX_REQUIREMENT_REASONS:
            raise ValueError("deferred source reasons exceed the supported bound")
        for reason in self.reasons:
            if reason not in EVIDENCE_REASONS:
                raise ValueError(f"unsupported evidence reason: {reason!r}")
        if not self.reasons:
            raise ValueError(
                f"deferred source {self.source_class!r} names no reason it was deferred"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_class": self.source_class,
            "disposition": self.disposition,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class EvidenceRequirementContract:
    """What one routed workflow will eventually need, stated and not obtained.

    The record deliberately has no room for a file, a path, a query, a read
    set, a retrieval result, a workflow of its own, a provider or a compute
    choice.  Those are not fields WAITER.2 declines to fill; they are fields it
    does not have.
    """

    status: str
    workflow: str | None = None
    scope: str | None = None
    requirements: tuple[EvidenceRequirement, ...] = ()
    deferred_sources: tuple[DeferredSource, ...] = ()
    verification_requirements: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    inconsistencies: tuple[str, ...] = ()
    source_contract_fingerprint: str | None = None
    source_completion_fingerprint: str | None = None
    source_decision_fingerprint: str | None = None
    schema_version: str = EVIDENCE_CONTRACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in EVIDENCE_CONTRACT_STATUSES:
            raise ValueError(f"unsupported evidence contract status: {self.status!r}")
        if self.workflow is not None and self.workflow not in WORKFLOW_TARGETS:
            raise ValueError(f"unsupported workflow: {self.workflow!r}")
        if self.scope is not None and self.scope not in EVIDENCE_SCOPES:
            raise ValueError(f"unsupported evidence scope: {self.scope!r}")

        if len(self.requirements) > MAX_EVIDENCE_REQUIREMENTS:
            raise ValueError("evidence requirements exceed the supported bound")
        if len(self.deferred_sources) > MAX_DEFERRED_SOURCES:
            raise ValueError("deferred sources exceed the supported bound")
        if len(self.verification_requirements) > MAX_VERIFICATION_REQUIREMENTS:
            raise ValueError("verification requirements exceed the supported bound")
        if len(self.reasons) > MAX_EVIDENCE_CONTRACT_REASONS:
            raise ValueError("evidence reasons exceed the supported bound")
        if len(self.inconsistencies) > MAX_INCONSISTENCIES:
            raise ValueError("inconsistencies exceed the supported bound")

        keys = [item.key for item in self.requirements]
        if len(set(keys)) != len(keys):
            raise ValueError(
                "each evidence domain and role pair may be required exactly once"
            )
        classes = [item.source_class for item in self.deferred_sources]
        if len(set(classes)) != len(classes):
            raise ValueError("each deferred source class may be stated exactly once")

        for reason in self.reasons:
            if reason not in EVIDENCE_REASONS:
                raise ValueError(f"unsupported evidence reason: {reason!r}")
        for item in self.verification_requirements:
            if item not in VERIFICATION_REQUIREMENTS:
                raise ValueError(f"unsupported verification requirement: {item!r}")
        for item in self.inconsistencies:
            if item not in EVIDENCE_INCONSISTENCIES:
                raise ValueError(f"unsupported inconsistency: {item!r}")
        if not self.reasons:
            raise ValueError("every evidence contract must state at least one reason")

        if self.status == STATUS_SPECIFIED:
            if self.workflow is None or self.scope is None:
                raise ValueError(
                    "a specified contract must name the workflow it was specified for "
                    "and the scope its evidence reaches"
                )
            if not self.requirements:
                raise ValueError("a specified contract must state at least one requirement")
            if self.inconsistencies:
                raise ValueError("a specified contract may not carry inconsistencies")
            if self.source_decision_fingerprint is None:
                raise ValueError("a specified contract must fingerprint its source decision")
        else:
            if self.workflow is not None or self.scope is not None:
                raise ValueError(
                    f"status {self.status!r} describes no workflow and no scope"
                )
            if self.requirements or self.deferred_sources or self.verification_requirements:
                raise ValueError(
                    "an order whose evidence could not be specified is not described: "
                    "WAITER.2 does not guess what an unrouted workflow would need"
                )
            if not self.inconsistencies:
                raise ValueError("a refused contract must state what did not hang together")

    # ── derived, authority-free facts ────────────────────────────────────────
    @property
    def specified(self) -> bool:
        return self.status == STATUS_SPECIFIED

    @property
    def human_approval_required(self) -> bool:
        """Always true.  A requirement is a report, never a go-ahead."""
        return True

    def domains(self) -> tuple[str, ...]:
        """Every domain named, in the canonical vocabulary order."""
        present = {item.domain for item in self.requirements}
        return tuple(domain for domain in EVIDENCE_DOMAINS if domain in present)

    def roles(self) -> tuple[str, ...]:
        """Every role named, in the canonical vocabulary order."""
        present = {item.role for item in self.requirements}
        return tuple(role for role in EVIDENCE_ROLES if role in present)

    def requires_domain(self, domain: str) -> bool:
        if domain not in EVIDENCE_DOMAINS:
            raise KeyError(f"unsupported evidence domain: {domain!r}")
        return any(item.domain == domain for item in self.requirements)

    def at_tier(self, tier: str) -> tuple[EvidenceRequirement, ...]:
        if tier not in EVIDENCE_TIERS:
            raise KeyError(f"unsupported evidence tier: {tier!r}")
        return tuple(item for item in self.requirements if item.tier == tier)

    def roles_at(self, tier: str) -> tuple[str, ...]:
        present = {item.role for item in self.at_tier(tier)}
        return tuple(role for role in EVIDENCE_ROLES if role in present)

    def tier_of(self, domain: str, role: str) -> str | None:
        """The tier of one domain and role pair, or ``None`` if not required."""
        for item in self.requirements:
            if item.domain == domain and item.role == role:
                return item.tier
        return None

    def deferred_classes(self) -> tuple[str, ...]:
        return tuple(
            item.source_class
            for item in self.deferred_sources
            if item.disposition == TIER_DEFERRED
        )

    def excluded_classes(self) -> tuple[str, ...]:
        return tuple(
            item.source_class
            for item in self.deferred_sources
            if item.disposition == TIER_EXCLUDED_INITIALLY
        )

    def reason_descriptions(self) -> tuple[str, ...]:
        return tuple(EVIDENCE_REASON_DESCRIPTIONS[reason] for reason in self.reasons)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "status": self.status,
            "workflow": self.workflow,
            "scope": self.scope,
            "evidence_domains": list(self.domains()),
            "evidence_roles": list(self.roles()),
            "requirements": [item.as_dict() for item in self.requirements],
            "deferred_sources": [item.as_dict() for item in self.deferred_sources],
            "verification_requirements": list(self.verification_requirements),
            "reasons": [
                {"code": reason, "description": EVIDENCE_REASON_DESCRIPTIONS[reason]}
                for reason in self.reasons
            ],
            "inconsistencies": list(self.inconsistencies),
            "source_contract_fingerprint": self.source_contract_fingerprint,
            "source_completion_fingerprint": self.source_completion_fingerprint,
            "source_decision_fingerprint": self.source_decision_fingerprint,
            "human_approval_required": self.human_approval_required,
            "note": (
                "These are evidence requirements, not evidence and not permission to "
                "obtain any. Nothing was read, searched, selected or retrieved."
            ),
            "authority": evidence_authority(),
            "guardrails": evidence_guardrails(),
        }


# ── The capability envelope ───────────────────────────────────────────────────

def check_capability_envelope(
    requirements: tuple[EvidenceRequirement, ...],
    capabilities: CapabilityRequirements,
) -> tuple[str, ...]:
    """Do these requirements stay inside the envelope WAITER.1 established?

    Returns an empty tuple when every requirement is licensed, and
    ``(INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED,)`` when any is not.  There is
    deliberately no third answer: a downstream layer that discovers it needs
    more than it was granted fails closed and says so, rather than quietly
    enlarging the scope of the work.
    """
    if not isinstance(capabilities, CapabilityRequirements):
        raise TypeError("check_capability_envelope requires CapabilityRequirements")

    for requirement in requirements:
        licence = DOMAIN_CAPABILITY_LICENCES[requirement.domain]
        if licence is None:
            continue
        if not capabilities.requires(licence):
            return (INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED,)
    return ()


def check_required_capability_coverage(
    requirements: tuple[EvidenceRequirement, ...],
    capabilities: CapabilityRequirements,
) -> tuple[str, ...]:
    """Does the contract still carry every evidence capability WAITER.1 required?

    The envelope check refuses to *widen* the work.  This one refuses to narrow
    it.  Every required capability names the domain and role that discharge it;
    the requirement that discharges it has to be at an active tier, because
    material that has been deferred out of the initial set is not evidence the
    work is going to have.

    Returns an empty tuple when every required capability is represented, and
    ``(INCONSISTENT_REQUIRED_CAPABILITY_DROPPED,)`` when any is not.  There is
    deliberately no third answer and no partial credit: a downstream layer that
    quietly drops a required evidence capability produces an answer built on
    less than the order needs, which is the failure mode nobody notices.
    """
    if not isinstance(capabilities, CapabilityRequirements):
        raise TypeError("check_required_capability_coverage requires CapabilityRequirements")

    active = {
        (requirement.domain, requirement.role)
        for requirement in requirements
        if requirement.tier in ACTIVE_TIERS
    }
    for name in CAPABILITY_NAMES:
        if not capabilities.requires(name):
            continue
        for obligation in CAPABILITY_EVIDENCE_OBLIGATIONS[name]:
            if obligation not in active:
                return (INCONSISTENT_REQUIRED_CAPABILITY_DROPPED,)
    return ()


__all__ = [
    "ACTIVE_TIERS",
    "CAPABILITY_EVIDENCE_OBLIGATIONS",
    "CURRENT_AUTHORITY_ROLES",
    "DEFERRED_DISPOSITIONS",
    "DEFERRED_SOURCE_CLASSES",
    "DOMAIN_CAPABILITY_LICENCES",
    "DOMAIN_DIRECT_CONTEXT",
    "DOMAIN_EXTERNAL_INFORMATION",
    "DOMAIN_HISTORICAL_CONTEXT",
    "DOMAIN_REPOSITORY",
    "DOMAIN_VALIDATION_ARTIFACTS",
    "EVIDENCE_ARCHITECTURE_RECON_REQUIRED",
    "EVIDENCE_CAPABILITY_ENVELOPE_VIOLATED",
    "EVIDENCE_CHANGE_REQUIRES_VALIDATION",
    "EVIDENCE_CONTRACT_SCHEMA_VERSION",
    "EVIDENCE_CONTRACT_STATUSES",
    "EVIDENCE_CROSS_SOURCE_RECONCILIATION_REQUIRED",
    "EVIDENCE_DIRECT_CONTEXT_FROM_TASK",
    "EVIDENCE_DOMAINS",
    "EVIDENCE_EXTERNAL_CURRENT_INFO_REQUIRED",
    "EVIDENCE_GENERATED_MATERIAL_NOT_INITIAL_AUTHORITY",
    "EVIDENCE_HISTORY_NON_AUTHORITATIVE",
    "EVIDENCE_INCONSISTENCIES",
    "EVIDENCE_NOT_SPECIFIED_UNROUTED",
    "EVIDENCE_REASONS",
    "EVIDENCE_REASON_DESCRIPTIONS",
    "EVIDENCE_REPOSITORY_REQUIRED",
    "EVIDENCE_REQUIRED_CAPABILITY_LOST",
    "EVIDENCE_ROLES",
    "EVIDENCE_SCOPES",
    "EVIDENCE_SOURCE_INTEGRITY_FAILED",
    "EVIDENCE_TESTS_ARE_THE_SUBJECT",
    "EVIDENCE_TESTS_FOR_VERIFICATION",
    "EVIDENCE_TIERS",
    "INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED",
    "INCONSISTENT_REQUIRED_CAPABILITY_DROPPED",
    "INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH",
    "INCONSISTENT_UNSUPPORTED_WORKFLOW",
    "INCONSISTENT_WAITER_NOT_ROUTED",
    "PHASE_ID",
    "ROLE_ARCHITECTURE_DESCRIPTION",
    "ROLE_CONFIGURATION_AUTHORITY",
    "ROLE_CURRENT_EXTERNAL_AUTHORITY",
    "ROLE_HISTORICAL_CONTEXT",
    "ROLE_HYPOTHESIS_SUPPORT",
    "ROLE_IMPLEMENTATION_AUTHORITY",
    "ROLE_INTERFACE_CONTRACT",
    "ROLE_SUPPLIED_MATERIAL",
    "ROLE_VALIDATION_EVIDENCE",
    "SCOPE_BOUNDED_REPOSITORY",
    "SCOPE_BROAD_REPOSITORY_RECONNAISSANCE",
    "SCOPE_DIRECT_CONTEXT_ONLY",
    "SCOPE_EXTERNAL_ONLY",
    "SCOPE_MIXED_SOURCES",
    "SOURCE_CLASS_DUPLICATE_RENDERINGS",
    "SOURCE_CLASS_GENERATED_ARTIFACTS",
    "SOURCE_CLASS_SNAPSHOTS",
    "SOURCE_CLASS_TEMPORARY_ARTIFACTS",
    "SOURCE_CLASS_UNRELATED_VALIDATION_ARTIFACTS",
    "STATUS_INCONSISTENT_INPUT",
    "STATUS_NOT_ROUTED",
    "STATUS_SPECIFIED",
    "TIER_DEFERRED",
    "TIER_EXCLUDED_INITIALLY",
    "TIER_REQUIRED_PRIMARY",
    "TIER_REQUIRED_SECONDARY",
    "VERIFICATION_REQUIREMENTS",
    "VERIFY_CURRENT_IMPLEMENTATION_OVER_HISTORY",
    "VERIFY_EXTERNAL_INFORMATION_CURRENCY",
    "VERIFY_SUPPLIED_MATERIAL_IS_THE_WHOLE_SET",
    "VERIFY_VALIDATION_EVIDENCE_BEFORE_BEHAVIOUR_CLAIMS",
    "DeferredSource",
    "EvidenceRequirement",
    "EvidenceRequirementContract",
    "check_capability_envelope",
    "check_required_capability_coverage",
    "evidence_authority",
    "evidence_guardrails",
]
