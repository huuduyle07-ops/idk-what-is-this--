"""A.17 — Flaky Case Review (report-only).

Reads an existing benchmark report (the JSON the benchmark runner writes into
``.agent/benchmarks/``), finds the benchmark cases that were flaky, then
classifies *why* each one may be flaky using
deterministic rules, and recommends the next human action. It never fixes a
flake.

This module is pure and read-only. It reads benchmark report JSON and returns
plain dicts. It never:
  - changes benchmark cases, prompts, patch generation, or validation behavior,
  - runs benchmarks, calls any model, applies patches, or runs validation,
  - runs Dream or Project Evolution, makes network calls, promotes lessons,
    imports proposals, or launches workers.

The CLI wrapper (``scripts/create_flaky_case_review.py``) is the only piece
that writes the review artifact to disk.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "flaky_case_review"

#: Deterministic flake categories. ``unknown_flake`` is the catch-all.
FLAKY_CATEGORIES: tuple[str, ...] = (
    "model_variance_or_prompt_instability",
    "validation_timing_or_environment",
    "generated_artifact_scope_noise",
    "unexpected_mutation_noise",
    "fallback_or_provider_variance",
    "test_harness_or_report_shape_issue",
    "safety_gate_boundary_case",
    "unknown_flake",
)

#: One recommended next action per category (operator-facing).
RECOMMENDED_ACTIONS: tuple[str, ...] = (
    "add_stability_replay",
    "tighten_allowed_files_or_generated_ignore",
    "inspect_validation_environment",
    "inspect_model_fallback_path",
    "add_report_schema_guard",
    "promote_to_honeypot_or_regression_case",
    "manual_review_required",
    "no_action_yet_monitor_only",
)

#: category → recommended next action (deterministic, one per category).
_CATEGORY_ACTION: dict[str, str] = {
    "model_variance_or_prompt_instability": "add_stability_replay",
    "validation_timing_or_environment": "inspect_validation_environment",
    "generated_artifact_scope_noise": "tighten_allowed_files_or_generated_ignore",
    "unexpected_mutation_noise": "tighten_allowed_files_or_generated_ignore",
    "fallback_or_provider_variance": "inspect_model_fallback_path",
    "test_harness_or_report_shape_issue": "add_report_schema_guard",
    "safety_gate_boundary_case": "manual_review_required",
    "unknown_flake": "no_action_yet_monitor_only",
}

FLAKY_REVIEW_GUARDRAIL_NOTE = (
    "Flaky Case Review is report-only: it reads an existing benchmark report and "
    "writes a review artifact. It does not fix flaky cases, change benchmark "
    "cases, change prompts, change patch generation, change validation behavior, "
    "run benchmarks, call any model, apply patches, run Dream or Project "
    "Evolution, make network calls, promote lessons, import proposals, or launch "
    "workers."
)

_BENCHMARK_DIR = Path(".agent") / "benchmarks"
_BENCHMARK_GLOB = "benchmark_report_*.json"

#: Lowercased substrings that signal a timing / environment / toolchain flake
#: (timeout, missing command, path issue, import error, OS or process error).
_ENV_KEYWORDS: tuple[str, ...] = (
    "timeout",
    "timed out",
    "permission denied",
    "command not found",
    "is not recognized",
    "no such file",
    "cannot open",
    "modulenotfounderror",
    "importerror",
    # Node / TS import-resolution errors — same "import error" bucket as the
    # Python signals above; the spec lists import errors under environment.
    "cannot find module",
    "err_module_not_found",
    "connection refused",
    "resource temporarily unavailable",
    "ld returned",
    "winerror",
    "access is denied",
    "broken pipe",
    "address already in use",
    "filenotfounderror",
    "oserror",
    "could not find",
    "not found on path",
    "calledprocesserror",
    "econnrefused",
    "etimedout",
)

#: Lowercased substrings that signal an inconsistently-firing safety gate.
_SAFETY_KEYWORDS: tuple[str, ...] = (
    "forbidden file",
    "safety gate",
    "blocked by safety",
)

#: Human-readable phrasing for each flake-detection signal.
_SIGNAL_REASONS: dict[str, str] = {
    "explicit_flaky_flag": "the report marked the case flaky",
    "first_attempt_failed_later_passed": "an early attempt failed then a later attempt passed",
    "multiple_attempts_final_pass": "the case needed more than one attempt before it passed",
    "recovered_after_retry": "retry metadata says the case recovered after a retry",
    "named_in_report_flaky_list": "the report's flaky list names this case",
}


# ── small helpers ─────────────────────────────────────────────────────────────

def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _nonempty_list(value: Any) -> list[str]:
    if isinstance(value, list) and value:
        return [str(item) for item in value]
    return []


def _one_line(text: str, limit: int = 240) -> str:
    flat = " ".join(str(text).split())
    if len(flat) > limit:
        return flat[: limit - 1] + "…"
    return flat


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


# ── Artifact loading ──────────────────────────────────────────────────────────

def find_latest_benchmark_report(repo_path: str | Path = ".") -> Path | None:
    """Return the newest ``benchmark_report_*.json`` under ``.agent/benchmarks/``.

    The epoch timestamp in the filename sorts lexicographically, so the
    lexicographically-greatest name is the newest report. Never raises.
    """
    bench_dir = Path(repo_path) / _BENCHMARK_DIR
    if not bench_dir.is_dir():
        return None
    candidates = sorted(bench_dir.glob(_BENCHMARK_GLOB))
    return candidates[-1] if candidates else None


def load_benchmark_report(path: str | Path) -> dict[str, Any] | None:
    """Load a benchmark report JSON file. Returns None on any error.

    Accepts any JSON object; a benchmark report is a dict (usually with a
    ``results`` list). Non-dict JSON (e.g. a bare list) is rejected.
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


