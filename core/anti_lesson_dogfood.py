"""Phase 11.8 - Anti-Lesson CONTROL dogfood evaluation report.

Evidence-only comparison of already-written baseline and two-key experiment
benchmark reports. No benchmark execution, model/API calls, CONTROL prompt
changes, lesson mutation, Dream, mutation oracle, patching, subprocess, Docker,
or network behavior lives in this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


REPORT_TITLE = "Anti-Lesson CONTROL Dogfood Evaluation Report"
GUARDRAIL_NOTE = (
    "This report is evidence-only. It does not enable anti-lessons, modify "
    "CONTROL prompts, run benchmarks, create lessons, promote lessons, or apply patches."
)

GREENLIGHT = "greenlight_default_off_experiment_path"
NEEDS_REVIEW = "needs_review_regression"
INCONCLUSIVE = "inconclusive_missing_matching_cases"
REJECT = "reject_correctness_regression"

MIN_SHARED_CASE_RATIO = 0.80
REJECT_PASS_RATE_DROP_POINTS = 5.0
SIGNIFICANT_USAGE_RATIO = 0.20


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _round(value: int | float | None, places: int = 4) -> int | float | None:
    if value is None:
        return None
    return round(float(value), places)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _unique_strings(value: Any) -> list[str]:
    out: list[str] = []
    for item in _as_list(value):
        if isinstance(item, str) and item not in out:
            out.append(item)
    return sorted(out)


def _results(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in _as_list(report.get("results")) if isinstance(r, dict)]


def _case_name(result: dict[str, Any]) -> str | None:
    name = result.get("name")
    return name if isinstance(name, str) and name.strip() else None


def _by_case_name(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for result in _results(report):
        name = _case_name(result)
        if name:
            out[name] = result
    return out


def _case_status(result: dict[str, Any] | None) -> str:
    if not isinstance(result, dict) or result.get("skipped") is True:
        return "inconclusive"
    if result.get("flaky") is True:
        return "flaky"
    if result.get("success") is True:
        return "passed"
    if result.get("success") is False:
        return "failed"
    return "inconclusive"


def _case_outcome(baseline_status: str, experiment_status: str) -> str:
    if baseline_status == "inconclusive" or experiment_status == "inconclusive":
        return "inconclusive"
    if baseline_status in {"failed", "flaky"} and experiment_status == "passed":
        return "improved"
    if baseline_status == "passed" and experiment_status in {"failed", "flaky"}:
        return "regressed"
    return "unchanged"


def _metric_pair(baseline: Any, experiment: Any) -> dict[str, Any]:
    base = _number(baseline)
    exp = _number(experiment)
    delta = None if base is None or exp is None else exp - base
    ratio = None
    if base not in (None, 0) and exp is not None:
        ratio = delta / base
    return {
        "baseline": base,
        "experiment": exp,
        "delta": _round(delta),
        "delta_ratio": _round(ratio),
    }


def _pass_rate(report: dict[str, Any]) -> float | None:
    total = _number(report.get("total"))
    passed = _number(report.get("passed"))
    if not total or passed is None:
        results = _results(report)
        if not results:
            return None
        total = len(results)
        passed = sum(1 for r in results if _case_status(r) == "passed")
    return float(passed) / float(total)


def _pass_rate_comparison(
    baseline: dict[str, Any],
    experiment: dict[str, Any],
) -> dict[str, Any]:
    base_rate = _pass_rate(baseline)
    exp_rate = _pass_rate(experiment)
    delta_points = None
    if base_rate is not None and exp_rate is not None:
        delta_points = (exp_rate - base_rate) * 100.0
    return {
        "baseline": _round(base_rate),
        "experiment": _round(exp_rate),
        "delta_percentage_points": _round(delta_points, 2),
    }


def _comparison_summary(
    baseline: dict[str, Any],
    experiment: dict[str, Any],
) -> dict[str, Any]:
    names = (
        "total",
        "passed",
        "failed",
        "flaky",
        "duration_sec",
        "avg_duration_sec",
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "total_estimated_cost_usd",
        "unknown_cost_calls",
        "model_calls",
        "total_fallbacks",
        "fallback_count",
    )
    return {name: _metric_pair(baseline.get(name), experiment.get(name)) for name in names}


def _case_file_summary(result: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "changed_files": _unique_strings(result.get("changed_files")),
        "patched_files": _unique_strings(result.get("patched_files")),
        "unexpected_mutations": _unique_strings(result.get("unexpected_mutations")),
    }


def _file_list_comparison(baseline: list[str], experiment: list[str]) -> dict[str, list[str]]:
    base = set(baseline)
    exp = set(experiment)
    return {
        "baseline_only": sorted(base - exp),
        "experiment_only": sorted(exp - base),
        "shared": sorted(base & exp),
    }


def _case_file_comparison(
    baseline: dict[str, Any],
    experiment: dict[str, Any],
) -> dict[str, dict[str, list[str]]]:
    baseline_files = _case_file_summary(baseline)
    experiment_files = _case_file_summary(experiment)
    return {
        name: _file_list_comparison(baseline_files[name], experiment_files[name])
        for name in baseline_files
    }


def _case_usage_delta(
    baseline: dict[str, Any],
    experiment: dict[str, Any],
) -> dict[str, Any]:
    return {
        "total_tokens": _metric_pair(baseline.get("total_tokens"), experiment.get("total_tokens")),
        "estimated_cost_usd": _metric_pair(
            baseline.get("estimated_cost_usd"),
            experiment.get("estimated_cost_usd"),
        ),
        "duration_sec": _metric_pair(baseline.get("duration_sec"), experiment.get("duration_sec")),
        "fallback_count": _metric_pair(
            baseline.get("fallback_count"),
            experiment.get("fallback_count"),
        ),
    }


def _per_case_rows(baseline: dict[str, Any], experiment: dict[str, Any]) -> list[dict[str, Any]]:
    baseline_by_name = _by_case_name(baseline)
    experiment_by_name = _by_case_name(experiment)
    rows: list[dict[str, Any]] = []
    for name in sorted(set(baseline_by_name) & set(experiment_by_name)):
        base = baseline_by_name[name]
        exp = experiment_by_name[name]
        base_status = _case_status(base)
        exp_status = _case_status(exp)
        rows.append(
            {
                "case_name": name,
                "baseline_status": base_status,
                "experiment_status": exp_status,
                "outcome": _case_outcome(base_status, exp_status),
                "baseline_files": _case_file_summary(base),
                "experiment_files": _case_file_summary(exp),
                "file_comparison": _case_file_comparison(base, exp),
                "usage_delta": _case_usage_delta(base, exp),
            }
        )
    return rows


def _case_matching(baseline: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
    baseline_names = set(_by_case_name(baseline))
    experiment_names = set(_by_case_name(experiment))
    total_baseline = int(_number(baseline.get("total")) or 0)
    total_experiment = int(_number(experiment.get("total")) or 0)
    denominator = max(total_baseline, total_experiment, len(baseline_names), len(experiment_names), 1)
    shared = baseline_names & experiment_names
    ratio = len(shared) / denominator
    return {
        "baseline_cases": len(baseline_names),
        "experiment_cases": len(experiment_names),
        "shared_cases": len(shared),
        "shared_case_ratio": _round(ratio),
        "missing_from_experiment": sorted(baseline_names - experiment_names),
        "new_in_experiment": sorted(experiment_names - baseline_names),
    }


def _is_held_out_or_hard(report: dict[str, Any], result: dict[str, Any]) -> bool:
    suite_id = str(report.get("suite_id") or "").lower()
    if "held_out" in suite_id or "held-out" in suite_id:
        return True
    return str(result.get("difficulty") or "").lower() == "hard"


def _usage_pressure_reasons(comparisons: dict[str, dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    usage_metrics = (
        "duration_sec",
        "avg_duration_sec",
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "total_estimated_cost_usd",
    )
    count_metrics = ("unknown_cost_calls", "model_calls", "total_fallbacks", "fallback_count")
    for name in usage_metrics:
        entry = comparisons.get(name) or {}
        ratio = entry.get("delta_ratio")
        baseline = entry.get("baseline")
        experiment = entry.get("experiment")
        if baseline == 0 and isinstance(experiment, (int, float)) and experiment > 0:
            reasons.append(f"{name} increased from zero to a positive value.")
            continue
        if isinstance(ratio, (int, float)) and ratio >= SIGNIFICANT_USAGE_RATIO:
            reasons.append(f"{name} increased by at least 20%.")
    for name in count_metrics:
        entry = comparisons.get(name) or {}
        ratio = entry.get("delta_ratio")
        delta = entry.get("delta")
        baseline = entry.get("baseline")
        experiment = entry.get("experiment")
        if baseline == 0 and isinstance(experiment, (int, float)) and experiment > 0:
            reasons.append(f"{name} increased from zero to a positive value.")
            continue
        if isinstance(ratio, (int, float)) and isinstance(delta, (int, float)):
            if ratio >= SIGNIFICANT_USAGE_RATIO and delta >= 1:
                reasons.append(f"{name} increased significantly.")
    return reasons


def _decision(
    baseline: dict[str, Any],
    case_matching: dict[str, Any],
    pass_rate: dict[str, Any],
    comparisons: dict[str, dict[str, Any]],
    per_case: list[dict[str, Any]],
) -> dict[str, Any]:
    reasons: list[str] = []
    if (case_matching.get("shared_case_ratio") or 0) < MIN_SHARED_CASE_RATIO:
        reasons.append("Shared case ratio is below 0.80; reports are not confidently comparable.")
        return {"status": INCONCLUSIVE, "reasons": reasons}

    delta_points = pass_rate.get("delta_percentage_points")
    if isinstance(delta_points, (int, float)) and delta_points <= -REJECT_PASS_RATE_DROP_POINTS:
        reasons.append("Experiment pass rate dropped by at least 5 percentage points.")
        return {"status": REJECT, "reasons": reasons}

    baseline_by_name = _by_case_name(baseline)
    hard_regressions: list[str] = []
    for row in per_case:
        name = row["case_name"]
        if row["outcome"] != "regressed":
            continue
        if _is_held_out_or_hard(baseline, baseline_by_name.get(name, {})):
            hard_regressions.append(name)
    if hard_regressions:
        joined = ", ".join(hard_regressions)
        reasons.append(f"Previously passing held-out/hard case regressed: {joined}.")
        if len(hard_regressions) > 1:
            return {"status": REJECT, "reasons": reasons}
        return {"status": NEEDS_REVIEW, "reasons": reasons}

    if not isinstance(delta_points, (int, float)):
        reasons.append("Pass rate delta is unavailable; review is required before greenlighting.")
        return {"status": NEEDS_REVIEW, "reasons": reasons}
    if delta_points < 0:
        reasons.append("Experiment pass rate declined but stayed below the reject threshold.")
        return {"status": NEEDS_REVIEW, "reasons": reasons}

    usage_reasons = _usage_pressure_reasons(comparisons)
    if usage_reasons:
        return {"status": NEEDS_REVIEW, "reasons": usage_reasons}

    reasons.append("Pass rate unchanged and usage/duration pressure stayed stable.")
    reasons.append("Safe to keep the default-off, explicitly requested experiment path only.")
    reasons.append("Not safe to make anti-lesson CONTROL injection default-on.")
    return {"status": GREENLIGHT, "reasons": reasons}


def build_anti_lesson_dogfood_report(
    baseline_report: dict[str, Any],
    experiment_report: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a pure evidence report from already-loaded benchmark report dicts."""
    baseline = baseline_report if isinstance(baseline_report, dict) else {}
    experiment = experiment_report if isinstance(experiment_report, dict) else {}
    comparisons = _comparison_summary(baseline, experiment)
    pass_rate = _pass_rate_comparison(baseline, experiment)
    matching = _case_matching(baseline, experiment)
    per_case = _per_case_rows(baseline, experiment)
    decision = _decision(baseline, matching, pass_rate, comparisons, per_case)
    return {
        "title": REPORT_TITLE,
        "generated_at": generated_at or _now_iso(),
        "guardrail": GUARDRAIL_NOTE,
        "baseline_report": baseline.get("filename") or baseline.get("report_path") or baseline.get("id"),
        "experiment_report": (
            experiment.get("filename") or experiment.get("report_path") or experiment.get("id")
        ),
        "summary": comparisons,
        "pass_rate": pass_rate,
        "case_matching": matching,
        "per_case": per_case,
        "decision": decision,
    }


