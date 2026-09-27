"""WAITER.1 — the deterministic capability-based execution router.

The Semantic Waiter understands what the customer ordered.  The Execution
Waiter decides which kitchen has the equipment to cook it — and then stops at
the kitchen door.

    TaskContract + CompletionDecision
        -> hard handoff eligibility gate       [core.waiter_receipt]
        -> Task Shape                          [core.task_shape]
        -> Capability Requirements             [core.capability_requirements]
        -> deterministic workflow policy       [here]
        -> WaiterDecision

The layer that was missing is the middle one.  A comparative architecture
request used to fall into Instant Run because the router jumped straight from
words to a mode; nothing in between ever asked *what the order would require*.
Once the question is asked, "compare A and B from what I pasted" and "compare
A and B by inspecting both repositories" stop looking alike: they share an
analysis shape and differ in evidence scope, and it is the evidence scope that
needs a workflow able to reconnoitre.

    The noun "compare" never decides a route.

Three boundaries hold in every status.

**Workflow is not compute.**  WAITER.1 recommends a workflow class.  It never
names a provider, a model, a model size, local or cloud, or a fallback chain,
and a COMMANDER route is not a request for a bigger model.

**A recommendation is not authority.**  Every decision serialises an authority
block with execution, repository read and write, patch, validation, worker
launch, provider and model selection, planning, context selection, dream and
project-evolution authority all false.  ``recommended_workflow=project_evolution``
does not grant ``project_evolution_authority`` — and nothing short of a
declaration the user actually authorised can even reach that recommendation.

**Recommending is not planning.**  The decision stops at the workflow name.
There are no stages, no read set, no file list, and no reconnaissance.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no model, inspects no repository, retrieves no evidence, plans nothing,
selects no provider or model, dispatches nothing, and is wired into no live
path.
"""

from __future__ import annotations

import json
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
    CAPABILITY_PERSISTENT_PROJECT_CONTEXT,
    CAPABILITY_REPOSITORY_READ,
    CapabilityRequirements,
    derive_capability_requirements,
)
from core.intake_completion import CompletionDecision
from core.task_contract import TaskContract
from core.task_shape import (
    DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NEGATED,
    DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NOT_LITERALLY_SUPPORTED,
    DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_AUTHORIZED,
    DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_REQUESTED,
    DISQUALIFIER_PROJECT_EVOLUTION_PROVENANCE_UNVERIFIED,
    FAMILY_UNKNOWN,
    PROJECT_EVOLUTION_DISQUALIFIERS,
    ProjectEvolutionRequest,
    ProjectEvolutionVerification,
    TaskShape,
    check_project_evolution_request,
    derive_task_shape,
    verify_project_evolution_request,
)
from core.waiter_receipt import (
    GATE_BLOCKERS,
    WaiterReceipt,
    check_handoff_eligibility,
    waiter_authority,
    waiter_guardrails,
)


PHASE_ID = "WAITER.1"
WAITER_DECISION_SCHEMA_VERSION = "waiter_1_decision_v1"

#: The stages WAITER.1 owns, in order.  Planning, reconnaissance, context
#: selection and execution are deliberately absent — they are the kitchen.
EXECUTION_WAITER_STAGES: tuple[str, ...] = (
    "handoff_eligibility_gate",
    "task_shape_derivation",
    "capability_requirement_derivation",
    "deterministic_workflow_policy",
)

# ── Statuses ──────────────────────────────────────────────────────────────────
#: A workflow class has the capabilities this order requires.
STATUS_ROUTED = "routed"
#: INPUT did not hand this order over.  Nothing downstream is described.
STATUS_NOT_HANDOFF_READY = "not_handoff_ready"
#: The order was handed over, but its shape does not determine a workflow.
STATUS_UNCERTAIN = "uncertain"

#: Three, and no more.  An ``unsupported`` status was considered and not
#: created: every capability in the bounded vocabulary is within reach of one
#: of the four workflow classes, so the status could never be produced, and a
#: status that cannot occur is decoration rather than honesty.
WAITER_STATUSES: tuple[str, ...] = (
    STATUS_ROUTED,
    STATUS_NOT_HANDOFF_READY,
    STATUS_UNCERTAIN,
)

