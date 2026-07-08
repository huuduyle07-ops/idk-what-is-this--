"""Create ADOPT.MODEL.CLOSE - Model Catalog Adoption Branch Checkpoint.

Writes a report-only checkpoint for the completed model catalog adoption branch.
The script reads local artifacts and writes JSON/Markdown output only. It does
not route models, call models, launch workers, create executable bindings,
enforce approvals, apply patches, run validation or benchmarks, contact
networks, write databases, or change route/auth behavior.
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

from core.model_role_catalog_adoption_checkpoint import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    GUARDRAIL_NOTE,
    read_json_input,
    write_model_role_catalog_adoption_checkpoint,
)


DEFAULT_REGISTRY = "docs/roadmap/phase_registry.json"
DEFAULT_ACTIVE_CATALOG = ".agent/model_role_registry/model_role_registry.json"
DEFAULT_ADOPTION_RECEIPT = ".agent/model_role_registry/adoption/model_role_catalog_adoption_receipt.json"
DEFAULT_POST_ADOPTION_COVERAGE = (
    ".agent/model_role_registry/post_adoption_coverage/model_role_post_adoption_coverage.json"
)
DEFAULT_MODEL_CLOSE = (
    ".agent/model_role_registry/model_role_planning_checkpoint/model_role_planning_checkpoint.json"
)
DEFAULT_HUMAN_CLOSE = ".agent/human/authority_branch_checkpoint/human_authority_branch_checkpoint.json"
DEFAULT_OUTPUT_DIR = str(DEFAULT_OUTPUT_ROOT)


def _optional_path(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "checkpoint_status": report.get("checkpoint_status"),
        "active_catalog_path": report.get("active_catalog_path"),
        "adoption_receipt_path": report.get("adoption_receipt_path"),
        "post_adoption_coverage_path": report.get("post_adoption_coverage_path"),
        "active_role_count": report.get("active_role_count"),
        "expected_role_count": report.get("expected_role_count"),
        "added_roles": report.get("added_roles") or [],
        "resolved_gaps": report.get("resolved_gaps") or [],
        "unresolved_gaps": report.get("unresolved_gaps") or [],
        "preserved_roles_verified": bool(report.get("preserved_roles_verified")),
        "advisory_only_confirmed": bool(report.get("advisory_only_confirmed")),
        "human_authority_boundary_referenced": bool(report.get("human_authority_boundary_referenced")),
        "warning_count": len(report.get("warnings") or []),
        "incomplete_reason_count": len(report.get("incomplete_reasons") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": report.get("warnings") or [],
        "incomplete_reasons": report.get("incomplete_reasons") or [],
        "blocked_reasons": report.get("blocked_reasons") or [],
    }


def run_create_model_role_catalog_adoption_checkpoint(
    *,
    registry: str = DEFAULT_REGISTRY,
    active_catalog: str = DEFAULT_ACTIVE_CATALOG,
    adoption_receipt: str = DEFAULT_ADOPTION_RECEIPT,
    post_adoption_coverage: str = DEFAULT_POST_ADOPTION_COVERAGE,
    model_close: str | None = DEFAULT_MODEL_CLOSE,
    human_close: str | None = DEFAULT_HUMAN_CLOSE,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create ADOPT.MODEL.CLOSE checkpoint artifacts and return summary data."""
    registry_data, registry_findings = read_json_input(registry, "phase registry", required=True)
    active_data, active_findings = read_json_input(active_catalog, "active catalog", required=True)
    receipt_data, receipt_findings = read_json_input(adoption_receipt, "adoption receipt", required=True)
    coverage_data, coverage_findings = read_json_input(
        post_adoption_coverage,
        "post-adoption coverage",
        required=True,
    )

    model_close = _optional_path(model_close)
    human_close = _optional_path(human_close)
    model_close_data: dict[str, Any] | None = None
    model_close_findings: list[str] = []
    if model_close is not None:
        model_close_data, model_close_findings = read_json_input(
            model_close,
            "MODEL.CLOSE checkpoint",
            required=False,
        )
    human_close_data: dict[str, Any] | None = None
    human_close_findings: list[str] = []
    if human_close is not None:
        human_close_data, human_close_findings = read_json_input(
            human_close,
            "HUMAN.CLOSE checkpoint",
            required=False,
        )

    result = write_model_role_catalog_adoption_checkpoint(
        registry_path=registry,
        active_catalog_path=active_catalog,
        adoption_receipt_path=adoption_receipt,
        post_adoption_coverage_path=post_adoption_coverage,
        model_close_path=model_close,
        human_close_path=human_close,
        output_dir=output_dir,
        registry_data=registry_data,
        active_catalog_data=active_data,
        adoption_receipt_data=receipt_data,
        post_adoption_coverage_data=coverage_data,
        model_close_data=model_close_data,
        human_close_data=human_close_data,
        input_blockers=active_findings,
        input_incomplete=registry_findings + receipt_findings + coverage_findings,
        input_warnings=model_close_findings + human_close_findings,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("ADOPT.MODEL.CLOSE - Model Catalog Adoption Branch Checkpoint")
    print("=" * 66)
    print(f"Checkpoint status : {summary['checkpoint_status']}")
    print(f"Active catalog    : {summary['active_catalog_path']}")
    print(f"Adoption receipt  : {summary['adoption_receipt_path']}")
    print(f"Coverage report   : {summary['post_adoption_coverage_path']}")
    print(f"Active roles      : {summary['active_role_count']}")
    print(f"Expected roles    : {summary['expected_role_count']}")
    print(f"Resolved gaps     : {', '.join(summary['resolved_gaps']) if summary['resolved_gaps'] else '(none)'}")
    print(f"Unresolved gaps   : {', '.join(summary['unresolved_gaps']) if summary['unresolved_gaps'] else '(none)'}")
    print(f"Recommended next  : {summary['recommended_next_phase']}")
    print(f"JSON report       : {summary['json_path']}")
    print(f"Markdown report   : {summary['md_path']}")
    if summary["blocked_reasons"]:
        print("Blocked reasons   :")
        for reason in summary["blocked_reasons"]:
            print(f"  - {reason}")
    if summary["incomplete_reasons"]:
        print("Incomplete        :")
        for reason in summary["incomplete_reasons"]:
            print(f"  - {reason}")
    if summary["warnings"]:
        print("Warnings          :")
        for warning in summary["warnings"]:
            print(f"  - {warning}")
    print(f"\n> {GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ADOPT.MODEL.CLOSE: write a report-only checkpoint that freezes the "
            "model catalog adoption branch without enabling routing, model calls, "
            "worker launch, executable bindings, or approval enforcement."
        )
    )
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--active-catalog", default=DEFAULT_ACTIVE_CATALOG)
    parser.add_argument("--adoption-receipt", default=DEFAULT_ADOPTION_RECEIPT)
    parser.add_argument("--post-adoption-coverage", default=DEFAULT_POST_ADOPTION_COVERAGE)
    parser.add_argument("--model-close", default=DEFAULT_MODEL_CLOSE)
    parser.add_argument("--human-close", default=DEFAULT_HUMAN_CLOSE)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Exit 0 when checkpoint_status is frozen_with_warnings.",
    )
    args = parser.parse_args(argv)

    result = run_create_model_role_catalog_adoption_checkpoint(
        registry=args.registry,
        active_catalog=args.active_catalog,
        adoption_receipt=args.adoption_receipt,
        post_adoption_coverage=args.post_adoption_coverage,
        model_close=args.model_close,
        human_close=args.human_close,
        output_dir=args.output_dir,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
