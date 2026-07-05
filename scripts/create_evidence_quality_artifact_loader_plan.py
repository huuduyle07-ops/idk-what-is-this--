"""EVAL.N4 - Create an Evidence Quality Artifact Loader Plan (CLI).

Writes advisory JSON/Markdown planning artifacts only. It does not add a UI,
backend route, runtime loader, validation run, benchmark run, model call, patch
application, scoring gate, approval gate, or automatic decision.
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

from core.evidence_quality_artifact_loader_plan import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    EVIDENCE_QUALITY_ARTIFACT_LOADER_PLAN_GUARDRAIL_NOTE,
    write_evidence_quality_artifact_loader_plan,
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
        "plan_status": report.get("plan_status"),
        "visible_field_count": len(report.get("visible_fields") or []),
        "debug_field_count": len(report.get("collapsed_debug_fields") or []),
        "empty_error_state_count": len(report.get("empty_error_states") or []),
        "warning_language_count": len(report.get("warning_language") or []),
        "forbidden_behavior_count": len(report.get("forbidden_loader_behavior") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_evidence_quality_artifact_loader_plan(
    *,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create EVAL.N4 plan artifacts and return paths plus summary."""
    result = write_evidence_quality_artifact_loader_plan(output_dir=output_dir)
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("EVAL.N4 - Evidence Quality Artifact Loader Plan")
    print("=" * 50)
    print(f"Plan status       : {summary['plan_status']}")
    print(f"Visible fields    : {summary['visible_field_count']}")
    print(f"Debug fields      : {summary['debug_field_count']}")
    print(f"Warning lines     : {summary['warning_language_count']}")
    print(f"Forbidden behavior: {summary['forbidden_behavior_count']}")
    print(f"Recommended next  : {summary['recommended_next_phase']}")
    print(f"JSON              : {summary['json_path']}")
    print(f"Markdown          : {summary['md_path']}")
    print(f"\n> {EVIDENCE_QUALITY_ARTIFACT_LOADER_PLAN_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "EVAL.N4: write a report-only artifact-loader/display plan for "
            "existing EVAL.N3 evidence quality reports. This adds no UI, route, "
            "runtime loader, validation, benchmark, model-call, patch, scoring, "
            "approval, or rejection behavior."
        )
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_evidence_quality_artifact_loader_plan(output_dir=args.output_dir)
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