# ── Workflow targets ──────────────────────────────────────────────────────────
#: Execution workflow *classes*, in the repository's existing vocabulary.
#: A workflow is a set of capabilities, never a model, a provider or a budget.
WORKFLOW_CHAT = "chat"
WORKFLOW_INSTANT_RUN = "instant_run"
WORKFLOW_COMMANDER = "commander"
WORKFLOW_PROJECT_EVOLUTION = "project_evolution"

WORKFLOW_TARGETS: tuple[str, ...] = (
    WORKFLOW_CHAT,
    WORKFLOW_INSTANT_RUN,
    WORKFLOW_COMMANDER,
    WORKFLOW_PROJECT_EVOLUTION,
)

#: How each class is named by the existing interaction shells.  Mixed Mode and
#: the Unified Workbench are shells that dispatch; neither is a workflow class,
#: and neither may be recommended here.  Goal Brief is an intake projection and
#: is likewise not a workflow.
WORKFLOW_SHELL_NAMES: dict[str, tuple[str, ...]] = {
    WORKFLOW_CHAT: ("chat",),
    WORKFLOW_INSTANT_RUN: ("instant_run",),
    WORKFLOW_COMMANDER: ("commander_plan", "commander_run"),
    WORKFLOW_PROJECT_EVOLUTION: ("project_evolution",),
}

# ── Reason codes ──────────────────────────────────────────────────────────────
ROUTE_PROJECT_EVOLUTION_EXPLICIT_LONG_HORIZON = "ROUTE_PROJECT_EVOLUTION_EXPLICIT_LONG_HORIZON"
ROUTE_COMMANDER_MULTI_STAGE = "ROUTE_COMMANDER_MULTI_STAGE"
ROUTE_COMMANDER_BROAD_REPOSITORY_RECON = "ROUTE_COMMANDER_BROAD_REPOSITORY_RECON"
ROUTE_COMMANDER_CROSS_SOURCE_SYNTHESIS = "ROUTE_COMMANDER_CROSS_SOURCE_SYNTHESIS"
ROUTE_INSTANT_BOUNDED_REPO_OPERATION = "ROUTE_INSTANT_BOUNDED_REPO_OPERATION"
ROUTE_CHAT_DIRECT_CONTEXT_ONLY = "ROUTE_CHAT_DIRECT_CONTEXT_ONLY"
ROUTE_CHAT_EXTERNAL_LOOKUP_ONLY = "ROUTE_CHAT_EXTERNAL_LOOKUP_ONLY"
ROUTE_CHAT_NO_EXECUTION_CAPABILITY_REQUIRED = "ROUTE_CHAT_NO_EXECUTION_CAPABILITY_REQUIRED"
ROUTE_BLOCKED_INPUT_NOT_HANDOFF_READY = "ROUTE_BLOCKED_INPUT_NOT_HANDOFF_READY"
ROUTE_UNCERTAIN_TASK_SHAPE_UNDETERMINED = "ROUTE_UNCERTAIN_TASK_SHAPE_UNDETERMINED"

ROUTE_REASONS: tuple[str, ...] = (
    ROUTE_PROJECT_EVOLUTION_EXPLICIT_LONG_HORIZON,
    ROUTE_COMMANDER_MULTI_STAGE,
    ROUTE_COMMANDER_BROAD_REPOSITORY_RECON,
    ROUTE_COMMANDER_CROSS_SOURCE_SYNTHESIS,
    ROUTE_INSTANT_BOUNDED_REPO_OPERATION,
    ROUTE_CHAT_DIRECT_CONTEXT_ONLY,
    ROUTE_CHAT_EXTERNAL_LOOKUP_ONLY,
    ROUTE_CHAT_NO_EXECUTION_CAPABILITY_REQUIRED,
    ROUTE_BLOCKED_INPUT_NOT_HANDOFF_READY,
    ROUTE_UNCERTAIN_TASK_SHAPE_UNDETERMINED,
)

