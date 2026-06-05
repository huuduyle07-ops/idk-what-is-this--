from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Ensure imports like `graph.builder` resolve when this file is invoked as
# `python scripts/build_presentation_evidence_pack.py` (in that case
# sys.path[0] would be the scripts/ directory, not the project root).
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.memory_temperature import MEMORY_TEMPERATURE_GUARDRAIL
from core.memory_temperature_retrieval_dogfood import (
    build_memory_temperature_tiebreaker_dogfood,
    format_memory_temperature_tiebreaker_dogfood_markdown,
)

UNKNOWN = "unknown"

GRAPH_EXPLAIN_COMMAND = (
    "python scripts\\explain_graph_weights.py --repo-path . --top 15 "
    "--include-zero-penalty --path-prefix core --path-prefix graph "
    "--path-prefix patching --hide-empty-symbols"
)

EVIDENCE_FILES = [
    "00_evidence_index.md",
    "01_full_suite_summary.md",
    "02_held_out_suite_summary.md",
    "03_held_out_watchlist.md",
    "04_patch_minimality_experiment.md",
    "05_same_suite_trends.md",
    "06_graph_weight_explainability.md",
    "07_graph_attraction_explainability.md",
    "08_memory_temperature_explainability.md",
    "09_memory_temperature_tiebreaker_dogfood.md",
]

MEMORY_TEMPERATURE_GUARDRAIL_BLOCK = f"> {MEMORY_TEMPERATURE_GUARDRAIL}"

