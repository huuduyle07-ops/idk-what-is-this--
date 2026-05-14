from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List
import difflib
import re

from patching.patch_engine import (
    apply_patch_from_json,
    restore_backup,
    cleanup_backup,
)
from core.validator import run_validation_command, classify_validation_output

# Markup / style files have no function-signature semantics, so risk heuristics
# tuned for code (signature change, function whitelist) misfire on them.
MARKUP_EXTENSIONS = {".html", ".htm", ".css", ".scss", ".sass"}


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
    validation_output: Optional[str] = None
    diff: Optional[str] = None
    risk: Optional[PatchRisk] = None

    rollback_performed: bool = False
    applied_patch: Optional[Dict[str, Any]] = None
    failure_info: Optional[Dict[str, str]] = None
    matched_by: Optional[str] = None

    # Mutation oracle (Phase 2). Populated only on successful validation when
    # the oracle is enabled. None means "not run" or "no mutants applicable" —
    # downstream code must treat None as "no signal" rather than "weak".
    oracle_strength: Optional[float] = None
    oracle_tested: int = 0
    oracle_killed: int = 0
    oracle_note: Optional[str] = None

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
            if self._is_verbatim_named_function_patch(patch) and validation_command and risk.level == "medium":
                print(
                    "⚠️ Literal match allowed: target is a verbatim named full-function "
                    "snippet and validation command is available."
                )
            else:
                if backup_path:
                    restore_backup(target_file, backup_path)
                    cleanup_backup(backup_path)

                return ExecutionResult(
                    success=False,
                    phase="post_apply_blocked",
                    message="Patch blocked (literal match too risky).",
                    target_file=str(target_file),
                    diff=dry["diff"],
                    risk=risk,
                    applied_patch=patch,
                    matched_by=matched_by,
                    rollback_performed=True,
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
        if not validation_command:
            cleanup_backup(backup_path)
            return ExecutionResult(
                success=True,
                phase="applied_no_validation",
                message="Applied patch (no validation).",
                target_file=str(target_file),
                diff=diff,
                risk=risk,
                applied_patch=patch,
                matched_by=matched_by,
            )

        # 4. VALIDATION
        print(f"🧪 Executor validation command: {validation_command}")
        print(f"🧪 Executor cwd: {self.project_root}")
        ok, output = run_validation_command(
            validation_command,
            cwd=str(self.project_root),
        )

        if ok:
            oracle_strength: Optional[float] = None
            oracle_tested = 0
            oracle_killed = 0
            oracle_note: Optional[str] = None
            try:
                from config import MUTATION_ORACLE_ENABLED, MUTATION_ORACLE_MAX_MUTANTS
            except ImportError:
                MUTATION_ORACLE_ENABLED = False
                MUTATION_ORACLE_MAX_MUTANTS = 0

            if MUTATION_ORACLE_ENABLED and new_snippet:
                try:
                    from core.mutation_oracle import run_mutation_oracle
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
                    oracle_note = oracle.summary_line()
                    print(f"🧬 {oracle_note}")
                except Exception as e:
                    oracle_note = f"oracle error: {type(e).__name__}: {e}"
                    print(f"⚠️ {oracle_note}")

            cleanup_backup(backup_path)
            return ExecutionResult(
                success=True,
                phase="validated",
                message="Patch OK + validation passed.",
                target_file=str(target_file),
                validation_ok=True,
                validation_output=output,
                diff=diff,
                risk=risk,
                applied_patch=patch,
                matched_by=matched_by,
                oracle_strength=oracle_strength,
                oracle_tested=oracle_tested,
                oracle_killed=oracle_killed,
                oracle_note=oracle_note,
            )
        print("🧪 Executor validation output:")
        print(output or "<empty>") 
        failure_info = classify_validation_output(output)

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

        is_environment_failure = failure_info.get("category") in {
            "missing_toolchain",
            "missing_dependency",
            "validation_environment",
        }

        # 5. FAIL → ROLLBACK
        rollback_performed = False
        if self.rollback_on_validation_fail:
            restore_backup(target_file, backup_path)
            rollback_performed = True

        cleanup_backup(backup_path)

        phase = "validation_environment_failed" if is_environment_failure else "validation_failed"

        message = (
            f"Validation environment failed ({failure_info['category']})."
            if is_environment_failure
            else f"Validation failed ({failure_info['category']})."
            )
        
        return ExecutionResult(
            success=False,
            phase=phase,
            message=message,
            target_file=str(target_file),
            validation_ok=False,
            validation_output=output,
            diff=diff,
            risk=risk,
            rollback_performed=rollback_performed,
            applied_patch=patch,
            failure_info=failure_info,
            matched_by=matched_by,
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
        )
        if first_line.startswith(fn_keyword_prefixes) and target_node_name in target_snippet:
            return True

        # C/C++/Java/C#-style: "<type/qualifiers> name(args)" — no leading
        # keyword to anchor on. Accept iff the name is followed by ( on the
        # first line and the snippet contains an opening brace.
        name_pat = re.compile(rf"\b{re.escape(target_node_name)}\s*\(")
        if name_pat.search(first_line) and "{" in target_snippet:
            return True

        return False

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

        # Class-level
        if node_kind == "class":
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

    def _is_signature_changed(self, old: str, new: str) -> bool:
        """
        Detects if a function/class signature changed.
        Works across multiple lines and ignores formatting changes.
        """
        def get_signature_block(text: str) -> str:
            # Capture until first ':' (Python) or '{' (C, C#, JS, Rust)
            match = re.search(r"^(.*?)(?::|\{)", text, re.DOTALL | re.MULTILINE)
            if match:
                sig = match.group(1)
            else:
                # Fallback to first line if no delimiter found
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                sig = lines[0] if lines else ""
            
            # Normalize whitespace: remove newlines, replace multiple spaces with one
            sig = re.sub(r"\s+", " ", sig).strip()
            return sig

        old_sig = get_signature_block(old)
        new_sig = get_signature_block(new)
        
        return old_sig != new_sig


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