#: Human-readable descriptions, so explainability never depends on an opaque
#: score.  Every recommendation is a rule, and every rule has a sentence.
ROUTE_REASON_DESCRIPTIONS: dict[str, str] = {
    ROUTE_PROJECT_EVOLUTION_EXPLICIT_LONG_HORIZON: (
        "The user explicitly asked for an ongoing project-evolution process: the "
        "declaration is literally backed by the preserved raw request, is bound to "
        "that request, comes from a trusted source, and is not something the user "
        "forbade."
    ),
    ROUTE_COMMANDER_MULTI_STAGE: (
        "The order requires coordinating several dependent stages, which needs a "
        "workflow able to orchestrate bounded operations."
    ),
    ROUTE_COMMANDER_BROAD_REPOSITORY_RECON: (
        "The repository has to be surveyed rather than opened at a place the order "
        "already identifies."
    ),
    ROUTE_COMMANDER_CROSS_SOURCE_SYNTHESIS: (
        "Evidence has to be gathered from the repository and from outside it, then "
        "reconciled into one answer."
    ),
    ROUTE_INSTANT_BOUNDED_REPO_OPERATION: (
        "The order is a bounded repository operation: a known target, a single stage, "
        "no survey required."
    ),
    ROUTE_CHAT_DIRECT_CONTEXT_ONLY: (
        "Every piece of evidence the order needs was supplied with it; no repository "
        "or external lookup is required."
    ),
    ROUTE_CHAT_EXTERNAL_LOOKUP_ONLY: (
        "The order needs current or external information and no repository work."
    ),
    ROUTE_CHAT_NO_EXECUTION_CAPABILITY_REQUIRED: (
        "The order is answered in place: no repository read, no change, no validation, "
        "no multi-stage coordination."
    ),
    ROUTE_BLOCKED_INPUT_NOT_HANDOFF_READY: (
        "INPUT did not hand this order over. WAITER.1 fails closed and does not "
        "reinterpret the request to rescue it."
    ),
    ROUTE_UNCERTAIN_TASK_SHAPE_UNDETERMINED: (
        "The handoff is valid but the task shape determines no workflow; recommending "
        "one would be a guess."
    ),
}

# ── Disqualifiers ─────────────────────────────────────────────────────────────
#: Why a workflow that might have been expected was not chosen.  The gate
#: blockers are reused verbatim so a blocked handoff reads the same here as it
#: does in INPUT.3, and the five project-evolution codes are re-exported from
#: :mod:`core.task_shape` rather than restated, so the check that emits one and
#: the router that reports it cannot drift into two words for one fact.
DISQUALIFIER_TASK_SHAPE_UNKNOWN = "task_shape_unknown"

WAITER_DISQUALIFIERS: tuple[str, ...] = (
    GATE_BLOCKERS + PROJECT_EVOLUTION_DISQUALIFIERS + (DISQUALIFIER_TASK_SHAPE_UNKNOWN,)
)

# ── Bounds ────────────────────────────────────────────────────────────────────
MAX_ROUTE_REASONS = 6
MAX_DISQUALIFIERS = 10


