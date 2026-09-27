from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from flask import Blueprint, request

from core.executor import Executor
from core.undo_backup import BackupError, UndoBackupStore, mutation_lock
from core.candidate_sandbox_validation import (
    candidate_plan_from_payload,
    patch_candidate_as_plan,
    patch_plan_fingerprint,
)
from core.execution_outcome_telemetry import (
    AUTHORITY_SOURCE_MANUAL_APPLY,
    authorized_execution,
    final_state_observation,
    no_execution,
    observe_named_paths,
    plan_execution_receipt,
    single_file_execution_receipt,
)
from core.human_apply_authorization import (
    DENIAL_PATCH_SAFETY_MISMATCH,
    HUMAN_ACTION_APPLY,
    authorize_human_apply,
    describe_human_apply_authorization,
)
from core.patch_safety import evaluate_patch_safety
from core.rollback_outcome import (
    disposable_clone_rollback_fields,
    rollback_failure_notice,
    rollback_not_required,
    rollback_outcome_from_mapping,
)
from core.run_lifecycle import run_patch_plan_with_artifacts
from core.validation_command import get_default_validation_command
from web.patch_helpers import (
    detect_patch_language,
    detect_repo_language,
    patch_plan_files,
)
from web.session_store import update_session_apply_outcome


bp = Blueprint("patch_routes", __name__)
BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
BACKUP_DIR.mkdir(exist_ok=True)


def _risk_dict(result) -> dict | None:
    risk = getattr(result, "risk", None)
    if not risk:
        return None
    return {
        "level": risk.level,
        "score": risk.score,
        "reasons": list(risk.reasons or []),
    }


def _failure_message_without_rollback(message: str) -> str:
    """Keep the failure cause while dropping an earlier rollback conclusion."""
    lower = message.lower()
    boundaries = [lower.find(marker) for marker in (
        " changes were reverted", " rollback ", "; rollback ",
        " patch operations rolled back", " the patch was rolled back",
        " the patch plan was rolled back", "\nrollback performed:",
    )]
    found = [index for index in boundaries if index >= 0]
    return message[:min(found)].rstrip(" ;") if found else message


def _rollback_response_message(reason: str, fields: dict, subject: str) -> str:
    """The final observation owns every rollback claim shown by the API."""
    outcome = rollback_outcome_from_mapping(fields)
    reason = _failure_message_without_rollback(reason)
    if outcome.performed:
        return f"{reason} The {subject} was rolled back."
    if outcome.status == "not_required":
        return reason
    clone = fields.get("rollback_scope") == "disposable_clone"
    notice = rollback_failure_notice(
        outcome,
        scope="disposable clone" if clone else "repository",
        # A removed clone keeps no recovery files; its own note says so.
        include_material=not clone,
    )
    return f"{reason} {notice}"


def _final_rollback_failure_info(failure_info, fields: dict):
    """Executor diagnostics keep their cause; rollback facts follow the final outcome."""
    if not isinstance(failure_info, dict) or not (
        {"rollback_code", "rollback_reason"} & failure_info.keys()
    ):
        return failure_info
    outcome = rollback_outcome_from_mapping(fields)
    return {
        **failure_info,
        "rollback_code": outcome.failure_code,
        "rollback_reason": outcome.failure_reason,
    }


def _manual_action_fields(payload: dict, plan: list[dict]) -> tuple[str, str, str]:
    """Read the explicit browser action, preserving old artifact semantics."""
    has_review = isinstance(payload.get("human_apply_review"), dict)
    action = request.form.get("human_action_kind", "")
    approved_candidate = request.form.get("approved_candidate_fingerprint", "")
    approved_eligibility = request.form.get(
        "approved_eligibility_receipt_fingerprint", ""
    )
    if not has_review:
        # A POST to these pre-existing Apply-only routes is itself the legacy
        # explicit action. New receipts never use this compatibility fallback.
        action = action or HUMAN_ACTION_APPLY
        approved_candidate = approved_candidate or patch_plan_fingerprint(plan)
    return action, approved_candidate, approved_eligibility


def _denial_message(authorization, patch_safety: dict, safety_prefix: str) -> str:
    """Keep this route's established safety wording when the gate is what blocked.

    Human Apply never overrides patch safety, so a safety refusal still reports
    the gate's own reasons exactly as it did before this authority boundary
    existed; the non-override sentence is added, never substituted.
    """
    if (
        authorization.denial_reason == DENIAL_PATCH_SAFETY_MISMATCH
        and patch_safety.get("ok") is not True
    ):
        return (
            f"{safety_prefix} blocked by safety gate: "
            + "; ".join(patch_safety.get("reasons") or [])
            + "\nHuman Apply did not override patch safety; nothing was applied."
        )
    return describe_human_apply_authorization(authorization)


