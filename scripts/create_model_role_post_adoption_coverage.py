"""ADOPT.MODEL.2 - Create a Post-Adoption Role Coverage Recheck.

Writes deterministic JSON and Markdown artifacts verifying that the active
advisory model-role catalog resolves the MODEL.N3 role gaps after ADOPT.MODEL.1.
This script grants no model routing, model calls, worker launch, executable
model binding, validation, benchmark, patch, network, database, route/auth,
approval-token, or automatic authority.
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

from core.model_role_post_adoption_coverage import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    MODEL_ROLE_POST_ADOPTION_COVERAGE_GUARDRAIL_NOTE,
    read_json_input,
    write_model_role_post_adoption_coverage,
)


DEFAULT_ACTIVE_CATALOG = ".agent/model_role_registry/model_role_registry.json"
DEFAULT_ADOPTION_RECEIPT = ".agent/model_role_registry/adoption/model_role_catalog_adoption_receipt.json"
DEFAULT_GAP_PLAN = ".agent/model_role_registry/model_role_gap_plan/model_role_gap_plan.json"
DEFAULT_READINESS = (
    ".agent/model_role_registry/model_role_catalog_adoption_readiness/"
    "model_role_catalog_adoption_readiness.json"
)
DEFAULT_OUTPUT_DIR = str(DEFAULT_OUTPUT_ROOT)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "post_adoption_coverage_status": report.get("post_adoption_coverage_status"),
        "source_active_catalog_path": report.get("source_active_catalog_path"),
        "source_adoption_receipt_path": report.get("source_adoption_receipt_path"),
        "source_gap_plan_path": report.get("source_gap_plan_path"),
        "source_readiness_path": report.get("source_readiness_path"),
        "active_role_count": report.get("active_role_count"),
        "expected_role_count": report.get("expected_role_count"),
        "resolved_gaps": report.get("resolved_gaps") or [],
        "unresolved_gaps": report.get("unresolved_gaps") or [],
        "added_roles_verified": bool(report.get("added_roles_verified")),
        "preserved_roles_verified": bool(report.get("preserved_roles_verified")),
        "warning_count": len(report.get("warnings") or []),
        "incomplete_reason_count": len(report.get("incomplete_reasons") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": report.get("warnings") or [],
        "incomplete_reasons": report.get("incomplete_reasons") or [],
        "blocked_reasons": report.get("blocked_reasons") or [],
    }


def run_create_model_role_post_adoption_coverage(
    *,
    active_catalog: str = DEFAULT_ACTIVE_CATALOG,
    adoption_receipt: str = DEFAULT_ADOPTION_RECEIPT,
    gap_plan: str | None = DEFAULT_GAP_PLAN,
    readiness: str | None = DEFAULT_READINESS,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create ADOPT.MODEL.2 coverage artifacts and return summary data."""
    active_data, active_findings = read_json_input(active_catalog, "active catalog", required=True)
    receipt_data, receipt_findings = read_json_input(adoption_receipt, "adoption receipt", required=True)
    gap_data: dict[str, Any] | None = None
    gap_findings: list[str] = []
    if gap_plan is not None:
        gap_data, gap_findings = read_json_input(gap_plan, "gap plan", required=True)
    readiness_data: dict[str, Any] | None = None
    readiness_findings: list[str] = []
    if readiness is not None:
        readiness_data, readiness_findings = read_json_input(readiness, "readiness", required=False)
    result = write_model_role_post_adoption_coverage(
        active_catalog_path=active_catalog,
        adoption_receipt_path=adoption_receipt,
        gap_plan_path=gap_plan,
        readiness_path=readiness,
        output_dir=output_dir,
        active_catalog_data=active_data,
        adoption_receipt_data=receipt_data,
        gap_plan_data=gap_data,
        readiness_data=readiness_data,
        input_blockers=active_findings,
        input_incomplete=receipt_findings + gap_findings,
        input_warnings=readiness_findings,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("ADOPT.MODEL.2 - Post-Adoption Role Coverage Recheck")
    print("=" * 58)
    print(f"Coverage status : {summary['post_adoption_coverage_status']}")
    print(f"Active catalog  : {summary['source_active_catalog_path']}")
    print(f"Adoption receipt: {summary['source_adoption_receipt_path']}")
    print(f"Gap plan        : {summary['source_gap_plan_path']}")
    print(f"Readiness       : {summary['source_readiness_path']}")
    print(f"Active roles    : {summary['active_role_count']}")
    print(f"Expected roles  : {summary['expected_role_count']}")
    print(f"Resolved gaps   : {', '.join(summary['resolved_gaps']) if summary['resolved_gaps'] else '(none)'}")
    print(f"Unresolved gaps : {', '.join(summary['unresolved_gaps']) if summary['unresolved_gaps'] else '(none)'}")
    print(f"Recommended next: {summary['recommended_next_phase']}")
    print(f"JSON report     : {summary['json_path']}")
    print(f"Markdown report : {summary['md_path']}")
    if summary["blocked_reasons"]:
        print("Blocked reasons :")
        for reason in summary["blocked_reasons"]:
            print(f"  - {reason}")
    if summary["incomplete_reasons"]:
        print("Incomplete      :")
        for reason in summary["incomplete_reasons"]:
            print(f"  - {reason}")
    if summary["warnings"]:
        print("Warnings        :")
        for warning in summary["warnings"]:
            print(f"  - {warning}")
    print(f"\n> {MODEL_ROLE_POST_ADOPTION_COVERAGE_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ADOPT.MODEL.2: write a report-only post-adoption model role "
            "coverage recheck. The report verifies the active advisory catalog "
            "and does not route tasks, call models, launch workers, or bind "
            "executable model IDs."
        )
    )
    parser.add_argument("--active-catalog", default=DEFAULT_ACTIVE_CATALOG)
    parser.add_argument("--adoption-receipt", default=DEFAULT_ADOPTION_RECEIPT)
    parser.add_argument("--gap-plan", default=DEFAULT_GAP_PLAN)
    parser.add_argument("--readiness", default=DEFAULT_READINESS)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_model_role_post_adoption_coverage(
        active_catalog=args.active_catalog,
        adoption_receipt=args.adoption_receipt,
        gap_plan=args.gap_plan,
        readiness=args.readiness,
        output_dir=args.output_dir,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
