"""CMD.N4 - Create a Commander Preflight Contract (CLI).

Writes deterministic JSON and Markdown artifacts for a report-only Commander
preflight contract. Input is a CMD.N3 fracture tree registry JSON artifact. The
script evaluates only; it does not execute sub-bosses, assign real workers, call
models, run validation, run benchmarks, route tasks, apply patches, mutate
execution eligibility, contact networks, or write databases.
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

from core.commander_preflight_contract import (  # noqa: E402
    COMMANDER_PREFLIGHT_CONTRACT_GUARDRAIL_NOTE,
    DEFAULT_OUTPUT_ROOT,
    write_commander_preflight_contract,
)


DEFAULT_OUTPUT_DIR = str(DEFAULT_OUTPUT_ROOT)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") or {}
    source = report.get("source_tree") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "tree_id": report.get("tree_id"),
        "boss_id": report.get("boss_id"),
        "title": report.get("title"),
        "source_tree_path": report.get("source_tree_path"),
        "tree_validation_status": source.get("validation_status"),
        "requested_sub_boss_id": report.get("requested_sub_boss_id"),
        "evaluated_sub_boss_count": report.get("evaluated_sub_boss_count"),
        "preflight_status": report.get("preflight_status"),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": report.get("warnings") or [],
        "incomplete_reasons": report.get("incomplete_reasons") or [],
        "blocked_reasons": report.get("blocked_reasons") or [],
    }


def run_create_commander_preflight_contract(
    *,
    tree: str,
    sub_boss_id: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create CMD.N4 preflight artifacts and return paths plus summary data."""
    result = write_commander_preflight_contract(
        tree_path=tree,
        output_dir=output_dir,
        sub_boss_id=sub_boss_id,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("CMD.N4 - Commander Preflight Contract")
    print("=" * 42)
    print(f"Tree id             : {summary['tree_id']}")
    print(f"Boss id             : {summary['boss_id']}")
    print(f"Title               : {summary['title']}")
    print(f"Tree status         : {summary['tree_validation_status']}")
    print(f"Requested sub-boss  : {summary['requested_sub_boss_id'] or '(all)'}")
    print(f"Evaluated sub-bosses: {summary['evaluated_sub_boss_count']}")
    print(f"Preflight status    : {summary['preflight_status']}")
    print(f"Recommended next    : {summary['recommended_next_phase']}")
    print(f"JSON                : {summary['json_path']}")
    print(f"Markdown            : {summary['md_path']}")
    blocked = summary["blocked_reasons"]
    if blocked:
        print("Blocked reasons     :")
        for reason in blocked:
            print(f"  - {reason}")
    incomplete = summary["incomplete_reasons"]
    if incomplete:
        print("Incomplete reasons  :")
        for reason in incomplete:
            print(f"  - {reason}")
    warnings = summary["warnings"]
    if warnings:
        print("Warnings            :")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"\n> {COMMANDER_PREFLIGHT_CONTRACT_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "CMD.N4: write a report-only Commander Preflight Contract from a "
            "CMD.N3 fracture tree registry JSON artifact. It evaluates only; "
            "it does not execute, assign workers, call models, route tasks, "
            "run validation, run benchmarks, or mutate eligibility."
        )
    )
    parser.add_argument("--tree", required=True, help="Path to CMD.N3 commander_fracture_tree_registry.json.")
    parser.add_argument("--sub-boss-id", help="Evaluate only one registered sub-boss.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_commander_preflight_contract(
        tree=args.tree,
        sub_boss_id=args.sub_boss_id,
        output_dir=args.output_dir,
    )

    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
