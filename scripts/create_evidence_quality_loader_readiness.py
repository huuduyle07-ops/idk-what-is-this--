"""EVAL.N7 - Create an Evidence Quality Loader Readiness Check (CLI).

Writes readiness JSON/Markdown artifacts only. It does not generate evidence
quality reports, run validation or benchmarks, call models, apply patches,
approve/reject work, mutate reports, or alter Submit/Apply behavior.
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

from core.evidence_quality_loader_readiness import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    GUARDRAIL_NOTE,
    write_evidence_quality_loader_readiness,
)


DEFAULT_OUTPUT_DIR = str(DEFAULT_OUTPUT_ROOT)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") or {}
    summary = report.get("summary") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "readiness_status": report.get("readiness_status"),
        "panel_ready": bool(summary.get("panel_ready")),
        "loader_ready": bool(summary.get("loader_ready")),
        "compatible_report_loaded": bool(summary.get("compatible_report_loaded")),
        "warning_count": int(summary.get("warning_count") or 0),
        "blocked_reason_count": int(summary.get("blocked_reason_count") or 0),
        "incomplete_reason_count": int(summary.get("incomplete_reason_count") or 0),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_evidence_quality_loader_readiness(
    *,
    report: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    repo_root: str | Path = PROJECT_ROOT,
    created_at: str = "",
) -> dict[str, Any]:
    """Create EVAL.N7 readiness artifacts and return paths plus summary."""
    result = write_evidence_quality_loader_readiness(
        repo_root=repo_root,
        report_path=report,
        output_dir=output_dir,
        created_at=created_at,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("EVAL.N7 - Evidence Quality Loader Readiness Check")
    print("=" * 55)
    print(f"Readiness status : {summary['readiness_status']}")
    print(f"Panel ready      : {summary['panel_ready']}")
    print(f"Loader ready     : {summary['loader_ready']}")
    print(f"Report compatible: {summary['compatible_report_loaded']}")
    print(f"Warnings         : {summary['warning_count']}")
    print(f"Blocked reasons  : {summary['blocked_reason_count']}")
    print(f"Incomplete items : {summary['incomplete_reason_count']}")
    print(f"Recommended next : {summary['recommended_next_phase']}")
    print(f"JSON             : {summary['json_path']}")
    print(f"Markdown         : {summary['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "EVAL.N7: write a report-only readiness checkpoint for the read-only "
            "Evidence Quality panel and GET-only artifact loader. This performs "
            "source/artifact inspection only."
        )
    )
    parser.add_argument("--report", help="Optional existing EVAL.N3 evidence_quality_report.json path.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT))
    parser.add_argument("--created-at", default="")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_evidence_quality_loader_readiness(
        report=args.report,
        output_dir=args.output_dir,
        repo_root=args.repo_root,
        created_at=args.created_at,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