# ── Records ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class WaiterDecision:
    """Which execution workflow has the capabilities one valid order requires.

    The record deliberately has no room for a plan, a read set, a stage list, a
    provider, a model, or a budget.  Those are not fields WAITER.1 declines to
    fill; they are fields it does not have.
    """

    status: str
    receipt: WaiterReceipt
    recommended_workflow: str | None = None
    task_shape: TaskShape | None = None
    capability_requirements: CapabilityRequirements | None = None
    reasons: tuple[str, ...] = ()
    disqualifiers: tuple[str, ...] = ()
    schema_version: str = WAITER_DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in WAITER_STATUSES:
            raise ValueError(f"unsupported waiter status: {self.status!r}")
        if not isinstance(self.receipt, WaiterReceipt):
            raise TypeError("a waiter decision requires a WaiterReceipt")
        if len(self.reasons) > MAX_ROUTE_REASONS:
            raise ValueError("route reasons exceed the supported bound")
        if len(self.disqualifiers) > MAX_DISQUALIFIERS:
            raise ValueError("disqualifiers exceed the supported bound")
        for reason in self.reasons:
            if reason not in ROUTE_REASONS:
                raise ValueError(f"unsupported route reason: {reason!r}")
        for item in self.disqualifiers:
            if item not in WAITER_DISQUALIFIERS:
                raise ValueError(f"unsupported disqualifier: {item!r}")
        if not self.reasons:
            raise ValueError("every waiter decision must state at least one reason")

        if self.status == STATUS_ROUTED:
            if self.recommended_workflow not in WORKFLOW_TARGETS:
                raise ValueError(
                    f"unsupported workflow target: {self.recommended_workflow!r}"
                )
            if self.task_shape is None or self.capability_requirements is None:
                raise ValueError("a routed decision must carry its shape and capabilities")
            if not self.receipt.handoff_verified:
                raise ValueError("a routed decision requires a verified handoff")
        else:
            if self.recommended_workflow is not None:
                raise ValueError(
                    f"status {self.status!r} may not recommend a workflow"
                )

        if self.status == STATUS_NOT_HANDOFF_READY:
            if self.receipt.handoff_verified:
                raise ValueError("a blocked decision requires an unverified handoff")
            if self.task_shape is not None or self.capability_requirements is not None:
                raise ValueError(
                    "a blocked handoff is not described: WAITER.1 does not reinterpret "
                    "an order INPUT did not hand over"
                )
            if not self.disqualifiers:
                raise ValueError("a blocked decision must state its blockers")

        if self.status == STATUS_UNCERTAIN:
            if not self.receipt.handoff_verified:
                raise ValueError("an uncertain decision still requires a verified handoff")
            if self.task_shape is None or self.capability_requirements is None:
                raise ValueError("an uncertain decision must carry its shape and capabilities")

    # ── derived, authority-free facts ────────────────────────────────────────
    @property
    def routed(self) -> bool:
        return self.status == STATUS_ROUTED

    @property
    def handoff_verified(self) -> bool:
        return self.receipt.handoff_verified

    @property
    def human_approval_required(self) -> bool:
        """Always true.  A recommendation is a report, never a go-ahead."""
        return True

    def requires(self, capability: str) -> bool:
        """Does this order require a capability?  False when nothing was derived."""
        if self.capability_requirements is None:
            return False
        return self.capability_requirements.requires(capability)

    def reason_descriptions(self) -> tuple[str, ...]:
        return tuple(ROUTE_REASON_DESCRIPTIONS[reason] for reason in self.reasons)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "stages": list(EXECUTION_WAITER_STAGES),
            "status": self.status,
            "recommended_workflow": self.recommended_workflow,
            "workflow_targets": list(WORKFLOW_TARGETS),
            "task_shape": self.task_shape.as_dict() if self.task_shape else None,
            "capability_requirements": (
                self.capability_requirements.as_dict()
                if self.capability_requirements
                else None
            ),
            "reasons": [
                {"code": reason, "description": ROUTE_REASON_DESCRIPTIONS[reason]}
                for reason in self.reasons
            ],
            "disqualifiers": list(self.disqualifiers),
            "receipt": self.receipt.as_dict(),
            "human_approval_required": self.human_approval_required,
            "authority": waiter_authority(),
            "guardrails": waiter_guardrails(),
        }


# ── Deterministic workflow policy ─────────────────────────────────────────────
#
# The rule table, in precedence order.  There is no scoring, no weighting and
# no confidence: a capability predicate is either true or it is not.
#
#   0. the handoff gate failed                       -> not_handoff_ready
#   1. persistent_project_context_required           -> project_evolution
#   2. multi_stage_coordination_required
#      or broad_repository_reconnaissance_required
#      or cross_source_synthesis_required            -> commander
#   3. repository_read_required
#      or code_change_required                       -> instant_run
#   4. a known family needing only an answer,
#      supplied context, or external information     -> chat
#   5. anything else                                 -> uncertain
#
# Rule 2 sits above rule 3 because orchestration is a strictly larger
# capability set than a bounded operation; rule 1 sits above rule 2 because an
# ongoing process is not merely a large task.  Rule 1 can only fire on a
# declaration that is literally backed, bound to this request, trusted at
# source and un-negated, which is what keeps "broad" from ever becoming
# "ongoing" — and keeps a real quotation from becoming an authorisation.

def _commander_reasons(capabilities: CapabilityRequirements) -> tuple[str, ...]:
    reasons: list[str] = []
    if capabilities.requires(CAPABILITY_MULTI_STAGE_COORDINATION):
        reasons.append(ROUTE_COMMANDER_MULTI_STAGE)
    if capabilities.requires(CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE):
        reasons.append(ROUTE_COMMANDER_BROAD_REPOSITORY_RECON)
    if capabilities.requires(CAPABILITY_CROSS_SOURCE_SYNTHESIS):
        reasons.append(ROUTE_COMMANDER_CROSS_SOURCE_SYNTHESIS)
    return tuple(reasons)


