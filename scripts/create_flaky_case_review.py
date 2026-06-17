"""A.17 — Create a Flaky Case Review report (report-only).

Reads an existing benchmark report JSON (written by the benchmark runner into
``.agent/benchmarks/``) and writes a deterministic, read-only review artifact
that explains which benchmark cases were flaky, why they may be flaky, and what
the next human action should be.

This script never runs the benchmark suite, never changes benchmark cases,
prompts, patch generation, or validation, never calls a model, applies a patch,
runs validation, runs Dream or Project Evolution, makes network calls, promotes
lessons, imports proposals, or launches workers. It only reads report files and
writes the review artifact.

Usage:
    python scripts/create_flaky_case_review.py --latest
    python scripts/create_flaky_case_review.py \\
        --report .agent/benchmarks/benchmark_report_<ts>.json
    python scripts/create_flaky_case_review.py --latest --json
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

from core.flaky_case_review import (  # noqa: E402
    FLAKY_REVIEW_GUARDRAIL_NOTE,
    build_flaky_case_review,
    build_flaky_case_review_from_empty,
    find_latest_benchmark_report,
    load_benchmark_report,
    render_flaky_case_review_markdown,
)

#: Default location for review artifacts, under the repo's ``.agent`` tree.
DEFAULT_OUTPUT_SUBPATH = Path(".agent") / "reliability" / "flaky_case_reviews"
JSON_NAME = "flaky_case_review.json"
MD_NAME = "flaky_case_review.md"


def _resolve_created_at(raw: str | float | None) -> tuple[str, datetime | None]:
    """Return (iso_string, datetime_or_None) for the created-at hook.

    Accepts an ISO-8601 string (used verbatim), an epoch number, or None
    (uses the current UTC time). The datetime is None when ``raw`` is a literal
    ISO string we did not parse, which is fine — it is only used to derive a
    default review id.
    """
    if raw is None:
        now = datetime.now(tz=timezone.utc)
        return now.isoformat(), now
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw), None
    moment = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return moment.isoformat(), moment


def _default_review_id(iso: str, moment: datetime | None) -> str:
    if moment is not None:
        stamp = moment.strftime("%Y%m%d_%H%M%S")
    else:
        stamp = "".join(ch if ch.isalnum() else "-" for ch in iso).strip("-")[:24]
        stamp = stamp or "review"
    return f"{stamp}_flaky-case-review"


def run_flaky_case_review(
    *,
    repo_path: str = ".",
    report: str | None = None,
    use_latest: bool = False,
    review_id: str | None = None,
    created_at: str | float | None = None,
    output_root: str | None = None,
) -> dict[str, Any]:
    """Locate a benchmark report, build the review, write JSON + Markdown.

    Returns a result dict with ``ok``, ``json_path``, ``md_path``, ``review``,
    and ``source``. On an explicit but missing ``--report`` path, returns
    ``ok=False``. When no report is found (``--latest`` with none present),
    returns ``ok=True`` with an empty ``no_input`` review.
    """
    # Resolve the source report path.
    report_path: Path | None
    if report:
        report_path = Path(report)
        if not report_path.exists():
            return {
                "ok": False,
                "error": f"benchmark report not found: {report}",
                "json_path": None,
                "md_path": None,
            }
    else:
        # No explicit report (or --latest): find the newest report.
        report_path = find_latest_benchmark_report(repo_path)

    # Load and build.
    if report_path is None:
        review = build_flaky_case_review_from_empty(source_report_path=None)
        source_label = "(no benchmark report found)"
    else:
        loaded = load_benchmark_report(report_path)
        if loaded is None:
            review = build_flaky_case_review_from_empty(
                source_report_path=str(report_path)
            )
            source_label = f"(could not load: {report_path})"
        else:
            review = build_flaky_case_review(
                loaded, source_report_path=str(report_path)
            )
            source_label = str(report_path)

    # Deterministic stamping (review id + created-at hooks).
    created_iso, moment = _resolve_created_at(created_at)
    final_review_id = review_id or _default_review_id(created_iso, moment)
    review["review_id"] = final_review_id
    review["created_at"] = created_iso
    review["repo_path"] = str(Path(repo_path).resolve())

    # Resolve the output directory: <output_root>/<review_id>/.
    if output_root:
        base_dir = Path(output_root)
    else:
        base_dir = Path(repo_path) / DEFAULT_OUTPUT_SUBPATH
    out_dir = base_dir / final_review_id
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(
        json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path.write_text(render_flaky_case_review_markdown(review), encoding="utf-8")

    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "review": review,
        "source": source_label,
    }


def _print_summary(result: dict[str, Any]) -> None:
    review = result["review"]
    summary = review.get("summary") or {}
    print("A.17 — Flaky Case Review")
    print("=" * 32)
    if review.get("no_input"):
        print("No benchmark report was found to review.")
    else:
        print(f"Source report      : {result.get('source', '')}")
        print(f"Total cases read   : {summary.get('total_cases_read', 0)}")
        print(f"Flaky cases found  : {summary.get('flaky_cases_found', 0)}")
        print(f"High-confidence    : {summary.get('high_confidence_count', 0)}")
        print(f"Low-confidence     : {summary.get('low_confidence_count', 0)}")
        present = [
            (category, count)
            for category, count in (summary.get("category_counts") or {}).items()
            if count
        ]
        for category, count in present:
            print(f"  {category}: {count}")
        top = summary.get("top_recommended_actions") or []
        if top:
            print("Top recommended actions:")
            for item in top:
                print(f"  {item.get('action')}: {item.get('count')}")
    print(f"\nReview id : {review.get('review_id')}")
    print(f"JSON      : {result['json_path']}")
    print(f"Markdown  : {result['md_path']}")
    print(f"\n> {FLAKY_REVIEW_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "A.17: read an existing benchmark report and write a deterministic, "
            "report-only flaky case review artifact. Does not run benchmarks, "
            "change cases, call models, apply patches, or run validation."
        )
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Explicit benchmark report JSON to review.",
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Repo root (used to locate reports and write artifacts; default: .).",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Find the latest benchmark report in .agent/benchmarks/.",
    )
    parser.add_argument(
        "--review-id",
        default=None,
        help="Deterministic review id (also the artifact folder name).",
    )
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help=(
            "Override the artifact root "
            "(default: <repo-path>/.agent/reliability/flaky_case_reviews)."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the review JSON summary to stdout.",
    )
    args = parser.parse_args(argv)

    result = run_flaky_case_review(
        repo_path=args.repo_path,
        report=args.report,
        use_latest=args.latest,
        review_id=args.review_id,
        created_at=args.created_at,
        output_root=args.output_root,
    )

    if not result["ok"]:
        print(f"Error: {result.get('error', 'unknown error')}")
        return 1

    if args.json:
        print(json.dumps(result["review"], indent=2, ensure_ascii=False))
    else:
        _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