# ── Flaky detection ───────────────────────────────────────────────────────────

def _report_flaky_names(report: dict[str, Any]) -> set[str]:
    """Case names referenced by a report-level flaky list (not the int count)."""
    names: set[str] = set()
    if not isinstance(report, dict):
        return names
    for key in ("flaky_cases", "flaky_case_names"):
        src = report.get(key)
        if not isinstance(src, list):
            continue
        for item in src:
            if isinstance(item, str):
                names.add(item)
            elif isinstance(item, dict) and item.get("name"):
                names.add(str(item["name"]))
    return names


def _first_fail_then_pass(retry_results: Any) -> bool:
    """True if some earlier attempt failed and a later attempt passed."""
    if not isinstance(retry_results, list):
        return False
    ordered = sorted(
        (e for e in retry_results if isinstance(e, dict)),
        key=lambda e: _as_int(e.get("attempt")),
    )
    seen_fail = False
    for entry in ordered:
        success = entry.get("success")
        if success is False:
            seen_fail = True
        elif success is True and seen_fail:
            return True
    return False


def flaky_signals(result: dict[str, Any], report: dict[str, Any]) -> list[str]:
    """Return the ordered, de-duplicated list of flake signals for a result.

    A case is flaky if any signal is present.
    """
    signals: list[str] = []

    if result.get("flaky") is True:
        signals.append("explicit_flaky_flag")

    if _first_fail_then_pass(result.get("retry_results")):
        signals.append("first_attempt_failed_later_passed")

    if _as_int(result.get("attempts"), default=1) > 1 and result.get("success") is True:
        signals.append("multiple_attempts_final_pass")

    if result.get("recovered_after_retry") is True or result.get("pass_after_retry") is True:
        signals.append("recovered_after_retry")

    if str(result.get("name") or "") in _report_flaky_names(report):
        signals.append("named_in_report_flaky_list")

    seen: set[str] = set()
    ordered: list[str] = []
    for sig in signals:
        if sig not in seen:
            seen.add(sig)
            ordered.append(sig)
    return ordered


def is_flaky_result(result: dict[str, Any], report: dict[str, Any]) -> bool:
    return bool(flaky_signals(result, report))


# ── Classification ────────────────────────────────────────────────────────────

def _combined_failure_text(result: dict[str, Any]) -> str:
    """Lowercased blob of validation / log text across all attempts.

    For a flaky case the *final* output is the passing run, so the failing
    evidence lives in ``retry_results`` tails — they must be included.
    """
    parts: list[str] = [
        str(result.get("validation_output") or ""),
        str(result.get("runner_log_tail") or ""),
        str(result.get("toolchain_issue") or ""),
    ]
    for entry in result.get("retry_results") or []:
        if isinstance(entry, dict):
            parts.append(str(entry.get("validation_output_tail") or ""))
            parts.append(str(entry.get("runner_log_tail") or ""))
    return "\n".join(parts).lower()


