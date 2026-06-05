# Phase 11.8 Anti-Lesson Dogfood Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a report-only Phase 11.8 evaluator that compares baseline and two-key anti-lesson CONTROL experiment benchmark reports without changing agent behavior.

**Architecture:** Add one pure core report module and one thin CLI artifact writer. The core module accepts already-loaded benchmark report dicts, computes suite/case/usage comparisons, and formats Markdown. The CLI only resolves strict local paths, reads JSON, writes JSON/Markdown under `.agent/experiments/`, and never runs benchmarks, models, patching, Dream, or lesson mutation code.

**Tech Stack:** Python 3.13, pytest, argparse, json, pathlib, datetime. No Flask route and no network/subprocess/model/patch dependencies.

**Design doc:** `docs/superpowers/designs/2026-06-04-phase11-anti-lessons-dogfood-evaluation.md`

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Create | `core/anti_lesson_dogfood.py` | Pure report builder, decision policy, per-case comparison, Markdown formatter |
| Create | `scripts/create_anti_lesson_dogfood_report.py` | Strict local CLI path resolution, JSON read, JSON/Markdown artifact write |
| Create | `tests/test_anti_lesson_dogfood.py` | Focused tests for report logic, Markdown, CLI writes, immutability, forbidden sinks |
| Modify | `docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md` | Compact Phase 11.8 shipped note after implementation |

---

## Task 1: Core Decision Tests

**Files:**
- Create: `tests/test_anti_lesson_dogfood.py`
- Create later: `core/anti_lesson_dogfood.py`

- [ ] **Step 1: Write failing tests for top-level decisions**

Create `tests/test_anti_lesson_dogfood.py` with these imports and helpers:

```python
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core import anti_lesson_dogfood as dogfood


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _case(
    name: str,
    *,
    success: bool,
    flaky: bool = False,
    difficulty: str = "medium",
    changed_files: list[str] | None = None,
    patched_files: list[str] | None = None,
    unexpected_mutations: list[str] | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    duration_sec: float | None = None,
    fallback_count: int | None = None,
) -> dict:
    out = {
        "name": name,
        "success": success,
        "flaky": flaky,
        "difficulty": difficulty,
        "changed_files": changed_files or [],
        "patched_files": patched_files or [],
        "unexpected_mutations": unexpected_mutations or [],
    }
    if total_tokens is not None:
        out["total_tokens"] = total_tokens
    if estimated_cost_usd is not None:
        out["estimated_cost_usd"] = estimated_cost_usd
    if duration_sec is not None:
        out["duration_sec"] = duration_sec
    if fallback_count is not None:
        out["fallback_count"] = fallback_count
    return out


def _report(
    cases: list[dict],
    *,
    filename: str = "benchmark_report_test.json",
    suite_id: str = "dev_v1",
) -> dict:
    passed = sum(1 for c in cases if c.get("success") and not c.get("flaky"))
    flaky = sum(1 for c in cases if c.get("flaky"))
    failed = sum(1 for c in cases if not c.get("success") and not c.get("skipped"))
    return {
        "filename": filename,
        "suite_id": suite_id,
        "total": len(cases),
        "passed": passed,
        "failed": failed,
        "flaky": flaky,
        "duration_sec": sum(c.get("duration_sec", 0.0) for c in cases),
        "total_tokens": sum(c.get("total_tokens", 0) for c in cases),
        "total_estimated_cost_usd": sum(c.get("estimated_cost_usd", 0.0) for c in cases),
        "total_fallbacks": sum(c.get("fallback_count", 0) for c in cases),
        "results": cases,
    }
```

Add decision tests:

```python
def test_pass_rate_unchanged_greenlights_default_off_experiment_path():
    baseline = _report([_case("a", success=True), _case("b", success=False)])
    experiment = _report([_case("a", success=True), _case("b", success=False)])

    report = dogfood.build_anti_lesson_dogfood_report(
        baseline, experiment, generated_at="2026-06-04T00:00:00+00:00"
    )

    assert report["decision"]["status"] == "greenlight_default_off_experiment_path"
    assert "default-off" in " ".join(report["decision"]["reasons"])
    assert report["pass_rate"]["delta_percentage_points"] == 0.0


def test_pass_rate_drop_of_five_points_rejects_correctness_regression():
    baseline_cases = [_case(f"case_{i}", success=True) for i in range(20)]
    experiment_cases = [
        _case(f"case_{i}", success=(i != 0)) for i in range(20)
    ]

    report = dogfood.build_anti_lesson_dogfood_report(
        _report(baseline_cases), _report(experiment_cases)
    )

    assert report["decision"]["status"] == "reject_correctness_regression"
    assert report["pass_rate"]["delta_percentage_points"] == -5.0


def test_low_shared_case_ratio_is_inconclusive_but_keeps_partial_rows():
    baseline = _report([_case(f"case_{i}", success=True) for i in range(10)])
    experiment = _report([_case("case_0", success=True), _case("case_1", success=True)])

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)

    assert report["case_matching"]["shared_case_ratio"] == 0.2
    assert report["decision"]["status"] == "inconclusive_missing_matching_cases"
    assert [row["case_name"] for row in report["per_case"]] == ["case_0", "case_1"]


def test_previously_passing_hard_case_failure_needs_review():
    baseline = _report([
        _case("hard_case", success=True, difficulty="hard"),
        _case("normal_case", success=True),
    ])
    experiment = _report([
        _case("hard_case", success=False, difficulty="hard"),
        _case("normal_case", success=True),
    ])

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)

    assert report["decision"]["status"] == "needs_review_regression"
    assert any("hard_case" in reason for reason in report["decision"]["reasons"])
```

- [ ] **Step 2: Run tests to confirm they fail**

Run:

```powershell
python -m pytest tests/test_anti_lesson_dogfood.py -q
```

Expected: import failure for `core.anti_lesson_dogfood`.

- [ ] **Step 3: Commit failing tests only**

Run:

```powershell
git add tests/test_anti_lesson_dogfood.py
git commit -m "test: add anti-lesson dogfood decision tests"
```

Expected: commit contains only `tests/test_anti_lesson_dogfood.py`.

---

## Task 2: Core Report Builder

**Files:**
- Create: `core/anti_lesson_dogfood.py`
- Modify: `tests/test_anti_lesson_dogfood.py`

- [ ] **Step 1: Implement constants and scalar helpers**

Create `core/anti_lesson_dogfood.py`:

```python
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
```

- [ ] **Step 2: Implement result/status helpers**

Append:

```python
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
    if not isinstance(result, dict) or result.get("skipped"):
        return "inconclusive"
    if result.get("flaky"):
        return "flaky"
    if result.get("success") is True:
        return "passed"
    if result.get("success") is False:
        return "failed"
    return "inconclusive"


def _is_success_status(status: str) -> bool:
    return status == "passed"


def _case_outcome(baseline_status: str, experiment_status: str) -> str:
    if baseline_status == "inconclusive" or experiment_status == "inconclusive":
        return "inconclusive"
    if baseline_status in {"failed", "flaky"} and experiment_status == "passed":
        return "improved"
    if baseline_status == "passed" and experiment_status in {"failed", "flaky"}:
        return "regressed"
    return "unchanged"
```

- [ ] **Step 3: Implement summary comparison helpers**

Append:

```python
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


def _pass_rate_comparison(baseline: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
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


def _comparison_summary(baseline: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
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
```

- [ ] **Step 4: Implement per-case rows and decision policy**

Append:

```python
def _case_file_summary(result: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "changed_files": _unique_strings(result.get("changed_files")),
        "patched_files": _unique_strings(result.get("patched_files")),
        "unexpected_mutations": _unique_strings(result.get("unexpected_mutations")),
    }


def _case_usage_delta(baseline: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_tokens": _metric_pair(baseline.get("total_tokens"), experiment.get("total_tokens")),
        "estimated_cost_usd": _metric_pair(
            baseline.get("estimated_cost_usd"), experiment.get("estimated_cost_usd")
        ),
        "duration_sec": _metric_pair(baseline.get("duration_sec"), experiment.get("duration_sec")),
        "fallback_count": _metric_pair(baseline.get("fallback_count"), experiment.get("fallback_count")),
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
                "usage_delta": _case_usage_delta(base, exp),
            }
        )
    return rows


def _case_matching(baseline: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
    baseline_names = set(_by_case_name(baseline))
    experiment_names = set(_by_case_name(experiment))
    larger = max(len(baseline_names), len(experiment_names), int(baseline.get("total") or 0), int(experiment.get("total") or 0), 1)
    shared = baseline_names & experiment_names
    ratio = len(shared) / larger
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
    for name in ("duration_sec", "avg_duration_sec", "total_tokens", "input_tokens", "output_tokens", "total_estimated_cost_usd"):
        entry = comparisons.get(name) or {}
        ratio = entry.get("delta_ratio")
        if isinstance(ratio, (int, float)) and ratio >= SIGNIFICANT_USAGE_RATIO:
            reasons.append(f"{name} increased by at least 20%.")
    for name in ("unknown_cost_calls", "model_calls", "total_fallbacks", "fallback_count"):
        entry = comparisons.get(name) or {}
        ratio = entry.get("delta_ratio")
        delta = entry.get("delta")
        if isinstance(ratio, (int, float)) and isinstance(delta, (int, float)):
            if ratio >= SIGNIFICANT_USAGE_RATIO and delta >= 1:
                reasons.append(f"{name} increased significantly.")
    return reasons


def _decision(
    baseline: dict[str, Any],
    experiment: dict[str, Any],
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

    usage_reasons = _usage_pressure_reasons(comparisons)
    if usage_reasons:
        return {"status": NEEDS_REVIEW, "reasons": usage_reasons}

    reasons.append("Pass rate unchanged and usage/duration pressure stayed stable.")
    reasons.append("Safe to keep the default-off, explicitly requested experiment path only.")
    reasons.append("Not safe to make anti-lesson CONTROL injection default-on.")
    return {"status": GREENLIGHT, "reasons": reasons}
```

- [ ] **Step 5: Implement public report builder**

Append:

```python
def build_anti_lesson_dogfood_report(
    baseline_report: dict[str, Any],
    experiment_report: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    baseline = baseline_report if isinstance(baseline_report, dict) else {}
    experiment = experiment_report if isinstance(experiment_report, dict) else {}
    comparisons = _comparison_summary(baseline, experiment)
    pass_rate = _pass_rate_comparison(baseline, experiment)
    matching = _case_matching(baseline, experiment)
    per_case = _per_case_rows(baseline, experiment)
    decision = _decision(baseline, experiment, matching, pass_rate, comparisons, per_case)
    return {
        "title": REPORT_TITLE,
        "generated_at": generated_at or _now_iso(),
        "guardrail": GUARDRAIL_NOTE,
        "baseline_report": baseline.get("filename") or baseline.get("report_path") or baseline.get("id"),
        "experiment_report": experiment.get("filename") or experiment.get("report_path") or experiment.get("id"),
        "summary": comparisons,
        "pass_rate": pass_rate,
        "case_matching": matching,
        "per_case": per_case,
        "decision": decision,
    }
```

- [ ] **Step 6: Run the decision tests**

Run:

```powershell
python -m pytest tests/test_anti_lesson_dogfood.py -q
```

Expected: current Task 1 tests pass.

- [ ] **Step 7: Commit core builder**

Run:

```powershell
git add core/anti_lesson_dogfood.py tests/test_anti_lesson_dogfood.py
git commit -m "feat: add anti-lesson dogfood report builder"
```

Expected: commit includes the core module and decision tests.

---

## Task 3: File and Mutation Comparison Tests

**Files:**
- Modify: `tests/test_anti_lesson_dogfood.py`
- Modify: `core/anti_lesson_dogfood.py`

- [ ] **Step 1: Add failing tests for file comparisons and case outcomes**

Append:

