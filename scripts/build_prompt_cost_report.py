"""CLI wrapper for Phase 5.7 — Prompt-Version & Cost Quantifier.

Reads ``<repo-path>/.agent/benchmarks/benchmark_report_*.json`` and writes a
single grouped report under ``<repo-path>/.agent/benchmarks/prompt_cost/``.
Never runs a benchmark, never calls a model, never executes a patch, and never
touches the source benchmark report files.

Examples::

    python scripts/build_prompt_cost_report.py
    python scripts/build_prompt_cost_report.py --output-md
    python scripts/build_prompt_cost_report.py --repo-path /path/to/repo
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.prompt_cost_quantifier import (  # noqa: E402  (path bootstrap above)
    PROMPT_COST_SUBDIR,
    write_prompt_cost_files,
)


def _benchmark_root(repo_path: str) -> Path:
    return Path(repo_path).resolve() / ".agent" / "benchmarks"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Group benchmark reports by prompt/config hash and emit a "
            "read-only Prompt / Cost Quantifier report. No benchmarks are "
            "executed and no models are called."
        )
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Path to the repo whose .agent/benchmarks/ should be read.",
    )
    parser.add_argument(
        "--output-json",
        dest="output_json",
        action="store_true",
        default=True,
        help="Write prompt_cost_report.json (default: on).",
    )
    parser.add_argument(
        "--no-output-json",
        dest="output_json",
        action="store_false",
        help="Skip the JSON file (only meaningful with --output-md).",
    )
    parser.add_argument(
        "--output-md",
        action="store_true",
        help="Also write prompt_cost_report.md next to the JSON.",
    )
    args = parser.parse_args(argv)

    benchmark_root = _benchmark_root(args.repo_path)
    written = write_prompt_cost_files(
        benchmark_root,
        output_json=args.output_json,
        output_md=args.output_md,
    )
    report = written["report"]
    out_dir = written["output_dir"]

    print(
        f"Built prompt/cost report from {benchmark_root} "
        f"({report['summary']['group_count']} group(s) over "
        f"{report['summary']['report_count']} report(s))"
    )
    print(f"Output dir: {out_dir} (subdir: {PROMPT_COST_SUBDIR})")
    for label, path in written["paths"].items():
        print(f"{label.upper()}: {path}")

    if report["summary"]["skipped_count"]:
        for entry in report["skipped_reports"]:
            print(f"Warning: skipped {entry['report']} ({entry['reason']})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
