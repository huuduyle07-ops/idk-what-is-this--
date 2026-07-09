#!/usr/bin/env python
"""Create OPS.TEST.3 - Test Suite Split Manifest Plan artifacts.

Writes report-only JSON/Markdown artifacts for named suite manifest planning.
The command records command templates only; it never launches validation.
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

from core.test_suite_split_manifest_plan import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_RUNTIME_PROFILE_AUDIT_PATH,
    DEFAULT_SLOW_TIMING_REPORT_PATH,
    GUARDRAIL_NOTE,
    STATUS_READY,
    STATUS_READY_WITH_WARNINGS,
    write_test_suite_split_manifest_plan,
)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "plan_status": report.get("plan_status"),
        "profile_count": len(report.get("manifest_profiles") or []),
        "template_count": len(report.get("profile_command_templates") or []),
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "incomplete_reason_count": len(report.get("incomplete_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_test_suite_split_manifest_plan(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    source_runtime_profile_audit_path: str | Path = DEFAULT_RUNTIME_PROFILE_AUDIT_PATH,
    source_slow_timing_report_path: str | Path = DEFAULT_SLOW_TIMING_REPORT_PATH,
    plan_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create OPS.TEST.3 manifest plan artifacts and return paths plus summary."""
    result = write_test_suite_split_manifest_plan(
        repo_root=repo_root,
        output_dir=output_dir,
        plan_id=plan_id,
        created_at=created_at,
        source_runtime_profile_audit_path=source_runtime_profile_audit_path,
        source_slow_timing_report_path=source_slow_timing_report_path,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("OPS.TEST.3 - Test Suite Split Manifest Plan")
    print("=" * 47)
    print(f"Plan status       : {summary['plan_status']}")
    print(f"Profiles          : {summary['profile_count']}")
    print(f"Templates         : {summary['template_count']}")
    print(f"Warnings          : {summary['warning_count']}")
    print(f"Blocked reasons   : {summary['blocked_reason_count']}")
    print(f"Incomplete reasons: {summary['incomplete_reason_count']}")
    print(f"Recommended next  : {summary['recommended_next_phase']}")
    print(f"JSON              : {summary['json_path']}")
    print(f"Markdown          : {summary['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="OPS.TEST.3: create report-only test suite split manifest plan artifacts."
    )
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument(
        "--source-runtime-profile-audit-path",
        default=str(DEFAULT_RUNTIME_PROFILE_AUDIT_PATH),
        help="OPS.TEST.1 artifact path.",
    )
    parser.add_argument(
        "--source-slow-timing-report-path",
        default=str(DEFAULT_SLOW_TIMING_REPORT_PATH),
        help="OPS.TEST.2 artifact path.",
    )
    parser.add_argument("--plan-id", default="", help="Optional deterministic plan id.")
    parser.add_argument("--created-at", default="", help="Optional created-at timestamp.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_test_suite_split_manifest_plan(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        source_runtime_profile_audit_path=args.source_runtime_profile_audit_path,
        source_slow_timing_report_path=args.source_slow_timing_report_path,
        plan_id=args.plan_id,
        created_at=args.created_at,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    status = result["summary"]["plan_status"]
    return 0 if status in {STATUS_READY, STATUS_READY_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
