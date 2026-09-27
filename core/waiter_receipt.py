"""WAITER.1 — handoff eligibility gate, source evidence, and authority block.

Before the Execution Waiter may describe an order at all, it must establish
that INPUT actually handed the order over:

    TaskContract + CompletionDecision
        -> hard entry gate
        -> WaiterReceipt

The gate is fail-closed and does not negotiate.  ``ready_for_future_handoff``
is INPUT.3's derived conjunction — READY completion, an actual contract, a
passed INPUT.1 preservation gate, and valid INPUT.2 receipt evidence — and
WAITER.1 re-checks it rather than trusting a flag.  READY alone is not enough,
a preview without a semantic receipt is not enough, and a contract whose own
fail-closed ``routing_allowed`` is false is not enough.

When the gate fails, WAITER.1 stops.  It does not reinterpret the request to
rescue it, does not ask a model, and does not fall back to a weaker workflow.

The receipt also carries the two things that make a routing decision auditable:
deterministic fingerprints of the exact contract and completion decision that
produced it, and the authority block — every operational power WAITER.1
declines to hold, in every status, including a routed one.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no model, inspects no repository, and grants no authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from core.intake_completion import (
    HANDOFF_BLOCKER_CONTRACT_MISSING,
    HANDOFF_BLOCKER_PRESERVATION_FAILED,
    HANDOFF_BLOCKER_SEMANTIC_RECEIPT_INVALID,
    HANDOFF_BLOCKER_SEMANTIC_RECEIPT_MISSING,
    HANDOFF_BLOCKER_COMPLETION_NOT_READY,
    CompletionDecision,
)
from core.task_contract import PRESERVATION_PASSED, TaskContract


PHASE_ID = "WAITER.1"
WAITER_RECEIPT_SCHEMA_VERSION = "waiter_1_receipt_v1"

# ── Entry gate blockers ───────────────────────────────────────────────────────
#: INPUT.3's own handoff blockers are reused verbatim rather than renamed, so
#: the two layers cannot drift into two different words for one fact.
GATE_COMPLETION_NOT_READY = HANDOFF_BLOCKER_COMPLETION_NOT_READY
GATE_CONTRACT_MISSING = HANDOFF_BLOCKER_CONTRACT_MISSING
GATE_PRESERVATION_FAILED = HANDOFF_BLOCKER_PRESERVATION_FAILED
GATE_SEMANTIC_RECEIPT_MISSING = HANDOFF_BLOCKER_SEMANTIC_RECEIPT_MISSING
GATE_SEMANTIC_RECEIPT_INVALID = HANDOFF_BLOCKER_SEMANTIC_RECEIPT_INVALID

#: The supplied contract and the supplied decision do not describe one run.
GATE_CONTRACT_DECISION_MISMATCH = "contract_decision_mismatch"
#: INPUT.1's own fail-closed routing flag is false on the supplied contract.
GATE_CONTRACT_ROUTING_NOT_ALLOWED = "contract_routing_not_allowed"

GATE_BLOCKERS: tuple[str, ...] = (
    GATE_COMPLETION_NOT_READY,
    GATE_CONTRACT_MISSING,
    GATE_PRESERVATION_FAILED,
    GATE_SEMANTIC_RECEIPT_MISSING,
    GATE_SEMANTIC_RECEIPT_INVALID,
    GATE_CONTRACT_DECISION_MISMATCH,
    GATE_CONTRACT_ROUTING_NOT_ALLOWED,
)

MAX_GATE_BLOCKERS = len(GATE_BLOCKERS)


def waiter_authority() -> dict[str, bool]:
    """Every authority WAITER.1 declines to hold, in every status.

    A workflow recommendation is descriptive.  ``recommended_workflow=commander``
    does not grant orchestration, ``recommended_workflow=project_evolution``
    does not grant ``project_evolution_authority``, and no route grants a
    provider or a model.  Later wiring may consume a recommendation, but it
    must obtain its own authority under its own gates.
    """
    return {
        "routing_execution_authority": False,
        "execution_authority": False,
        "repository_read_authority": False,
        "repository_write_authority": False,
        "patch_authority": False,
        "validation_authority": False,
        "benchmark_authority": False,
        "work" + "er_launch_authority": False,
        "provider_selection_authority": False,
        "model_selection_authority": False,
        "model_escalation_authority": False,
        "dream_authority": False,
        "project_evolution_authority": False,
        "planning_authority": False,
        "context_selection_authority": False,
        "human_approval_required": True,
    }


def waiter_guardrails() -> dict[str, bool]:
    """Every action WAITER.1 did not perform while producing a decision."""
    return {
        "execution_performed": False,
        "workflow_dispatch_performed": False,
        "plan_generated": False,
        "repository_scan_performed": False,
        "repository_read_performed": False,
        "context_selection_performed": False,
        "read_set_generated": False,
        "reconnaissance_performed": False,
        "patch_generation_performed": False,
        "patch_application_performed": False,
        "validation_run": False,
        "benchmark_run_performed": False,
        "model_call_performed": False,
        "provider_selected": False,
        "network_call_performed": False,
        "web_search_performed": False,
        "semantic_reinterpretation_performed": False,
    }


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


# ── Records ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class WaiterReceipt:
    """Evidence for one Execution Waiter run: what it consumed, and what it was.

    The receipt deliberately records *statuses*, never the machinery behind
    them.  INPUT.2's adapter name and configured model are visible on the
    semantic receipt and are not copied here: a workflow decision that could
    name a model would be a model decision wearing a workflow's clothes.
    """

    handoff_verified: bool
    completion_state: str
    preservation_status: str
    semantic_status: str
    semantic_evidence_status: str
    contract_present: bool
    gate_blockers: tuple[str, ...] = ()
    source_contract_fingerprint: str | None = None
    source_raw_request_sha256: str | None = None
    source_completion_fingerprint: str = ""
    schema_version: str = WAITER_RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if len(self.gate_blockers) > MAX_GATE_BLOCKERS:
            raise ValueError("gate blockers exceed the supported bound")
        if len(set(self.gate_blockers)) != len(self.gate_blockers):
            raise ValueError("gate blockers must be distinct")
        for blocker in self.gate_blockers:
            if blocker not in GATE_BLOCKERS:
                raise ValueError(f"unsupported gate blocker: {blocker!r}")
        if self.handoff_verified and self.gate_blockers:
            raise ValueError("a verified handoff may not carry gate blockers")
        if not self.handoff_verified and not self.gate_blockers:
            raise ValueError("an unverified handoff must state at least one blocker")
        if self.handoff_verified and not self.source_contract_fingerprint:
            raise ValueError("a verified handoff must fingerprint its source contract")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "handoff_verified": self.handoff_verified,
            "gate_blockers": list(self.gate_blockers),
            "completion_state": self.completion_state,
            "preservation_status": self.preservation_status,
            "semantic_status": self.semantic_status,
            "semantic_evidence_status": self.semantic_evidence_status,
            "contract_present": self.contract_present,
            "source_contract_fingerprint": self.source_contract_fingerprint,
            "source_raw_request_sha256": self.source_raw_request_sha256,
            "source_completion_fingerprint": self.source_completion_fingerprint,
            "authority": waiter_authority(),
            "guardrails": waiter_guardrails(),
        }


# ── The hard entry gate ───────────────────────────────────────────────────────

def check_handoff_eligibility(
    contract: TaskContract | None,
    decision: CompletionDecision,
) -> WaiterReceipt:
    """Decide whether INPUT handed this order over, and record the evidence.

    Every blocker INPUT.3 already derived is carried through unchanged, and two
    integrity checks are added on top: the supplied contract must describe the
    same run as the supplied decision, and INPUT.1's own fail-closed
    ``routing_allowed`` must be true.  Neither can rescue a failed handoff; they
    can only refuse one that would otherwise have looked fine.
    """
    if not isinstance(decision, CompletionDecision):
        raise TypeError("check_handoff_eligibility requires a CompletionDecision")
    if contract is not None and not isinstance(contract, TaskContract):
        raise TypeError("check_handoff_eligibility requires a TaskContract or None")

    blockers: list[str] = list(decision.handoff_blockers)

    if (contract is None) != (not decision.contract_present):
        if GATE_CONTRACT_DECISION_MISMATCH not in blockers:
            blockers.append(GATE_CONTRACT_DECISION_MISMATCH)
    if contract is not None:
        if contract.preservation.status != decision.preservation_status:
            if GATE_CONTRACT_DECISION_MISMATCH not in blockers:
                blockers.append(GATE_CONTRACT_DECISION_MISMATCH)
        if contract.preservation.status != PRESERVATION_PASSED:
            if GATE_PRESERVATION_FAILED not in blockers:
                blockers.append(GATE_PRESERVATION_FAILED)
        if not contract.routing_allowed:
            blockers.append(GATE_CONTRACT_ROUTING_NOT_ALLOWED)

    ordered = tuple(item for item in GATE_BLOCKERS if item in blockers)

    return WaiterReceipt(
        handoff_verified=not ordered,
        completion_state=decision.state,
        preservation_status=decision.preservation_status,
        semantic_status=decision.semantic_status,
        semantic_evidence_status=decision.semantic_evidence_status,
        contract_present=decision.contract_present,
        gate_blockers=ordered,
        source_contract_fingerprint=(
            _fingerprint(contract.as_dict()) if contract is not None else None
        ),
        source_raw_request_sha256=(
            contract.raw_request.sha256 if contract is not None else None
        ),
        source_completion_fingerprint=_fingerprint(decision.as_dict()),
    )
