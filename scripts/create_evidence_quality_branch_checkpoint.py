#!/usr/bin/env python
"""Create EVAL.CLOSE - Evidence Quality Branch Checkpoint.

Writes checkpoint JSON/Markdown artifacts only. It does not generate evidence
quality reports, run validation or benchmarks, call models, apply patches,
approve/reject work, mutate evidence reports, or block Apply/Submit.
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

from core.evidence_quality_branch_checkpoint import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_REGISTRY_PATH,
    GUARDRAIL_NOTE,
    STATUS_FROZEN,
    STATUS_FROZEN_WITH_WARNINGS,
    write_evidence_quality_branch_checkpoint,
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
        "checkpoint_status": report.get("checkpoint_status"),
        "all_required_eval_phases_complete": bool(summary.get("all_required_eval_phases_complete")),
        "required_artifacts_present": bool(summary.get("required_artifacts_present")),
        "ui_stub_present": bool(summary.get("ui_stub_present")),
        "get_loader_present": bool(summary.get("get_loader_present")),
        "warning_count": int(summary.get("warning_count") or 0),
        "blocked_reason_count": int(summary.get("blocked_reason_count") or 0),
        "incomplete_reason_count": int(summary.get("incomplete_reason_count") or 0),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_evidence_quality_branch_checkpoint(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create EVAL.CLOSE checkpoint artifacts and return paths plus summary."""
    result = write_evidence_quality_branch_checkpoint(
        repo_root=repo_root,
        registry_path=registry_path,
        output_dir=output_dir,
        report_id=report_id,
        created_at=created_at,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("EVAL.CLOSE - Evidence Quality Branch Checkpoint")
    print("=" * 55)
    print(f"Checkpoint status : {summary['checkpoint_status']}")
    print(f"Phases complete   : {summary['all_required_eval_phases_complete']}")
    print(f"Artifacts present : {summary['required_artifacts_present']}")
    print(f"UI stub present   : {summary['ui_stub_present']}")
    print(f"GET loader present: {summary['get_loader_present']}")
    print(f"Warnings          : {summary['warning_count']}")
    print(f"Blocked reasons   : {summary['blocked_reason_count']}")
    print(f"Incomplete items  : {summary['incomplete_reason_count']}")
    print(f"Recommended next  : {summary['recommended_next_phase']}")
    print(f"JSON              : {summary['json_path']}")
    print(f"Markdown          : {summary['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "EVAL.CLOSE: write a report-only checkpoint freezing the Evidence "
            "Quality branch after EVAL.N7. This performs local source/artifact "
            "inspection only."
        )
    )
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root.")
    parser.add_argument("--registry-path", default=DEFAULT_REGISTRY_PATH, help="Phase registry path.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument("--report-id", default="", help="Optional deterministic report id.")
    parser.add_argument("--created-at", default="", help="Optional created-at timestamp.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_evidence_quality_branch_checkpoint(
        repo_root=args.repo_root,
        registry_path=args.registry_path,
        output_dir=args.output_dir,
        report_id=args.report_id,
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
