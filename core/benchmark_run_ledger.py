"""EVAL.1 — Live Benchmark Run Ledger (report-only).

Reads existing benchmark report artifacts (the JSON files the benchmark runner
leaves under ``.agent/benchmarks/``) and summarizes live benchmark history into a
single ledger: a deterministic run-by-run record, a per-case history, and a list of
suspected flake candidates, plus model-usage and cost roll-ups.

Core principle: EVAL.1 reads benchmark reports and writes a ledger. It does not run
benchmarks, call models, apply patches, edit benchmark cases, run validation,
contact network services, write to a database, launch workers, or merge. The input
reports are read once and never mutated.

This module is stdlib-only. ``load_benchmark_reports`` reads files and
``write_benchmark_run_ledger`` writes the ledger artifacts, but the analysis
functions (``summarize_run`` / ``build_ledger`` / ``render_benchmark_run_ledger_markdown``)
are pure and never read, write, mutate, or run anything.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "benchmark_run_ledger"

DEFAULT_INPUT_GLOB = ".agent/benchmarks/benchmark_report_*.json"

#: Output artifact filenames.
LEDGER_JSON_NAME = "benchmark_run_ledger.json"
LEDGER_MD_NAME = "benchmark_run_ledger.md"

#: The flake-classification note vocabulary. The first four are the canonical
#: classifications; the rest are informative annotations that never overclaim.
FLAKE_NOTES: tuple[str, ...] = (
    "insufficient_history",
    "single_failure_observed",
    "mixed_pass_fail_history",
    "recovered_on_later_run",
    "passed_in_single_case_rerun",
    "within_run_retry_flake",
    "repeated_failure_no_pass",
    "stable_passing",
)

BENCHMARK_RUN_LEDGER_GUARDRAIL_NOTE = (
    "Live Benchmark Run Ledger is report-only: it reads existing benchmark report "
    "artifacts and summarizes live benchmark run history, per-case history, flake "
    "candidates, model usage, and cost. It does not run benchmarks, call models, "
    "apply patches, edit benchmark cases, run validation, contact network services, "
    "write to a database, launch workers, or merge. It only reads reports and writes "
    "a ledger."
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _norm(value: Any) -> str:
    return str(value).replace("\\", "/").strip()


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalize_models(models_used: Any) -> dict[str, dict[str, int]]:
    """Read a report's ``models_used`` map into ``{role: {model: count}}``."""
    out: dict[str, dict[str, int]] = {}
    if isinstance(models_used, dict):
        for role, models in models_used.items():
            if isinstance(models, dict):
                out[str(role)] = {str(name): _as_int(count, 0) for name, count in models.items()}
            else:
                out[str(role)] = {}
    return out


def _run_scope(data: dict[str, Any]) -> tuple[str, str]:
    """Classify a report's coverage from its ``filters`` metadata.

    Returns ``(scope, filter_case)`` where scope is ``"single_case"`` (the run
    targeted one named case), ``"suite"`` (a named suite), or ``"full"``.
    """
    filters = data.get("filters")
    filters = filters if isinstance(filters, dict) else {}
    filter_case = str(filters.get("case") or "")
    filter_suite = str(filters.get("suite") or "")
    if filter_case:
        return "single_case", filter_case
    if filter_suite:
        return "suite", ""
    return "full", ""


# ── Report scanning ───────────────────────────────────────────────────────────

def find_report_files(repo_path: str | Path, input_glob: str) -> list[str]:
    """Return the benchmark report paths matching ``input_glob``, sorted.

    A relative glob is resolved under ``repo_path``; an absolute glob is used as
    given. Matching never reads file contents.
    """
    pattern = Path(input_glob)
    combined = str(pattern) if pattern.is_absolute() else str(Path(repo_path) / input_glob)
    return sorted(glob.glob(combined))