def _denied_manual_apply_response(
    *,
    payload: dict,
    authorization,
    patch_safety: dict,
    safety_prefix: str,
) -> dict:
    telemetry = no_execution(
        authorization.denial_reason,
        human_approval_required_for_execution=True,
    ).as_payload_fields()
    payload.update(authorization.as_payload_fields())
    payload.update(telemetry)
    return {
        "success": False,
        "message": _denial_message(authorization, patch_safety, safety_prefix),
        "diff": "",
        "validation": "",
        "risk": None,
        "validation_command": "",
        "patch_safety": patch_safety,
        "patch": json.dumps(payload, indent=2, ensure_ascii=False),
        **authorization.as_payload_fields(),
        **telemetry,
    }


def _persist_manual_apply(
    *, payload: dict, repo_path: str, response: dict
) -> None:
    try:
        update_session_apply_outcome(
            request.form.get("session_id", ""),
            repo_path=repo_path,
            patch_payload=payload,
            response=response,
        )
    except OSError:
        # Replay artifacts remain the durable executor record when the optional
        # web session history cannot be updated.
        pass


@bp.route("/apply_patch", methods=["POST"])
def apply_patch():
    repo_path = request.form.get("repo_path", "")
    patch_json = request.form["patch"]
    apply_policy = request.form.get("apply_policy", "ask")

    if apply_policy == "plan":
        return {
            "success": False,
            "message": "Plan-only policy: server refused to apply.",
            "diff": "",
            "validation": "",
        }

    try:
        parsed = json.loads(patch_json)
        if not isinstance(parsed, dict):
            raise ValueError("patch payload must be an object")
        if isinstance(parsed.get("patch_candidate"), dict):
            patch = parsed["patch_candidate"]
            approval_payload = parsed
        else:
            patch = parsed
            approval_payload = {**parsed, "patch_candidate": dict(parsed)}
        if "patched_snippet" not in patch:
            return {
                "success": False,
                "message": "No patch_candidate found. Expected top-level patch_candidate or direct patch object.",
                "diff": "",
                "validation": "",
            }
    except Exception:
        return {"error": "Invalid patch JSON"}

    approval_payload.pop("undo_backup", None)

    target_file = patch.get("relative_path") or patch.get("file")
    if not target_file:
        return {"error": "Patch missing target file"}

    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}

    repo_root = Path(repo_path).resolve()
    patch_safety = evaluate_patch_safety([target_file], project_root=repo_root)
    approval_plan = patch_candidate_as_plan(patch)
    action, approved_candidate, approved_eligibility = _manual_action_fields(
        approval_payload, approval_plan
    )
    authorization = authorize_human_apply(
        payload=approval_payload,
        repo_path=repo_root,
        patch_safety_verdict=patch_safety,
        human_action_kind=action,
        approved_candidate_fingerprint=approved_candidate,
        approved_eligibility_receipt_fingerprint=approved_eligibility,
        allow_legacy_explicit_change=True,
    )
    if not authorization.authorized:
        response = _denied_manual_apply_response(
            payload=approval_payload,
            authorization=authorization,
            patch_safety=patch_safety,
            safety_prefix="Patch",
        )
        _persist_manual_apply(
            payload=approval_payload, repo_path=repo_path, response=response
        )
        return response

    file_path = (repo_root / target_file).resolve()
    try:
        file_path.relative_to(repo_root)
    except ValueError:
        return {
            "success": False,
            "message": "Unsafe patch target: file is outside repo.",
            "diff": "",
            "validation": "",
            "patch_safety": patch_safety,
        }, 400

    executor = Executor(
        project_root=repo_path,
        rollback_on_validation_fail=True,
    )

    lang = detect_patch_language(patch)
    validation_command = get_default_validation_command(lang, repo_root)

    # The durable web Undo producer and consumer share one local mutation lock.
    # Executor rollback and execution authority retain their existing semantics.
    store = UndoBackupStore(BACKUP_DIR)
    backup = None
    backup_error = None
    with mutation_lock:
        try:
            pending = store.prepare(repo_root, target_file)
        except (BackupError, OSError, ValueError, RuntimeError) as exc:
            return {"success": False, "code": getattr(exc, "code", "backup_io_failed"),
                    "message": f"Could not preserve Undo backup; Apply refused: {exc}"}
        manual_before = observe_named_paths(repo_root, [target_file])
        result = executor.run(
            patch=patch,
            language=lang,
            validation_command=validation_command,
        )
        if result.success:
            try:
                backup = store.complete(pending, repo_root, target_file)
            except (BackupError, OSError, ValueError, RuntimeError) as exc:
                # Apply already completed. Report backup publication separately;
                # do not rewrite executor success or rollback truthfulness.
                backup_error = {"code": getattr(exc, "code", "backup_io_failed"), "message": str(exc)}
    approval_payload["undo_backup"] = (
        {"backup_id": backup.backup_id, "transaction_id": backup.transaction_id}
        if backup else None
    )
    receipt = single_file_execution_receipt(
        [
            {
                "phase": result.phase,
                **result.rollback_payload_fields(),
                "validation_outcome": result.validation_outcome,
                "target_file": result.target_file,
            }
        ],
        success=result.success,
        validation_requested=bool(validation_command),
    )
    telemetry = authorized_execution(
        authority_source=AUTHORITY_SOURCE_MANUAL_APPLY,
        receipt=receipt,
        observation=final_state_observation(
            manual_before, observe_named_paths(repo_root, [target_file])
        ),
    ).as_payload_fields()
    approval_payload.update(authorization.as_payload_fields())
    approval_payload.update(telemetry)
    response = {
        "undo_backup": approval_payload["undo_backup"],
        "backup_id": backup.backup_id if backup else None,
        "backup_error": backup_error,
        "message": result.message,
        "phase": result.phase,
        "validation_outcome": result.validation_outcome,
        "failure_info": _final_rollback_failure_info(result.failure_info, telemetry),
        "diff": result.diff,
        "validation": result.validation_output,
        "success": result.success,
        "risk": _risk_dict(result),
        "validation_command": validation_command or "",
        "patch_safety": patch_safety,
        **result.rollback_payload_fields(),
        "patch": json.dumps(approval_payload, indent=2, ensure_ascii=False),
        **authorization.as_payload_fields(),
        **telemetry,
    }
    if result.success:
        response["message"] = str(telemetry.get("execution_summary") or result.message)
    else:
        response["message"] = _rollback_response_message(result.message, telemetry, "patch")
    _persist_manual_apply(
        payload=approval_payload, repo_path=repo_path, response=response
    )
    return response


