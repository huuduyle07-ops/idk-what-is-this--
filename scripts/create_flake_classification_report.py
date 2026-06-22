"""EVAL.3 - Create the Flake Classification Report (CLI).

Reads existing EVAL.1/EVAL.2 evidence and benchmark reports as fallback input,
then writes deterministic JSON and Markdown stability triage artifacts.

This tool is report-only. It does not run benchmarks, call models, apply patches,
edit benchmark cases, run validation, contact network services, write to a
database, launch workers, or merge.
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

from core.flake_classification_report import (  # noqa: E402
    DEFAULT_COMPARE_ROOT,
    DEFAULT_INPUT_GLOB,
    DEFAULT_LEDGER_PATH,
    DEFAULT_OUTPUT_ROOT,
    FLAKE_CLASSIFICATION_GUARDRAIL_NOTE,
    write_flake_classification_report,
)


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _default_report_id(created_iso: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'report'}_flake-classification-report"


def run_create_flake_classification_report(
    *,
    repo_path: str = ".",
    ledger_path: str = DEFAULT_LEDGER_PATH,
    compare_root: str = DEFAULT_COMPARE_ROOT,
    input_glob: str = DEFAULT_INPUT_GLOB,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | float | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Create the EVAL.3 report and return its paths plus report record."""
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)
    result = write_flake_classification_report(
        repo_path,
        output_root,
        ledger_path=ledger_path,
        compare_root=compare_root,
        input_glob=input_glob,
        report_id=final_report_id,
        created_at=created_iso,
        limit=limit,
    )
    result["report_id"] = final_report_id
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    counts = report.get("classification_counts") or {}
    source = report.get("source_summary") or {}
    print("EVAL.3 - Flake Classification Report")
    print("=" * 37)
    print(f"Report id        : {report.get('report_id')}")
    print(f"Repo path        : {report.get('repo_path')}")
    print(f"Ledger path      : {report.get('ledger_path')}")
    print(f"Compare root     : {report.get('compare_root')}")
    print(f"Input glob       : {report.get('input_glob')}")
    print(f"Case count       : {report.get('case_count')}")
    print(
        "Sources          : "
        f"ledger={bool(source.get('ledger_loaded'))} "
        f"compare={source.get('compare_reports_loaded', 0)} "
        f"benchmark_reports={source.get('benchmark_reports_loaded', 0)} "
        f"fallback={bool(source.get('fallback_used'))}"
    )
    print(
        "Classifications  : "
        f"stable={counts.get('stable', 0)} "
        f"flake={counts.get('likely_flake', 0)} "
        f"broken={counts.get('likely_broken', 0)} "
        f"needs_rerun={counts.get('needs_rerun', 0)} "
        f"insufficient={counts.get('insufficient_history', 0)}"
    )
    flakes = report.get("likely_flakes") or []
    if flakes:
        print("Likely flakes    :")
        for case in flakes[:10]:
            print(f"  - {case.get('case_id')}: {case.get('recommended_action')}")
    broken = report.get("likely_broken_cases") or []
    if broken:
        print("Likely broken    :")
        for case in broken[:10]:
            print(f"  - {case.get('case_id')}: {case.get('recommended_action')}")
    rerun = report.get("needs_rerun_cases") or []
    if rerun:
        print("Needs rerun      :")
        for case in rerun[:10]:
            print(f"  - {case.get('case_id')}: {case.get('recommended_action')}")
    warnings = report.get("warnings") or []
    if warnings:
        print("Warnings         :")
        for warning in warnings[:10]:
            print(f"  - {warning}")
    blockers = report.get("blockers") or []
    if blockers:
        print("Blockers         :")
        for blocker in blockers:
            print(f"  - {blocker}")
    print(f"JSON             : {result['json_path']}")
    print(f"Markdown         : {result['md_path']}")
    print(f"\n> {FLAKE_CLASSIFICATION_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "EVAL.3: read existing benchmark stability evidence and write a "
            "deterministic flake classification report. Report-only: it does not run "
            "benchmarks, call models, apply patches, edit benchmark cases, run "
            "validation, contact network services, write to a database, launch workers, "
            "or merge."
        )
    )
    parser.add_argument("--repo-path", default=".", help="Repository root for resolving relative inputs.")
    parser.add_argument("--ledger", default=DEFAULT_LEDGER_PATH, help="EVAL.1 ledger JSON path.")
    parser.add_argument("--compare-root", default=DEFAULT_COMPARE_ROOT, help="Directory containing EVAL.2 compare JSON files.")
    parser.add_argument(
        "--input-glob",
        default=DEFAULT_INPUT_GLOB,
        help="Benchmark report glob used only as fallback evidence.",
    )
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory to write the report artifacts into.")
    parser.add_argument("--report-id", default=None, help="Deterministic report id.")
    parser.add_argument("--created-at", default=None, help="Deterministic created-at string or epoch seconds.")
    parser.add_argument("--limit", type=int, default=None, help="Classify at most N highest-priority cases.")
    parser.add_argument("--json", action="store_true", help="Print the report JSON.")
    args = parser.parse_args(argv)

    result = run_create_flake_classification_report(
        repo_path=args.repo_path,
        ledger_path=args.ledger,
        compare_root=args.compare_root,
        input_glob=args.input_glob,
        output_root=args.output_root,
        report_id=args.report_id,
        created_at=args.created_at,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
