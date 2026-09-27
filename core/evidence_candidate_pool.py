"""ACQUIRE.2 — Bounded Candidate Eligibility & Selector Bridge.

    AcquisitionRequestContract + EvidenceRequirementContract
        + CandidateInventory
        -> acquisition-ready gate           [here]
        -> source integrity gate            [here]
        -> inventory gate                   [here]
        -> eligibility policy               [core.eligibility_policy]
        -> monotonicity check               [core.eligibility_policy]
        -> required-role satisfaction       [here]
        -> CandidateEligibilityReceipt

ACQUIRE.1 wrote the shopping list in classes and ceilings.  ACQUIRE.2 walks up
to a shelf somebody else has already catalogued and says which items on it are
of the kinds the list asks for.  It puts nothing in the basket.

Five boundaries hold in every status.

**A candidate is not evidence.**  ``content_read`` is false, ``evidence_status``
is ``not_acquired``, and the role a candidate is eligible for is an expectation
about a source nobody has opened.  There is no value in this vocabulary that
says otherwise, so no code path can produce one.

**Membership is the only door.**  A concrete identifier exists because the
authorized snapshot says it does.  ACQUIRE.2 walks nothing, opens nothing, and
invents no path — not even one the user typed, which is reported unmatched
rather than conjured into existence.

**Exclusions and deferrals survive.**  A class ACQUIRE.1 excluded cannot enter
the active pool, and :func:`core.eligibility_policy.validate_selector_output`
exists so a selector cannot smuggle one back in either.

**The ceiling narrows, never widens.**  The pool is bounded by the number
ACQUIRE.1 wrote down, ordered deterministically, and the source budget is
carried forward untouched because nothing was acquired to spend it on.

**Failing to find something is a result, not an error to paper over.**  A
required role with no confidently eligible candidate produces
``insufficient_candidates`` — never a widened classification that makes the
number come out right.

The module is stdlib-only and pure.  It reads no files, walks no directory,
contacts no service, calls no language system, executes no selector, obtains no
evidence, and is wired into no live path.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.acquisition_request import AcquisitionRequestContract
from core.candidate_eligibility import (
    ELIGIBILITY_ACQUISITION_NOT_READY,
    ELIGIBILITY_CANDIDATES_BOUNDED,
    ELIGIBILITY_DEFERRED_KEPT_SEPARATE,
    ELIGIBILITY_DIRECT_CONTEXT_REFERENCED,
    ELIGIBILITY_ENVELOPE_WIDENED,
    ELIGIBILITY_EXCLUSIONS_ENFORCED,
    ELIGIBILITY_EXTERNAL_ENVELOPE_ONLY,
    ELIGIBILITY_INVENTORY_IDENTITY_MISMATCH,
    ELIGIBILITY_INVENTORY_REQUIRED,
    ELIGIBILITY_REASONS,
    ELIGIBILITY_REQUIRED_ROLE_UNSATISFIED,
    ELIGIBILITY_SOURCE_INTEGRITY_FAILED,
    ELIGIBILITY_TARGET_ANCHOR_MATCHED,
    ELIGIBILITY_TARGET_ANCHOR_UNMATCHED,
    INCONSISTENT_ACQUISITION_NOT_READY,
    INCONSISTENT_ELIGIBILITY_WIDENED,
    INCONSISTENT_INVENTORY_ABSENT,
    INCONSISTENT_INVENTORY_FINGERPRINT_MISMATCH,
    INCONSISTENT_INVENTORY_IDENTITY_MISMATCH,
    INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,
    STATUS_INCONSISTENT_INPUT,
    STATUS_INSUFFICIENT_CANDIDATES,
    STATUS_INVENTORY_REQUIRED,
    STATUS_NOT_ACQUISITION_READY,
    STATUS_READY,
    CandidateEligibilityReceipt,
    eligibility_authority,
    eligibility_guardrails,
)
from core.candidate_inventory import CandidateInventory
from core.eligibility_policy import (
    check_eligibility_monotonicity,
    derive_eligibility,
    requires_inventory,
)
from core.evidence_requirements import EvidenceRequirementContract


PHASE_ID = "ACQUIRE.2"

#: The stages ACQUIRE.2 owns, in order.  Traversal, content reading, ranking,
#: selection and acquisition are deliberately absent — they belong to phases
#: with authority ACQUIRE.2 does not hold.
ELIGIBILITY_STAGES: tuple[str, ...] = (
    "acquisition_ready_gate",
    "source_integrity_gate",
    "inventory_gate",
    "eligibility_policy_derivation",
    "eligibility_monotonicity_check",
    "required_role_satisfaction_check",
)


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _ordered_reasons(codes: list[str]) -> tuple[str, ...]:
    """Distinct reason codes in the canonical vocabulary order."""
    present = set(codes)
    return tuple(code for code in ELIGIBILITY_REASONS if code in present)


def _refused(
    status: str,
    reason: str,
    inconsistencies: tuple[str, ...],
) -> CandidateEligibilityReceipt:
    """A receipt that describes no pool, and says exactly why."""
    return CandidateEligibilityReceipt(
        status=status,
        reasons=(reason,),
        inconsistencies=inconsistencies,
    )


def acquisition_contract_identity(contract: AcquisitionRequestContract) -> dict[str, Any]:
    """Everything about the request contract a candidate pool depends on."""
    if not isinstance(contract, AcquisitionRequestContract):
        raise TypeError(
            "acquisition_contract_identity requires an AcquisitionRequestContract"
        )
    return {
        "status": contract.status,
        "workflow": contract.workflow,
        "evidence_scope": contract.evidence_scope,
        "requests": [item.as_dict() for item in contract.requests],
        "deferred_requests": [item.as_dict() for item in contract.deferred_requests],
        "exclusions": [item.as_dict() for item in contract.exclusions],
        "source_evidence_fingerprint": contract.source_evidence_fingerprint,
        "source_decision_fingerprint": contract.source_decision_fingerprint,
        "source_contract_fingerprint": contract.source_contract_fingerprint,
        "source_completion_fingerprint": contract.source_completion_fingerprint,
    }


def _evidence_identity(evidence: EvidenceRequirementContract) -> dict[str, Any]:
    """The same shape ACQUIRE.1 fingerprinted, re-derived rather than trusted."""
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


def derive_candidate_eligibility(
    acquisition: AcquisitionRequestContract,
    evidence: EvidenceRequirementContract,
    inventory: CandidateInventory | None = None,
    *,
    repository_identity: str | None = None,
) -> CandidateEligibilityReceipt:
    """Say which candidates are eligible, and acquire none of them.

    ``acquisition`` must be a ready :class:`AcquisitionRequestContract` and
    ``evidence`` the very contract it was written over, which is checked by
    fingerprint rather than trusted.  ``inventory`` is required for any request
    that reaches the repository, and its absence fails closed: ACQUIRE.2 does
    not go and build one.

    ``repository_identity``, when supplied, is compared against the inventory's
    own.  A snapshot of a different repository is refused rather than used.

    The result is report-only.  No directory is walked, no file is opened, no
    manifest, index or graph is consulted, no selector is executed, no search is
    issued, and no candidate becomes evidence because of it.
    """
    if not isinstance(acquisition, AcquisitionRequestContract):
        raise TypeError(
            "derive_candidate_eligibility requires an AcquisitionRequestContract"
        )
    if not isinstance(evidence, EvidenceRequirementContract):
        raise TypeError(
            "derive_candidate_eligibility requires an EvidenceRequirementContract"
        )
    if inventory is not None and not isinstance(inventory, CandidateInventory):
        raise TypeError("derive_candidate_eligibility requires a CandidateInventory or None")

    # ── the acquisition-ready gate ───────────────────────────────────────────
    if not acquisition.ready:
        return _refused(
            STATUS_NOT_ACQUISITION_READY,
            ELIGIBILITY_ACQUISITION_NOT_READY,
            (INCONSISTENT_ACQUISITION_NOT_READY,),
        )

    # ── the source integrity gate ────────────────────────────────────────────
    # The evidence contract is re-fingerprinted here rather than believed, so a
    # request contract paired with a different upstream record cannot quietly
    # produce candidates for the wrong order.
    evidence_fingerprint = _fingerprint(_evidence_identity(evidence))
    if (
        not evidence.specified
        or evidence_fingerprint != acquisition.source_evidence_fingerprint
        or evidence.workflow != acquisition.workflow
        or evidence.scope != acquisition.evidence_scope
    ):
        return _refused(
            STATUS_INCONSISTENT_INPUT,
            ELIGIBILITY_SOURCE_INTEGRITY_FAILED,
            (INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,),
        )

    # ── the inventory gate ───────────────────────────────────────────────────
    needs_inventory = requires_inventory(acquisition)
    if needs_inventory and inventory is None:
        return _refused(
            STATUS_INVENTORY_REQUIRED,
            ELIGIBILITY_INVENTORY_REQUIRED,
            (INCONSISTENT_INVENTORY_ABSENT,),
        )
    if inventory is not None:
        if (
            repository_identity is not None
            and repository_identity != inventory.repository_identity
        ):
            return _refused(
                STATUS_INCONSISTENT_INPUT,
                ELIGIBILITY_INVENTORY_IDENTITY_MISMATCH,
                (INCONSISTENT_INVENTORY_IDENTITY_MISMATCH,),
            )
        if not inventory.declared_fingerprint_matches():
            return _refused(
                STATUS_INCONSISTENT_INPUT,
                ELIGIBILITY_INVENTORY_IDENTITY_MISMATCH,
                (INCONSISTENT_INVENTORY_FINGERPRINT_MISMATCH,),
            )

    # ── the pools themselves ─────────────────────────────────────────────────
    outcome = derive_eligibility(acquisition, inventory if needs_inventory else None)

    if check_eligibility_monotonicity(outcome, acquisition):
        return _refused(
            STATUS_INCONSISTENT_INPUT,
            ELIGIBILITY_ENVELOPE_WIDENED,
            (INCONSISTENT_ELIGIBILITY_WIDENED,),
        )

    collected = [ELIGIBILITY_CANDIDATES_BOUNDED]
    if acquisition.exclusions:
        collected.append(ELIGIBILITY_EXCLUSIONS_ENFORCED)
    if outcome.deferred_candidates or acquisition.deferred_requests:
        collected.append(ELIGIBILITY_DEFERRED_KEPT_SEPARATE)
    if any(
        candidate.domain == "direct_context" for candidate in outcome.all_candidates()
    ):
        collected.append(ELIGIBILITY_DIRECT_CONTEXT_REFERENCED)
    if outcome.external_envelopes:
        collected.append(ELIGIBILITY_EXTERNAL_ENVELOPE_ONLY)
    if any(candidate.target_anchor_match for candidate in outcome.all_candidates()):
        collected.append(ELIGIBILITY_TARGET_ANCHOR_MATCHED)
    if outcome.unmatched_target_anchors:
        collected.append(ELIGIBILITY_TARGET_ANCHOR_UNMATCHED)

    # ── required-role satisfaction ───────────────────────────────────────────
    # Reported, never repaired.  Widening a classification until the roles come
    # out satisfied is exactly the helpfulness that turns "we could not find the
    # architecture" into "here are six thousand files".
    status = STATUS_READY
    if outcome.unsatisfied_required_roles:
        status = STATUS_INSUFFICIENT_CANDIDATES
        collected.append(ELIGIBILITY_REQUIRED_ROLE_UNSATISFIED)

    return CandidateEligibilityReceipt(
        status=status,
        workflow=acquisition.workflow,
        evidence_scope=acquisition.evidence_scope,
        active_candidates=outcome.active_candidates,
        secondary_candidates=outcome.secondary_candidates,
        deferred_candidates=outcome.deferred_candidates,
        exclusion_summary=outcome.exclusion_summary,
        selector_envelopes=outcome.selector_envelopes,
        external_envelopes=outcome.external_envelopes,
        unmatched_target_anchors=outcome.unmatched_target_anchors,
        unsatisfied_required_roles=outcome.unsatisfied_required_roles,
        candidate_limit=outcome.candidate_limit,
        source_limit_reserved=outcome.source_limit_reserved,
        byte_limit=outcome.byte_limit,
        byte_eligible_total=outcome.byte_eligible_total,
        reasons=_ordered_reasons(collected),
        acquisition_request_fingerprint=_fingerprint(
            acquisition_contract_identity(acquisition)
        ),
        evidence_contract_fingerprint=evidence_fingerprint,
        inventory_fingerprint=(
            inventory.fingerprint() if inventory is not None and needs_inventory else None
        ),
        repository_identity=(
            inventory.repository_identity
            if inventory is not None and needs_inventory
            else None
        ),
    )


def canonical_eligibility_shape(
    receipt: CandidateEligibilityReceipt,
) -> dict[str, Any]:
    """Everything the receipt says, with no reference to its source.

    Two orders that mean the same thing in different languages, over the same
    inventory, produce the same shape, because none of it is derived from words.
    """
    if not isinstance(receipt, CandidateEligibilityReceipt):
        raise TypeError("canonical_eligibility_shape requires a CandidateEligibilityReceipt")
    return {
        "status": receipt.status,
        "workflow": receipt.workflow,
        "evidence_scope": receipt.evidence_scope,
        "active_candidates": [item.as_dict() for item in receipt.active_candidates],
        "secondary_candidates": [item.as_dict() for item in receipt.secondary_candidates],
        "deferred_candidates": [item.as_dict() for item in receipt.deferred_candidates],
        "exclusion_summary": [item.as_dict() for item in receipt.exclusion_summary],
        "selector_envelopes": [item.as_dict() for item in receipt.selector_envelopes],
        "external_envelopes": [item.as_dict() for item in receipt.external_envelopes],
        "unmatched_target_anchors": list(receipt.unmatched_target_anchors),
        "unsatisfied_required_roles": list(receipt.unsatisfied_required_roles),
        "budget": receipt.budget_summary(),
        "reasons": list(receipt.reasons),
        "inconsistencies": list(receipt.inconsistencies),
        "authority": eligibility_authority(),
        "guardrails": eligibility_guardrails(),
    }


def canonical_eligibility_fingerprint(
    receipt: CandidateEligibilityReceipt,
) -> dict[str, Any]:
    """The shape, plus the exact upstream records it was derived over."""
    payload = canonical_eligibility_shape(receipt)
    payload["acquisition_request_fingerprint"] = receipt.acquisition_request_fingerprint
    payload["evidence_contract_fingerprint"] = receipt.evidence_contract_fingerprint
    payload["inventory_fingerprint"] = receipt.inventory_fingerprint
    payload["repository_identity"] = receipt.repository_identity
    return payload


def render_eligibility_receipt_json(receipt: CandidateEligibilityReceipt) -> str:
    """Render a candidate eligibility receipt as deterministic JSON."""
    if not isinstance(receipt, CandidateEligibilityReceipt):
        raise TypeError(
            "render_eligibility_receipt_json requires a CandidateEligibilityReceipt"
        )
    return json.dumps(receipt.as_dict(), indent=2, ensure_ascii=False, sort_keys=False)


__all__ = [
    "ELIGIBILITY_STAGES",
    "PHASE_ID",
    "acquisition_contract_identity",
    "canonical_eligibility_fingerprint",
    "canonical_eligibility_shape",
    "derive_candidate_eligibility",
    "render_eligibility_receipt_json",
]
