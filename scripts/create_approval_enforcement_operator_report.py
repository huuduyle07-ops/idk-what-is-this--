#!/usr/bin/env python
"""Create HARDEN.N4 - Approval Enforcement Operator Report.

Writes a report-only operator summary for HARDEN.N3 simulated approval-gate
outcomes. It does not enforce gates, approve or reject real actions, issue or
consume tokens, change routes/auth, call models, launch workers, invoke tools,
apply patches, contact networks, or write databases.
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

from core.approval_enforcement_operator_report import (  # noqa: E402
    DEFAULT_ATTACHMENT_PLAN_PATH,
    DEFAULT_HUMAN_CLOSE_CHECKPOINT_PATH,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_READINESS_AUDIT_PATH,
    DEFAULT_SIMULATOR_PATH,
    DEFAULT_TOKEN_CONTRACT_PATH,
    GUARDRAIL_NOTE,
    STATUS_READY,
    STATUS_READY_WITH_WARNINGS,
    write_approval_enforcement_operator_report,
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
        "scenario_count": int(report.get("scenario_count") or 0),
        "decision_summary": report.get("decision_summary") or {},
        "allow_count": len(report.get("allow_simulations") or []),
        "deny_count": len(report.get("deny_simulations") or []),
        "block_count": len(report.get("block_simulations") or []),
        "warning_count": len(report.get("warning_simulations") or []),
        "incomplete_count": len(report.get("incomplete_simulations") or []),
        "high_risk_count": len(report.get("high_risk_items") or []),
        "blocked_forever_count": len(report.get("blocked_forever_items") or []),
        "enforcement_was_applied": bool(report.get("enforcement_was_applied")),
        "token_was_issued": bool(report.get("token_was_issued")),
        "token_was_consumed": bool(report.get("token_was_consumed")),
        "runtime_behavior_changed": bool(report.get("runtime_behavior_changed")),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "incomplete_reason_count": len(report.get("incomplete_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_approval_enforcement_operator_report(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    source_simulator_path: str | Path = DEFAULT_SIMULATOR_PATH,
    source_attachment_plan_path: str | Path = DEFAULT_ATTACHMENT_PLAN_PATH,
    source_readiness_audit_path: str | Path = DEFAULT_READINESS_AUDIT_PATH,
    source_token_contract_path: str | Path = DEFAULT_TOKEN_CONTRACT_PATH,
    source_human_close_checkpoint_path: str | Path = DEFAULT_HUMAN_CLOSE_CHECKPOINT_PATH,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create HARDEN.N4 operator report artifacts and return paths plus summary."""
    result = write_approval_enforcement_operator_report(
        repo_root=repo_root,
        output_dir=output_dir,
        source_simulator_path=source_simulator_path,
        source_attachment_plan_path=source_attachment_plan_path,
        source_readiness_audit_path=source_readiness_audit_path,
        source_token_contract_path=source_token_contract_path,
        source_human_close_checkpoint_path=source_human_close_checkpoint_path,
        report_id=report_id,
        created_at=created_at,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("HARDEN.N4 - Approval Enforcement Operator Report")
    print("=" * 54)
    print(f"Report status      : {summary['report_status']}")
    print(f"Scenarios          : {summary['scenario_count']}")
    print(f"Allow simulations  : {summary['allow_count']}")
    print(f"Deny simulations   : {summary['deny_count']}")
    print(f"Block simulations  : {summary['block_count']}")
    print(f"Warning simulations: {summary['warning_count']}")
    print(f"High-risk items    : {summary['high_risk_count']}")
    print(f"Blocked forever    : {summary['blocked_forever_count']}")
    print(f"Enforcement applied: {summary['enforcement_was_applied']}")
    print(f"Token issued       : {summary['token_was_issued']}")
    print(f"Token consumed     : {summary['token_was_consumed']}")
    print(f"Runtime changed    : {summary['runtime_behavior_changed']}")
    print(f"Recommended next   : {summary['recommended_next_phase']}")
    print(f"JSON               : {summary['json_path']}")
    print(f"Markdown           : {summary['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "HARDEN.N4: write a report-only operator summary for simulated "
            "approval-gate outcomes without runtime enforcement."
        )
    )
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument("--simulator-path", default=str(DEFAULT_SIMULATOR_PATH), help="HARDEN.N3 simulator artifact.")
    parser.add_argument("--attachment-plan-path", default=str(DEFAULT_ATTACHMENT_PLAN_PATH), help="HARDEN.N2 artifact.")
    parser.add_argument("--readiness-audit-path", default=str(DEFAULT_READINESS_AUDIT_PATH), help="HARDEN.N1 artifact.")
    parser.add_argument("--token-contract-path", default=str(DEFAULT_TOKEN_CONTRACT_PATH), help="HUMAN.N2 artifact.")
    parser.add_argument(
        "--human-close-checkpoint-path",
        default=str(DEFAULT_HUMAN_CLOSE_CHECKPOINT_PATH),
        help="Optional HUMAN.CLOSE checkpoint artifact.",
    )
    parser.add_argument("--report-id", default="", help="Optional deterministic report id.")
    parser.add_argument("--created-at", default="", help="Optional created-at timestamp.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_approval_enforcement_operator_report(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        source_simulator_path=args.simulator_path,
        source_attachment_plan_path=args.attachment_plan_path,
        source_readiness_audit_path=args.readiness_audit_path,
        source_token_contract_path=args.token_contract_path,
        source_human_close_checkpoint_path=args.human_close_checkpoint_path,
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