def load_benchmark_reports(repo_path: str | Path, input_glob: str = DEFAULT_INPUT_GLOB) -> dict[str, Any]:
    """Read and parse benchmark report files.

    Returns ``{entries, warnings, skipped, present, matched_count}``. ``entries``
    is a list of ``{path, data}`` for each readable JSON object. A glob that
    matches nothing yields ``present=False`` and a warning; unreadable, malformed,
    or non-object files are skipped with a warning rather than raising.
    """
    matched = find_report_files(repo_path, input_glob)
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    skipped = 0
    for path in matched:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            skipped += 1
            warnings.append(f"could not read benchmark report {_norm(path)}: {exc}")
            continue
        try:
            data = json.loads(text)
        except ValueError:
            skipped += 1
            warnings.append(f"skipped malformed benchmark report {_norm(path)}")
            continue
        if not isinstance(data, dict):
            skipped += 1
            warnings.append(f"skipped non-object benchmark report {_norm(path)}")
            continue
        entries.append({"path": path, "data": data})

    present = bool(matched)
    if not present:
        warnings.append(
            f"no benchmark reports found matching {input_glob} under {_norm(repo_path)}"
        )
    return {
        "entries": entries,
        "warnings": warnings,
        "skipped": skipped,
        "present": present,
        "matched_count": len(matched),
    }


# ── Per-run summary ───────────────────────────────────────────────────────────

def summarize_run(report_path: str, data: dict[str, Any]) -> dict[str, Any]:
    """Build one deterministic run record from a parsed benchmark report.

    Pure: it reads ``data`` and never mutates it. Older or partial reports are
    tolerated — missing aggregates are derived from the per-case results where
    possible and recorded as run-level warnings.
    """
    warnings: list[str] = []
    brain_stamp = data.get("brain_stamp")
    brain_stamp = brain_stamp if isinstance(brain_stamp, dict) else {}

    created_at = str(data.get("created_at") or brain_stamp.get("created_at") or "")
    run_id = str(
        data.get("run_id")
        or data.get("suite_id")
        or brain_stamp.get("brain_stamp_id")
        or Path(report_path).stem
    )

    raw_results = data.get("results")
    results = [r for r in raw_results if isinstance(r, dict)] if isinstance(raw_results, list) else []
    derived_passed = sum(1 for r in results if r.get("success") is True)
    derived_failed = sum(1 for r in results if r.get("success") is not True and not r.get("skipped"))

    total_cases = _as_int(data["total"], len(results)) if data.get("total") is not None else len(results)
    passed = _as_int(data["passed"], derived_passed) if data.get("passed") is not None else derived_passed
    failed = _as_int(data["failed"], derived_failed) if data.get("failed") is not None else derived_failed

    success_rate = _as_float(data.get("success_rate"))
    if success_rate is None:
        success_rate = round(passed / total_cases, 6) if total_cases else 0.0
    else:
        success_rate = round(success_rate, 6)

    failed_cases = sorted(
        {
            str(r.get("name") or "")
            for r in results
            if r.get("name") and r.get("success") is not True and not r.get("skipped")
        }
    )

    if data.get("total") is None:
        warnings.append("report has no 'total'; case count derived from results")
    if not results:
        warnings.append("report has no per-case results")

    return {
        "report_path": _norm(report_path),
        "run_id": run_id,
        "created_at": created_at,
        "total_cases": total_cases,
        "passed": passed,
        "failed": failed,
        "success_rate": success_rate,
        "failed_cases": failed_cases,
        "models_used": _normalize_models(data.get("models_used")),
        "fallbacks": _as_int(data.get("total_fallbacks"), 0),
        "tokens_total": _as_int_or_none(data.get("total_tokens")),
        "estimated_cost": _as_float(data.get("total_estimated_cost_usd")),
        "duration_seconds": _as_float(data.get("duration_sec")),
        "loaded": True,
        "warnings": warnings,
    }


# ── Case-history extraction + flake classification ────────────────────────────