def _chat_reasons(capabilities: CapabilityRequirements) -> tuple[str, ...]:
    reasons: list[str] = []
    if capabilities.requires(CAPABILITY_DIRECT_CONTEXT_ANALYSIS):
        reasons.append(ROUTE_CHAT_DIRECT_CONTEXT_ONLY)
    if capabilities.requires(CAPABILITY_EXTERNAL_INFORMATION):
        reasons.append(ROUTE_CHAT_EXTERNAL_LOOKUP_ONLY)
    if not reasons:
        reasons.append(ROUTE_CHAT_NO_EXECUTION_CAPABILITY_REQUIRED)
    return tuple(reasons)


def select_workflow(
    shape: TaskShape,
    capabilities: CapabilityRequirements,
) -> tuple[str | None, tuple[str, ...], tuple[str, ...]]:
    """Apply the rule table.  Returns ``(workflow, reasons, disqualifiers)``.

    Pure and total over the bounded vocabularies: the same shape and the same
    capabilities always produce the same triple, whatever the machine, the
    clock, the filesystem or the network are doing.
    """
    disqualifiers: list[str] = []

    if capabilities.requires(CAPABILITY_PERSISTENT_PROJECT_CONTEXT):
        return (
            WORKFLOW_PROJECT_EVOLUTION,
            (ROUTE_PROJECT_EVOLUTION_EXPLICIT_LONG_HORIZON,),
            (),
        )

    commander_reasons = _commander_reasons(capabilities)
    if commander_reasons:
        # Stated on every Commander route, because "this task is big" is the
        # single most tempting reason to reach for Project Evolution and the
        # single least sufficient one.
        disqualifiers.append(DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_REQUESTED)
        return WORKFLOW_COMMANDER, commander_reasons, tuple(disqualifiers)

    if capabilities.requires(CAPABILITY_REPOSITORY_READ) or capabilities.requires(
        CAPABILITY_CODE_CHANGE
    ):
        return WORKFLOW_INSTANT_RUN, (ROUTE_INSTANT_BOUNDED_REPO_OPERATION,), ()

    answerable = (
        capabilities.requires(CAPABILITY_DIRECT_CONTEXT_ANALYSIS)
        or capabilities.requires(CAPABILITY_EXTERNAL_INFORMATION)
        or capabilities.requires(CAPABILITY_CONVERSATIONAL_RESPONSE)
        or capabilities.requires(CAPABILITY_COMPARISON)
    )
    if shape.task_family != FAMILY_UNKNOWN and answerable:
        return WORKFLOW_CHAT, _chat_reasons(capabilities), ()

    disqualifiers.append(DISQUALIFIER_TASK_SHAPE_UNKNOWN)
    return None, (ROUTE_UNCERTAIN_TASK_SHAPE_UNDETERMINED,), tuple(disqualifiers)


# ── Public entry point ────────────────────────────────────────────────────────

def route_execution_workflow(
    contract: TaskContract | None,
    decision: CompletionDecision,
    *,
    project_evolution_request: ProjectEvolutionRequest | None = None,
) -> WaiterDecision:
    """Recommend the execution workflow one valid order requires, and stop.

    ``contract`` and ``decision`` are the frozen INPUT products; pass the same
    pair INPUT.3 decided over.  A handoff that INPUT did not verify produces
    :data:`STATUS_NOT_HANDOFF_READY` with no shape, no capabilities and no
    workflow — WAITER.1 fails closed rather than reinterpreting the request or
    consulting a model.

    ``project_evolution_request`` is optional, defaults to absent, and is
    verified before it is honoured: its evidence must be a literal span of the
    preserved raw request, outside any prohibition the user wrote; it must come
    from a trusted declaration source; and it must name the fingerprint of the
    request it was read from.  Without all four, Project Evolution is
    unreachable no matter how broad, architectural or long the order is, and a
    refused declaration disqualifies that one workflow rather than failing the
    request — the order still routes wherever its capabilities point.

    The result is report-only.  Nothing is planned, retrieved, selected,
    dispatched or executed, and no workflow starts because of it.
    """
    receipt = check_handoff_eligibility(contract, decision)

    if not receipt.handoff_verified or contract is None:
        return WaiterDecision(
            status=STATUS_NOT_HANDOFF_READY,
            receipt=receipt,
            reasons=(ROUTE_BLOCKED_INPUT_NOT_HANDOFF_READY,),
            disqualifiers=receipt.gate_blockers,
        )

    verification = check_project_evolution_request(contract, project_evolution_request)
    shape = derive_task_shape(contract, project_evolution_request=project_evolution_request)
    capabilities = derive_capability_requirements(shape, contract)
    workflow, reasons, disqualifiers = select_workflow(shape, capabilities)

    if project_evolution_request is not None:
        # A declaration *was* supplied, so "not explicitly requested" would be
        # the wrong sentence: it was requested and refused, and the refusal
        # states which of the four checks it failed.
        disqualifiers = tuple(
            item
            for item in disqualifiers
            if item != DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_REQUESTED
        )
        for item in verification.disqualifiers:
            if item not in disqualifiers:
                disqualifiers = disqualifiers + (item,)

    return WaiterDecision(
        status=STATUS_ROUTED if workflow is not None else STATUS_UNCERTAIN,
        receipt=receipt,
        recommended_workflow=workflow,
        task_shape=shape,
        capability_requirements=capabilities,
        reasons=reasons,
        disqualifiers=disqualifiers,
    )


