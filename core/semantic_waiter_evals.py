"""INPUT.2 — semantic evaluation case matrix and deterministic checker.

The DeepSeek dogfood sentence is patient zero, not the benchmark.  A Semantic
Waiter is only useful if it reads paraphrases, other languages, bounded local
comparisons, plain explanations, and ambiguous references without inventing
work the user never asked for.

Every expectation here is checked deterministically against a finished
:class:`~core.semantic_waiter_runner.SemanticWaiterOutcome`.  The same cases
drive the default scripted tests and the opt-in live provider smoke, so the two
never drift apart.

This module is pure data plus a pure checker: no model call, no network, no
repository access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.semantic_waiter_runner import SemanticWaiterOutcome


PHASE_ID = "INPUT.2"

#: Opt-in switch for the live provider smoke. The default suite never sets it.
LIVE_SMOKE_ENV_VAR = "RUN_LIVE_SEMANTIC_WAITER_TESTS"

#: Task types that count as "the user asked to be told about something",
#: as opposed to a comparison. INPUT.1's vocabulary is frozen, so an
#: explanation lands on one of these rather than getting its own type.
EXPLANATORY_TASK_TYPES: tuple[str, ...] = ("question", "analysis", "research")

#: Mirrors the identity normalization used by the INPUT.1 preservation gate so
#: "C.A.T.T.U.S", "CATTUS" and "cattus" count as the same thing here too.
_IGNORED_KEY_CHARS: frozenset[str] = frozenset(" \t\n.-_/\\'\"`")


def _key(value: str) -> str:
    return "".join(char for char in value.casefold() if char not in _IGNORED_KEY_CHARS)


@dataclass(frozen=True, slots=True)
class SemanticEvalCase:
    """One semantic expectation about how a request should be understood."""

    case_id: str
    label: str
    prompt: str
    expected_task_types: tuple[str, ...]
    required_subjects: tuple[str, ...] = ()
    forbidden_subjects: tuple[str, ...] = ()
    require_comparison: bool = False
    forbid_comparison: bool = False
    require_framework: bool = False
    forbid_framework: bool = False
    required_framework_value_count: int | None = None
    required_framework_fragments: tuple[str, ...] = ()
    require_output: bool = False
    allowed_output_formats: tuple[str, ...] = ()
    required_constraint_fragments: tuple[str, ...] = ()
    require_ambiguity: bool = False
    forbidden_execution_requirements: tuple[str, ...] = ()
    require_preservation_pass: bool = True
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "label": self.label,
            "prompt": self.prompt,
            "expected_task_types": list(self.expected_task_types),
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class SemanticEvalResult:
    """Deterministic verdict for one evaluated case."""

    case_id: str
    passed: bool
    status: str
    failures: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "status": self.status,
            "failures": list(self.failures),
        }


DOGFOOD_PROMPT = """Analyze DeepSeek Harness against C.A.T.T.U.S using the following framework:

