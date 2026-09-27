"""ACQUIRE.1 — Bounded Evidence Acquisition Request Contract.

    EvidenceRequirementContract + WaiterDecision + TaskContract + CompletionDecision
        -> evidence-ready gate              [here]
        -> source integrity gate            [here]
        -> capability faithfulness gate     [core.evidence_requirements]
        -> acquisition policy               [core.acquisition_policy]
        -> monotonicity and closure checks  [core.acquisition_policy]
        -> AcquisitionRequestContract

WAITER.2 wrote down the ingredients.  ACQUIRE.1 writes the shopping list.
Somebody else, later, under their own authority, may go to the shop.

Five boundaries hold in every status.

**Requesting is not acquiring.**  The contract states domains, roles, source
classes, tiers and ceilings.  It opens no file, walks no directory, consults no
manifest, no index and no graph, calls no selector, issues no search, opens no
address and runs nothing.  The guardrail block says so field by field, and the
authority block stays false even when the status is ``ready``.

**Nothing is regenerated.**  The evidence contract is consumed, not re-derived.
The raw request is never reinterpreted, the workflow is copied verbatim, and a
discovered inconsistency produces ``inconsistent_input`` rather than a second
opinion about where the order should have gone.

**The translation is faithful in both directions.**  A request may refine an
evidence requirement and may not enlarge one; every active requirement must have
exactly one request that carries it, at its own tier, with a budget that permits
the work.  Not wider, and not narrower.

**Broad is not everything.**  A reconnaissance request names which classes it may
reach, carries a finite ceiling, and sits beside explicit exclusions.  The
6,087-file dogfood is not a warning here; it is a shape the schema cannot hold.

**A path is preserved, never produced.**  An identifier the user wrote survives
as a target anchor.  ACQUIRE.1 has no way to discover one, and an anchor asserts
nothing about whether the thing exists.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no language system, inspects no repository, obtains no evidence, plans
nothing, dispatches nothing, and is wired into no live path.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.acquisition_policy import (
    check_bounded_reconnaissance,
    check_deferred_source_coverage,
    check_request_monotonicity,
    check_requirement_coverage,
    derive_acquisition_policy,
    unmappable_roles,
)
from core.acquisition_request import (
    ACQUIRE_CAPABILITY_ENVELOPE_VIOLATED,
    ACQUIRE_EVIDENCE_NOT_READY,
    ACQUIRE_REQUIRED_CAPABILITY_LOST,
    ACQUIRE_REQUIRED_EVIDENCE_LOST,
    ACQUIRE_REQUIREMENT_WIDENED,
    ACQUIRE_ROLE_NOT_MAPPABLE,
    ACQUIRE_SOURCE_INTEGRITY_FAILED,
    ACQUISITION_REASONS,
    INCONSISTENT_ACQUISITION_WIDENED,
    INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED,
    INCONSISTENT_EVIDENCE_NOT_SPECIFIED,
    INCONSISTENT_REQUIRED_CAPABILITY_DROPPED,
    INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,
    INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,
    INCONSISTENT_UNMAPPABLE_ROLE,
    INCONSISTENT_WAITER_NOT_ROUTED,
    INCONSISTENT_WORKFLOW_MISMATCH,
    STATUS_INCONSISTENT_INPUT,
    STATUS_NOT_EVIDENCE_READY,
    STATUS_READY,
    AcquisitionRequestContract,
    acquisition_authority,
    acquisition_guardrails,
)
from core.evidence_requirements import (
    EvidenceRequirementContract,
    check_capability_envelope,
    check_required_capability_coverage,
)
from core.execution_waiter import (
    STATUS_ROUTED,
    WaiterDecision,
    canonical_waiter_fingerprint,
)
from core.intake_completion import CompletionDecision
from core.task_contract import TaskContract


PHASE_ID = "ACQUIRE.1"

#: The stages ACQUIRE.1 owns, in order.  Acquisition, selection, retrieval,
#: traversal and execution are deliberately absent — they are somebody else's
#: phase, behind somebody else's gate.
ACQUISITION_STAGES: tuple[str, ...] = (
    "evidence_ready_gate",
    "source_integrity_gate",
    "capability_faithfulness_gate",
    "acquisition_policy_derivation",
    "request_monotonicity_check",
    "requirement_coverage_check",
    "bounded_reconnaissance_check",
)


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _ordered_reasons(codes: list[str]) -> tuple[str, ...]:
    """Distinct reason codes in the canonical vocabulary order."""
    present = set(codes)
    return tuple(code for code in ACQUISITION_REASONS if code in present)


def _refused(
    status: str,
    reason: str,
    inconsistencies: tuple[str, ...],
) -> AcquisitionRequestContract:
    """A contract that requests nothing, and says exactly why."""
    return AcquisitionRequestContract(
        status=status,
        reasons=(reason,),
        inconsistencies=inconsistencies,
    )


def derive_acquisition_requests(
    evidence: EvidenceRequirementContract,
    decision: WaiterDecision,
    contract: TaskContract | None,
    completion: CompletionDecision,
) -> AcquisitionRequestContract:
    """Write the bounded requests one evidence contract licenses, and obtain none.

    ``evidence`` must be a specified :class:`EvidenceRequirementContract`;
    ``decision``, ``contract`` and ``completion`` must be the very records it was
    specified over, which is checked by fingerprint rather than trusted.  Anything
    else fails closed with no requests at all: ACQUIRE.1 does not re-route, does
    not regenerate the evidence contract, does not reinterpret the raw prompt,
    and does not describe an order nobody specified evidence for.

    The result is report-only.  No file is opened, no directory is walked, no
    manifest, index or graph is consulted, no selector is called, no search is
    issued and no workflow starts because of it.
    """
    if not isinstance(evidence, EvidenceRequirementContract):
        raise TypeError("derive_acquisition_requests requires an EvidenceRequirementContract")
    if not isinstance(decision, WaiterDecision):
        raise TypeError("derive_acquisition_requests requires a WaiterDecision")
    if contract is not None and not isinstance(contract, TaskContract):
        raise TypeError("derive_acquisition_requests requires a TaskContract or None")
    if not isinstance(completion, CompletionDecision):
        raise TypeError("derive_acquisition_requests requires a CompletionDecision")

    # ── the evidence-ready gate ──────────────────────────────────────────────
    if not evidence.specified or contract is None:
        return _refused(
            STATUS_NOT_EVIDENCE_READY,
            ACQUIRE_EVIDENCE_NOT_READY,
            (INCONSISTENT_EVIDENCE_NOT_SPECIFIED,),
        )

    if (
        decision.status != STATUS_ROUTED
        or decision.recommended_workflow is None
        or decision.capability_requirements is None
    ):
        return _refused(
            STATUS_INCONSISTENT_INPUT,
            ACQUIRE_SOURCE_INTEGRITY_FAILED,
            (INCONSISTENT_WAITER_NOT_ROUTED,),
        )

    # ── workflow immutability ────────────────────────────────────────────────
    # Copied for traceability and compared, never chosen.  There is no branch
    # below that could produce a different one, so "reroute" is not a failure
    # mode this phase has: a mismatch is a broken input, not a decision to make.
    if evidence.workflow != decision.recommended_workflow:
        return _refused(
            STATUS_INCONSISTENT_INPUT,
            ACQUIRE_SOURCE_INTEGRITY_FAILED,
            (INCONSISTENT_WORKFLOW_MISMATCH,),
        )

    # ── the source integrity gate ────────────────────────────────────────────
    # Three fingerprints, re-derived rather than believed: the INPUT records, the
    # routing decision, and the evidence contract's own claim about which of each
    # it was specified over.  Tampering with any upstream record invalidates the
    # request set instead of quietly producing requests for a different order.
    contract_fingerprint = _fingerprint(contract.as_dict())
    completion_fingerprint = _fingerprint(completion.as_dict())
    decision_fingerprint = _fingerprint(canonical_waiter_fingerprint(decision))
    if (
        contract_fingerprint != evidence.source_contract_fingerprint
        or completion_fingerprint != evidence.source_completion_fingerprint
        or decision_fingerprint != evidence.source_decision_fingerprint
        or contract_fingerprint != decision.receipt.source_contract_fingerprint
        or completion_fingerprint != decision.receipt.source_completion_fingerprint
    ):
        return _refused(
            STATUS_INCONSISTENT_INPUT,
            ACQUIRE_SOURCE_INTEGRITY_FAILED,
            (INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,),
        )

    # ── the capability faithfulness gate ─────────────────────────────────────
    # Both directions, re-checked here rather than assumed from the fact that
    # WAITER.2 said "specified".  A contract that reaches outside the envelope,
    # or one already narrower than the order, is not a thing to write requests
    # over.
    if check_capability_envelope(evidence.requirements, decision.capability_requirements):
        return _refused(
            STATUS_INCONSISTENT_INPUT,
            ACQUIRE_CAPABILITY_ENVELOPE_VIOLATED,
            (INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED,),
        )
    if check_required_capability_coverage(
        evidence.requirements, decision.capability_requirements
    ):
        return _refused(
            STATUS_INCONSISTENT_INPUT,
            ACQUIRE_REQUIRED_CAPABILITY_LOST,
            (INCONSISTENT_REQUIRED_CAPABILITY_DROPPED,),
        )

    if unmappable_roles(evidence):
        return _refused(
            STATUS_INCONSISTENT_INPUT,
            ACQUIRE_ROLE_NOT_MAPPABLE,
            (INCONSISTENT_UNMAPPABLE_ROLE,),
        )

    # ── the requests themselves ──────────────────────────────────────────────
    policy = derive_acquisition_policy(evidence, contract)

    if check_request_monotonicity(policy, evidence) or check_bounded_reconnaissance(policy):
        return _refused(
            STATUS_INCONSISTENT_INPUT,
            ACQUIRE_REQUIREMENT_WIDENED,
            (INCONSISTENT_ACQUISITION_WIDENED,),
        )
    if check_requirement_coverage(policy, evidence) or check_deferred_source_coverage(
        policy, evidence
    ):
        return _refused(
            STATUS_INCONSISTENT_INPUT,
            ACQUIRE_REQUIRED_EVIDENCE_LOST,
            (INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,),
        )

    collected: list[str] = []
    for request in policy.requests + policy.deferred_requests:
        collected.extend(request.reasons)
    for exclusion in policy.exclusions:
        collected.extend(exclusion.reasons)

    return AcquisitionRequestContract(
        status=STATUS_READY,
        workflow=evidence.workflow,
        evidence_scope=evidence.scope,
        requests=policy.requests,
        deferred_requests=policy.deferred_requests,
        exclusions=policy.exclusions,
        reasons=_ordered_reasons(collected),
        source_evidence_fingerprint=_fingerprint(_evidence_identity(evidence)),
        source_decision_fingerprint=decision_fingerprint,
        source_contract_fingerprint=contract_fingerprint,
        source_completion_fingerprint=completion_fingerprint,
    )


def _evidence_identity(evidence: EvidenceRequirementContract) -> dict[str, Any]:
    """Everything about the evidence contract that a request set depends on."""
    return {
        "status": evidence.status,
        "workflow": evidence.workflow,
        "scope": evidence.scope,
        "requirements": [item.as_dict() for item in evidence.requirements],
        "deferred_sources": [item.as_dict() for item in evidence.deferred_sources],
        "verification_requirements": list(evidence.verification_requirements),
        "source_contract_fingerprint": evidence.source_contract_fingerprint,
        "source_completion_fingerprint": evidence.source_completion_fingerprint,
        "source_decision_fingerprint": evidence.source_decision_fingerprint,
    }


def canonical_acquisition_shape(
    contract: AcquisitionRequestContract,
) -> dict[str, Any]:
    """Everything the request contract says, with no reference to its source.

    Two orders that mean the same thing in different languages produce the same
    shape, because none of it is derived from words.
    """
    if not isinstance(contract, AcquisitionRequestContract):
        raise TypeError("canonical_acquisition_shape requires an AcquisitionRequestContract")
    return {
        "status": contract.status,
        "workflow": contract.workflow,
        "evidence_scope": contract.evidence_scope,
        "requests": [item.as_dict() for item in contract.requests],
        "deferred_requests": [item.as_dict() for item in contract.deferred_requests],
        "exclusions": [item.as_dict() for item in contract.exclusions],
        "budget_summary": contract.budget_summary(),
        "reasons": list(contract.reasons),
        "inconsistencies": list(contract.inconsistencies),
        "authority": acquisition_authority(),
        "guardrails": acquisition_guardrails(),
    }


def canonical_acquisition_fingerprint(
    contract: AcquisitionRequestContract,
) -> dict[str, Any]:
    """The shape, plus the exact upstream records it was written over."""
    payload = canonical_acquisition_shape(contract)
    payload["source_evidence_fingerprint"] = contract.source_evidence_fingerprint
    payload["source_decision_fingerprint"] = contract.source_decision_fingerprint
    payload["source_contract_fingerprint"] = contract.source_contract_fingerprint
    payload["source_completion_fingerprint"] = contract.source_completion_fingerprint
    return payload


def render_acquisition_contract_json(contract: AcquisitionRequestContract) -> str:
    """Render an acquisition request contract as deterministic JSON."""
    if not isinstance(contract, AcquisitionRequestContract):
        raise TypeError(
            "render_acquisition_contract_json requires an AcquisitionRequestContract"
        )
    return json.dumps(contract.as_dict(), indent=2, ensure_ascii=False, sort_keys=False)


__all__ = [
    "ACQUISITION_STAGES",
    "PHASE_ID",
    "canonical_acquisition_fingerprint",
    "canonical_acquisition_shape",
    "derive_acquisition_requests",
    "render_acquisition_contract_json",
]
