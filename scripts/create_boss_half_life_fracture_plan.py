"""CMD.N1 - Create the Boss Half-Life Fracture Plan (CLI).

Writes deterministic JSON and Markdown planning artifacts for the report-only
Boss Half-Life Fracture model. The script computes expected half-life decay,
fracture pressure, and a Commander recommendation status. It does not decompose
tasks, assign workers, call models, launch Commander mode, affect routing, apply
patches, run validation, run benchmarks, contact networks, or write databases.
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

from core.boss_half_life_fracture_plan import (  # noqa: E402
    BOSS_HALF_LIFE_GUARDRAIL_NOTE,
    DEFAULT_ACTUAL_REMAINING,
    DEFAULT_AGGRESSIVENESS,
    DEFAULT_ATTEMPT,
    DEFAULT_INITIAL_COMPLEXITY,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_TOLERANCE,
    write_boss_half_life_fracture_plan,
)


DEFAULT_OUTPUT_DIR = str(Path(".agent") / "commander" / "boss_half_life_fracture_plan")


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    plan = result["plan"]
    params = plan.get("parameters") or {}
    decision = plan.get("decision") or {}
    next_phase = plan.get("recommended_next_phase") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": plan.get("report_kind"),
        "initial_complexity": params.get("initial_complexity"),
        "actual_remaining": decision.get("actual_remaining"),
        "attempt": params.get("attempt"),
        "max_attempts": params.get("max_attempts"),
        "aggressiveness": params.get("aggressiveness"),
        "half_life": params.get("half_life"),
        "tolerance": params.get("tolerance"),
        "expected_remaining": decision.get("expected_remaining"),
        "fracture_pressure": decision.get("fracture_pressure"),
        "decision_status": decision.get("status"),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": plan.get("warnings") or [],
        "blockers": plan.get("blockers") or [],
    }


def run_create_boss_half_life_fracture_plan(
    *,
    initial_complexity: float = DEFAULT_INITIAL_COMPLEXITY,
    actual_remaining: float = DEFAULT_ACTUAL_REMAINING,
    attempt: int = DEFAULT_ATTEMPT,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    aggressiveness: float = DEFAULT_AGGRESSIVENESS,
    tolerance: float = DEFAULT_TOLERANCE,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create the CMD.N1 report artifacts and return paths plus summary data."""
    result = write_boss_half_life_fracture_plan(
        output_dir=output_dir,
        initial_complexity=initial_complexity,
        actual_remaining=actual_remaining,
        attempt=attempt,
        max_attempts=max_attempts,
        aggressiveness=aggressiveness,
        tolerance=tolerance,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("CMD.N1 - Boss Half-Life Fracture Plan")
    print("=" * 40)
    print(f"Initial complexity : {summary['initial_complexity']}")
    print(f"Actual remaining   : {summary['actual_remaining']}")
    print(f"Attempt            : {summary['attempt']}")
    print(f"Max attempts       : {summary['max_attempts']}")
    print(f"Aggressiveness     : {summary['aggressiveness']}")
    print(f"Half-life          : {summary['half_life']}")
    print(f"Expected remaining : {summary['expected_remaining']}")
    print(f"Fracture pressure  : {summary['fracture_pressure']}")
    print(f"Decision status    : {summary['decision_status']}")
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
    print(f"\n> {BOSS_HALF_LIFE_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "CMD.N1: write the report-only Boss Half-Life Fracture Plan. "
            "Computes expected decay and fracture pressure; it does not execute "
            "Commander mode, decompose tasks, assign workers, call models, or "
            "change routing."
        )
    )
    parser.add_argument("--initial-complexity", type=float, default=DEFAULT_INITIAL_COMPLEXITY)
    parser.add_argument("--actual-remaining", type=float, default=DEFAULT_ACTUAL_REMAINING)
    parser.add_argument("--attempt", type=int, default=DEFAULT_ATTEMPT)
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--aggressiveness", type=float, default=DEFAULT_AGGRESSIVENESS)
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_boss_half_life_fracture_plan(
        initial_complexity=args.initial_complexity,
        actual_remaining=args.actual_remaining,
        attempt=args.attempt,
        max_attempts=args.max_attempts,
        aggressiveness=args.aggressiveness,
        tolerance=args.tolerance,
        output_dir=args.output_dir,
    )

    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
