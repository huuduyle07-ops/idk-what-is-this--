from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List
import difflib
import os
import re
import shutil
import tempfile

from patching.patch_engine import (
    apply_patch_from_json,
    find_target_file,
    restore_backup,
    cleanup_backup,
)
from core.patch_safety import evaluate_patch_safety
from core.failed_rollback_recovery import persist_failed_rollback_material
from core.rollback_outcome import (
    ROLLBACK_PROTECTION_SEMANTICS_CAPABILITY_ONLY,
    RollbackOutcome,
    rollback_completed_verified,
    rollback_failure_notice,
    rollback_incomplete,
    rollback_not_attempted,
    rollback_not_required,
    rollback_unverifiable,
)
from core.validation_execution import SafeValidationCommand, run_safe_validation_command
from core.validation_side_effects import (
    diff_validation_side_effects,
    empty_validation_side_effect_report,
    snapshot_repo_files,
)
from core.validator import (
    classify_validation_output,
    detect_no_tests_collected,
    run_validation_command_detailed,
)
from core.validation_outcome import (
    CATEGORY_NO_TESTS_COLLECTED,
    VALIDATION_PASSED,
    budget_exhausted_info,
    is_inconclusive_category,
    outcome_reason,
    validation_outcome,
)

# Markup / style files have no function-signature semantics, so risk heuristics
# tuned for code (signature change, function whitelist) misfire on them.
MARKUP_EXTENSIONS = {".html", ".htm", ".css", ".scss", ".sass"}


# Regexes that identify function/class declaration lines across the languages
# we benchmark. `_is_signature_changed` uses them to compare the actual
# declaration line instead of "everything before the first '{' or ':'" — the
# old heuristic false-positived on any prologue edit (imports, package
# declarations, top-level comments).
_FN_KW_PATTERNS = (
    re.compile(r"\b(?:async\s+)?def\s+\w+\s*\("),                       # Python
    re.compile(r"\b(?:async\s+)?function\s+\w+\s*\("),                  # JS / TS
    re.compile(r"\bfn\s+\w+\s*\("),                                      # Rust
    re.compile(r"\bfunc\s+(?:\([^)]*\)\s+)?\w+\s*\("),                   # Go (incl. methods)
)
_CLASS_KW_PATTERNS = (
    re.compile(r"\bclass\s+\w+"),                                        # Python / JS / TS / Java / C++ / C#
    re.compile(r"\b(?:struct|enum|trait|impl)\s+\w+"),                   # Rust
    re.compile(r"\btype\s+\w+\s+(?:struct|interface)\b"),                # Go
)
# C-style fallback for languages without a function keyword (C, C++, Java, C#).
# Only used when none of the keyword patterns matched.
_CSTYLE_FN_PATTERN = re.compile(r"^\s*[\w<>:&*][\w<>:&*\s,]*\s+\w+\s*\(")
_CSTYLE_BLACKLIST = frozenset({
    "if", "while", "for", "switch", "return", "do", "else", "case",
})
_COMMENT_PREFIXES = ("//", "#", "/*", "*", "--")


# =========================
# Data Models
# =========================

