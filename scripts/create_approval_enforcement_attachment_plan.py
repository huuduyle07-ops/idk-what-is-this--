#!/usr/bin/env python
"""Create HARDEN.N2 - Approval Enforcement Attachment Plan.

Writes a report-only plan that maps dangerous action categories to future
approval-token attachment points. It does not add approval enforcement, validate
tokens, issue or consume tokens, block routes, change auth policy, call models,
launch workers, invoke tools, run validation or benchmarks, apply patches, or
approve/reject work.
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

from core.approval_enforcement_attachment_plan import (  # noqa: E402
    DEFAULT_APPROVAL_CONTRACT_PATH,
    DEFAULT_HUMAN_CHECKPOINT_PATH,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_READINESS_AUDIT_PATH,
    DEFAULT_REGISTRY_PATH,
    GUARDRAIL_NOTE,
    STATUS_READY,
    STATUS_READY_WITH_WARNINGS,
    write_approval_enforcement_attachment_plan,
)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "plan_status": report.get("plan_status"),
        "attachment_item_count": int(report.get("attachment_item_count") or 0),
        "planned_action_count": int(report.get("planned_action_count") or 0),
        "missing_action_count": int(report.get("missing_action_count") or 0),
        "enforcement_not_implemented_confirmed": bool(report.get("enforcement_not_implemented_confirmed")),
        "approval_tokens_treated_as_real_authority": bool(report.get("approval_tokens_treated_as_real_authority")),
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "incomplete_reason_count": len(report.get("incomplete_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_approval_enforcement_attachment_plan(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    source_readiness_audit_path: str | Path = DEFAULT_READINESS_AUDIT_PATH,
    source_approval_contract_path: str | Path = DEFAULT_APPROVAL_CONTRACT_PATH,
    source_human_checkpoint_path: str | Path = DEFAULT_HUMAN_CHECKPOINT_PATH,
    optional_route_inventory_path: str | Path | None = None,
    optional_audit_inventory_path: str | Path | None = None,
    plan_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create HARDEN.N2 plan artifacts and return paths plus summary."""
    result = write_approval_enforcement_attachment_plan(
        repo_root=repo_root,
        output_dir=output_dir,
        registry_path=registry_path,
        source_readiness_audit_path=source_readiness_audit_path,
        source_approval_contract_path=source_approval_contract_path,
        source_human_checkpoint_path=source_human_checkpoint_path,
        optional_route_inventory_path=optional_route_inventory_path,
        optional_audit_inventory_path=optional_audit_inventory_path,
        plan_id=plan_id,
        created_at=created_at,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("HARDEN.N2 - Approval Enforcement Attachment Plan")
    print("=" * 55)
    print(f"Plan status       : {summary['plan_status']}")
    print(f"Attachment items  : {summary['attachment_item_count']}")
    print(f"Planned actions   : {summary['planned_action_count']}")
    print(f"Missing actions   : {summary['missing_action_count']}")
    print(f"No enforcement    : {summary['enforcement_not_implemented_confirmed']}")
    print(f"Tokens authority  : {summary['approval_tokens_treated_as_real_authority']}")
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
            "HARDEN.N2: write a report-only plan mapping dangerous action "
            "surfaces to future approval-token attachment points."
        )
    )
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH), help="Phase registry path.")
    parser.add_argument("--readiness-audit-path", default=str(DEFAULT_READINESS_AUDIT_PATH), help="HARDEN.N1 artifact.")
    parser.add_argument(
        "--approval-contract-path",
        default=str(DEFAULT_APPROVAL_CONTRACT_PATH),
        help="HUMAN.N2 artifact.",
    )
    parser.add_argument("--human-checkpoint-path", default=str(DEFAULT_HUMAN_CHECKPOINT_PATH), help="HUMAN.CLOSE artifact.")
    parser.add_argument("--route-inventory-path", default=None, help="Optional route inventory artifact.")
    parser.add_argument("--audit-inventory-path", default=None, help="Optional audit inventory artifact.")
    parser.add_argument("--plan-id", default="", help="Optional deterministic plan id.")
    parser.add_argument("--created-at", default="", help="Optional created-at timestamp.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_approval_enforcement_attachment_plan(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        registry_path=args.registry_path,
        source_readiness_audit_path=args.readiness_audit_path,
        source_approval_contract_path=args.approval_contract_path,
        source_human_checkpoint_path=args.human_checkpoint_path,
        optional_route_inventory_path=args.route_inventory_path,
        optional_audit_inventory_path=args.audit_inventory_path,
        plan_id=args.plan_id,
        created_at=args.created_at,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    status = result["summary"]["plan_status"]
    return 0 if status in {STATUS_READY, STATUS_READY_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