- Equivalent
- DeepSeek stronger
- C.A.T.T.U.S stronger
- Orthogonal
- Not worth adopting
"""


SEMANTIC_EVAL_CASES: tuple[SemanticEvalCase, ...] = (
    SemanticEvalCase(
        case_id="A_dogfood_original",
        label="DeepSeek Harness dogfood, original wording",
        prompt=DOGFOOD_PROMPT,
        expected_task_types=("comparative_analysis",),
        required_subjects=("DeepSeek Harness", "C.A.T.T.U.S"),
        require_comparison=True,
        require_framework=True,
        required_framework_value_count=5,
        required_framework_fragments=("Equivalent", "Orthogonal", "Not worth adopting"),
        notes="Patient zero: the run where C.A.T.T.U.S vanished as a subject.",
    ),
    SemanticEvalCase(
        case_id="B_paraphrase",
        label="Same request, paraphrased and reordered",
        prompt=(
            "Compare C.A.T.T.U.S with DeepSeek Harness and tell me where they overlap, "
            "where each is stronger, what is orthogonal, and what is not worth adopting."
        ),
        expected_task_types=("comparative_analysis",),
        required_subjects=("DeepSeek Harness", "C.A.T.T.U.S"),
        require_comparison=True,
        notes=(
            "The rubric is prose here, not a list, so INPUT.1 extracts no framework; "
            "the task class and both subjects must still survive."
        ),
    ),
    SemanticEvalCase(
        case_id="C_vietnamese",
        label="Same request in Vietnamese",
        prompt=(
            "Hãy so sánh DeepSeek Harness với C.A.T.T.U.S theo các tiêu chí: "
            "tương đương, DeepSeek mạnh hơn, C.A.T.T.U.S mạnh hơn, độc lập, "
            "và không đáng để học theo."
        ),
        expected_task_types=("comparative_analysis",),
        required_subjects=("DeepSeek Harness", "C.A.T.T.U.S"),
        require_comparison=True,
        require_framework=True,
        required_framework_value_count=5,
        notes=(
            "INPUT.1's literal extractor is English-only, so the comparison and the "
            "criteria must be marked inferred. Semantic understanding may be "
            "multilingual while literal preservation covers only what was extracted."
        ),
    ),
    SemanticEvalCase(
        case_id="D_bounded_code_comparison",
        label="Bounded comparison of two pasted snippets",
        prompt="Compare these two pasted functions for readability and complexity.",
        expected_task_types=("comparative_analysis",),
        require_comparison=True,
        forbidden_execution_requirements=(
            "repository_inspection_required",
            "local_repository_required",
            "external_information_required",
        ),
        notes="A comparative task is not a large-task execution.",
    ),
    SemanticEvalCase(
        case_id="E_explanation_not_comparison",
        label="Explanation request, no comparison",
        prompt="Explain what DeepSeek Harness is.",
        expected_task_types=EXPLANATORY_TASK_TYPES,
        required_subjects=("DeepSeek Harness",),
        forbidden_subjects=("C.A.T.T.U.S",),
        forbid_comparison=True,
        forbid_framework=True,
        notes="Must not invent a C.A.T.T.U.S comparison or a comparative rubric.",
    ),
    SemanticEvalCase(
        case_id="F_ambiguous_reference",
        label="Ambiguous reference with no named entities",
        prompt="Compare it with the other one.",
        expected_task_types=("comparative_analysis", "unknown"),
        forbidden_subjects=("DeepSeek Harness", "C.A.T.T.U.S"),
        require_ambiguity=True,
        notes="Ambiguity must be preserved, not resolved by guessing.",
    ),
    SemanticEvalCase(
        case_id="G_explicit_constraint",
        label="Analysis carrying an explicit prohibition",
        prompt="Analyze this architecture, but do not inspect tests.",
        expected_task_types=("analysis", "review", "unknown"),
        required_constraint_fragments=("do not inspect tests",),
        notes="The prohibition must survive as an explicit constraint.",
    ),
    SemanticEvalCase(
        case_id="H_output_contract",
        label="Comparison with a requested output shape",
        prompt="Compare A and B and return a Markdown table.",
        expected_task_types=("comparative_analysis",),
        require_output=True,
        allowed_output_formats=("markdown", "table"),
        notes=(
            "INPUT.1 has no literal cue for 'return a Markdown table', so the format "
            "is honestly inferred rather than claimed explicit."
        ),
    ),
    SemanticEvalCase(
        case_id="I_notes_are_not_a_rubric",
        label="A plain bullet list is not an evaluation framework",
        prompt="Here are notes:\n- foo\n- bar",
        expected_task_types=("conversation", "unknown", "question", "analysis"),
        forbid_framework=True,
        notes="Not every list is a rubric.",
    ),
    SemanticEvalCase(
        case_id="J_inferred_metadata",
        label="Useful inferred execution metadata is allowed",
        prompt=DOGFOOD_PROMPT,
        expected_task_types=("comparative_analysis",),
        required_subjects=("DeepSeek Harness", "C.A.T.T.U.S"),
        require_comparison=True,
        require_framework=True,
        required_framework_value_count=5,
        notes=(
            "Inference may add execution metadata and ambiguities so long as no "
            "explicit user commitment changes."
        ),
    ),
    SemanticEvalCase(
        case_id="K_owasp_reference",
        label="Review against a user-supplied external framework",
        prompt="Review this according to OWASP Top 10.",
        expected_task_types=("review", "analysis"),
        required_constraint_fragments=("OWASP Top 10",),
        notes=(
            "A security review may be inferred, but the OWASP reference is the "
            "user's own and must be preserved."
        ),
    ),
    SemanticEvalCase(
        case_id="L_explain_package",
        label="Explain a package, invent nothing",
        prompt="Explain package X.",
        expected_task_types=EXPLANATORY_TASK_TYPES,
        forbid_comparison=True,
        forbid_framework=True,
        forbidden_execution_requirements=(
            "repository_inspection_required",
            "local_repository_required",
            "multi_stage",
        ),
        notes="Must not invent a comparison subject, benchmark, or validation need.",
    ),
)


def find_eval_case(case_id: str) -> SemanticEvalCase:
    """Return the case with ``case_id`` or raise ``KeyError``."""
    for case in SEMANTIC_EVAL_CASES:
        if case.case_id == case_id:
            return case
    raise KeyError(f"unknown semantic eval case: {case_id!r}")


def _subject_keys(outcome: SemanticWaiterOutcome) -> list[str]:
    if outcome.contract is None:
        return []
    return [_key(value) for value in outcome.contract.subject_values()]


def _represented(needle: str, haystack: list[str]) -> bool:
    wanted = _key(needle)
    return any(wanted in candidate for candidate in haystack)


def evaluate_semantic_case(
    case: SemanticEvalCase,
    outcome: SemanticWaiterOutcome,
) -> SemanticEvalResult:
    """Check one finished outcome against one case's expectations."""
    failures: list[str] = []
    contract = outcome.contract

    if contract is None:
        return SemanticEvalResult(
            case_id=case.case_id,
            passed=False,
            status=outcome.status,
            failures=(f"no task contract was produced (status {outcome.status})",),
        )

    if case.require_preservation_pass and not contract.preservation.passed:
        failures.append(
            "preservation failed: " + "; ".join(contract.preservation.reasons[:3])
        )

    if contract.task.type not in case.expected_task_types:
        failures.append(
            f"task type {contract.task.type!r} is not one of "
            f"{list(case.expected_task_types)}"
        )

    subject_keys = _subject_keys(outcome)
    for subject in case.required_subjects:
        if not _represented(subject, subject_keys):
            failures.append(f"required subject {subject!r} is not represented")
    for subject in case.forbidden_subjects:
        if _represented(subject, subject_keys):
            failures.append(f"invented subject {subject!r} appears in the interpretation")

    comparisons = [rel for rel in contract.relationships if rel.type == "comparison"]
    if case.require_comparison and not comparisons:
        failures.append("expected a comparison relationship, found none")
    if case.forbid_comparison and comparisons:
        failures.append("invented a comparison relationship the user did not ask for")

    framework = contract.user_supplied_framework
    if case.require_framework and framework is None:
        failures.append("expected an evaluation framework, found none")
    if case.forbid_framework and framework is not None:
        failures.append("invented an evaluation framework the user did not supply")
    if framework is not None:
        if (
            case.required_framework_value_count is not None
            and len(framework.values) != case.required_framework_value_count
        ):
            failures.append(
                f"expected {case.required_framework_value_count} framework values, "
                f"found {len(framework.values)}"
            )
        rendered = [_key(value) for value in framework.values]
        for fragment in case.required_framework_fragments:
            if not _represented(fragment, rendered):
                failures.append(f"framework value {fragment!r} is not represented")

    if case.require_output and contract.requested_output is None:
        failures.append("expected a requested output format, found none")
    if contract.requested_output is not None and case.allowed_output_formats:
        if contract.requested_output.format not in case.allowed_output_formats:
            failures.append(
                f"requested output format {contract.requested_output.format!r} is not "
                f"one of {list(case.allowed_output_formats)}"
            )

    constraint_keys = [_key(item.text) for item in contract.constraints]
    for fragment in case.required_constraint_fragments:
        if not _represented(fragment, constraint_keys):
            failures.append(f"required constraint {fragment!r} is not represented")

    if case.require_ambiguity and not contract.ambiguities:
        failures.append("expected the ambiguity to be preserved, found none")

    requirements = contract.execution_requirements.as_dict()
    for flag in case.forbidden_execution_requirements:
        if requirements.get(flag) is True:
            failures.append(f"invented execution requirement {flag}")

    return SemanticEvalResult(
        case_id=case.case_id,
        passed=not failures,
        status=outcome.status,
        failures=tuple(failures),
    )


def summarize_eval_results(results: list[SemanticEvalResult]) -> dict[str, Any]:
    """Aggregate eval results into a bounded, deterministic summary."""
    passed = [result for result in results if result.passed]
    failed = [result for result in results if not result.passed]
    return {
        "phase_id": PHASE_ID,
        "total": len(results),
        "passed": len(passed),
        "failed": len(failed),
        "failed_case_ids": [result.case_id for result in failed],
        "results": [result.as_dict() for result in results],
    }
