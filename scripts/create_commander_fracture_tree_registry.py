"""CMD.N3 - Create a Commander Fracture Tree Registry (CLI).

Writes deterministic JSON and Markdown artifacts for a report-only Commander
fracture tree registry. Inputs are manual: a CMD.N2 report, a manually written
tree JSON file, or minimal CLI metadata. The script does not execute sub-bosses,
assign real workers, call models, launch Commander mode, route tasks, apply
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

from core.commander_fracture_tree_registry import (  # noqa: E402
    COMMANDER_FRACTURE_TREE_REGISTRY_GUARDRAIL_NOTE,
    DEFAULT_OUTPUT_ROOT,
    read_json_input,
    write_commander_fracture_tree_registry,
)


DEFAULT_OUTPUT_DIR = str(DEFAULT_OUTPUT_ROOT)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    registry = result["registry"]
    next_phase = registry.get("recommended_next_phase") or {}
    source = registry.get("source_inputs") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": registry.get("report_kind"),
        "tree_id": registry.get("tree_id"),
        "boss_id": registry.get("boss_id"),
        "title": registry.get("title"),
        "input_source": source.get("input_source"),
        "validation_status": registry.get("validation_status"),
        "sub_boss_count": (registry.get("validation_findings") or {}).get("sub_boss_count"),
        "dependency_edge_count": (registry.get("validation_findings") or {}).get("dependency_edge_count"),
        "total_expected_complexity": registry.get("total_expected_complexity"),
        "total_attempt_budget": registry.get("total_attempt_budget"),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": registry.get("warnings") or [],
        "blocked_reasons": registry.get("blocked_reasons") or [],
    }


def run_create_commander_fracture_tree_registry(
    *,
    tree_id: str,
    boss_id: str,
    title: str,
    source_report: str | None = None,
    tree_file: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create CMD.N3 registry artifacts and return paths plus summary data."""
    source_data, source_blockers = read_json_input(source_report, "source_report")
    tree_data, tree_blockers = read_json_input(tree_file, "tree_file")
    result = write_commander_fracture_tree_registry(
        output_dir=output_dir,
        tree_id=tree_id,
        boss_id=boss_id,
        title=title,
        source_report_path=str(source_report or ""),
        tree_file_path=str(tree_file or ""),
        source_report=source_data,
        tree_data=tree_data,
        input_blockers=source_blockers + tree_blockers,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("CMD.N3 - Commander Fracture Tree Registry")
    print("=" * 44)
    print(f"Tree id             : {summary['tree_id']}")
    print(f"Boss id             : {summary['boss_id']}")
    print(f"Title               : {summary['title']}")
    print(f"Input source        : {summary['input_source']}")
    print(f"Validation status   : {summary['validation_status']}")
    print(f"Sub-boss count      : {summary['sub_boss_count']}")
    print(f"Dependency edges    : {summary['dependency_edge_count']}")
    print(f"Expected complexity : {summary['total_expected_complexity']}")
    print(f"Attempt budget      : {summary['total_attempt_budget']}")
    print(f"Recommended next    : {summary['recommended_next_phase']}")
    print(f"JSON                : {summary['json_path']}")
    print(f"Markdown            : {summary['md_path']}")
    blocked = summary["blocked_reasons"]
    if blocked:
        print("Blocked reasons     :")
        for reason in blocked:
            print(f"  - {reason}")
    warnings = summary["warnings"]
    if warnings:
        print("Warnings            :")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"\n> {COMMANDER_FRACTURE_TREE_REGISTRY_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "CMD.N3: write a report-only Commander Fracture Tree Registry. "
            "Inputs must be a CMD.N2 report, a manual tree JSON file, or "
            "minimal CLI metadata. The registry validates only; it does not "
            "execute, assign workers, call models, route tasks, or run checks."
        )
    )
    parser.add_argument("--tree-id", required=True)
    parser.add_argument("--boss-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--source-report")
    parser.add_argument("--tree-file")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_commander_fracture_tree_registry(
        tree_id=args.tree_id,
        boss_id=args.boss_id,
        title=args.title,
        source_report=args.source_report,
        tree_file=args.tree_file,
        output_dir=args.output_dir,
    )

    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
