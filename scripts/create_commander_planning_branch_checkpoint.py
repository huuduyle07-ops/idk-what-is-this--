"""CMD.CLOSE - Create Commander Planning Branch Checkpoint (CLI).

Reads the phase registry and CMD.N1-CMD.N6 planning artifacts, then writes a
report-only Commander planning branch checkpoint. It does not launch workers,
bind model or worker authority, call models, route tasks, run tools, run
validation, run benchmarks, apply patches, mutate source artifacts, contact
networks, use Docker/subprocess, write databases, or change route/auth/routing
behavior.
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

from core.commander_planning_branch_checkpoint import (  # noqa: E402
    COMMANDER_PLANNING_BRANCH_CHECKPOINT_GUARDRAIL_NOTE,
    DEFAULT_ASSIGNMENT_PATH,
    DEFAULT_BOSS_HALF_LIFE_PATH,
    DEFAULT_FRACTURE_TREE_PATH,
    DEFAULT_MANUAL_FRACTURE_PATH,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_PREFLIGHT_PATH,
    DEFAULT_REGISTRY_PATH,
    DEFAULT_REVIEW_PACK_PATH,
    STATUS_BLOCKED,
    STATUS_INCOMPLETE,
    write_commander_planning_branch_checkpoint,
)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") or {}
    phase = report.get("phase_completion") or {}
    artifacts = report.get("artifact_coverage") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "checkpoint_id": report.get("checkpoint_id"),
        "checkpoint_status": report.get("checkpoint_status"),
        "all_required_phases_complete": phase.get("all_required_phases_complete"),
        "all_required_artifacts_present": artifacts.get("all_required_artifacts_present"),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": report.get("warnings") or [],
        "incomplete_reasons": report.get("incomplete_reasons") or [],
        "blocked_reasons": report.get("blocked_reasons") or [],
    }


def run_create_commander_planning_branch_checkpoint(
    *,
    registry: str = str(DEFAULT_REGISTRY_PATH),
    boss_half_life: str = str(DEFAULT_BOSS_HALF_LIFE_PATH),
    manual_fracture: str = str(DEFAULT_MANUAL_FRACTURE_PATH),
    fracture_tree: str = str(DEFAULT_FRACTURE_TREE_PATH),
    preflight: str = str(DEFAULT_PREFLIGHT_PATH),
    assignment: str = str(DEFAULT_ASSIGNMENT_PATH),
    review_pack: str = str(DEFAULT_REVIEW_PACK_PATH),
    output_dir: str = str(DEFAULT_OUTPUT_ROOT),
) -> dict[str, Any]:
    """Create CMD.CLOSE checkpoint artifacts and return paths plus summary data."""
    result = write_commander_planning_branch_checkpoint(
        registry_path=registry,
        boss_half_life_path=boss_half_life,
        manual_fracture_path=manual_fracture,
        fracture_tree_path=fracture_tree,
        preflight_path=preflight,
        assignment_path=assignment,
        review_pack_path=review_pack,
        output_dir=output_dir,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("CMD.CLOSE - Commander Planning Branch Checkpoint")
    print("=" * 52)
    print(f"Checkpoint id      : {summary['checkpoint_id']}")
    print(f"Checkpoint status  : {summary['checkpoint_status']}")
    print(f"Phases complete    : {summary['all_required_phases_complete']}")
    print(f"Artifacts present  : {summary['all_required_artifacts_present']}")
    print(f"Recommended next   : {summary['recommended_next_phase']}")
    print(f"JSON               : {summary['json_path']}")
    print(f"Markdown           : {summary['md_path']}")
    for reason in summary["blocked_reasons"]:
        print(f"  BLOCKED: {reason}")
    for reason in summary["incomplete_reasons"]:
        print(f"  INCOMPLETE: {reason}")
    for warning in summary["warnings"]:
        print(f"  WARNING: {warning}")
    print(f"\n> {COMMANDER_PLANNING_BRANCH_CHECKPOINT_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "CMD.CLOSE: write a report-only checkpoint that freezes CMD.N1-CMD.N6 "
            "as Commander planning-only evidence before execution design."
        )
    )
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH), help="Path to phase_registry.json.")
    parser.add_argument("--boss-half-life", default=str(DEFAULT_BOSS_HALF_LIFE_PATH), help="Path to CMD.N1 JSON artifact.")
    parser.add_argument("--manual-fracture", default=str(DEFAULT_MANUAL_FRACTURE_PATH), help="Path to CMD.N2 JSON artifact.")
    parser.add_argument("--fracture-tree", default=str(DEFAULT_FRACTURE_TREE_PATH), help="Path to CMD.N3 JSON artifact.")
    parser.add_argument("--preflight", default=str(DEFAULT_PREFLIGHT_PATH), help="Path to CMD.N4 JSON artifact.")
    parser.add_argument("--assignment", default=str(DEFAULT_ASSIGNMENT_PATH), help="Path to CMD.N5 JSON artifact.")
    parser.add_argument("--review-pack", default=str(DEFAULT_REVIEW_PACK_PATH), help="Path to CMD.N6 JSON artifact.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Exit 0 for incomplete checkpoint reports. Blocked reports still exit nonzero.",
    )
    args = parser.parse_args(argv)

    result = run_create_commander_planning_branch_checkpoint(
        registry=args.registry,
        boss_half_life=args.boss_half_life,
        manual_fracture=args.manual_fracture,
        fracture_tree=args.fracture_tree,
        preflight=args.preflight,
        assignment=args.assignment,
        review_pack=args.review_pack,
        output_dir=args.output_dir,
    )

    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=True, sort_keys=True))
    else:
        _print_summary(result)

    status = result["summary"]["checkpoint_status"]
    if status == STATUS_BLOCKED:
        return 1
    if status == STATUS_INCOMPLETE and not args.allow_incomplete:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
