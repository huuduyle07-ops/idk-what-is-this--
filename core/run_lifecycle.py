from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.brain_stamp import collect_brain_stamp
from core.patch_safety import evaluate_patch_safety
from core.pre_execution_change_intent import (
    INTENT_ARTIFACT_NAME,
    PreExecutionIntentCapture,
    is_pre_execution_change_intent_enabled,
    worker_change_declaration_from_intent_capture,
)
from core.post_run_reconciliation_shadow import (
    LiveExecutionObservation,
    RUN_STATUS_BLOCKED,
    RUN_STATUS_FAILED,
    RUN_STATUS_SUCCESS,
    is_post_run_reconciliation_shadow_enabled,
    not_reached_receipt,
    persist_shadow_post_run_check,
    safe_run_shadow_post_run_reconciliation,
)
from core.rollback_outcome import (
    ROLLBACK_INCOMPLETE,
    ROLLBACK_UNVERIFIABLE,
    rollback_outcome_from_mapping,
)
from core.validation_execution import SafeValidationCommand
from core.validation_side_effects import with_atomicity_metadata
from core.worker_patch_envelope import (
    ENVELOPE_ARTIFACT_NAME,
    WorkerPatchResponseCompatibility,
    is_strict_worker_patch_envelope_shadow_enabled,
)
from core.strict_envelope_emission import (
    EMISSION_ARTIFACT_NAME,
    StrictEnvelopeEmissionObservation,
    is_strict_envelope_emission_enabled,
)
from core.replay_recorder import (
    create_replay_bundle,
    finalize_replay_bundle,
    write_replay_artifact,
    write_replay_json,
)
from patching.patch_plan_executor import apply_patch_plan


def _patch_plan_files(plan: list[dict]) -> list[str]:
    """Return target paths from patch-plan ops for the shared safety gate."""
    return [
        (op.get("relative_path") or op.get("file") or "")
        for op in plan
        if isinstance(op, dict)
    ]


def _shadow_pre_apply_digests(project_root: str, plan: Any) -> Any:
    """Digest the paths this plan already names, before anything is written.

    Bounded and non-traversing: only the plan's own targets are read, and only
    when the default-off shadow observer is enabled.  Any failure yields
    ``None``, which the shadow receipt later reports as an unavailable
    observation rather than a fabricated one.
    """
    try:
        from core.live_change_observation import digest_known_paths

        return digest_known_paths(project_root, _patch_plan_files(plan or []))
    except Exception:  # noqa: BLE001 - observation failure is isolated
        return None


def _shadow_validation_facts(result: dict[str, Any]) -> dict[str, Any]:
    """Read the validation outcome the apply path already recorded.

    Every value here comes from a typed field the apply engine set for its own
    purposes.  Nothing is executed, re-run, or read out of the validation log:
    a crash is recognised structurally, by the absence of the classifier
    category the engine attaches to a genuine validation failure.
    """
    validation_ok = result.get("validation_ok")
    mode = str(result.get("validation_mode") or "")
    blocked = (
        bool(result.get("unsafe_validation_blocked"))
        or bool(result.get("safe_validation_blocked"))
        or mode == "blocked_unsafe_legacy_shell"
    )
    failed_op = result.get("failed_op")
    crashed = (
        isinstance(failed_op, dict)
        and failed_op.get("op") == "validation"
        and "category" not in failed_op
    )
    # OPS.VALIDATE.1 - the apply path now records which of the two non-passing
    # outcomes it saw.  This reads that typed field; it never re-classifies
    # output or re-runs anything to decide.
    from core.validation_outcome import VALIDATION_INCONCLUSIVE

    # OPS.VALIDATE.2 - the apply path records whether it stopped its own
    # command at the budget.  That is read here as a typed field and projected
    # additively: the receipt result becomes CHECK.1's existing ``timed_out``
    # rather than a bare ``errored``, and ``validation_inconclusive`` stays true
    # alongside it so the worker's declared action remains ``not_run``.  Neither
    # value is new vocabulary and CHECK.1 is not redesigned.
    timed_out = bool(result.get("validation_timed_out")) and not blocked

    return {
        "validation_executed": validation_ok is not None and not blocked,
        "validation_passed": (
            bool(validation_ok) if validation_ok is not None else None
        ),
        "validation_blocked": blocked,
        "validation_crashed": bool(crashed),
        "validation_timed_out": timed_out,
        "validation_inconclusive": (
            result.get("validation_outcome") == VALIDATION_INCONCLUSIVE
            and not blocked
            and not crashed
        ),
    }