```python
def test_changed_patched_and_unexpected_mutation_comparison_is_per_case():
    baseline = _report([
        _case("a", success=True, changed_files=["app.py"], patched_files=["app.py"]),
    ])
    experiment = _report([
        _case(
            "a",
            success=True,
            changed_files=["app.py", "generated.txt"],
            patched_files=["app.py"],
            unexpected_mutations=["generated.txt"],
        ),
    ])

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)
    row = report["per_case"][0]

    assert row["baseline_files"]["changed_files"] == ["app.py"]
    assert row["experiment_files"]["changed_files"] == ["app.py", "generated.txt"]
    assert row["experiment_files"]["unexpected_mutations"] == ["generated.txt"]


def test_per_case_outcome_classification_covers_improved_regressed_unchanged_and_inconclusive():
    baseline = _report([
        _case("improved", success=False),
        _case("regressed", success=True),
        _case("unchanged", success=True),
        {"name": "inconclusive", "skipped": True},
    ])
    experiment = _report([
        _case("improved", success=True),
        _case("regressed", success=False),
        _case("unchanged", success=True),
        _case("inconclusive", success=True),
    ])

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)
    outcomes = {row["case_name"]: row["outcome"] for row in report["per_case"]}

    assert outcomes == {
        "improved": "improved",
        "inconclusive": "inconclusive",
        "regressed": "regressed",
        "unchanged": "unchanged",
    }


def test_missing_optional_cost_and_token_fields_are_unknown_not_errors():
    baseline = _report([_case("a", success=True)])
    experiment = _report([_case("a", success=True)])

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)
    row = report["per_case"][0]

    assert row["usage_delta"]["estimated_cost_usd"]["baseline"] is None
    assert row["usage_delta"]["estimated_cost_usd"]["experiment"] is None
    assert report["decision"]["status"] == "greenlight_default_off_experiment_path"
```

- [ ] **Step 2: Run tests and see failures if helper shape differs**

Run:

```powershell
python -m pytest tests/test_anti_lesson_dogfood.py -q
```

Expected: failures identify missing unknown-cost handling if Task 2 helper used top-level default zeros.

- [ ] **Step 3: Update helper code to preserve missing optional per-case values**

In `core/anti_lesson_dogfood.py`, ensure `_case_usage_delta` uses `_metric_pair` directly on per-case fields without substituting `0`.

Code already matches the required form:

```python
def _case_usage_delta(baseline: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_tokens": _metric_pair(baseline.get("total_tokens"), experiment.get("total_tokens")),
        "estimated_cost_usd": _metric_pair(
            baseline.get("estimated_cost_usd"), experiment.get("estimated_cost_usd")
        ),
        "duration_sec": _metric_pair(baseline.get("duration_sec"), experiment.get("duration_sec")),
        "fallback_count": _metric_pair(baseline.get("fallback_count"), experiment.get("fallback_count")),
    }
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_anti_lesson_dogfood.py -q
```

Expected: all focused tests pass.

- [ ] **Step 5: Commit file comparison behavior**

Run:

```powershell
git add core/anti_lesson_dogfood.py tests/test_anti_lesson_dogfood.py
git commit -m "test: cover anti-lesson dogfood case comparisons"
```

Expected: commit includes updated tests and any helper fixes.

---

## Task 4: Markdown Formatter

**Files:**
- Modify: `tests/test_anti_lesson_dogfood.py`
- Modify: `core/anti_lesson_dogfood.py`

- [ ] **Step 1: Add failing Markdown test**

Append:

```python
def test_markdown_includes_guardrail_decision_and_per_case_table():
    report = dogfood.build_anti_lesson_dogfood_report(
        _report([_case("a", success=True)]),
        _report([_case("a", success=True)]),
        generated_at="2026-06-04T00:00:00+00:00",
    )

    md = dogfood.format_anti_lesson_dogfood_markdown(report)

    assert "# Anti-Lesson CONTROL Dogfood Evaluation Report" in md
    assert dogfood.GUARDRAIL_NOTE in md
    assert "greenlight_default_off_experiment_path" in md
    assert "| case | baseline | experiment | outcome |" in md
    assert "Not safe to make anti-lesson CONTROL injection default-on" in md
```

- [ ] **Step 2: Run the Markdown test and confirm failure**

