#!/usr/bin/env python
"""Write report-only UX.LIVE.2 run-progress snapshot-writer planning artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.run_progress_snapshot_writer_plan import (  # noqa: E402
    DEFAULT_BRANCH_CHECKPOINT_PATH,
    DEFAULT_INSTRUMENTATION_PLAN_PATH,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_REGISTRY_PATH,
    DEFAULT_SNAPSHOT_LOADER_REPORT_PATH,
    DEFAULT_VISIBILITY_REPORT_PATH,
    GUARDRAIL_NOTE,
    READY,
    READY_WITH_WARNINGS,
    write_run_progress_snapshot_writer_plan,
)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "status": report.get("status"),
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "incomplete_reason_count": len(report.get("incomplete_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_run_progress_snapshot_writer_plan(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    registry: str | Path = DEFAULT_REGISTRY_PATH,
    instrumentation_plan_path: str | Path = DEFAULT_INSTRUMENTATION_PLAN_PATH,
    visibility_report_path: str | Path = DEFAULT_VISIBILITY_REPORT_PATH,
    snapshot_loader_report_path: str | Path = DEFAULT_SNAPSHOT_LOADER_REPORT_PATH,
    branch_checkpoint_path: str | Path = DEFAULT_BRANCH_CHECKPOINT_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    plan_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create planning artifacts only; this function does not write run snapshots."""
    result = write_run_progress_snapshot_writer_plan(
        repo_root=repo_root,
        registry_path=registry,
        instrumentation_plan_path=instrumentation_plan_path,
        visibility_report_path=visibility_report_path,
        snapshot_loader_report_path=snapshot_loader_report_path,
        branch_checkpoint_path=branch_checkpoint_path,
        output_dir=output_dir,
        plan_id=plan_id,
        created_at=created_at,
    )
    result["summary"] = _summary(result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UX.LIVE.2: create a report-only run-progress snapshot-writer plan.")
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH), help="Phase registry JSON path.")
    parser.add_argument("--instrumentation-plan-path", default=str(DEFAULT_INSTRUMENTATION_PLAN_PATH), help="UX.LIVE.1 instrumentation-plan JSON path.")
    parser.add_argument("--visibility-report-path", default=str(DEFAULT_VISIBILITY_REPORT_PATH), help="UX.RUN.1 visibility report JSON path.")
    parser.add_argument("--snapshot-loader-report-path", default=str(DEFAULT_SNAPSHOT_LOADER_REPORT_PATH), help="UX.RUN.2 loader report JSON path.")
    parser.add_argument("--branch-checkpoint-path", default=str(DEFAULT_BRANCH_CHECKPOINT_PATH), help="UX.RUN.CLOSE checkpoint JSON path.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Plan artifact output directory.")
    parser.add_argument("--plan-id", default="", help="Optional deterministic plan id.")
    parser.add_argument("--created-at", default="", help="Optional deterministic creation timestamp.")
    parser.add_argument("--json", action="store_true", help="Print a compact JSON summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_run_progress_snapshot_writer_plan(
        repo_root=args.repo_root,
        registry=args.registry,
        instrumentation_plan_path=args.instrumentation_plan_path,
        visibility_report_path=args.visibility_report_path,
        snapshot_loader_report_path=args.snapshot_loader_report_path,
        branch_checkpoint_path=args.branch_checkpoint_path,
        output_dir=args.output_dir,
        plan_id=args.plan_id,
        created_at=args.created_at,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        summary = result["summary"]
        print("UX.LIVE.2 - Run Progress Snapshot Writer Plan")
        print(f"Status: {summary['status']}")
        print(f"Recommended next phase: {summary['recommended_next_phase']}")
        print(f"JSON: {summary['json_path']}")
        print(f"Markdown: {summary['md_path']}")
        print(f"\n> {GUARDRAIL_NOTE}")
    return 0 if result["summary"]["status"] in {READY, READY_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
