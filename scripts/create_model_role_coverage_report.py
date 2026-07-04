"""MODEL.N2 - Create a Model Role Coverage Report (CLI).

Writes deterministic JSON and Markdown coverage artifacts comparing Commander
advisory role labels from CMD.N5/CMD.N6 to MODEL.N1 advisory tower cards. The
script does not route tasks, call models, launch workers, bind executable model
IDs, run validation or benchmarks, apply patches, contact networks, write
databases, or mutate source artifacts.
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

from core.model_role_coverage_report import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    MODEL_ROLE_COVERAGE_GUARDRAIL_NOTE,
    read_json_input,
    write_model_role_coverage_report,
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
        "coverage_status": report.get("coverage_status"),
        "source_model_registry_path": report.get("source_model_registry_path"),
        "source_assignment_path": report.get("source_assignment_path"),
        "source_review_pack_path": report.get("source_review_pack_path"),
        "required_commander_role_count": len(report.get("required_commander_roles") or []),
        "available_model_role_count": len(report.get("available_model_roles") or []),
        "matched_role_count": len(report.get("matched_roles") or []),
        "missing_roles": report.get("missing_roles") or [],
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": report.get("warnings") or [],
        "blocked_reasons": report.get("blocked_reasons") or [],
    }


def run_create_model_role_coverage_report(
    *,
    model_registry: str,
    assignment: str | None = None,
    review_pack: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create MODEL.N2 coverage artifacts and return paths plus summary data."""
    registry_data, registry_blockers = read_json_input(model_registry, "model registry", required=True)
    assignment_data: dict[str, Any] | None = None
    assignment_blockers: list[str] = []
    if assignment is not None:
        assignment_data, assignment_blockers = read_json_input(assignment, "assignment")
    review_pack_data: dict[str, Any] | None = None
    review_pack_blockers: list[str] = []
    if review_pack is not None:
        review_pack_data, review_pack_blockers = read_json_input(review_pack, "review pack")
    result = write_model_role_coverage_report(
        model_registry_path=model_registry,
        assignment_path=assignment,
        review_pack_path=review_pack,
        output_dir=output_dir,
        model_registry_data=registry_data,
        assignment_data=assignment_data,
        review_pack_data=review_pack_data,
        input_blockers=registry_blockers + assignment_blockers + review_pack_blockers,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("MODEL.N2 - Model Role Coverage Report")
    print("=" * 39)
    print(f"Coverage status : {summary['coverage_status']}")
    print(f"Model registry  : {summary['source_model_registry_path']}")
    print(f"Assignment      : {summary['source_assignment_path']}")
    print(f"Review pack     : {summary['source_review_pack_path']}")
    print(f"Required roles  : {summary['required_commander_role_count']}")
    print(f"Available roles : {summary['available_model_role_count']}")
    print(f"Matched roles   : {summary['matched_role_count']}")
    print(f"Missing roles   : {', '.join(summary['missing_roles']) if summary['missing_roles'] else '(none)'}")
    print(f"Recommended next: {summary['recommended_next_phase']}")
    print(f"JSON            : {summary['json_path']}")
    print(f"Markdown        : {summary['md_path']}")
    if summary["blocked_reasons"]:
        print("Blocked reasons :")
        for reason in summary["blocked_reasons"]:
            print(f"  - {reason}")
    if summary["warnings"]:
        print("Warnings        :")
        for warning in summary["warnings"]:
            print(f"  - {warning}")
    print(f"\n> {MODEL_ROLE_COVERAGE_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "MODEL.N2: write a report-only model role coverage report. The "
            "report compares Commander advisory labels to MODEL.N1 cards and "
            "does not route tasks, call models, launch workers, or bind "
            "executable model IDs."
        )
    )
    parser.add_argument("--model-registry", required=True, help="Path to MODEL.N1 model_role_registry.json.")
    parser.add_argument("--assignment", help="Optional CMD.N5 commander_manual_assignment_plan.json.")
    parser.add_argument("--review-pack", help="Optional CMD.N6 commander_assignment_review_pack.json.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_model_role_coverage_report(
        model_registry=args.model_registry,
        assignment=args.assignment,
        review_pack=args.review_pack,
        output_dir=args.output_dir,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
