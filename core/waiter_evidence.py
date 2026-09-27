"""WAITER.2 — Deterministic Evidence Requirement Contract.

    WaiterDecision (routed) + TaskContract + CompletionDecision
        -> source integrity gate            [here]
        -> evidence policy                  [core.evidence_policy]
        -> capability envelope check        [core.evidence_requirements]
        -> required capability coverage     [core.evidence_requirements]
        -> EvidenceRequirementContract

WAITER.1 chose the kitchen.  WAITER.2 writes down what that kitchen should ask
for.  Somebody else, later, under their own authority, may go and get it.

Four boundaries hold in every status.

**Specifying is not acquiring.**  The contract states domains, roles and tiers.
It contains no file, no path, no query, no read set, no retrieval result and no
manifest.  Nothing was read, searched, indexed, selected or retrieved to produce
it, and the guardrail block says so field by field.

**Routing already happened.**  The workflow is copied verbatim from the routed
decision.  The policy layer that derives the requirements is never told what the
workflow is, so there is no argument by which an evidence need could promote
chat to commander.  A discovered inconsistency produces ``inconsistent_input``,
never a different route.

**No downstream surprise, in either direction.**  Every domain names the upstream
capability that licenses it.  A requirement WAITER.1's envelope does not cover
fails the whole contract closed rather than quietly widening the scope of the
work — and a required capability that no active requirement discharges fails it
closed just as hard, because an evidence set narrower than the order is a wrong
answer nobody is warned about.

**Fail closed on anything that does not hang together.**  A decision that is not
routed, a contract that does not fingerprint to the one the decision was made
over, a completion record from another run: all produce a contract with no
requirements at all, because guessing what an unrouted workflow would need is
exactly the kind of helpfulness this layer exists to refuse.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no language system, inspects no repository, obtains no evidence, plans
nothing, dispatches nothing, and is wired into no live path.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.evidence_policy import derive_evidence_policy
from core.evidence_requirements import (
    EVIDENCE_CAPABILITY_ENVELOPE_VIOLATED,
    EVIDENCE_NOT_SPECIFIED_UNROUTED,
    EVIDENCE_REASONS,
    EVIDENCE_REQUIRED_CAPABILITY_LOST,
    EVIDENCE_SOURCE_INTEGRITY_FAILED,
    INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED,
    INCONSISTENT_REQUIRED_CAPABILITY_DROPPED,
    INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,
    INCONSISTENT_UNSUPPORTED_WORKFLOW,
    INCONSISTENT_WAITER_NOT_ROUTED,
    STATUS_INCONSISTENT_INPUT,
    STATUS_NOT_ROUTED,
    STATUS_SPECIFIED,
    EvidenceRequirementContract,
    check_capability_envelope,
    check_required_capability_coverage,
    evidence_authority,
    evidence_guardrails,
)
from core.execution_waiter import (
    STATUS_ROUTED,
    WORKFLOW_TARGETS,
    WaiterDecision,
    canonical_waiter_fingerprint,
)
from core.intake_completion import CompletionDecision
from core.task_contract import TaskContract


PHASE_ID = "WAITER.2"

#: The stages WAITER.2 owns, in order.  Acquisition, selection, retrieval and
#: execution are deliberately absent — they are somebody else's phase.
EVIDENCE_WAITER_STAGES: tuple[str, ...] = (
    "routed_decision_gate",
    "source_integrity_gate",
    "evidence_policy_derivation",
    "capability_envelope_check",
    "required_capability_coverage_check",
)


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _ordered_reasons(codes: list[str]) -> tuple[str, ...]:
    """Distinct reason codes in the canonical vocabulary order."""
    present = set(codes)
    return tuple(code for code in EVIDENCE_REASONS if code in present)


def _refused(
    status: str,
    reason: str,
    inconsistencies: tuple[str, ...],
) -> EvidenceRequirementContract:
    """A contract that describes nothing, and says exactly why."""
    return EvidenceRequirementContract(
        status=status,
        reasons=(reason,),
        inconsistencies=inconsistencies,
    )


def derive_evidence_requirements(
    decision: WaiterDecision,
    contract: TaskContract | None,
    completion: CompletionDecision,
) -> EvidenceRequirementContract:
    """State what the routed workflow will need, and obtain none of it.

    ``decision`` must be a routed :class:`WaiterDecision`; ``contract`` and
    ``completion`` must be the very records that decision was made over, which
    is checked by fingerprint rather than trusted.  Anything else fails closed
    with no requirements: WAITER.2 does not re-route, does not reinterpret the
    raw prompt, and does not describe an order nobody routed.

    The result is report-only.  No file is opened, no directory is walked, no
    index or graph is consulted, no search is issued and no workflow starts
    because of it.
    """
    if not isinstance(decision, WaiterDecision):
        raise TypeError("derive_evidence_requirements requires a WaiterDecision")
    if contract is not None and not isinstance(contract, TaskContract):
        raise TypeError("derive_evidence_requirements requires a TaskContract or None")
    if not isinstance(completion, CompletionDecision):
        raise TypeError("derive_evidence_requirements requires a CompletionDecision")

    # ── the routed-decision gate ─────────────────────────────────────────────
    if (
        decision.status != STATUS_ROUTED
        or decision.recommended_workflow is None
        or decision.task_shape is None
        or decision.capability_requirements is None
        or contract is None
    ):
        return _refused(
            STATUS_NOT_ROUTED,
            EVIDENCE_NOT_SPECIFIED_UNROUTED,
            (INCONSISTENT_WAITER_NOT_ROUTED,),
        )

    if decision.recommended_workflow not in WORKFLOW_TARGETS:
        return _refused(
            STATUS_INCONSISTENT_INPUT,
            EVIDENCE_SOURCE_INTEGRITY_FAILED,
            (INCONSISTENT_UNSUPPORTED_WORKFLOW,),
        )

    # ── the source integrity gate ────────────────────────────────────────────
    # The receipt already fingerprinted what INPUT handed over.  Re-deriving the
    # fingerprints here is what makes "same order" a checkable claim rather than
    # an assumption about how the caller assembled its arguments.
    contract_fingerprint = _fingerprint(contract.as_dict())
    completion_fingerprint = _fingerprint(completion.as_dict())
    if (
        contract_fingerprint != decision.receipt.source_contract_fingerprint
        or completion_fingerprint != decision.receipt.source_completion_fingerprint
    ):
        return _refused(
            STATUS_INCONSISTENT_INPUT,
            EVIDENCE_SOURCE_INTEGRITY_FAILED,
            (INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,),
        )

    # ── the policy, derived without knowing the workflow ─────────────────────
    policy = derive_evidence_policy(
        decision.task_shape,
        decision.capability_requirements,
        contract,
    )

    violations = check_capability_envelope(
        policy.requirements, decision.capability_requirements
    )
    if violations:
        return _refused(
            STATUS_INCONSISTENT_INPUT,
            EVIDENCE_CAPABILITY_ENVELOPE_VIOLATED,
            (INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED,),
        )

    # ── the closure check, in the other direction ────────────────────────────
    # Refusing to widen is only half of faithfulness.  A policy that quietly
    # dropped a required evidence capability would answer a smaller question
    # than the one that was asked, and nothing downstream would ever know a
    # smaller question had been substituted.
    dropped = check_required_capability_coverage(
        policy.requirements, decision.capability_requirements
    )
    if dropped:
        return _refused(
            STATUS_INCONSISTENT_INPUT,
            EVIDENCE_REQUIRED_CAPABILITY_LOST,
            (INCONSISTENT_REQUIRED_CAPABILITY_DROPPED,),
        )

    collected: list[str] = []
    for requirement in policy.requirements:
        collected.extend(requirement.reasons)
    for source in policy.deferred_sources:
        collected.extend(source.reasons)

    return EvidenceRequirementContract(
        status=STATUS_SPECIFIED,
        # Copied, never chosen.  WAITER.2 has no rule that produces a workflow.
        workflow=decision.recommended_workflow,
        scope=policy.scope,
        requirements=policy.requirements,
        deferred_sources=policy.deferred_sources,
        verification_requirements=policy.verification_requirements,
        reasons=_ordered_reasons(collected),
        source_contract_fingerprint=contract_fingerprint,
        source_completion_fingerprint=completion_fingerprint,
        source_decision_fingerprint=_fingerprint(canonical_waiter_fingerprint(decision)),
    )


def canonical_evidence_shape(contract: EvidenceRequirementContract) -> dict[str, Any]:
    """Everything the requirement contract says, with no reference to its source.

    Two orders that mean the same thing in different languages produce the same
    shape, because none of it is derived from words.
    """
    if not isinstance(contract, EvidenceRequirementContract):
        raise TypeError("canonical_evidence_shape requires an EvidenceRequirementContract")
    return {
        "status": contract.status,
        "workflow": contract.workflow,
        "scope": contract.scope,
        "requirements": [item.as_dict() for item in contract.requirements],
        "deferred_sources": [item.as_dict() for item in contract.deferred_sources],
        "verification_requirements": list(contract.verification_requirements),
        "reasons": list(contract.reasons),
        "inconsistencies": list(contract.inconsistencies),
        "authority": evidence_authority(),
        "guardrails": evidence_guardrails(),
    }


def canonical_evidence_fingerprint(
    contract: EvidenceRequirementContract,
) -> dict[str, Any]:
    """The shape, plus the exact upstream records it was specified over."""
    payload = canonical_evidence_shape(contract)
    payload["source_contract_fingerprint"] = contract.source_contract_fingerprint
    payload["source_completion_fingerprint"] = contract.source_completion_fingerprint
    payload["source_decision_fingerprint"] = contract.source_decision_fingerprint
    return payload


def render_evidence_contract_json(contract: EvidenceRequirementContract) -> str:
    """Render an evidence requirement contract as deterministic JSON."""
    if not isinstance(contract, EvidenceRequirementContract):
        raise TypeError(
            "render_evidence_contract_json requires an EvidenceRequirementContract"
        )
    return json.dumps(contract.as_dict(), indent=2, ensure_ascii=False, sort_keys=False)


__all__ = [
    "EVIDENCE_WAITER_STAGES",
    "PHASE_ID",
    "canonical_evidence_fingerprint",
    "canonical_evidence_shape",
    "derive_evidence_requirements",
    "render_evidence_contract_json",
]
