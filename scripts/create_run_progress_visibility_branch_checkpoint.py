#!/usr/bin/env python
"""Write report-only UX.RUN.CLOSE Run Progress Visibility checkpoint artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.run_progress_visibility_branch_checkpoint import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_REGISTRY_PATH,
    DEFAULT_SNAPSHOT_LOADER_REPORT_PATH,
    DEFAULT_UI_PANEL_MARKER_PATH,
    DEFAULT_VISIBILITY_CONTRACT_PATH,
    GUARDRAIL_NOTE,
    STATUS_FROZEN,
    STATUS_FROZEN_WITH_WARNINGS,
    write_run_progress_visibility_branch_checkpoint,
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
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "incomplete_reason_count": len(report.get("incomplete_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_run_progress_visibility_branch_checkpoint(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    registry: str | Path = DEFAULT_REGISTRY_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    source_visibility_contract_path: str | Path = DEFAULT_VISIBILITY_CONTRACT_PATH,
    source_snapshot_loader_report_path: str | Path = DEFAULT_SNAPSHOT_LOADER_REPORT_PATH,
    source_ui_panel_marker_path: str | Path = DEFAULT_UI_PANEL_MARKER_PATH,
    checkpoint_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create UX.RUN.CLOSE artifacts without running or changing the application."""
    result = write_run_progress_visibility_branch_checkpoint(
        repo_root=repo_root,
        registry_path=registry,
        output_dir=output_dir,
        source_visibility_contract_path=source_visibility_contract_path,
        source_snapshot_loader_report_path=source_snapshot_loader_report_path,
        source_ui_panel_marker_path=source_ui_panel_marker_path,
        checkpoint_id=checkpoint_id,
        created_at=created_at,
    )
    result["summary"] = _summary(result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UX.RUN.CLOSE: create a report-only run-progress visibility branch checkpoint.")
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH), help="Phase registry JSON path.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument("--source-visibility-contract-path", default=str(DEFAULT_VISIBILITY_CONTRACT_PATH), help="UX.RUN.1 report JSON.")
    parser.add_argument("--source-snapshot-loader-report-path", default=str(DEFAULT_SNAPSHOT_LOADER_REPORT_PATH), help="UX.RUN.2 report JSON.")
    parser.add_argument("--source-ui-panel-marker-path", default=str(DEFAULT_UI_PANEL_MARKER_PATH), help="UX.RUN.3 template path.")
    parser.add_argument("--checkpoint-id", default="", help="Optional deterministic checkpoint id.")
    parser.add_argument("--created-at", default="", help="Optional deterministic creation timestamp.")
    parser.add_argument("--json", action="store_true", help="Print a compact JSON summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_run_progress_visibility_branch_checkpoint(
        repo_root=args.repo_root,
        registry=args.registry,
        output_dir=args.output_dir,
        source_visibility_contract_path=args.source_visibility_contract_path,
        source_snapshot_loader_report_path=args.source_snapshot_loader_report_path,
        source_ui_panel_marker_path=args.source_ui_panel_marker_path,
        checkpoint_id=args.checkpoint_id,
        created_at=args.created_at,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        summary = result["summary"]
        print("UX.RUN.CLOSE - Run Progress Visibility Branch Checkpoint")
        print(f"Status: {summary['checkpoint_status']}")
        print(f"Recommended next phase: {summary['recommended_next_phase']}")
        print(f"JSON: {summary['json_path']}")
        print(f"Markdown: {summary['md_path']}")
        print(f"\n> {GUARDRAIL_NOTE}")
    return 0 if result["summary"]["checkpoint_status"] in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