@dataclass
class PatchRisk:
    level: str   # low | medium | high
    score: int
    reasons: List[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    success: bool
    phase: str
    message: str

    target_file: Optional[str] = None
    validation_ok: Optional[bool] = None
    # OPS.VALIDATE.1 - passed | failed | inconclusive. ``validation_ok``
    # stays boolean for the callers that have always read it; this carries
    # the fact that boolean cannot: whether anything was checked at all.
    validation_outcome: Optional[str] = None
    validation_output: Optional[str] = None
    diff: Optional[str] = None
    risk: Optional[PatchRisk] = None

    # DATA.ROLLBACK.1: every compatibility fact below is derived from this
    # immutable outcome.  Callers cannot set rollback_performed independently.
    rollback_outcome: RollbackOutcome = field(default_factory=rollback_not_required)
    applied_patch: Optional[Dict[str, Any]] = None
    failure_info: Optional[Dict[str, str]] = None
    matched_by: Optional[str] = None
    patch_safety: Optional[Dict[str, Any]] = None
    patch_safety_blocked: bool = False
    patch_safety_reasons: List[str] = field(default_factory=list)
    blocked_reason: Optional[str] = None
    atomicity_scope: str = "patch_ops_only"
    patch_ops_rollback_protected: bool = True
    patch_ops_rollback_protection_semantics: str = (
        ROLLBACK_PROTECTION_SEMANTICS_CAPABILITY_ONLY
    )
    validation_side_effects_in_rollback_scope: bool = False
    validation_side_effect_policy: str = "reported_not_rolled_back"
    sandbox_validation_recommended: bool = True
    validation_side_effects: Dict[str, Any] = field(
        default_factory=empty_validation_side_effect_report
    )

    # Mutation oracle (Phase 2). Populated only on successful validation when
    # the oracle is enabled. None means "not run" or "no mutants applicable" —
    # downstream code must treat None as "no signal" rather than "weak".
    oracle_strength: Optional[float] = None
    oracle_tested: int = 0
    oracle_killed: int = 0
    oracle_note: Optional[str] = None

    @property
    def rollback_performed(self) -> bool:
        return self.rollback_outcome.performed

    @property
    def rollback_attempted(self) -> bool:
        return self.rollback_outcome.attempted

    @property
    def rollback_completed(self) -> bool:
        return self.rollback_outcome.completed

    @property
    def rollback_verified(self) -> bool:
        return self.rollback_outcome.verified

    @property
    def final_repository_changed(self) -> bool:
        return self.rollback_outcome.final_repository_changed

    def get_failure_report(self) -> str:
        if self.success:
            return "Success"
        report = f"Phase: {self.phase}\nMessage: {self.message}\n"
        if self.failure_info:
            report += (
                f"Category: {self.failure_info.get('category')}\n"
                f"Reason: {self.failure_info.get('reason')}\n"
                f"Hint: {self.failure_info.get('hint')}\n"
            )
        if self.validation_output:
            # Show first 10 lines of output to avoid context bloat
            lines = self.validation_output.splitlines()[:10]
            report += "Output Sample:\n" + "\n".join(lines) + "\n"
        return report

    def rollback_payload_fields(self) -> Dict[str, Any]:
        return self.rollback_outcome.as_payload_fields()


def _single_file_relative(root: Path, target: Path) -> str:
    try:
        # Keep the captured target identity even if an external writer redirects it.
        return target.absolute().relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return str(target)


def _recheck_recovery_path(path: Path) -> None:
    if path.resolve() != path.absolute():
        raise OSError("Recovery path no longer identifies the captured target.")


def _observe_single_file_change(
    target: Path, backup_path: Path | None
) -> tuple[bool, bool]:
    """Return (changed, verified) against the exact pre-mutation backup."""

    if backup_path is None:
        return True, False
    try:
        _recheck_recovery_path(backup_path)
        baseline = backup_path.read_bytes()
        _recheck_recovery_path(target)
        current = target.read_bytes()
    except (OSError, RuntimeError):
        return True, False
    return current != baseline, True


def _recover_single_file(
    root: Path, target: Path, backup_path: Path | None
) -> tuple[RollbackOutcome, str]:
    """Attempt restore, then let a separate byte read determine truth."""

    relative = _single_file_relative(root, target)
    try:
        if backup_path is None:
            raise FileNotFoundError("missing backup")
        _recheck_recovery_path(backup_path)
        baseline = backup_path.read_bytes()
    except (OSError, RuntimeError) as exc:
        return (
            rollback_unverifiable(
                [relative],
                attempted=False,
                failure_code="rollback_baseline_unavailable",
                failure_reason="Rollback baseline could not be read for verification.",
            ).with_recovery_material(
                [], error=f"rollback_baseline_unavailable:{type(exc).__name__}"
            ),
            "",
        )

    restore_error = ""
    try:
        _recheck_recovery_path(target)
        restore_backup(target, backup_path)
    except Exception as exc:  # noqa: BLE001 - converted to structured outcome
        restore_error = f"rollback_restore_failed:{type(exc).__name__}"

    try:
        _recheck_recovery_path(target)
        restored = target.read_bytes()
    except (OSError, RuntimeError) as exc:
        outcome = rollback_unverifiable(
            [relative],
            failure_code="rollback_state_unverifiable",
            failure_reason="Final target bytes could not be verified.",
        )
        artifact_ids, artifact_error, source_execution_id = (
            persist_failed_rollback_material(
                root,
                [(relative, baseline, True, None)],
                originating_rollback_status=outcome.status,
            )
        )
        outcome = outcome.with_recovery_material(
            artifact_ids, error=artifact_error
        )
        return outcome, source_execution_id

    if restored == baseline:
        # Final bytes win even if a restore primitive raised after completing.
        return rollback_completed_verified(), ""

    outcome = rollback_incomplete(
        [relative],
        failure_code="rollback_restore_failed" if restore_error else "rollback_noop_detected",
        failure_reason=(
            "Restore failed and final bytes still differ from the baseline."
            if restore_error
            else "Restore returned but final bytes still differ from the baseline."
        ),
    )
    artifact_ids, artifact_error, source_execution_id = (
        persist_failed_rollback_material(
            root,
            [(relative, baseline, True, None)],
            originating_rollback_status=outcome.status,
        )
    )
    outcome = outcome.with_recovery_material(artifact_ids, error=artifact_error)
    return outcome, source_execution_id


def _cleanup_recovery_backups(*backup_paths: Path | None) -> str:
    """Cleanup cannot change a final byte observation or hide its receipt."""

    errors = []
    for backup_path in dict.fromkeys(backup_paths):
        if backup_path is None:
            continue
        try:
            cleanup_backup(backup_path)
        except Exception as exc:  # noqa: BLE001 - separate cleanup diagnostic
            errors.append(f"backup_cleanup_failed:{type(exc).__name__}")
    return ";".join(errors)


def _stage_oracle_baseline(backup_path: Path | None) -> Path:
    """Protect the original baseline from the oracle's shared ``target.bak``."""

    if backup_path is None:
        raise FileNotFoundError("missing original backup")
    baseline = backup_path.read_bytes()
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{backup_path.name}.rollback-", suffix=".bak", dir=backup_path.parent
    )
    guarded_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(baseline)
            stream.flush()
            os.fsync(stream.fileno())
        shutil.copystat(backup_path, guarded_path)
        if guarded_path.read_bytes() != baseline:
            raise OSError("original baseline copy failed verification")
        return guarded_path
    except Exception:
        _cleanup_recovery_backups(guarded_path)
        raise


