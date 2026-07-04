"""MODEL.N4 - Create a Model Role Catalog Update Proposal (CLI).

Writes deterministic JSON and Markdown artifacts plus a separate proposed
MODEL.N1 catalog file from MODEL.N3 gap-plan evidence. The script does not edit
the active registry, change runtime model selection, route tasks, call models,
launch workers, bind executable model IDs, run validation or benchmarks, apply
patches, contact networks, write databases, or mutate source artifacts.
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

from core.model_role_catalog_update_proposal import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    MODEL_ROLE_CATALOG_UPDATE_PROPOSAL_GUARDRAIL_NOTE,
    read_json_input,
    write_model_role_catalog_update_proposal,
)


DEFAULT_OUTPUT_DIR = str(DEFAULT_OUTPUT_ROOT)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "proposed_registry_path": result.get("proposed_registry_path"),
        "report_kind": report.get("report_kind"),
        "proposal_status": report.get("proposal_status"),
        "source_gap_plan_path": report.get("source_gap_plan_path"),
        "source_model_registry_path": report.get("source_model_registry_path"),
        "current_role_count": report.get("current_role_count"),
        "proposed_role_count": report.get("proposed_role_count"),
        "proposed_new_role_count": len(report.get("proposed_new_roles") or []),
        "proposed_role_update_count": len(report.get("proposed_role_updates") or []),
        "rejected_gap_item_count": len(report.get("rejected_gap_items") or []),
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": report.get("warnings") or [],
        "blocked_reasons": report.get("blocked_reasons") or [],
    }


def run_create_model_role_catalog_update_proposal(
    *,
    gap_plan: str,
    model_registry: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create MODEL.N4 proposal artifacts and return paths plus summary data."""
    gap_plan_data, gap_blockers = read_json_input(gap_plan, "gap plan", required=True)
    registry_data: dict[str, Any] | None = None
    registry_blockers: list[str] = []
    if model_registry is not None:
        registry_data, registry_blockers = read_json_input(model_registry, "model registry")
    result = write_model_role_catalog_update_proposal(
        gap_plan_path=gap_plan,
        model_registry_path=model_registry,
        output_dir=output_dir,
        gap_plan_data=gap_plan_data,
        model_registry_data=registry_data,
        input_blockers=gap_blockers + registry_blockers,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("MODEL.N4 - Model Role Catalog Update Proposal")
    print("=" * 47)
    print(f"Proposal status : {summary['proposal_status']}")
    print(f"Gap plan        : {summary['source_gap_plan_path']}")
    print(f"Model registry  : {summary['source_model_registry_path']}")
    print(f"Current roles   : {summary['current_role_count']}")
    print(f"Proposed roles  : {summary['proposed_role_count']}")
    print(f"New roles       : {summary['proposed_new_role_count']}")
    print(f"Role updates    : {summary['proposed_role_update_count']}")
    print(f"Rejected gaps   : {summary['rejected_gap_item_count']}")
    print(f"Recommended next: {summary['recommended_next_phase']}")
    print(f"JSON            : {summary['json_path']}")
    print(f"Markdown        : {summary['md_path']}")
    print(f"Proposed catalog: {summary['proposed_registry_path']}")
    if summary["blocked_reasons"]:
        print("Blocked reasons :")
        for reason in summary["blocked_reasons"]:
            print(f"  - {reason}")
    if summary["warnings"]:
        print("Warnings        :")
        for warning in summary["warnings"]:
            print(f"  - {warning}")
    print(f"\n> {MODEL_ROLE_CATALOG_UPDATE_PROPOSAL_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "MODEL.N4: write a report-only proposed model-role catalog update "
            "from MODEL.N3 gap-plan evidence. The proposal is separate from the "
            "active MODEL.N1 registry and grants no routing, worker launch, "
            "model-call, patch, or executable model-binding authority."
        )
    )
    parser.add_argument("--gap-plan", required=True, help="Path to MODEL.N3 model_role_gap_plan.json.")
    parser.add_argument("--model-registry", help="Optional MODEL.N1 model_role_registry.json.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_model_role_catalog_update_proposal(
        gap_plan=args.gap_plan,
        model_registry=args.model_registry,
        output_dir=args.output_dir,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
