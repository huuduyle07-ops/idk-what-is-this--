"""MODEL.CLOSE - Create a Model Role Planning Checkpoint (CLI).

Writes deterministic JSON and Markdown checkpoint artifacts from the MODEL.N1
through MODEL.N7 report chain. The script is report-only: it does not adopt
catalogs, replace registries, route tasks, call models, launch workers, bind
executable model IDs, run validation or benchmarks, apply patches, contact
networks, write databases, or change runtime behavior.
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

from core.model_role_planning_checkpoint import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    MODEL_ROLE_PLANNING_CHECKPOINT_GUARDRAIL_NOTE,
    read_json_input,
    write_model_role_planning_checkpoint,
)


DEFAULT_OUTPUT_DIR = str(DEFAULT_OUTPUT_ROOT)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") or {}
    active = report.get("active_registry_status") or {}
    proposed = report.get("proposed_registry_status") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "checkpoint_status": report.get("checkpoint_status"),
        "active_role_count": active.get("active_role_count"),
        "proposed_role_count": proposed.get("proposed_role_count"),
        "proposed_catalog_adopted": proposed.get("proposed_catalog_adopted"),
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": report.get("warnings") or [],
        "blocked_reasons": report.get("blocked_reasons") or [],
    }


def run_create_model_role_planning_checkpoint(
    *,
    phase_registry: str,
    model_registry: str,
    coverage_report: str,
    gap_plan: str,
    proposal: str,
    proposed_registry: str,
    review: str,
    adoption_plan: str,
    adoption_readiness: str,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create MODEL.CLOSE checkpoint artifacts and return paths plus summary data."""
    registry_data, registry_blockers = read_json_input(phase_registry, "phase registry", required=True)
    model_data, model_blockers = read_json_input(model_registry, "active registry", required=True)
    coverage_data, coverage_blockers = read_json_input(coverage_report, "coverage report", required=True)
    gap_data, gap_blockers = read_json_input(gap_plan, "gap plan", required=True)
    proposal_data, proposal_blockers = read_json_input(proposal, "proposal", required=True)
    proposed_data, proposed_blockers = read_json_input(proposed_registry, "proposed registry", required=True)
    review_data, review_blockers = read_json_input(review, "proposal review", required=True)
    adoption_data, adoption_blockers = read_json_input(adoption_plan, "adoption plan", required=True)
    readiness_data, readiness_blockers = read_json_input(adoption_readiness, "adoption readiness", required=True)

    result = write_model_role_planning_checkpoint(
        phase_registry_path=phase_registry,
        phase_registry_data=registry_data,
        model_registry_path=model_registry,
        model_registry_data=model_data,
        coverage_report_path=coverage_report,
        coverage_report_data=coverage_data,
        gap_plan_path=gap_plan,
        gap_plan_data=gap_data,
        proposal_path=proposal,
        proposal_data=proposal_data,
        proposed_registry_path=proposed_registry,
        proposed_registry_data=proposed_data,
        review_path=review,
        review_data=review_data,
        adoption_plan_path=adoption_plan,
        adoption_plan_data=adoption_data,
        adoption_readiness_path=adoption_readiness,
        adoption_readiness_data=readiness_data,
        output_dir=output_dir,
        input_blockers=registry_blockers
        + model_blockers
        + coverage_blockers
        + gap_blockers
        + proposal_blockers
        + proposed_blockers
        + review_blockers
        + adoption_blockers
        + readiness_blockers,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("MODEL.CLOSE - Model Role Planning Checkpoint")
    print("=" * 48)
    print(f"Checkpoint      : {summary['checkpoint_status']}")
    print(f"Active roles    : {summary['active_role_count']}")
    print(f"Proposed roles  : {summary['proposed_role_count']}")
    print(f"Catalog adopted : {summary['proposed_catalog_adopted']}")
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
    print(f"\n> {MODEL_ROLE_PLANNING_CHECKPOINT_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "MODEL.CLOSE: write a report-only checkpoint for the completed "
            "MODEL.N1-MODEL.N7 advisory planning branch. This grants no adoption, "
            "routing, worker launch, model-call, patch, or executable model-binding authority."
        )
    )
    parser.add_argument("--registry", dest="phase_registry", required=True, help="Path to phase_registry.json.")
    parser.add_argument("--model-registry", required=True, help="Path to MODEL.N1 model_role_registry.json.")
    parser.add_argument("--coverage-report", required=True, help="Path to MODEL.N2 model_role_coverage_report.json.")
    parser.add_argument("--gap-plan", required=True, help="Path to MODEL.N3 model_role_gap_plan.json.")
    parser.add_argument("--proposal", required=True, help="Path to MODEL.N4 model_role_catalog_update_proposal.json.")
    parser.add_argument("--proposed-registry", required=True, help="Path to MODEL.N4 proposed_model_role_registry.json.")
    parser.add_argument("--review", required=True, help="Path to MODEL.N5 model_role_catalog_proposal_review.json.")
    parser.add_argument("--adoption-plan", required=True, help="Path to MODEL.N6 model_role_catalog_adoption_plan.json.")
    parser.add_argument(
        "--adoption-readiness",
        required=True,
        help="Path to MODEL.N7 model_role_catalog_adoption_readiness.json.",
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_model_role_planning_checkpoint(
        phase_registry=args.phase_registry,
        model_registry=args.model_registry,
        coverage_report=args.coverage_report,
        gap_plan=args.gap_plan,
        proposal=args.proposal,
        proposed_registry=args.proposed_registry,
        review=args.review,
        adoption_plan=args.adoption_plan,
        adoption_readiness=args.adoption_readiness,
        output_dir=args.output_dir,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
