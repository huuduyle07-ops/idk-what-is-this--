"""Phase 14.5a — Create unknown failure category review report.

Reads the latest (or an explicit) Phase 14.5 failure taxonomy derivation
artifact, reviews unknown/unmapped cases, and writes a read-only report
to .agent/audits/. Does not change any runtime behavior.

Usage:
    python scripts/create_failure_unknown_review.py --repo-path .
    python scripts/create_failure_unknown_review.py --repo-path . \\
        --taxonomy-report .agent/audits/<file>.json
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

from core.failure_unknown_review import (  # noqa: E402
    UNKNOWN_REVIEW_GUARDRAIL_NOTE,
    build_unknown_review,
    build_unknown_review_from_empty,
    find_latest_derivation_artifact,
    load_derivation_artifact,
    render_unknown_review_markdown,
)

DEFAULT_OUTPUT_DIR = ".agent/audits"


def run_review(
    *,
    repo_path: str = ".",
    taxonomy_report: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    generated_at: float,
) -> dict[str, Any]:
    """Locate derivation artifact, build review, write artifacts.

    Returns a result dict with ``ok``, ``json_path``, ``md_path``, ``review``.
    On missing input, returns ``ok=True`` with an empty review (exit-0 style).
    """
    # Resolve the derivation artifact path
    if taxonomy_report:
        artifact_path: Path | None = Path(taxonomy_report)
        if not artifact_path.exists():
            return {
                "ok": False,
                "error": f"taxonomy report not found: {taxonomy_report}",
                "json_path": None,
                "md_path": None,
            }
    else:
        artifact_path = find_latest_derivation_artifact(repo_path)

    # Load (or produce empty review on missing artifact)
    if artifact_path is None:
        review = build_unknown_review_from_empty()
        source_label = "(no artifact found)"
    else:
        derivation = load_derivation_artifact(artifact_path)
        if derivation is None:
            review = build_unknown_review_from_empty()
            source_label = f"(could not load: {artifact_path})"
        else:
            review = build_unknown_review(derivation, source_path=str(artifact_path))
            source_label = str(artifact_path)

    review["generated_at"] = datetime.fromtimestamp(
        generated_at, tz=timezone.utc
    ).isoformat()
    review["generated_at_epoch"] = generated_at
    review["repo_path"] = str(Path(repo_path).resolve())

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.fromtimestamp(generated_at, tz=timezone.utc).strftime(
        "%Y%m%d_%H%M%S"
    )
    json_path = out_dir / f"{stamp}_failure-unknown-review.json"
    md_path = out_dir / f"{stamp}_failure-unknown-review.md"

    json_path.write_text(
        json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path.write_text(render_unknown_review_markdown(review), encoding="utf-8")

    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "review": review,
        "source": source_label,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 14.5a: review unknown/unmapped failing cases from a "
            "Phase 14.5 failure taxonomy derivation artifact. Writes a "
            "read-only report to .agent/audits/. Does not change any "
            "runtime behavior."
        )
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Repo root to locate the latest derivation artifact (default: .).",
    )
    parser.add_argument(
        "--taxonomy-report",
        default=None,
        help="Explicit path to a *_failure-taxonomy-derivation.json artifact.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for report artifacts (default: {DEFAULT_OUTPUT_DIR}).",
    )
    args = parser.parse_args(argv)

    result = run_review(
        repo_path=args.repo_path,
        taxonomy_report=args.taxonomy_report,
        output_dir=args.output_dir,
        generated_at=datetime.now(tz=timezone.utc).timestamp(),
    )

    if not result["ok"]:
        print(f"Error: {result.get('error', 'unknown error')}")
        return 1

    review = result["review"]
    summary = review.get("summary") or {}
    source = result.get("source", "")

    print("Phase 14.5a — Unknown Failure Category Review")
    print("=" * 48)
    if review.get("no_input"):
        print("No Phase 14.5 derivation artifact found.")
        print("Run create_failure_taxonomy_derivation_report.py first.")
    else:
        print(f"Source derivation: {source}")
        print(f"Unknown cases reviewed     : {summary.get('total_unknown_cases_reviewed', 0)}")
        outcome_counts = summary.get("outcome_counts") or {}
        for oc, count in outcome_counts.items():
            if count:
                print(f"  {oc}: {count}")
        print(f"Can map to existing cat    : {summary.get('can_map_to_existing_category', 0)}")
        print(f"Need new category          : {summary.get('need_new_category', 0)}")
        print(f"Leave unknown              : {summary.get('leave_unknown', 0)}")
        print(f"Need better evidence       : {summary.get('need_better_evidence', 0)}")
        print(f"Suggested rules            : {summary.get('suggested_rule_count', 0)}")
        print(f"Proposed new categories    : {summary.get('proposed_new_category_count', 0)}")
        print(f"Phase 14.6 readiness       : {summary.get('phase_14_6_readiness', 'not_ready')}")

    print(f"\nJSON:     {result['json_path']}")
    print(f"Markdown: {result['md_path']}")
    print(f"\n> {UNKNOWN_REVIEW_GUARDRAIL_NOTE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
