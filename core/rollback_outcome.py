"""DATA.ROLLBACK.1: immutable, verified rollback truth.

The contract answers what happened after a mutation failed.  It carries no
authority and deliberately does not infer success from an exception, an
operation count, or the fact that a restore function returned.  Current-run
serializers must render the compatibility booleans from this object.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping


ROLLBACK_OUTCOME_SCHEMA_VERSION = "data_rollback_1_outcome_v1"
ROLLBACK_PROTECTION_SEMANTICS_CAPABILITY_ONLY = "capability_only"

ROLLBACK_NOT_REQUIRED = "not_required"
ROLLBACK_NOT_ATTEMPTED = "not_attempted"
ROLLBACK_COMPLETED_VERIFIED = "completed_verified"
ROLLBACK_INCOMPLETE = "incomplete"
ROLLBACK_UNVERIFIABLE = "unverifiable"

ROLLBACK_STATUSES: tuple[str, ...] = (
    ROLLBACK_NOT_REQUIRED,
    ROLLBACK_NOT_ATTEMPTED,
    ROLLBACK_COMPLETED_VERIFIED,
    ROLLBACK_INCOMPLETE,
    ROLLBACK_UNVERIFIABLE,
)


class RollbackOutcomeError(ValueError):
    """Raised when rollback facts contradict their closed status."""


def _paths(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(sorted({str(value) for value in values if str(value)}))


def _carries_measured_recovery_failure(value: Mapping[str, Any]) -> bool:
    """Transaction facts in the same receipt that measured unresolved state."""

    return value.get("recovery_complete") is False or any(
        value.get(name) not in (None, [], ())
        for name in ("remaining_changed_paths", "remaining_created_directories")
    )


@dataclass(frozen=True, slots=True)
class RollbackOutcome:
    """One authoritative account of rollback and final scoped state.

    ``verified`` means the rollback result was independently inspected.
    ``completed`` is stronger: it is valid only when that inspection proved
    every baseline restored.  ``final_state_verified`` describes whether the
    final changed/unchanged answer itself was observable; an unverifiable state
    fails closed to ``final_repository_changed=True``.
    """

    status: str
    attempted: bool
    completed: bool
    verified: bool
    remaining_changed_paths: tuple[str, ...] = ()
    remaining_created_directories: tuple[str, ...] = ()
    failure_code: str = ""
    failure_reason: str = ""
    recovery_artifact_ids: tuple[str, ...] = ()
    recovery_material_available: bool = False
    recovery_material_error: str = ""
    final_repository_changed: bool = False
    final_state_verified: bool = True

    def __post_init__(self) -> None:
        if self.status not in ROLLBACK_STATUSES:
            raise RollbackOutcomeError(f"unknown rollback status: {self.status!r}")
        bool_fields = (
            "attempted",
            "completed",
            "verified",
            "recovery_material_available",
            "final_repository_changed",
            "final_state_verified",
        )
        if any(type(getattr(self, name)) is not bool for name in bool_fields):
            raise RollbackOutcomeError("rollback truth fields must be booleans")
        tuple_fields = (
            "remaining_changed_paths",
            "remaining_created_directories",
            "recovery_artifact_ids",
        )
        if any(not isinstance(getattr(self, name), tuple) for name in tuple_fields):
            raise RollbackOutcomeError("rollback path and artifact collections must be tuples")
        if any(
            type(value) is not str or not value
            for name in tuple_fields for value in getattr(self, name)
        ):
            raise RollbackOutcomeError("rollback collections require non-empty strings")
        if self.recovery_material_available != bool(self.recovery_artifact_ids):
            raise RollbackOutcomeError(
                "recovery_material_available must agree with recovery_artifact_ids"
            )

        remaining = bool(
            self.remaining_changed_paths or self.remaining_created_directories
        )
        if remaining and not self.final_repository_changed:
            raise RollbackOutcomeError(
                "unresolved rollback state requires a final repository change"
            )
        if self.completed and not (self.attempted and self.verified):
            raise RollbackOutcomeError(
                "completed rollback requires an attempt and independent verification"
            )
        if self.completed and remaining:
            raise RollbackOutcomeError(
                "completed rollback cannot carry unresolved paths"
            )
        if self.completed and self.final_repository_changed:
            raise RollbackOutcomeError(
                "completed rollback cannot leave a scoped repository change"
            )
        if self.verified and not self.final_state_verified:
            raise RollbackOutcomeError(
                "verified rollback requires a verified final state"
            )

        expected = {
            ROLLBACK_NOT_REQUIRED: (False, False, False),
            ROLLBACK_NOT_ATTEMPTED: (False, False, False),
            ROLLBACK_COMPLETED_VERIFIED: (True, True, True),
            ROLLBACK_INCOMPLETE: (True, False, True),
        }.get(self.status)
        if expected is not None and (
            self.attempted, self.completed, self.verified
        ) != expected:
            raise RollbackOutcomeError(
                f"rollback facts contradict status={self.status}"
            )
        if self.status == ROLLBACK_UNVERIFIABLE and (
            self.completed or self.verified
        ):
            raise RollbackOutcomeError(
                "unverifiable rollback cannot be completed or verified"
            )
        if self.status == ROLLBACK_COMPLETED_VERIFIED and (
            not self.final_state_verified or self.failure_code or self.failure_reason
        ):
            raise RollbackOutcomeError(
                "verified completion cannot carry failure or unverified final state"
            )
        if self.status == ROLLBACK_NOT_REQUIRED and (
            self.failure_code or self.failure_reason
        ):
            raise RollbackOutcomeError(
                "not-required rollback cannot carry a rollback failure"
            )
        if self.status in {
            ROLLBACK_NOT_ATTEMPTED,
            ROLLBACK_INCOMPLETE,
            ROLLBACK_UNVERIFIABLE,
        } and (not self.failure_code or not self.failure_reason):
            raise RollbackOutcomeError(
                "non-success rollback outcomes require a failure code and reason"
            )
        if self.status == ROLLBACK_INCOMPLETE and (
            not remaining or not self.final_repository_changed
        ):
            raise RollbackOutcomeError(
                "incomplete rollback requires exact unresolved state"
            )
        if self.status == ROLLBACK_UNVERIFIABLE and (
            self.final_state_verified or not self.final_repository_changed
            or not self.failure_code
        ):
            raise RollbackOutcomeError(
                "unverifiable rollback must fail closed with a failure code"
            )
        if self.status == ROLLBACK_NOT_REQUIRED and remaining:
            raise RollbackOutcomeError(
                "not-required rollback cannot carry unresolved rollback paths"
            )

    @property
    def performed(self) -> bool:
        """Backward-compatible success, true only for verified completion."""

        return self.status == ROLLBACK_COMPLETED_VERIFIED

    def with_recovery_material(
        self,
        artifact_ids: tuple[str, ...] | list[str],
        *,
        error: str = "",
    ) -> "RollbackOutcome":
        ids = _paths(artifact_ids)
        return replace(
            self,
            recovery_artifact_ids=ids,
            recovery_material_available=bool(ids),
            recovery_material_error=str(error or ""),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ROLLBACK_OUTCOME_SCHEMA_VERSION,
            "status": self.status,
            "attempted": self.attempted,
            "completed": self.completed,
            "verified": self.verified,
            "performed": self.performed,
            "remaining_changed_paths": list(self.remaining_changed_paths),
            "remaining_created_directories": list(
                self.remaining_created_directories
            ),
            "failure": {
                "code": self.failure_code,
                "reason": self.failure_reason,
            },
            "recovery_artifact_ids": list(self.recovery_artifact_ids),
            "recovery_material_available": self.recovery_material_available,
            "recovery_material_error": self.recovery_material_error,
            "final_repository_changed": self.final_repository_changed,
            "final_state_verified": self.final_state_verified,
            "authority_effect": "none",
        }

    def as_payload_fields(self) -> dict[str, Any]:
        """Render every compatibility field from this one outcome."""

        failure = {
            "code": self.failure_code,
            "reason": self.failure_reason,
        }
        return {
            "rollback_outcome_schema_version": ROLLBACK_OUTCOME_SCHEMA_VERSION,
            "rollback_outcome": self.as_dict(),
            "rollback_status": self.status,
            "rollback_attempted": self.attempted,
            "rollback_completed": self.completed,
            "rollback_verified": self.verified,
            "rollback_performed": self.performed,
            "remaining_changed_paths": list(self.remaining_changed_paths),
            "remaining_created_directories": list(
                self.remaining_created_directories
            ),
            "rollback_failure": failure,
            "recovery_artifact_ids": list(self.recovery_artifact_ids),
            "recovery_material_available": self.recovery_material_available,
            "recovery_material_error": self.recovery_material_error,
            "final_repository_changed": self.final_repository_changed,
            "final_state_verified": self.final_state_verified,
        }


def rollback_not_required(
    *, final_repository_changed: bool = False, final_state_verified: bool = True
) -> RollbackOutcome:
    return RollbackOutcome(
        status=ROLLBACK_NOT_REQUIRED,
        attempted=False,
        completed=False,
        verified=False,
        final_repository_changed=bool(final_repository_changed),
        final_state_verified=bool(final_state_verified),
    )


def rollback_not_attempted(
    remaining_changed_paths: tuple[str, ...] | list[str] = (),
    remaining_created_directories: tuple[str, ...] | list[str] = (),
    *,
    failure_code: str = "rollback_not_attempted",
    failure_reason: str = "Rollback was required but not attempted.",
) -> RollbackOutcome:
    paths = _paths(remaining_changed_paths)
    directories = _paths(remaining_created_directories)
    return RollbackOutcome(
        status=ROLLBACK_NOT_ATTEMPTED,
        attempted=False,
        completed=False,
        verified=False,
        remaining_changed_paths=paths,
        remaining_created_directories=directories,
        failure_code=failure_code,
        failure_reason=failure_reason,
        final_repository_changed=bool(paths or directories),
        final_state_verified=True,
    )


def rollback_completed_verified() -> RollbackOutcome:
    return RollbackOutcome(
        status=ROLLBACK_COMPLETED_VERIFIED,
        attempted=True,
        completed=True,
        verified=True,
        final_repository_changed=False,
        final_state_verified=True,
    )


def rollback_incomplete(
    remaining_changed_paths: tuple[str, ...] | list[str] = (),
    remaining_created_directories: tuple[str, ...] | list[str] = (),
    *,
    failure_code: str = "rollback_incomplete",
    failure_reason: str = "Rollback completed with unresolved repository state.",
) -> RollbackOutcome:
    paths = _paths(remaining_changed_paths)
    directories = _paths(remaining_created_directories)
    if not paths and not directories:
        raise RollbackOutcomeError(
            "incomplete rollback requires an unresolved path or directory"
        )
    return RollbackOutcome(
        status=ROLLBACK_INCOMPLETE,
        attempted=True,
        completed=False,
        verified=True,
        remaining_changed_paths=paths,
        remaining_created_directories=directories,
        failure_code=failure_code,
        failure_reason=failure_reason,
        final_repository_changed=True,
        final_state_verified=True,
    )


def rollback_unverifiable(
    unresolved_paths: tuple[str, ...] | list[str] = (),
    remaining_created_directories: tuple[str, ...] | list[str] = (),
    *,
    attempted: bool = True,
    failure_code: str = "rollback_state_unverifiable",
    failure_reason: str = "Final repository state could not be verified.",
) -> RollbackOutcome:
    return RollbackOutcome(
        status=ROLLBACK_UNVERIFIABLE,
        attempted=bool(attempted),
        completed=False,
        verified=False,
        remaining_changed_paths=_paths(unresolved_paths),
        remaining_created_directories=_paths(remaining_created_directories),
        failure_code=failure_code,
        failure_reason=failure_reason,
        final_repository_changed=True,
        final_state_verified=False,
    )


def rollback_outcome_from_plan(result: Mapping[str, Any]) -> RollbackOutcome:
    """Translate frozen EXEC.PLAN.1 transaction facts without re-inferring them."""

    for name in ("mutation_attempted", "recovery_attempted"):
        if name in result and type(result[name]) is not bool:
            raise RollbackOutcomeError("transaction attempt facts must be booleans")
    for name in ("remaining_changed_paths", "remaining_created_directories"):
        if name in result and (
            not isinstance(result[name], (list, tuple))
            or any(type(item) is not str or not item for item in result[name])
        ):
            raise RollbackOutcomeError("transaction remaining state must be explicit paths")
    if result.get("recovery_complete") is True and (
        result.get("mutation_attempted") is not True
        or result.get("recovery_attempted") is not True
        or any(name not in result for name in (
            "remaining_changed_paths", "remaining_created_directories",
        ))
    ):
        raise RollbackOutcomeError("transaction recovery success requires complete evidence")
    mutation_attempted = result.get("mutation_attempted") is True
    attempted = result.get("recovery_attempted") is True
    remaining = _paths(result.get("remaining_changed_paths"))
    remaining_dirs = _paths(result.get("remaining_created_directories"))
    if not mutation_attempted:
        if attempted or remaining or remaining_dirs:
            raise RollbackOutcomeError("transaction facts contradict no mutation")
        return rollback_not_required()
    if not attempted:
        if result.get("success") is True:
            return rollback_not_required(
                final_repository_changed=bool(
                    result.get("final_repository_changed", True)
                ),
                final_state_verified=bool(result.get("final_state_verified", False)),
            )
        return rollback_not_attempted(remaining, remaining_dirs)
    if result.get("recovery_complete") is True and not remaining and not remaining_dirs:
        return rollback_completed_verified()
    return rollback_incomplete(
        remaining,
        remaining_dirs,
        failure_code=str(result.get("code") or "rollback_incomplete"),
        failure_reason=str(
            result.get("message")
            or "Transaction recovery left unresolved repository state."
        ),
    )


def rollback_outcome_from_mapping(value: Mapping[str, Any] | None) -> RollbackOutcome:
    """Load current receipts and fail closed for legacy/missing success proof."""

    if not isinstance(value, Mapping):
        # No receipt is no observation: never report a verified final state.
        return rollback_not_required(final_state_verified=False)
    raw = value.get("rollback_outcome")
    if isinstance(raw, Mapping) and raw.get("schema_version") == ROLLBACK_OUTCOME_SCHEMA_VERSION:
        failure = raw.get("failure") if isinstance(raw.get("failure"), Mapping) else {}
        try:
            for name in (
                "remaining_changed_paths", "remaining_created_directories",
                "recovery_artifact_ids",
            ):
                collection = raw.get(name, ())
                if not isinstance(collection, (list, tuple)) or any(
                    type(item) is not str or not item for item in collection
                ):
                    raise RollbackOutcomeError("invalid serialized rollback collection")
            if raw.get("status") == ROLLBACK_COMPLETED_VERIFIED and any(
                name not in raw for name in (
                    "attempted", "completed", "verified", "remaining_changed_paths",
                    "remaining_created_directories", "final_repository_changed",
                    "final_state_verified",
                )
            ):
                raise RollbackOutcomeError("verified success requires complete evidence")
            outcome = RollbackOutcome(
                status=str(raw.get("status") or ""),
                attempted=raw.get("attempted", False),
                completed=raw.get("completed", False),
                verified=raw.get("verified", False),
                remaining_changed_paths=_paths(raw.get("remaining_changed_paths")),
                remaining_created_directories=_paths(
                    raw.get("remaining_created_directories")
                ),
                failure_code=str(failure.get("code") or ""),
                failure_reason=str(failure.get("reason") or ""),
                recovery_artifact_ids=_paths(raw.get("recovery_artifact_ids")),
                recovery_material_available=raw.get("recovery_material_available", False),
                recovery_material_error=str(raw.get("recovery_material_error") or ""),
                final_repository_changed=raw.get("final_repository_changed", False),
                final_state_verified=raw.get("final_state_verified", False),
            )
            if outcome.performed and _carries_measured_recovery_failure(value):
                # A typed success never outranks measured unresolved state
                # recorded beside it; conflicting evidence proves nothing.
                return rollback_unverifiable(
                    _paths(value.get("remaining_changed_paths")),
                    _paths(value.get("remaining_created_directories")),
                    failure_code="conflicting_rollback_evidence",
                    failure_reason=(
                        "Typed rollback success contradicts measured recovery facts."
                    ),
                )
            return outcome
        except RollbackOutcomeError:
            return rollback_unverifiable(
                _paths(raw.get("remaining_changed_paths")),
                _paths(raw.get("remaining_created_directories")),
                attempted=raw.get("attempted") is True,
                failure_code="invalid_rollback_evidence",
                failure_reason="Current rollback evidence is inconsistent or incomplete.",
            )
    elif "rollback_outcome" in value:
        return rollback_unverifiable(
            _paths(value.get("remaining_changed_paths")),
            _paths(value.get("remaining_created_directories")),
            attempted=value.get("rollback_attempted") is True,
            failure_code="unsupported_rollback_evidence",
            failure_reason="Rollback evidence has no supported typed schema.",
        )
    if value.get("recovery_attempted") is not None or value.get("mutation_attempted") is not None:
        try:
            return rollback_outcome_from_plan(value)
        except RollbackOutcomeError:
            return rollback_unverifiable(
                _paths(value.get("remaining_changed_paths")),
                _paths(value.get("remaining_created_directories")),
                attempted=value.get("recovery_attempted") is True,
                failure_code="invalid_transaction_recovery_evidence",
                failure_reason="Transaction recovery facts do not establish a final state.",
            )
    # A historical true boolean proves only that old code claimed success.  It
    # cannot be upgraded into independently verified success under this schema.
    if value.get("rollback_performed") is True:
        return rollback_unverifiable(
            _paths(value.get("remaining_changed_paths")),
            failure_code="legacy_rollback_unverified",
            failure_reason="Historical rollback metadata has no verification evidence.",
        )
    if value.get("rollback_attempted") is True:
        return rollback_unverifiable(
            _paths(value.get("remaining_changed_paths")),
            failure_code="rollback_attempt_without_verification",
            failure_reason="A rollback attempt has no independently verified outcome.",
        )
    return rollback_not_required(
        final_repository_changed=value.get("final_repository_changed") is True,
        final_state_verified=False,
    )


def rollback_disqualifies_success_evidence(
    value: Mapping[str, Any] | None,
) -> bool:
    """Conservatively classify rollback metadata used by lesson eligibility.

    This is deliberately broader than :attr:`RollbackOutcome.performed`.
    ``performed`` is verified-success truth; eligibility must also reject an
    incomplete, unverifiable, or not-attempted recovery and must preserve an
    old receipt's historical ``rollback_performed=true`` as a review blocker.
    """

    if not isinstance(value, Mapping):
        return False
    return rollback_outcome_from_mapping(value).status != ROLLBACK_NOT_REQUIRED


# Presentation derived from one outcome.  These sentences are rendered from a
# RollbackOutcome so every current surface words the same measured facts the
# same way; they are not part of the truth object and add no fact of their own.


def recovery_material_notice(outcome: RollbackOutcome) -> str:
    """Describe failed-rollback material without overstating its coverage."""

    if outcome.status not in {ROLLBACK_INCOMPLETE, ROLLBACK_UNVERIFIABLE}:
        return ""
    if outcome.recovery_material_available and not outcome.recovery_material_error:
        return "Emergency recovery material is available."
    if outcome.recovery_material_available:
        return (
            "Emergency recovery material is only partially available; some "
            "unresolved targets have no retained baseline."
        )
    if outcome.recovery_material_error:
        return "Emergency recovery material could not be fully persisted."
    return "Emergency recovery material is not recorded."


def rollback_failure_notice(
    outcome: RollbackOutcome,
    *,
    scope: str = "repository",
    include_material: bool = True,
) -> str:
    """Name an unsuccessful rollback, its unresolved paths and its material."""

    if outcome.performed or outcome.status == ROLLBACK_NOT_REQUIRED:
        return ""
    if outcome.status == ROLLBACK_NOT_ATTEMPTED:
        message = f"Rollback was not attempted; the {scope} may still contain changes."
    else:
        message = (
            f"Rollback failed or is incomplete; the {scope} may still contain changes."
        )
    unresolved = outcome.remaining_changed_paths + outcome.remaining_created_directories
    if unresolved:
        message += " Unresolved paths: " + ", ".join(unresolved) + "."
    material = recovery_material_notice(outcome) if include_material else ""
    return f"{message} {material}" if material else message


def attach_rollback_outcome(
    result: Mapping[str, Any], outcome: RollbackOutcome
) -> dict[str, Any]:
    """Outcome fields win over legacy/default fields by construction."""

    return {**dict(result), **outcome.as_payload_fields()}


def disposable_clone_rollback_fields(value: Mapping[str, Any]) -> dict[str, Any]:
    """Project clone-scoped truth without advertising discarded recovery files."""

    outcome = rollback_outcome_from_mapping(value)
    had_material = bool(
        outcome.recovery_artifact_ids or outcome.recovery_material_available
    )
    outcome = replace(
        outcome,
        recovery_artifact_ids=(),
        recovery_material_available=False,
        recovery_material_error=(
            "disposable_clone_removed" if had_material
            else outcome.recovery_material_error
        ),
    )
    return {
        **outcome.as_payload_fields(),
        "rollback_scope": "disposable_clone",
        "final_repository_state_scope": "disposable_clone",
        "real_repository_changed": False,
        "recovery_material_scope": "disposable_clone",
        "recovery_source_execution_id": "",
        "recovery_material_note": (
            "Validation ran in a disposable clone. Its recovery artifacts are "
            "discarded on cleanup; no recovery material is retained for the real repository."
        ),
    }


__all__ = [
    "ROLLBACK_OUTCOME_SCHEMA_VERSION",
    "ROLLBACK_PROTECTION_SEMANTICS_CAPABILITY_ONLY",
    "ROLLBACK_NOT_REQUIRED",
    "ROLLBACK_NOT_ATTEMPTED",
    "ROLLBACK_COMPLETED_VERIFIED",
    "ROLLBACK_INCOMPLETE",
    "ROLLBACK_UNVERIFIABLE",
    "ROLLBACK_STATUSES",
    "RollbackOutcomeError",
    "RollbackOutcome",
    "rollback_not_required",
    "rollback_not_attempted",
    "rollback_completed_verified",
    "rollback_incomplete",
    "rollback_unverifiable",
    "rollback_outcome_from_plan",
    "rollback_outcome_from_mapping",
    "rollback_disqualifies_success_evidence",
    "recovery_material_notice",
    "rollback_failure_notice",
    "attach_rollback_outcome",
    "disposable_clone_rollback_fields",
]
