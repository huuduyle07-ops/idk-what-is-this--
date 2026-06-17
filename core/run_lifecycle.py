from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.brain_stamp import collect_brain_stamp
from core.patch_safety import evaluate_patch_safety
from core.validation_execution import SafeValidationCommand
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


def run_patch_plan_with_artifacts(
    project_root: str,
    plan: list[dict],
    validation_command: str | None = None,
    safe_validation_command: SafeValidationCommand | None = None,
    require_safe_validation: bool = False,
    user_query: str = "",
    control_result: dict[str, Any] | None = None,
    source: str = "pipeline",
) -> dict[str, Any]:
    """Run a patch plan and persist a replay bundle around the existing executor."""
    brain_stamp = collect_brain_stamp(project_root)
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

    def with_replay_fields(result: dict[str, Any]) -> dict[str, Any]:
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
        result = with_replay_fields(
            {
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
            }
        )
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
        result = with_replay_fields(
            {
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
            }
        )
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
        finish("failed", result)
        return result

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
    if result.get("rollback_performed"):
        append_event("rollback_performed", {"failed_op_index": result.get("failed_op_index")})
    finish("success" if result.get("success") else "failed", result)
    return result
