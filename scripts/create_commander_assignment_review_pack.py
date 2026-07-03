"""CMD.N6 - Create a Commander Assignment Review Pack (CLI).

Writes deterministic JSON and Markdown artifacts for a report-only Commander
assignment review pack. Inputs are CMD.N3, CMD.N4, and CMD.N5 JSON artifacts.
The script packages review state only; it does not launch workers, bind model
or worker authority, run validation, run benchmarks, apply patches, mutate
source artifacts, route tasks, contact networks, or write databases.
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

from core.commander_assignment_review_pack import (  # noqa: E402
    COMMANDER_ASSIGNMENT_REVIEW_PACK_GUARDRAIL_NOTE,
    DEFAULT_OUTPUT_ROOT,
    write_commander_assignment_review_pack,
)


DEFAULT_OUTPUT_DIR = str(DEFAULT_OUTPUT_ROOT)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "review_id": report.get("review_id"),
        "tree_id": report.get("tree_id"),
        "boss_id": report.get("boss_id"),
        "review_status": report.get("review_status"),
        "sub_boss_review_count": len(report.get("per_sub_boss_review") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": report.get("warnings") or [],
        "blocked_reasons": report.get("blocked_reasons") or [],
    }


def run_create_commander_assignment_review_pack(
    *,
    tree: str,
    preflight: str,
    assignment: str,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create CMD.N6 review-pack artifacts and return paths plus summary data."""
    result = write_commander_assignment_review_pack(
        tree_path=tree,
        preflight_path=preflight,
        assignment_path=assignment,
        output_dir=output_dir,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("CMD.N6 - Commander Assignment Review Pack")
    print("=" * 45)
    print(f"Review id          : {summary['review_id']}")
    print(f"Tree id            : {summary['tree_id']}")
    print(f"Boss id            : {summary['boss_id']}")
    print(f"Review status      : {summary['review_status']}")
    print(f"Sub-boss reviews   : {summary['sub_boss_review_count']}")
    print(f"Recommended next   : {summary['recommended_next_phase']}")
    print(f"JSON               : {summary['json_path']}")
    print(f"Markdown           : {summary['md_path']}")
    blocked = summary["blocked_reasons"]
    if blocked:
        print("Blocked reasons    :")
        for reason in blocked:
            print(f"  - {reason}")
    warnings = summary["warnings"]
    if warnings:
        print("Warnings           :")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"\n> {COMMANDER_ASSIGNMENT_REVIEW_PACK_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "CMD.N6: write a report-only Commander Assignment Review Pack from "
            "CMD.N3, CMD.N4, and CMD.N5 JSON artifacts. It packages review "
            "state only; it does not launch workers, call models, route tasks, "
            "run validation, run benchmarks, apply patches, or mutate source "
            "artifacts."
        )
    )
    parser.add_argument("--tree", required=True, help="Path to CMD.N3 commander_fracture_tree_registry.json.")
    parser.add_argument("--preflight", required=True, help="Path to CMD.N4 commander_preflight_contract.json.")
    parser.add_argument("--assignment", required=True, help="Path to CMD.N5 commander_manual_assignment_plan.json.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_commander_assignment_review_pack(
        tree=args.tree,
        preflight=args.preflight,
        assignment=args.assignment,
        output_dir=args.output_dir,
    )

    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
