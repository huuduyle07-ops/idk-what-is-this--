"""EVAL.2 — Benchmark Report Compare / Single-Case Flake Evidence (report-only).

Explains one benchmark case (or a small set of cases) across the existing benchmark
report artifacts: which reports mention the case, which runs passed or failed, which
report is considered latest and why, and what the evidence supports — a stochastic
"likely flake" or a "likely broken" case. It optionally cross-checks the EVAL.1 run
ledger but works without it.

Core principle: EVAL.2 compares existing benchmark reports and explains evidence. It
does not run benchmarks, call models, apply patches, edit benchmark cases, run
validation, contact network services, write to a database, launch workers, or merge.
The input reports are read once and never mutated, and no scoring is changed.

This module reuses the EVAL.1 report loader/summarizer and is otherwise stdlib-only.
The analysis functions (``build_case_comparison`` / ``build_flake_candidates_comparison``
/ ``render_*_markdown``) are pure; only the loaders read and the writers write.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.benchmark_run_ledger import (
    DEFAULT_INPUT_GLOB,
    load_benchmark_reports,
    summarize_run,
)


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "benchmark_report_compare"

DEFAULT_LEDGER_PATH = ".agent/eval/benchmark_run_ledger/benchmark_run_ledger.json"

ALL_FLAKE_JSON_NAME = "flake_candidates_compare.json"
ALL_FLAKE_MD_NAME = "flake_candidates_compare.md"

#: Conservative single-value classification vocabulary.
CLASSIFICATIONS: tuple[str, ...] = (
    "no_evidence",
    "single_pass_only",
    "single_failure_only",
    "mixed_pass_fail_history",
    "recovered_on_later_run",
    "regressed_after_pass",
    "likely_flake",
    "likely_broken",
    "insufficient_history",
)

#: Evidence-label vocabulary (a comparison may carry several).
EVIDENCE_LABELS: tuple[str, ...] = (
    "seen_in_full_suite",
    "seen_in_single_case_run",
    "failed_in_full_suite",
    "passed_in_full_suite",
    "failed_in_single_case_run",
    "passed_in_single_case_run",
    "mixed_pass_fail_history",
    "recovered_on_later_run",
    "regressed_after_pass",
    "within_run_retry_flake",
    "latest_is_pass",
    "latest_is_fail",
    "ledger_flake_candidate",
)

#: Ordering sources, highest priority first. ``modified_time`` is recognized but
#: deliberately not consulted by default so output stays deterministic and
#: machine-independent; the resolver emits ``created_at`` or ``path``.
ORDERING_SOURCES: tuple[str, ...] = ("created_at", "modified_time", "path")

BENCHMARK_REPORT_COMPARE_GUARDRAIL_NOTE = (
    "Benchmark Report Compare is report-only: it reads existing benchmark report "
    "artifacts and explains a case across them — which reports mention it, which runs "
    "passed or failed, which report is latest, and whether the evidence supports a "
    "likely flake or a likely broken case. It does not run benchmarks, call models, "
    "apply patches, edit benchmark cases, run validation, contact network services, "
    "write to a database, launch workers, or merge. It only reads reports and writes "
    "a comparison."
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _norm(value: Any) -> str:
    return str(value).replace("\\", "/").strip()


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _first_line(text: str) -> str:
    for line in str(text).splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _suite_scope(data: dict[str, Any]) -> str:
    """Classify a report's coverage from its ``filters`` metadata."""
    filters = data.get("filters")
    filters = filters if isinstance(filters, dict) else {}
    if str(filters.get("case") or ""):
        return "single_case"
    if str(filters.get("suite") or ""):
        return "suite"
    return "full"


def _find_case_result(data: dict[str, Any], case_id: str) -> dict[str, Any] | None:
    raw_results = data.get("results")
    if not isinstance(raw_results, list):
        return None
    for result in raw_results:
        if isinstance(result, dict) and str(result.get("name") or "") == case_id:
            return result
    return None


def _case_status(result: dict[str, Any]) -> str:
    if result.get("skipped"):
        return "skipped"
    if result.get("success") is True:
        return "pass"
    return "fail"


