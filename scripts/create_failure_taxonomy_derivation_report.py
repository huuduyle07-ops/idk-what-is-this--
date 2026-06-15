"""Phase 14.5 — Create failure taxonomy data-derivation report.

Scans existing project artifacts (.agent/benchmarks, lessons, dreams,
proposals, workers) and writes a read-only derivation report to
.agent/audits/. Does not change any runtime behavior: no patches, no
lessons, no scoring, no model calls, no database writes, no subprocess.

Usage:
    python scripts/create_failure_taxonomy_derivation_report.py --repo-path .
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.failure_taxonomy_derivation import (  # noqa: E402
    DERIVATION_GUARDRAIL_NOTE,
    derive_taxonomy_report,
    render_derivation_markdown,
)

DEFAULT_OUTPUT_DIR = ".agent/audits"


def run_derivation(
    *,
    repo_path: str = ".",
    output_dir: str = DEFAULT_OUTPUT_DIR,
    generated_at: float,
) -> dict[str, Any]:
    """Derive taxonomy from artifacts and write report artifacts.

    Returns a result dict with ``ok``, ``json_path``, ``md_path``, ``report``.
    Never raises for expected failure modes.
    """
    report = derive_taxonomy_report(repo_path=repo_path)
    report["generated_at"] = datetime.fromtimestamp(
        generated_at, tz=timezone.utc
    ).isoformat()
    report["generated_at_epoch"] = generated_at
    report["repo_path"] = str(Path(repo_path).resolve())

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.fromtimestamp(generated_at, tz=timezone.utc).strftime(
        "%Y%m%d_%H%M%S"
    )
    json_path = out_dir / f"{stamp}_failure-taxonomy-derivation.json"
    md_path = out_dir / f"{stamp}_failure-taxonomy-derivation.md"

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path.write_text(render_derivation_markdown(report), encoding="utf-8")

    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 14.5: derive failure taxonomy from existing project artifacts "
            "and write a read-only report to .agent/audits/. "
            "Does not modify any artifact, scoring, patching, validation, "
            "lesson promotion, retrieval, or runtime behavior."
        )
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Repo root to scan (default: .).",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for report artifacts (default: {DEFAULT_OUTPUT_DIR}).",
    )
    args = parser.parse_args(argv)

    result = run_derivation(
        repo_path=args.repo_path,
        output_dir=args.output_dir,
        generated_at=datetime.now(tz=timezone.utc).timestamp(),
    )

    report = result["report"]
    summary = report.get("summary") or {}

    print("Phase 14.5 — Failure Taxonomy Data-Derivation Report")
    print("=" * 52)
    print(f"Benchmark reports scanned : {summary.get('total_benchmark_reports_scanned', 0)}")
    print(f"Cases scanned             : {summary.get('total_cases_scanned', 0)}")
    print(f"Failing cases classified  : {summary.get('total_failing_cases_classified', 0)}")
    print(f"Lesson records scanned    : {summary.get('total_lesson_records_scanned', 0)}")
    print(f"Anti-lesson records       : {summary.get('total_anti_lesson_records_scanned', 0)}")
    print(f"Dream artifacts scanned   : {summary.get('total_dream_artifacts_scanned', 0)}")
    print(f"Proposal artifacts scanned: {summary.get('total_proposal_artifacts_scanned', 0)}")
    print(f"Categories proposed       : {summary.get('candidate_categories_proposed', 0)}")
    print(f"Categories with matches   : {summary.get('categories_with_matches', 0)}")
    print(f"Unmapped cases            : {summary.get('unmapped_case_count', 0)}")

    counts = report.get("counts_by_category") or {}
    if counts:
        print("\nCounts by category:")
        for cat, count in counts.items():
            print(f"  {cat}: {count}")

    recs = report.get("recommendations") or []
    if recs:
        print("\nRecommendations:")
        for rec in recs:
            print(f"  {rec.get('phase', '')}: {rec.get('action', '')[:80]}...")

    print(f"\nJSON:     {result['json_path']}")
    print(f"Markdown: {result['md_path']}")
    print(f"\n> {DERIVATION_GUARDRAIL_NOTE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