def _has_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _distinct_models(result: dict[str, Any]) -> set[str]:
    models: set[str] = set()
    selected = result.get("selected_model")
    if selected:
        models.add(str(selected))
    for entry in result.get("retry_results") or []:
        if isinstance(entry, dict) and entry.get("selected_model"):
            models.add(str(entry["selected_model"]))
    return models


def _verdict(category: str, confidence: str, why: str) -> dict[str, Any]:
    return {
        "category": category,
        "confidence": confidence,
        "why_category": why,
        "recommended_action": _CATEGORY_ACTION[category],
    }


def classify_flaky_case(
    result: dict[str, Any],
    signals: list[str],
) -> dict[str, Any]:
    """Deterministically classify one flaky result. First matching rule wins.

    Returns a dict with ``category``, ``confidence`` (``high``/``low``),
    ``why_category``, and ``recommended_action``. No model calls.
    """
    unexpected = _nonempty_list(result.get("unexpected_mutations"))
    forbidden = _nonempty_list(result.get("touched_forbidden_files"))
    generated = _nonempty_list(result.get("generated_artifacts"))
    rollback = result.get("rollback_happened") is True
    fallback_n = _as_int(result.get("fallback_count"))
    failure_text = _combined_failure_text(result)
    env_hit = bool(result.get("toolchain_issue")) or _has_keyword(failure_text, _ENV_KEYWORDS)
    success_is_bool = isinstance(result.get("success"), bool)
    rerun_recovered = any(
        sig in signals
        for sig in (
            "first_attempt_failed_later_passed",
            "multiple_attempts_final_pass",
            "recovered_after_retry",
        )
    )

    # 1. Unexpected mutation — most serious concrete signal.
    if unexpected:
        return _verdict(
            "unexpected_mutation_noise",
            "high",
            "an unexpected mutation appeared in at least one attempt",
        )

    # 2. Safety gate boundary — a forbidden-scope / rollback / safety signal.
    if forbidden or rollback or _has_keyword(failure_text, _SAFETY_KEYWORDS):
        return _verdict(
            "safety_gate_boundary_case",
            "high" if forbidden else "low",
            "a safety gate or forbidden-scope signal fired inconsistently",
        )

    # 3. Validation timing / environment — toolchain or env keyword in output.
    if env_hit:
        return _verdict(
            "validation_timing_or_environment",
            "high",
            "validation output shows a timing, path, import, or toolchain signal",
        )

    # 4. Generated-artifact scope noise — generated files but no bad mutation.
    if generated:
        return _verdict(
            "generated_artifact_scope_noise",
            "low",
            "generated artifacts were involved but no unexpected mutation was seen",
        )

    # 5. Fallback / provider variance — a fallback happened or model changed.
    if fallback_n > 0 or len(_distinct_models(result)) > 1:
        return _verdict(
            "fallback_or_provider_variance",
            "low",
            "a model fallback or provider change occurred during the run",
        )

    # 6. Clean rerun-recovery with no other signal — model / prompt instability.
    if rerun_recovered:
        return _verdict(
            "model_variance_or_prompt_instability",
            "high",
            "failed on an early attempt then passed on rerun with no environment signal",
        )

    # 7. Flaky asserted but the attempt trail is missing or contradictory.
    if (not success_is_bool) or (
        "explicit_flaky_flag" in signals or "named_in_report_flaky_list" in signals
    ):
        return _verdict(
            "test_harness_or_report_shape_issue",
            "low",
            "the report marks the case flaky but the attempt trail is missing or ambiguous",
        )

    # 8. Catch-all.
    return _verdict(
        "unknown_flake",
        "low",
        "a flaky signal is present but no deterministic cause could be identified",
    )


# ── Per-case review entry ─────────────────────────────────────────────────────

def _final_status(result: dict[str, Any]) -> str:
    if result.get("skipped"):
        return "skip"
    success = result.get("success")
    if success is True:
        return "pass"
    if success is False:
        return "fail"
    return "unknown"


def _suite_name(result: dict[str, Any], report: dict[str, Any]) -> str | None:
    suite = result.get("suite") or result.get("suite_id")
    if not suite and isinstance(report, dict):
        suite = report.get("suite_id")
    return str(suite) if suite else None


