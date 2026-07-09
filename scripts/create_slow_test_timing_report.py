#!/usr/bin/env python
"""Create OPS.TEST.2 - Slow Test Timing Report artifacts.

Reads an optional timing log and writes report-only JSON/Markdown timing
artifacts. The command never launches pytest or any other validation command.
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

from core.slow_test_timing_collector import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_PROFILE_AUDIT_PATH,
    GUARDRAIL_NOTE,
    STATUS_READY,
    STATUS_READY_WITH_WARNINGS,
    write_slow_test_timing_report,
)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "report_status": report.get("report_status"),
        "timing_source_type": report.get("timing_source_type"),
        "total_observed_runtime_seconds": float(report.get("total_observed_runtime_seconds") or 0),
        "collected_test_count": int(report.get("collected_test_count") or 0),
        "collected_file_count": int(report.get("collected_file_count") or 0),
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "incomplete_reason_count": len(report.get("incomplete_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def _read_timing_log(path: str | Path | None) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def run_create_slow_test_timing_report(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    timing_log: str | Path | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    source_profile_audit_path: str | Path = DEFAULT_PROFILE_AUDIT_PATH,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create OPS.TEST.2 timing report artifacts and return paths plus summary."""
    timing_text = _read_timing_log(timing_log)
    result = write_slow_test_timing_report(
        repo_root=repo_root,
        output_dir=output_dir,
        report_id=report_id,
        created_at=created_at,
        timing_text=timing_text or None,
        source_profile_audit_path=source_profile_audit_path,
        source_timing_log_path=timing_log or "",
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("OPS.TEST.2 - Slow Test Timing Report")
    print("=" * 39)
    print(f"Report status     : {summary['report_status']}")
    print(f"Timing source     : {summary['timing_source_type']}")
    print(f"Observed seconds  : {summary['total_observed_runtime_seconds']}")
    print(f"Collected tests   : {summary['collected_test_count']}")
    print(f"Collected files   : {summary['collected_file_count']}")
    print(f"Warnings          : {summary['warning_count']}")
    print(f"Blocked reasons   : {summary['blocked_reason_count']}")
    print(f"Incomplete reasons: {summary['incomplete_reason_count']}")
    print(f"Recommended next  : {summary['recommended_next_phase']}")
    print(f"JSON              : {summary['json_path']}")
    print(f"Markdown          : {summary['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "OPS.TEST.2: create report-only slow-test timing artifacts from an "
            "optional provided timing log."
        )
    )
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root.")
    parser.add_argument("--timing-log", default="", help="Optional pytest duration/progress text log.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument("--source-profile-audit-path", default=str(DEFAULT_PROFILE_AUDIT_PATH), help="OPS.TEST.1 artifact path.")
    parser.add_argument("--report-id", default="", help="Optional deterministic report id.")
    parser.add_argument("--created-at", default="", help="Optional created-at timestamp.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_slow_test_timing_report(
        repo_root=args.repo_root,
        timing_log=args.timing_log,
        output_dir=args.output_dir,
        source_profile_audit_path=args.source_profile_audit_path,
        report_id=args.report_id,
        created_at=args.created_at,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    status = result["summary"]["report_status"]
    return 0 if status in {STATUS_READY, STATUS_READY_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