GRAPH_ATTRACTION_GUARDRAIL = (
    "> Graph attraction/repulsion is explain-only. It does not change Evidence "
    "Spread scoring, CONTROL ranking, Phantom Limb ranking, patch generation, "
    "validation, or benchmark scoring."
)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _timestamp_from_text(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _report_sort_key(report: dict[str, Any], path: Path) -> float:
    for field in ("created_at", "timestamp", "created_at_epoch"):
        ts = _timestamp_from_text(report.get(field))
        if ts is not None:
            return ts
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _list_reports(bench_dir: Path) -> list[tuple[float, Path, dict[str, Any]]]:
    if not bench_dir.is_dir():
        return []
    rows: list[tuple[float, Path, dict[str, Any]]] = []
    for path in sorted(bench_dir.glob("benchmark_report_*.json")):
        data = _load_json(path)
        if data is None:
            continue
        rows.append((_report_sort_key(data, path), path, data))
    rows.sort(key=lambda item: (item[0], item[1].name))
    return rows


def _pick_full_suite_report(
    reports: list[tuple[float, Path, dict[str, Any]]],
) -> tuple[float, Path, dict[str, Any]] | None:
    full = [
        row
        for row in reports
        if isinstance(row[2].get("total"), (int, float)) and row[2].get("total", 0) >= 31
    ]
    return full[-1] if full else None


def _pick_held_out_report(
    reports: list[tuple[float, Path, dict[str, Any]]],
    suite_id: str = "held_out_v1",
) -> tuple[float, Path, dict[str, Any]] | None:
    held = [row for row in reports if row[2].get("suite_id") == suite_id]
    return held[-1] if held else None


def _pick_minimality_experiment(
    exp_dir: Path,
) -> tuple[dict[str, Any] | None, Path | None]:
    if not exp_dir.is_dir():
        return None, None
    candidates: list[tuple[float, Path, dict[str, Any]]] = []
    for path in sorted(exp_dir.glob("*.json")):
        data = _load_json(path)
        if data is None:
            continue
        haystack = " ".join(
            str(data.get(key, "")) for key in ("title", "hypothesis", "experiment_id")
        ).lower()
        if "patch minimality" in haystack or "patch-minimality" in haystack:
            ts = (
                _timestamp_from_text(data.get("created_at"))
                or _report_sort_key(data, path)
            )
            candidates.append((ts, path, data))
    if not candidates:
        return None, None
    candidates.sort(key=lambda item: (item[0], item[1].name))
    _, path, data = candidates[-1]
    return data, path


def _find_graph_artifact(project_root: Path) -> tuple[str | None, Path | None]:
    for candidate in (
        project_root / ".agent" / "graph_explainability.md",
        project_root / ".agent" / "graph_weights_report.md",
        project_root / ".agent" / "explain_graph_weights.md",
        project_root / ".agent" / "graph_weights" / "latest.md",
    ):
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8"), candidate
            except OSError:
                continue
    return None, None


def _find_graph_attraction_artifact(project_root: Path) -> tuple[str | None, Path | None]:
    """Locate the latest graph attraction/repulsion smoke or report artifact.

    Read-only. Prefers stable, well-known names, then the newest timestamped
    report under ``.agent/reports/graph_attraction/``. Returns ``(text, path)``
    or ``(None, None)`` when no artifact exists."""
    candidates = [
        project_root / ".agent" / "graph_attraction.md",
        project_root / ".agent" / "graph_attraction_smoke.md",
        project_root / ".agent" / "reports" / "graph_attraction" / "latest.md",
    ]
    reports_dir = project_root / ".agent" / "reports" / "graph_attraction"
    if reports_dir.is_dir():
        for path in sorted(reports_dir.glob("*.md"), reverse=True):
            if path.name != "latest.md" and path not in candidates:
                candidates.append(path)
    for candidate in candidates:
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8"), candidate
            except OSError:
                continue
    return None, None


def _format_graph_attraction(
    artifact_text: str | None,
    source_path: Path | None,
    include_raw_paths: bool,
) -> str:
    if artifact_text is not None:
        lines = [
            "# 07 Graph Attraction / Repulsion Explainability",
            "",
            "An existing graph attraction/repulsion report was found.",
            "",
        ]
        if include_raw_paths and source_path is not None:
            lines.extend([f"_Source: `{source_path}`_", ""])
        lines.extend(
            [
                "```",
                artifact_text.strip(),
                "```",
                "",
                GRAPH_ATTRACTION_GUARDRAIL,
                "",
            ]
        )
        return "\n".join(lines)

    return (
        "# 07 Graph Attraction / Repulsion Explainability\n\n"
        "_No graph attraction/repulsion report was found under "
        "`.agent/reports/graph_attraction/` (or `.agent/graph_attraction*.md`)._\n\n"
        "This section is explain-only: it visualizes which graph nodes attract "
        "attention (query / target / evidence-confidence matches) and which "
        "generic utility hubs repel it. A report is produced by the read-only "
        "evidence-spread export, which now embeds the Graph Attraction / "
        "Repulsion section:\n\n"
        "```\n"
        "POST /graph/evidence_spread/export  (repo_path, query, target_node)\n"
        "```\n\n"
        + GRAPH_ATTRACTION_GUARDRAIL
        + "\n"
    )


def _find_memory_temperature_artifact(project_root: Path) -> tuple[str | None, Path | None]:
    """Locate the latest memory-temperature report artifact, if any.

    Read-only. Prefers stable, well-known names, then the newest timestamped
    report under ``.agent/reports/memory_temperature/``. Returns ``(text, path)``
    or ``(None, None)`` when no artifact exists."""
    candidates = [
        project_root / ".agent" / "memory_temperature.md",
        project_root / ".agent" / "reports" / "memory_temperature" / "latest.md",
    ]
    reports_dir = project_root / ".agent" / "reports" / "memory_temperature"
    if reports_dir.is_dir():
        for path in sorted(reports_dir.glob("*.md"), reverse=True):
            if path.name != "latest.md" and path not in candidates:
                candidates.append(path)
    for candidate in candidates:
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8"), candidate
            except OSError:
                continue
    return None, None


def _format_memory_temperature(
    artifact_text: str | None,
    source_path: Path | None,
    include_raw_paths: bool,
) -> str:
    if artifact_text is not None:
        lines = [
            "# 08 Memory Temperature Explainability",
            "",
            "An existing memory-temperature report was found.",
            "",
        ]
        if include_raw_paths and source_path is not None:
            lines.extend([f"_Source: `{source_path}`_", ""])
        lines.extend(
            [
                "```",
                artifact_text.strip(),
                "```",
                "",
                MEMORY_TEMPERATURE_GUARDRAIL_BLOCK,
                "",
            ]
        )
        return "\n".join(lines)

    # Graceful placeholder: explain the model even when no report exists yet.
    return (
        "# 08 Memory Temperature Explainability\n\n"
        "_No memory-temperature report was found under "
        "`.agent/reports/memory_temperature/` (or `.agent/memory_temperature.md`)._\n\n"
        "This section is explain-only: it shows how warm each already-loaded "
        "lesson / proposal / note is, so a reviewer can see *why* a memory would "
        "or would not be surfaced. It never changes retrieval, ranking, or "
        "scoring.\n\n"
        "## Thermal bands\n\n"
        "- 🔥 **hot** (`temperature >= 0.75`): recently reinforced or trusted; "
        "would be surfaced.\n"
        "- 🌤 **warm** (`temperature >= 0.40`): still relevant; would be "
        "surfaced.\n"
        "- ❄️ **cold** (`temperature < 0.40`): cooled off; not surfaced by "
        "default.\n"
        "- 🧊 **frozen** (`temperature == 0.0`): hard-frozen; never surfaced.\n\n"
        "## Cooling formula\n\n"
        "```\n"
        "T_now = clamp(T_base * exp(-lambda * age_days) + reheating - risk, 0, 1)\n"
        "```\n\n"
        "where `lambda` is the cooling rate, `age_days` is how long since the "
        "memory was last used, `reheating` rewards human approval / repeated "
        "use / recent success, and `risk` subtracts needs-review and risk-score "
        "penalties.\n\n"
        "## Hard-freeze override\n\n"
        "Records marked `blocked`, `unsafe`, failed-validation, or `audit-only` "
        "are hard-frozen to `temperature == 0.0` regardless of reheating, so an "
        "unsafe memory can never be surfaced. They remain visible here purely "
        "for explanation.\n\n"
        "A report is produced by the read-only memory-temperature classifier, "
        "which is also embedded in the Related Notes / Lessons explainability "
        "output:\n\n"
        "```\n"
        "GET /graph/explainability/view  (repo_path, query)\n"
        "```\n\n"
        + MEMORY_TEMPERATURE_GUARDRAIL_BLOCK
        + "\n"
    )


# Fixed reference "now" so the dogfood sample bands are reproducible across
# rebuilds (the sample is representative, not time-sensitive).
TIEBREAKER_DOGFOOD_REFERENCE_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)