def _attempt_summary(entry: dict[str, Any]) -> dict[str, Any]:
    tail = str(entry.get("validation_output_tail") or entry.get("runner_log_tail") or "")
    return {
        "attempt": _as_int(entry.get("attempt")),
        "success": entry.get("success"),
        "validation_ok": entry.get("validation_ok"),
        "summary": _one_line(tail, limit=300) if tail else "",
    }


def _first_failing_attempt(retry_results: Any) -> dict[str, Any] | None:
    if not isinstance(retry_results, list):
        return None
    ordered = sorted(
        (e for e in retry_results if isinstance(e, dict)),
        key=lambda e: _as_int(e.get("attempt")),
    )
    for entry in ordered:
        if entry.get("success") is False:
            return _attempt_summary(entry)
    return None


def _passing_attempt(retry_results: Any, result: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(retry_results, list):
        ordered = sorted(
            (e for e in retry_results if isinstance(e, dict)),
            key=lambda e: _as_int(e.get("attempt")),
        )
        for entry in ordered:
            if entry.get("success") is True:
                return _attempt_summary(entry)
    if result.get("success") is True:
        return {
            "attempt": _as_int(result.get("attempts"), default=1),
            "success": True,
            "validation_ok": result.get("validation_ok"),
            "summary": "",
        }
    return None


def _validation_snippet(result: dict[str, Any], first_failing: dict[str, Any] | None) -> str:
    if first_failing and first_failing.get("summary"):
        return str(first_failing["summary"])
    output = str(result.get("validation_output") or "")
    return _one_line(output[-800:], limit=300) if output else ""


def _flaky_reason(signals: list[str]) -> str:
    reasons = [_SIGNAL_REASONS[s] for s in signals if s in _SIGNAL_REASONS]
    return "; ".join(reasons) if reasons else "flaky signal detected"


def review_flaky_case(result: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """Build the full review entry for a single flaky result. Input untouched."""
    signals = flaky_signals(result, report)
    verdict = classify_flaky_case(result, signals)
    retry = result.get("retry_results")
    first_failing = _first_failing_attempt(retry)

    return {
        "name": str(result.get("name") or "(unknown)"),
        "suite_name": _suite_name(result, report),
        "final_status": _final_status(result),
        "flaky_flag": result.get("flaky") is True,
        "flaky_signals": signals,
        "flaky_reason": _flaky_reason(signals),
        "attempts": _as_int(result.get("attempts"), default=1),
        "first_failing_attempt": first_failing,
        "passing_attempt": _passing_attempt(retry, result),
        "validation_command": result.get("validation_command"),
        "validation_output_snippet": _validation_snippet(result, first_failing),
        "selected_model": result.get("selected_model"),
        "fallback_count": _as_int(result.get("fallback_count")),
        "models_by_role": result.get("models_by_role") or {},
        "changed_files": _nonempty_list(result.get("changed_files")),
        "patched_files": _nonempty_list(result.get("patched_files")),
        "generated_artifacts": _nonempty_list(result.get("generated_artifacts")),
        "unexpected_mutations": _nonempty_list(result.get("unexpected_mutations")),
        "duration_sec": result.get("duration_sec"),
        "total_tokens": result.get("total_tokens"),
        "estimated_cost_usd": result.get("estimated_cost_usd"),
        "failure_category": result.get("failure_category"),
        "failure_category_confidence": result.get("failure_category_confidence"),
        "failure_category_rule": result.get("failure_category_rule"),
        "failure_category_reason": result.get("failure_category_reason"),
        "category": verdict["category"],
        "why_category": verdict["why_category"],
        "confidence": verdict["confidence"],
        "recommended_action": verdict["recommended_action"],
    }


# ── Summary + boundaries ──────────────────────────────────────────────────────

def _boundaries() -> dict[str, bool]:
    return {
        "fixes_flakes": False,
        "alters_benchmark_cases": False,
        "runs_benchmarks": False,
        "calls_models": False,
        "applies_patches": False,
        "runs_validation": False,
        "source_report_modified": False,
        "benchmarks_run_by_tool": False,
    }


def _build_summary(total_cases: int, entries: list[dict[str, Any]]) -> dict[str, Any]:
    category_counts = {category: 0 for category in FLAKY_CATEGORIES}
    action_counts: dict[str, int] = {}
    high = 0
    low = 0
    for entry in entries:
        category_counts[entry["category"]] = category_counts.get(entry["category"], 0) + 1
        action = entry["recommended_action"]
        action_counts[action] = action_counts.get(action, 0) + 1
        if entry["confidence"] == "high":
            high += 1
        else:
            low += 1

    top_actions = [
        {"action": action, "count": count}
        for action, count in sorted(
            action_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )
    ]

    return {
        "total_cases_read": total_cases,
        "flaky_cases_found": len(entries),
        "category_counts": category_counts,
        "high_confidence_count": high,
        "low_confidence_count": low,
        "recommended_action_counts": action_counts,
        "top_recommended_actions": top_actions,
        "source_report_modified": False,
        "benchmarks_run_by_tool": False,
    }


# ── Review builders ───────────────────────────────────────────────────────────

def build_flaky_case_review(
    report: dict[str, Any],
    *,
    source_report_path: str = "",
) -> dict[str, Any]:
    """Build the complete flaky-case review from a benchmark report dict.

    Input is never mutated. A report with zero flaky cases yields a valid
    review with an empty ``flaky_cases`` list (not ``no_input``).
    """
    results = report.get("results") if isinstance(report, dict) else None
    results = results if isinstance(results, list) else []

    entries: list[dict[str, Any]] = []
    for result in results:
        if isinstance(result, dict) and is_flaky_result(result, report):
            entries.append(review_flaky_case(result, report))
    entries.sort(key=lambda entry: entry["name"])

    if results:
        total_cases = len(results)
    else:
        total_cases = _as_int(report.get("total")) if isinstance(report, dict) else 0

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": FLAKY_REVIEW_GUARDRAIL_NOTE,
        "source_report_path": source_report_path or "",
        "summary": _build_summary(total_cases, entries),
        "flaky_cases": entries,
        "boundaries": _boundaries(),
    }


def build_flaky_case_review_from_empty(
    *,
    source_report_path: str | None = None,
) -> dict[str, Any]:
    """Return a minimal valid review when no benchmark report is available."""
    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": FLAKY_REVIEW_GUARDRAIL_NOTE,
        "source_report_path": source_report_path,
        "no_input": True,
        "summary": _build_summary(0, []),
        "flaky_cases": [],
        "boundaries": _boundaries(),
    }


