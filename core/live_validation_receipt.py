"""CHECK.LIVE.1 — validation expectation and receipt producers.

The live apply path runs at most one validation per execution, and it already
knows everything a CHECK.1 receipt needs at the moment that validation returns:
whether it was required, whether it executed, whether it passed, what it was run
against, and which state it therefore validated.  This module wraps those facts;
it never re-runs, re-orders, adds or removes a validation, and it never reads a
terminal log to decide what happened.

Two distinctions are preserved exactly because CHECK.1 depends on them:

*A failed validation still produces a receipt.*  "Only passing checks get
receipts" would make a red required check indistinguishable from a missing one,
and CHECK.1 treats those very differently — failed is blocked, missing is
merely incomplete.

*Not executed is not failed.*  When no validation was requested, this producer
emits **no** expectation and **no** receipt rather than a receipt claiming a
false result.  When the runtime refused to execute one it had (an unsafe legacy
shell command under an automation policy), the receipt result is ``skipped``: a
skip is not an execution, and CHECK.1 already refuses to let one discharge a
required expectation.
"""

from __future__ import annotations

from collections.abc import Sequence

from core.live_change_observation import canonical_relative_paths
from core.post_run_reconciliation import (
    MAX_TARGET_SCOPE_ENTRIES,
    RECEIPT_ERRORED,
    RECEIPT_FAILED,
    RECEIPT_PASSED,
    RECEIPT_SKIPPED,
    RECEIPT_TIMED_OUT,
    VALIDATION_UNIT_TESTS,
    ValidationExpectation,
    ValidationReceipt,
    validation_receipt_fingerprint,
)


PHASE_ID = "CHECK.LIVE.1"
PRODUCER_KIND = "live_validation_receipt"

#: The live apply path runs exactly one validation, so one stable id suffices.
#: The expectation and the receipt share it by construction, which is what lets
#: CHECK.1 match them without any name or scope heuristic.
LIVE_VALIDATION_ID = "live-validation"
LIVE_RECEIPT_ID_PREFIX = "live-receipt"

#: The live runtime has no structured validation *taxonomy*: it holds a single
#: project validation/test command and a safe-argv or legacy-shell mode.  This
#: producer therefore declares one fixed kind for the live validation rather
#: than inferring a kind from command text or changed filenames.  A richer
#: taxonomy has to come from an upstream expectation, not from here.
LIVE_VALIDATION_KIND = VALIDATION_UNIT_TESTS

#: Why no expectation could be produced.
EXPECTATION_UNAVAILABLE_NO_VALIDATION = "no_validation_requested"
EXPECTATION_UNAVAILABLE_SCOPE_UNBOUNDED = "target_scope_exceeds_bound"

EXPECTATION_UNAVAILABLE_REASONS: tuple[str, ...] = (
    EXPECTATION_UNAVAILABLE_NO_VALIDATION,
    EXPECTATION_UNAVAILABLE_SCOPE_UNBOUNDED,
)


class LiveValidationInputError(ValueError):
    """Raised when the supplied validation facts cannot form a receipt."""


def live_validation_target_scope(paths: Sequence[str]) -> tuple[str, ...] | None:
    """Canonical, sorted target scope, or ``None`` when it exceeds its bound."""
    scope = canonical_relative_paths(paths)
    if len(scope) > MAX_TARGET_SCOPE_ENTRIES:
        return None
    return scope


def build_live_validation_expectation(
    *,
    validation_requested: bool,
    target_scope: Sequence[str],
    required: bool = True,
) -> tuple[ValidationExpectation | None, str]:
    """Emit the one expectation the live path structurally knows about.

    Returns ``(expectation, unavailable_reason)``.  When the run requested no
    validation there is no expectation to state, and the caller records that
    rather than inventing a required check nobody asked for.
    """
    if not validation_requested:
        return None, EXPECTATION_UNAVAILABLE_NO_VALIDATION
    scope = live_validation_target_scope(target_scope)
    if scope is None:
        return None, EXPECTATION_UNAVAILABLE_SCOPE_UNBOUNDED
    return (
        ValidationExpectation(
            validation_id=LIVE_VALIDATION_ID,
            validation_kind=LIVE_VALIDATION_KIND,
            required=bool(required),
            target_scope=scope,
        ),
        "",
    )