def _failure_summary(result: dict[str, Any]) -> str:
    if result.get("success") is True or result.get("skipped"):
        return ""
    parts: list[str] = []
    for key in ("failure_kind_display", "failure_cause", "failure_category"):
        value = result.get(key)
        if value:
            parts.append(str(value))
    evidence = result.get("failure_evidence") or result.get("validation_output") or ""
    if evidence:
        parts.append(_first_line(str(evidence))[:200])
    return " | ".join(parts)[:400]


# ── Ledger cross-check ────────────────────────────────────────────────────────

def load_ledger(repo_path: str | Path, ledger_path: str | None) -> dict[str, Any]:
    """Read the optional EVAL.1 ledger.

    Returns ``{present, path, flake_candidate_ids, case_notes, warnings}``. A missing
    or malformed ledger is a warning only — EVAL.2 works without it.
    """
    rel = ledger_path or DEFAULT_LEDGER_PATH
    candidate = Path(rel)
    full = candidate if candidate.is_absolute() else (Path(repo_path) / rel)
    out: dict[str, Any] = {
        "present": False,
        "path": _norm(full),
        "flake_candidate_ids": [],
        "case_notes": {},
        "warnings": [],
    }
    if not full.exists():
        out["warnings"].append(f"EVAL.1 ledger not found at {_norm(full)} (cross-check skipped)")
        return out
    try:
        data = json.loads(full.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        out["warnings"].append(f"EVAL.1 ledger at {_norm(full)} could not be read (cross-check skipped)")
        return out
    if not isinstance(data, dict):
        out["warnings"].append(f"EVAL.1 ledger at {_norm(full)} is not an object (cross-check skipped)")
        return out

    ids: list[str] = []
    notes: dict[str, list[str]] = {}
    for entry in data.get("flake_candidates") or []:
        if isinstance(entry, dict):
            cid = str(entry.get("case_id") or "")
            if cid:
                ids.append(cid)
                notes[cid] = list(entry.get("notes") or [])
    out["present"] = True
    out["flake_candidate_ids"] = sorted(set(ids))
    out["case_notes"] = notes
    return out


# ── Per-report view + ordering ────────────────────────────────────────────────

def _report_view(path: str, data: dict[str, Any], case_id: str) -> dict[str, Any]:
    """Summarize one report for one case: run-level facts + the case observation."""
    run = summarize_run(path, data)
    created = run["created_at"]
    norm_path = run["report_path"]
    ordering_source = "created_at" if created else "path"
    ordering_value = created if created else norm_path
    timestamp = created  # ISO strings sort chronologically; "" sorts oldest
    ordering_key = f"{timestamp}|{norm_path}"

    result = _find_case_result(data, case_id)
    scope = _suite_scope(data)

    observation: dict[str, Any] | None = None
    if result is not None:
        notes: list[str] = [f"scope:{scope}"]
        if result.get("flaky"):
            notes.append("within_run_retry")
        observation = {
            "report_path": norm_path,
            "run_id": run["run_id"],
            "created_at": created,
            "ordering_key": ordering_key,
            "suite_scope": scope,
            "case_id": case_id,
            "status": _case_status(result),
            "passed": run["passed"],
            "failed": run["failed"],
            "duration_seconds": _as_float(result.get("duration_sec")),
            "models_used": run["models_used"],
            "fallbacks": run["fallbacks"],
            "tokens_total": run["tokens_total"],
            "estimated_cost": run["estimated_cost"],
            "failure_summary": _failure_summary(result),
            "notes": notes,
        }

    return {
        "report_path": norm_path,
        "run_id": run["run_id"],
        "created_at": created,
        "ordering_source": ordering_source,
        "ordering_value": ordering_value,
        "ordering_key": ordering_key,
        "_sort_key": (timestamp, norm_path),
        "contains_case": observation is not None,
        "observation": observation,
    }


def _recovered_on_later_run(timeline: list[dict[str, Any]]) -> bool:
    seen_fail = False
    for obs in timeline:
        if obs["status"] == "fail":
            seen_fail = True
        elif obs["status"] == "pass" and seen_fail:
            return True
    return False


def _regressed_after_pass(timeline: list[dict[str, Any]]) -> bool:
    seen_pass = False
    for obs in timeline:
        if obs["status"] == "pass":
            seen_pass = True
        elif obs["status"] == "fail" and seen_pass:
            return True
    return False


# ── Evidence + classification ─────────────────────────────────────────────────

def _evidence_labels(timeline: list[dict[str, Any]], ledger_flake: bool) -> list[str]:
    if not timeline:
        return ["ledger_flake_candidate"] if ledger_flake else []
    statuses = [o["status"] for o in timeline]
    has_pass = "pass" in statuses
    has_fail = "fail" in statuses
    labels: list[str] = []

    def add(label: str) -> None:
        if label not in labels:
            labels.append(label)

    for obs in timeline:
        scope = obs["suite_scope"]
        status = obs["status"]
        if scope == "full":
            add("seen_in_full_suite")
            if status == "fail":
                add("failed_in_full_suite")
            elif status == "pass":
                add("passed_in_full_suite")
        elif scope == "single_case":
            add("seen_in_single_case_run")
            if status == "fail":
                add("failed_in_single_case_run")
            elif status == "pass":
                add("passed_in_single_case_run")

    if has_pass and has_fail:
        add("mixed_pass_fail_history")
    if _recovered_on_later_run(timeline):
        add("recovered_on_later_run")
    if _regressed_after_pass(timeline):
        add("regressed_after_pass")
    if any("within_run_retry" in (o.get("notes") or []) for o in timeline):
        add("within_run_retry_flake")

    latest = timeline[-1]["status"]
    if latest == "pass":
        add("latest_is_pass")
    elif latest == "fail":
        add("latest_is_fail")

    if ledger_flake:
        add("ledger_flake_candidate")
    return labels


def _classify(timeline: list[dict[str, Any]], ledger_flake: bool) -> tuple[str, str]:
    if not timeline:
        if ledger_flake:
            return "likely_flake", "case not in the current report window, but the EVAL.1 ledger flags it as a flake candidate"
        return "no_evidence", "case not found in any loaded benchmark report"

    statuses = [o["status"] for o in timeline]
    has_pass = "pass" in statuses
    has_fail = "fail" in statuses
    fail_count = statuses.count("fail")

    if not has_pass and not has_fail:
        return "insufficient_history", "case seen only with skipped or non-pass/fail status"
    if has_pass and has_fail:
        return "likely_flake", "mixed pass/fail evidence for the same case across reports"
    if has_fail:  # only failures, no pass
        if ledger_flake:
            return "likely_flake", "reports show only failures, but the EVAL.1 ledger records a recovery / flake"
        if fail_count >= 2:
            return "likely_broken", "repeated failures with no later pass evidence"
        return "single_failure_only", "one failure observed and no pass"
    return "single_pass_only", "only pass observations and no failure"


# ── Comparison assembly ───────────────────────────────────────────────────────

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


def _ledger_reference(case_id: str, ledger_info: dict[str, Any] | None) -> dict[str, Any]:
    if not ledger_info:
        return {
            "present": False,
            "path": "",
            "case_is_flake_candidate": False,
            "ledger_notes": [],
            "flake_candidate_count": 0,
        }
    ids = ledger_info.get("flake_candidate_ids") or []
    return {
        "present": bool(ledger_info.get("present")),
        "path": str(ledger_info.get("path") or ""),
        "case_is_flake_candidate": case_id in ids,
        "ledger_notes": list((ledger_info.get("case_notes") or {}).get(case_id, [])),
        "flake_candidate_count": len(ids),
    }


def build_case_comparison(
    entries: Any,
    case_id: str,
    *,
    ledger_info: dict[str, Any] | None = None,
    comparison_id: str = "",
    created_at: str = "",
    repo_path: str = "",
    input_glob: str = DEFAULT_INPUT_GLOB,
    matched_count: int = 0,
    skipped_count: int = 0,
    scan_warnings: Any = (),
    limit: Any = None,
) -> dict[str, Any]:
    """Build a deterministic single-case comparison report.

    Pure: never mutates ``entries`` or their data. Reports are ordered by
    ``created_at`` then path, an optional ``limit`` keeps the most recent reports,
    and the case timeline plus classification are derived from that ordered set.
    """
    warnings: list[str] = list(scan_warnings)
    blockers: list[str] = []

    valid = [e for e in entries if isinstance(e, dict) and isinstance(e.get("data"), dict)] if isinstance(entries, list) else []
    views = [_report_view(str(e.get("path") or ""), e["data"], case_id) for e in valid]
    views.sort(key=lambda v: v["_sort_key"])

    total_loaded = len(views)
    if isinstance(limit, int) and limit >= 0 and total_loaded > limit:
        views = views[total_loaded - limit:]
        warnings.append(f"comparison limited to the most recent {limit} of {total_loaded} loaded report(s)")

    loaded_count = len(views)
    timeline = [v["observation"] for v in views if v["contains_case"]]

    # The latest report that contains the case (timeline is sorted ascending).
    latest_key = timeline[-1]["ordering_key"] if timeline else None
    report_ordering: list[dict[str, Any]] = []
    for view in views:
        report_ordering.append(
            {
                "report_path": view["report_path"],
                "run_id": view["run_id"],
                "created_at": view["created_at"],
                "ordering_source": view["ordering_source"],
                "ordering_value": view["ordering_value"],
                "ordering_key": view["ordering_key"],
                "contains_case": view["contains_case"],
                "is_latest": bool(view["contains_case"] and view["ordering_key"] == latest_key),
            }
        )

    ledger_flake = bool(ledger_info) and case_id in (ledger_info.get("flake_candidate_ids") or [])
    classification, classification_reason = _classify(timeline, ledger_flake)
    evidence_labels = _evidence_labels(timeline, ledger_flake)
    status_counts = {
        "pass": sum(1 for o in timeline if o["status"] == "pass"),
        "fail": sum(1 for o in timeline if o["status"] == "fail"),
        "skipped": sum(1 for o in timeline if o["status"] == "skipped"),
    }
    latest_observation = dict(timeline[-1]) if timeline else None

    if not timeline:
        warnings.append(f"case '{case_id}' was not found in any loaded benchmark report")

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": BENCHMARK_REPORT_COMPARE_GUARDRAIL_NOTE,
        "comparison_id": str(comparison_id or ""),
        "created_at": str(created_at or ""),
        "repo_path": _norm(repo_path) if repo_path else "",
        "input_glob": str(input_glob or ""),
        "case_id": case_id,
        "report_count": matched_count or loaded_count,
        "matched_report_count": matched_count or loaded_count,
        "loaded_report_count": loaded_count,
        "skipped_report_count": skipped_count,
        "report_ordering": report_ordering,
        "case_timeline": timeline,
        "latest_observation": latest_observation,
        "status_counts": status_counts,
        "evidence_labels": evidence_labels,
        "classification": classification,
        "classification_reason": classification_reason,
        "ledger_reference": _ledger_reference(case_id, ledger_info),
        "warnings": warnings,
        "blockers": blockers,
        "guardrails": _guardrails(),
    }


