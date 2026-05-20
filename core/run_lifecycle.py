from __future__ import annotations

from typing import Any

from core.brain_stamp import collect_brain_stamp
from core.run_artifacts import RunArtifactRecorder
from patching.patch_plan_executor import apply_patch_plan


def run_patch_plan_with_artifacts(
    project_root: str,
    plan: list[dict],
    validation_command: str | None = None,
    user_query: str = "",
    control_result: dict[str, Any] | None = None,
    source: str = "pipeline",
) -> dict[str, Any]:
    """Run a patch plan and persist a replay bundle around the existing executor."""
    brain_stamp = collect_brain_stamp(project_root)
    recorder = RunArtifactRecorder.start(
        repo_path=project_root,
        source=source,
        brain_stamp=brain_stamp,
    )
    recorder.write_text("user_query.txt", user_query or "")
    recorder.write_json("control_result.json", control_result or {})
    recorder.write_json("patch_plan.json", plan)
    recorder.append_event("started", {"validation_command": validation_command or ""})

    result = apply_patch_plan(
        project_root,
        plan,
        validation_command=validation_command,
    )
    result = {
        **result,
        "replay_dir": str(recorder.replay_dir),
        "brain_stamp_id": brain_stamp.get("brain_stamp_id"),
    }

    recorder.write_json("apply_result.json", result)
    recorder.write_text("validation_output.txt", result.get("validation_output", "") or "")
    recorder.append_event(
        "patch_plan_applied" if result.get("success") else "patch_plan_failed",
        {
            "success": bool(result.get("success")),
            "error": result.get("error"),
            "validation_ok": result.get("validation_ok"),
        },
    )
    if result.get("rollback_performed"):
        recorder.append_event("rollback_performed", {"failed_op_index": result.get("failed_op_index")})
    recorder.finish("success" if result.get("success") else "failed", result)
    return result