def _markdown_cell(value: Any) -> str:
    if value is None:
        text = ""
    elif isinstance(value, float):
        text = f"{value:g}"
    elif isinstance(value, list):
        text = ", ".join(str(item) for item in value)
    else:
        text = str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")


def _metric_markdown(name: str, entry: dict[str, Any]) -> str:
    return (
        f"| {_markdown_cell(name)} | {_markdown_cell(entry.get('baseline'))} | "
        f"{_markdown_cell(entry.get('experiment'))} | {_markdown_cell(entry.get('delta'))} | "
        f"{_markdown_cell(entry.get('delta_ratio'))} |"
    )


def format_anti_lesson_dogfood_markdown(report: dict[str, Any]) -> str:
    """Format an anti-lesson dogfood report as evidence-only Markdown."""
    safe_report = report if isinstance(report, dict) else {}
    title = safe_report.get("title") or REPORT_TITLE
    guardrail = safe_report.get("guardrail") or GUARDRAIL_NOTE
    decision = safe_report.get("decision") if isinstance(safe_report.get("decision"), dict) else {}
    pass_rate = safe_report.get("pass_rate") if isinstance(safe_report.get("pass_rate"), dict) else {}
    matching = (
        safe_report.get("case_matching") if isinstance(safe_report.get("case_matching"), dict) else {}
    )
    summary = safe_report.get("summary") if isinstance(safe_report.get("summary"), dict) else {}
    per_case = safe_report.get("per_case") if isinstance(safe_report.get("per_case"), list) else []

    lines = [
        f"# {title}",
        "",
        "## Guardrail",
        "",
        str(guardrail),
        "",
        "## Decision",
        "",
        f"- Status: {_markdown_cell(decision.get('status'))}",
    ]
    for reason in _as_list(decision.get("reasons")):
        lines.append(f"- {reason}")

    lines.extend(
        [
            "",
            "## Pass Rate",
            "",
            "| baseline | experiment | delta percentage points |",
            "| --- | --- | --- |",
            (
                f"| {_markdown_cell(pass_rate.get('baseline'))} | "
                f"{_markdown_cell(pass_rate.get('experiment'))} | "
                f"{_markdown_cell(pass_rate.get('delta_percentage_points'))} |"
            ),
            "",
            "## Shared Cases",
            "",
            "| baseline cases | experiment cases | shared cases | shared case ratio |",
            "| --- | --- | --- | --- |",
            (
                f"| {_markdown_cell(matching.get('baseline_cases'))} | "
                f"{_markdown_cell(matching.get('experiment_cases'))} | "
                f"{_markdown_cell(matching.get('shared_cases'))} | "
                f"{_markdown_cell(matching.get('shared_case_ratio'))} |"
            ),
            "",
            "## Summary",
            "",
            "| metric | baseline | experiment | delta | delta ratio |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for name in sorted(summary):
        entry = summary.get(name)
        if isinstance(entry, dict):
            lines.append(_metric_markdown(name, entry))

    lines.extend(
        [
            "",
            "## Per-Case Comparison",
            "",
            "| case | baseline | experiment | outcome |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in per_case:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {_markdown_cell(row.get('case_name'))} | "
            f"{_markdown_cell(row.get('baseline_status'))} | "
            f"{_markdown_cell(row.get('experiment_status'))} | "
            f"{_markdown_cell(row.get('outcome'))} |"
        )

    return "\n".join(lines).rstrip() + "\n"
