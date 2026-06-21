"""EVAL.1 — Create the Live Benchmark Run Ledger (CLI).

Reads existing benchmark report artifacts (``.agent/benchmarks/benchmark_report_*.json``
by default), builds a deterministic run-by-run ledger with per-case history and
suspected flake candidates, and writes the ledger JSON + Markdown.

This tool is report-only. It does not run benchmarks, call models, apply patches,
edit benchmark cases, run validation, contact network services, write to a
database, launch workers, or merge. It reads the reports only and never mutates
them.

Usage:
    python scripts/create_benchmark_run_ledger.py --repo-path . --json
    python scripts/create_benchmark_run_ledger.py \\
        --input-glob ".agent/benchmarks/benchmark_report_*.json" --limit 20
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

from core.benchmark_run_ledger import (  # noqa: E402
    BENCHMARK_RUN_LEDGER_GUARDRAIL_NOTE,
    DEFAULT_INPUT_GLOB,
    write_benchmark_run_ledger,
)

DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "eval" / "benchmark_run_ledger")


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _default_ledger_id(created_iso: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'ledger'}_benchmark-run-ledger"


def run_create_benchmark_run_ledger(
    *,
    repo_path: str = ".",
    input_glob: str = DEFAULT_INPUT_GLOB,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    ledger_id: str | None = None,
    created_at: str | float | None = None,
    limit: int | None = None,
    json_out: bool = False,
) -> dict[str, Any]:
    """Scan benchmark reports and write the ledger.

    Returns ``{ok, json_path, md_path, report, ledger_id}``.
    """
    created_iso = _resolve_created_at(created_at)
    final_ledger_id = ledger_id or _default_ledger_id(created_iso)

    result = write_benchmark_run_ledger(
        repo_path,
        output_root,
        input_glob=input_glob,
        ledger_id=final_ledger_id,
        created_at=created_iso,
        limit=limit,
    )
    result["ledger_id"] = final_ledger_id
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    latest = report.get("latest_run_summary") or {}
    cost = report.get("cost_summary") or {}
    print("EVAL.1 — Live Benchmark Run Ledger")
    print("=" * 34)
    print(f"Ledger id        : {report.get('ledger_id')}")
    print(f"Repo path        : {report.get('repo_path')}")
    print(f"Input glob       : {report.get('input_glob')}")
    print(f"Run count        : {report.get('run_count')}")
    print(f"Case count       : {report.get('case_count')}")
    if latest:
        print(
            "Latest run       : "
            f"{latest.get('run_id')} "
            f"({latest.get('passed')}/{latest.get('total_cases')} passed, "
            f"rate {latest.get('success_rate')})"
        )
        if latest.get("failed_cases"):
            print(f"Latest failures  : {', '.join(latest['failed_cases'])}")
    else:
        print("Latest run       : (none)")
    flakes = report.get("flake_candidates") or []
    print(f"Flake candidates : {len(flakes)}")
    for case in flakes[:10]:
        print(f"  - {case.get('case_id')}: {', '.join(case.get('notes') or [])}")
    print(
        "Cost             : "
        f"tokens={cost.get('tokens_total')} "
        f"est_usd={cost.get('estimated_cost_usd_total')} "
        f"fallbacks={cost.get('total_fallbacks')}"
    )
    blockers = report.get("blockers") or []
    if blockers:
        print("Blockers         :")
        for blocker in blockers:
            print(f"  - {blocker}")
    warnings = report.get("warnings") or []
    if warnings:
        print("Warnings         :")
        for warning in warnings[:10]:
            print(f"  - {warning}")
    print(f"JSON             : {result['json_path']}")
    print(f"Markdown         : {result['md_path']}")
    print(f"\n> {BENCHMARK_RUN_LEDGER_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "EVAL.1: read existing benchmark report artifacts and write a deterministic "
            "run ledger with per-case history and flake candidates. Report-only — it does "
            "not run benchmarks, call models, apply patches, edit benchmark cases, run "
            "validation, contact network services, write to a database, launch workers, or "
            "merge."
        )
    )
    parser.add_argument("--repo-path", default=".", help="Repository root to resolve the input glob against.")
    parser.add_argument(
        "--input-glob",
        default=DEFAULT_INPUT_GLOB,
        help="Glob for benchmark report JSON files (default .agent/benchmarks/benchmark_report_*.json).",
    )
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory to write the ledger into.")
    parser.add_argument("--ledger-id", default=None, help="Deterministic ledger id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Use at most the N most recent runs.")
    parser.add_argument("--json", action="store_true", help="Print the ledger report JSON.")
    args = parser.parse_args(argv)

    result = run_create_benchmark_run_ledger(
        repo_path=args.repo_path,
        input_glob=args.input_glob,
        output_root=args.output_root,
        ledger_id=args.ledger_id,
        created_at=args.created_at,
        limit=args.limit,
        json_out=args.json,
    )

    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
