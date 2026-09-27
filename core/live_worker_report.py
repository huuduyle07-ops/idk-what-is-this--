"""CHECK.LIVE.1 — typed WorkerReport producer for the live apply path.

The point of this module is what it refuses to do.  The project already has a
prose-heuristic note reader (``core.worker_result_review``) and a regex
note-vs-diff check (``core.mirror_tunnel_claim_diff_check``); neither is used
here and neither may be.  A CHECK.1 ``WorkerReport`` is built **only** from
structure the runtime already holds:

* an independently supplied typed worker declaration, when one exists; or
* the typed patch-plan operations, apply outcome, and validation action used by
  CHECK.LIVE.1's explicitly measured legacy fallback.

Nothing is extracted from a completion note, a diff body, a validation log, a
model response, or any other free text.  There is no ``re`` import here, no
string search over report prose, and the boundary suite asserts both.  Where a
fact exists only in prose today it is recorded as
``typed_worker_fact_unavailable`` and left unrepresented.

Existing completion prose is untouched: the typed report is purely additive and
renders nothing to the user.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from core.live_change_observation import canonical_relative_path
from core.live_worker_declaration import (
    CHANGE_KIND_UNAVAILABLE_CLAIM,
    WorkerChangeDeclaration,
)
from core.post_run_reconciliation import (
    CHANGE_ADDED,
    CHANGE_MODIFIED,
    DECLARED_VALIDATION_FAILED,
    DECLARED_VALIDATION_NOT_RUN,
    DECLARED_VALIDATION_PASSED,
    MAX_DECLARED_CHANGES,
    WORKER_CLAIM_BLOCKED,
    WORKER_CLAIM_FAILED,
    WORKER_CLAIM_SUCCESS,
    DeclaredChange,
    DeclaredValidationAction,
    WorkerReport,
    worker_report_fingerprint,
)


PHASE_ID = "CHECK.LIVE.1"
PRODUCER_KIND = "live_worker_report"

REPORT_ID_PREFIX = "live-report"

#: Marker for a fact that exists in the run today only as prose.  CHECK.LIVE.1
#: records the absence rather than mining the text for it.
TYPED_WORKER_FACT_UNAVAILABLE = "typed_worker_fact_unavailable"

#: The only structural op-to-change-kind translation this producer performs.
#: It is a table, not an inference: an op type the apply engine does not define
#: yields no declared change at all.
PLAN_OP_CHANGE_KINDS: dict[str, str] = {
    "create_file": CHANGE_ADDED,
    "replace_snippet": CHANGE_MODIFIED,
}


class LiveWorkerReportInputError(ValueError):
    """Raised when the supplied structural facts cannot form a report."""


def declared_changes_from_patch_plan(
    plan: Sequence[Mapping[str, Any]],
) -> tuple[tuple[DeclaredChange, ...], tuple[str, ...]]:
    """Translate typed patch-plan ops into typed declared changes.

    Returns ``(declared_changes, untranslated_op_types)``.  The second element
    is how an op the table does not cover stays visible instead of being
    guessed at.
    """
    if isinstance(plan, (str, bytes)) or not isinstance(plan, Sequence):
        raise LiveWorkerReportInputError("patch plan must be a sequence of ops")

    declared: dict[str, str] = {}
    untranslated: set[str] = set()
    for op in plan:
        if not isinstance(op, Mapping):
            untranslated.add(TYPED_WORKER_FACT_UNAVAILABLE)
            continue
        op_type = str(op.get("op") or "").strip()
        change_kind = PLAN_OP_CHANGE_KINDS.get(op_type)
        path = canonical_relative_path(
            op.get("relative_path") or op.get("file") or ""
        )
        if not path:
            untranslated.add(TYPED_WORKER_FACT_UNAVAILABLE)
            continue
        if change_kind is None:
            untranslated.add(op_type or TYPED_WORKER_FACT_UNAVAILABLE)
            continue
        # The last op on a path wins: a plan that creates then edits a file
        # declares one change to that path, and CHECK.1 forbids duplicates.
        declared[path] = change_kind

    if len(declared) > MAX_DECLARED_CHANGES:
        raise LiveWorkerReportInputError(
            "declared changes exceed their finite bound"
        )

    records = tuple(
        DeclaredChange(path=path, change_kind=kind)
        for path, kind in sorted(declared.items())
    )
    return records, tuple(sorted(untranslated))


def declared_changes_from_worker_declaration(
    declaration: WorkerChangeDeclaration,
) -> tuple[tuple[DeclaredChange, ...], tuple[str, ...]]:
    """Translate independent typed claims into CHECK.1 declared changes.

    A worker that explicitly reports an unavailable kind contributes no guessed
    change record.  Its path remains visible in the same untranslated bucket the
    legacy plan translator already exposes.
    """
    if type(declaration) is not WorkerChangeDeclaration:
        raise LiveWorkerReportInputError(
            "worker declaration must be an exact WorkerChangeDeclaration"
        )

    declared: list[DeclaredChange] = []
    untranslated: list[str] = []
    for claim in declaration.declared_changes:
        if claim.change_kind == CHANGE_KIND_UNAVAILABLE_CLAIM:
            untranslated.append(claim.path)
            continue
        declared.append(
            DeclaredChange(
                path=claim.path,
                change_kind=claim.change_kind,
                from_path=claim.from_path,
            )
        )
    return tuple(sorted(declared, key=lambda item: item.path)), tuple(
        sorted(untranslated)
    )


def declared_status_from_worker_declaration(
    declaration: WorkerChangeDeclaration,
) -> str:
    """Return the status the independent worker declaration actually states."""
    if type(declaration) is not WorkerChangeDeclaration:
        raise LiveWorkerReportInputError(
            "worker declaration must be an exact WorkerChangeDeclaration"
        )
    return declaration.declared_status


def declared_validation_actions_from_worker_declaration(
    declaration: WorkerChangeDeclaration,
) -> tuple[DeclaredValidationAction, ...]:
    """Return the declaration's already-typed validation claims unchanged."""
    if type(declaration) is not WorkerChangeDeclaration:
        raise LiveWorkerReportInputError(
            "worker declaration must be an exact WorkerChangeDeclaration"
        )
    return declaration.declared_validation_actions


