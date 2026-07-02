"""CMD.N5 - Create a Commander Manual Assignment Plan (CLI).

Writes deterministic JSON and Markdown artifacts for a report-only Commander
manual assignment plan. Input is a CMD.N4 Commander Preflight Contract JSON
artifact. The script maps sub-bosses to advisory role labels only; it does not
launch workers, bind executable worker IDs, call models, route tasks, apply
patches, run validation, run benchmarks, or mutate the source preflight/tree.
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

from core.commander_manual_assignment_plan import (  # noqa: E402
    COMMANDER_MANUAL_ASSIGNMENT_PLAN_GUARDRAIL_NOTE,
    DEFAULT_OUTPUT_ROOT,
    write_commander_manual_assignment_plan,
)


DEFAULT_OUTPUT_DIR = str(DEFAULT_OUTPUT_ROOT)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") or {}
    source = report.get("source_preflight") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "plan_id": report.get("plan_id"),
        "tree_id": report.get("tree_id"),
        "boss_id": report.get("boss_id"),
        "title": report.get("title"),
        "source_preflight_path": report.get("source_preflight_path"),
        "source_preflight_status": source.get("preflight_status"),
        "assignment_status": report.get("assignment_status"),
        "assignment_count": len(report.get("assignments") or []),
        "unassigned_sub_boss_count": len(report.get("unassigned_sub_bosses") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": report.get("warnings") or [],
        "blocked_reasons": report.get("blocked_reasons") or [],
    }


def run_create_commander_manual_assignment_plan(
    *,
    preflight: str,
    role_catalog: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create CMD.N5 assignment artifacts and return paths plus summary data."""
    result = write_commander_manual_assignment_plan(
        preflight_path=preflight,
        role_catalog_path=role_catalog,
        output_dir=output_dir,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("CMD.N5 - Commander Manual Assignment Plan")
    print("=" * 45)
    print(f"Plan id              : {summary['plan_id']}")
    print(f"Tree id              : {summary['tree_id']}")
    print(f"Boss id              : {summary['boss_id']}")
    print(f"Title                : {summary['title']}")
    print(f"Preflight status     : {summary['source_preflight_status']}")
    print(f"Assignment status    : {summary['assignment_status']}")
    print(f"Assignments          : {summary['assignment_count']}")
    print(f"Unassigned sub-bosses: {summary['unassigned_sub_boss_count']}")
    print(f"Recommended next     : {summary['recommended_next_phase']}")
    print(f"JSON                 : {summary['json_path']}")
    print(f"Markdown             : {summary['md_path']}")
    blocked = summary["blocked_reasons"]
    if blocked:
        print("Blocked reasons      :")
        for reason in blocked:
            print(f"  - {reason}")
    warnings = summary["warnings"]
    if warnings:
        print("Warnings             :")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"\n> {COMMANDER_MANUAL_ASSIGNMENT_PLAN_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "CMD.N5: write a report-only Commander Manual Assignment Plan from "
            "a CMD.N4 preflight contract JSON artifact. It assigns advisory "
            "role labels only; it does not launch workers, call models, route "
            "tasks, run validation, run benchmarks, apply patches, or mutate "
            "source artifacts."
        )
    )
    parser.add_argument("--preflight", required=True, help="Path to CMD.N4 commander_preflight_contract.json.")
    parser.add_argument("--role-catalog", help="Optional manual advisory role catalog JSON.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_commander_manual_assignment_plan(
        preflight=args.preflight,
        role_catalog=args.role_catalog,
        output_dir=args.output_dir,
    )

    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