def _all_case_ids(entries: list[dict[str, Any]]) -> list[str]:
    ids: set[str] = set()
    for entry in entries:
        results = entry["data"].get("results")
        if isinstance(results, list):
            for result in results:
                if isinstance(result, dict):
                    name = str(result.get("name") or "")
                    if name:
                        ids.add(name)
    return sorted(ids)


def _is_flake_candidate(comparison: dict[str, Any]) -> bool:
    labels = comparison.get("evidence_labels") or []
    return (
        comparison.get("classification") == "likely_flake"
        or "ledger_flake_candidate" in labels
        or "within_run_retry_flake" in labels
    )


def build_flake_candidates_comparison(
    entries: Any,
    *,
    ledger_info: dict[str, Any] | None = None,
    comparison_id: str = "",
    created_at: str = "",
    repo_path: str = "",
    input_glob: str = DEFAULT_INPUT_GLOB,
    matched_count: int = 0,
    skipped_count: int = 0,
    scan_warnings: Any = (),
    limit: Any = None,
) -> dict[str, Any]:
    """Build an aggregate comparison over every suspected flake candidate case.

    Candidates come from the union of the EVAL.1 ledger's flake candidates and any
    case the reports themselves show as flake-leaning (mixed pass/fail or a
    within-run retry flake). Each candidate gets a full single-case comparison.
    """
    warnings: list[str] = list(scan_warnings)
    valid = [e for e in entries if isinstance(e, dict) and isinstance(e.get("data"), dict)] if isinstance(entries, list) else []

    ledger_ids = list((ledger_info or {}).get("flake_candidate_ids") or [])
    candidate_ids = sorted(set(_all_case_ids(valid)) | set(ledger_ids))

    comparisons: list[dict[str, Any]] = []
    for case_id in candidate_ids:
        comparison = build_case_comparison(
            valid,
            case_id,
            ledger_info=ledger_info,
            comparison_id=comparison_id,
            created_at=created_at,
            repo_path=repo_path,
            input_glob=input_glob,
            matched_count=matched_count,
            skipped_count=skipped_count,
            limit=limit,
        )
        if _is_flake_candidate(comparison):
            comparisons.append(comparison)

    comparisons.sort(key=lambda c: c["case_id"])
    loaded_count = len(valid)
    if not comparisons:
        warnings.append("no flake candidate cases were found in the loaded reports or ledger")

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": BENCHMARK_REPORT_COMPARE_GUARDRAIL_NOTE,
        "mode": "all_flake_candidates",
        "comparison_id": str(comparison_id or ""),
        "created_at": str(created_at or ""),
        "repo_path": _norm(repo_path) if repo_path else "",
        "input_glob": str(input_glob or ""),
        "report_count": matched_count or loaded_count,
        "matched_report_count": matched_count or loaded_count,
        "loaded_report_count": loaded_count,
        "skipped_report_count": skipped_count,
        "case_ids": [c["case_id"] for c in comparisons],
        "case_count": len(comparisons),
        "comparisons": comparisons,
        "ledger_reference": {
            "present": bool((ledger_info or {}).get("present")),
            "path": str((ledger_info or {}).get("path") or ""),
            "flake_candidate_count": len(ledger_ids),
        },
        "warnings": warnings,
        "blockers": [],
        "guardrails": _guardrails(),
    }


