"""Phase 14.4 — Failure Taxonomy Trend Report export (read-only).

Read the ``benchmark_report_*.json`` files under ``.agent/benchmarks`` (oldest
first), compare their Phase 14 failure taxonomies with
``core.failure_taxonomy_trends.compare_failure_taxonomies``, and write a trend
report as JSON + Markdown under ``.agent/failure_taxonomy``.

This exporter is read-only with respect to the system under test: it never runs
benchmarks, generates/applies patches, runs validation, promotes lessons, runs
Dream automation, calls a model/API, writes a database, spawns subprocesses,
touches Docker, or makes network calls. The *only* writes it performs are the
two trend artifacts it is explicitly asked to produce; it never mutates the
source benchmark reports. Nothing here is wired into live benchmark scoring.
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

from core.failure_taxonomy_trends import (  # noqa: E402
    compare_failure_taxonomies,
    format_trend_markdown,
)

DEFAULT_OUTPUT_DIR = ".agent/failure_taxonomy"
BENCHMARK_SUBDIR = (".agent", "benchmarks")
BENCHMARK_GLOB = "benchmark_report_*.json"


def _benchmark_report_sort_key(path: Path) -> tuple[int, float, str]:
    """Sort oldest-first: prefer the numeric suffix, fall back to mtime."""
    suffix = path.stem.rsplit("_", 1)[-1]
    try:
        numeric = int(suffix)
    except ValueError:
        numeric = -1
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (numeric, mtime, path.name)


def _load_valid_reports(
    repo_path: str | Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return ``(reports, identifiers)`` for valid benchmark report JSON files.

    Missing/invalid JSON files are skipped (not fatal); the caller decides
    whether enough valid reports remain.
    """
    bench_dir = Path(repo_path).joinpath(*BENCHMARK_SUBDIR)
    if not bench_dir.is_dir():
        return [], []
    paths = sorted(bench_dir.glob(BENCHMARK_GLOB), key=_benchmark_report_sort_key)
    reports: list[dict[str, Any]] = []
    identifiers: list[str] = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            reports.append(data)
            identifiers.append(path.stem)
    return reports, identifiers


def export_failure_taxonomy_trend_report(
    *,
    repo_path: str = ".",
    output_dir: str = DEFAULT_OUTPUT_DIR,
    generated_at: float,
) -> dict[str, Any]:
    """Build and write the trend report JSON + Markdown.

    Returns a result dict with ``ok``; on success it includes ``json_path`` and
    ``md_path``; on failure it includes a friendly ``error`` and null paths.
    """
    reports, identifiers = _load_valid_reports(repo_path)
    if len(reports) < 2:
        return _failure(
            "need at least two valid benchmark reports under "
            ".agent/benchmarks to compute a trend "
            f"(found {len(reports)})"
        )

    trend = compare_failure_taxonomies(reports, identifiers=identifiers)
    if not trend.get("ok"):
        return _failure(trend.get("error", "could not compute trend"))

    trend = {
        "report_kind": "failure_taxonomy_trend",
        "generated_at": datetime.fromtimestamp(
            generated_at, tz=timezone.utc
        ).isoformat(),
        "generated_at_epoch": generated_at,
        **trend,
    }

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = int(generated_at)
    json_path = out_dir / f"{stamp}_failure_taxonomy_trend.json"
    md_path = out_dir / f"{stamp}_failure_taxonomy_trend.md"
    json_path.write_text(
        json.dumps(trend, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path.write_text(format_trend_markdown(trend), encoding="utf-8")

    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "trend": trend,
    }


def _failure(error: str) -> dict[str, Any]:
    return {"ok": False, "error": error, "json_path": None, "md_path": None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export a read-only failure taxonomy trend report by comparing the "
            ".agent/benchmarks/benchmark_report_*.json files. Does not change "
            "scoring, patching, validation, or lessons."
        ),
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Repo root containing .agent/benchmarks (default: .).",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for trend artifacts (default: {DEFAULT_OUTPUT_DIR}).",
    )
    args = parser.parse_args(argv)

    result = export_failure_taxonomy_trend_report(
        repo_path=args.repo_path,
        output_dir=args.output_dir,
        generated_at=datetime.now(tz=timezone.utc).timestamp(),
    )

    if not result["ok"]:
        print(f"Failed: {result['error']}")
        return 1

    trend = result["trend"]
    print(
        f"Compared {trend['report_count']} benchmark report(s): "
        f"{trend['baseline']} -> {trend['latest']}."
    )
    if trend["new_categories"]:
        print(f"  New categories: {', '.join(trend['new_categories'])}")
    if trend["disappeared_categories"]:
        print(
            f"  Disappeared categories: "
            f"{', '.join(trend['disappeared_categories'])}"
        )
    print(f"JSON: {result['json_path']}")
    print(f"Markdown: {result['md_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