@bp.route("/test_patch", methods=["POST"])
def test_patch():
    repo_path = request.form.get("repo_path", "")
    patch_json = request.form["patch"]

    try:
        parsed = json.loads(patch_json)

        if isinstance(parsed.get("patch_candidate"), dict):
            patch = parsed["patch_candidate"]
        else:
            patch = parsed

        if "patched_snippet" not in patch:
            return {
                "success": False,
                "message": "No patch_candidate found. Expected top-level patch_candidate or direct patch object.",
                "diff": "",
                "validation": "",
            }
    except Exception:
        return {"error": "Invalid patch JSON"}

    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}

    target_file = patch.get("relative_path") or patch.get("file") or ""
    patch_safety = evaluate_patch_safety(
        [target_file],
        project_root=Path(repo_path).resolve(),
    )
    if not patch_safety["ok"]:
        return {
            "success": False,
            "message": "Patch blocked by safety gate: " + "; ".join(patch_safety["reasons"]),
            "diff": "",
            "validation": "",
            "risk": None,
            "validation_command": "",
            "patch_safety": patch_safety,
            **rollback_not_required().as_payload_fields(),
        }

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        temp_repo = Path(temp_dir) / "repo"
        shutil.copytree(
            repo_path,
            temp_repo,
            ignore=shutil.ignore_patterns(
                "target",
                ".git",
                ".agent",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                "node_modules",
                "dist",
                "build",
                ".venv",
                "venv",
                ".env",
                ".env.*",
            ),
        )

        executor = Executor(
            project_root=str(temp_repo),
            rollback_on_validation_fail=True,
        )

        lang = detect_patch_language(patch)
        validation_command = get_default_validation_command(lang, temp_repo)

        result = executor.run(
            patch=patch,
            language=lang,
            validation_command=validation_command,
            dry_run_only=False,
        )

        clone_fields = disposable_clone_rollback_fields(result.rollback_payload_fields())
        message = result.message if result.success else _rollback_response_message(
            result.message, clone_fields, "patch"
        )
        return {
            "message": message + " " + clone_fields["recovery_material_note"],
            "diff": result.diff,
            "validation": result.validation_output,
            "success": result.success,
            "risk": _risk_dict(result),
            "validation_command": validation_command or "",
            "patch_safety": patch_safety,
            **clone_fields,
        }