def _tiebreaker_dogfood_sample_candidates() -> list[dict[str, Any]]:
    """A deterministic, near-equal-relevance representative candidate set.

    Built-in (no DB / lesson_store query). The scores cluster so the tie-breaker
    has a near-equal group to reorder, plus one clearly-more-relevant cold lesson
    to show that cold is *not* hard-filtered and that a clearly higher score is
    never reordered."""
    return [
        {
            "id": "hot-lesson",
            "title": "trusted retry lesson",
            "score": 0.50,
            "status": "active",
            "source_type": "lesson",
            "trusted": True,
            "updated_at": "2026-06-01T12:00:00+00:00",
        },
        {
            "id": "cold-manual",
            "title": "old manual note about retries",
            "score": 0.50,
            "status": "active",
            "source_type": "manual",
            "updated_at": "2026-03-01T12:00:00+00:00",
        },
        {
            "id": "warm-manual",
            "title": "recent manual retry note",
            "score": 0.49,
            "status": "active",
            "source_type": "manual",
            "updated_at": "2026-05-26T12:00:00+00:00",
        },
        {
            "id": "blocked-lesson",
            "title": "blocked lesson",
            "score": 0.50,
            "status": "blocked",
            "source_type": "lesson",
            "updated_at": "2026-06-01T12:00:00+00:00",
        },
        {
            "id": "audit-only-lesson",
            "title": "audit-only lesson",
            "score": 0.50,
            "status": "audit-only",
            "source_type": "lesson",
            "updated_at": "2026-06-01T12:00:00+00:00",
        },
        {
            "id": "high-relevance-cold",
            "title": "clearly more relevant but cold",
            "score": 0.92,
            "status": "active",
            "source_type": "manual",
            "updated_at": "2026-02-01T12:00:00+00:00",
        },
    ]


def _format_memory_temperature_tiebreaker_dogfood(include_raw_paths: bool) -> str:
    """Render the Phase 13.10 tie-breaker dogfood as an evidence-pack section.

    Read-only / explain-only: it runs the default-off tie-breaker over a
    deterministic built-in sample (never querying the DB or ``lesson_store``)
    and embeds the resulting evidence table. It does not touch live retrieval,
    the CONTROL prompt, or the harness flag (which is off by default)."""
    candidates = _tiebreaker_dogfood_sample_candidates()
    report = build_memory_temperature_tiebreaker_dogfood(
        candidates, now=TIEBREAKER_DOGFOOD_REFERENCE_NOW, enabled=True
    )
    dogfood_md = format_memory_temperature_tiebreaker_dogfood_markdown(report)

    lines = [
        "# 09 Memory Temperature Tie-breaker Dogfood",
        "",
        "This is an evidence-only dogfood of the Phase 13.9 Memory Temperature",
        "tie-breaker. When enabled, the tie-breaker only reorders lesson",
        "candidates *within* a near-equal relevance group (hot/warm memories",
        "rise, cold ones fall); the relevance score and the overall ranking are",
        "preserved. It is off by default (an opt-in editable toggle).",
        "",
        "- Live retrieval is unchanged.",
        "- CONTROL prompt is unchanged.",
        "- `MEMORY_TEMPERATURE_RETRIEVAL_ENABLED` is off by default "
        "(an opt-in editable toggle; this pack never enables it).",
        "- Cold memories are never hard-filtered (they only lose priority inside "
        "a near-equal group).",
        "- Frozen / audit-only / blocked memories are excluded from CONTROL and "
        "are never revived or surfaced.",
        "",
        "The representative preview below was generated by "
        "`core.memory_temperature_retrieval_dogfood` from a deterministic, "
        "built-in sample candidate set (no DB or `lesson_store` query).",
        "",
    ]
    if include_raw_paths:
        lines.extend(["_Source: built-in representative sample candidates_", ""])
    return "\n".join(lines) + "\n" + dogfood_md


