#!/usr/bin/env python
"""Create HARDEN.CLOSE - Approval Enforcement Planning Branch Checkpoint.

Writes report-only checkpoint JSON/Markdown artifacts. It does not enforce
approval gates, validate live tokens, issue or consume tokens, approve/reject
real actions, change route/auth behavior, call models, launch workers, invoke
tools, apply patches, contact networks, write databases, run validation, or run
benchmarks.
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

from core.approval_enforcement_planning_branch_checkpoint import (  # noqa: E402
    DEFAULT_ATTACHMENT_PLAN_PATH,
    DEFAULT_DRY_RUN_SIMULATOR_PATH,
    DEFAULT_HUMAN_AUTHORITY_CHECKPOINT_PATH,
    DEFAULT_OPERATOR_REPORT_PATH,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_READINESS_AUDIT_PATH,
    DEFAULT_REGISTRY_PATH,
    DEFAULT_TOKEN_CONTRACT_PATH,
    GUARDRAIL_NOTE,
    STATUS_FROZEN,
    STATUS_FROZEN_WITH_WARNINGS,
    write_approval_enforcement_planning_branch_checkpoint,
)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    phase_summary = (
        report.get("phase_completion_summary") if isinstance(report.get("phase_completion_summary"), dict) else {}
    )
    coverage = report.get("artifact_coverage") if isinstance(report.get("artifact_coverage"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "checkpoint_status": report.get("checkpoint_status"),
        "all_required_harden_phases_complete": bool(phase_summary.get("all_required_harden_phases_complete")),
        "required_artifacts_present": bool(coverage.get("required_artifacts_present")),
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "incomplete_reason_count": len(report.get("incomplete_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_approval_enforcement_planning_branch_checkpoint(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    source_readiness_audit_path: str | Path = DEFAULT_READINESS_AUDIT_PATH,
    source_attachment_plan_path: str | Path = DEFAULT_ATTACHMENT_PLAN_PATH,
    source_dry_run_simulator_path: str | Path = DEFAULT_DRY_RUN_SIMULATOR_PATH,
    source_operator_report_path: str | Path = DEFAULT_OPERATOR_REPORT_PATH,
    source_human_authority_checkpoint_path: str | Path = DEFAULT_HUMAN_AUTHORITY_CHECKPOINT_PATH,
    source_token_contract_path: str | Path = DEFAULT_TOKEN_CONTRACT_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    checkpoint_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create HARDEN.CLOSE checkpoint artifacts and return paths plus summary."""
    result = write_approval_enforcement_planning_branch_checkpoint(
        repo_root=repo_root,
        registry_path=registry_path,
        source_readiness_audit_path=source_readiness_audit_path,
        source_attachment_plan_path=source_attachment_plan_path,
        source_dry_run_simulator_path=source_dry_run_simulator_path,
        source_operator_report_path=source_operator_report_path,
        source_human_authority_checkpoint_path=source_human_authority_checkpoint_path,
        source_token_contract_path=source_token_contract_path,
        output_dir=output_dir,
        checkpoint_id=checkpoint_id,
        created_at=created_at,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("HARDEN.CLOSE - Approval Enforcement Planning Branch Checkpoint")
    print("=" * 66)
    print(f"Checkpoint status : {summary['checkpoint_status']}")
    print(f"Phases complete   : {summary['all_required_harden_phases_complete']}")
    print(f"Artifacts present : {summary['required_artifacts_present']}")
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
            "HARDEN.CLOSE: write a report-only checkpoint freezing HARDEN.N1-N4 "
            "as a non-enforcing approval-enforcement planning branch."
        )
    )
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root.")
    parser.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH), help="Phase registry path.")
    parser.add_argument("--readiness-audit-path", default=str(DEFAULT_READINESS_AUDIT_PATH), help="HARDEN.N1 artifact.")
    parser.add_argument("--attachment-plan-path", default=str(DEFAULT_ATTACHMENT_PLAN_PATH), help="HARDEN.N2 artifact.")
    parser.add_argument("--dry-run-simulator-path", default=str(DEFAULT_DRY_RUN_SIMULATOR_PATH), help="HARDEN.N3 artifact.")
    parser.add_argument("--operator-report-path", default=str(DEFAULT_OPERATOR_REPORT_PATH), help="HARDEN.N4 artifact.")
    parser.add_argument(
        "--human-authority-checkpoint-path",
        default=str(DEFAULT_HUMAN_AUTHORITY_CHECKPOINT_PATH),
        help="Optional HUMAN.CLOSE checkpoint artifact.",
    )
    parser.add_argument("--token-contract-path", default=str(DEFAULT_TOKEN_CONTRACT_PATH), help="Optional HUMAN.N2 artifact.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument("--checkpoint-id", default="", help="Optional deterministic checkpoint id.")
    parser.add_argument("--created-at", default="", help="Optional created-at timestamp.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_approval_enforcement_planning_branch_checkpoint(
        repo_root=args.repo_root,
        registry_path=args.registry_path,
        source_readiness_audit_path=args.readiness_audit_path,
        source_attachment_plan_path=args.attachment_plan_path,
        source_dry_run_simulator_path=args.dry_run_simulator_path,
        source_operator_report_path=args.operator_report_path,
        source_human_authority_checkpoint_path=args.human_authority_checkpoint_path,
        source_token_contract_path=args.token_contract_path,
        output_dir=args.output_dir,
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
