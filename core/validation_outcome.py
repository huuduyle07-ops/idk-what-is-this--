"""OPS.VALIDATE.1 — the three questions the validation path answers separately.

Production validation used to collapse three different facts into one boolean.
A repository whose test runner was not installed, a repository with no tests at
all and a repository whose tests genuinely failed all arrived downstream as
"validation failed", and a runner that executed zero checks and exited ``0``
arrived as "validation passed".  Both collapses are wrong in the direction that
matters: the first invents defect evidence, the second invents proof.

So the vocabulary here keeps them apart:

``passed``
    checks actually ran and passed.

``failed``
    checks actually ran and something the code asserted did not hold.

``inconclusive``
    validation established neither.  No command existed, the tool was not
    available, zero tests were collected, the command infrastructure failed
    before any code assertion was evaluated, or - OPS.VALIDATE.2 - the command
    ran but exhausted its validation budget before it could finish.

The last of those is the defect OPS.VALIDATE.2 exists to remove.  Running the
C.A.T.T.U.S self-repository suite (~8,944 tests) under a 30 s budget produced
partial pytest output that the failure taxonomy read as ``test_failure``: the
infrastructure ran out of time and production reported that the tests had
proved the candidate wrong.  A budget the validator itself imposed is a fact
about the validator, never evidence about the code, so
``validation_budget_exhausted`` joins the inconclusive set and can never ground
a defect.

The categorical facts are the substance; ``ok`` remains only for the existing
boolean APIs.  There is deliberately no score, weight or confidence here — an
inconclusive validation is not a weak failure, it is the absence of a result.
"""

from __future__ import annotations


VALIDATION_PASSED = "passed"
VALIDATION_FAILED = "failed"
VALIDATION_INCONCLUSIVE = "inconclusive"

VALIDATION_OUTCOMES: tuple[str, ...] = (
    VALIDATION_PASSED,
    VALIDATION_FAILED,
    VALIDATION_INCONCLUSIVE,
)

# ── Categories that mean "no code assertion was evaluated" ───────────────────
#
# ``missing_toolchain`` and ``validation_environment`` already existed and
# already meant this; they are named here rather than renamed, because the
# classifier's existing vocabulary is what downstream code and stored artifacts
# were written against.  ``no_tests_collected`` and
# ``validation_tool_unavailable`` are the two facts the field test proved were
# missing.
CATEGORY_NO_VALIDATION_COMMAND = "no_validation_command"
CATEGORY_NO_TESTS_COLLECTED = "no_tests_collected"
CATEGORY_VALIDATION_TOOL_UNAVAILABLE = "validation_tool_unavailable"
CATEGORY_MISSING_TOOLCHAIN = "missing_toolchain"
CATEGORY_VALIDATION_ENVIRONMENT = "validation_environment"
CATEGORY_UNSAFE_VALIDATION_COMMAND = "unsafe_validation_command"

#: OPS.VALIDATE.2 - the command was selected, started and ran, and the
#: validator stopped it at its own budget.  One canonical spelling, used by
#: every runner, classifier and consumer in the project; ``validation_timeout``
#: is deliberately *not* a second synonym.
CATEGORY_VALIDATION_BUDGET_EXHAUSTED = "validation_budget_exhausted"

INCONCLUSIVE_CATEGORIES: frozenset[str] = frozenset(
    {
        CATEGORY_NO_VALIDATION_COMMAND,
        CATEGORY_NO_TESTS_COLLECTED,
        CATEGORY_VALIDATION_TOOL_UNAVAILABLE,
        CATEGORY_MISSING_TOOLCHAIN,
        CATEGORY_VALIDATION_ENVIRONMENT,
        CATEGORY_UNSAFE_VALIDATION_COMMAND,
        CATEGORY_VALIDATION_BUDGET_EXHAUSTED,
    }
)

# ── Categories that are genuine executed-failure evidence ────────────────────
#
# These are the only categories that may ground a diagnosis: in each of them a
# runner reached the code and the code did something wrong.  This is the set the
# pre-existing "preflight failed, so preserve the grounded patch" optimisation
# was always meant to describe; before OPS.VALIDATE.1 it also contained the
# infrastructure categories above, which let a missing toolchain masquerade as
# proof about the source.
EXECUTED_FAILURE_CATEGORIES: frozenset[str] = frozenset(
    {
        "build_error",
        "syntax_error",
        "runtime_error",
        "assertion_failure",
        "test_failure",
        "import_error",
        "missing_dependency",
    }
)

#: The narrower subset that a compiler or import step proved, used where the
#: existing code speaks of a "compiler-grounded" fix.
COMPILER_GROUNDED_CATEGORIES: frozenset[str] = frozenset(
    {
        "build_error",
        "syntax_error",
        "import_error",
        "missing_dependency",
    }
)

