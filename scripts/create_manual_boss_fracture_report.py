"""CMD.N2 - Create a Manual Boss Fracture Report (CLI).

Writes deterministic JSON and Markdown artifacts for one manually described
Commander boss. The script applies CMD.N1 half-life math and includes only
manual sub-boss candidates from an optional JSON file. It does not call models,
decompose tasks automatically, assign workers, launch workers, route tasks,
apply patches, run validation, run benchmarks, contact networks, or write
databases.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.manual_boss_fracture_report import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    MANUAL_BOSS_FRACTURE_GUARDRAIL_NOTE,
    read_sub_boss_candidates,
    write_manual_boss_fracture_report,
)


DEFAULT_OUTPUT_DIR = str(DEFAULT_OUTPUT_ROOT)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    boss = report.get("boss_input") or {}
    params = report.get("half_life_parameters") or {}
    decision = report.get("commander_decision") or {}
    next_phase = report.get("recommended_next_phase") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "boss_id": boss.get("boss_id"),
        "title": boss.get("title"),
        "initial_complexity": params.get("initial_complexity"),
        "actual_remaining": report.get("actual_remaining_complexity"),
        "attempt": params.get("attempt"),
        "max_attempts": params.get("max_attempts"),
        "aggressiveness": params.get("aggressiveness"),
        "half_life": params.get("half_life"),
        "tolerance": params.get("tolerance"),
        "expected_remaining": report.get("expected_remaining_complexity"),
        "fracture_pressure": report.get("fracture_pressure"),
        "decision_status": decision.get("status"),
        "sub_boss_count": (report.get("summary") or {}).get("sub_boss_count"),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": report.get("warnings") or [],
        "blockers": report.get("blockers") or [],
    }


def run_create_manual_boss_fracture_report(
    *,
    boss_id: str,
    title: str,
    description: str,
    initial_complexity: float,
    actual_remaining: float,
    attempt: int,
    max_attempts: int,
    aggressiveness: float,
    tolerance: float,
    sub_boss_file: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create CMD.N2 report artifacts and return paths plus summary data."""
    sub_bosses, sub_boss_blockers = read_sub_boss_candidates(sub_boss_file)
    result = write_manual_boss_fracture_report(
        output_dir=output_dir,
        boss_id=boss_id,
        title=title,
        description=description,
        initial_complexity=initial_complexity,
        actual_remaining=actual_remaining,
        attempt=attempt,
        max_attempts=max_attempts,
        aggressiveness=aggressiveness,
        tolerance=tolerance,
        sub_bosses=sub_bosses,
        sub_boss_blockers=sub_boss_blockers,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("CMD.N2 - Manual Boss Fracture Report")
    print("=" * 39)
    print(f"Boss id            : {summary['boss_id']}")
    print(f"Title              : {summary['title']}")
    print(f"Initial complexity : {summary['initial_complexity']}")
    print(f"Actual remaining   : {summary['actual_remaining']}")
    print(f"Attempt            : {summary['attempt']}")
    print(f"Max attempts       : {summary['max_attempts']}")
    print(f"Aggressiveness     : {summary['aggressiveness']}")
    print(f"Half-life          : {summary['half_life']}")
    print(f"Expected remaining : {summary['expected_remaining']}")
    print(f"Fracture pressure  : {summary['fracture_pressure']}")
    print(f"Decision status    : {summary['decision_status']}")
    print(f"Sub-boss count     : {summary['sub_boss_count']}")
    print(f"Recommended next   : {summary['recommended_next_phase']}")
    print(f"JSON               : {summary['json_path']}")
    print(f"Markdown           : {summary['md_path']}")
    blockers = summary["blockers"]
    if blockers:
        print("Blockers           :")
        for blocker in blockers:
            print(f"  - {blocker}")
    warnings = summary["warnings"]
    if warnings:
        print("Warnings           :")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"\n> {MANUAL_BOSS_FRACTURE_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "CMD.N2: write a report-only Manual Boss Fracture Report. "
            "Applies CMD.N1 math to manual boss input and optional manual "
            "sub-boss JSON; it does not call models, decompose tasks, assign "
            "workers, route tasks, run validation, or run benchmarks."
        )
    )
    parser.add_argument("--boss-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--initial-complexity", type=float, required=True)
    parser.add_argument("--actual-remaining", type=float, required=True)
    parser.add_argument("--attempt", type=int, required=True)
    parser.add_argument("--max-attempts", type=int, required=True)
    parser.add_argument("--aggressiveness", type=float, required=True)
    parser.add_argument("--tolerance", type=float, required=True)
    parser.add_argument("--sub-boss-file")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_manual_boss_fracture_report(
        boss_id=args.boss_id,
        title=args.title,
        description=args.description,
        initial_complexity=args.initial_complexity,
        actual_remaining=args.actual_remaining,
        attempt=args.attempt,
        max_attempts=args.max_attempts,
        aggressiveness=args.aggressiveness,
        tolerance=args.tolerance,
        sub_boss_file=args.sub_boss_file,
        output_dir=args.output_dir,
    )

    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
