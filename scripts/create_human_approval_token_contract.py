#!/usr/bin/env python
"""Create HUMAN.N2 - Human Approval Token / Confirmation Contract.

Writes approval-token contract JSON/Markdown artifacts only. It does not enforce
approval gates, validate live confirmations, issue tokens, approve/reject work,
apply patches, run validation or benchmarks, invoke MCP/tools, use network
access, execute Docker/subprocess work, write databases, change auth/routes, or
launch workers.
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

from core.human_approval_token_contract import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    GUARDRAIL_NOTE,
    STATUS_READY,
    STATUS_READY_WITH_WARNINGS,
    write_human_approval_token_contract,
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
        "contract_status": report.get("contract_status"),
        "schema_field_count": int(summary.get("schema_field_count") or 0),
        "required_field_count": int(summary.get("required_field_count") or 0),
        "missing_required_fields": list(summary.get("missing_required_fields") or []),
        "allowed_approval_action_count": int(summary.get("allowed_approval_action_count") or 0),
        "missing_dangerous_approval_actions": list(summary.get("missing_dangerous_approval_actions") or []),
        "target_type_count": int(summary.get("target_type_count") or 0),
        "risk_level_count": int(summary.get("risk_level_count") or 0),
        "confirmation_scope_count": int(summary.get("confirmation_scope_count") or 0),
        "missing_policy_sections": list(summary.get("missing_policy_sections") or []),
        "policy_sections_complete": bool(summary.get("policy_sections_complete")),
        "warning_count": int(summary.get("warning_count") or 0),
        "blocked_reason_count": int(summary.get("blocked_reason_count") or 0),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_human_approval_token_contract(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create HUMAN.N2 contract artifacts and return paths plus summary."""
    result = write_human_approval_token_contract(
        output_dir=output_dir,
        report_id=report_id,
        created_at=created_at,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("HUMAN.N2 - Human Approval Token / Confirmation Contract")
    print("=" * 61)
    print(f"Contract status  : {summary['contract_status']}")
    print(f"Schema fields    : {summary['schema_field_count']}")
    print(f"Required fields  : {summary['required_field_count']}")
    print(f"Allowed actions  : {summary['allowed_approval_action_count']}")
    print(f"Target types     : {summary['target_type_count']}")
    print(f"Risk levels      : {summary['risk_level_count']}")
    print(f"Scopes           : {summary['confirmation_scope_count']}")
    print(f"Missing policies : {len(summary['missing_policy_sections'])}")
    print(f"Warnings         : {summary['warning_count']}")
    print(f"Blocked reasons  : {summary['blocked_reason_count']}")
    print(f"Recommended next : {summary['recommended_next_phase']}")
    print(f"JSON             : {summary['json_path']}")
    print(f"Markdown         : {summary['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "HUMAN.N2: write a report-only contract defining explicit human "
            "approval token shape before dangerous actions."
        )
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument("--report-id", default="", help="Optional deterministic report id.")
    parser.add_argument("--created-at", default="", help="Optional created-at timestamp.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_human_approval_token_contract(
        output_dir=args.output_dir,
        report_id=args.report_id,
        created_at=args.created_at,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    status = result["summary"]["contract_status"]
    return 0 if status in {STATUS_READY, STATUS_READY_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
