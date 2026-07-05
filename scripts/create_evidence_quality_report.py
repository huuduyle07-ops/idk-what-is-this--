"""EVAL.N3 - Create an Evidence Quality Report (CLI).

Reads only explicitly supplied existing artifacts and writes advisory
JSON/Markdown report artifacts. It does not run validation, benchmarks, models,
patch application, MCP tools, workers, networks, databases, scoring gates, or
approval/rejection logic.
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

from core.evidence_quality_report_builder import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    EVIDENCE_QUALITY_REPORT_GUARDRAIL_NOTE,
    write_evidence_quality_report,
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
        "evidence_quality_status": report.get("evidence_quality_status"),
        "overall_evidence_quality": report.get("overall_evidence_quality"),
        "source_artifact_count": len(report.get("source_artifacts") or []),
        "artifact_inventory_count": len(report.get("artifact_inventory") or []),
        "claim_count": len(report.get("claim_inventory") or []),
        "evidence_item_count": len(report.get("evidence_inventory") or []),
        "dimension_count": len(report.get("dimension_reviews") or []),
        "recommended_human_check_count": len(report.get("recommended_human_checks") or []),
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_evidence_quality_report(
    *,
    patch: str | None = None,
    diff: str | None = None,
    validation: str | None = None,
    benchmark: str | None = None,
    final_answer: str | None = None,
    mirror_preview: str | None = None,
    commander_review: str | None = None,
    evidence_pack: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    repo_root: str | Path | None = None,
    report_id: str = "evidence-quality-report",
) -> dict[str, Any]:
    """Create EVAL.N3 report artifacts and return paths plus summary."""
    result = write_evidence_quality_report(
        output_dir=output_dir,
        patch=patch,
        diff=diff,
        validation=validation,
        benchmark=benchmark,
        final_answer=final_answer,
        mirror_preview=mirror_preview,
        commander_review=commander_review,
        evidence_pack=evidence_pack,
        repo_root=repo_root,
        report_id=report_id,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("EVAL.N3 - Evidence Quality Report")
    print("=" * 35)
    print(f"Report status   : {summary['evidence_quality_status']}")
    print(f"Overall quality : {summary['overall_evidence_quality']}")
    print(f"Source artifacts: {summary['source_artifact_count']}")
    print(f"Claims          : {summary['claim_count']}")
    print(f"Evidence items  : {summary['evidence_item_count']}")
    print(f"Warnings        : {summary['warning_count']}")
    print(f"Blocked reasons : {summary['blocked_reason_count']}")
    print(f"Recommended next: {summary['recommended_next_phase']}")
    print(f"JSON            : {summary['json_path']}")
    print(f"Markdown        : {summary['md_path']}")
    print(f"\n> {EVIDENCE_QUALITY_REPORT_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "EVAL.N3: write a report-only evidence quality report from explicitly "
            "supplied existing artifacts. This grants no validation, benchmark, "
            "model-call, patch, worker, MCP, scoring-gate, or approval authority."
        )
    )
    parser.add_argument("--patch", help="Existing patch proposal/diff artifact.")
    parser.add_argument("--diff", help="Existing diff text artifact.")
    parser.add_argument("--validation", help="Existing validation result artifact/text.")
    parser.add_argument("--benchmark", help="Existing benchmark result artifact/text.")
    parser.add_argument("--final-answer", help="Existing final answer text.")
    parser.add_argument("--mirror-preview", help="Existing MIRROR.8 live trace scoring preview JSON.")
    parser.add_argument("--commander-review", help="Existing CMD.N6 assignment review pack JSON.")
    parser.add_argument("--evidence-pack", help="Existing evidence pack JSON/MD.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-id", default="evidence-quality-report")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_evidence_quality_report(
        patch=args.patch,
        diff=args.diff,
        validation=args.validation,
        benchmark=args.benchmark,
        final_answer=args.final_answer,
        mirror_preview=args.mirror_preview,
        commander_review=args.commander_review,
        evidence_pack=args.evidence_pack,
        output_dir=args.output_dir,
        repo_root=PROJECT_ROOT,
        report_id=args.report_id,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
