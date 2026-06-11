#!/usr/bin/env python
"""Phase A.10 — Proposal/Lesson Entry Dedup Audit CLI.

Produces a static deterministic audit report of every lesson candidate
creation entry point. Report-only: no lesson writes, no source mutations,
no model calls, no subprocess calls, no web behavior changes.

Artifacts are written to:
    .agent/audits/<timestamp>_lesson-entry-dedup-audit.json
    .agent/audits/<timestamp>_lesson-entry-dedup-audit.md

Example:
    python scripts/create_lesson_entry_audit.py --repo-path .
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_AUDITS_ROOT = PROJECT_ROOT / ".agent" / "audits"


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a static report of all lesson candidate creation entry points. "
            "Report-only: no lesson writes, no source mutations."
        ),
    )
    parser.add_argument(
        "--repo-path",
        default=str(PROJECT_ROOT),
        help=(
            "Repo root for file-existence validation. "
            "Defaults to the project root derived from this script's location."
        ),
    )
    parser.add_argument(
        "--audits-root",
        default=str(DEFAULT_AUDITS_ROOT),
        help="Directory where audit artifacts are written. Default: .agent/audits/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the report but do not write artifact files.",
    )
    args = parser.parse_args(argv)

    from core.lesson_entry_audit import build_report, write_artifacts

    try:
        report = build_report(repo_path=args.repo_path)
    except Exception as e:
        print(f"[lesson_entry_audit] error building report: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    summary = report["summary"]
    print("[lesson_entry_audit] Report built:")
    print(f"  Total entrypoints: {summary['total_entrypoints']}")
    print(f"  Proposal to candidate: {summary['proposal_to_candidate']}")
    print(f"  Dream to candidate: {summary['dream_to_candidate']}")
    print(f"  Benchmark to candidate: {summary['benchmark_to_candidate']}")
    print(f"  Anti-lesson: {summary['anti_lesson']}")
    print(f"  Merge: {summary['merge']}")
    print(f"  Other: {summary['other']}")
    print(f"  Duplicate-risk count: {summary['duplicate_risk_count']}")
    print(f"  Recommendations: {len(report['recommendations'])}")

    if args.dry_run:
        print("[lesson_entry_audit] --dry-run: skipping artifact write.")
        return 0

    try:
        paths = write_artifacts(report, audits_root=args.audits_root)
    except Exception as e:
        print(f"[lesson_entry_audit] error writing artifacts: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(f"[lesson_entry_audit] JSON:     {paths['json']}")
    print(f"[lesson_entry_audit] Markdown: {paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
