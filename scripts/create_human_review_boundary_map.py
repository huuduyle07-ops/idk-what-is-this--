#!/usr/bin/env python
"""Create HUMAN.N1 - Human Review Boundary Map.

Writes boundary-map JSON/Markdown artifacts only. It does not enforce approval,
call models, route models, launch workers, run validation or benchmarks, invoke
MCP/tools, use network access, execute Docker/subprocess work, write databases,
change auth/routes, apply patches, or approve/reject work.
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

from core.human_review_boundary_map import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    GUARDRAIL_NOTE,
    STATUS_READY,
    STATUS_READY_WITH_WARNINGS,
    write_human_review_boundary_map,
)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "boundary_status": report.get("boundary_status"),
        "critical_action_category_count": int(summary.get("critical_action_category_count") or 0),
        "mapped_action_category_count": int(summary.get("mapped_action_category_count") or 0),
        "missing_critical_action_categories": list(summary.get("missing_critical_action_categories") or []),
        "explicit_approval_action_count": int(summary.get("explicit_approval_action_count") or 0),
        "forbidden_automatic_action_count": int(summary.get("forbidden_automatic_action_count") or 0),
        "branch_boundary_count": int(summary.get("branch_boundary_count") or 0),
        "warning_count": int(summary.get("warning_count") or 0),
        "blocked_reason_count": int(summary.get("blocked_reason_count") or 0),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_human_review_boundary_map(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create HUMAN.N1 boundary artifacts and return paths plus summary."""
    result = write_human_review_boundary_map(
        output_dir=output_dir,
        report_id=report_id,
        created_at=created_at,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("HUMAN.N1 - Human Review Boundary Map")
    print("=" * 43)
    print(f"Boundary status  : {summary['boundary_status']}")
    print(f"Actions covered  : {summary['mapped_action_category_count']}")
    print(f"Missing actions  : {len(summary['missing_critical_action_categories'])}")
    print(f"Explicit approval: {summary['explicit_approval_action_count']}")
    print(f"Forbidden auto   : {summary['forbidden_automatic_action_count']}")
    print(f"Branch boundaries: {summary['branch_boundary_count']}")
    print(f"Warnings         : {summary['warning_count']}")
    print(f"Blocked reasons  : {summary['blocked_reason_count']}")
    print(f"Recommended next : {summary['recommended_next_phase']}")
    print(f"JSON             : {summary['json_path']}")
    print(f"Markdown         : {summary['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "HUMAN.N1: write a report-only boundary map defining where AI advice "
            "stops and explicit human decision-making begins."
        )
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument("--report-id", default="", help="Optional deterministic report id.")
    parser.add_argument("--created-at", default="", help="Optional created-at timestamp.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_human_review_boundary_map(
        output_dir=args.output_dir,
        report_id=args.report_id,
        created_at=args.created_at,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    status = result["summary"]["boundary_status"]
    return 0 if status in {STATUS_READY, STATUS_READY_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
