"""EXEC.AUTH.LIVE.1 — execution authorization and outcome telemetry.

The black-box rerun that triggered this phase found runs in which T1/T2/T3
really did rewrite repository files, validation really did pass, and the bytes
really did stay on disk — while the operator-visible payload still said::

    write_authority             = false
    patch_application_authority = false
    human_approval_required     = true

None of those three fields was lying.  They were answering a different question
from the one the operator was asking.  They are written by
``core.control_engine.enforce_control_grounding_on_payload`` and by
``core.pipeline._record_patch_safety_handoff``, and their subject is *CONTROL
and the candidate it hands on*: CONTROL mints no write authority, CONTROL
cannot apply a patch, and a candidate CONTROL produced is not something a human
has approved.  All three remain true of CONTROL for the whole run, including a
run whose patch was applied a moment later by a different component under a
different rule.

So this module does not flip them.  It adds the two subjects the payload never
had, and keeps them apart from each other and from the first:

``component authority``
    may *this component* authorize a write?  CONTROL: no.  WAITER: no.  Patch
    basis: no.  Unchanged, and still reported by the historical fields, whose
    subject is now named explicitly by ``authority_scope``.

``execution authorization``
    did a later runtime gate authorize *this exact mutation*, and which one?
    That is ``core.pipeline.maybe_run_auto_patch`` reaching one of its two apply
    calls, under ``policy.auto_apply_allowed`` or the low-risk grounded
    single-file rule, with ``AUTO_PATCH_ENABLED`` on — or a human pressing an
    Apply control.

``execution fact``
    was it attempted, did bytes move, did anything survive, and what did
    validation say?

The three are deliberately not collapsible.  Authorization is not application
(§5); application is not persistence (§6); and passing sandbox validation,
carrying a legitimate patch basis, or reporting high model confidence are none
of them (§27–§29).

Everything here is *derived* from facts other components already established:
the policy object that made the decision, the executor's own result receipt,
CHECK.LIVE.1's bounded observation of the paths the operation named, and the
typed OPS.VALIDATE.1 outcome.  No model prose is consulted (§35), no repository
is traversed (§31), no model is called (§32), no network is opened (§33), and
nothing here can authorize, refuse, apply or roll back anything: with this
module deleted the run behaves identically (§34).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.rollback_outcome import (
    ROLLBACK_COMPLETED_VERIFIED,
    ROLLBACK_INCOMPLETE,
    ROLLBACK_NOT_ATTEMPTED,
    ROLLBACK_NOT_REQUIRED,
    ROLLBACK_UNVERIFIABLE,
    RollbackOutcome,
    RollbackOutcomeError,
    rollback_completed_verified,
    rollback_failure_notice,
    rollback_incomplete,
    rollback_not_attempted,
    rollback_not_required,
    rollback_outcome_from_mapping,
    rollback_unverifiable,
)
from core.validation_outcome import (
    VALIDATION_FAILED,
    VALIDATION_INCONCLUSIVE,
    VALIDATION_PASSED,
)


PHASE_ID = "EXEC.AUTH.LIVE.1"

#: Identity of the telemetry shape.  A future change to the vocabulary is a
#: visible schema change rather than a silent redefinition of old artifacts.
EXECUTION_TELEMETRY_SCHEMA_VERSION = "exec_auth_live_1_execution_telemetry_v2"

# ── §19/§20: the subject the historical authority fields always had ──────────
#
# ``write_authority=false`` in an artifact from before this phase meant "this
# component may not authorize writes".  It never meant "no write happened", and
# nothing here reinterprets it: the old fields keep their old value and their
# old meaning, and ``authority_scope`` states out loud which stage they are
# about, so a reader stops mistaking them for an outcome.
AUTHORITY_SCOPE_KEY = "authority_scope"
AUTHORITY_SCOPE_CONTROL_OR_PLANNING = "control_or_planning"

# ── §23: the execution authority sources that actually exist ─────────────────
#: No execution authority was obtained.
AUTHORITY_SOURCE_NONE = "none"
#: ``policy.auto_apply_allowed`` from
#: :func:`policy.decision_helper.build_patch_policy` — grounded-defect basis,
#: patch confidence at or above the style threshold, a known primary language,
#: and (for ``balanced``) a validation command.
AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY = "grounded_defect_auto_apply_policy"
#: ``core.pipeline.is_low_risk_single_file_patch`` — a CONTROL-grounded defect
#: candidate whose single target file and exact target snippet were verified
#: against the real file before the executor was called.  It is the one rule
#: that lets a ``safe_minimal`` run apply where the style policy alone would
#: not.
AUTHORITY_SOURCE_LOW_RISK_SINGLE_FILE = "low_risk_grounded_single_file_policy"
#: A human operator invoked an Apply control on an already-prepared plan.
AUTHORITY_SOURCE_MANUAL_APPLY = "manual_apply_action"

EXECUTION_AUTHORITY_SOURCES: tuple[str, ...] = (
    AUTHORITY_SOURCE_NONE,
    AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY,
    AUTHORITY_SOURCE_LOW_RISK_SINGLE_FILE,
    AUTHORITY_SOURCE_MANUAL_APPLY,
)

# ── Why execution was not authorized ─────────────────────────────────────────
#: Authorized runs carry no denial reason.
DENIED_NOT_APPLICABLE = ""
DENIED_NO_CHANGE_REQUESTED = "no_change_requested"
DENIED_HARNESS_MODE_BLOCKED = "harness_mode_blocked"
DENIED_AUTO_PATCH_DISABLED = "auto_patch_disabled"
DENIED_NO_PATCH_BASIS_HANDOFF = "no_patch_basis_handoff"
DENIED_NEEDS_ESCALATION = "needs_escalation"
DENIED_PATCH_STYLE_OR_TASK_NOT_ELIGIBLE = "patch_style_or_task_not_eligible"
DENIED_PATCH_BASIS_NOT_ACCEPTED = "patch_basis_not_accepted"
DENIED_HUMAN_APPROVAL_REQUIRED = "human_approval_required"
DENIED_PATCH_SAFETY_BLOCKED = "patch_safety_blocked"
DENIED_UNSAFE_VALIDATION_COMMAND = "unsafe_validation_command"
DENIED_EXECUTOR_RISK_BLOCKED = "executor_risk_blocked"
DENIED_PATCH_CONFIDENCE_BELOW_THRESHOLD = "patch_confidence_below_threshold"
DENIED_MISSING_SOURCE_SNIPPET = "missing_source_snippet"
DENIED_AUTO_PATCH_POLICY_DECLINED = "auto_patch_policy_declined"
DENIED_CANDIDATE_REJECTED = "candidate_rejected"
DENIED_TIME_BUDGET_EXCEEDED = "time_budget_exceeded"
# EXEC.APPROVAL.LIVE.1 — closed pre-execution manual-authorization denials.
DENIED_NOT_HUMAN_REVIEW_ELIGIBLE = "not_human_review_eligible"
DENIED_APPROVAL_MISSING = "approval_missing"
DENIED_CANDIDATE_MISMATCH = "candidate_mismatch"
DENIED_ELIGIBILITY_RECEIPT_STALE = "eligibility_receipt_stale"
DENIED_SOURCE_STATE_STALE = "source_state_stale"
DENIED_PATCH_SAFETY_MISMATCH = "patch_safety_mismatch"
DENIED_REPOSITORY_IDENTITY_MISMATCH = "repository_identity_mismatch"
DENIED_POLICY_PROFILE_MISMATCH = "policy_profile_mismatch"
DENIED_INCONSISTENT_INPUT = "inconsistent_input"

EXECUTION_DENIAL_REASONS: tuple[str, ...] = (
    DENIED_NOT_APPLICABLE,
    DENIED_NO_CHANGE_REQUESTED,
    DENIED_HARNESS_MODE_BLOCKED,
    DENIED_AUTO_PATCH_DISABLED,
    DENIED_NO_PATCH_BASIS_HANDOFF,
    DENIED_NEEDS_ESCALATION,
    DENIED_PATCH_STYLE_OR_TASK_NOT_ELIGIBLE,
    DENIED_PATCH_BASIS_NOT_ACCEPTED,
    DENIED_HUMAN_APPROVAL_REQUIRED,
    DENIED_PATCH_SAFETY_BLOCKED,
    DENIED_UNSAFE_VALIDATION_COMMAND,
    DENIED_EXECUTOR_RISK_BLOCKED,
    DENIED_PATCH_CONFIDENCE_BELOW_THRESHOLD,
    DENIED_MISSING_SOURCE_SNIPPET,
    DENIED_AUTO_PATCH_POLICY_DECLINED,
    DENIED_CANDIDATE_REJECTED,
    DENIED_TIME_BUDGET_EXCEEDED,
    DENIED_NOT_HUMAN_REVIEW_ELIGIBLE,
    DENIED_APPROVAL_MISSING,
    DENIED_CANDIDATE_MISMATCH,
    DENIED_ELIGIBILITY_RECEIPT_STALE,
    DENIED_SOURCE_STATE_STALE,
    DENIED_PATCH_SAFETY_MISMATCH,
    DENIED_REPOSITORY_IDENTITY_MISMATCH,
    DENIED_POLICY_PROFILE_MISMATCH,
    DENIED_INCONSISTENT_INPUT,
)

# ── What became of the attempt ───────────────────────────────────────────────
#: Nothing was executed.
APPLICATION_NOT_ATTEMPTED = "not_attempted"
#: The executor wrote, nothing reversed it, and the bytes really differ.
APPLICATION_APPLIED = "applied"
#: The executor wrote and the write was reversed.  Nothing persists.
APPLICATION_ROLLED_BACK = "rolled_back"
#: The executor ran and did not apply the patch.  Nothing persists.
APPLICATION_FAILED = "failed"
#: The executor ran and reported success, but no material change resulted.
APPLICATION_NO_OP = "no_op"

APPLICATION_STATUSES: tuple[str, ...] = (
    APPLICATION_NOT_ATTEMPTED,
    APPLICATION_APPLIED,
    APPLICATION_ROLLED_BACK,
    APPLICATION_FAILED,
    APPLICATION_NO_OP,
)

# ── §37: the typed validation fact, reported exactly as it already exists ────
#: No validation ran, because no execution ran or none was requested.
FINAL_VALIDATION_NOT_RUN = "not_run"
#: The run recorded no typed validation outcome at all.
FINAL_VALIDATION_UNAVAILABLE = "unavailable"

FINAL_VALIDATION_OUTCOMES: tuple[str, ...] = (
    FINAL_VALIDATION_NOT_RUN,
    VALIDATION_PASSED,
    VALIDATION_FAILED,
    VALIDATION_INCONCLUSIVE,
    FINAL_VALIDATION_UNAVAILABLE,
)

# ── §30: where the final-state answer came from ──────────────────────────────
#: No execution ran, so there was nothing to observe.
OBSERVATION_NOT_ATTEMPTED = "not_attempted"
#: Before/after content digests of exactly the paths the operation named.  That
#: is the whole scope: no other path in the repository is looked at, and a
#: change outside the named set is invisible here by construction.
OBSERVATION_PLAN_NAMED_PATHS = "plan_named_paths"
#: Digests were taken but could not type every path (a path with no "before"
#: identity, an unreadable or oversized file).  Final state falls back to the
#: executor's own receipt, and says so.
OBSERVATION_INCOMPLETE = "incomplete"
#: No digest observation was available at all; the executor receipt is the only
#: source.
OBSERVATION_UNAVAILABLE = "unavailable"

FINAL_STATE_OBSERVATIONS: tuple[str, ...] = (
    OBSERVATION_NOT_ATTEMPTED,
    OBSERVATION_PLAN_NAMED_PATHS,
    OBSERVATION_INCOMPLETE,
    OBSERVATION_UNAVAILABLE,
)

#: Payload keys this module owns.  Nothing outside this tuple is written, and
#: no historical key is removed or given a new meaning.
EXECUTION_TELEMETRY_KEYS: tuple[str, ...] = (
    "execution_telemetry_schema_version",
    AUTHORITY_SCOPE_KEY,
    "execution_authorized",
    "execution_authority_source",
    "execution_authorization_denied_reason",
    "human_approval_required_for_execution",
    "execution_attempted",
    "mutation_observed",
    "patch_applied",
    "application_status",
    "rollback_outcome_schema_version",
    "rollback_outcome",
    "rollback_status",
    "rollback_attempted",
    "rollback_completed",
    "rollback_verified",
    "rollback_performed",
    "remaining_changed_paths",
    "remaining_created_directories",
    "rollback_failure",
    "recovery_artifact_ids",
    "recovery_material_available",
    "recovery_material_error",
    "final_repository_changed",
    "final_state_verified",
    "final_validation_outcome",
    "final_state_observation",
    "observed_changed_paths",
    "execution_summary",
    "execution_authorization",
    "execution_outcome",
)


class ExecutionTelemetryError(ValueError):
    """Raised when a caller asks for a self-contradictory set of facts."""


@dataclass(frozen=True, slots=True)
class ExecutionTelemetry:
    """One run's execution authorization and execution outcome, kept apart.

    The invariants in :meth:`__post_init__` are the point of the type.  They
    are the collapses the field test actually produced, refused structurally
    rather than by convention, so a later caller cannot quietly reintroduce
    "authorized therefore applied" or "attempted therefore on disk".
    """

    execution_authorized: bool = False
    execution_authority_source: str = AUTHORITY_SOURCE_NONE
    execution_authorization_denied_reason: str = DENIED_NOT_APPLICABLE
    human_approval_required_for_execution: bool = True
    execution_attempted: bool = False
    mutation_observed: bool = False
    patch_applied: bool = False
    application_status: str = APPLICATION_NOT_ATTEMPTED
    rollback_outcome: RollbackOutcome = field(default_factory=rollback_not_required)
    rollback_performed: bool | None = None
    final_repository_changed: bool = False
    final_validation_outcome: str = FINAL_VALIDATION_NOT_RUN
    final_state_observation: str = OBSERVATION_NOT_ATTEMPTED
    observed_changed_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.rollback_outcome, RollbackOutcome):
            raise ExecutionTelemetryError("rollback_outcome must be typed")
        derived_rollback = self.rollback_outcome.performed
        if self.rollback_performed is None:
            object.__setattr__(self, "rollback_performed", derived_rollback)
        elif self.rollback_performed is not derived_rollback:
            raise ExecutionTelemetryError(
                "rollback_performed must derive from rollback_outcome"
            )
        if self.final_repository_changed != self.rollback_outcome.final_repository_changed:
            raise ExecutionTelemetryError(
                "final_repository_changed must derive from rollback_outcome"
            )
        if self.execution_authority_source not in EXECUTION_AUTHORITY_SOURCES:
            raise ExecutionTelemetryError(
                "unknown execution authority source: "
                f"{self.execution_authority_source!r}"
            )
        if (
            self.execution_authorization_denied_reason
            not in EXECUTION_DENIAL_REASONS
        ):
            raise ExecutionTelemetryError(
                "unknown execution denial reason: "
                f"{self.execution_authorization_denied_reason!r}"
            )
        if self.application_status not in APPLICATION_STATUSES:
            raise ExecutionTelemetryError(
                f"unknown application status: {self.application_status!r}"
            )
        if self.final_validation_outcome not in FINAL_VALIDATION_OUTCOMES:
            raise ExecutionTelemetryError(
                "unknown final validation outcome: "
                f"{self.final_validation_outcome!r}"
            )
        if self.final_state_observation not in FINAL_STATE_OBSERVATIONS:
            raise ExecutionTelemetryError(
                "unknown final state observation: "
                f"{self.final_state_observation!r}"
            )
        if not isinstance(self.observed_changed_paths, tuple):
            raise ExecutionTelemetryError(
                "observed_changed_paths must be a tuple"
            )

        # Authorization <-> source.  An authorized run names the gate that
        # authorized it; an unauthorized run names none and carries a reason.
        if self.execution_authorized:
            if self.execution_authority_source == AUTHORITY_SOURCE_NONE:
                raise ExecutionTelemetryError(
                    "an authorized execution must name its authority source"
                )
            if (
                self.execution_authorization_denied_reason
                != DENIED_NOT_APPLICABLE
            ):
                raise ExecutionTelemetryError(
                    "an authorized execution carries no denial reason"
                )
        else:
            if self.execution_authority_source != AUTHORITY_SOURCE_NONE:
                raise ExecutionTelemetryError(
                    "an unauthorized execution has no authority source"
                )
            if (
                self.execution_authorization_denied_reason
                == DENIED_NOT_APPLICABLE
            ):
                raise ExecutionTelemetryError(
                    "an unauthorized execution must record why"
                )

        # §5: authorization is not execution.  The implication runs one way
        # only — nothing may be attempted without authorization, and being
        # authorized never implies anything was attempted.
        if self.execution_attempted and not self.execution_authorized:
            raise ExecutionTelemetryError(
                "execution may not be attempted without authorization"
            )
        if self.mutation_observed and not self.execution_attempted:
            raise ExecutionTelemetryError(
                "a mutation cannot be observed without an attempt"
            )

        # §6/§13: execution is not final persistence.
        if self.final_repository_changed and not self.mutation_observed:
            raise ExecutionTelemetryError(
                "the repository cannot have changed with no observed mutation"
            )
        if self.patch_applied and not self.final_repository_changed:
            raise ExecutionTelemetryError(
                "a patch is not applied unless the change survives on disk"
            )
        if self.patch_applied and self.rollback_performed:
            raise ExecutionTelemetryError(
                "a rolled-back patch is not an applied patch"
            )
        if self.rollback_performed and self.final_repository_changed:
            raise ExecutionTelemetryError(
                "a rolled-back run leaves no repository change behind"
            )

        # Status <-> facts.
        if (self.application_status == APPLICATION_APPLIED) != self.patch_applied:
            raise ExecutionTelemetryError(
                "application_status=applied and patch_applied must agree"
            )
        if (
            self.application_status == APPLICATION_ROLLED_BACK
            and not self.rollback_performed
        ):
            raise ExecutionTelemetryError(
                "application_status=rolled_back requires a rollback"
            )
        if (
            self.application_status == APPLICATION_NOT_ATTEMPTED
            and self.execution_attempted
        ):
            raise ExecutionTelemetryError(
                "an attempted execution is not application_status=not_attempted"
            )
        if (
            self.application_status != APPLICATION_NOT_ATTEMPTED
            and not self.execution_attempted
        ):
            raise ExecutionTelemetryError(
                "an unattempted execution has no application status"
            )
        if self.observed_changed_paths and not self.execution_attempted:
            raise ExecutionTelemetryError(
                "no path may be observed changed without an attempt"
            )
        if (
            self.final_state_observation == OBSERVATION_NOT_ATTEMPTED
            and self.execution_attempted
        ):
            raise ExecutionTelemetryError(
                "an attempted execution must record how final state was derived"
            )

    # ── rendering ───────────────────────────────────────────────────────────
    def authorization_dict(self) -> dict[str, Any]:
        """The pre-mutation half: who allowed this, and was anyone asked."""
        return {
            "execution_authorized": self.execution_authorized,
            "execution_authority_source": self.execution_authority_source,
            "execution_authorization_denied_reason": (
                self.execution_authorization_denied_reason
            ),
            "human_approval_required_for_execution": (
                self.human_approval_required_for_execution
            ),
        }

    def outcome_dict(self) -> dict[str, Any]:
        """The post-mutation half: what was actually observed to happen."""
        return {
            "execution_attempted": self.execution_attempted,
            "mutation_observed": self.mutation_observed,
            "patch_applied": self.patch_applied,
            "application_status": self.application_status,
            **self.rollback_outcome.as_payload_fields(),
            "final_validation_outcome": self.final_validation_outcome,
            "final_state_observation": self.final_state_observation,
            "observed_changed_paths": list(self.observed_changed_paths),
        }

    def summary(self) -> str:
        """One operator-readable sentence pair, never a universal template."""
        return describe_execution_telemetry(self)

    def as_payload_fields(self) -> dict[str, Any]:
        """Every key this module writes onto an operator-visible payload.

        Flat facts and the two grouped structures are rendered from the same
        object in one place, so a reader who scans top-level keys and a reader
        who opens ``execution_outcome`` can never be told different things.
        """
        authorization = self.authorization_dict()
        outcome = self.outcome_dict()
        return {
            "execution_telemetry_schema_version": (
                EXECUTION_TELEMETRY_SCHEMA_VERSION
            ),
            AUTHORITY_SCOPE_KEY: AUTHORITY_SCOPE_CONTROL_OR_PLANNING,
            **authorization,
            **outcome,
            "execution_summary": self.summary(),
            "execution_authorization": authorization,
            "execution_outcome": outcome,
        }


@dataclass(frozen=True, slots=True)
class FinalStateObservation:
    """What the bounded observer could say about the paths an operation named."""

    scope: str = OBSERVATION_NOT_ATTEMPTED
    changed_paths: tuple[str, ...] = ()
    complete: bool = False

    def __post_init__(self) -> None:
        if self.scope not in FINAL_STATE_OBSERVATIONS:
            raise ExecutionTelemetryError(
                f"unknown final state observation: {self.scope!r}"
            )
        if self.changed_paths and self.scope in {
            OBSERVATION_NOT_ATTEMPTED,
            OBSERVATION_UNAVAILABLE,
        }:
            raise ExecutionTelemetryError(
                "an unavailable observation reports no changed path"
            )
        if self.complete and self.scope != OBSERVATION_PLAN_NAMED_PATHS:
            raise ExecutionTelemetryError(
                "only a fully typed observation may be marked complete"
            )


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    """The executor's own account of one apply attempt.

    Every field is copied from a typed value the executor set for its own
    purposes.  Nothing here is parsed out of prose, and nothing is inferred
    from what a model said it did (§35).
    """

    write_receipted: bool = False
    apply_succeeded: bool = False
    rollback_outcome: RollbackOutcome = field(
        default_factory=lambda: rollback_not_required(final_state_verified=False)
    )
    rollback_performed: bool | None = None
    validation_requested: bool = False
    validation_outcome: str | None = None
    target_paths: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.rollback_outcome, RollbackOutcome):
            raise ExecutionTelemetryError("receipt rollback_outcome must be typed")
        derived = self.rollback_outcome.performed
        if self.rollback_performed is None:
            object.__setattr__(self, "rollback_performed", derived)
        elif self.rollback_performed is not derived:
            raise ExecutionTelemetryError(
                "receipt rollback_performed must derive from rollback_outcome"
            )


#: Executor phases that mean bytes were written to the worktree, whether or not
#: they survived.  Every other phase returns before ``apply_patch_from_json``.
_SINGLE_FILE_WRITE_PHASES: frozenset[str] = frozenset(
    {
        "validated",
        "applied_no_validation",
        "validation_failed",
        "validation_environment_failed",
        "post_apply_blocked",
        "oracle_recovery_failed",
    }
)


def _normalize_validation_outcome(value: Any) -> str | None:
    if value in {VALIDATION_PASSED, VALIDATION_FAILED, VALIDATION_INCONCLUSIVE}:
        return str(value)
    return None


def plan_execution_receipt(result: Mapping[str, Any] | None) -> ExecutionReceipt:
    """Read one ``patching.patch_plan_executor`` result as a receipt.

    ``applied_ops`` — not ``rollback_performed`` — is the plan executor's
    record of writes.  The two are not the same fact: rollback success records
    independently verified restoration after writes, while a first-operation
    failure has no mutation to recover.  The write question is therefore asked
    of the applied operations and rollback truth comes from its typed outcome.
    """
    if not isinstance(result, Mapping):
        return ExecutionReceipt()
    applied_ops = result.get("applied_ops")
    command = result.get("validation_command")
    return ExecutionReceipt(
        write_receipted=bool(applied_ops),
        apply_succeeded=bool(result.get("success")),
        rollback_outcome=rollback_outcome_from_mapping(result),
        validation_requested=bool(command),
        validation_outcome=_normalize_validation_outcome(
            result.get("validation_outcome")
        ),
    )


def plan_pre_mutation_refusal(result: Mapping[str, Any] | None) -> str:
    """Name the gate that refused a plan *before* any byte was written, if any.

    The plan apply path runs the frozen patch-safety gate and the safe-validation
    gate against the real project root before it touches a file.  A refusal
    there is not an execution that failed; it is a mutation that was never
    authorized (§12), and the honest telemetry says exactly that rather than
    reporting an attempt nobody made.
    """
    if not isinstance(result, Mapping):
        return DENIED_NOT_APPLICABLE
    if result.get("unsafe_validation_blocked"):
        return DENIED_UNSAFE_VALIDATION_COMMAND
    safety = result.get("patch_safety")
    if isinstance(safety, Mapping) and safety.get("ok") is False:
        return DENIED_PATCH_SAFETY_BLOCKED
    return DENIED_NOT_APPLICABLE


#: Executor phases that end the run before ``apply_patch_from_json`` is called,
#: mapped to the gate that ended it.  ``conflict`` is deliberately absent: a
#: patch whose target no longer matches was executed and failed, not refused.
_SINGLE_FILE_REFUSAL_PHASES: dict[str, str] = {
    "patch_safety_blocked": DENIED_PATCH_SAFETY_BLOCKED,
    "unsafe_validation_blocked": DENIED_UNSAFE_VALIDATION_COMMAND,
    "dry_run_blocked": DENIED_EXECUTOR_RISK_BLOCKED,
}


def single_file_pre_mutation_refusal(
    attempts: Sequence[Mapping[str, Any]] | None,
) -> str:
    """Name the executor gate that refused every attempt before writing."""
    records = [
        record for record in (attempts or []) if isinstance(record, Mapping)
    ]
    if not records:
        return DENIED_NOT_APPLICABLE
    reasons = {
        _SINGLE_FILE_REFUSAL_PHASES.get(str(record.get("phase") or ""), "")
        for record in records
    }
    if len(reasons) == 1:
        return reasons.pop() or DENIED_NOT_APPLICABLE
    return DENIED_NOT_APPLICABLE


def single_file_execution_receipt(
    attempts: Sequence[Mapping[str, Any]] | None,
    *,
    success: bool,
    validation_requested: bool,
) -> ExecutionReceipt:
    """Read a self-correction loop's attempt records as one receipt.

    The loop may write more than once — attempt 1 fails and is rolled back,
    attempt 2 applies.  ``write_receipted`` is therefore true if *any* attempt
    wrote, while ``rollback_performed`` describes the run's terminal state: a
    loop that ended successfully has an applied patch on disk whatever an
    earlier attempt did, and only a loop that ended without success reports
    that its writes were reversed.
    """
    records = [
        record for record in (attempts or []) if isinstance(record, Mapping)
    ]
    wrote = any(
        str(record.get("phase") or "") in _SINGLE_FILE_WRITE_PHASES
        for record in records
    )
    outcomes = [rollback_outcome_from_mapping(record) for record in records]
    last = records[-1] if records else {}
    targets = tuple(
        sorted(
            {
                str(record.get("target_file"))
                for record in records
                if record.get("target_file")
            }
        )
    )
    unresolved = [
        outcome for outcome in outcomes
        if outcome.status in {ROLLBACK_INCOMPLETE, ROLLBACK_UNVERIFIABLE}
        or outcome.status == ROLLBACK_NOT_ATTEMPTED
        and outcome.final_repository_changed
    ]
    if unresolved:
        # A later attempt has its own baseline. It cannot prove that an earlier
        # failed rollback restored the earlier baseline, even on the same path.
        paths = tuple(sorted({p for o in unresolved for p in o.remaining_changed_paths}))
        directories = tuple(sorted({p for o in unresolved for p in o.remaining_created_directories}))
        if any(o.status == ROLLBACK_UNVERIFIABLE for o in unresolved):
            terminal_outcome = rollback_unverifiable(
                paths, directories, attempted=any(o.attempted for o in unresolved),
                failure_code="loop_rollback_unverifiable",
                failure_reason="At least one attempt has unresolved rollback evidence.",
            )
        elif any(o.attempted for o in unresolved):
            terminal_outcome = rollback_incomplete(
                paths, directories,
                failure_code="loop_rollback_incomplete",
                failure_reason="At least one attempt left unresolved repository state.",
            )
        else:
            terminal_outcome = rollback_not_attempted(paths, directories)
        terminal_outcome = terminal_outcome.with_recovery_material(
            tuple(i for o in unresolved for i in o.recovery_artifact_ids),
            error=";".join(dict.fromkeys(o.recovery_material_error for o in unresolved if o.recovery_material_error)),
        )
    elif success:
        terminal_outcome = outcomes[-1] if outcomes else rollback_not_required(
            final_state_verified=False
        )
    else:
        terminal_outcome = next(
            (
                outcome
                for outcome in reversed(outcomes)
                if outcome.status != ROLLBACK_NOT_REQUIRED
            ),
            rollback_not_required(),
        )
    return ExecutionReceipt(
        write_receipted=wrote or terminal_outcome.attempted,
        apply_succeeded=bool(success) and not unresolved,
        rollback_outcome=terminal_outcome,
        validation_requested=bool(validation_requested),
        validation_outcome=_normalize_validation_outcome(
            last.get("validation_outcome")
        ),
        target_paths=targets,
    )


# ── Builders ─────────────────────────────────────────────────────────────────

def no_execution(
    denied_reason: str,
    *,
    human_approval_required_for_execution: bool = True,
) -> ExecutionTelemetry:
    """Nothing was authorized and nothing was attempted.

    This is the honest shape for analysis, clarification, a wrong-target run
    with no resolved patch basis, a candidate patch safety rejected, an
    explicit change awaiting approval, and ``AUTO_PATCH_ENABLED=false``.  None
    of them may imply a patch was attempted (§9–§12, §25).
    """
    if denied_reason == DENIED_NOT_APPLICABLE:
        raise ExecutionTelemetryError("a refusal must record why")
    return ExecutionTelemetry(
        execution_authorized=False,
        execution_authority_source=AUTHORITY_SOURCE_NONE,
        execution_authorization_denied_reason=denied_reason,
        human_approval_required_for_execution=(
            human_approval_required_for_execution
        ),
    )


def authorized_execution(
    *,
    authority_source: str,
    receipt: ExecutionReceipt,
    observation: FinalStateObservation,
    human_approval_required_for_execution: bool = False,
) -> ExecutionTelemetry:
    """Describe a run a runtime gate authorized and the executor then ran.

    Final persistence is taken from the bounded observation when it typed every
    named path, and from the executor's own receipt when it could not (§30).
    Which of the two answered is reported rather than hidden, because "the
    bytes differ" and "the executor says it wrote" are different claims, and an
    operator is entitled to know which one they are being given.
    """
    if authority_source not in EXECUTION_AUTHORITY_SOURCES:
        raise ExecutionTelemetryError(
            f"unknown execution authority source: {authority_source!r}"
        )
    if authority_source == AUTHORITY_SOURCE_NONE:
        raise ExecutionTelemetryError(
            "an authorized execution must name its authority source"
        )

    observed_changed = bool(observation.changed_paths)
    outcome = receipt.rollback_outcome
    if observation.complete:
        observed_paths = tuple(observation.changed_paths)
        if outcome.status in {
            ROLLBACK_COMPLETED_VERIFIED,
            ROLLBACK_INCOMPLETE,
            ROLLBACK_UNVERIFIABLE,
        } and outcome.attempted:
            if observed_paths:
                paths = tuple(sorted(set(observed_paths) | set(outcome.remaining_changed_paths)))
                # A digest window does not cover modes, created directories,
                # unreadable earlier targets, or another attempt's baseline.
                # It may refute success, but cannot upgrade broader failure.
                if outcome.status == ROLLBACK_UNVERIFIABLE:
                    reconciled = replace(outcome, remaining_changed_paths=paths)
                else:
                    reconciled = rollback_incomplete(
                        paths,
                        outcome.remaining_created_directories,
                        failure_code=(
                            "post_rollback_state_changed"
                            if outcome.performed
                            else outcome.failure_code or "rollback_incomplete"
                        ),
                        failure_reason=(
                            "A later final-state observation found paths different "
                            "from the authoritative pre-mutation baseline."
                            if outcome.performed
                            else outcome.failure_reason
                            or "Final observation confirmed unresolved rollback paths."
                        ),
                    )
                outcome = reconciled.with_recovery_material(
                    outcome.recovery_artifact_ids,
                    error=outcome.recovery_material_error,
                )
        elif outcome.status == ROLLBACK_NOT_ATTEMPTED:
            outcome = rollback_not_attempted(
                tuple(sorted(set(observed_paths) | set(outcome.remaining_changed_paths))),
                outcome.remaining_created_directories,
                failure_code=outcome.failure_code or "rollback_not_attempted",
                failure_reason=outcome.failure_reason,
            )
        elif outcome.status == ROLLBACK_NOT_REQUIRED:
            outcome = rollback_not_required(
                final_repository_changed=observed_changed,
                final_state_verified=True,
            )
    elif outcome.status == ROLLBACK_NOT_REQUIRED and not outcome.final_state_verified:
        outcome = rollback_not_required(
            final_repository_changed=bool(
                receipt.apply_succeeded and receipt.write_receipted
            ),
            final_state_verified=False,
        )

    final_changed = outcome.final_repository_changed
    mutation_observed = bool(
        receipt.write_receipted or observed_changed or outcome.attempted
        or outcome.final_repository_changed
    )

    patch_applied = bool(
        final_changed
        and receipt.apply_succeeded
        and not outcome.performed
    )

    if outcome.performed and mutation_observed:
        status = APPLICATION_ROLLED_BACK
    elif patch_applied:
        status = APPLICATION_APPLIED
    elif receipt.apply_succeeded:
        # The executor reports success, and nothing material changed on disk.
        status = APPLICATION_NO_OP
    else:
        # Including a run whose reversal routine ran over nothing: no write
        # was receipted, so there is no rollback to report as an outcome.
        status = APPLICATION_FAILED

    if receipt.validation_outcome is not None:
        validation = receipt.validation_outcome
    elif not receipt.validation_requested:
        validation = FINAL_VALIDATION_NOT_RUN
    else:
        validation = FINAL_VALIDATION_UNAVAILABLE

    return ExecutionTelemetry(
        execution_authorized=True,
        execution_authority_source=authority_source,
        execution_authorization_denied_reason=DENIED_NOT_APPLICABLE,
        human_approval_required_for_execution=(
            human_approval_required_for_execution
        ),
        execution_attempted=True,
        mutation_observed=mutation_observed,
        patch_applied=patch_applied,
        application_status=status,
        rollback_outcome=outcome,
        final_repository_changed=final_changed,
        final_validation_outcome=validation,
        final_state_observation=(
            observation.scope
            if observation.scope != OBSERVATION_NOT_ATTEMPTED
            else OBSERVATION_UNAVAILABLE
        ),
        observed_changed_paths=tuple(observation.changed_paths),
    )


# ── §31: bounded observation, reusing CHECK.LIVE.1's own observer ────────────

def observe_named_paths(project_root: str | Path, paths: Sequence[str]) -> Any:
    """Digest exactly the named paths, or return ``None``.

    A thin, failure-isolated wrapper over CHECK.LIVE.1's ``digest_known_paths``:
    no directory is walked, no path is discovered, and an observation that
    cannot be taken becomes an honest ``None`` rather than a fabricated fact.
    """
    if not paths:
        return None
    try:
        from core.live_change_observation import digest_known_paths

        return digest_known_paths(project_root, list(paths))
    except Exception:  # noqa: BLE001 - observation failure is never fatal
        return None


def final_state_observation(before: Any, after: Any) -> FinalStateObservation:
    """Compare two bounded digest windows into a final-state observation."""
    if before is None or after is None:
        return FinalStateObservation(scope=OBSERVATION_UNAVAILABLE)
    try:
        from core.live_change_observation import derive_observed_change_records

        change_set = derive_observed_change_records(before, after)
    except Exception:  # noqa: BLE001 - observation failure is never fatal
        return FinalStateObservation(scope=OBSERVATION_UNAVAILABLE)

    complete = not change_set.observation_incomplete
    return FinalStateObservation(
        scope=(
            OBSERVATION_PLAN_NAMED_PATHS if complete else OBSERVATION_INCOMPLETE
        ),
        changed_paths=tuple(change_set.changed_paths),
        complete=complete,
    )


# ── §21: the operator-visible sentence ───────────────────────────────────────

_AUTHORITY_PHRASES: dict[str, str] = {
    AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY: (
        "the grounded-defect auto-apply policy"
    ),
    AUTHORITY_SOURCE_LOW_RISK_SINGLE_FILE: (
        "the low-risk grounded single-file policy"
    ),
    AUTHORITY_SOURCE_MANUAL_APPLY: "a human apply action",
}

_DENIAL_PHRASES: dict[str, str] = {
    DENIED_NO_CHANGE_REQUESTED: "no repository change was requested",
    DENIED_HARNESS_MODE_BLOCKED: "the harness mode does not permit applying",
    DENIED_AUTO_PATCH_DISABLED: "automatic patching is disabled",
    DENIED_NO_PATCH_BASIS_HANDOFF: (
        "there is no legitimate patch basis with exact grounded targets"
    ),
    DENIED_NEEDS_ESCALATION: "the candidate was escalated for review",
    DENIED_PATCH_STYLE_OR_TASK_NOT_ELIGIBLE: (
        "this task and patch style do not permit automatic application"
    ),
    DENIED_PATCH_BASIS_NOT_ACCEPTED: "the patch basis was not accepted",
    DENIED_HUMAN_APPROVAL_REQUIRED: (
        "human approval is required before this candidate may be applied"
    ),
    DENIED_PATCH_SAFETY_BLOCKED: "patch safety blocked the candidate",
    DENIED_UNSAFE_VALIDATION_COMMAND: (
        "the validation command was not safe to run under automation"
    ),
    DENIED_EXECUTOR_RISK_BLOCKED: (
        "the executor's risk gate refused the patch before writing"
    ),
    DENIED_PATCH_CONFIDENCE_BELOW_THRESHOLD: (
        "patch confidence is below the threshold this policy requires"
    ),
    DENIED_MISSING_SOURCE_SNIPPET: "no exact source snippet was available",
    DENIED_AUTO_PATCH_POLICY_DECLINED: "the auto-patch policy declined",
    DENIED_CANDIDATE_REJECTED: "the candidate was rejected",
    DENIED_TIME_BUDGET_EXCEEDED: "the time budget was exhausted",
    DENIED_NOT_HUMAN_REVIEW_ELIGIBLE: (
        "the candidate is not eligible for bounded human review"
    ),
    DENIED_APPROVAL_MISSING: "an explicit human Apply action is missing",
    DENIED_CANDIDATE_MISMATCH: "approval targets a different candidate",
    DENIED_ELIGIBILITY_RECEIPT_STALE: (
        "the reviewed execution-eligibility receipt is stale"
    ),
    DENIED_SOURCE_STATE_STALE: "the reviewed source state is stale",
    DENIED_PATCH_SAFETY_MISMATCH: (
        "patch safety no longer matches the reviewed candidate"
    ),
    DENIED_REPOSITORY_IDENTITY_MISMATCH: (
        "the Apply action targets a different repository"
    ),
    DENIED_POLICY_PROFILE_MISMATCH: (
        "the Apply action does not match the reviewed policy profile"
    ),
    DENIED_INCONSISTENT_INPUT: "the human Apply input is inconsistent",
}

_VALIDATION_PHRASES: dict[str, str] = {
    VALIDATION_PASSED: "Validation passed.",
    VALIDATION_FAILED: "Validation failed.",
    VALIDATION_INCONCLUSIVE: "Validation was inconclusive.",
    FINAL_VALIDATION_NOT_RUN: "No validation was run.",
    FINAL_VALIDATION_UNAVAILABLE: "Validation recorded no typed outcome.",
}


def describe_execution_telemetry(telemetry: ExecutionTelemetry) -> str:
    """Render the facts as a sentence that says only what they support."""
    if not telemetry.execution_authorized:
        reason = _DENIAL_PHRASES.get(
            telemetry.execution_authorization_denied_reason,
            "execution was not authorized",
        )
        return (
            f"No patch was applied: {reason}. "
            "The repository was not modified by this run."
        )

    source = _AUTHORITY_PHRASES.get(
        telemetry.execution_authority_source, "an existing execution policy"
    )
    validation = _VALIDATION_PHRASES.get(
        telemetry.final_validation_outcome,
        "Validation recorded no typed outcome.",
    )

    if not telemetry.execution_attempted:
        return (
            f"Patch execution was authorized under {source}, but never "
            "attempted. The repository was not modified by this run."
        )
    if telemetry.application_status == APPLICATION_APPLIED:
        if telemetry.execution_authority_source == AUTHORITY_SOURCE_MANUAL_APPLY:
            return (
                "You approved this exact candidate. It was applied under the "
                "manual Apply authority path (human apply action). "
                f"{validation} Repository changes "
                "remain on disk."
            )
        return (
            f"Patch applied automatically under {source}. {validation} "
            "Repository changes remain on disk."
        )
    if telemetry.application_status == APPLICATION_ROLLED_BACK:
        return (
            f"Patch execution was authorized under {source} and attempted. "
            f"{validation} Changes were rolled back; the repository was "
            "restored."
        )
    if telemetry.final_repository_changed and telemetry.rollback_outcome.status in {
        ROLLBACK_INCOMPLETE,
        ROLLBACK_UNVERIFIABLE,
        ROLLBACK_NOT_ATTEMPTED,
    }:
        return (
            f"Patch execution was authorized under {source} and attempted. "
            f"{validation} {rollback_failure_notice(telemetry.rollback_outcome)}"
        )
    if telemetry.application_status == APPLICATION_NO_OP:
        return (
            f"Patch execution was authorized under {source} and ran, but "
            f"produced no material repository change. {validation}"
        )
    return (
        f"Patch execution was authorized under {source} and attempted, but the "
        f"patch was not applied. {validation} No final repository change was "
        "observed for this run."
    )


def execution_telemetry_guardrails() -> dict[str, bool]:
    """Every power this telemetry declines to exercise (§26, §31–§34)."""
    return {
        "authority_described_not_granted": True,
        "authority_widening_possible": False,
        "execution_behavior_changed": False,
        "patch_eligibility_changed": False,
        "human_approval_policy_changed": False,
        "patch_safety_changed": False,
        "auto_patch_policy_changed": False,
        "model_self_report_consumed": False,
        "repository_traversed": False,
        "validation_executed": False,
        "patch_applied_by_this_module": False,
        "model_called": False,
        "network_call_performed": False,
        "authoritative_effect": False,
    }


def attach_execution_telemetry(payload: Any, telemetry: ExecutionTelemetry) -> Any:
    """Write the telemetry onto one operator-visible payload.

    Additive by construction: every historical key keeps its value and its
    meaning, and only :data:`EXECUTION_TELEMETRY_KEYS` are written (§19, §20).
    """
    if not isinstance(payload, dict):
        return payload
    payload.update(telemetry.as_payload_fields())
    return payload


__all__ = [
    "PHASE_ID",
    "EXECUTION_TELEMETRY_SCHEMA_VERSION",
    "AUTHORITY_SCOPE_KEY",
    "AUTHORITY_SCOPE_CONTROL_OR_PLANNING",
    "AUTHORITY_SOURCE_NONE",
    "AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY",
    "AUTHORITY_SOURCE_LOW_RISK_SINGLE_FILE",
    "AUTHORITY_SOURCE_MANUAL_APPLY",
    "EXECUTION_AUTHORITY_SOURCES",
    "DENIED_NOT_APPLICABLE",
    "DENIED_NO_CHANGE_REQUESTED",
    "DENIED_HARNESS_MODE_BLOCKED",
    "DENIED_AUTO_PATCH_DISABLED",
    "DENIED_NO_PATCH_BASIS_HANDOFF",
    "DENIED_NEEDS_ESCALATION",
    "DENIED_PATCH_STYLE_OR_TASK_NOT_ELIGIBLE",
    "DENIED_PATCH_BASIS_NOT_ACCEPTED",
    "DENIED_HUMAN_APPROVAL_REQUIRED",
    "DENIED_PATCH_SAFETY_BLOCKED",
    "DENIED_UNSAFE_VALIDATION_COMMAND",
    "DENIED_EXECUTOR_RISK_BLOCKED",
    "DENIED_PATCH_CONFIDENCE_BELOW_THRESHOLD",
    "DENIED_MISSING_SOURCE_SNIPPET",
    "DENIED_AUTO_PATCH_POLICY_DECLINED",
    "DENIED_CANDIDATE_REJECTED",
    "DENIED_TIME_BUDGET_EXCEEDED",
    "DENIED_NOT_HUMAN_REVIEW_ELIGIBLE",
    "DENIED_APPROVAL_MISSING",
    "DENIED_CANDIDATE_MISMATCH",
    "DENIED_ELIGIBILITY_RECEIPT_STALE",
    "DENIED_SOURCE_STATE_STALE",
    "DENIED_PATCH_SAFETY_MISMATCH",
    "DENIED_REPOSITORY_IDENTITY_MISMATCH",
    "DENIED_POLICY_PROFILE_MISMATCH",
    "DENIED_INCONSISTENT_INPUT",
    "EXECUTION_DENIAL_REASONS",
    "APPLICATION_NOT_ATTEMPTED",
    "APPLICATION_APPLIED",
    "APPLICATION_ROLLED_BACK",
    "APPLICATION_FAILED",
    "APPLICATION_NO_OP",
    "APPLICATION_STATUSES",
    "FINAL_VALIDATION_NOT_RUN",
    "FINAL_VALIDATION_UNAVAILABLE",
    "FINAL_VALIDATION_OUTCOMES",
    "OBSERVATION_NOT_ATTEMPTED",
    "OBSERVATION_PLAN_NAMED_PATHS",
    "OBSERVATION_INCOMPLETE",
    "OBSERVATION_UNAVAILABLE",
    "FINAL_STATE_OBSERVATIONS",
    "EXECUTION_TELEMETRY_KEYS",
    "ExecutionTelemetryError",
    "ExecutionTelemetry",
    "FinalStateObservation",
    "ExecutionReceipt",
    "plan_execution_receipt",
    "plan_pre_mutation_refusal",
    "single_file_pre_mutation_refusal",
    "single_file_execution_receipt",
    "no_execution",
    "authorized_execution",
    "observe_named_paths",
    "final_state_observation",
    "describe_execution_telemetry",
    "execution_telemetry_guardrails",
    "attach_execution_telemetry",
]
