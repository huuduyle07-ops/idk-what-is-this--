"""Rollback-protected executor for multi-op patch plans.

Used when the AI returns `patch_plan` instead of `patch_candidate` — usually
for feature work that touches multiple files or creates new ones (only
permitted under balanced/vibe vibecoding styles).

Design rules:
- Atomicity scope: patch operations are rolled back on apply or validation
  failure. Validation side effects are outside patch rollback scope unless
  validation runs in a disposable sandbox or a future explicit side-effect
  rollback mechanism is used.
- Security: every relative_path must resolve INSIDE project_root. Absolute
  paths and `..` traversal are rejected up front.
- Order matters: ops apply top-to-bottom. AI is responsible for ordering
  (e.g. create the file before replacing a snippet that imports it).

Supported ops:
  create_file       — write a new file with `content`. Fails if file exists.
  replace_snippet   — same as patch_candidate's target/patched snippet, but
                      for one of many files.

Write fidelity (OPS.PATCH.1)
----------------------------
Every read and write here is byte-oriented. `Path.read_text()` collapses CRLF
and lone CR to LF, and `Path.write_text()` translates every LF back to
`os.linesep` — so on Windows this path used to rewrite the line endings of any
file a patch touched, and rolled back through the same translation, leaving a
whole-file line-ending diff where it claimed to have restored the original.

The invariant is therefore stated in bytes:

  * an existing file keeps its own newline convention; only the bytes of the
    requested replacement may differ;
  * rollback restores the exact original bytes (encoding, BOM and terminators
    included), or the exact original absence for a created file;
  * a created file is written with the payload's own newline bytes — the host
    OS never converts it.

Snippet matching is deliberately unchanged: it still runs against the
universal-newline view that `read_text()` used to produce, so a `\\n` snippet
matches a CRLF file exactly as it always did. Only the write side moved.
"""
from __future__ import annotations

import difflib
import hashlib
import stat
from bisect import bisect_left
from pathlib import Path
from typing import Any

from core.failed_rollback_recovery import persist_failed_rollback_material
from core.rollback_outcome import (
    ROLLBACK_INCOMPLETE,
    attach_rollback_outcome,
    recovery_material_notice,
    rollback_not_required,
    rollback_outcome_from_plan,
)
from patching.patch_plan_transaction import (
    PlanError, PreparedPatchPlan, create_parents, plan_mutation_lock,
    plan_rejection, prepare_patch_plan, recover_transaction, recheck_target,
    snapshot_targets,
)

from core.validation_execution import (
    SafeValidationCommand,
    run_safe_validation_command,
)
from core.validation_outcome import (
    VALIDATION_INCONCLUSIVE,
    VALIDATION_PASSED,
)
from core.validation_side_effects import (
    diff_validation_side_effects,
    empty_validation_side_effect_report,
    snapshot_repo_files,
    with_atomicity_metadata,
)


# Byte baseline references used by the existing validation touched-path scope.
# TargetBaseline in patch_plan_transaction owns the one-per-physical-file
# transaction snapshot, including exact bytes, absence, hash and mode.
RollbackEntry = tuple[Path, bytes | None]


def _failed_result(
    rollbacks: list[RollbackEntry],
    op: dict,
    idx: int,
    error: str,
    diffs: list[str],
    applied_ops: list[dict],
    validation_side_effects: dict[str, Any] | None = None,
) -> dict:
    """Keep generic receipt semantics; the outer transaction owns recovery."""
    return with_atomicity_metadata(
        {
            "success": False,
            "failed_op_index": idx,
            "failed_op": op,
            "error": error,
            # The outer transaction has not attempted recovery yet.  Its
            # measured recovery facts are translated after final inspection.
            "rollback_performed": False,
            "applied_ops": applied_ops,
            "diffs": diffs,
        },
        validation_side_effects,
    )