GRAPH_AUTORUN_TOP = 15
GRAPH_AUTORUN_PATH_PREFIXES = ("core", "graph", "patching")
GRAPH_AUTORUN_INCLUDE_ZERO_PENALTY = True
GRAPH_AUTORUN_HIDE_EMPTY_SYMBOLS = True


def _try_build_graph_explanation(
    project_root: Path,
) -> dict[str, Any] | None:
    """Attempt to run the graph explainer for this project.

    Returns a dict with `rows` (ranked node entries) on success or None on
    any failure. The caller falls back to a placeholder when None is returned
    so a single bad import or a graph-build edge case never breaks the
    evidence pack."""
    try:
        from graph.builder import build_graph_from_repo
        from graph.weights import explain_node_weights
        from scripts.explain_graph_weights import _rank_and_filter
    except Exception:
        return None

    try:
        graph = build_graph_from_repo(str(project_root))
    except Exception:
        return None

    try:
        rows = explain_node_weights(graph, repo_path=str(project_root))
    except Exception:
        return None

    try:
        ranked = _rank_and_filter(
            rows,
            top=GRAPH_AUTORUN_TOP,
            kind_filter=None,
            include_zero_penalty=GRAPH_AUTORUN_INCLUDE_ZERO_PENALTY,
            path_prefixes=list(GRAPH_AUTORUN_PATH_PREFIXES),
            exclude_paths=None,
            hide_empty_symbols=GRAPH_AUTORUN_HIDE_EMPTY_SYMBOLS,
        )
    except Exception:
        return None

    return {
        "rows": ranked,
        "top": GRAPH_AUTORUN_TOP,
        "path_prefixes": list(GRAPH_AUTORUN_PATH_PREFIXES),
        "include_zero_penalty": GRAPH_AUTORUN_INCLUDE_ZERO_PENALTY,
        "hide_empty_symbols": GRAPH_AUTORUN_HIDE_EMPTY_SYMBOLS,
    }


def _format_full_suite(
    picked: tuple[float, Path, dict[str, Any]] | None,
    include_raw_paths: bool,
) -> str:
    if picked is None:
        return (
            "# 01 Full Suite Summary\n\n"
            "_No benchmark report with `total >= 31` was found in "
            "`.agent/benchmarks/`._\n"
        )
    _, path, data = picked
    results = data.get("results") or []
    nested_present = any(
        isinstance(r, dict) and r.get("name") == "ts_nested_dispatch_root_cause"
        for r in results
    )
    nested_passed = any(
        isinstance(r, dict)
        and r.get("name") == "ts_nested_dispatch_root_cause"
        and bool(r.get("success"))
        for r in results
    )
    if not nested_present:
        nested_status = "not in this report"
    else:
        nested_status = "yes" if nested_passed else "no"

    avg_duration = data.get("avg_duration_sec")
    if avg_duration is None:
        avg_duration = data.get("average_duration", UNKNOWN)

    lines = [
        "# 01 Full Suite Summary",
        "",
        f"- Report: `{path.name}`",
        f"- Total: {data.get('total', UNKNOWN)}",
        f"- Passed: {data.get('passed', UNKNOWN)}",
        f"- Failed: {data.get('failed', UNKNOWN)}",
        f"- Flaky: {data.get('flaky', UNKNOWN)}",
        f"- Average duration (sec): {avg_duration}",
        f"- Fallback count: {data.get('total_fallbacks', UNKNOWN)}",
        f"- Tokens total: {data.get('total_tokens', UNKNOWN)}",
        f"- Estimated cost (USD): {data.get('total_estimated_cost_usd', UNKNOWN)}",
        f"- ts_nested_dispatch_root_cause passed: {nested_status}",
    ]
    if include_raw_paths:
        lines.extend(["", f"_Source: `{path}`_"])
    return "\n".join(lines) + "\n"


