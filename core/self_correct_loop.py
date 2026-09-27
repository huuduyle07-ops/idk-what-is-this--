from __future__ import annotations
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config import PATCH_LOOP_MAX
from core.executor import Executor, ExecutionResult
from core.prompter import build_re_patch_prompt


RePatchFn = Callable[[ExecutionResult, str], Optional[Dict[str, Any]]]
OnAttemptFn = Callable[[int, ExecutionResult], Optional[bool]]


def _result_to_attempt_record(idx: int, result: ExecutionResult) -> Dict[str, Any]:
    return {
        "attempt": idx,
        "success": result.success,
        "phase": result.phase,
        "matched_by": result.matched_by,
        "message": result.message,
        "validation_ok": result.validation_ok,
        "validation_output": result.validation_output,
        **result.rollback_payload_fields(),
        "failure_info": result.failure_info,
        "target_file": result.target_file,
        "patch_safety": result.patch_safety,
        "patch_safety_blocked": result.patch_safety_blocked,
        "patch_safety_reasons": result.patch_safety_reasons,
        "blocked_reason": result.blocked_reason,
    }


def run_self_correct_loop(
    project_root: str,
    initial_patch: Dict[str, Any],
    language: str,
    re_patch_fn: Optional[RePatchFn] = None,
    on_attempt: Optional[OnAttemptFn] = None,
    validation_command: str = "",
    max_attempts: int = PATCH_LOOP_MAX,
    rollback_on_validation_fail: bool = True,
    fallback_candidates: Optional[List[Dict[str, Any]]] = None,
    project_tag: Optional[str] = None,
) -> Dict[str, Any]:
    """Precision-Double-Tap self-healing patch loop.

    Attempt 1 applies `initial_patch`. On failure the executor classifies the
    error and rolls back atomically; attempt 2+ asks `re_patch_fn` for a
    revised patch built from the failure context (failed snippet + classifier
    hint + truncated validation log) via `build_re_patch_prompt`.

    `re_patch_fn(prev_result, prompt)` should call the LLM and return a parsed
    patch dict, or `None` to abort. If `re_patch_fn` is not provided, the loop
    falls back to consuming `fallback_candidates` (legacy behavior: try a fixed
    list of pre-computed patches).
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    executor = Executor(
        project_root=project_root,
        rollback_on_validation_fail=rollback_on_validation_fail,
    )

    attempts: List[Dict[str, Any]] = []
    current_patch: Optional[Dict[str, Any]] = dict(initial_patch)
    fallback_iter = iter(fallback_candidates or [])

    last_result: Optional[ExecutionResult] = None

    for idx in range(1, max_attempts + 1):
        if current_patch is None:
            break

        result = executor.run(
            patch=current_patch,
            language=language,
            validation_command=validation_command or None,
        )
        last_result = result
        attempts.append(_result_to_attempt_record(idx, result))

        if on_attempt is not None:
            try:
                cont = on_attempt(idx, result)
            except Exception as e:
                attempts[-1]["on_attempt_error"] = repr(e)
                cont = None
            if cont is False:
                return {
                    "success": bool(result.success),
                    "chosen_patch": current_patch if result.success else None,
                    "attempts": attempts,
                    "final_phase": result.phase,
                    "stop_reason": "aborted_by_on_attempt",
                }

        if result.success:
            return {
                "success": True,
                "chosen_patch": current_patch,
                "attempts": attempts,
                "final_phase": result.phase,
            }

        # A new attempt would use the unresolved state as its baseline and can
        # overwrite the only retained recovery bytes. Require manual repair
        # before continuing a loop whose automatic recovery did not complete.
        if result.rollback_outcome.status in {"incomplete", "unverifiable"}:
            return {
                "success": False,
                "chosen_patch": None,
                "attempts": attempts,
                "final_phase": result.phase,
                "stop_reason": "rollback_requires_manual_recovery",
            }

        # An inconclusive validation is not the AI's fault - and it is not
        # evidence the patch is wrong either. Re-prompting against a
        # missing toolchain, an absent test runner, a suite that collected
        # nothing, or (OPS.VALIDATE.2) a command the validator stopped at its
        # own budget would ask the model to fix a defect nobody observed, so
        # the loop stops instead of spending its second shot.
        if result.phase == "validation_environment_failed":
            return {
                "success": False,
                "chosen_patch": None,
                "attempts": attempts,
                "final_phase": result.phase,
                "stop_reason": "validation_environment_failed",
            }

        # Hard policy blocks: re-prompting won't help.
        if result.phase in {"dry_run_blocked", "post_apply_blocked", "patch_safety_blocked"}:
            return {
                "success": False,
                "chosen_patch": None,
                "attempts": attempts,
                "final_phase": result.phase,
                "stop_reason": "policy_block",
            }

        if idx >= max_attempts:
            break

        if re_patch_fn is not None:
            prompt = build_re_patch_prompt(
                failed_patch=current_patch,
                failure_info=getattr(result, "failure_info", None),
                validation_output=result.validation_output or "",
                target_file=result.target_file,
                matched_by=result.matched_by,
                project_tag=project_tag,
            )
            try:
                next_patch = re_patch_fn(result, prompt)
            except Exception as e:
                attempts[-1]["re_patch_error"] = repr(e)
                next_patch = None
            current_patch = next_patch
        else:
            current_patch = next(fallback_iter, None)

    return {
        "success": False,
        "chosen_patch": None,
        "attempts": attempts,
        "final_phase": last_result.phase if last_result else "no_attempt",
        "stop_reason": "max_attempts_reached" if last_result else "no_initial_patch",
    }
