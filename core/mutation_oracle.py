"""Mutation oracle for executor-level patch validation.

After a patch passes validation_command, we don't actually know whether the
validation was sensitive enough to catch nearby mistakes. The oracle answers
that: generate small mutants of the patched snippet (operator flips, return
swaps, boolean inversions), re-apply each on top of the validated patch,
re-run validation. A *weak* validation will let mutants through; a *strong*
validation will kill them.

Strength = killed / tested. Returns None when nothing meaningful to test.

The oracle is opt-in (config.MUTATION_ORACLE_ENABLED) because each mutant
costs one validation_command run. With MAX_MUTANTS=5 and a 30s test suite,
that adds ~2.5 minutes per patch.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from patching.patch_engine import (
    apply_patch_from_json,
    backup_file,
    cleanup_backup,
    restore_backup,
)
from core.validator import run_validation_command


# =========================
# Data Models
# =========================

@dataclass
class Mutant:
    kind: str          # operator_flip | return_swap | boolean_flip | drop_guard
    description: str   # one-line human description
    code: str          # mutated snippet


@dataclass
class MutantOutcome:
    kind: str
    description: str
    killed: bool                 # True = validation failed = oracle caught it (good)
    apply_ok: bool               # False = couldn't even apply the mutant
    note: str = ""               # optional detail


@dataclass
class MutationOracleResult:
    strength: Optional[float]    # killed / tested, or None when no mutants tested
    tested: int
    killed: int
    skipped_no_mutants: bool = False
    skipped_disabled: bool = False
    skipped_error: Optional[str] = None
    details: List[MutantOutcome] = field(default_factory=list)

    def summary_line(self) -> str:
        if self.skipped_disabled:
            return "oracle: disabled"
        if self.skipped_no_mutants:
            return "oracle: no mutants applicable"
        if self.skipped_error:
            return f"oracle: error ({self.skipped_error})"
        if self.tested == 0:
            return "oracle: no mutants tested"
        return f"oracle: strength={self.strength:.2f} ({self.killed}/{self.tested} killed)"


# =========================
# Mutation Generators
# =========================
# Each generator takes a snippet and yields candidate mutants. They are
# regex-based and *idempotent per occurrence*: one pattern hit = one mutant,
# so we keep the action space bounded.

OperatorMap = dict[str, str]

# Symbol-style operators that show up across C-family + Python.
_SYMBOL_FLIPS: OperatorMap = {
    "==": "!=",
    "!=": "==",
    "<=": ">=",
    ">=": "<=",
    "&&": "||",
    "||": "&&",
    " < ": " > ",   # spaced to avoid generics like Vec<T>, List<int>
    " > ": " < ",
}

# Keyword-style operators (Python-ish). Word-boundary matched.
_KEYWORD_FLIPS: OperatorMap = {
    "and": "or",
    "or": "and",
}


def _gen_operator_flip(snippet: str) -> List[Mutant]:
    out: List[Mutant] = []
    for orig, flipped in _SYMBOL_FLIPS.items():
        idx = snippet.find(orig)
        if idx < 0:
            continue
        mutated = snippet[:idx] + flipped + snippet[idx + len(orig):]
        out.append(Mutant(
            kind="operator_flip",
            description=f"flip first `{orig.strip()}` -> `{flipped.strip()}`",
            code=mutated,
        ))
    for kw, flipped in _KEYWORD_FLIPS.items():
        m = re.search(rf"\b{kw}\b", snippet)
        if not m:
            continue
        mutated = snippet[:m.start()] + flipped + snippet[m.end():]
        out.append(Mutant(
            kind="operator_flip",
            description=f"flip first `{kw}` -> `{flipped}`",
            code=mutated,
        ))
    return out


_RETURN_PATTERNS: list[tuple[re.Pattern[str], Callable[[re.Match[str]], str], str]] = [
    (re.compile(r"\breturn\s+True\b"), lambda m: "return False", "return True -> False"),
    (re.compile(r"\breturn\s+False\b"), lambda m: "return True", "return False -> True"),
    (re.compile(r"\breturn\s+true\b"), lambda m: "return false", "return true -> false"),
    (re.compile(r"\breturn\s+false\b"), lambda m: "return true", "return false -> true"),
    (re.compile(r"\breturn\s+None\b"), lambda m: "return 0", "return None -> 0"),
    (re.compile(r"\breturn\s+nil\b"), lambda m: "return 0", "return nil -> 0"),
    (re.compile(r"\breturn\s+0\b"), lambda m: "return 1", "return 0 -> 1"),
]


def _gen_return_swap(snippet: str) -> List[Mutant]:
    out: List[Mutant] = []
    for pat, repl, desc in _RETURN_PATTERNS:
        m = pat.search(snippet)
        if not m:
            continue
        mutated = snippet[:m.start()] + repl(m) + snippet[m.end():]
        out.append(Mutant(kind="return_swap", description=desc, code=mutated))
    return out


def _gen_boolean_flip(snippet: str) -> List[Mutant]:
    """Negate a boolean literal at first occurrence — distinct from return swap."""
    out: List[Mutant] = []
    patterns = [
        (re.compile(r"(?<!\.)\bTrue\b"), "False", "True -> False"),
        (re.compile(r"(?<!\.)\bFalse\b"), "True", "False -> True"),
        (re.compile(r"(?<!\.)\btrue\b"), "false", "true -> false"),
        (re.compile(r"(?<!\.)\bfalse\b"), "true", "false -> true"),
    ]
    for pat, repl, desc in patterns:
        # Avoid double-counting with return_swap by only firing when not preceded by `return `.
        m = pat.search(snippet)
        if not m:
            continue
        preceding = snippet[max(0, m.start() - 8):m.start()]
        if preceding.rstrip().endswith("return"):
            continue
        mutated = snippet[:m.start()] + repl + snippet[m.end():]
        out.append(Mutant(kind="boolean_flip", description=desc, code=mutated))
    return out


_OFF_BY_ONE_PATTERNS = [
    (re.compile(r"(\w+)\s*<\s*len\("), r"\1 <= len("),
    (re.compile(r"(\w+)\s*<=\s*len\("), r"\1 < len("),
]


def _gen_off_by_one(snippet: str) -> List[Mutant]:
    out: List[Mutant] = []
    for pat, repl in _OFF_BY_ONE_PATTERNS:
        m = pat.search(snippet)
        if not m:
            continue
        mutated = snippet[:m.start()] + pat.sub(repl, snippet[m.start():], count=1)
        out.append(Mutant(
            kind="off_by_one",
            description="loop bound off-by-one",
            code=mutated,
        ))
    return out


_GENERATORS = [
    _gen_operator_flip,
    _gen_return_swap,
    _gen_boolean_flip,
    _gen_off_by_one,
]


def generate_mutants(snippet: str, max_mutants: int = 5, seed: Optional[int] = None) -> List[Mutant]:
    """Return up to `max_mutants` candidate mutants for `snippet`.

    Bucketed by kind for diversity: take one from each kind in round-robin order,
    then fill with remaining. Deterministic when seed is provided (used in tests).
    """
    if not snippet or max_mutants <= 0:
        return []

    rng = random.Random(seed) if seed is not None else random.Random()

    buckets: List[List[Mutant]] = []
    for gen in _GENERATORS:
        bucket = gen(snippet)
        if bucket:
            buckets.append(bucket)

    if not buckets:
        return []

    # Shuffle within buckets so we don't always pick the same operator first.
    for b in buckets:
        rng.shuffle(b)

    chosen: List[Mutant] = []
    while buckets and len(chosen) < max_mutants:
        for bucket in list(buckets):
            if not bucket:
                buckets.remove(bucket)
                continue
            chosen.append(bucket.pop(0))
            if len(chosen) >= max_mutants:
                break
    return chosen


# =========================
# Oracle Runner
# =========================

def run_mutation_oracle(
    project_root: str,
    target_file: Path | str,
    applied_snippet: str,
    validation_command: str,
    language: str,
    max_mutants: int = 5,
    seed: Optional[int] = None,
) -> MutationOracleResult:
    """Apply mutants on top of the already-validated file state, re-validate.

    Precondition: the file at `target_file` currently contains `applied_snippet`
    verbatim (i.e. the original patch has just been applied and validated).

    Each mutant cycle:
      1. apply_patch_from_json swaps `applied_snippet` for the mutant.
         (This creates the mutant's own backup of the *post-original-patch* state.)
      2. Re-run validation_command.
      3. Restore from the mutant's backup -> file returns to the validated state.
    """
    if not validation_command:
        return MutationOracleResult(strength=None, tested=0, killed=0,
                                    skipped_error="no validation_command")

    mutants = generate_mutants(applied_snippet, max_mutants=max_mutants, seed=seed)
    if not mutants:
        return MutationOracleResult(strength=None, tested=0, killed=0, skipped_no_mutants=True)

    target_file = Path(target_file)
    relative_path = str(target_file.relative_to(project_root)) if target_file.is_absolute() else str(target_file)

    outcomes: List[MutantOutcome] = []
    killed = 0
    tested = 0

    # Belt-and-braces backup of the validated state. If anything goes sideways
    # mid-cycle, we restore to this snapshot before propagating the error.
    safety_backup = backup_file(target_file)

    try:
        for mut in mutants:
            mutant_patch = {
                "file": str(target_file),
                "relative_path": relative_path,
                "target_snippet": applied_snippet,
                "patched_snippet": mut.code,
                "language": language,
            }
            apply_res = apply_patch_from_json(str(project_root), mutant_patch)

            if not apply_res.get("success") or not apply_res.get("backup_path"):
                outcomes.append(MutantOutcome(
                    kind=mut.kind, description=mut.description,
                    killed=False, apply_ok=False,
                    note="mutant did not apply (engine declined)",
                ))
                # Make sure we haven't drifted from the validated state.
                restore_backup(target_file, safety_backup)
                continue

            mutant_backup = apply_res["backup_path"]
            try:
                ok, _ = run_validation_command(validation_command, cwd=str(project_root))
            except Exception as e:
                ok = True   # treat as "passed" defensively so we don't credit the oracle for env failures
                outcomes.append(MutantOutcome(
                    kind=mut.kind, description=mut.description,
                    killed=False, apply_ok=True,
                    note=f"validation raised: {e!r}",
                ))
                restore_backup(target_file, mutant_backup)
                cleanup_backup(mutant_backup)
                tested += 1
                continue
            finally:
                pass

            restore_backup(target_file, mutant_backup)
            cleanup_backup(mutant_backup)

            tested += 1
            if not ok:
                killed += 1
            outcomes.append(MutantOutcome(
                kind=mut.kind, description=mut.description,
                killed=(not ok), apply_ok=True,
            ))
    except Exception as e:
        # Catastrophe path: try our best to restore from the safety backup.
        try:
            restore_backup(target_file, safety_backup)
        except Exception:
            pass
        cleanup_backup(safety_backup)
        return MutationOracleResult(
            strength=None, tested=tested, killed=killed,
            skipped_error=f"{type(e).__name__}: {e}",
            details=outcomes,
        )
    finally:
        cleanup_backup(safety_backup)

    strength = (killed / tested) if tested > 0 else None
    return MutationOracleResult(
        strength=strength, tested=tested, killed=killed, details=outcomes,
    )