# ── Markdown rendering ────────────────────────────────────────────────────────

def _fmt(value: Any) -> str:
    return "(none)" if value is None or value == "" else _md(value)


def _boundary_lines() -> list[str]:
    return [
        "- EVAL.2 does not run benchmarks.",
        "- EVAL.2 does not call models.",
        "- EVAL.2 does not apply patches.",
        "- EVAL.2 does not edit benchmark cases.",
        "- EVAL.2 does not run validation.",
        "- EVAL.2 does not contact network services.",
        "- EVAL.2 does not launch workers.",
        "- EVAL.2 is a report-only comparison tool.",
    ]


def render_benchmark_report_compare_markdown(report: dict[str, Any]) -> str:
    """Render a single-case comparison as one operator-readable Markdown document."""
    lines: list[str] = [
        "# Benchmark Report Compare",
        "",
        f"> {report.get('guardrail_note', BENCHMARK_REPORT_COMPARE_GUARDRAIL_NOTE)}",
        "",
        f"_Report only: EVAL.2 compares existing benchmark reports for case "
        f"`{_md(report.get('case_id'))}` and explains the flake evidence. It runs "
        "nothing and changes nothing._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Comparison id:** `{_fmt(report.get('comparison_id'))}`",
        f"- **Created at:** `{_fmt(report.get('created_at'))}`",
        f"- **Case id:** `{_fmt(report.get('case_id'))}`",
        f"- **Matched reports:** {report.get('matched_report_count', 0)} "
        f"(loaded {report.get('loaded_report_count', 0)}, skipped {report.get('skipped_report_count', 0)})",
        f"- **Status counts:** {report.get('status_counts')}",
        "",
        "## Classification",
        "",
        f"- **Classification:** `{_fmt(report.get('classification'))}`",
        f"- **Reason:** {_fmt(report.get('classification_reason'))}",
        "",
    ]

    # Latest observation
    lines += ["## Latest Observation", ""]
    latest = report.get("latest_observation")
    if isinstance(latest, dict):
        lines += [
            f"- **Run id:** `{_fmt(latest.get('run_id'))}`",
            f"- **Created at:** `{_fmt(latest.get('created_at'))}`",
            f"- **Report:** `{_fmt(latest.get('report_path'))}`",
            f"- **Status:** `{_fmt(latest.get('status'))}` (scope `{_fmt(latest.get('suite_scope'))}`)",
            f"- **Duration (s):** {_fmt(latest.get('duration_seconds'))}",
        ]
    else:
        lines.append("_None — the case was not found in any loaded report._")
    lines.append("")

    # Report ordering
    lines += ["## Report Ordering", ""]
    ordering = report.get("report_ordering") or []
    if ordering:
        lines += [
            "| Report | Run id | Ordering source | Ordering value | Has case | Latest |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for row in ordering:
            lines.append(
                f"| `{_md(row.get('report_path'))}` | `{_md(row.get('run_id'))}` | "
                f"{_md(row.get('ordering_source'))} | `{_md(row.get('ordering_value'))}` | "
                f"{str(bool(row.get('contains_case'))).lower()} | {str(bool(row.get('is_latest'))).lower()} |"
            )
    else:
        lines.append("_None._")
    lines.append("")

    # Case timeline
    lines += ["## Case Timeline", ""]
    timeline = report.get("case_timeline") or []
    if timeline:
        lines += [
            "| Created at | Run id | Scope | Status | Run passed/failed | Duration (s) |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for obs in timeline:
            lines.append(
                f"| {_fmt(obs.get('created_at'))} | `{_md(obs.get('run_id'))}` | "
                f"{_md(obs.get('suite_scope'))} | `{_md(obs.get('status'))}` | "
                f"{obs.get('passed')}/{obs.get('failed')} | {_fmt(obs.get('duration_seconds'))} |"
            )
    else:
        lines.append("_None._")
    lines.append("")

    # Evidence labels
    lines += ["## Evidence Labels", ""]
    labels = report.get("evidence_labels") or []
    if labels:
        for label in labels:
            lines.append(f"- `{_md(label)}`")
    else:
        lines.append("_None._")
    lines.append("")

    # Failure notes
    lines += ["## Failure Notes", ""]
    failures = [o for o in timeline if o.get("failure_summary")]
    if failures:
        for obs in failures:
            lines.append(f"- `{_md(obs.get('run_id'))}` ({_fmt(obs.get('created_at'))}): {_md(obs.get('failure_summary'))}")
    else:
        lines.append("_None — no failing observation carried a failure summary._")
    lines.append("")

    # Ledger cross-check
    lines += ["## Ledger Cross-Check", ""]
    ledger = report.get("ledger_reference") or {}
    lines += [
        f"- **Ledger present:** {str(bool(ledger.get('present'))).lower()}",
        f"- **Ledger path:** `{_fmt(ledger.get('path'))}`",
        f"- **Case is a ledger flake candidate:** {str(bool(ledger.get('case_is_flake_candidate'))).lower()}",
        f"- **Ledger notes:** {', '.join(ledger.get('ledger_notes') or []) or '(none)'}",
        "",
    ]

    _render_warn_block(lines, report)

    lines += ["## Boundaries", ""]
    lines += _boundary_lines()
    lines.append("")
    return "\n".join(lines) + "\n"


def _render_warn_block(lines: list[str], report: dict[str, Any]) -> None:
    lines += ["## Warnings", ""]
    warnings = report.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- {_md(warning)}")
    else:
        lines.append("_None._")
    lines.append("")
    lines += ["## Blockers", ""]
    blockers = report.get("blockers") or []
    if blockers:
        for blocker in blockers:
            lines.append(f"- {_md(blocker)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_flake_candidates_compare_markdown(report: dict[str, Any]) -> str:
    """Render the all-flake-candidates aggregate as one Markdown document."""
    lines: list[str] = [
        "# Benchmark Report Compare — Flake Candidates",
        "",
        f"> {report.get('guardrail_note', BENCHMARK_REPORT_COMPARE_GUARDRAIL_NOTE)}",
        "",
        "_Report only: EVAL.2 compares existing benchmark reports for each suspected "
        "flake candidate. It runs nothing and changes nothing._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Comparison id:** `{_fmt(report.get('comparison_id'))}`",
        f"- **Created at:** `{_fmt(report.get('created_at'))}`",
        f"- **Matched reports:** {report.get('matched_report_count', 0)} "
        f"(loaded {report.get('loaded_report_count', 0)}, skipped {report.get('skipped_report_count', 0)})",
        f"- **Flake candidate cases:** {report.get('case_count', 0)}",
        "",
        "## Classification",
        "",
    ]
    comparisons = report.get("comparisons") or []
    if comparisons:
        lines += [
            "| Case | Classification | Latest | Evidence |",
            "| --- | --- | --- | --- |",
        ]
        for comparison in comparisons:
            latest = comparison.get("latest_observation") or {}
            labels = comparison.get("evidence_labels") or []
            lines.append(
                f"| `{_md(comparison.get('case_id'))}` | `{_md(comparison.get('classification'))}` | "
                f"`{_md(latest.get('status') if latest else '(none)')}` | {_md(', '.join(labels) or '-')} |"
            )
    else:
        lines.append("_None — no flake candidate cases were found._")
    lines.append("")

    # Ledger cross-check
    lines += ["## Ledger Cross-Check", ""]
    ledger = report.get("ledger_reference") or {}
    lines += [
        f"- **Ledger present:** {str(bool(ledger.get('present'))).lower()}",
        f"- **Ledger path:** `{_fmt(ledger.get('path'))}`",
        f"- **Ledger flake candidates:** {ledger.get('flake_candidate_count', 0)}",
        "",
    ]

    _render_warn_block(lines, report)

    lines += ["## Boundaries", ""]
    lines += _boundary_lines()
    lines.append("")
    return "\n".join(lines) + "\n"


# ── Writing ───────────────────────────────────────────────────────────────────

def _safe_filename(case_id: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in case_id) or "case"


def write_case_comparison(
    repo_path: str | Path,
    output_dir: str | Path,
    *,
    case_id: str,
    input_glob: str = DEFAULT_INPUT_GLOB,
    ledger_path: str | None = None,
    comparison_id: str = "",
    created_at: str = "",
    limit: Any = None,
) -> dict[str, Any]:
    """Compare benchmark reports for one case and write JSON + Markdown.

    Returns ``{ok, json_path, md_path, report}``. Reports and the optional ledger are
    read only; nothing outside ``output_dir`` is written.
    """
    loaded = load_benchmark_reports(repo_path, input_glob)
    ledger_info = load_ledger(repo_path, ledger_path)
    report = build_case_comparison(
        loaded["entries"],
        case_id,
        ledger_info=ledger_info,
        comparison_id=comparison_id,
        created_at=created_at,
        repo_path=str(repo_path),
        input_glob=input_glob,
        matched_count=loaded["matched_count"],
        skipped_count=loaded["skipped"],
        scan_warnings=list(loaded["warnings"]) + list(ledger_info["warnings"]),
        limit=limit,
    )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{_safe_filename(case_id)}_compare.json"
    md_path = out_dir / f"{_safe_filename(case_id)}_compare.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_benchmark_report_compare_markdown(report), encoding="utf-8")

    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}


def write_flake_candidates_comparison(
    repo_path: str | Path,
    output_dir: str | Path,
    *,
    input_glob: str = DEFAULT_INPUT_GLOB,
    ledger_path: str | None = None,
    comparison_id: str = "",
    created_at: str = "",
    limit: Any = None,
) -> dict[str, Any]:
    """Compare reports for every suspected flake candidate and write JSON + Markdown."""
    loaded = load_benchmark_reports(repo_path, input_glob)
    ledger_info = load_ledger(repo_path, ledger_path)
    report = build_flake_candidates_comparison(
        loaded["entries"],
        ledger_info=ledger_info,
        comparison_id=comparison_id,
        created_at=created_at,
        repo_path=str(repo_path),
        input_glob=input_glob,
        matched_count=loaded["matched_count"],
        skipped_count=loaded["skipped"],
        scan_warnings=list(loaded["warnings"]) + list(ledger_info["warnings"]),
        limit=limit,
    )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / ALL_FLAKE_JSON_NAME
    md_path = out_dir / ALL_FLAKE_MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_flake_candidates_compare_markdown(report), encoding="utf-8")

    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