def _prepare_plan_request(repo_path, plan):
    # Reject before the lifecycle creates replay artifacts or a dry-run clone.
    from patching.patch_plan_transaction import PlanError, plan_rejection, prepare_patch_plan
    try:
        prepare_patch_plan(repo_path, plan)
    except PlanError as error:
        return plan_rejection(error)
    except Exception:
        return plan_rejection(PlanError("invalid_plan_schema", "Plan preparation failed."))
    return None


def _plan_transaction_fields(result):
    return {key: result[key] for key in (
        "code", "failure_code", "mutation_attempted", "recovery_attempted",
        "recovery_complete", "remaining_changed_paths", "remaining_created_directories",
        "rollback_outcome_schema_version", "rollback_outcome", "rollback_status",
        "rollback_attempted", "rollback_completed", "rollback_verified",
        "rollback_failure", "recovery_artifact_ids", "recovery_material_available",
        "recovery_material_error", "recovery_source_execution_id",
        "final_repository_changed", "final_state_verified",
    ) if key in result}


@bp.route("/test_patch_plan", methods=["POST"])
def test_patch_plan():
    """Dry-run a multi-op patch_plan in a temp clone, then validate."""
    repo_path = request.form.get("repo_path", "")
    patch_json = request.form.get("patch", "")
    patch_style = request.form.get("patch_style", "")

    if patch_style == "safe_minimal":
        return {
            "success": False,
            "message": "safe_minimal mode forbids patch_plan. Switch to balanced or vibe to test multi-file changes.",
            "diff": "",
            "validation": "",
        }

    try:
        patch = json.loads(patch_json)
        if not isinstance(patch, dict):
            raise ValueError("patch payload must be an object")
    except Exception:
        from patching.patch_plan_transaction import PlanError, plan_rejection
        return plan_rejection(PlanError("invalid_plan_schema", "Invalid patch JSON"))

    plan = patch.get("patch_plan")
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}

    preparation_error = _prepare_plan_request(repo_path, plan)
    if preparation_error is not None and preparation_error["code"] != "unsafe_target":
        return preparation_error

    patch_safety = evaluate_patch_safety(
        patch_plan_files(plan),
        project_root=Path(repo_path).resolve(),
    )
    if preparation_error is not None and patch_safety["ok"]:
        return preparation_error
    if not patch_safety["ok"]:
        return {
            "success": False,
            "message": "Patch plan blocked by safety gate: " + "; ".join(patch_safety["reasons"]),
            "diff": "",
            "validation": "",
            "risk": None,
            "validation_command": "",
            **_plan_transaction_fields(preparation_error or {}),
            "patch_safety": patch_safety,
        }

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        temp_repo = Path(temp_dir) / "repo"
        shutil.copytree(
            repo_path,
            temp_repo,
            ignore=shutil.ignore_patterns(
                "target",
                ".git",
                ".agent",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                "node_modules",
                "dist",
                "build",
                ".venv",
                "venv",
                ".env",
                ".env.*",
            ),
        )

        lang = detect_repo_language(temp_repo)
        validation_command = get_default_validation_command(lang, temp_repo)

        result = run_patch_plan_with_artifacts(
            str(temp_repo),
            plan,
            validation_command=validation_command,
            user_query=request.form.get("query", ""),
            control_result={"route": "test_patch_plan"},
            source="web_test_patch_plan",
        )

        combined_diff = "\n\n".join(d for d in result.get("diffs", []) if d)
        summary = result.get("message") or ""

        if not result.get("success"):
            failed = result.get("failed_op") or {}
            idx = result.get("failed_op_index")
            err = result.get("error") or "unknown"
            summary = (
                f"Plan dry-run failed at op #{idx}: {err}\n"
                f"Failed op: {json.dumps(failed, ensure_ascii=False)[:200]}"
            )

        clone_fields = disposable_clone_rollback_fields(result)
        if not result.get("success"):
            summary = _rollback_response_message(summary, clone_fields, "patch plan")
        return {
            "success": result.get("success", False),
            "message": summary + " " + clone_fields["recovery_material_note"],
            "diff": combined_diff,
            "validation": result.get("validation_output", ""),
            "applied_ops": result.get("applied_ops", []),
            "rollback_performed": result.get("rollback_performed", False),
            **_plan_transaction_fields(result),
            **clone_fields,
            "risk": None,
            "validation_command": validation_command or "",
            "patch_safety": patch_safety,
        }


