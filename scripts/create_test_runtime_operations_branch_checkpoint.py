#!/usr/bin/env python
"""Create OPS.TEST.CLOSE - Test Runtime Operations Branch Checkpoint artifacts.

Writes report-only JSON and Markdown checkpoint artifacts for the completed
OPS.TEST.1-OPS.TEST.3 planning branch. It reads existing JSON artifacts and the
phase registry, but never runs pytest, creates executable manifests, launches a
runner, changes tests, calls models, contacts networks, mutates benchmarks, or
changes production behavior.
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

from core.test_runtime_operations_branch_checkpoint import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_REGISTRY_PATH,
    DEFAULT_RUNTIME_PROFILE_AUDIT_PATH,
    DEFAULT_SLOW_TIMING_REPORT_PATH,
    DEFAULT_SUITE_SPLIT_MANIFEST_PLAN_PATH,
    GUARDRAIL_NOTE,
    STATUS_FROZEN,
    STATUS_FROZEN_WITH_WARNINGS,
    write_test_runtime_operations_branch_checkpoint,
)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "checkpoint_status": report.get("checkpoint_status"),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "incomplete_reason_count": len(report.get("incomplete_reasons") or []),
        "warning_count": len(report.get("warnings") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_test_runtime_operations_branch_checkpoint(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    registry: str | Path = DEFAULT_REGISTRY_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    source_runtime_profile_audit_path: str | Path = DEFAULT_RUNTIME_PROFILE_AUDIT_PATH,
    source_slow_timing_report_path: str | Path = DEFAULT_SLOW_TIMING_REPORT_PATH,
    source_suite_split_manifest_plan_path: str | Path = DEFAULT_SUITE_SPLIT_MANIFEST_PLAN_PATH,
    checkpoint_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create OPS.TEST.CLOSE checkpoint artifacts and return paths plus summary."""
    result = write_test_runtime_operations_branch_checkpoint(
        repo_root=repo_root,
        registry_path=registry,
        output_dir=output_dir,
        source_runtime_profile_audit_path=source_runtime_profile_audit_path,
        source_slow_timing_report_path=source_slow_timing_report_path,
        source_suite_split_manifest_plan_path=source_suite_split_manifest_plan_path,
        checkpoint_id=checkpoint_id,
        created_at=created_at,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("OPS.TEST.CLOSE - Test Runtime Operations Branch Checkpoint")
    print("=" * 61)
    print(f"Checkpoint status : {summary['checkpoint_status']}")
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
            "OPS.TEST.CLOSE: write report-only checkpoint artifacts for the "
            "completed OPS.TEST.1-OPS.TEST.3 planning branch."
        )
    )
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH), help="Path to phase registry JSON.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument(
        "--source-runtime-profile-audit-path",
        default=str(DEFAULT_RUNTIME_PROFILE_AUDIT_PATH),
        help="OPS.TEST.1 runtime profile audit JSON artifact.",
    )
    parser.add_argument(
        "--source-slow-timing-report-path",
        default=str(DEFAULT_SLOW_TIMING_REPORT_PATH),
        help="OPS.TEST.2 slow timing report JSON artifact.",
    )
    parser.add_argument(
        "--source-suite-split-manifest-plan-path",
        default=str(DEFAULT_SUITE_SPLIT_MANIFEST_PLAN_PATH),
        help="OPS.TEST.3 suite split manifest plan JSON artifact.",
    )
    parser.add_argument("--checkpoint-id", default="", help="Optional deterministic checkpoint id.")
    parser.add_argument("--created-at", default="", help="Optional created-at timestamp.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_test_runtime_operations_branch_checkpoint(
        repo_root=args.repo_root,
        registry=args.registry,
        output_dir=args.output_dir,
        source_runtime_profile_audit_path=args.source_runtime_profile_audit_path,
        source_slow_timing_report_path=args.source_slow_timing_report_path,
        source_suite_split_manifest_plan_path=args.source_suite_split_manifest_plan_path,
        checkpoint_id=args.checkpoint_id,
        created_at=args.created_at,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    status = result["summary"]["checkpoint_status"]
    return 0 if status in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