def _rollback_message(prefix: str, outcome: RollbackOutcome) -> str:
    if outcome.performed:
        return f"{prefix} Changes were reverted successfully."
    notice = rollback_failure_notice(outcome)
    return f"{prefix} {notice}" if notice else prefix


# =========================
# Executor Core
# =========================

class Executor:
    def __init__(
        self,
        project_root: str,
        rollback_on_validation_fail: bool = True,
    ):
        self.project_root = Path(project_root).resolve()
        self.rollback_on_validation_fail = rollback_on_validation_fail

    # =========================
    # MAIN ENTRY
    # =========================

    def run(
        self,
        patch: Dict[str, Any],
        language: str,
        validation_command: Optional[str] = None,
        safe_validation_command: SafeValidationCommand | None = None,
        require_safe_validation: bool = False,
        dry_run_only: bool = False,
    ) -> ExecutionResult:

        patch = dict(patch)
        patch["language"] = language

        # 1. DRY RUN
        dry = self.dry_run(patch)

        if dry_run_only:
            return ExecutionResult(
                success=True,
                phase="dry_run_only",
                message="Dry run only. Patch was not applied.",
                diff=dry["diff"],
                risk=dry["risk"],
                applied_patch=patch,
            )

        if require_safe_validation and validation_command and safe_validation_command is None:
            message = (
                "Unsafe legacy shell validation is blocked: automation requires "
                "safe validation argv."
            )
            return ExecutionResult(
                success=False,
                phase="unsafe_validation_blocked",
                message=message,
                target_file=self._single_file_patch_target(patch) or None,
                validation_ok=None,
                validation_output="",
                diff=dry["diff"],
                risk=dry["risk"],
                applied_patch=patch,
                matched_by=None,
                blocked_reason=message,
            )

        patch_safety = evaluate_patch_safety(
            self._single_file_patch_candidate_files(patch),
            project_root=self.project_root,
        )
        if not patch_safety["ok"]:
            message = "Patch blocked by safety gate: " + "; ".join(
                patch_safety["reasons"]
            )
            return ExecutionResult(
                success=False,
                phase="patch_safety_blocked",
                message=message,
                target_file=self._single_file_patch_target(patch) or None,
                validation_ok=None,
                diff=dry["diff"],
                risk=dry["risk"],
                applied_patch=patch,
                matched_by=None,
                patch_safety=patch_safety,
                patch_safety_blocked=True,
                patch_safety_reasons=list(patch_safety["reasons"]),
                blocked_reason=message,
            )

        if dry["risk"].level == "high":
            return ExecutionResult(
                success=False,
                phase="dry_run_blocked",
                message="Patch is blocked due to high risk.",
                diff=dry["diff"],
                risk=dry["risk"],
                applied_patch=patch,
                matched_by=None,
            )

        # 2. APPLY PATCH
        patch_result = apply_patch_from_json(str(self.project_root), patch)

        target_file = patch_result["target_file"]
        old_snippet = patch_result["old_snippet"]
        new_snippet = patch_result["new_snippet"]
        backup_path = patch_result["backup_path"]
        matched_by = patch_result["matched_by"]
        risk = self._adjust_risk_by_match_source(dry["risk"], matched_by)

        if matched_by == "literal" and risk.level in {"medium", "high"}:
            # Exception: verbatim named full-function patch + validation command.
            # The Executor block exists to guard against fragile literal matches,
            # but a literal match against a complete named function body with a
            # runnable validation command is exactly the safe case — the snippet
            # is unambiguous and the result will be checked. Don't reject those.
            if self._is_verbatim_named_literal_patch(patch) and validation_command:
                print(
                    "⚠️ Literal match allowed: target is a verbatim named "
                    "snippet and validation command is available."
                )
            else:
                outcome, _source_execution_id = _recover_single_file(
                    self.project_root, Path(target_file), backup_path
                )
                failure_info = {}
                if outcome.failure_code:
                    failure_info.update({
                        "rollback_code": outcome.failure_code,
                        "rollback_reason": outcome.failure_reason,
                    })
                if _source_execution_id:
                    failure_info["recovery_source_execution_id"] = _source_execution_id
                if outcome.performed and backup_path:
                    cleanup_error = _cleanup_recovery_backups(backup_path)
                    if cleanup_error:
                        failure_info["recovery_cleanup_error"] = cleanup_error

                return ExecutionResult(
                    success=False,
                    phase="post_apply_blocked",
                    message=_rollback_message(
                        "Patch blocked (literal match too risky).", outcome
                    ),
                    target_file=str(target_file),
                    diff=dry["diff"],
                    risk=risk,
                    applied_patch=patch,
                    matched_by=matched_by,
                    rollback_outcome=outcome,
                    failure_info=failure_info or None,
                )

        if not patch_result["success"] or not target_file:
            return ExecutionResult(
                success=False,
                phase="conflict",
                message="Patch failed to apply (conflict/drift detected).",
                diff=dry["diff"],
                risk=risk,
                applied_patch=patch,
                matched_by=matched_by,
                target_file=str(target_file) if target_file else str(patch.get("file", "")),
            )

        diff = self._generate_diff(old_snippet or "", new_snippet or "")

        # 3. NO VALIDATION MODE
        if not validation_command and safe_validation_command is None:
            changed, final_verified = _observe_single_file_change(
                Path(target_file), backup_path
            )
            outcome = rollback_not_required(
                final_repository_changed=changed,
                final_state_verified=final_verified,
            )
            cleanup_error = _cleanup_recovery_backups(backup_path)
            return ExecutionResult(
                success=True,
                phase="applied_no_validation",
                message="Applied patch (no validation).",
                target_file=str(target_file),
                diff=diff,
                risk=risk,
                applied_patch=patch,
                matched_by=matched_by,
                rollback_outcome=outcome,
                failure_info=(
                    {"recovery_cleanup_error": cleanup_error} if cleanup_error else None
                ),
            )

        # 4. VALIDATION
        print(
            "🧪 Executor validation command: "
            + (
                " ".join(safe_validation_command.command)
                if safe_validation_command
                else str(validation_command)
            )
        )
        print(f"🧪 Executor cwd: {self.project_root}")
        safe_validation_block_reason = ""
        validation_exit_code: Optional[int] = None
        # OPS.VALIDATE.2 - both runners report whether they stopped the command
        # at its budget; the executor carries that fact rather than letting the
        # classifier infer a verdict from partial output.
        validation_timed_out = False
        validation_timeout_seconds: Optional[int] = None
        if safe_validation_command:
            before_validation = snapshot_repo_files(self.project_root)
            safe_result = run_safe_validation_command(safe_validation_command)
            after_validation = snapshot_repo_files(self.project_root)
            ok = safe_result.ok
            output = safe_result.output or safe_result.block_reason
            validation_exit_code = safe_result.exit_code
            executed_command_text = " ".join(safe_validation_command.command)
            safe_validation_block_reason = safe_result.block_reason if safe_result.blocked else ""
            validation_timed_out = bool(safe_result.timed_out)
            validation_timeout_seconds = safe_result.timeout_sec
        else:
            before_validation = snapshot_repo_files(self.project_root)
            validation_run = run_validation_command_detailed(
                validation_command,
                cwd=str(self.project_root),
            )
            ok = validation_run.ok
            output = validation_run.output
            validation_exit_code = validation_run.exit_code
            executed_command_text = validation_command or ""
            validation_timed_out = bool(validation_run.timed_out)
            validation_timeout_seconds = validation_run.timeout_seconds
            after_validation = snapshot_repo_files(self.project_root)
        validation_side_effects = diff_validation_side_effects(
            self.project_root,
            before_validation,
            after_validation,
            [target_file],
        )

        # A runner that exited 0 having collected nothing has validated nothing.
        # Treating it as a pass would let an unchecked patch through the one
        # gate that exists to check it, so it drops into the failure branch and
        # is reported for what it is: inconclusive, not failed.
        no_tests_collected = ok and detect_no_tests_collected(
            output,
            exit_code=validation_exit_code,
            command=executed_command_text,
        )
        if no_tests_collected:
            ok = False

        if ok:
            oracle_strength: Optional[float] = None
            oracle_tested = 0
            oracle_killed = 0
            oracle_note: Optional[str] = None
            guarded_backup_path: Path | None = None
            oracle_state_failure = ""
            try:
                from config import MUTATION_ORACLE_ENABLED, MUTATION_ORACLE_MAX_MUTANTS
            except ImportError:
                MUTATION_ORACLE_ENABLED = False
                MUTATION_ORACLE_MAX_MUTANTS = 0

            if MUTATION_ORACLE_ENABLED and new_snippet and safe_validation_command is None:
                validated_bytes: bytes | None = None
                try:
                    # The frozen oracle shares target.bak with patch application.
                    # Preserve the original baseline before it can overwrite it.
                    guarded_backup_path = _stage_oracle_baseline(backup_path)
                    validated_bytes = Path(target_file).read_bytes()
                except OSError:
                    oracle_state_failure = "oracle_baseline_unavailable"
                try:
                    from core.mutation_oracle import run_mutation_oracle
                    if not oracle_state_failure:
                        print(f"🧬 Running mutation oracle (max={MUTATION_ORACLE_MAX_MUTANTS})...")
                        oracle = run_mutation_oracle(
                            project_root=str(self.project_root),
                            target_file=target_file,
                            applied_snippet=new_snippet,
                            validation_command=validation_command,
                            language=language,
                            max_mutants=MUTATION_ORACLE_MAX_MUTANTS,
                        )
                        oracle_strength = oracle.strength
                        oracle_tested = oracle.tested
                        oracle_killed = oracle.killed
                        oracle_note = (
                            "oracle: error during mutation validation"
                            if oracle.skipped_error
                            else oracle.summary_line()
                        )
                        print(f"🧬 {oracle_note}")
                except Exception as e:
                    oracle_note = f"oracle error: {type(e).__name__}"
                    print(f"⚠️ {oracle_note}")
                if not oracle_state_failure:
                    try:
                        if Path(target_file).read_bytes() != validated_bytes:
                            oracle_state_failure = "oracle_final_state_mismatch"
                    except OSError:
                        oracle_state_failure = "oracle_final_state_unverifiable"

            recovery_backup_path = guarded_backup_path or backup_path
            if oracle_state_failure:
                outcome, source_execution_id = _recover_single_file(
                    self.project_root, Path(target_file), recovery_backup_path
                )
                failure_info = {
                    "category": "oracle_recovery_failed",
                    "reason": "The mutation oracle did not preserve verified patch bytes.",
                    "code": oracle_state_failure,
                    "rollback_code": outcome.failure_code,
                    "rollback_reason": outcome.failure_reason,
                }
                if source_execution_id:
                    failure_info["recovery_source_execution_id"] = source_execution_id
                if outcome.performed:
                    cleanup_error = _cleanup_recovery_backups(
                        guarded_backup_path, backup_path
                    )
                    if cleanup_error:
                        failure_info["recovery_cleanup_error"] = cleanup_error
                return ExecutionResult(
                    success=False,
                    phase="oracle_recovery_failed",
                    message=_rollback_message(
                        "Mutation oracle left an unverified patch state.", outcome
                    ),
                    target_file=str(target_file),
                    validation_ok=True,
                    validation_outcome=VALIDATION_PASSED,
                    validation_output=output,
                    diff=diff,
                    risk=risk,
                    applied_patch=patch,
                    matched_by=matched_by,
                    oracle_strength=oracle_strength,
                    oracle_tested=oracle_tested,
                    oracle_killed=oracle_killed,
                    oracle_note=oracle_note,
                    validation_side_effects=validation_side_effects,
                    rollback_outcome=outcome,
                    failure_info=failure_info,
                )

            changed, final_verified = _observe_single_file_change(
                Path(target_file), recovery_backup_path
            )
            outcome = rollback_not_required(
                final_repository_changed=changed,
                final_state_verified=final_verified,
            )
            cleanup_error = _cleanup_recovery_backups(guarded_backup_path, backup_path)
            return ExecutionResult(
                success=True,
                phase="validated",
                message="Patch OK + validation passed.",
                target_file=str(target_file),
                validation_ok=True,
                validation_outcome=VALIDATION_PASSED,
                validation_output=output,
                diff=diff,
                risk=risk,
                applied_patch=patch,
                matched_by=matched_by,
                oracle_strength=oracle_strength,
                oracle_tested=oracle_tested,
                oracle_killed=oracle_killed,
                oracle_note=oracle_note,
                validation_side_effects=validation_side_effects,
                rollback_outcome=outcome,
                failure_info=(
                    {"recovery_cleanup_error": cleanup_error} if cleanup_error else None
                ),
            )
        print("🧪 Executor validation output:")
        print(output or "<empty>") 
        if safe_validation_block_reason:
            failure_info = {
                "category": "unsafe_validation_command",
                "reason": safe_validation_block_reason,
                "hint": "Use SafeValidationCommand for automation-safe validation.",
            }
        elif validation_timed_out:
            # The patch is on disk and the checks never returned a verdict about
            # it.  That is inconclusive, and the rollback below is unchanged:
            # an unvalidated patch is still not accepted.
            failure_info = budget_exhausted_info(validation_timeout_seconds)
        elif no_tests_collected:
            failure_info = {
                "category": CATEGORY_NO_TESTS_COLLECTED,
                "reason": outcome_reason(CATEGORY_NO_TESTS_COLLECTED),
                "hint": (
                    "No test was executed, so this run says nothing about the "
                    "patch. Point the validation command at tests that exist."
                ),
            }
        else:
            failure_info = classify_validation_output(
                output,
                exit_code=validation_exit_code,
                command=executed_command_text,
                timed_out=validation_timed_out,
                timeout_seconds=validation_timeout_seconds,
            )

        # Save patched file BEFORE rollback
        try:
            debug_dir = self.project_root / ".agent"
            debug_dir.mkdir(exist_ok=True)

            debug_name = f"debug_failed_validation_{Path(target_file).name}"
            debug_path = debug_dir / debug_name

            debug_path.write_text(
                Path(target_file).read_text(encoding="utf-8", errors="replace"),
                encoding="utf-8",
            )

            (debug_dir / "debug_failed_validation_output.txt").write_text(
                output or "<empty>",
                encoding="utf-8",
            )

            (debug_dir / "debug_failed_validation_command.txt").write_text(
                f"cwd={self.project_root}\ncommand={validation_command}\n",
                encoding="utf-8",
            )
        except Exception as e:
            print(f"⚠️ Could not write validation debug artifact: {e}")

        # OPS.VALIDATE.1 - "inconclusive" is the honest name for this bucket:
        # validation did not establish a result, so no diagnosis may be built on
        # it and the self-correction loop must not ask the model to rewrite a
        # patch against evidence that does not exist.  ``missing_dependency``
        # leaves the bucket because a dependency the repository itself imports
        # is a fact about the repository.
        validation_outcome_value = validation_outcome(
            category=failure_info.get("category"),
            ok=False,
        )
        is_environment_failure = is_inconclusive_category(
            failure_info.get("category")
        )

        # 5. FAIL → ROLLBACK
        source_execution_id = ""
        cleanup_error = ""
        if self.rollback_on_validation_fail:
            outcome, source_execution_id = _recover_single_file(
                self.project_root, Path(target_file), backup_path
            )
            if outcome.performed:
                cleanup_error = _cleanup_recovery_backups(backup_path)
        else:
            changed, final_verified = _observe_single_file_change(
                Path(target_file), backup_path
            )
            outcome = rollback_not_attempted(
                [_single_file_relative(self.project_root, Path(target_file))]
                if changed
                else [],
                failure_reason="Rollback policy disabled automatic recovery.",
            )
            if not final_verified:
                outcome = rollback_unverifiable(
                    [_single_file_relative(self.project_root, Path(target_file))],
                    attempted=False,
                    failure_code="rollback_not_attempted_state_unverifiable",
                    failure_reason=(
                        "Rollback was not attempted and final bytes could not be verified."
                    ),
                )
            cleanup_error = _cleanup_recovery_backups(backup_path)

        phase = "validation_environment_failed" if is_environment_failure else "validation_failed"

        failure_message = (
            f"Validation inconclusive ({failure_info['category']})."
            if is_environment_failure
            else f"Validation failed ({failure_info['category']})."
            )
        message = _rollback_message(failure_message, outcome)
        failure_info = {
            **failure_info,
            "rollback_code": outcome.failure_code,
            "rollback_reason": outcome.failure_reason,
        }
        if source_execution_id:
            failure_info["recovery_source_execution_id"] = source_execution_id
        if cleanup_error:
            failure_info["recovery_cleanup_error"] = cleanup_error
        
        return ExecutionResult(
            success=False,
            phase=phase,
            message=message,
            target_file=str(target_file),
            validation_ok=False,
            validation_outcome=validation_outcome_value,
            validation_output=output,
            diff=diff,
            risk=risk,
            rollback_outcome=outcome,
            applied_patch=patch,
            failure_info=failure_info,
            matched_by=matched_by,
            validation_side_effects=validation_side_effects,
        )
    
        
        
    # =========================
    # DRY RUN
    # =========================

    def dry_run(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        target = str(patch.get("target_snippet", "") or "")
        patched = str(patch.get("patched_snippet", "") or "")

        diff = self._generate_diff(target, patched)
        risk = self._score_patch_risk(patch, diff)

        return {
            "diff": diff,
            "risk": risk,
        }

    def _single_file_patch_target(self, patch: Dict[str, Any]) -> str:
        relative_path = patch.get("relative_path")
        if relative_path and relative_path != "<relative path if known>":
            return str(relative_path)
        return str(patch.get("file") or "")

    def _single_file_patch_candidate_files(self, patch: Dict[str, Any]) -> List[str]:
        """Return candidate touched files for the shared patch-safety gate.

        The patch engine accepts either a concrete ``relative_path`` or a
        basename-ish ``file`` fallback that it resolves before writing. Check
        both the raw candidate and, when discoverable without writing, the same
        resolved relative path the engine would target.
        """
        touched: List[str] = []
        raw_target = self._single_file_patch_target(patch)
        if raw_target:
            touched.append(raw_target)

        resolved = self._resolve_single_file_patch_target_for_safety(patch)
        if resolved is not None:
            try:
                relative = str(resolved.relative_to(self.project_root)).replace("\\", "/")
            except ValueError:
                relative = str(resolved)
            if relative not in touched:
                touched.append(relative)

        return touched or [""]

    def _resolve_single_file_patch_target_for_safety(
        self,
        patch: Dict[str, Any],
    ) -> Optional[Path]:
        relative_path = patch.get("relative_path")
        if relative_path and relative_path != "<relative path if known>":
            try:
                candidate = (self.project_root / str(relative_path)).resolve()
                candidate.relative_to(self.project_root)
            except (ValueError, OSError):
                return None
            if candidate.exists() and candidate.is_file():
                return candidate

        file_name = patch.get("file")
        if file_name:
            return find_target_file(str(self.project_root), str(file_name))
        return None

    def _is_verbatim_named_function_patch(self, patch: Dict[str, Any]) -> bool:
        """Whitelist for the literal-medium-risk block.

        True iff target_snippet is a complete named function body whose
        opening line begins with a recognised function keyword and contains
        the declared target_node_name. The check stays language-agnostic
        and conservative: any miss falls back to the normal block path.

        Markup files (HTML/CSS) are also whitelisted: a literal match
        guarantees the snippet is verbatim from source, and there are no
        function semantics to drift, so the normal "fragile literal match"
        concern does not apply.
        """
        target_snippet = str(patch.get("target_snippet") or "")
        target_node_name = str(patch.get("target_node_name") or "")
        node_kind = patch.get("target_node_kind") or "function"
        patch_file = str(patch.get("file") or patch.get("relative_path") or "")
        patch_ext = Path(patch_file).suffix.lower() if patch_file else ""

        if patch_ext in MARKUP_EXTENSIONS and target_snippet:
            return True

        if not target_snippet or not target_node_name or node_kind != "function":
            return False

        first_line = ""
        for line in target_snippet.splitlines():
            if line.strip():
                first_line = line.strip()
                break
        if not first_line:
            return False

        fn_keyword_prefixes = (
            "pub fn ", "pub(crate) fn ", "pub async fn ", "async fn ", "fn ",
            "def ", "async def ",
            "function ", "async function ",
            "export function ", "export async function ",
            "export default function ", "export default async function ",
            "func ",  # Go (incl. methods with explicit receiver)
        )
        # Accept if the declaration is on any non-blank line, not just the
        # first. Scanning every line lets patches that include file-level
        # context (imports, package declarations, top-level comments) still
        # qualify, as long as the named function declaration itself is
        # present verbatim. The literal-match has already confirmed the
        # snippet is taken from source, so the snippet is unambiguous.
        for line in target_snippet.splitlines():
            stripped = line.strip()
            if stripped.startswith(fn_keyword_prefixes) and target_node_name in line:
                return True

        # C/C++/Java/C#-style: "<type/qualifiers> name(args)" — no leading
        # keyword to anchor on. Accept iff the name is followed by ( on any
        # non-blank line and the snippet contains an opening brace. Scanning
        # every line (not just the first) mirrors the keyword-anchored path
        # above so patches that include file-level context — for instance an
        # `#include <...>` line prepended by normalize_patch_candidate_with_
        # control_source — still qualify.
        name_pat = re.compile(rf"\b{re.escape(target_node_name)}\s*\(")
        if "{" in target_snippet:
            for line in target_snippet.splitlines():
                if name_pat.search(line):
                    return True

        return False

    def _is_verbatim_named_assignment_patch(self, patch: Dict[str, Any]) -> bool:
        """Allow exact validated replacements of named top-level assignments.

        Reviewer models sometimes tag module constants/maps as ``class`` because
        the JSON schema only advertises function/class node kinds. A byte-exact
        target for a named assignment plus validation is still an unambiguous
        patch, so it should not be blocked solely for that schema mismatch.
        """
        target_snippet = str(patch.get("target_snippet") or "")
        target_node_name = str(patch.get("target_node_name") or "")
        if not target_snippet or not target_node_name:
            return False

        first_line = ""
        for line in target_snippet.splitlines():
            if line.strip():
                first_line = line.strip()
                break
        if not first_line:
            return False

        name = re.escape(target_node_name)
        assignment_patterns = (
            rf"^{name}\b\s*(?::[^=]+)?=",
            rf"^(?:export\s+)?(?:const|let|var)\s+{name}\b[^=]*=",
        )
        return any(re.match(pattern, first_line) for pattern in assignment_patterns)

    def _is_verbatim_named_literal_patch(self, patch: Dict[str, Any]) -> bool:
        return (
            self._is_verbatim_named_function_patch(patch)
            or self._is_verbatim_named_assignment_patch(patch)
        )

    def _adjust_risk_by_match_source(self, risk: PatchRisk, matched_by: Optional[str]) -> PatchRisk:
        score = risk.score
        reasons = list(risk.reasons)

        if matched_by == "fuzzy":
            score += 1
            reasons.append("Patch applied via fuzzy match.")
        elif matched_by == "literal":
            score += 2
            reasons.append("Patch applied via literal replace.")

        if score >= 5:
            level = "high"
        elif score >= 2:
            level = "medium"
        else:
            level = "low"
        return PatchRisk(level=level, score=score, reasons=reasons)
    # =========================
    # RISK SCORING
    # =========================

    def _score_patch_risk(self, patch: Dict[str, Any], diff: str) -> PatchRisk:
        score = 0
        reasons: List[str] = []

        target_snippet = patch.get("target_snippet", "")
        patched_snippet = patch.get("patched_snippet", "")
        node_kind = patch.get("target_node_kind", "")
        issue = str(patch.get("issue", "")).lower()
        patch_file = str(patch.get("file") or patch.get("relative_path") or "")
        patch_ext = Path(patch_file).suffix.lower() if patch_file else ""

        removed = [l for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
        added = [l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]

        # Size
        if len(removed) + len(added) > 30:
            score += 2
            reasons.append("Oversized patch (>30 lines).")

        # Deletion heavy
        if len(removed) > 10:
            score += 2
            reasons.append("Deletion heavy.")

        # Class-level. Models may mislabel module constants/maps as class nodes;
        # only apply this penalty when the target actually declares a class-like
        # structure.
        if node_kind == "class" and self._looks_like_class_declaration(target_snippet):
            score += 2
            reasons.append("Patch touches class.")

        # Signature change — skip for markup (no function signatures, and the
        # regex misreads HTML comments like `<!-- BUG: ... -->` as a delimiter).
        if patch_ext not in MARKUP_EXTENSIONS and self._is_signature_changed(target_snippet, patched_snippet):
            score += 3
            reasons.append("Function signature changed.")

        # Import added
        if "import" in patched_snippet and "import" not in target_snippet:
            score += 1
            reasons.append("Import added.")

        # Architecture-level
        if any(k in issue for k in ["architecture", "system", "multi-file"]):
            score += 2
            reasons.append("Patch related to architecture.")

        # Final level
        if score >= 5:
            level = "high"
        elif score >= 2:
            level = "medium"
        else:
            level = "low"

        return PatchRisk(level=level, score=score, reasons=reasons)

    def _looks_like_class_declaration(self, text: str) -> bool:
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(_COMMENT_PREFIXES):
                continue
            return any(pattern.search(line) for pattern in _CLASS_KW_PATTERNS)
        return False

    def _is_signature_changed(self, old: str, new: str) -> bool:
        """Detect if a function/class signature changed.

        Compares the first function/class declaration in each snippet
        (whitespace-normalised, parens balanced across lines). Edits to
        surrounding prologue — imports, package declarations, top-level
        comments — do not register as a signature change, which was the
        prior heuristic's most common false positive.
        """
        old_sig = self._find_signature_line(old)
        new_sig = self._find_signature_line(new)

        if not old_sig and not new_sig:
            return False
        return old_sig != new_sig

    def _find_signature_line(self, text: str) -> str:
        """Return the first function/class declaration in ``text``.

        For function declarations the result spans across lines until parens
        balance, so multi-line argument lists are captured intact. Returns
        an empty string if no declaration is found.
        """
        lines = text.splitlines()
        for i, raw_line in enumerate(lines):
            stripped = raw_line.strip()
            if not stripped or stripped.startswith(_COMMENT_PREFIXES):
                continue

            # Function-keyword anchored (Python, JS/TS, Rust, Go).
            if any(p.search(raw_line) for p in _FN_KW_PATTERNS):
                return self._collect_signature(lines, i)

            # Class / type declarations (single-line is sufficient).
            if any(p.search(raw_line) for p in _CLASS_KW_PATTERNS):
                return re.sub(r"\s+", " ", stripped)

            # C-style fallback: "<type> name(" with no leading keyword.
            # Reject control-flow constructs and method-call expressions.
            first_word = stripped.split(None, 1)[0] if stripped else ""
            if (
                first_word not in _CSTYLE_BLACKLIST
                and _CSTYLE_FN_PATTERN.match(raw_line)
                and "." not in stripped.split("(", 1)[0]
            ):
                return self._collect_signature(lines, i)

        return ""

    def _collect_signature(self, lines: List[str], start_idx: int) -> str:
        """Concatenate lines from ``start_idx`` until parens balance.

        Captures multi-line argument lists; stops at the line that closes
        the last opening paren, or at end of input.
        """
        depth = 0
        seen_open = False
        collected: List[str] = []
        for i in range(start_idx, len(lines)):
            line = lines[i]
            collected.append(line)
            for ch in line:
                if ch == "(":
                    depth += 1
                    seen_open = True
                elif ch == ")":
                    depth -= 1
            if seen_open and depth <= 0:
                break
        return re.sub(r"\s+", " ", " ".join(collected)).strip()


    # =========================
    # DIFF
    # =========================

    def _generate_diff(self, original: str, modified: str) -> str:
        diff = difflib.unified_diff(
            original.splitlines(),
            modified.splitlines(),
            fromfile="original",
            tofile="patched",
            lineterm=""
        )
        return "\n".join(diff)