Run:

```powershell
python -m pytest tests/test_anti_lesson_dogfood.py::test_markdown_includes_guardrail_decision_and_per_case_table -q
```

Expected: `AttributeError` for missing formatter.

- [ ] **Step 3: Implement Markdown formatter**

Append to `core/anti_lesson_dogfood.py`:

```python
def _md_cell(value: Any) -> str:
    text = "unknown" if value is None or value == "" else str(value)
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _fmt_metric(entry: dict[str, Any]) -> str:
    return f"{entry.get('baseline', 'unknown')} -> {entry.get('experiment', 'unknown')} (delta {entry.get('delta', 'unknown')})"


def format_anti_lesson_dogfood_markdown(report: dict[str, Any]) -> str:
    data = report if isinstance(report, dict) else {}
    decision = data.get("decision") or {}
    lines: list[str] = []
    lines.append(f"# {data.get('title') or REPORT_TITLE}")
    lines.append("")
    lines.append(f"_generated_at: {data.get('generated_at') or 'unknown'}_")
    lines.append("")
    lines.append(f"> {data.get('guardrail') or GUARDRAIL_NOTE}")
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append(f"- Status: `{decision.get('status') or 'unknown'}`")
    for reason in decision.get("reasons") or []:
        lines.append(f"- {reason}")
    lines.append("- Not safe to make anti-lesson CONTROL injection default-on.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Baseline report: `{data.get('baseline_report') or 'unknown'}`")
    lines.append(f"- Experiment report: `{data.get('experiment_report') or 'unknown'}`")
    pass_rate = data.get("pass_rate") or {}
    lines.append(
        "- Pass rate: "
        f"{pass_rate.get('baseline', 'unknown')} -> {pass_rate.get('experiment', 'unknown')} "
        f"(delta {pass_rate.get('delta_percentage_points', 'unknown')} pp)"
    )
    matching = data.get("case_matching") or {}
    lines.append(
        "- Shared cases: "
        f"{matching.get('shared_cases', 0)} / ratio {matching.get('shared_case_ratio', 'unknown')}"
    )
    lines.append("")
    lines.append("## Per-Case Comparison")
    lines.append("")
    lines.append("| case | baseline | experiment | outcome |")
    lines.append("| --- | --- | --- | --- |")
    for row in data.get("per_case") or []:
        lines.append(
            "| {case} | {base} | {exp} | {outcome} |".format(
                case=_md_cell(row.get("case_name")),
                base=_md_cell(row.get("baseline_status")),
                exp=_md_cell(row.get("experiment_status")),
                outcome=_md_cell(row.get("outcome")),
            )
        )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest tests/test_anti_lesson_dogfood.py -q
```

Expected: focused tests pass.

- [ ] **Step 5: Commit Markdown formatter**

Run:

```powershell
git add core/anti_lesson_dogfood.py tests/test_anti_lesson_dogfood.py
git commit -m "feat: render anti-lesson dogfood markdown"
```

Expected: commit includes formatter and tests.

---

## Task 5: CLI Artifact Writer

**Files:**
- Create: `scripts/create_anti_lesson_dogfood_report.py`
- Modify: `tests/test_anti_lesson_dogfood.py`

- [ ] **Step 1: Add failing CLI tests**

Append:

