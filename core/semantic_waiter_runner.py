"""INPUT.2 — bounded semantic interpretation run, repair loop, and telemetry.

Drives one request through the Semantic Waiter:

    raw prompt
      -> explicit evidence            [INPUT.1, deterministic]
      -> model interpretation         [INPUT.2, at most 2 calls]
      -> Task Contract construction   [INPUT.1, deterministic]
      -> Requirement Preservation Gate[INPUT.1, deterministic]

The model never builds the authoritative contract. Its output is an
intermediate ``SemanticInterpretation`` that the frozen INPUT.1 path converts
and gates; ``routing_allowed`` continues to come from the gate alone.

Repair is hard-bounded at one retry, so a request costs at most
``MAX_SEMANTIC_MODEL_CALLS`` semantic calls. There is no recursive retry, no
escalation to a stronger model, and no provider switch. Asking the user is
INPUT.3 and is not done here.

This module is pure and transport-free.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

from core.explicit_evidence import extract_explicit_evidence
from core.input_understanding import understand_request
from core.semantic_waiter import ExplicitEvidenceInterpreter, StaticSemanticInterpreter
from core.semantic_waiter_adapter import (
    SemanticModelUnavailable,
    SemanticOutputInvalid,
    SemanticWaiterModelAdapter,
    prompt_was_truncated,
)
from core.task_contract import TaskContract


PHASE_ID = "INPUT.2"

#: Hard ceiling on semantic model calls per request: one attempt, one repair.
MAX_SEMANTIC_MODEL_CALLS = 2

# ── Outcome statuses ──────────────────────────────────────────────────────────
SEMANTIC_INTERPRETATION_OK = "semantic_interpretation_ok"
SEMANTIC_INTERPRETATION_REPAIRED = "semantic_interpretation_repaired"
SEMANTIC_INTERPRETATION_FAILED = "semantic_interpretation_failed"
SEMANTIC_OUTPUT_INVALID = "semantic_output_invalid"
SEMANTIC_MODEL_UNAVAILABLE = "semantic_model_unavailable"
#: A deterministic fallback is its own status, never dressed up as model
#: understanding, and it carries no routing authority.
SEMANTIC_DETERMINISTIC_FALLBACK = "semantic_deterministic_fallback"

SEMANTIC_WAITER_STATUSES: tuple[str, ...] = (
    SEMANTIC_INTERPRETATION_OK,
    SEMANTIC_INTERPRETATION_REPAIRED,
    SEMANTIC_INTERPRETATION_FAILED,
    SEMANTIC_OUTPUT_INVALID,
    SEMANTIC_MODEL_UNAVAILABLE,
    SEMANTIC_DETERMINISTIC_FALLBACK,
)

_SUCCESS_STATUSES: frozenset[str] = frozenset(
    {SEMANTIC_INTERPRETATION_OK, SEMANTIC_INTERPRETATION_REPAIRED}
)

# ── Per-attempt statuses ──────────────────────────────────────────────────────
ATTEMPT_OK = "ok"
ATTEMPT_PRESERVATION_FAILED = "preservation_failed"
ATTEMPT_OUTPUT_INVALID = "output_invalid"
ATTEMPT_MODEL_UNAVAILABLE = "model_unavailable"

ATTEMPT_STATUSES: tuple[str, ...] = (
    ATTEMPT_OK,
    ATTEMPT_PRESERVATION_FAILED,
    ATTEMPT_OUTPUT_INVALID,
    ATTEMPT_MODEL_UNAVAILABLE,
)

#: Bound on how much failure text is retained in telemetry.
MAX_RECEIPT_REASONS = 12
MAX_RECEIPT_REASON_CHARS = 200


def _authority() -> dict[str, bool]:
    """Every authority the Semantic Waiter does not hold, in any status."""
    return {
        "repository_read_authority": False,
        "repository_write_authority": False,
        "patch_authority": False,
        "validation_authority": False,
        "benchmark_authority": False,
        "routing_authority": False,
        "work" + "er_launch_authority": False,
        "provider_selection_authority": False,
        "execution_authority": False,
    }


@dataclass(frozen=True, slots=True)
class SemanticWaiterReceipt:
    """Bounded telemetry for one semantic interpretation run.

    Holds no credentials and no raw provider payload — only what is needed to
    explain what the waiter did. The raw user prompt is already preserved on
    the Task Contract.
    """

    adapter_name: str
    configured_model: str
    final_status: str
    first_attempt_status: str
    attempt_count: int = 0
    model_call_count: int = 0
    repair_attempted: bool = False
    repair_status: str | None = None
    structured_output_valid: bool = False
    preservation_failure_reasons: tuple[str, ...] = ()
    fallback_used: bool = False
    #: When a fallback replaced the model, the model failure it replaced.
    model_status: str | None = None
    prompt_truncated: bool = False

    def __post_init__(self) -> None:
        if self.final_status not in SEMANTIC_WAITER_STATUSES:
            raise ValueError(f"unsupported semantic status: {self.final_status!r}")
        if self.first_attempt_status not in ATTEMPT_STATUSES:
            raise ValueError(f"unsupported attempt status: {self.first_attempt_status!r}")
        if self.repair_status is not None and self.repair_status not in ATTEMPT_STATUSES:
            raise ValueError(f"unsupported repair status: {self.repair_status!r}")
        if self.model_call_count > MAX_SEMANTIC_MODEL_CALLS:
            raise ValueError(
                f"semantic model calls ({self.model_call_count}) exceeded the bound of "
                f"{MAX_SEMANTIC_MODEL_CALLS}"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase_id": PHASE_ID,
            "adapter_name": self.adapter_name,
            "configured_model": self.configured_model,
            "final_status": self.final_status,
            "first_attempt_status": self.first_attempt_status,
            "repair_attempted": self.repair_attempted,
            "repair_status": self.repair_status,
            "attempt_count": self.attempt_count,
            "model_call_count": self.model_call_count,
            "max_model_calls": MAX_SEMANTIC_MODEL_CALLS,
            "structured_output_valid": self.structured_output_valid,
            "preservation_failure_reasons": list(self.preservation_failure_reasons),
            "fallback_used": self.fallback_used,
            "model_status": self.model_status,
            "prompt_truncated": self.prompt_truncated,
            "authority": _authority(),
        }


@dataclass(frozen=True, slots=True)
class SemanticWaiterOutcome:
    """The result of one semantic interpretation run."""

    status: str
    receipt: SemanticWaiterReceipt
    contract: TaskContract | None = None

    def __post_init__(self) -> None:
        if self.status not in SEMANTIC_WAITER_STATUSES:
            raise ValueError(f"unsupported semantic status: {self.status!r}")
        if self.contract is not None and self.contract.routing_allowed:
            if self.status not in _SUCCESS_STATUSES:
                raise ValueError(
                    "routing may only be allowed after a successful semantic "
                    f"interpretation, not {self.status!r}"
                )

    @property
    def succeeded(self) -> bool:
        return self.status in _SUCCESS_STATUSES

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "receipt": self.receipt.as_dict(),
            "contract": self.contract.as_dict() if self.contract else None,
        }


def _reasons(contract: TaskContract | None) -> tuple[str, ...]:
    if contract is None:
        return ()
    return tuple(
        reason[:MAX_RECEIPT_REASON_CHARS]
        for reason in contract.preservation.reasons[:MAX_RECEIPT_REASONS]
    )


def _contract_from(raw_text: str, interpretation: Any) -> TaskContract:
    """Convert a model interpretation through the frozen deterministic path."""
    return understand_request(raw_text, interpreter=StaticSemanticInterpreter(interpretation))


def understand_request_semantically(
    raw_text: str,
    *,
    adapter: SemanticWaiterModelAdapter,
    allow_deterministic_fallback: bool = False,
) -> SemanticWaiterOutcome:
    """Interpret a request with the Semantic Waiter, with one bounded repair.

    ``adapter`` holds the single configured model; this function never selects,
    switches, or escalates one.

    ``allow_deterministic_fallback`` opts into producing a contract from the
    INPUT.1 deterministic interpreter when the model fails. The fallback is
    reported as :data:`SEMANTIC_DETERMINISTIC_FALLBACK`, still runs the
    preservation gate, and never allows routing — it is a record of the
    request, not a claim of semantic understanding.
    """
    if not isinstance(raw_text, str):
        raise TypeError("raw_text must be a string")

    evidence = extract_explicit_evidence(raw_text)
    truncated = prompt_was_truncated(raw_text)

    def _receipt(**kwargs: Any) -> SemanticWaiterReceipt:
        base: dict[str, Any] = {
            "adapter_name": adapter.name,
            "configured_model": adapter.model_id,
            "model_call_count": adapter.call_count,
            "prompt_truncated": truncated,
        }
        base.update(kwargs)
        return SemanticWaiterReceipt(**base)

    def _fallback(model_status: str, receipt: SemanticWaiterReceipt) -> SemanticWaiterOutcome:
        if not allow_deterministic_fallback:
            return SemanticWaiterOutcome(status=model_status, receipt=receipt, contract=None)
        deterministic = understand_request(raw_text, interpreter=ExplicitEvidenceInterpreter())
        # A deterministic reading of the words is not semantic understanding;
        # it may describe the request but may never authorize acting on it.
        deterministic = dataclasses.replace(deterministic, routing_allowed=False)
        return SemanticWaiterOutcome(
            status=SEMANTIC_DETERMINISTIC_FALLBACK,
            receipt=dataclasses.replace(
                receipt,
                final_status=SEMANTIC_DETERMINISTIC_FALLBACK,
                fallback_used=True,
                model_status=model_status,
            ),
            contract=deterministic,
        )

    # ── attempt 1 ─────────────────────────────────────────────────────────────
    try:
        interpretation = adapter.interpret(raw_text, evidence)
    except SemanticOutputInvalid:
        return _fallback(
            SEMANTIC_OUTPUT_INVALID,
            _receipt(
                final_status=SEMANTIC_OUTPUT_INVALID,
                first_attempt_status=ATTEMPT_OUTPUT_INVALID,
                attempt_count=1,
                structured_output_valid=False,
            ),
        )
    except SemanticModelUnavailable:
        return _fallback(
            SEMANTIC_MODEL_UNAVAILABLE,
            _receipt(
                final_status=SEMANTIC_MODEL_UNAVAILABLE,
                first_attempt_status=ATTEMPT_MODEL_UNAVAILABLE,
                attempt_count=1,
                structured_output_valid=False,
            ),
        )

    contract = _contract_from(raw_text, interpretation)
    if contract.routing_allowed:
        return SemanticWaiterOutcome(
            status=SEMANTIC_INTERPRETATION_OK,
            receipt=_receipt(
                final_status=SEMANTIC_INTERPRETATION_OK,
                first_attempt_status=ATTEMPT_OK,
                attempt_count=1,
                structured_output_valid=True,
            ),
            contract=contract,
        )

    # ── attempt 2: the single bounded repair ──────────────────────────────────
    first_reasons = _reasons(contract)
    try:
        repaired = adapter.repair(raw_text, evidence, contract.preservation)
    except SemanticOutputInvalid:
        return _fallback(
            SEMANTIC_INTERPRETATION_FAILED,
            _receipt(
                final_status=SEMANTIC_INTERPRETATION_FAILED,
                first_attempt_status=ATTEMPT_PRESERVATION_FAILED,
                attempt_count=2,
                repair_attempted=True,
                repair_status=ATTEMPT_OUTPUT_INVALID,
                structured_output_valid=False,
                preservation_failure_reasons=first_reasons,
            ),
        )
    except SemanticModelUnavailable:
        return _fallback(
            SEMANTIC_INTERPRETATION_FAILED,
            _receipt(
                final_status=SEMANTIC_INTERPRETATION_FAILED,
                first_attempt_status=ATTEMPT_PRESERVATION_FAILED,
                attempt_count=2,
                repair_attempted=True,
                repair_status=ATTEMPT_MODEL_UNAVAILABLE,
                structured_output_valid=True,
                preservation_failure_reasons=first_reasons,
            ),
        )

    repaired_contract = _contract_from(raw_text, repaired)
    if repaired_contract.routing_allowed:
        return SemanticWaiterOutcome(
            status=SEMANTIC_INTERPRETATION_REPAIRED,
            receipt=_receipt(
                final_status=SEMANTIC_INTERPRETATION_REPAIRED,
                first_attempt_status=ATTEMPT_PRESERVATION_FAILED,
                attempt_count=2,
                repair_attempted=True,
                repair_status=ATTEMPT_OK,
                structured_output_valid=True,
                preservation_failure_reasons=first_reasons,
            ),
            contract=repaired_contract,
        )

    # Budget exhausted. Stop honestly; escalation and clarification are not
    # INPUT.2's to perform.
    receipt = _receipt(
        final_status=SEMANTIC_INTERPRETATION_FAILED,
        first_attempt_status=ATTEMPT_PRESERVATION_FAILED,
        attempt_count=2,
        repair_attempted=True,
        repair_status=ATTEMPT_PRESERVATION_FAILED,
        structured_output_valid=True,
        preservation_failure_reasons=_reasons(repaired_contract) or first_reasons,
    )
    if allow_deterministic_fallback:
        return _fallback(SEMANTIC_INTERPRETATION_FAILED, receipt)
    return SemanticWaiterOutcome(
        status=SEMANTIC_INTERPRETATION_FAILED,
        receipt=receipt,
        contract=repaired_contract,
    )