@bp.route("/apply_patch_plan", methods=["POST"])
def apply_patch_plan_route():
    """Apply a multi-op patch_plan (used by balanced/vibe styles)."""
    repo_path = request.form.get("repo_path", "")
    patch_json = request.form.get("patch", "")
    apply_policy = request.form.get("apply_policy", "ask")
    patch_style = request.form.get("patch_style", "")

    if apply_policy == "plan":
        return {
            "success": False,
            "message": "Plan-only policy: server refused to apply.",
            "diff": "",
            "validation": "",
        }

    if patch_style == "safe_minimal":
        return {
            "success": False,
            "message": "safe_minimal mode forbids patch_plan. Switch to balanced or vibe to apply multi-file changes.",
            "diff": "",
            "validation": "",
        }

    try:
        patch = json.loads(patch_json)
        if not isinstance(patch, dict):
            raise ValueError("patch payload must be an object")
    except Exception:
        from patching.patch_plan_transaction import PlanError, plan_rejection
        return plan_rejection(PlanError("invalid_plan_schema", "Invalid patch JSON"))

    plan = patch.get("patch_plan")
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}

    preparation_error = _prepare_plan_request(repo_path, plan)
    if preparation_error is not None and preparation_error["code"] != "unsafe_target":
        return preparation_error

    repo_root = Path(repo_path).resolve()
    patch_safety = evaluate_patch_safety(
        patch_plan_files(plan),
        project_root=repo_root,
    )
    if preparation_error is not None and patch_safety["ok"]:
        return preparation_error
    action, approved_candidate, approved_eligibility = _manual_action_fields(
        patch, plan
    )
    authorization = authorize_human_apply(
        payload=patch,
        repo_path=repo_root,
        patch_safety_verdict=patch_safety,
        human_action_kind=action,
        approved_candidate_fingerprint=approved_candidate,
        approved_eligibility_receipt_fingerprint=approved_eligibility,
        allow_legacy_explicit_change=True,
    )
    if not authorization.authorized:
        response = _denied_manual_apply_response(
            payload=patch,
            authorization=authorization,
            patch_safety=patch_safety,
            safety_prefix="Patch plan",
        )
        response.update(_plan_transaction_fields(preparation_error or {}))
        _persist_manual_apply(payload=patch, repo_path=repo_path, response=response)
        return response

    lang = detect_repo_language(repo_root)
    validation_command = get_default_validation_command(lang, repo_root)

    touched = patch_plan_files(plan)
    manual_before = observe_named_paths(repo_root, touched)
    result = run_patch_plan_with_artifacts(
        repo_path,
        plan,
        validation_command=validation_command,
        user_query=request.form.get("query", ""),
        control_result={"route": "apply_patch_plan"},
        source="web_apply_patch_plan",
        pre_execution_authorization=authorization.as_dict(),
    )
    telemetry = authorized_execution(
        authority_source=AUTHORITY_SOURCE_MANUAL_APPLY,
        receipt=plan_execution_receipt(result),
        observation=final_state_observation(
            manual_before, observe_named_paths(repo_root, touched)
        ),
    ).as_payload_fields()
    patch.update(authorization.as_payload_fields())
    patch.update(telemetry)

    combined_diff = "\n\n".join(d for d in result.get("diffs", []) if d)
    summary = result.get("message") or ""
    if not result.get("success"):
        failed = result.get("failed_op") or {}
        idx = result.get("failed_op_index")
        err = result.get("error") or "unknown"
        summary = (
            f"Plan failed at op #{idx}: {err}\n"
            f"Failed op: {json.dumps(failed, ensure_ascii=False)[:200]}"
        )

    response = {
        "success": result.get("success", False),
        "message": summary,
        "diff": combined_diff,
        "validation": result.get("validation_output", ""),
        "applied_ops": result.get("applied_ops", []),
        "rollback_performed": result.get("rollback_performed", False),
        **_plan_transaction_fields(result),
        "replay_dir": result.get("replay_dir", ""),
        "replay_id": result.get("replay_id", ""),
        "validation_outcome": result.get("validation_outcome"),
        "validation_info": result.get("validation_info"),
        "failed_op": result.get("failed_op"),
        "failed_op_index": result.get("failed_op_index"),
        "error": result.get("error"),
        "risk": None,
        "validation_command": validation_command or "",
        "patch_safety": patch_safety,
        "patch": json.dumps(patch, indent=2, ensure_ascii=False),
        **authorization.as_payload_fields(),
        **telemetry,
    }
    if result.get("success"):
        response["message"] = str(telemetry.get("execution_summary") or summary)
    else:
        response["message"] = _rollback_response_message(summary, telemetry, "patch plan")
    _persist_manual_apply(payload=patch, repo_path=repo_path, response=response)
    return response