```python
def _write_json(path: Path, data: dict) -> bytes:
    raw = json.dumps(data, indent=2).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def test_cli_writes_json_and_markdown_without_mutating_source_reports(tmp_path):
    from scripts import create_anti_lesson_dogfood_report as cli

    repo = tmp_path
    bench = repo / ".agent" / "benchmarks"
    baseline_path = bench / "baseline.json"
    experiment_path = bench / "experiment.json"
    baseline_bytes = _write_json(baseline_path, _report([_case("a", success=True)]))
    experiment_bytes = _write_json(experiment_path, _report([_case("a", success=True)]))

    rc = cli.main([
        "--repo-path", str(repo),
        "--baseline-report", str(baseline_path),
        "--experiment-report", str(experiment_path),
    ])

    assert rc == 0
    produced_json = list((repo / ".agent" / "experiments").glob("*_anti-lesson-control-dogfood.json"))
    produced_md = list((repo / ".agent" / "experiments").glob("*_anti-lesson-control-dogfood.md"))
    assert len(produced_json) == 1
    assert len(produced_md) == 1
    assert baseline_path.read_bytes() == baseline_bytes
    assert experiment_path.read_bytes() == experiment_bytes
    saved = json.loads(produced_json[0].read_text(encoding="utf-8"))
    assert saved["decision"]["status"] == "greenlight_default_off_experiment_path"


def test_cli_rejects_source_report_outside_agent_roots(tmp_path):
    from scripts import create_anti_lesson_dogfood_report as cli

    repo = tmp_path
    outside = repo / "outside.json"
    valid = repo / ".agent" / "benchmarks" / "valid.json"
    _write_json(outside, _report([_case("a", success=True)]))
    _write_json(valid, _report([_case("a", success=True)]))

    rc = cli.main([
        "--repo-path", str(repo),
        "--baseline-report", str(outside),
        "--experiment-report", str(valid),
    ])

    assert rc == 2


def test_cli_rejects_traversal_and_non_json_output(tmp_path):
    from scripts import create_anti_lesson_dogfood_report as cli

    repo = tmp_path
    valid = repo / ".agent" / "benchmarks" / "valid.json"
    _write_json(valid, _report([_case("a", success=True)]))

    rc = cli.main([
        "--repo-path", str(repo),
        "--baseline-report", str(valid),
        "--experiment-report", str(valid),
        "--output-json", str(repo / ".agent" / "experiments" / ".." / "bad.json"),
    ])
    assert rc == 2

    rc = cli.main([
        "--repo-path", str(repo),
        "--baseline-report", str(valid),
        "--experiment-report", str(valid),
        "--output-md", str(repo / ".agent" / "experiments" / "bad.txt"),
    ])
    assert rc == 2
```

- [ ] **Step 2: Run CLI tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_anti_lesson_dogfood.py -k cli -q
```

Expected: import failure for `scripts.create_anti_lesson_dogfood_report`.

- [ ] **Step 3: Implement CLI script**

Create `scripts/create_anti_lesson_dogfood_report.py`:

```python
#!/usr/bin/env python
"""Create a Phase 11.8 anti-lesson CONTROL dogfood report.

Reads existing JSON reports only. Writes JSON/Markdown evidence artifacts under
`.agent/experiments/`. Never runs benchmarks, models, Dream, patching, or lesson
mutation code.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import anti_lesson_dogfood as dogfood


class CliError(ValueError):
    """Friendly CLI validation error."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create an anti-lesson CONTROL dogfood report.")
    parser.add_argument("--baseline-report", required=True)
    parser.add_argument("--experiment-report", required=True)
    parser.add_argument("--repo-path", default=None)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-md", default=None)
    return parser


def _repo_root(raw: str | None) -> Path:
    return Path(raw).resolve() if raw else PROJECT_ROOT


