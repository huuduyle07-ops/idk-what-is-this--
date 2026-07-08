#!/usr/bin/env python
"""Create OPS.TEST.1 - Test Suite Runtime Profile Audit artifacts.

Writes report-only JSON and Markdown policy artifacts for test runtime profiles.
It does not run pytest, validation, benchmarks, model calls, network access,
workers, patch application, database writes, or production behavior changes.
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

from core.test_suite_runtime_profile_audit import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    GUARDRAIL_NOTE,
    STATUS_READY,
    STATUS_READY_WITH_WARNINGS,
    write_test_suite_runtime_profile_audit,
)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "audit_status": report.get("audit_status"),
        "quick_timeout_seconds": int(report.get("quick_timeout_seconds") or 0),
        "full_timeout_seconds": int(report.get("full_timeout_seconds") or 0),
        "suite_profile_count": len(report.get("suite_profiles") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "incomplete_reason_count": len(report.get("incomplete_reasons") or []),
        "warning_count": len(report.get("warnings") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_test_suite_runtime_profile_audit(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    audit_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create OPS.TEST.1 audit artifacts and return paths plus summary."""
    result = write_test_suite_runtime_profile_audit(
        repo_root=repo_root,
        output_dir=output_dir,
        audit_id=audit_id,
        created_at=created_at,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("OPS.TEST.1 - Test Suite Runtime Profile Audit")
    print("=" * 49)
    print(f"Audit status      : {summary['audit_status']}")
    print(f"Suite profiles    : {summary['suite_profile_count']}")
    print(f"Quick timeout     : {summary['quick_timeout_seconds']} seconds")
    print(f"Full timeout      : {summary['full_timeout_seconds']} seconds")
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
            "OPS.TEST.1: write report-only test-suite runtime profile artifacts "
            "without running validation or changing test coverage."
        )
    )
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument("--audit-id", default="", help="Optional deterministic audit id.")
    parser.add_argument("--created-at", default="", help="Optional created-at timestamp.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_test_suite_runtime_profile_audit(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        audit_id=args.audit_id,
        created_at=args.created_at,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    status = result["summary"]["audit_status"]
    return 0 if status in {STATUS_READY, STATUS_READY_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
