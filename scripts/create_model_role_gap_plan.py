"""MODEL.N3 - Create a Model Role Gap Plan (CLI).

Writes deterministic JSON and Markdown artifacts that recommend manual MODEL.N1
tower card improvements from MODEL.N2 coverage evidence. The script does not
edit registries, route tasks, call models, launch workers, bind executable
model IDs, run validation or benchmarks, apply patches, contact networks, write
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

from core.model_role_gap_plan import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    MODEL_ROLE_GAP_PLAN_GUARDRAIL_NOTE,
    read_json_input,
    write_model_role_gap_plan,
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
        "gap_plan_status": report.get("gap_plan_status"),
        "source_coverage_path": report.get("source_coverage_path"),
        "source_model_registry_path": report.get("source_model_registry_path"),
        "missing_role_plan_count": len(report.get("missing_role_plans") or []),
        "weak_role_plan_count": len(report.get("weak_role_plans") or []),
        "risky_role_plan_count": len(report.get("risky_role_plans") or []),
        "fallback_improvement_plan_count": len(report.get("fallback_improvement_plans") or []),
        "metadata_improvement_plan_count": len(report.get("metadata_improvement_plans") or []),
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": report.get("warnings") or [],
        "blocked_reasons": report.get("blocked_reasons") or [],
    }


def run_create_model_role_gap_plan(
    *,
    coverage: str,
    model_registry: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create MODEL.N3 gap plan artifacts and return paths plus summary data."""
    coverage_data, coverage_blockers = read_json_input(coverage, "coverage", required=True)
    registry_data: dict[str, Any] | None = None
    registry_blockers: list[str] = []
    if model_registry is not None:
        registry_data, registry_blockers = read_json_input(model_registry, "model registry")
    result = write_model_role_gap_plan(
        coverage_path=coverage,
        model_registry_path=model_registry,
        output_dir=output_dir,
        coverage_data=coverage_data,
        model_registry_data=registry_data,
        input_blockers=coverage_blockers + registry_blockers,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("MODEL.N3 - Model Role Gap Plan")
    print("=" * 33)
    print(f"Gap plan status : {summary['gap_plan_status']}")
    print(f"Coverage        : {summary['source_coverage_path']}")
    print(f"Model registry  : {summary['source_model_registry_path']}")
    print(f"Missing plans   : {summary['missing_role_plan_count']}")
    print(f"Weak plans      : {summary['weak_role_plan_count']}")
    print(f"Risky plans     : {summary['risky_role_plan_count']}")
    print(f"Fallback plans  : {summary['fallback_improvement_plan_count']}")
    print(f"Metadata plans  : {summary['metadata_improvement_plan_count']}")
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
    print(f"\n> {MODEL_ROLE_GAP_PLAN_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "MODEL.N3: write a report-only model role gap plan from MODEL.N2 "
            "coverage evidence. The plan recommends manual MODEL.N1 catalog "
            "improvements and does not route tasks, call models, launch "
            "workers, or update the registry automatically."
        )
    )
    parser.add_argument("--coverage", required=True, help="Path to MODEL.N2 model_role_coverage_report.json.")
    parser.add_argument("--model-registry", help="Optional MODEL.N1 model_role_registry.json for richer metadata checks.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_model_role_gap_plan(
        coverage=args.coverage,
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
