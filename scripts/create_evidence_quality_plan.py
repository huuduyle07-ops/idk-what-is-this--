"""EVAL.N1 - Create an Evidence Quality Plan (CLI).

Writes deterministic JSON and Markdown planning artifacts. The script is
report-only: it does not score real patches, run validation or benchmarks, call
models, apply patches, invoke MCP tools, launch workers, contact networks, write
databases, change routes/auth/scoring gates, or approve/reject work.
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

from core.evidence_quality_plan import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    EVIDENCE_QUALITY_PLAN_GUARDRAIL_NOTE,
    write_evidence_quality_plan,
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
        "dimension_count": len(report.get("evidence_dimensions") or []),
        "future_verdict_count": len(report.get("future_verdicts") or []),
        "future_score_field_count": len(report.get("future_score_fields") or []),
        "supported_artifact_type_count": len(report.get("supported_artifact_types") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_evidence_quality_plan(
    *,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create EVAL.N1 plan artifacts and return paths plus summary data."""
    result = write_evidence_quality_plan(output_dir=output_dir)
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("EVAL.N1 - Evidence Quality Plan")
    print("=" * 35)
    print(f"Plan status     : {summary['plan_status']}")
    print(f"Dimensions      : {summary['dimension_count']}")
    print(f"Future verdicts : {summary['future_verdict_count']}")
    print(f"Score fields    : {summary['future_score_field_count']}")
    print(f"Recommended next: {summary['recommended_next_phase']}")
    print(f"JSON            : {summary['json_path']}")
    print(f"Markdown        : {summary['md_path']}")
    print(f"\n> {EVIDENCE_QUALITY_PLAN_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "EVAL.N1: write a report-only evidence quality plan. This grants no "
            "validation, benchmark, model-call, patch, worker, MCP, scoring-gate, "
            "or approval authority."
        )
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_evidence_quality_plan(output_dir=args.output_dir)
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