def declared_status_from_apply_outcome(
    *,
    apply_succeeded: bool,
    rollback_performed: bool,
    blocked: bool,
) -> str:
    """Derive the worker's status claim from typed outcome booleans only."""
    if blocked:
        return WORKER_CLAIM_BLOCKED
    if apply_succeeded and not rollback_performed:
        return WORKER_CLAIM_SUCCESS
    return WORKER_CLAIM_FAILED


def declared_validation_action(
    *,
    validation_id: str | None,
    validation_kind: str,
    executed: bool,
    passed: bool | None,
    inconclusive: bool = False,
) -> DeclaredValidationAction | None:
    """Build the one typed validation action the runner itself performed.

    ``executed=False`` produces no action at all: a validation that never ran
    is not a claim that it failed.  ``inconclusive`` (OPS.VALIDATE.1) is the
    same refusal one step in: a command that ran but evaluated no check has no
    result to declare, so it declares ``not_run`` rather than asserting a
    failure the runner never observed.  Only a ``passed`` claim is ever
    cross-checked against a receipt, so this narrows what is claimed without
    loosening any reconciliation.
    """
    if not executed:
        return None
    if inconclusive:
        result = DECLARED_VALIDATION_NOT_RUN
    elif passed is True:
        result = DECLARED_VALIDATION_PASSED
    elif passed is False:
        result = DECLARED_VALIDATION_FAILED
    else:
        result = DECLARED_VALIDATION_NOT_RUN
    return DeclaredValidationAction(
        validation_kind=validation_kind,
        declared_result=result,
        validation_id=validation_id,
    )


def live_report_id(
    *,
    execution_run_id: str,
    declared_status: str,
) -> str:
    """A bounded report identity derived from the run, never from a clock."""
    run = "".join(
        character
        for character in str(execution_run_id)
        if character.isalnum() or character in {"_", "-"}
    )[:96]
    return f"{REPORT_ID_PREFIX}-{run or 'unknown'}-{declared_status}"


def build_live_worker_report(
    *,
    execution_run_id: str,
    declared_status: str,
    declared_changes: Sequence[DeclaredChange] = (),
    declared_validation_actions: Sequence[DeclaredValidationAction] = (),
    declared_limitations: Sequence[str] = (),
    declared_unresolved_items: Sequence[str] = (),
    worker_id: str | None = None,
) -> WorkerReport:
    """Assemble one typed WorkerReport from already-structural facts."""
    return WorkerReport(
        report_id=live_report_id(
            execution_run_id=execution_run_id,
            declared_status=declared_status,
        ),
        execution_run_id=execution_run_id,
        declared_status=declared_status,
        declared_changes=tuple(declared_changes),
        declared_validation_actions=tuple(declared_validation_actions),
        declared_limitations=tuple(declared_limitations),
        declared_unresolved_items=tuple(declared_unresolved_items),
        worker_id=worker_id,
    )


def live_worker_report_fingerprint(report: WorkerReport) -> str:
    """Re-expose the frozen fingerprint so callers need no second import."""
    return worker_report_fingerprint(report)


def live_worker_report_guardrails() -> dict[str, bool]:
    """Every power the worker-report producer declines to exercise."""
    return {
        "built_from_structural_facts_only": True,
        "prose_parsed": False,
        "completion_note_read": False,
        "diff_parsed": False,
        "validation_log_parsed": False,
        "regular_expression_used": False,
        "model_called": False,
        "existing_prose_output_changed": False,
        "repository_traversed": False,
        "source_content_read": False,
        "validation_executed": False,
        "patch_applied": False,
        "files_modified": False,
        "network_call_performed": False,
        "authoritative_effect": False,
        "human_approval_required": True,
    }


__all__ = [
    "PHASE_ID",
    "PRODUCER_KIND",
    "REPORT_ID_PREFIX",
    "TYPED_WORKER_FACT_UNAVAILABLE",
    "PLAN_OP_CHANGE_KINDS",
    "LiveWorkerReportInputError",
    "declared_changes_from_patch_plan",
    "declared_changes_from_worker_declaration",
    "declared_status_from_worker_declaration",
    "declared_validation_actions_from_worker_declaration",
    "declared_status_from_apply_outcome",
    "declared_validation_action",
    "live_report_id",
    "build_live_worker_report",
    "live_worker_report_fingerprint",
    "live_worker_report_guardrails",
]
