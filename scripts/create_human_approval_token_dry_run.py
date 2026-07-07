#!/usr/bin/env python
"""Create HUMAN.N3 - Human Approval Token Dry-Run Validator reports.

Reads a sample approval token JSON artifact and a HUMAN.N2 contract JSON artifact,
then writes dry-run JSON/Markdown reports only. It does not authorize actions,
reject live actions, enforce routes, consume tokens, apply patches, run validation
or benchmarks, invoke MCP/tools, use network access, execute Docker/subprocess
work, write databases, change auth/routes, or launch workers.
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

from core.human_approval_token_dry_run_validator import (  # noqa: E402
    DEFAULT_CONTRACT_PATH,
    DEFAULT_OUTPUT_ROOT,
    GUARDRAIL_NOTE,
    STATUS_BLOCKED,
    write_human_approval_token_dry_run,
)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    token_summary = report.get("token_summary") if isinstance(report.get("token_summary"), dict) else {}
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "dry_run_status": report.get("dry_run_status"),
        "token_id": report.get("token_id"),
        "approval_action": token_summary.get("approval_action"),
        "target_type": token_summary.get("target_type"),
        "target_id": token_summary.get("target_id"),
        "risk_level": token_summary.get("risk_level"),
        "schema_finding_count": int(token_summary.get("schema_finding_count") or 0),
        "blocked_reason_count": int(token_summary.get("blocked_reason_count") or 0),
        "warning_count": int(token_summary.get("warning_count") or 0),
        "authorizes_action": False,
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_human_approval_token_dry_run(
    *,
    token: str | Path,
    contract: str | Path = DEFAULT_CONTRACT_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str = "",
    created_at: str = "",
    now: str = "",
) -> dict[str, Any]:
    """Create a HUMAN.N3 dry-run report and return paths plus summary."""
    result = write_human_approval_token_dry_run(
        token_path=token,
        contract_path=contract,
        output_dir=output_dir,
        report_id=report_id,
        created_at=created_at,
        now=now,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("HUMAN.N3 - Human Approval Token Dry-Run Validator")
    print("=" * 56)
    print(f"Dry-run status : {summary['dry_run_status']}")
    print(f"Token ID       : {summary['token_id']}")
    print(f"Action         : {summary['approval_action']}")
    print(f"Target         : {summary['target_type']} / {summary['target_id']}")
    print(f"Risk           : {summary['risk_level']}")
    print(f"Schema findings: {summary['schema_finding_count']}")
    print(f"Warnings       : {summary['warning_count']}")
    print(f"Blocked reasons: {summary['blocked_reason_count']}")
    print(f"Authorizes     : {str(summary['authorizes_action']).lower()}")
    print(f"Recommended next: {summary['recommended_next_phase']}")
    print(f"JSON           : {summary['json_path']}")
    print(f"Markdown       : {summary['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "HUMAN.N3: validate one sample approval token against the HUMAN.N2 "
            "contract and write dry-run report artifacts only."
        )
    )
    parser.add_argument("--token", required=True, help="Path to sample approval token JSON.")
    parser.add_argument(
        "--contract",
        default=str(DEFAULT_CONTRACT_PATH),
        help="Path to HUMAN.N2 human_approval_token_contract.json.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument("--report-id", default="", help="Optional deterministic dry-run id.")
    parser.add_argument("--created-at", default="", help="Optional report created-at timestamp.")
    parser.add_argument("--now", default="", help="Optional ISO timestamp used for expiry checks.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_human_approval_token_dry_run(
        token=args.token,
        contract=args.contract,
        output_dir=args.output_dir,
        report_id=args.report_id,
        created_at=args.created_at,
        now=args.now,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 1 if result["summary"]["dry_run_status"] == STATUS_BLOCKED else 0


if __name__ == "__main__":
    raise SystemExit(main())