# ── Markdown rendering ────────────────────────────────────────────────────────

def _plain_files(files: list[str]) -> str:
    return ", ".join(f"`{_md(f)}`" for f in files) if files else "none"


def _render_summary(lines: list[str], review: dict[str, Any]) -> None:
    summary = review.get("summary") or {}
    source = review.get("source_report_path") or "(none)"
    lines += ["## Summary", ""]
    lines.append(f"- Source report: `{_md(source)}`")
    lines.append(f"- Total cases read: {summary.get('total_cases_read', 0)}")
    lines.append(f"- Flaky cases found: {summary.get('flaky_cases_found', 0)}")
    lines.append(f"- High-confidence: {summary.get('high_confidence_count', 0)}")
    lines.append(f"- Low-confidence: {summary.get('low_confidence_count', 0)}")
    lines.append("- Source report modified: false")
    lines.append("- Benchmarks run by this tool: false")
    lines.append("")

    category_counts = summary.get("category_counts") or {}
    present = [(c, n) for c, n in category_counts.items() if n]
    lines += ["**Category counts:**", ""]
    if present:
        for category, count in present:
            lines.append(f"- `{category}`: {count}")
    else:
        lines.append("- none")
    lines.append("")

    top_actions = summary.get("top_recommended_actions") or []
    lines += ["**Top recommended actions:**", ""]
    if top_actions:
        for item in top_actions:
            lines.append(f"- `{item.get('action', '')}`: {item.get('count', 0)}")
    else:
        lines.append("- none")
    lines.append("")


def _render_table(lines: list[str], cases: list[dict[str, Any]]) -> None:
    lines += ["## Flaky Cases", ""]
    if not cases:
        lines += ["_No flaky cases detected in this report._", ""]
        return
    lines.append(
        "| Case | Final | Attempts | Category | Confidence | Recommended action |"
    )
    lines.append("|---|---|---|---|---|---|")
    for case in cases:
        final = case.get("final_status", "")
        if case.get("flaky_flag"):
            final = f"{final} (flaky)"
        lines.append(
            f"| `{_md(case.get('name', ''))}` "
            f"| {final} "
            f"| {case.get('attempts', '')} "
            f"| `{case.get('category', '')}` "
            f"| {case.get('confidence', '')} "
            f"| `{case.get('recommended_action', '')}` |"
        )
    lines.append("")