def _worker_patch_envelope_record(record: Any) -> dict[str, Any] | None:
    """Render an already-measured strict/legacy compatibility record.

    WORKER.DECL.2A measurement happens where the worker response actually
    exists, upstream of this module.  Nothing is parsed, re-parsed or decided
    here: the record either arrived as a typed value or it did not.  It is
    bounded identity metadata only — no snippet, no file body, no raw response.
    """
    if isinstance(record, WorkerPatchResponseCompatibility):
        return record.as_dict()
    return None


def _strict_envelope_emission_record(record: Any) -> dict[str, Any] | None:
    """Render an already-made emission observation, or nothing.

    WORKER.DECL.2A.1 decides the transport where the model call actually
    happens, upstream of this module.  Nothing is requested, re-requested or
    decided here: the observation either arrived as a typed value or it did
    not, and a raw mapping is never laundered into one.
    """
    if isinstance(record, StrictEnvelopeEmissionObservation):
        return record.as_dict()
    return None


def _attach_shadow_post_run_reconciliation(
    *,
    result: dict[str, Any],
    bundle: Any,
    project_root: str,
    plan: Any,
    patch_safety: dict[str, Any],
    pre_apply_digests: Any,
    validation_requested: bool,
    worker_declaration: Any,
    pre_execution_intent: Any,
    intent_plan_agreement: str,
    append_event: Any,
) -> dict[str, Any]:
    """Observe the finished run with CHECK.1 and attach a shadow summary.

    This runs at the true terminal boundary: every patch operation, every
    rollback and the one validation have completed, and nothing after this point
    writes to the worktree.  It never changes ``result["success"]``, any
    existing key, the patch, the validation, or the run's terminal category.
    """
    validation = _shadow_validation_facts(result)
    observation = LiveExecutionObservation(
        project_root=project_root,
        execution_run_id=str(getattr(bundle, "replay_id", "") or ""),
        authoritative_run_status=(
            RUN_STATUS_SUCCESS if result.get("success") else RUN_STATUS_FAILED
        ),
        plan=tuple(op for op in (plan or []) if isinstance(op, dict)),
        patch_safety_verdict=patch_safety,
        pre_apply_digests=pre_apply_digests,
        reached_post_run_boundary=pre_apply_digests is not None,
        apply_succeeded=bool(result.get("success")),
        # DATA.ROLLBACK.1 narrowed rollback_performed to verified completion.
        # This frozen input marks a patched state that existed before the final
        # digest, so a failed or partial reversal must still set it.
        rollback_performed=rollback_outcome_from_mapping(result).attempted,
        blocked=False,
        validation_requested=bool(validation_requested),
        validation_side_effects=result.get("validation_side_effects") or {},
        worker_declaration=worker_declaration,
        pre_execution_change_intent=pre_execution_intent,
        intent_plan_agreement=intent_plan_agreement,
        **validation,
    )
    receipt = safe_run_shadow_post_run_reconciliation(observation)
    persist_shadow_post_run_check(bundle, receipt)
    append_event(
        "post_run_reconciliation_shadow",
        {
            "shadow_outcome": receipt.shadow_outcome,
            "reconciliation_status": receipt.reconciliation_status,
            "producer_completeness": receipt.producer_completeness,
            "disagreement": receipt.disagreement,
            "authoritative_effect": False,
        },
    )
    result.update(receipt.result_metadata())
    return result


def _attach_not_reached_shadow(
    *,
    result: dict[str, Any],
    bundle: Any,
    authoritative_run_status: str,
) -> dict[str, Any]:
    """Record honestly that a run ended before the post-run boundary."""
    receipt = not_reached_receipt(
        execution_run_id=str(getattr(bundle, "replay_id", "") or ""),
        repository_id="",
        authoritative_run_status=authoritative_run_status,
    )
    persist_shadow_post_run_check(bundle, receipt)
    result.update(receipt.result_metadata())
    return result