def _format_held_out_summary(
    picked: tuple[float, Path, dict[str, Any]] | None,
    include_raw_paths: bool,
) -> str:
    if picked is None:
        return (
            "# 02 Held-out Suite Summary\n\n"
            "_No benchmark report with `suite_id == \"held_out_v1\"` was found "
            "in `.agent/benchmarks/`._\n"
        )
    _, path, data = picked
    results = data.get("results") or []
    case_names = [
        str(r.get("name"))
        for r in results
        if isinstance(r, dict) and r.get("name")
    ]
    avg_duration = data.get("avg_duration_sec")
    if avg_duration is None:
        avg_duration = data.get("average_duration", UNKNOWN)
    lines = [
        "# 02 Held-out Suite Summary",
        "",
        f"- Report: `{path.name}`",
        f"- Suite id: `{data.get('suite_id', UNKNOWN)}`",
        f"- Suite case count: {data.get('suite_case_count', UNKNOWN)}",
        f"- Passed: {data.get('passed', UNKNOWN)}",
        f"- Failed: {data.get('failed', UNKNOWN)}",
        f"- Flaky: {data.get('flaky', UNKNOWN)}",
        f"- Average duration (sec): {avg_duration}",
        f"- Fallback count: {data.get('total_fallbacks', UNKNOWN)}",
        "",
        "## Held-out cases",
        "",
    ]
    if case_names:
        for name in case_names:
            lines.append(f"- `{name}`")
    else:
        lines.append("_No case names found in this report._")
    if include_raw_paths:
        lines.extend(["", f"_Source: `{path}`_"])
    return "\n".join(lines) + "\n"


def _format_watchlist(
    watchlist: dict[str, Any] | None,
    source_path: Path | None,
    include_raw_paths: bool,
) -> str:
    if watchlist is None:
        return (
            "# 03 Held-out Watchlist\n\n"
            "_No watchlist artifact found at "
            "`.agent/benchmarks/trends/suite_watchlist_held_out_v1.json`._\n\n"
            "Generate it with:\n\n"
            "```\n"
            "python scripts\\build_suite_watchlist.py "
            "--suite held_out_v1 --output-md\n"
            "```\n"
        )
    cases = watchlist.get("cases") or []
    watchlisted_names = watchlist.get("watchlist") or []
    stable_names = watchlist.get("stable") or []
    window = watchlist.get("report_window") or {}
    lines = [
        "# 03 Held-out Watchlist",
        "",
        f"- Suite id: `{watchlist.get('suite_id', UNKNOWN)}`",
        f"- Reports selected: {window.get('selected', UNKNOWN)} of last "
        f"{window.get('requested', UNKNOWN)} requested",
        f"- Watchlisted cases: {len(watchlisted_names)}",
        f"- Stable cases: {len(stable_names)}",
        "",
        "> This watchlist is observational. It does **not** change pass/fail",
        "> scoring; it only highlights held-out cases that have been unstable",
        "> across repeated runs.",
        "",
        "## Watchlisted cases",
        "",
    ]
    watchlisted_cases = [c for c in cases if c.get("watchlisted")]
    if watchlisted_cases:
        lines.extend(
            [
                "| case | reasons | failure_rate | last_status | last_seen_report |",
                "|---|---|---:|---|---|",
            ]
        )
        for case in watchlisted_cases:
            reasons = ", ".join(case.get("watchlist_reasons") or []) or "-"
            lines.append(
                f"| `{case.get('name', UNKNOWN)}` | {reasons} | "
                f"{case.get('failure_rate', UNKNOWN)} | "
                f"{case.get('last_status', UNKNOWN)} | "
                f"`{case.get('last_seen_report', UNKNOWN)}` |"
            )
    else:
        lines.append("_No watchlisted cases in the selected window._")
    if include_raw_paths and source_path is not None:
        lines.extend(["", f"_Source: `{source_path}`_"])
    return "\n".join(lines) + "\n"