def _render_case_details(lines: list[str], cases: list[dict[str, Any]]) -> None:
    lines += ["## Case Details", ""]
    if not cases:
        lines += ["_No flaky cases to detail._", ""]
        return
    for case in cases:
        lines.append(f"### `{_md(case.get('name', ''))}`")
        lines.append("")

        lines.append("- **Evidence:**")
        lines.append(f"  - Final status: {case.get('final_status', '')}")
        lines.append(f"  - Attempts: {case.get('attempts', '')}")
        if case.get("suite_name"):
            lines.append(f"  - Suite: `{_md(case['suite_name'])}`")
        lines.append(f"  - Flaky signals: {', '.join(case.get('flaky_signals') or []) or 'none'}")
        lines.append(f"  - Flaky reason: {_md(case.get('flaky_reason', ''))}")
        first_failing = case.get("first_failing_attempt")
        if first_failing:
            lines.append(
                f"  - First failing attempt: #{first_failing.get('attempt')} "
                f"(validation_ok={first_failing.get('validation_ok')})"
            )
            if first_failing.get("summary"):
                lines.append(f"    - Output: `{_md(first_failing['summary'])}`")
        passing = case.get("passing_attempt")
        if passing:
            lines.append(f"  - Passing attempt: #{passing.get('attempt')}")
        if case.get("validation_command"):
            lines.append(f"  - Validation command: `{_md(case['validation_command'])}`")
        if case.get("validation_output_snippet"):
            lines.append(f"  - Validation output: `{_md(case['validation_output_snippet'])}`")
        lines.append(
            f"  - Model: `{_md(case.get('selected_model') or 'unknown')}` "
            f"| fallbacks: {case.get('fallback_count', 0)}"
        )
        lines.append(f"  - Changed files: {_plain_files(case.get('changed_files') or [])}")
        lines.append(
            f"  - Generated artifacts: {_plain_files(case.get('generated_artifacts') or [])}"
        )
        lines.append(
            f"  - Unexpected mutations: {_plain_files(case.get('unexpected_mutations') or [])}"
        )
        lines.append(
            f"  - Duration: {case.get('duration_sec')}s "
            f"| tokens: {case.get('total_tokens')} "
            f"| est. cost: {case.get('estimated_cost_usd')}"
        )
        if case.get("failure_category"):
            lines.append(
                f"  - Existing failure_category: `{_md(case['failure_category'])}`"
                f" ({_md(case.get('failure_category_confidence') or '')})"
            )
        lines.append("")

        lines.append(
            f"- **Why this category:** {_md(case.get('why_category', ''))} → "
            f"`{case.get('category', '')}` (confidence: {case.get('confidence', '')})"
        )
        lines.append(f"- **Next action:** `{case.get('recommended_action', '')}`")
        lines.append(
            "- **What not to change yet:** Do not edit this benchmark case, its "
            "prompt, patch generation, or validation in this phase. Treat the "
            "action above as a human to-do, not an automated fix."
        )
        lines.append("")


def _render_boundaries(lines: list[str]) -> None:
    lines += ["## Boundaries", ""]
    lines += [
        "- This report does not fix flaky cases.",
        "- This report does not alter benchmark cases.",
        "- This report does not run benchmarks.",
        "- This report does not call models.",
        "- This report does not apply patches.",
        "",
    ]


def render_flaky_case_review_markdown(review: dict[str, Any]) -> str:
    """Render the review as operator-readable, read-only Markdown."""
    lines: list[str] = [
        "# Flaky Case Review",
        "",
        f"> {review.get('guardrail_note', FLAKY_REVIEW_GUARDRAIL_NOTE)}",
        "",
        "_Report-only: this reads an existing benchmark report and writes this "
        "review. Nothing is fixed, run, or applied._",
        "",
        "---",
        "",
    ]

    if review.get("no_input"):
        lines += [
            "## Summary",
            "",
            "No benchmark report was found to review.",
            "Produce a benchmark report with retry enabled (`--retry-failed 1`) "
            "first, then re-run this review.",
            "",
        ]
        _render_boundaries(lines)
        return "\n".join(lines) + "\n"

    cases = review.get("flaky_cases") or []
    _render_summary(lines, review)
    _render_table(lines, cases)
    _render_case_details(lines, cases)
    _render_boundaries(lines)
    return "\n".join(lines) + "\n"