_INCONCLUSIVE_REASONS: dict[str, str] = {
    CATEGORY_NO_VALIDATION_COMMAND: (
        "Validation inconclusive: no suitable validation command was detected."
    ),
    CATEGORY_NO_TESTS_COLLECTED: (
        "Validation inconclusive: no tests were collected, so nothing was checked."
    ),
    CATEGORY_VALIDATION_TOOL_UNAVAILABLE: (
        "Validation inconclusive: the validation tool is not available in this "
        "environment."
    ),
    CATEGORY_MISSING_TOOLCHAIN: (
        "Validation inconclusive: the required toolchain is missing."
    ),
    CATEGORY_VALIDATION_ENVIRONMENT: (
        "Validation inconclusive: the validation command could not execute."
    ),
    CATEGORY_UNSAFE_VALIDATION_COMMAND: (
        "Validation inconclusive: the validation command was refused as unsafe."
    ),
    CATEGORY_VALIDATION_BUDGET_EXHAUSTED: (
        "Validation inconclusive: the validation command was attempted but "
        "exhausted its validation budget before finishing, so no check "
        "reached a verdict."
    ),
}


def is_inconclusive_category(category: str | None) -> bool:
    """True when the category means validation established no result."""
    return str(category or "") in INCONCLUSIVE_CATEGORIES


def is_executed_failure_evidence(category: str | None) -> bool:
    """True only for a failure a runner actually observed in the code.

    An inconclusive category is never evidence of a defect, however plausible
    the surrounding run looked.  Callers use this to decide whether a failed
    preflight may ground a diagnosis.
    """
    return str(category or "") in EXECUTED_FAILURE_CATEGORIES


def is_compiler_grounded_category(category: str | None) -> bool:
    """True for the compiler/import subset of executed-failure evidence."""
    return str(category or "") in COMPILER_GROUNDED_CATEGORIES


def is_validation_budget_exhausted(category: str | None) -> bool:
    """True when the validator stopped its own command at the budget."""
    return str(category or "") == CATEGORY_VALIDATION_BUDGET_EXHAUSTED


def budget_exhausted_info(timeout_seconds: int | None = None) -> dict[str, str]:
    """The one classifier payload every timeout site returns.

    Built here rather than spelled out at each call site so the category, the
    wording and the hint cannot drift apart between the legacy shell runner,
    the safe-argv runner, preflight and the plan executor.  The hint says what
    a reader may do about it and deliberately makes no claim about what the
    tests would have concluded, because nothing observed one.
    """
    reason = _INCONCLUSIVE_REASONS[CATEGORY_VALIDATION_BUDGET_EXHAUSTED]
    if isinstance(timeout_seconds, int) and not isinstance(timeout_seconds, bool):
        reason = (
            "Validation inconclusive: the validation command was attempted but "
            f"exhausted its {timeout_seconds}s validation budget before "
            "finishing, so no check reached a verdict."
        )
    return {
        "category": CATEGORY_VALIDATION_BUDGET_EXHAUSTED,
        "reason": reason,
        "hint": (
            "The budget ran out, not the code. Nothing here says whether the "
            "checks would pass or fail. Narrow the validation command or raise "
            "its explicit timeout for this repository."
        ),
    }


def validation_outcome(*, category: str | None, ok: bool | None) -> str:
    """Map one categorical fact plus the legacy boolean onto the three-way answer.

    The category wins.  A runner that exits ``0`` after collecting zero tests is
    inconclusive even though ``ok`` is ``True``; a runner that could not start is
    inconclusive even though ``ok`` is ``False``.
    """
    if is_inconclusive_category(category):
        return VALIDATION_INCONCLUSIVE
    if ok is True:
        return VALIDATION_PASSED
    if ok is False:
        return VALIDATION_FAILED
    return VALIDATION_INCONCLUSIVE


def outcome_reason(category: str | None, *, fallback: str = "") -> str:
    """Human phrasing for an inconclusive category, never "tests failed"."""
    return _INCONCLUSIVE_REASONS.get(str(category or ""), fallback)


__all__ = [
    "VALIDATION_PASSED",
    "VALIDATION_FAILED",
    "VALIDATION_INCONCLUSIVE",
    "VALIDATION_OUTCOMES",
    "CATEGORY_NO_VALIDATION_COMMAND",
    "CATEGORY_NO_TESTS_COLLECTED",
    "CATEGORY_VALIDATION_TOOL_UNAVAILABLE",
    "CATEGORY_MISSING_TOOLCHAIN",
    "CATEGORY_VALIDATION_ENVIRONMENT",
    "CATEGORY_UNSAFE_VALIDATION_COMMAND",
    "CATEGORY_VALIDATION_BUDGET_EXHAUSTED",
    "INCONCLUSIVE_CATEGORIES",
    "EXECUTED_FAILURE_CATEGORIES",
    "COMPILER_GROUNDED_CATEGORIES",
    "is_inconclusive_category",
    "is_executed_failure_evidence",
    "is_compiler_grounded_category",
    "is_validation_budget_exhausted",
    "budget_exhausted_info",
    "validation_outcome",
    "outcome_reason",
]