def _to_lf(text: str) -> str:
    """Apply the same translation `Path.read_text()` applies (CRLF/CR → LF)."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _universal_newline_view(raw_text: str) -> tuple[str, list[int]]:
    """Return the LF view of `raw_text` plus the offsets needed to map back.

    Snippet matching has always run against `Path.read_text()` output, so it
    must keep running against the identical view or patches that used to apply
    to CRLF checkouts would start failing. This rebuilds that view without
    reading the file a second time, and returns the LF positions at which a
    `\\r\\n` was collapsed into one character.

    Only `\\r\\n` shortens the text; a lone `\\r` is substituted in place. So
    the raw offset of LF index ``i`` is ``i`` plus the number of collapsed
    pairs before it — see `_raw_offset`. Storing one int per CRLF line keeps
    this proportional to the file's line count, not its length.
    """
    if "\r" not in raw_text:
        # The overwhelmingly common case: the view is the text, unchanged.
        return raw_text, []

    collapsed: list[int] = []
    raw_index = 0
    lf_index = 0
    length = len(raw_text)
    while raw_index < length:
        if raw_text.startswith("\r\n", raw_index):
            collapsed.append(lf_index)
            raw_index += 2
        else:
            raw_index += 1
        lf_index += 1
    return _to_lf(raw_text), collapsed


def _raw_offset(lf_index: int, collapsed: list[int]) -> int:
    """Translate an index in the LF view back into the raw text."""
    if not collapsed:
        return lf_index
    return lf_index + bisect_left(collapsed, lf_index)


def _newline_for(region: str, fallback: str) -> str:
    """The newline convention to render an inserted snippet in.

    Preference order is the region being replaced, then the file as a whole —
    the same heuristic `patch_engine` already uses for the single-file path.
    A mixed-newline file therefore keeps whatever the untouched parts used,
    because those bytes are never rewritten at all.
    """
    if "\r\n" in region:
        return "\r\n"
    if "\n" in region:
        return "\n"
    return fallback


def _make_diff(original: str, modified: str, label: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            original.splitlines(),
            modified.splitlines(),
            fromfile=f"a/{label}",
            tofile=f"b/{label}",
            lineterm="",
        )
    )


def _validation_failed_message(kind: str) -> str:
    return (
        f"Patch plan applied, {kind} validation failed. "
        "Patch operations rolled back. "
        "Validation side effects are outside patch rollback scope; "
        "see validation_side_effects."
    )


def _validation_outcome_message(kind: str, outcome: str) -> str:
    """Say which of the two non-passing outcomes actually happened.

    Rollback policy is identical either way - an unvalidated patch is not
    accepted - but the sentence a human and a receipt read must not claim the
    patch failed its tests when no test was ever executed.
    """
    if outcome != VALIDATION_INCONCLUSIVE:
        return _validation_failed_message(kind)
    return (
        f"Patch plan applied, {kind} validation was inconclusive: it "
        "established neither a pass nor a failure. Patch operations rolled "
        "back. Validation side effects are outside patch rollback scope; "
        "see validation_side_effects."
    )


def _validation_crashed_message() -> str:
    return (
        "Patch plan validation crashed. Patch operations rolled back. "
        "Validation side effects are outside patch rollback scope; "
        "see validation_side_effects."
    )


def _patch_touched_paths(root: Path, rollbacks: list[RollbackEntry]) -> list[str]:
    paths: list[str] = []
    for path, _original in rollbacks:
        try:
            paths.append(path.resolve().relative_to(root).as_posix())
        except ValueError:
            paths.append(str(path))
    return paths


def _inspect_plan_final_state(root: Path, baselines) -> tuple[list[str], list[str]]:
    """Compare only the already-named targets with their exact baselines."""

    changed: set[str] = set()
    unverifiable: set[str] = set()
    for baseline in baselines:
        for path in baseline.paths:
            relative = path.relative_to(root).as_posix()
            try:
                recheck_target(root, path)
                if baseline.before_exists:
                    matches = (
                        path.is_file()
                        and hashlib.sha256(path.read_bytes()).hexdigest()
                        == baseline.before_sha256
                        and stat.S_IMODE(path.stat().st_mode) == baseline.before_mode
                    )
                else:
                    matches = not path.exists() and not path.is_symlink()
                if not matches:
                    changed.add(relative)
            except Exception:
                unverifiable.add(relative)
    return sorted(changed), sorted(unverifiable)


def _persist_plan_recovery_material(root: Path, baselines, outcome):
    unresolved = set(outcome.remaining_changed_paths)
    entries: list[tuple[str, bytes | None, bool, int | None]] = []
    for baseline in baselines:
        for path in baseline.paths:
            relative = path.relative_to(root).as_posix()
            if relative in unresolved:
                entries.append(
                    (
                        relative,
                        baseline.before_bytes,
                        baseline.before_exists,
                        baseline.before_mode if baseline.before_exists else None,
                    )
                )
    entries.extend(
        (relative, None, False, None)
        for relative in outcome.remaining_created_directories
    )
    artifact_ids, artifact_error, source_execution_id = (
        persist_failed_rollback_material(
            root,
            entries,
            originating_rollback_status=outcome.status,
        )
    )
    return (
        outcome.with_recovery_material(artifact_ids, error=artifact_error),
        source_execution_id,
    )


def apply_patch_plan(
    project_root: str,
    plan: list[dict],
    validation_command: str | None = None,
    safe_validation_command: SafeValidationCommand | None = None,
    require_safe_validation: bool = False,
) -> dict[str, Any]:
    """Prepare the entire supplied plan before any transaction can mutate."""
    try:
        if (validation_command is not None and type(validation_command) is not str
                or type(require_safe_validation) is not bool
                or safe_validation_command is not None and
                not isinstance(safe_validation_command, SafeValidationCommand)):
            raise PlanError("invalid_plan_schema", "Invalid validation option types.")
        prepared = prepare_patch_plan(project_root, plan)
    except PlanError as error:
        return plan_rejection(error)
    except Exception:
        return plan_rejection(PlanError("invalid_plan_schema", "Plan preparation failed."))
    return execute_prepared_patch_plan(
        prepared, validation_command, safe_validation_command, require_safe_validation,
    )


def execute_prepared_patch_plan(
    prepared: PreparedPatchPlan,
    validation_command: str | None = None,
    safe_validation_command: SafeValidationCommand | None = None,
    require_safe_validation: bool = False,
) -> dict[str, Any]:
    """Contain snapshot, ordered execution, validation and verified recovery.

    Prepared plans are internal immutable state, not a deserialization API or
    an authorization receipt. Existing caller authorization remains required.
    """
    if type(prepared) is not PreparedPatchPlan:
        return plan_rejection(PlanError("invalid_plan_schema", "Expected a prepared patch plan."))
    if require_safe_validation and validation_command and safe_validation_command is None:
        message = (
            "Unsafe legacy shell validation is blocked: automation requires "
            "safe validation argv."
        )
        return with_atomicity_metadata({
            "success": False,
            "applied_ops": [],
            "diffs": [],
            "rollback_performed": False,
            "failed_op_index": None,
            "failed_op": None,
            "error": message,
            "validation_ok": None,
            "validation_outcome": VALIDATION_INCONCLUSIVE,
            "validation_command": validation_command,
            "validation_output": "",
            "validation_mode": "blocked_unsafe_legacy_shell",
            "unsafe_validation_blocked": True,
            "message": message,
        })

    with plan_mutation_lock:
        try:
            baselines = snapshot_targets(prepared)
        except PlanError as error:
            return plan_rejection(error)
        except Exception:
            return plan_rejection(PlanError("execution_failed", "Transaction snapshot failed before mutation."))
        diffs: list[str] = []
        applied_ops: list[dict] = []
        created = []
        progress = {"mutation_attempted": False, "ordinal": None, "op": None}
        try:
            result = _execute_prepared_operations(
                prepared, baselines, created, progress, diffs, applied_ops,
                validation_command, safe_validation_command,
            )
        except Exception as error:
            result = _failed_result(
                [], progress["op"], progress["ordinal"],
                str(error) if isinstance(error, PlanError) else "Patch plan execution failed.",
                diffs, applied_ops,
            )
            result["code"] = error.code if isinstance(error, PlanError) else "execution_failed"
        result.update(mutation_attempted=progress["mutation_attempted"],
                      recovery_attempted=False, recovery_complete=None,
                      remaining_changed_paths=[], remaining_created_directories=[])
        if not result["success"]:
            result.setdefault("code", "execution_failed")
            if progress["mutation_attempted"]:
                result.update(recover_transaction(prepared.root, baselines, created))
                if not result["recovery_complete"]:
                    result["failure_code"] = result["code"]
                    result["code"] = "recovery_incomplete"
                    result["message"] = (
                        "Patch plan failed; rollback is incomplete and the "
                        "repository may still contain changes. Inspect "
                        "remaining_changed_paths and remaining_created_directories."
                    )
            result.setdefault("message", result.get("error", "Patch plan failed."))
        else:
            changed, unverifiable = _inspect_plan_final_state(
                prepared.root, baselines
            )
            result["final_repository_changed"] = bool(changed or unverifiable)
            result["final_state_verified"] = not unverifiable

        outcome = rollback_outcome_from_plan(result)
        if outcome.status == ROLLBACK_INCOMPLETE:
            outcome, source_execution_id = _persist_plan_recovery_material(
                prepared.root, baselines, outcome
            )
            result["recovery_source_execution_id"] = source_execution_id
            unresolved = list(outcome.remaining_changed_paths) + list(
                outcome.remaining_created_directories
            )
            result["message"] = (
                "Patch plan failed; rollback is incomplete and the repository "
                "may still contain changes. Unresolved: "
                + ", ".join(unresolved)
                + ". "
                + recovery_material_notice(outcome)
            )
        elif not progress["mutation_attempted"]:
            outcome = rollback_not_required()
        return attach_rollback_outcome(result, outcome)


def _execute_prepared_operations(
    prepared, baselines, created, progress, diffs, applied_ops,
    validation_command, safe_validation_command,
):
    root = prepared.root
    plan = prepared.operations
    # Preserve the existing validation side-effect scope calculation. These
    # pairs are baseline references, not per-op copies or durable Undo artifacts.
    rollbacks = [(path, baseline.before_bytes) for baseline in baselines for path in baseline.paths]
    for operation in plan:
        idx = operation.ordinal
        target = operation.target
        rel_path = operation.requested_path or operation.relative_path
        op_type = operation.kind
        op = operation.as_dict()
        progress.update(ordinal=idx, op=op)
        recheck_target(root, target)
        if op_type == "create_file":
            if target.exists():
                raise PlanError("precondition_failed", f"create_file: target already exists: {rel_path}", idx)
            content = operation.content
            progress["mutation_attempted"] = True
            create_parents(root, target, created)
            recheck_target(root, target)
            target.write_bytes(content.encode("utf-8"))
            diffs.append(_make_diff("", content, rel_path))
        elif op_type == "replace_snippet":
            if not target.is_file():
                raise PlanError("precondition_failed", f"replace_snippet: target file does not exist: {rel_path}", idx)
            original_bytes = target.read_bytes()
            try:
                raw_text = original_bytes.decode("utf-8")
            except UnicodeError:
                raise PlanError("precondition_failed", "replace_snippet: target is not valid UTF-8", idx) from None
            original, collapsed = _universal_newline_view(raw_text)
            match_start = original.find(operation.target_snippet)
            if match_start < 0:
                raise PlanError("precondition_failed", f"replace_snippet: target_snippet not found verbatim in {rel_path}", idx)
            raw_start = _raw_offset(match_start, collapsed)
            raw_end = _raw_offset(match_start + len(operation.target_snippet), collapsed)
            newline = _newline_for(
                raw_text[raw_start:raw_end],
                "\r\n" if "\r\n" in raw_text else "\n",
            )
            replacement = _to_lf(operation.patched_snippet).replace("\n", newline)
            new_raw = raw_text[:raw_start] + replacement + raw_text[raw_end:]
            recheck_target(root, target)
            progress["mutation_attempted"] = True
            target.write_bytes(new_raw.encode("utf-8"))
            diffs.append(_make_diff(original, _to_lf(new_raw), rel_path))
        else:
            raise PlanError("unsupported_operation", "unknown op type (allowed: create_file, replace_snippet)", idx)
        applied_ops.append(op)
    progress.update(ordinal=len(plan), op={"op": "validation"})
    # ---- validation after all ops ----
    validation_output = ""
    validation_ok = None
    validation_side_effects = empty_validation_side_effect_report()

    if safe_validation_command:
        before_validation = snapshot_repo_files(root)
        safe_result = run_safe_validation_command(safe_validation_command)
        after_validation = snapshot_repo_files(root)
        validation_side_effects = diff_validation_side_effects(
            root,
            before_validation,
            after_validation,
            _patch_touched_paths(root, rollbacks),
        )
        validation_ok = safe_result.ok
        validation_output = safe_result.output or safe_result.block_reason
        validation_command_label = " ".join(safe_validation_command.command)

        # OPS.VALIDATE.1 - a runner that exited 0 having collected nothing has
        # validated nothing, so it must not be accepted as a passing gate.
        from core.validator import (
            classify_validation_output,
            detect_no_tests_collected,
        )
        from core.validation_outcome import (
            CATEGORY_NO_TESTS_COLLECTED,
            budget_exhausted_info,
            outcome_reason,
            validation_outcome,
        )

        no_tests_collected = validation_ok and detect_no_tests_collected(
            validation_output,
            exit_code=safe_result.exit_code,
            command=validation_command_label,
        )
        if no_tests_collected:
            validation_ok = False

        if not validation_ok:
            if safe_result.blocked:
                info = {
                    "category": "unsafe_validation_command",
                    "reason": safe_result.block_reason,
                }
            elif safe_result.timed_out:
                # OPS.VALIDATE.2 - the plan is applied and the checks never
                # reached a verdict about it.  The rollback below is unchanged:
                # only a passing validation keeps a plan on disk.
                info = budget_exhausted_info(safe_result.timeout_sec)
            elif no_tests_collected:
                info = {
                    "category": CATEGORY_NO_TESTS_COLLECTED,
                    "reason": outcome_reason(CATEGORY_NO_TESTS_COLLECTED),
                }
            else:
                info = classify_validation_output(
                    validation_output,
                    exit_code=safe_result.exit_code,
                    command=validation_command_label,
                    timed_out=safe_result.timed_out,
                    timeout_seconds=safe_result.timeout_sec,
                )
            outcome = validation_outcome(
                category=info.get("category"), ok=False
            )

            return _failed_result(
                rollbacks=rollbacks,
                op={
                    "op": "validation",
                    "command": validation_command_label,
                    "category": info.get("category", "unknown"),
                    "validation_mode": "safe_argv",
                },
                idx=len(plan),
                error=(
                    f"validation {outcome} ({info.get('category', 'unknown')}): "
                    f"{info.get('reason', '')}"
                ),
                diffs=diffs,
                applied_ops=applied_ops,
                validation_side_effects=validation_side_effects,
            ) | {
                "validation_ok": False,
                "validation_outcome": outcome,
                "validation_command": validation_command_label,
                "validation_output": validation_output,
                "validation_info": info,
                "validation_mode": "safe_argv",
                "safe_validation_blocked": safe_result.blocked,
                "validation_timed_out": bool(safe_result.timed_out),
                "validation_timeout_seconds": safe_result.timeout_sec,
                "python_bytecode_cache_isolated": bool(
                    safe_result.python_bytecode_cache_isolated
                ),
                "message": _validation_outcome_message("safe", outcome),
            }

    elif validation_command:
        try:
            from core.validator import (
                classify_validation_output,
                detect_no_tests_collected,
                run_validation_command_detailed,
            )
            from core.validation_outcome import (
                CATEGORY_NO_TESTS_COLLECTED,
                budget_exhausted_info,
                outcome_reason,
                validation_outcome,
            )

            before_validation = snapshot_repo_files(root)
            validation_run = run_validation_command_detailed(
                validation_command,
                cwd=str(root),
            )
            validation_ok = validation_run.ok
            validation_output = validation_run.output
            after_validation = snapshot_repo_files(root)
            validation_side_effects = diff_validation_side_effects(
                root,
                before_validation,
                after_validation,
                _patch_touched_paths(root, rollbacks),
            )

            no_tests_collected = validation_ok and detect_no_tests_collected(
                validation_output,
                exit_code=validation_run.exit_code,
                command=validation_command,
            )
            if no_tests_collected:
                validation_ok = False

            if not validation_ok:
                if validation_run.timed_out:
                    # OPS.VALIDATE.2 - see the safe-argv branch above.
                    info = budget_exhausted_info(validation_run.timeout_seconds)
                elif no_tests_collected:
                    info = {
                        "category": CATEGORY_NO_TESTS_COLLECTED,
                        "reason": outcome_reason(CATEGORY_NO_TESTS_COLLECTED),
                    }
                else:
                    info = classify_validation_output(
                        validation_output,
                        exit_code=validation_run.exit_code,
                        command=validation_command,
                        timed_out=validation_run.timed_out,
                        timeout_seconds=validation_run.timeout_seconds,
                    )
                outcome = validation_outcome(
                    category=info.get("category"), ok=False
                )

                return _failed_result(
                    rollbacks=rollbacks,
                    op={
                        "op": "validation",
                        "command": validation_command,
                        "category": info.get("category", "unknown"),
                    },
                    idx=len(plan),
                    error=(
                        f"validation {outcome} ({info.get('category', 'unknown')}): "
                        f"{info.get('reason', '')}"
                    ),
                    diffs=diffs,
                    applied_ops=applied_ops,
                    validation_side_effects=validation_side_effects,
                ) | {
                    "validation_ok": False,
                    "validation_outcome": outcome,
                    "validation_command": validation_command,
                    "validation_output": validation_output,
                    "validation_info": info,
                    "validation_mode": "legacy_shell",
                    "validation_timed_out": bool(validation_run.timed_out),
                    "validation_timeout_seconds": validation_run.timeout_seconds,
                    "python_bytecode_cache_isolated": bool(
                        validation_run.python_bytecode_cache_isolated
                    ),
                    "message": _validation_outcome_message("legacy shell", outcome),
                }

        except Exception as e:
            return _failed_result(
                rollbacks=rollbacks,
                op={"op": "validation", "command": validation_command},
                idx=len(plan),
                error="validation runner crashed",
                diffs=diffs,
                applied_ops=applied_ops,
                validation_side_effects=validation_side_effects,
            ) | {
                "validation_ok": False,
                "validation_outcome": VALIDATION_INCONCLUSIVE,
                "validation_command": validation_command,
                "validation_output": validation_output,
                "validation_mode": "legacy_shell",
                "message": _validation_crashed_message(),
            }
    return with_atomicity_metadata(
        {
            "success": True,
            "applied_ops": applied_ops,
            "diffs": diffs,
            "rollback_performed": False,
            "failed_op_index": None,
            "failed_op": None,
            "error": None,
            "validation_ok": validation_ok,
            # Reached only when validation passed or was never requested.  A
            # run with no validation command has no outcome to report, which is
            # a different fact from an inconclusive one.
            "validation_outcome": (
                VALIDATION_PASSED if validation_ok is True else None
            ),
            "validation_command": (
                " ".join(safe_validation_command.command)
                if safe_validation_command
                else validation_command or ""
            ),
            "validation_output": validation_output,
            "validation_mode": "safe_argv" if safe_validation_command else (
                "legacy_shell" if validation_command else ""
            ),
            "message": (
                "Patch plan applied and validation passed."
                if validation_command or safe_validation_command
                else "Patch plan applied."
            ),
        },
        validation_side_effects,
    )