def live_validation_result(
    *,
    executed: bool,
    passed: bool | None,
    blocked: bool = False,
    crashed: bool = False,
    timed_out: bool = False,
    inconclusive: bool = False,
) -> str | None:
    """Map the live validation outcome onto CHECK.1's receipt vocabulary.

    ``None`` means *not executed and not refused* — no receipt exists, which is
    a different fact from any receipt result and must stay that way.

    ``inconclusive`` (OPS.VALIDATE.1) is the third such distinction: the command
    ran, but no check was evaluated — the test runner was unavailable, or zero
    tests were collected.  CHECK.1's frozen vocabulary already has the word for
    that, and it is not ``failed``: ``errored`` says a validation did not
    produce a result, and it remains a *failing* receipt result, so a required
    expectation is still not discharged by one.  Emitting ``failed`` instead
    would put "the tests failed" into a receipt for a run in which no test
    existed.
    """
    if blocked:
        return RECEIPT_SKIPPED
    if crashed:
        return RECEIPT_ERRORED
    if timed_out:
        return RECEIPT_TIMED_OUT
    if not executed:
        return None
    if inconclusive:
        return RECEIPT_ERRORED
    if passed is True:
        return RECEIPT_PASSED
    if passed is False:
        return RECEIPT_FAILED
    return RECEIPT_ERRORED


def live_receipt_id(*, execution_run_id: str, result: str) -> str:
    """A bounded receipt identity derived from the run, never from a clock."""
    run = "".join(
        character
        for character in str(execution_run_id)
        if character.isalnum() or character in {"_", "-"}
    )[:96]
    return f"{LIVE_RECEIPT_ID_PREFIX}-{run or 'unknown'}-{result}"


def build_live_validation_receipt(
    *,
    execution_run_id: str,
    repository_id: str,
    validated_state_fingerprint: str,
    target_scope: Sequence[str],
    executed: bool,
    passed: bool | None,
    blocked: bool = False,
    crashed: bool = False,
    timed_out: bool = False,
    inconclusive: bool = False,
) -> ValidationReceipt | None:
    """Wrap one real validation outcome in a typed receipt, or emit none.

    The receipt is bound to the run, the repository, the expectation identity,
    the validation kind, the exact target scope, and — critically — the state
    the validation actually validated.  A receipt whose state is not the final
    state is what CHECK.1 later calls stale; that determination is CHECK.1's,
    never this producer's.
    """
    result = live_validation_result(
        executed=executed,
        passed=passed,
        blocked=blocked,
        crashed=crashed,
        timed_out=timed_out,
        inconclusive=inconclusive,
    )
    if result is None:
        return None
    scope = live_validation_target_scope(target_scope)
    if scope is None:
        raise LiveValidationInputError(
            "live validation target scope exceeds its finite bound"
        )
    return ValidationReceipt(
        receipt_id=live_receipt_id(
            execution_run_id=execution_run_id, result=result
        ),
        validation_id=LIVE_VALIDATION_ID,
        execution_run_id=execution_run_id,
        repository_id=repository_id,
        validation_kind=LIVE_VALIDATION_KIND,
        result=result,
        state_fingerprint=validated_state_fingerprint,
        target_scope=scope,
    )


def live_validation_receipt_fingerprint(receipt: ValidationReceipt) -> str:
    """Re-expose the frozen fingerprint so callers need no second import."""
    return validation_receipt_fingerprint(receipt)


def live_validation_guardrails() -> dict[str, bool]:
    """Every power the validation producers decline to exercise."""
    return {
        "wraps_existing_validation_result_only": True,
        "failed_validation_emits_receipt": True,
        "validation_executed": False,
        "validation_re_executed": False,
        "validation_command_added": False,
        "validation_command_removed": False,
        "validation_reordered": False,
        "validation_output_parsed": False,
        "terminal_prose_parsed": False,
        "repository_traversed": False,
        "source_content_read": False,
        "patch_applied": False,
        "files_modified": False,
        "network_call_performed": False,
        "model_called": False,
        "authoritative_effect": False,
        "human_approval_required": True,
    }


__all__ = [
    "PHASE_ID",
    "PRODUCER_KIND",
    "LIVE_VALIDATION_ID",
    "LIVE_RECEIPT_ID_PREFIX",
    "LIVE_VALIDATION_KIND",
    "EXPECTATION_UNAVAILABLE_NO_VALIDATION",
    "EXPECTATION_UNAVAILABLE_SCOPE_UNBOUNDED",
    "EXPECTATION_UNAVAILABLE_REASONS",
    "LiveValidationInputError",
    "live_validation_target_scope",
    "build_live_validation_expectation",
    "live_validation_result",
    "live_receipt_id",
    "build_live_validation_receipt",
    "live_validation_receipt_fingerprint",
    "live_validation_guardrails",
]
