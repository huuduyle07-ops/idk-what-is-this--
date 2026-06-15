"""Phase 14.4 — Failure taxonomy trend / dogfood report (read-only).

Compare the Phase 14 failure taxonomy across *multiple* already-existing
benchmark reports and surface how failure categories drift over time:
category deltas, newly appearing / disappearing categories, and individual
cases whose failure category changed between reports.

This module is analysis-only. It reuses
``core.failure_taxonomy.summarize_benchmark_failures`` over already-loaded
report dictionaries (or local report paths it reads). It never runs benchmarks,
changes scoring, generates/applies patches, runs validation, promotes lessons,
runs Dream automation, calls a model/API, writes a database, spawns
subprocesses, touches Docker, makes network calls, or mutates any input. It
writes no files of its own — the optional script is the only writer, and only
of its two explicit trend artifacts. Recommendations are limited to text-only
next-action notes; nothing is acted upon.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.failure_taxonomy import (
    CATEGORIES,
    summarize_benchmark_failures,
)

def extract_failure_category_counts(report: dict[str, Any]) -> dict[str, int]:
    """Return counts of failure_category values from case records in a report.

    Reads the Phase-14.6 ``failure_category`` field added by
    ``with_failure_category_fields()``.  Returns an empty dict for old reports
    that pre-date Phase 14.6 (backward-compatible, never raises).
    """
    counts: dict[str, int] = {}
    for case in (report.get("results") or []):
        if not isinstance(case, dict):
            continue
        if case.get("success") is True or case.get("skipped"):
            continue
        cat = case.get("failure_category")
        if isinstance(cat, str) and cat:
            counts[cat] = counts.get(cat, 0) + 1
    return counts


TREND_GUARDRAIL_NOTE = (
    "Failure taxonomy trend report is read-only: it only compares already "
    "computed benchmark results and does not affect benchmark scoring, "
    "patching, validation, lesson promotion, or model routing."
)


def compare_failure_taxonomies(
    reports: list[Any],
    *,
    identifiers: list[str] | None = None,
) -> dict[str, Any]:
    """Compare the failure taxonomy across two or more benchmark reports.

    ``reports`` is a list of already-loaded report dicts and/or local report
    paths (``str``/``Path``); paths are read as JSON and an unreadable/invalid
    path degrades gracefully to an empty report rather than raising. The inputs
    are never mutated.

    Returns a result dict. With fewer than two reports it returns
    ``{"ok": False, ...}`` with a friendly ``error`` (and never raises). With
    two or more it returns the trend fields: per-report identifiers, total
    failing cases and counts by category; baseline/latest identifiers; category
    deltas (latest minus baseline); newly appearing and disappearing
    categories; and cases whose failure category changed.
    """
    items = list(reports)
    ids = _resolve_identifiers(items, identifiers)

    per_report: list[dict[str, Any]] = []
    case_categories: list[dict[str, str]] = []
    for index, item in enumerate(items):
        report = _as_report_dict(item)
        summary = summarize_benchmark_failures(report)
        fc_counts = extract_failure_category_counts(report)
        entry: dict[str, Any] = {
            "identifier": ids[index],
            "total_failing": summary["total_failing"],
            "counts_by_category": dict(summary["counts_by_category"]),
        }
        if fc_counts:
            entry["failure_category_counts"] = fc_counts
        per_report.append(entry)
        case_categories.append(
            {c["name"]: c["category"] for c in summary["classifications"]}
        )

    if len(items) < 2:
        return {
            "ok": False,
            "error": "need at least two reports to compute a trend",
            "report_count": len(items),
            "reports": per_report,
            "guardrail_note": TREND_GUARDRAIL_NOTE,
        }

    baseline_counts = per_report[0]["counts_by_category"]
    latest_counts = per_report[-1]["counts_by_category"]

    union = [
        c for c in CATEGORIES if c in baseline_counts or c in latest_counts
    ]
    category_deltas = {
        c: latest_counts.get(c, 0) - baseline_counts.get(c, 0) for c in union
    }
    new_categories = [
        c for c in CATEGORIES if c in latest_counts and c not in baseline_counts
    ]
    disappeared_categories = [
        c for c in CATEGORIES if c in baseline_counts and c not in latest_counts
    ]

    baseline_cases = case_categories[0]
    latest_cases = case_categories[-1]
    changed_cases = [
        {
            "name": name,
            "from_category": baseline_cases[name],
            "to_category": latest_cases[name],
        }
        for name in sorted(set(baseline_cases) & set(latest_cases))
        if baseline_cases[name] != latest_cases[name]
    ]

    notes = _next_action_notes(
        new_categories, disappeared_categories, changed_cases, ids[-1]
    )

    return {
        "ok": True,
        "report_count": len(items),
        "reports": per_report,
        "baseline": ids[0],
        "latest": ids[-1],
        "category_deltas": category_deltas,
        "new_categories": new_categories,
        "disappeared_categories": disappeared_categories,
        "changed_cases": changed_cases,
        "next_action_notes": notes,
        "guardrail_note": TREND_GUARDRAIL_NOTE,
    }


def format_trend_markdown(trend: dict[str, Any]) -> str:
    """Render a read-only Markdown trend report from :func:`compare_*` output."""
    lines = ["# Failure Taxonomy Trend", ""]
    lines.append(f"> {trend.get('guardrail_note', TREND_GUARDRAIL_NOTE)}")
    lines.append("")

    if not trend.get("ok"):
        lines.append(
            f"Not enough reports to compute a trend (need at least two, "
            f"got {trend.get('report_count', 0)})."
        )
        lines.append("")
        return "\n".join(lines) + "\n"

    lines.append(f"- Reports compared: {trend['report_count']}")
    lines.append(f"- Baseline: `{trend['baseline']}`")
    lines.append(f"- Latest: `{trend['latest']}`")
    lines.append("")

    lines.append("## Reports")
    lines.append("")
    for report in trend["reports"]:
        lines.append(
            f"- `{report['identifier']}` — failing cases: "
            f"{report['total_failing']}"
        )
        counts = report["counts_by_category"]
        if counts:
            for category, count in counts.items():
                lines.append(f"  - {category}: {count}")
    lines.append("")

    lines.append("## Category deltas (latest minus baseline)")
    lines.append("")
    if trend["category_deltas"]:
        for category, delta in trend["category_deltas"].items():
            lines.append(f"- {category}: {delta:+d}")
    else:
        lines.append("_No failing categories in either report._")
    lines.append("")

    lines.append("## Newly appearing categories")
    lines.append("")
    lines.extend(
        [f"- {c}" for c in trend["new_categories"]] or ["_None._"]
    )
    lines.append("")

    lines.append("## Disappearing categories")
    lines.append("")
    lines.extend(
        [f"- {c}" for c in trend["disappeared_categories"]] or ["_None._"]
    )
    lines.append("")

    lines.append("## Cases whose category changed")
    lines.append("")
    if trend["changed_cases"]:
        lines.append("| Case | From | To |")
        lines.append("|---|---|---|")
        for item in trend["changed_cases"]:
            name = str(item["name"]).replace("|", "\\|")
            lines.append(
                f"| `{name}` | {item['from_category']} | {item['to_category']} |"
            )
    else:
        lines.append("_No cases changed category._")
    lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.extend([f"- {n}" for n in trend["next_action_notes"]] or ["_None._"])
    lines.append("")

    return "\n".join(lines) + "\n"


# --- internals --------------------------------------------------------------


def _as_report_dict(item: Any) -> dict[str, Any]:
    """Coerce an input into a report dict, never raising.

    Already-loaded dicts are returned as-is. Paths (``str``/``Path``) are read
    as JSON; anything unreadable, non-JSON, or non-object degrades to ``{}`` so
    callers see zero failing cases rather than an exception.
    """
    if isinstance(item, dict):
        return item
    if isinstance(item, (str, Path)):
        try:
            raw = Path(item).read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _identifier_for(item: Any, index: int) -> str:
    if isinstance(item, (str, Path)):
        return Path(item).stem
    if isinstance(item, dict):
        for key in ("identifier", "report_id", "source_benchmark_report", "name"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return Path(value).stem if key == "source_benchmark_report" else value
    return f"report_{index}"


def _resolve_identifiers(
    items: list[Any], identifiers: list[str] | None
) -> list[str]:
    if identifiers is not None and len(identifiers) == len(items):
        return [str(i) for i in identifiers]
    return [_identifier_for(item, index) for index, item in enumerate(items)]


def _next_action_notes(
    new_categories: list[str],
    disappeared_categories: list[str],
    changed_cases: list[dict[str, str]],
    latest_id: str,
) -> list[str]:
    """Text-only observations. Nothing here is acted upon."""
    notes: list[str] = []
    for category in new_categories:
        notes.append(
            f"New failure category '{category}' appeared in '{latest_id}'; "
            f"review whether a recent change introduced it."
        )
    for category in disappeared_categories:
        notes.append(
            f"Failure category '{category}' no longer appears in '{latest_id}'."
        )
    for item in changed_cases:
        notes.append(
            f"Case '{item['name']}' changed category from "
            f"'{item['from_category']}' to '{item['to_category']}'."
        )
    if not notes:
        notes.append("No category drift detected between the compared reports.")
    return notes