def _case_observations(run_index: int, run_record: dict[str, Any], data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract one observation per case in a run (chronological by run order)."""
    scope, _filter_case = _run_scope(data)
    raw_results = data.get("results")
    results = [r for r in raw_results if isinstance(r, dict)] if isinstance(raw_results, list) else []
    observations: list[dict[str, Any]] = []
    for result in results:
        name = str(result.get("name") or "")
        if not name:
            continue
        if result.get("skipped"):
            status = "skipped"
        elif result.get("success") is True:
            status = "pass"
        else:
            status = "fail"
        observations.append(
            {
                "case_id": name,
                "run_index": run_index,
                "run_id": run_record["run_id"],
                "created_at": run_record["created_at"],
                "status": status,
                "duration_seconds": _as_float(result.get("duration_sec")),
                "language": str(result.get("language") or ""),
                "category": str(result.get("category") or ""),
                "difficulty": str(result.get("difficulty") or ""),
                "within_run_flaky": bool(result.get("flaky")),
                "scope": scope,
            }
        )
    return observations


def _recovered_on_later_run(observations: list[dict[str, Any]]) -> bool:
    """True if a FAIL is followed by a later PASS (observations in run order)."""
    seen_fail = False
    for obs in observations:
        if obs["status"] == "fail":
            seen_fail = True
        elif obs["status"] == "pass" and seen_fail:
            return True
    return False


def _classify_case(case_id: str, observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a deterministic case-history record with flake classification.

    The flake rule marks ``suspected_flaky=true`` only on real evidence: a case
    seen both passing and failing, a fail recovered by a later pass, a suite
    failure that passed in a single-case rerun, or a within-run retry flake. With
    too little evidence it does not overclaim.
    """
    pass_count = sum(1 for o in observations if o["status"] == "pass")
    fail_count = sum(1 for o in observations if o["status"] == "fail")
    seen_runs = len(observations)
    latest = observations[-1]

    has_pass = pass_count > 0
    has_fail = fail_count > 0
    within_run_flaky = any(o["within_run_flaky"] for o in observations)
    recovered = _recovered_on_later_run(observations)
    failed_in_suite = any(o["status"] == "fail" and o["scope"] in ("suite", "full") for o in observations)
    passed_in_single = any(o["status"] == "pass" and o["scope"] == "single_case" for o in observations)
    suite_fail_single_pass = failed_in_suite and passed_in_single

    notes: list[str] = []
    suspected = False

    if has_pass and has_fail:
        suspected = True
        notes.append("mixed_pass_fail_history")
        if recovered:
            notes.append("recovered_on_later_run")
        if suite_fail_single_pass:
            notes.append("passed_in_single_case_rerun")
    elif has_fail:  # failures only, no pass ever seen
        if seen_runs == 1 and fail_count == 1:
            notes.append("single_failure_observed")
        else:
            notes.append("repeated_failure_no_pass")
    elif has_pass:  # passes only
        notes.append("insufficient_history" if seen_runs == 1 else "stable_passing")

    if within_run_flaky:
        suspected = True
        if "within_run_retry_flake" not in notes:
            notes.append("within_run_retry_flake")

    return {
        "case_id": case_id,
        "seen_runs": seen_runs,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "latest_status": latest["status"],
        "latest_duration_seconds": latest["duration_seconds"],
        "languages": sorted({o["language"] for o in observations if o["language"]}),
        "categories": sorted({o["category"] for o in observations if o["category"]}),
        "difficulties": sorted({o["difficulty"] for o in observations if o["difficulty"]}),
        "suspected_flaky": suspected,
        "notes": notes,
    }


# ── Roll-ups ──────────────────────────────────────────────────────────────────

def _model_usage_summary(run_records: list[dict[str, Any]]) -> dict[str, Any]:
    by_role: dict[str, dict[str, int]] = {}
    by_model: dict[str, int] = {}
    for record in run_records:
        for role, models in record.get("models_used", {}).items():
            role_bucket = by_role.setdefault(role, {})
            for name, count in models.items():
                role_bucket[name] = role_bucket.get(name, 0) + count
                by_model[name] = by_model.get(name, 0) + count
    total = sum(by_model.values())
    return {
        "by_role": {role: dict(models) for role, models in by_role.items()},
        "by_model": dict(by_model),
        "roles": sorted(by_role),
        "models": sorted(by_model),
        "total_model_invocations": total,
    }


def _cost_summary(run_records: list[dict[str, Any]], datas: list[dict[str, Any]]) -> dict[str, Any]:
    tokens_total = 0
    input_total = 0
    output_total = 0
    cost_total = 0.0
    runs_with_tokens = 0
    runs_with_cost = 0
    total_fallbacks = 0
    for record, data in zip(run_records, datas):
        if record["tokens_total"] is not None:
            tokens_total += record["tokens_total"]
            runs_with_tokens += 1
        if record["estimated_cost"] is not None:
            cost_total += record["estimated_cost"]
            runs_with_cost += 1
        total_fallbacks += record["fallbacks"]
        input_total += _as_int(data.get("input_tokens"), 0)
        output_total += _as_int(data.get("output_tokens"), 0)
    return {
        "tokens_total": tokens_total,
        "input_tokens_total": input_total,
        "output_tokens_total": output_total,
        "estimated_cost_usd_total": round(cost_total, 6),
        "runs_with_tokens": runs_with_tokens,
        "runs_with_cost": runs_with_cost,
        "total_fallbacks": total_fallbacks,
    }


def _latest_run_summary(run_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_record["run_id"],
        "report_path": run_record["report_path"],
        "created_at": run_record["created_at"],
        "total_cases": run_record["total_cases"],
        "passed": run_record["passed"],
        "failed": run_record["failed"],
        "success_rate": run_record["success_rate"],
        "failed_cases": list(run_record["failed_cases"]),
        "duration_seconds": run_record["duration_seconds"],
        "fallbacks": run_record["fallbacks"],
        "tokens_total": run_record["tokens_total"],
        "estimated_cost": run_record["estimated_cost"],
    }


def _guardrails() -> dict[str, bool]:
    """This tool performs none of these actions."""
    return {
        "benchmark_run_performed": False,
        "model_call_performed": False,
        "patch_applied": False,
        "benchmark_case_modified": False,
        "validation_run": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "worker_launch_performed": False,
        "merge_performed": False,
    }


# ── Ledger assembly ───────────────────────────────────────────────────────────

def _sort_key(entry: dict[str, Any]) -> tuple[str, str]:
    data = entry.get("data") or {}
    brain_stamp = data.get("brain_stamp")
    brain_stamp = brain_stamp if isinstance(brain_stamp, dict) else {}
    created = str(data.get("created_at") or brain_stamp.get("created_at") or "")
    return (created, _norm(entry.get("path") or ""))


def build_ledger(
    entries: Any,
    *,
    ledger_id: str = "",
    created_at: str = "",
    repo_path: str = "",
    input_glob: str = DEFAULT_INPUT_GLOB,
    scan_warnings: Any = (),
    present: bool = True,
    matched_count: int = 0,
    limit: Any = None,
) -> dict[str, Any]:
    """Assemble the deterministic ledger report from loaded report entries.

    Pure: never mutates ``entries`` or their data. ``entries`` is a list of
    ``{path, data}``; reports are ordered by ``created_at`` then path, an optional
    ``limit`` keeps the most recent runs, and the per-case history plus flake
    candidates are derived from that ordered set.
    """
    warnings: list[str] = list(scan_warnings)
    blockers: list[str] = []

    valid = [e for e in entries if isinstance(e, dict) and isinstance(e.get("data"), dict)] if isinstance(entries, list) else []
    ordered = sorted(valid, key=_sort_key)
    total_found = len(ordered)

    if isinstance(limit, int) and limit >= 0 and total_found > limit:
        ordered = ordered[total_found - limit:]
        warnings.append(f"ledger limited to the most recent {limit} of {total_found} loaded run(s)")

    if matched_count and not ordered:
        blockers.append("no_loadable_benchmark_reports: every matched report was unreadable or malformed")

    run_records: list[dict[str, Any]] = []
    datas: list[dict[str, Any]] = []
    observations_by_case: dict[str, list[dict[str, Any]]] = {}

    for index, entry in enumerate(ordered):
        path = str(entry.get("path") or "")
        data = entry["data"]
        record = summarize_run(path, data)
        run_records.append(record)
        datas.append(data)
        for obs in _case_observations(index, record, data):
            observations_by_case.setdefault(obs["case_id"], []).append(obs)

    case_history = [
        _classify_case(case_id, observations_by_case[case_id])
        for case_id in sorted(observations_by_case)
    ]
    flake_candidates = [dict(case) for case in case_history if case["suspected_flaky"]]

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": BENCHMARK_RUN_LEDGER_GUARDRAIL_NOTE,
        "ledger_id": str(ledger_id or ""),
        "created_at": str(created_at or ""),
        "repo_path": _norm(repo_path) if repo_path else "",
        "input_glob": str(input_glob or ""),
        "run_count": len(run_records),
        "case_count": len(case_history),
        "runs": run_records,
        "case_history": case_history,
        "flake_candidates": flake_candidates,
        "latest_run_summary": _latest_run_summary(run_records[-1]) if run_records else None,
        "model_usage_summary": _model_usage_summary(run_records),
        "cost_summary": _cost_summary(run_records, datas),
        "warnings": warnings,
        "blockers": blockers,
        "guardrails": _guardrails(),
    }


