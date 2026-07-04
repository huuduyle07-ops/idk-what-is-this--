"""MODEL.N7 - Create a Model Role Catalog Adoption Readiness Check (CLI).

Writes deterministic JSON and Markdown readiness artifacts from MODEL.N4,
MODEL.N5, MODEL.N6, MODEL.N1, and proposed registry artifacts. The script is
report-only: it does not replace registries, mutate proposals, route tasks, call
models, launch workers, bind executable model IDs, run validation or benchmarks,
apply patches, contact networks, write databases, or change runtime behavior.
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

from core.model_role_catalog_adoption_readiness import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    MODEL_ROLE_CATALOG_ADOPTION_READINESS_GUARDRAIL_NOTE,
    read_json_input,
    write_model_role_catalog_adoption_readiness,
)


DEFAULT_OUTPUT_DIR = str(DEFAULT_OUTPUT_ROOT)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") or {}
    proposed = report.get("proposed_registry_safety_check") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "readiness_status": report.get("readiness_status"),
        "source_proposal_path": report.get("source_proposal_path"),
        "source_review_path": report.get("source_review_path"),
        "source_adoption_plan_path": report.get("source_adoption_plan_path"),
        "source_registry_path": report.get("source_registry_path"),
        "proposed_registry_path": report.get("proposed_registry_path"),
        "proposed_role_count": proposed.get("proposed_role_count"),
        "expected_new_role_count": len(proposed.get("expected_new_role_ids") or []),
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": report.get("warnings") or [],
        "blocked_reasons": report.get("blocked_reasons") or [],
    }


def run_create_model_role_catalog_adoption_readiness(
    *,
    proposal: str,
    review: str,
    adoption_plan: str,
    source_registry: str,
    proposed_registry: str,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create MODEL.N7 readiness artifacts and return paths plus summary data."""
    proposal_data, proposal_blockers = read_json_input(proposal, "proposal", required=True)
    review_data, review_blockers = read_json_input(review, "review", required=True)
    adoption_data, adoption_blockers = read_json_input(adoption_plan, "adoption plan", required=True)
    source_data, source_blockers = read_json_input(source_registry, "source registry", required=True)
    proposed_data, proposed_blockers = read_json_input(proposed_registry, "proposed registry", required=True)

    result = write_model_role_catalog_adoption_readiness(
        proposal_path=proposal,
        proposal_data=proposal_data,
        review_path=review,
        review_data=review_data,
        adoption_plan_path=adoption_plan,
        adoption_plan_data=adoption_data,
        source_registry_path=source_registry,
        source_registry_data=source_data,
        proposed_registry_path=proposed_registry,
        proposed_registry_data=proposed_data,
        output_dir=output_dir,
        input_blockers=proposal_blockers
        + review_blockers
        + adoption_blockers
        + source_blockers
        + proposed_blockers,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("MODEL.N7 - Model Role Catalog Adoption Readiness Check")
    print("=" * 58)
    print(f"Readiness status: {summary['readiness_status']}")
    print(f"Proposal        : {summary['source_proposal_path']}")
    print(f"Review          : {summary['source_review_path']}")
    print(f"Adoption plan   : {summary['source_adoption_plan_path']}")
    print(f"Source registry : {summary['source_registry_path']}")
    print(f"Proposed catalog: {summary['proposed_registry_path']}")
    print(f"Proposed roles  : {summary['proposed_role_count']}")
    print(f"Expected new    : {summary['expected_new_role_count']}")
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
    print(f"\n> {MODEL_ROLE_CATALOG_ADOPTION_READINESS_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "MODEL.N7: write a report-only readiness check before any future "
            "human-approved model-role catalog adoption. This grants no routing, "
            "worker launch, model-call, patch, executable model-binding, or "
            "automatic adoption authority."
        )
    )
    parser.add_argument("--proposal", required=True, help="Path to MODEL.N4 model_role_catalog_update_proposal.json.")
    parser.add_argument("--review", required=True, help="Path to MODEL.N5 model_role_catalog_proposal_review.json.")
    parser.add_argument("--adoption-plan", required=True, help="Path to MODEL.N6 model_role_catalog_adoption_plan.json.")
    parser.add_argument("--source-registry", required=True, help="Path to MODEL.N1 model_role_registry.json.")
    parser.add_argument(
        "--proposed-registry",
        required=True,
        help="Path to MODEL.N4 proposed_model_role_registry.json.",
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_model_role_catalog_adoption_readiness(
        proposal=args.proposal,
        review=args.review,
        adoption_plan=args.adoption_plan,
        source_registry=args.source_registry,
        proposed_registry=args.proposed_registry,
        output_dir=args.output_dir,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