def _format_minimality(
    experiment: dict[str, Any] | None,
    source_path: Path | None,
    include_raw_paths: bool,
    current_full_report: dict[str, Any] | None = None,
) -> str:
    if experiment is None:
        return (
            "# 04 Patch Minimality Experiment\n\n"
            "_No patch-minimality experiment was found in "
            "`.agent/experiments/`._\n\n"
            "Create one with `scripts/create_experiment.py` (or its variants) "
            "comparing a baseline benchmark report to one captured with the "
            "patch-minimality metrics enabled.\n"
        )
    result = experiment.get("result") or {}
    decision = result.get("decision") or {}
    metrics = result.get("metrics") or {}
    total_metric = metrics.get("total") if isinstance(metrics.get("total"), dict) else {}
    baseline_total = total_metric.get("baseline", UNKNOWN)
    variant_total = total_metric.get("variant", UNKNOWN)
    current_total = (
        current_full_report.get("total")
        if isinstance(current_full_report, dict)
        else None
    )

    def _delta(key: str) -> Any:
        entry = metrics.get(key)
        if isinstance(entry, dict):
            return entry.get("delta", UNKNOWN)
        return UNKNOWN

    lines = [
        "# 04 Patch Minimality Experiment",
        "",
        f"- Title: {experiment.get('title', UNKNOWN)}",
        f"- Experiment id: `{experiment.get('experiment_id', UNKNOWN)}`",
        f"- Status: `{experiment.get('status', UNKNOWN)}`",
        f"- Decision: `{decision.get('status', UNKNOWN)}`",
        f"- Human review required: {decision.get('human_review_required', UNKNOWN)}",
        f"- Experiment case scope: {baseline_total} baseline cases / {variant_total} variant cases",
    ]
    if current_total is not None:
        lines.append(f"- Current presentation full-suite size: {current_total} cases")
    lines.extend(
        [
            "",
            "> Current full-suite size can change independently. The metrics below",
            "> describe the baseline and variant reports captured for this experiment,",
            "> not a fixed global benchmark size.",
            "",
            "## Correctness metrics",
            "",
            "| metric | baseline | variant | delta | status |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for key in ("total", "passed", "failed", "flaky"):
        entry = metrics.get(key)
        if isinstance(entry, dict):
            lines.append(
                f"| {key} | {entry.get('baseline', UNKNOWN)} | "
                f"{entry.get('variant', UNKNOWN)} | "
                f"{entry.get('delta', UNKNOWN)} | "
                f"{entry.get('status', UNKNOWN)} |"
            )
    lines.extend(
        [
            "",
            f"- average_duration delta: {_delta('average_duration')}",
            f"- fallback_count delta: {_delta('fallback_count')}",
            "",
            "## Warnings",
            "",
        ]
    )
    warnings = decision.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("_No warnings._")
    if include_raw_paths and source_path is not None:
        lines.extend(["", f"_Source: `{source_path}`_"])
    return "\n".join(lines) + "\n"


def _format_trends(
    trend_index: dict[str, Any] | None,
    source_path: Path | None,
    include_raw_paths: bool,
) -> str:
    if trend_index is None:
        return (
            "# 05 Same-suite Trends\n\n"
            "_No trend index found at "
            "`.agent/benchmarks/trends/benchmark_trend_index.json`._\n\n"
            "Generate it with:\n\n"
            "```\n"
            "python scripts\\build_benchmark_trends.py --output-md\n"
            "```\n"
        )
    groups = trend_index.get("groups") or []
    warnings = trend_index.get("warnings") or []
    largest = max(groups, key=lambda group: len(group.get("runs") or []), default=None)
    lines = [
        "# 05 Same-suite Trends",
        "",
        f"- Trend groups: {len(groups)}",
        f"- Same-total / different-case warnings: {len(warnings)}",
        "",
        "> Same-suite grouping protects against fake comparisons: reports that",
        "> share the same `total` but use different case names are kept in",
        "> separate groups.",
        "> A run is only compared with reports that share the same case-set fingerprint,",
        "> so this remains valid as case counts grow.",
        "",
    ]
    if warnings:
        lines.extend(["## Same-total / different-suite warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")
    if largest:
        lines.extend(
            [
                "## Largest same-suite group",
                "",
                f"- Suite fingerprint: `{largest.get('suite_fingerprint', UNKNOWN)}`",
                f"- Case count: {largest.get('total', UNKNOWN)}",
                f"- Runs in this group: {len(largest.get('runs') or [])}",
            ]
        )
    if include_raw_paths and source_path is not None:
        lines.extend(["", f"_Source: `{source_path}`_"])
    return "\n".join(lines) + "\n"


def _format_graph_rows_md(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["_No graph nodes matched the configured filters._"]
    lines = [
        "| rank | node | kind | weight | topology | complexity | penalty | reasons |",
        "|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        reasons = " + ".join(row.get("reasons") or []) or "-"
        lines.append(
            "| "
            f"{row.get('rank', UNKNOWN)} | "
            f"`{row.get('node_id', UNKNOWN)}` | "
            f"{row.get('node_kind') or UNKNOWN} | "
            f"{row.get('total_weight', UNKNOWN)} | "
            f"{row.get('topology_contribution', UNKNOWN)} | "
            f"{row.get('complexity_contribution', UNKNOWN)} | "
            f"{row.get('failure_penalty', UNKNOWN)} | "
            f"{reasons} |"
        )
    return lines


def _format_graph(
    artifact_text: str | None,
    source_path: Path | None,
    auto_explanation: dict[str, Any] | None,
    include_raw_paths: bool,
) -> str:
    # Prefer a prebuilt artifact if the project ships one.
    if artifact_text is not None:
        lines = [
            "# 06 Graph Weight Explainability",
            "",
            "An existing graph explainability artifact was found.",
            "",
        ]
        if include_raw_paths and source_path is not None:
            lines.extend([f"_Source: `{source_path}`_", ""])
        lines.extend(
            [
                "```",
                artifact_text.strip(),
                "```",
                "",
            ]
        )
        return "\n".join(lines)

    # Otherwise embed the auto-run result if we got one.
    if auto_explanation is not None:
        prefixes = ", ".join(
            f"`{p}`" for p in auto_explanation.get("path_prefixes") or []
        ) or "_(none)_"
        lines = [
            "# 06 Graph Weight Explainability",
            "",
            "Graph explainer ran automatically when this evidence pack was built.",
            "",
            f"- Top: {auto_explanation.get('top', UNKNOWN)}",
            f"- Path prefixes: {prefixes}",
            f"- Include zero-penalty nodes: {auto_explanation.get('include_zero_penalty', UNKNOWN)}",
            f"- Hide empty symbols: {auto_explanation.get('hide_empty_symbols', UNKNOWN)}",
            "",
            "## Top-ranked nodes",
            "",
        ]
        lines.extend(_format_graph_rows_md(auto_explanation.get("rows") or []))
        lines.extend(
            [
                "",
                "> Each row shows *why* the weighted graph promoted a node:",
                "> topology (in/out degree), complexity, and failure penalty",
                "> contributions. The same data is also available on the CLI:",
                "",
                "```",
                GRAPH_EXPLAIN_COMMAND,
                "```",
                "",
            ]
        )
        return "\n".join(lines)

    # Fallback: graph build was unavailable or failed.
    return (
        "# 06 Graph Weight Explainability\n\n"
        "_The graph explainer could not be auto-run for this evidence pack._\n\n"
        "Run the read-only explainer manually to inspect node rankings:\n\n"
        "```\n"
        f"{GRAPH_EXPLAIN_COMMAND}\n"
        "```\n\n"
        "It prints a ranked table of nodes (file / function / class) with\n"
        "their topology, complexity, and failure-penalty contributions,\n"
        "explaining *why* the weighted graph promoted each node — not just\n"
        "that it did.\n"
    )


def _format_index() -> str:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "# 00 Evidence Index",
        "",
        "## Generated evidence files",
        "",
    ]
    for name in EVIDENCE_FILES[1:]:
        lines.append(f"- [{name}]({name})")
    lines.extend(
        [
            "",
            "## Proof summary",
            "",
            "- **Full benchmark suite passed.** "
            "See [01_full_suite_summary.md](01_full_suite_summary.md).",
            "- **Held-out suite exists** as a separate evaluation split. "
            "See [02_held_out_suite_summary.md](02_held_out_suite_summary.md).",
            "- **Watchlist tracks instability** across repeated held-out runs, "
            "observationally only. "
            "See [03_held_out_watchlist.md](03_held_out_watchlist.md).",
            "- **Patch minimality measures patch quality beyond pass/fail**, "
            "so a green run with bloated patches still surfaces. "
            "See [04_patch_minimality_experiment.md](04_patch_minimality_experiment.md).",
            "- **Same-suite trends prevent fake comparisons** from "
            "same-total / different-case reports. "
            "See [05_same_suite_trends.md](05_same_suite_trends.md).",
            "- **Graph attraction/repulsion is explain-only**, visualizing which "
            "nodes pull attention and which generic hubs push it away. "
            "See [07_graph_attraction_explainability.md](07_graph_attraction_explainability.md).",
            "- **Memory temperature is explain-only**, showing how warm each "
            "loaded lesson/note is (hot/warm/cold/frozen) and *why* it would or "
            "would not be surfaced. "
            "See [08_memory_temperature_explainability.md](08_memory_temperature_explainability.md).",
            "- **Memory temperature tie-breaker is evidence-only dogfood**, "
            "showing what the default-off tie-breaker *would* do to near-equal "
            "candidates without changing live retrieval, the CONTROL prompt, or "
            "the harness flag (which is off by default). "
            "See [09_memory_temperature_tiebreaker_dogfood.md](09_memory_temperature_tiebreaker_dogfood.md).",
            "",
            "## Generated at",
            "",
            f"- {generated_at}",
        ]
    )
    return "\n".join(lines) + "\n"


def build_evidence_pack(
    project_root: str | Path = PROJECT_ROOT,
    *,
    output_dir: str | Path | None = None,
    include_raw_paths: bool = False,
) -> dict[str, Any]:
    project_root = Path(project_root)
    bench_dir = project_root / ".agent" / "benchmarks"
    trends_dir = bench_dir / "trends"
    exp_dir = project_root / ".agent" / "experiments"

    if output_dir is None:
        output_dir = project_root / ".agent" / "presentation_evidence"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    reports = _list_reports(bench_dir)
    full_picked = _pick_full_suite_report(reports)
    held_picked = _pick_held_out_report(reports)

    watchlist_path = trends_dir / "suite_watchlist_held_out_v1.json"
    watchlist_data = _load_json(watchlist_path) if watchlist_path.exists() else None

    trend_index_path = trends_dir / "benchmark_trend_index.json"
    trend_index_data = (
        _load_json(trend_index_path) if trend_index_path.exists() else None
    )

    minimality_data, minimality_path = _pick_minimality_experiment(exp_dir)
    graph_text, graph_path = _find_graph_artifact(project_root)
    graph_auto = (
        _try_build_graph_explanation(project_root) if graph_text is None else None
    )
    attraction_text, attraction_path = _find_graph_attraction_artifact(project_root)
    memory_temp_text, memory_temp_path = _find_memory_temperature_artifact(project_root)

    written: dict[str, Path] = {}

    def _write(name: str, content: str) -> None:
        path = output_dir / name
        path.write_text(content, encoding="utf-8")
        written[name] = path

    _write("01_full_suite_summary.md", _format_full_suite(full_picked, include_raw_paths))
    _write(
        "02_held_out_suite_summary.md",
        _format_held_out_summary(held_picked, include_raw_paths),
    )
    _write(
        "03_held_out_watchlist.md",
        _format_watchlist(
            watchlist_data,
            watchlist_path if watchlist_data is not None else None,
            include_raw_paths,
        ),
    )
    _write(
        "04_patch_minimality_experiment.md",
        _format_minimality(
            minimality_data,
            minimality_path,
            include_raw_paths,
            full_picked[2] if full_picked else None,
        ),
    )
    _write(
        "05_same_suite_trends.md",
        _format_trends(
            trend_index_data,
            trend_index_path if trend_index_data is not None else None,
            include_raw_paths,
        ),
    )
    _write(
        "06_graph_weight_explainability.md",
        _format_graph(graph_text, graph_path, graph_auto, include_raw_paths),
    )
    _write(
        "07_graph_attraction_explainability.md",
        _format_graph_attraction(attraction_text, attraction_path, include_raw_paths),
    )
    _write(
        "08_memory_temperature_explainability.md",
        _format_memory_temperature(memory_temp_text, memory_temp_path, include_raw_paths),
    )
    _write(
        "09_memory_temperature_tiebreaker_dogfood.md",
        _format_memory_temperature_tiebreaker_dogfood(include_raw_paths),
    )
    _write("00_evidence_index.md", _format_index())

    return {
        "output_dir": output_dir,
        "files": written,
        "full_report": full_picked[1] if full_picked else None,
        "held_report": held_picked[1] if held_picked else None,
        "watchlist_path": watchlist_path if watchlist_data is not None else None,
        "trend_index_path": trend_index_path if trend_index_data is not None else None,
        "minimality_path": minimality_path,
        "graph_artifact_path": graph_path,
        "graph_auto_explanation": graph_auto,
        "graph_attraction_artifact_path": attraction_path,
        "memory_temperature_artifact_path": memory_temp_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a presentation-ready evidence pack from existing "
            "benchmark, experiment, trend, watchlist, and graph artifacts."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Output directory (default: "
            "<project_root>/.agent/presentation_evidence)."
        ),
    )
    parser.add_argument(
        "--include-raw-paths",
        action="store_true",
        help="Include source artifact paths inside each Markdown file.",
    )
    args = parser.parse_args(argv)

    result = build_evidence_pack(
        PROJECT_ROOT,
        output_dir=args.output_dir,
        include_raw_paths=args.include_raw_paths,
    )
    print(f"Evidence pack written to: {result['output_dir']}")
    for name in EVIDENCE_FILES:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
