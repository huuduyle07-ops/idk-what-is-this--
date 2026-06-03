"""Read-only failure taxonomy classifier for Phase 14.1.

This module turns already-loaded failure evidence (a benchmark case result,
an optional replay manifest/artifact summary, and optional validation output)
into a single, stable failure category using *deterministic rules only*.

It is intentionally inert: it never edits the CONTROL prompt, generates or
applies patches, runs validation or benchmarks, promotes lessons, runs Dream
automation, calls a model/API, writes to a database, spawns subprocesses,
touches Docker, makes network calls, or mutates any file. Inputs are plain
dictionaries / JSON objects; outputs are dataclasses and Markdown strings.

Nothing here is wired into live benchmark scoring; classification is purely a
reporting aid.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


# --- stable categories ------------------------------------------------------

RETRIEVAL_MISS = "retrieval_miss"
WRONG_FILE = "wrong_file"
PATCH_TOO_LARGE = "patch_too_large"
PATCH_TOO_SMALL = "patch_too_small"
VALIDATION_GAP = "validation_gap"
VALIDATION_COMMAND_FAILURE = "validation_command_failure"
MODEL_FALLBACK_INSTABILITY = "model_fallback_instability"
FORBIDDEN_FILE_TEMPTATION = "forbidden_file_temptation"
NO_PATCH_EXPECTED = "no_patch_expected"
ALGORITHM_REASONING_FAILURE = "algorithm_reasoning_failure"
TIMEOUT_OR_COST = "timeout_or_cost"
ENVIRONMENT_ISSUE = "environment_issue"
UNKNOWN = "unknown"

CATEGORIES: tuple[str, ...] = (
    RETRIEVAL_MISS,
    WRONG_FILE,
    PATCH_TOO_LARGE,
    PATCH_TOO_SMALL,
    VALIDATION_GAP,
    VALIDATION_COMMAND_FAILURE,
    MODEL_FALLBACK_INSTABILITY,
    FORBIDDEN_FILE_TEMPTATION,
    NO_PATCH_EXPECTED,
    ALGORITHM_REASONING_FAILURE,
    TIMEOUT_OR_COST,
    ENVIRONMENT_ISSUE,
    UNKNOWN,
)

GUARDRAIL_NOTE = (
    "Failure taxonomy is a read-only classifier: it only reads already-loaded "
    "evidence and never edits the CONTROL prompt, generates/applies patches, "
    "runs validation/benchmarks, promotes lessons, runs Dream, calls a "
    "model/API, writes a database, spawns subprocesses, touches Docker, makes "
    "network calls, or mutates any file."
)

# Short guardrail shown in benchmark report views (Phase 14.3). Display-only.
BENCHMARK_DISPLAY_GUARDRAIL_NOTE = (
    "Failure taxonomy is read-only and does not affect benchmark scoring, "
    "patching, validation, or lesson promotion."
)

# Keys under which a benchmark report may hold its per-case result list, in
# precedence order (newest shape first, older shapes after).
_BENCHMARK_RESULT_KEYS = ("results", "case_results", "cases")

# Deterministic thresholds (override per-case via the documented keys below).
DEFAULT_LARGE_PATCH_LINES = 150
DEFAULT_LARGE_PATCH_FILES = 8
DEFAULT_SMALL_PATCH_LINES = 2

# Lowercased substrings that indicate a broken toolchain / OS / dependency.
ENVIRONMENT_MARKERS: tuple[str, ...] = (
    "0xc0000005",
    "modulenotfounderror",
    "no module named",
    "importerror",
    "command not found",
    "is not recognized",
    "no such file or directory",
    "permission denied",
    "access is denied",
    ".dll",
    "dll load failed",
    "toolchain",
    "compiler not found",
    "cannot find -l",
    "ld returned",
)

# Lowercased substrings that indicate a timeout or cost/budget cutoff.
TIMEOUT_MARKERS: tuple[str, ...] = (
    "timed out",
    "timeout",
    "timeoutexpired",
    "deadline exceeded",
)
COST_MARKERS: tuple[str, ...] = (
    "budget exceeded",
    "cost limit",
    "token limit",
    "out of budget",
    "max cost",
)

# Lowercased substrings that indicate the validation *command* could not run.
VALIDATION_COMMAND_MARKERS: tuple[str, ...] = (
    "could not run validation",
    "validation command failed to start",
    "failed to start validation",
    "invalid validation command",
)

_CONFIDENCE: dict[str, float] = {
    ENVIRONMENT_ISSUE: 0.85,
    TIMEOUT_OR_COST: 0.80,
    VALIDATION_COMMAND_FAILURE: 0.80,
    FORBIDDEN_FILE_TEMPTATION: 0.90,
    NO_PATCH_EXPECTED: 0.85,
    RETRIEVAL_MISS: 0.70,
    WRONG_FILE: 0.75,
    PATCH_TOO_LARGE: 0.70,
    PATCH_TOO_SMALL: 0.65,
    MODEL_FALLBACK_INSTABILITY: 0.60,
    VALIDATION_GAP: 0.60,
    ALGORITHM_REASONING_FAILURE: 0.65,
    UNKNOWN: 0.20,
}

_NEXT_ACTION: dict[str, str] = {
    ENVIRONMENT_ISSUE: (
        "Fix the local toolchain/dependency/environment before re-running; "
        "this failure is not about the model's reasoning."
    ),
    TIMEOUT_OR_COST: (
        "Raise the time/cost budget or shrink the task; the run was cut off "
        "before it could finish."
    ),
    VALIDATION_COMMAND_FAILURE: (
        "Repair the case's validation command/configuration so it can execute "
        "at all."
    ),
    FORBIDDEN_FILE_TEMPTATION: (
        "Reinforce forbidden-file guardrails; the patch touched files it must "
        "never change."
    ),
    NO_PATCH_EXPECTED: (
        "This case expects no patch; teach the agent to recognise no-op "
        "situations and return without editing."
    ),
    RETRIEVAL_MISS: (
        "Improve retrieval/scout so the relevant code is surfaced before patch "
        "generation."
    ),
    WRONG_FILE: (
        "Patch landed in unrelated files; improve localization of the target "
        "before editing."
    ),
    PATCH_TOO_LARGE: (
        "Constrain patch scope; the change was far larger than the expected "
        "minimal fix."
    ),
    PATCH_TOO_SMALL: (
        "The patch was too small to plausibly fix the case; encourage a "
        "complete change."
    ),
    MODEL_FALLBACK_INSTABILITY: (
        "Investigate model fallbacks; instability across models suggests "
        "flakiness rather than a single clear cause."
    ),
    VALIDATION_GAP: (
        "Validation passed yet the case still failed; strengthen the "
        "validation so it actually catches the defect."
    ),
    ALGORITHM_REASONING_FAILURE: (
        "Right files, failing logic: focus on the algorithm/reasoning of the "
        "fix."
    ),
    UNKNOWN: (
        "Not enough signal to classify; gather more evidence (validation "
        "output, replay summary, expected files)."
    ),
}


@dataclass(frozen=True)
class FailureClassification:
    category: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    explanation: str = ""
    recommended_next_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_failure(
    case_result: dict[str, Any] | None = None,
    *,
    replay_summary: dict[str, Any] | None = None,
    validation_output: Any = None,
) -> FailureClassification:
    """Classify failure evidence into a single stable category.

    ``case_result`` is a benchmark case result dict. ``replay_summary`` is an
    optional replay manifest/artifact summary dict. ``validation_output`` is
    optional validation text (a string) or a dict with text-bearing fields.
    The inputs are never mutated. Rules are deterministic and evaluated in a
    fixed precedence; the first matching rule wins.
    """
    case = dict(case_result or {})
    replay = replay_summary if isinstance(replay_summary, dict) else None

    text = _text_blob(case, replay, validation_output)
    produced = _produced_patch(case)
    lines = _changed_lines(case)
    files = _files_touched(case)
    expected = {str(f) for f in (case.get("expected_changed_files") or [])}
    changed = {str(f) for f in (case.get("changed_files") or [])}
    forbidden = [str(f) for f in (case.get("touched_forbidden_files") or []) if f]
    fallback_count = _int(case.get("fallback_count"))
    if not fallback_count and replay is not None:
        fallback_count = _int(replay.get("fallback_count"))

    # 1. Environment issue masks everything else.
    env_hits = [m for m in ENVIRONMENT_MARKERS if m in text]
    if case.get("environment_error") is True or env_hits:
        evidence = ["environment_error flag set"] if case.get(
            "environment_error"
        ) is True else []
        evidence += [f"validation output contains {m!r}" for m in env_hits]
        return _build(ENVIRONMENT_ISSUE, evidence)

    # 2. Timeout / cost cutoff.
    time_hits = [m for m in TIMEOUT_MARKERS if m in text]
    cost_hits = [m for m in COST_MARKERS if m in text]
    if (
        case.get("timed_out") is True
        or case.get("cost_exceeded") is True
        or time_hits
        or cost_hits
    ):
        evidence = []
        if case.get("timed_out") is True:
            evidence.append("timed_out flag set")
        if case.get("cost_exceeded") is True:
            evidence.append("cost_exceeded flag set")
        evidence += [f"output contains {m!r}" for m in time_hits + cost_hits]
        return _build(TIMEOUT_OR_COST, evidence)

    # 3. The validation command itself could not run.
    cmd_hits = [m for m in VALIDATION_COMMAND_MARKERS if m in text]
    if (
        case.get("validation_command_ok") is False
        or str(case.get("validation_status") or "").lower() == "error"
        or cmd_hits
    ):
        evidence = []
        if case.get("validation_command_ok") is False:
            evidence.append("validation_command_ok is False")
        if str(case.get("validation_status") or "").lower() == "error":
            evidence.append("validation_status is 'error'")
        evidence += [f"output contains {m!r}" for m in cmd_hits]
        return _build(VALIDATION_COMMAND_FAILURE, evidence)

    # 4. The patch touched forbidden files.
    if forbidden:
        return _build(
            FORBIDDEN_FILE_TEMPTATION,
            [f"touched forbidden file: {name}" for name in forbidden],
        )

    # 5. The case expected no patch, but one was produced.
    expects_no_patch = (
        case.get("expects_patch") is False
        or case.get("no_patch_expected") is True
    )
    if expects_no_patch and produced:
        return _build(
            NO_PATCH_EXPECTED,
            ["case expects no patch but the agent produced one"],
        )

    # 6. Retrieval surfaced nothing relevant.
    if _is_retrieval_miss(case, replay):
        evidence = []
        if case.get("retrieval_hit") is False:
            evidence.append("retrieval_hit is False")
        if replay is not None:
            if _int(replay.get("retrieved_count"), default=-1) == 0:
                evidence.append("replay retrieved_count is 0")
            if replay.get("scout_snippet_count") == 0:
                evidence.append("replay scout_snippet_count is 0")
            if replay.get("expected_files_retrieved") is False:
                evidence.append("expected files were not retrieved")
        return _build(RETRIEVAL_MISS, evidence)

    # 7. A patch was produced, but in files unrelated to the target.
    if produced and expected and changed and changed.isdisjoint(expected):
        return _build(
            WRONG_FILE,
            [
                f"expected: {sorted(expected)}",
                f"changed: {sorted(changed)}",
            ],
        )

    # 8. Patch far larger than the expected minimal fix.
    large_lines = _int(case.get("patch_size_limit"), default=DEFAULT_LARGE_PATCH_LINES)
    large_files = _int(case.get("files_limit"), default=DEFAULT_LARGE_PATCH_FILES)
    if produced and (
        (lines is not None and lines > large_lines)
        or (files is not None and files > large_files)
    ):
        evidence = []
        if lines is not None and lines > large_lines:
            evidence.append(f"changed {lines} lines (> {large_lines})")
        if files is not None and files > large_files:
            evidence.append(f"touched {files} files (> {large_files})")
        return _build(PATCH_TOO_LARGE, evidence)

    # 9. Patch implausibly small for the expected change.
    min_lines = _int(case.get("min_changed_lines"), default=DEFAULT_SMALL_PATCH_LINES)
    if produced and lines is not None and 0 < lines < min_lines:
        return _build(
            PATCH_TOO_SMALL,
            [f"changed only {lines} lines (< {min_lines})"],
        )

    # 10. Model fallbacks fired — instability rather than one clear cause.
    if fallback_count > 0:
        return _build(
            MODEL_FALLBACK_INSTABILITY,
            [f"model fallback_count is {fallback_count}"],
        )

    # 11. Validation passed yet the case still failed.
    if case.get("validation_passed") is True and _case_failed(case):
        return _build(
            VALIDATION_GAP,
            ["validation passed but the case still failed"],
        )

    # 12. Right files, failing logic.
    if (
        case.get("validation_passed") is False
        and produced
        and (not expected or not changed.isdisjoint(expected))
    ):
        return _build(
            ALGORITHM_REASONING_FAILURE,
            ["correct/target files changed but validation logic failed"],
        )

    # 13. Fallthrough.
    return _build(UNKNOWN, [])


def format_failure_taxonomy_markdown(
    classification: FailureClassification,
) -> str:
    """Render a single classification as read-only markdown."""
    lines = [
        "# Failure Taxonomy Classification",
        "",
        f"- Category: {classification.category}",
        f"- Confidence: {classification.confidence:.2f}",
        f"- Recommended next action: {classification.recommended_next_action}",
        "",
        "## Explanation",
        "",
        classification.explanation or "_none_",
        "",
        "## Evidence",
        "",
    ]
    if classification.evidence:
        lines.extend(f"- {item}" for item in classification.evidence)
    else:
        lines.append("_no specific evidence_")
    lines.extend(["", f"> {GUARDRAIL_NOTE}", ""])
    return "\n".join(lines) + "\n"


def format_failure_taxonomy_report(
    classifications: Iterable[FailureClassification],
    *,
    title: str = "Failure Taxonomy Report",
) -> str:
    """Render an aggregate, count-per-category read-only markdown report."""
    items = list(classifications)
    counts: dict[str, int] = {}
    for item in items:
        counts[item.category] = counts.get(item.category, 0) + 1

    lines = [
        f"# {title}",
        "",
        f"- Total classified: {len(items)}",
        "",
        f"> {GUARDRAIL_NOTE}",
        "",
        "_Read-only report: classification only, nothing is acted upon._",
        "",
        "## Category counts",
        "",
    ]
    if counts:
        for category in CATEGORIES:
            if category in counts:
                lines.append(f"- {category}: {counts[category]}")
    else:
        lines.append("_No classifications._")

    lines.extend(["", "## Details", ""])
    if not items:
        lines.append("_No classifications._")
    for index, item in enumerate(items, start=1):
        evidence = "; ".join(item.evidence) if item.evidence else "none"
        lines.extend(
            [
                f"### {index}. {item.category} ({item.confidence:.2f})",
                "",
                f"- Explanation: {item.explanation}",
                f"- Evidence: {evidence}",
                f"- Next action: {item.recommended_next_action}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


# --- benchmark report integration (Phase 14.3, display-only) ----------------


def summarize_benchmark_failures(report: Any) -> dict[str, Any]:
    """Classify the *failing* cases of an already-loaded benchmark report.

    Purely a display aid: it reads the report, classifies each failing case
    with :func:`classify_failure`, and returns a compact summary. Passing and
    skipped cases are never classified. The ``report`` is never mutated, no
    files are written, and nothing about scoring/pass-fail is touched.
    """
    results = _benchmark_results(report)
    classifications: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    for index, case in enumerate(results):
        if not _is_failing_case(case):
            continue
        # classify_failure copies its input and never mutates it.
        result = classify_failure(case)
        counts[result.category] = counts.get(result.category, 0) + 1
        name = str(case.get("name") or "").strip() or f"case_{index}"
        classifications.append(
            {
                "name": name,
                "category": result.category,
                "confidence": result.confidence,
                "explanation": result.explanation,
                "recommended_next_action": result.recommended_next_action,
            }
        )

    ordered_counts = {
        category: counts[category]
        for category in CATEGORIES
        if category in counts
    }
    return {
        "total_cases": len(results),
        "total_failing": len(classifications),
        "counts_by_category": ordered_counts,
        "classifications": classifications,
        "guardrail_note": BENCHMARK_DISPLAY_GUARDRAIL_NOTE,
    }


def render_benchmark_taxonomy_lines(report: Any) -> list[str]:
    """Return Markdown lines for a read-only ``## Failure Taxonomy`` section.

    Shows a friendly empty state when there are no failing cases. Display-only:
    classification of already-loaded evidence, nothing is acted upon.
    """
    summary = summarize_benchmark_failures(report)
    lines = ["## Failure Taxonomy", ""]
    if not summary["classifications"]:
        lines.append("No failing cases to classify.")
        lines.append("")
        lines.append(f"> {BENCHMARK_DISPLAY_GUARDRAIL_NOTE}")
        lines.append("")
        return lines

    lines.append("Counts by category:")
    lines.append("")
    for category, count in summary["counts_by_category"].items():
        lines.append(f"- {category}: {count}")
    lines.append("")
    lines.append("| Case | Category | Confidence | Recommended next action |")
    lines.append("|---|---|---|---|")
    for item in summary["classifications"]:
        name = str(item["name"]).replace("|", "\\|")
        action = str(item["recommended_next_action"]).replace("|", "\\|")
        lines.append(
            f"| `{name}` | {item['category']} | "
            f"{item['confidence']:.2f} | {action} |"
        )
    lines.append("")
    lines.append(f"> {BENCHMARK_DISPLAY_GUARDRAIL_NOTE}")
    lines.append("")
    return lines


# --- internals --------------------------------------------------------------


def _benchmark_results(report: Any) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    for key in _BENCHMARK_RESULT_KEYS:
        value = report.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _is_failing_case(case: dict[str, Any]) -> bool:
    """A case counts as failing when it neither passed nor was skipped."""
    if case.get("skipped"):
        return False
    for key in ("success", "passed", "ok", "correct"):
        if case.get(key) is True:
            return False
    status = str(case.get("status") or "").lower()
    if status in {"pass", "passed", "ok", "success"}:
        return False
    return _case_failed(case)


def _build(category: str, evidence: list[str]) -> FailureClassification:
    base = _CONFIDENCE.get(category, 0.5)
    bump = min(0.1, 0.02 * max(0, len(evidence) - 1))
    confidence = round(min(0.99, base + bump), 4)
    return FailureClassification(
        category=category,
        confidence=confidence,
        evidence=list(evidence),
        explanation=_explanation(category, evidence),
        recommended_next_action=_NEXT_ACTION.get(category, ""),
    )


def _explanation(category: str, evidence: list[str]) -> str:
    detail = f" Signals: {'; '.join(evidence)}." if evidence else ""
    return f"Classified as {category}.{detail}"


def _text_blob(
    case: dict[str, Any],
    replay: dict[str, Any] | None,
    validation_output: Any,
) -> str:
    parts: list[str] = []
    for key in ("validation", "validation_output", "error_text", "stderr", "stdout"):
        value = case.get(key)
        if isinstance(value, str):
            parts.append(value)
    if isinstance(validation_output, str):
        parts.append(validation_output)
    elif isinstance(validation_output, dict):
        for key in ("text", "stdout", "stderr", "output", "message"):
            value = validation_output.get(key)
            if isinstance(value, str):
                parts.append(value)
    if replay is not None:
        value = replay.get("validation_output")
        if isinstance(value, str):
            parts.append(value)
    return "\n".join(parts).lower()


def _produced_patch(case: dict[str, Any]) -> bool:
    changed = case.get("changed_files")
    if isinstance(changed, list) and changed:
        return True
    lines = _changed_lines(case)
    if lines is not None and lines > 0:
        return True
    kind = str(case.get("patch_kind") or "").lower()
    if kind and kind not in {"no_patch", "none"}:
        return True
    return case.get("produced_patch") is True


def _changed_lines(case: dict[str, Any]) -> float | None:
    value = case.get("total_changed_lines")
    if value is None:
        minimality = case.get("patch_minimality")
        if isinstance(minimality, dict):
            value = minimality.get("total_changed_lines")
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _files_touched(case: dict[str, Any]) -> float | None:
    value = case.get("files_touched")
    if value is None:
        minimality = case.get("patch_minimality")
        if isinstance(minimality, dict):
            value = minimality.get("files_touched")
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _is_retrieval_miss(
    case: dict[str, Any],
    replay: dict[str, Any] | None,
) -> bool:
    if case.get("retrieval_hit") is False:
        return True
    if replay is not None:
        if _int(replay.get("retrieved_count"), default=-1) == 0:
            return True
        if replay.get("scout_snippet_count") == 0:
            return True
        if replay.get("expected_files_retrieved") is False:
            return True
    return False


def _case_failed(case: dict[str, Any]) -> bool:
    for key in ("passed", "ok", "correct", "success"):
        if case.get(key) is False:
            return True
    status = str(case.get("status") or "").lower()
    return status in {"fail", "failed", "incorrect", "error"}


def _int(value: Any, *, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return int(value)
    return default