def run_patch_plan_with_artifacts(
    project_root: str,
    plan: list[dict],
    validation_command: str | None = None,
    safe_validation_command: SafeValidationCommand | None = None,
    require_safe_validation: bool = False,
    user_query: str = "",
    control_result: dict[str, Any] | None = None,
    source: str = "pipeline",
    worker_declaration: Any = None,
    worker_patch_response: Any = None,
    strict_envelope_emission: Any = None,
    pre_execution_intent_capture: Any = None,
    pre_execution_authorization: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a patch plan and persist a replay bundle around the existing executor."""
    brain_stamp = collect_brain_stamp(project_root)
    intent_enabled = is_pre_execution_change_intent_enabled()
    shadow_enabled = is_post_run_reconciliation_shadow_enabled() or intent_enabled
    shadow_pre_apply_digests = None
    bundle = None
    try:
        bundle = create_replay_bundle(
            project_root,
            run_kind=source,
            user_query=user_query or "",
        )
    except OSError:
        bundle = None
    events: list[dict[str, Any]] = []

    def safe_write_json(name: str, obj: Any) -> None:
        if bundle is None:
            return
        try:
            write_replay_json(bundle, name, obj)
        except OSError:
            pass

    def safe_write_artifact(name: str, content: str) -> None:
        if bundle is None:
            return
        try:
            write_replay_artifact(bundle, name, content)
        except OSError:
            pass

    safe_write_json("brain_stamp.json", brain_stamp or {})
    safe_write_json("control_result.json", control_result or {})
    safe_write_json("patch_parsed.json", plan)
    safe_write_json("patch_plan.json", plan)
    if isinstance(pre_execution_authorization, Mapping):
        # EXEC.APPROVAL.LIVE.1: the caller creates this immutable authorization
        # before entering the lifecycle.  Persist it before the safety chokepoint
        # and executor, never retroactively after mutation.
        safe_write_json(
            "human_apply_authorization.json",
            dict(pre_execution_authorization),
        )

    # WORKER.DECL.2B: freeze/adapt the already-parsed native intent before the
    # first objective path digest is taken.  The adapter never sees filesystem
    # facts, and an invalid/missing capture leaves the existing declaration seam
    # untouched.
    intent_capture = (
        pre_execution_intent_capture
        if type(pre_execution_intent_capture) is PreExecutionIntentCapture
        else None
    )
    effective_worker_declaration = worker_declaration
    if effective_worker_declaration is None and intent_capture is not None and bundle is not None:
        try:
            effective_worker_declaration = worker_change_declaration_from_intent_capture(
                intent_capture,
                execution_run_id=str(bundle.replay_id),
            )
        except (TypeError, ValueError):
            effective_worker_declaration = None
    if intent_enabled and intent_capture is not None:
        safe_write_json(INTENT_ARTIFACT_NAME, intent_capture.as_dict())

    if is_strict_worker_patch_envelope_shadow_enabled():
        # WORKER.DECL.2A: record how the strict one-object envelope parser and
        # the legacy extractor each read the worker response that produced this
        # plan.  Observation only — the plan below is the caller's, unchanged,
        # whatever the record says.
        envelope_record = _worker_patch_envelope_record(worker_patch_response)
        if envelope_record is not None:
            safe_write_json(ENVELOPE_ARTIFACT_NAME, envelope_record)

    if is_strict_envelope_emission_enabled():
        # WORKER.DECL.2A.1: record which transport strategy asked for the
        # response this plan came from.  Adoption telemetry beside the plan,
        # never above it — the plan below is the caller's, unchanged, whatever
        # the strict parser made of the response.
        emission_record = _strict_envelope_emission_record(strict_envelope_emission)
        if emission_record is not None:
            safe_write_json(EMISSION_ARTIFACT_NAME, emission_record)

    def with_replay_fields(result: dict[str, Any]) -> dict[str, Any]:
        result = with_atomicity_metadata(result)
        result = {
            **result,
            "brain_stamp_id": brain_stamp.get("brain_stamp_id"),
        }
        if bundle is not None:
            result["replay_dir"] = str(bundle.replay_dir)
            result["replay_id"] = bundle.replay_id
        return result

    def append_event(phase: str, payload: dict[str, Any] | None = None) -> None:
        if bundle is None:
            return
        events.append(
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source": source,
                "phase": phase,
                "payload": payload or {},
            }
        )
        safe_write_artifact(
            "events.jsonl",
            "".join(
                json.dumps(event, sort_keys=True, ensure_ascii=False, default=str) + "\n"
                for event in events
            ),
        )

    def finish(status: str, result: dict[str, Any]) -> None:
        if bundle is not None:
            try:
                finalize_replay_bundle(
                    bundle,
                    {
                        "status": status,
                        "result": result,
                    },
                )
            except OSError:
                pass

    append_event(
        "started",
        {
            "validation_command": validation_command or "",
            "validation_mode": "safe_argv" if safe_validation_command else (
                "safe_required" if require_safe_validation else "legacy_shell"
            ),
        },
    )

    if require_safe_validation and validation_command and safe_validation_command is None:
        message = (
            "Unsafe legacy shell validation is blocked: automation requires "
            "safe validation argv."
        )
        result = with_replay_fields({
            "success": False,
            "applied_ops": [],
            "diffs": [],
            "rollback_performed": False,
            "failed_op_index": None,
            "failed_op": None,
            "error": message,
            "validation_ok": None,
            "validation_command": validation_command,
            "validation_output": "",
            "validation_mode": "blocked_unsafe_legacy_shell",
            "unsafe_validation_blocked": True,
            "message": message,
        })
        if bundle is not None:
            safe_write_json("apply_result.json", result)
            safe_write_artifact("validation_output.txt", "")
        append_event(
            "unsafe_validation_blocked",
            {
                "success": False,
                "validation_command": validation_command,
                "reason": message,
            },
        )
        if shadow_enabled:
            _attach_not_reached_shadow(
                result=result,
                bundle=bundle,
                authoritative_run_status=RUN_STATUS_BLOCKED,
            )
        finish("failed", result)
        return result

    patch_safety = evaluate_patch_safety(
        _patch_plan_files(plan),
        project_root=Path(project_root).resolve(),
    )
    if not patch_safety["ok"]:
        message = "Patch plan blocked by safety gate: " + "; ".join(
            patch_safety["reasons"]
        )
        result = with_replay_fields({
            "success": False,
            "applied_ops": [],
            "diffs": [],
            "rollback_performed": False,
            "failed_op_index": None,
            "failed_op": None,
            "error": message,
            "validation_ok": None,
            "validation_command": validation_command or "",
            "validation_output": "",
            "message": message,
            "patch_safety": patch_safety,
        })
        if bundle is not None:
            safe_write_json("apply_result.json", result)
            safe_write_artifact("validation_output.txt", "")
        append_event(
            "patch_plan_blocked_by_safety",
            {
                "success": False,
                "blocked_paths": patch_safety.get("blocked_paths", []),
                "reasons": patch_safety.get("reasons", []),
            },
        )
        if shadow_enabled:
            _attach_not_reached_shadow(
                result=result,
                bundle=bundle,
                authoritative_run_status=RUN_STATUS_BLOCKED,
            )
        finish("failed", result)
        return result

    if shadow_enabled:
        # Observe the pre-execution identity of the paths this plan already
        # names.  Nothing is discovered here and nothing is written; the apply
        # path proceeds identically whether or not this succeeded.
        shadow_pre_apply_digests = _shadow_pre_apply_digests(project_root, plan)

    apply_kwargs: dict[str, Any] = {"validation_command": validation_command}
    if safe_validation_command is not None:
        apply_kwargs["safe_validation_command"] = safe_validation_command
    if require_safe_validation:
        apply_kwargs["require_safe_validation"] = require_safe_validation

    result = apply_patch_plan(
        project_root,
        plan,
        **apply_kwargs,
    )
    result = with_replay_fields(result)

    if bundle is not None:
        safe_write_json("apply_result.json", result)
        safe_write_artifact("validation_output.txt", result.get("validation_output", "") or "")
    append_event(
        "patch_plan_applied" if result.get("success") else "patch_plan_failed",
        {
            "success": bool(result.get("success")),
            "error": result.get("error"),
            "validation_ok": result.get("validation_ok"),
        },
    )
    rollback = rollback_outcome_from_mapping(result)
    if rollback.performed:
        append_event("rollback_performed", {"failed_op_index": result.get("failed_op_index")})
    elif rollback.status in {ROLLBACK_INCOMPLETE, ROLLBACK_UNVERIFIABLE}:
        # Replay readers must not infer recovery from the absence of an event.
        append_event(
            "rollback_incomplete",
            {
                "failed_op_index": result.get("failed_op_index"),
                "rollback_status": rollback.status,
                "remaining_changed_paths": list(rollback.remaining_changed_paths),
                "remaining_created_directories": list(
                    rollback.remaining_created_directories
                ),
                "recovery_artifact_ids": list(rollback.recovery_artifact_ids),
                "recovery_material_error": rollback.recovery_material_error,
            },
        )
    if shadow_enabled:
        # Terminal boundary: every patch operation, any rollback and the one
        # validation have finished, and nothing below mutates the worktree.
        _attach_shadow_post_run_reconciliation(
            result=result,
            bundle=bundle,
            project_root=project_root,
            plan=plan,
            patch_safety=patch_safety,
            pre_apply_digests=shadow_pre_apply_digests,
            validation_requested=bool(
                validation_command or safe_validation_command
            ),
            worker_declaration=effective_worker_declaration,
            pre_execution_intent=(
                intent_capture.intent if intent_capture is not None else None
            ),
            intent_plan_agreement=(
                intent_capture.intent_plan_agreement
                if intent_capture is not None
                else "unavailable"
            ),
            append_event=append_event,
        )
    finish("success" if result.get("success") else "failed", result)
    return result