def _has_traversal(raw: str) -> bool:
    return any(part == ".." for part in raw.replace("\\", "/").split("/"))


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _resolve_source_report(raw: str, repo: Path) -> Path:
    if not raw or _has_traversal(raw):
        raise CliError("report path must be non-empty and must not contain '..'")
    path = Path(raw)
    if not path.is_absolute():
        path = repo / path
    path = path.resolve()
    if path.suffix.lower() != ".json":
        raise CliError("report path must be a .json file")
    if not path.is_file():
        raise CliError(f"report file not found: {path}")
    roots = (repo / ".agent" / "benchmarks", repo / ".agent" / "experiments")
    if not any(_inside(path, root) for root in roots):
        raise CliError("report path must resolve inside .agent/benchmarks or .agent/experiments")
    return path


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _resolve_output(raw: str | None, repo: Path, suffix: str, baseline: Path, experiment: Path) -> Path:
    default = repo / ".agent" / "experiments" / f"{_stamp()}_anti-lesson-control-dogfood{suffix}"
    if raw is None:
        path = default
    else:
        if _has_traversal(raw):
            raise CliError("output path must not contain '..'")
        path = Path(raw)
        if not path.is_absolute():
            path = repo / path
    path = path.resolve()
    if path.suffix.lower() != suffix:
        raise CliError(f"output path must end with {suffix}")
    if not _inside(path, repo / ".agent" / "experiments"):
        raise CliError("output path must resolve inside .agent/experiments")
    if path == baseline.resolve() or path == experiment.resolve():
        raise CliError("output path must not overwrite an input report")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise CliError(f"report must be a JSON object: {path}")
    data.setdefault("report_path", str(path))
    data.setdefault("filename", path.name)
    return data


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo = _repo_root(args.repo_path)
    try:
        baseline_path = _resolve_source_report(args.baseline_report, repo)
        experiment_path = _resolve_source_report(args.experiment_report, repo)
        json_path = _resolve_output(args.output_json, repo, ".json", baseline_path, experiment_path)
        md_path = _resolve_output(args.output_md, repo, ".md", baseline_path, experiment_path)
        baseline = _read_json(baseline_path)
        experiment = _read_json(experiment_path)
        report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)
        markdown = dogfood.format_anti_lesson_dogfood_markdown(report)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(markdown, encoding="utf-8")
    except (CliError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"json: {json_path}")
    print(f"markdown: {md_path}")
    print(f"decision: {report['decision']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests**

Run:

```powershell
python -m pytest tests/test_anti_lesson_dogfood.py -k cli -q
```

Expected: CLI tests pass.

- [ ] **Step 5: Commit CLI**

Run:

```powershell
git add scripts/create_anti_lesson_dogfood_report.py tests/test_anti_lesson_dogfood.py
git commit -m "feat: add anti-lesson dogfood CLI"
```

Expected: commit includes CLI and CLI tests.

---

## Task 6: Guardrail and Forbidden-Sink Tests

**Files:**
- Modify: `tests/test_anti_lesson_dogfood.py`
- Modify if tests fail: `core/anti_lesson_dogfood.py`
- Modify if tests fail: `scripts/create_anti_lesson_dogfood_report.py`

- [ ] **Step 1: Add AST and source-immutability guard tests**

Append:

```python
def _imports_and_calls(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    return imports, calls


def test_core_module_has_no_forbidden_imports_or_calls():
    imports, calls = _imports_and_calls(PROJECT_ROOT / "core" / "anti_lesson_dogfood.py")
    forbidden_imports = {
        "subprocess", "socket", "requests", "httpx", "urllib", "aiohttp",
        "openai", "docker", "benchmarks", "patching",
    }
    forbidden_calls = {
        "run_benchmarks", "build_control_prompt", "apply_patch", "generate_patch",
        "save_candidate_lesson", "promote_lesson", "block_lesson", "create_merge",
        "patch_lesson_fields", "create_mutation_oracle", "run_reverse_dream",
    }
    assert not (imports & forbidden_imports)
    assert not (calls & forbidden_calls)


def test_cli_has_no_benchmark_model_patch_or_lesson_mutation_calls():
    imports, calls = _imports_and_calls(PROJECT_ROOT / "scripts" / "create_anti_lesson_dogfood_report.py")
    assert "benchmarks" not in imports
    assert "patching" not in imports
    assert "subprocess" not in imports
    assert "openai" not in imports
    assert not (calls & {"run_benchmarks", "promote_lesson", "save_candidate_lesson", "apply_patch"})


def test_sensitive_control_and_retrieval_files_do_not_import_dogfood_module():
    for rel in ("core/control_engine.py", "core/prompter.py", "core/lesson_retrieval.py"):
        text = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
        assert "anti_lesson_dogfood" not in text
```

- [ ] **Step 2: Run guard tests**

Run:

```powershell
python -m pytest tests/test_anti_lesson_dogfood.py -k "forbidden or sensitive" -q
```

Expected: guard tests pass.

- [ ] **Step 3: Fix any forbidden imports or calls**

If the AST tests fail, remove the imported forbidden module or call. Keep `core/anti_lesson_dogfood.py` limited to `datetime` and `typing`. Keep the CLI limited to `argparse`, `json`, `sys`, `datetime`, `pathlib`, and the pure dogfood module.

- [ ] **Step 4: Commit guardrails**

Run:

```powershell
git add tests/test_anti_lesson_dogfood.py core/anti_lesson_dogfood.py scripts/create_anti_lesson_dogfood_report.py
git commit -m "test: pin anti-lesson dogfood guardrails"
```

Expected: commit contains guardrail tests and any guardrail cleanup.

---

## Task 7: Roadmap Note

**Files:**
- Modify: `docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md`

- [ ] **Step 1: Add compact roadmap note near the top refresh notes**

Add one compact dated note after the most recent Phase 11/Phase 12 refresh block near the top:

```markdown
> **2026-06-04 refresh:** Phase 11.8 Anti-Lesson CONTROL Dogfood Evaluation Report is shipped (report-only; evaluates the Phase 11.7c two-key, default-off injection path without expanding it, enabling it by default, or recommending default-on behavior). `core/anti_lesson_dogfood.py` compares existing baseline vs experiment benchmark report dicts, classifies per-case outcomes, applies the `greenlight_default_off_experiment_path` / `needs_review_regression` / `inconclusive_missing_matching_cases` / `reject_correctness_regression` decision policy, and renders Markdown with the evidence-only guardrail. `scripts/create_anti_lesson_dogfood_report.py` reads existing `.agent/benchmarks/` or `.agent/experiments/` JSON reports only and writes `.agent/experiments/<timestamp>_anti-lesson-control-dogfood.{json,md}`; source reports remain byte-identical. Guardrails: no web route, no benchmark execution, no model/API calls, no Reverse Dream execution, no mutation-oracle minting, no lesson creation/promotion/demotion, no patch generation/apply, and no changes to CONTROL, prompt, or lesson-retrieval behavior.
```

- [ ] **Step 2: Verify roadmap note does not claim default-on behavior**

Run:

```powershell
Select-String -Path 'docs\AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md' -Pattern 'Phase 11.8|default-on|greenlight_default_off_experiment_path'
```

Expected: Phase 11.8 text says no default-on behavior and uses `greenlight_default_off_experiment_path`.

- [ ] **Step 3: Commit roadmap note**

Run:

```powershell
git add docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md
git commit -m "docs: note Phase 11.8 dogfood evaluation"
```

Expected: commit includes only the roadmap note, unless user-authored roadmap edits are already present and intentionally preserved.

---

## Task 8: Final Validation

**Files:**
- Verify: `core/anti_lesson_dogfood.py`
- Verify: `scripts/create_anti_lesson_dogfood_report.py`
- Verify: `tests/test_anti_lesson_dogfood.py`
- Verify: `docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md`

- [ ] **Step 1: Run compileall**

Run:

```powershell
python -m compileall core scripts tests
```

Expected: command exits 0.

- [ ] **Step 2: Run focused Phase 11.8 tests**

Run:

```powershell
python -m pytest tests/test_anti_lesson_dogfood.py -q --basetemp .fresh_tmp_anti_lessons_11_8
```

Expected: all `tests/test_anti_lesson_dogfood.py` tests pass.

- [ ] **Step 3: Run full pytest**

Run:

```powershell
python -m pytest tests -q --basetemp .fresh_tmp_phase11_8_full
```

Expected: full suite passes. Record the exact pass count and any warnings.

- [ ] **Step 4: Run benchmark check**

Run:

```powershell
python -m benchmarks.run_benchmarks --check
```

Expected: `Checked: 50` and `Errors: 0`.

- [ ] **Step 5: Inspect git status**

Run:

```powershell
git status --short
```

Expected: only intentionally uncommitted user files remain.

- [ ] **Step 6: Final report**

Report these items to the user:

- files changed
- report helper behavior
- CLI behavior
- decision policy
- proof no benchmarks are run
- proof no CONTROL/retrieval behavior changed
- proof source reports are not mutated
- focused pytest result
- full pytest result
- benchmark `--check` result
