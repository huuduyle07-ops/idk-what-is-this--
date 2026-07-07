#!/usr/bin/env python
"""Create HUMAN.N4 - Human Approval Token Sample Catalog.

Writes documentation-only sample approval token catalog artifacts. It does not
issue approvals, approve/reject work, consume tokens, enforce routes, apply
patches, run validation or benchmarks, invoke MCP/tools, use network access,
execute Docker/subprocess work, write databases, change auth/routes, or launch
workers.
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

from core.human_approval_token_sample_catalog import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    GUARDRAIL_NOTE,
    STATUS_READY,
    STATUS_READY_WITH_WARNINGS,
    write_human_approval_token_sample_catalog,
)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "sample_paths": dict(result.get("sample_paths") or {}),
        "report_kind": report.get("report_kind"),
        "catalog_status": report.get("catalog_status"),
        "sample_count": int(summary.get("sample_count") or 0),
        "validation_expectation_count": int(summary.get("validation_expectation_count") or 0),
        "documentation_note_count": int(summary.get("documentation_note_count") or 0),
        "forbidden_usage_count": int(summary.get("forbidden_usage_count") or 0),
        "warning_count": int(summary.get("warning_count") or 0),
        "blocked_reason_count": int(summary.get("blocked_reason_count") or 0),
        "authorizes_action": False,
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_human_approval_token_sample_catalog(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    catalog_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create HUMAN.N4 sample catalog artifacts and return paths plus summary."""
    result = write_human_approval_token_sample_catalog(
        output_dir=output_dir,
        catalog_id=catalog_id,
        created_at=created_at,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("HUMAN.N4 - Human Approval Token Sample Catalog")
    print("=" * 51)
    print(f"Catalog status  : {summary['catalog_status']}")
    print(f"Samples         : {summary['sample_count']}")
    print(f"Expectations    : {summary['validation_expectation_count']}")
    print(f"Doc notes       : {summary['documentation_note_count']}")
    print(f"Forbidden usage : {summary['forbidden_usage_count']}")
    print(f"Warnings        : {summary['warning_count']}")
    print(f"Blocked reasons : {summary['blocked_reason_count']}")
    print(f"Authorizes      : {str(summary['authorizes_action']).lower()}")
    print(f"Recommended next: {summary['recommended_next_phase']}")
    print(f"JSON            : {summary['json_path']}")
    print(f"Markdown        : {summary['md_path']}")
    print(f"Sample files    : {len(summary['sample_paths'])}")
    print(f"\n> {GUARDRAIL_NOTE}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "HUMAN.N4: write documentation-only approval-token sample catalog "
            "artifacts for HUMAN.N2/HUMAN.N3 documentation and tests."
        )
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument("--catalog-id", default="", help="Optional deterministic catalog id.")
    parser.add_argument("--created-at", default="", help="Optional created-at timestamp.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_human_approval_token_sample_catalog(
        output_dir=args.output_dir,
        catalog_id=args.catalog_id,
        created_at=args.created_at,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    status = result["summary"]["catalog_status"]
    return 0 if status in {STATUS_READY, STATUS_READY_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