def canonical_waiter_fingerprint(decision: WaiterDecision) -> dict[str, Any]:
    """Everything that must be identical for identical structured INPUT.

    Excludes nothing that could change a route: the whole point is that two
    runs over the same contract and completion decision agree, on any machine,
    at any time, with any repository state and no network.
    """
    return {
        "status": decision.status,
        "recommended_workflow": decision.recommended_workflow,
        "task_shape": decision.task_shape.as_dict() if decision.task_shape else None,
        "capability_requirements": (
            decision.capability_requirements.as_dict()
            if decision.capability_requirements
            else None
        ),
        "reasons": list(decision.reasons),
        "disqualifiers": list(decision.disqualifiers),
        "handoff_verified": decision.receipt.handoff_verified,
        "gate_blockers": list(decision.receipt.gate_blockers),
        "source_contract_fingerprint": decision.receipt.source_contract_fingerprint,
        "source_completion_fingerprint": decision.receipt.source_completion_fingerprint,
        "authority": waiter_authority(),
    }


def render_waiter_decision_json(decision: WaiterDecision) -> str:
    """Render a waiter decision as deterministic JSON."""
    return json.dumps(decision.as_dict(), indent=2, ensure_ascii=False, sort_keys=False)


__all__ = [
    "EXECUTION_WAITER_STAGES",
    "PHASE_ID",
    "ROUTE_BLOCKED_INPUT_NOT_HANDOFF_READY",
    "ROUTE_CHAT_DIRECT_CONTEXT_ONLY",
    "ROUTE_CHAT_EXTERNAL_LOOKUP_ONLY",
    "ROUTE_CHAT_NO_EXECUTION_CAPABILITY_REQUIRED",
    "ROUTE_COMMANDER_BROAD_REPOSITORY_RECON",
    "ROUTE_COMMANDER_CROSS_SOURCE_SYNTHESIS",
    "ROUTE_COMMANDER_MULTI_STAGE",
    "ROUTE_INSTANT_BOUNDED_REPO_OPERATION",
    "ROUTE_PROJECT_EVOLUTION_EXPLICIT_LONG_HORIZON",
    "ROUTE_REASONS",
    "ROUTE_REASON_DESCRIPTIONS",
    "ROUTE_UNCERTAIN_TASK_SHAPE_UNDETERMINED",
    "STATUS_NOT_HANDOFF_READY",
    "STATUS_ROUTED",
    "STATUS_UNCERTAIN",
    "WAITER_DISQUALIFIERS",
    "WAITER_STATUSES",
    "WORKFLOW_CHAT",
    "WORKFLOW_COMMANDER",
    "WORKFLOW_INSTANT_RUN",
    "WORKFLOW_PROJECT_EVOLUTION",
    "WORKFLOW_SHELL_NAMES",
    "WORKFLOW_TARGETS",
    "DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NEGATED",
    "DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NOT_LITERALLY_SUPPORTED",
    "DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_AUTHORIZED",
    "DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_REQUESTED",
    "DISQUALIFIER_PROJECT_EVOLUTION_PROVENANCE_UNVERIFIED",
    "DISQUALIFIER_TASK_SHAPE_UNKNOWN",
    "PROJECT_EVOLUTION_DISQUALIFIERS",
    "ProjectEvolutionRequest",
    "ProjectEvolutionVerification",
    "WaiterDecision",
    "canonical_waiter_fingerprint",
    "check_project_evolution_request",
    "render_waiter_decision_json",
    "route_execution_workflow",
    "select_workflow",
    "verify_project_evolution_request",
]
