"""EVAL.2 — Compare Benchmark Reports for a Case (CLI).

Reads existing benchmark report artifacts and explains one case (or every suspected
flake candidate) across them: which reports mention the case, which runs passed or
failed, which report is latest and why, and whether the evidence supports a likely
flake or a likely broken case. It optionally cross-checks the EVAL.1 ledger.

This tool is report-only. It does not run benchmarks, call models, apply patches,
edit benchmark cases, run validation, contact network services, write to a database,
launch workers, or merge. It reads reports and the optional ledger only, never
mutating them.

Usage:
    python scripts/compare_benchmark_reports.py --repo-path . \\
        --case-id ts_migration_import_path_case --json
    python scripts/compare_benchmark_reports.py --repo-path . --all-flake-candidates
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

from core.benchmark_report_compare import (  # noqa: E402
    BENCHMARK_REPORT_COMPARE_GUARDRAIL_NOTE,
    DEFAULT_LEDGER_PATH,
    write_case_comparison,
    write_flake_candidates_comparison,
)
from core.benchmark_run_ledger import DEFAULT_INPUT_GLOB  # noqa: E402

DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "eval" / "benchmark_report_compare")


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _default_comparison_id(created_iso: str, slug: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'compare'}_{slug}"


def run_compare_benchmark_reports(
    *,
    repo_path: str = ".",
    input_glob: str = DEFAULT_INPUT_GLOB,
    ledger_path: str | None = None,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    case_id: str | None = None,
    all_flake_candidates: bool = False,
    comparison_id: str | None = None,
    created_at: str | float | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Build and write a single-case or all-flake-candidates comparison.

    Returns ``{ok, json_path, md_path, report, comparison_id}``.
    """
    created_iso = _resolve_created_at(created_at)
    slug = "flake-candidates-compare" if all_flake_candidates else f"{case_id}-compare"
    final_comparison_id = comparison_id or _default_comparison_id(created_iso, slug)

    if all_flake_candidates:
        result = write_flake_candidates_comparison(
            repo_path,
            output_root,
            input_glob=input_glob,
            ledger_path=ledger_path,
            comparison_id=final_comparison_id,
            created_at=created_iso,
            limit=limit,
        )
    else:
        result = write_case_comparison(
            repo_path,
            output_root,
            case_id=str(case_id),
            input_glob=input_glob,
            ledger_path=ledger_path,
            comparison_id=final_comparison_id,
            created_at=created_iso,
            limit=limit,
        )
    result["comparison_id"] = final_comparison_id
    return result


def _print_summary(result: dict[str, Any], *, all_flake_candidates: bool) -> None:
    report = result["report"]
    print("EVAL.2 — Benchmark Report Compare")
    print("=" * 33)
    print(f"Comparison id    : {report.get('comparison_id')}")
    print(f"Repo path        : {report.get('repo_path')}")
    print(f"Input glob       : {report.get('input_glob')}")
    print(
        "Reports          : "
        f"matched={report.get('matched_report_count')} "
        f"loaded={report.get('loaded_report_count')} "
        f"skipped={report.get('skipped_report_count')}"
    )
    if all_flake_candidates:
        print(f"Flake candidates : {report.get('case_count')}")
        for comparison in (report.get("comparisons") or [])[:20]:
            print(f"  - {comparison.get('case_id')}: {comparison.get('classification')}")
    else:
        print(f"Case id          : {report.get('case_id')}")
        print(f"Classification   : {report.get('classification')}")
        latest = report.get("latest_observation") or {}
        if latest:
            print(f"Latest           : {latest.get('run_id')} -> {latest.get('status')} (scope {latest.get('suite_scope')})")
        else:
            print("Latest           : (none)")
        print(f"Evidence labels  : {', '.join(report.get('evidence_labels') or []) or '(none)'}")
        ledger = report.get("ledger_reference") or {}
        print(f"Ledger present   : {bool(ledger.get('present'))} (flake candidate: {bool(ledger.get('case_is_flake_candidate'))})")
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
    print(f"\n> {BENCHMARK_REPORT_COMPARE_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "EVAL.2: compare existing benchmark report artifacts to explain a case "
            "across runs and classify its flake evidence. Report-only — it does not run "
            "benchmarks, call models, apply patches, edit benchmark cases, run "
            "validation, contact network services, write to a database, launch workers, "
            "or merge."
        )
    )
    parser.add_argument("--repo-path", default=".", help="Repository root to resolve the input glob against.")
    parser.add_argument(
        "--input-glob",
        default=DEFAULT_INPUT_GLOB,
        help="Glob for benchmark report JSON files (default .agent/benchmarks/benchmark_report_*.json).",
    )
    parser.add_argument(
        "--ledger",
        default=DEFAULT_LEDGER_PATH,
        help="Optional EVAL.1 ledger JSON to cross-check (missing is fine).",
    )
    parser.add_argument("--case-id", default=None, help="Case id to explain (required unless --all-flake-candidates).")
    parser.add_argument(
        "--all-flake-candidates",
        action="store_true",
        help="Compare every suspected flake candidate and write an aggregate report.",
    )
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory to write the comparison into.")
    parser.add_argument("--comparison-id", default=None, help="Deterministic comparison id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Use at most the N most recent reports.")
    parser.add_argument("--json", action="store_true", help="Print the comparison report JSON.")
    args = parser.parse_args(argv)

    if not args.all_flake_candidates and not args.case_id:
        parser.error("--case-id is required unless --all-flake-candidates is used")

    result = run_compare_benchmark_reports(
        repo_path=args.repo_path,
        input_glob=args.input_glob,
        ledger_path=args.ledger,
        output_root=args.output_root,
        case_id=args.case_id,
        all_flake_candidates=args.all_flake_candidates,
        comparison_id=args.comparison_id,
        created_at=args.created_at,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result, all_flake_candidates=args.all_flake_candidates)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