# ── Markdown rendering ────────────────────────────────────────────────────────

def _fmt(value: Any) -> str:
    return "(none)" if value is None or value == "" else _md(value)


def render_benchmark_run_ledger_markdown(report: dict[str, Any]) -> str:
    """Render the ledger as one operator-readable Markdown document."""
    lines: list[str] = [
        "# Live Benchmark Run Ledger",
        "",
        f"> {report.get('guardrail_note', BENCHMARK_RUN_LEDGER_GUARDRAIL_NOTE)}",
        "",
        "_Report only: EVAL.1 reads existing benchmark report artifacts and summarizes "
        "live benchmark run history and flake candidates. It runs nothing and changes "
        "nothing._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Ledger id:** `{_fmt(report.get('ledger_id'))}`",
        f"- **Created at:** `{_fmt(report.get('created_at'))}`",
        f"- **Repo path:** `{_fmt(report.get('repo_path'))}`",
        f"- **Input glob:** `{_fmt(report.get('input_glob'))}`",
        f"- **Run count:** {report.get('run_count', 0)}",
        f"- **Case count:** {report.get('case_count', 0)}",
        f"- **Flake candidates:** {len(report.get('flake_candidates') or [])}",
        "",
    ]

    # Latest run
    lines += ["## Latest Run", ""]
    latest = report.get("latest_run_summary")
    if isinstance(latest, dict):
        lines += [
            f"- **Run id:** `{_fmt(latest.get('run_id'))}`",
            f"- **Created at:** `{_fmt(latest.get('created_at'))}`",
            f"- **Report:** `{_fmt(latest.get('report_path'))}`",
            f"- **Passed / total:** {latest.get('passed')} / {latest.get('total_cases')}"
            f" (success rate {latest.get('success_rate')})",
            f"- **Failed cases:** {', '.join(latest.get('failed_cases') or []) or '(none)'}",
            f"- **Duration (s):** {_fmt(latest.get('duration_seconds'))}",
            f"- **Fallbacks:** {latest.get('fallbacks')}",
        ]
    else:
        lines.append("_None — no benchmark reports were loaded._")
    lines.append("")

    # Run history
    lines += ["## Run History", ""]
    runs = report.get("runs") or []
    if runs:
        lines += [
            "| Run id | Created at | Passed | Total | Rate | Fallbacks | Tokens | Cost | Duration (s) |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for run in runs:
            lines.append(
                f"| `{_md(run.get('run_id'))}` | {_fmt(run.get('created_at'))} | "
                f"{run.get('passed')} | {run.get('total_cases')} | {run.get('success_rate')} | "
                f"{run.get('fallbacks')} | {_fmt(run.get('tokens_total'))} | "
                f"{_fmt(run.get('estimated_cost'))} | {_fmt(run.get('duration_seconds'))} |"
            )
    else:
        lines.append("_None._")
    lines.append("")

    # Case history
    lines += ["## Case History", ""]
    case_history = report.get("case_history") or []
    if case_history:
        lines += [
            "| Case | Runs | Pass | Fail | Latest | Flaky? | Notes |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for case in case_history:
            lines.append(
                f"| `{_md(case.get('case_id'))}` | {case.get('seen_runs')} | "
                f"{case.get('pass_count')} | {case.get('fail_count')} | "
                f"{_md(case.get('latest_status'))} | {str(bool(case.get('suspected_flaky'))).lower()} | "
                f"{_md(', '.join(case.get('notes') or []) or '-')} |"
            )
    else:
        lines.append("_None._")
    lines.append("")

    # Flake candidates
    lines += ["## Flake Candidates", ""]
    flakes = report.get("flake_candidates") or []
    if flakes:
        lines += [
            "| Case | Pass | Fail | Latest | Notes |",
            "| --- | --- | --- | --- | --- |",
        ]
        for case in flakes:
            lines.append(
                f"| `{_md(case.get('case_id'))}` | {case.get('pass_count')} | "
                f"{case.get('fail_count')} | {_md(case.get('latest_status'))} | "
                f"{_md(', '.join(case.get('notes') or []) or '-')} |"
            )
    else:
        lines.append("_None — no case shows flake evidence across the loaded runs._")
    lines.append("")

    # Model usage
    lines += ["## Model Usage", ""]
    usage = report.get("model_usage_summary") or {}
    by_role = usage.get("by_role") or {}
    if by_role:
        lines += ["| Role | Model | Invocations |", "| --- | --- | --- |"]
        for role in sorted(by_role):
            for name in sorted(by_role[role]):
                lines.append(f"| {_md(role)} | `{_md(name)}` | {by_role[role][name]} |")
    else:
        lines.append("_None recorded._")
    lines.append("")

    # Cost summary
    lines += ["## Cost Summary", ""]
    cost = report.get("cost_summary") or {}
    lines += [
        f"- **Tokens total:** {cost.get('tokens_total', 0)}",
        f"- **Input tokens:** {cost.get('input_tokens_total', 0)}",
        f"- **Output tokens:** {cost.get('output_tokens_total', 0)}",
        f"- **Estimated cost (USD):** {cost.get('estimated_cost_usd_total', 0)}",
        f"- **Runs with cost data:** {cost.get('runs_with_cost', 0)}",
        f"- **Total fallbacks:** {cost.get('total_fallbacks', 0)}",
        "",
    ]

    # Warnings
    lines += ["## Warnings", ""]
    warnings = report.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- {_md(warning)}")
    else:
        lines.append("_None._")
    lines.append("")

    # Blockers
    lines += ["## Blockers", ""]
    blockers = report.get("blockers") or []
    if blockers:
        for blocker in blockers:
            lines.append(f"- {_md(blocker)}")
    else:
        lines.append("_None._")
    lines.append("")

    # Boundaries
    lines += ["## Boundaries", ""]
    lines += [
        "- EVAL.1 does not run benchmarks.",
        "- EVAL.1 does not call models.",
        "- EVAL.1 does not apply patches.",
        "- EVAL.1 does not edit benchmark cases.",
        "- EVAL.1 does not run validation.",
        "- EVAL.1 does not contact network services.",
        "- EVAL.1 does not launch workers.",
        "- EVAL.1 is a report-only ledger.",
        "",
    ]
    return "\n".join(lines) + "\n"


# ── Writing ───────────────────────────────────────────────────────────────────

def write_benchmark_run_ledger(
    repo_path: str | Path,
    output_dir: str | Path,
    *,
    input_glob: str = DEFAULT_INPUT_GLOB,
    ledger_id: str = "",
    created_at: str = "",
    limit: Any = None,
) -> dict[str, Any]:
    """Scan benchmark reports and write the ledger JSON + Markdown.

    Returns ``{ok, json_path, md_path, report}``. Input reports are read only;
    nothing outside ``output_dir`` is written.
    """
    loaded = load_benchmark_reports(repo_path, input_glob)
    report = build_ledger(
        loaded["entries"],
        ledger_id=ledger_id,
        created_at=created_at,
        repo_path=str(repo_path),
        input_glob=input_glob,
        scan_warnings=loaded["warnings"],
        present=loaded["present"],
        matched_count=loaded["matched_count"],
        limit=limit,
    )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / LEDGER_JSON_NAME
    md_path = out_dir / LEDGER_MD_NAME

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    md_path.write_text(render_benchmark_run_ledger_markdown(report), encoding="utf-8")

    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
