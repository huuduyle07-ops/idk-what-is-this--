#!/usr/bin/env python
"""Phase 6.4e: explicit operator action to create a repo-scoped lesson CANDIDATE
from a single proposal or Dream artifact.

This is the controlled trigger for "auto candidate creation": nothing happens
unless this CLI is run (it passes enabled=True to core.lesson_auto_candidates).
It never promotes a lesson to active, never runs benchmarks / models / patch
executors / validation, never executes Dream runs, and never mutates the source
artifacts. Candidates are created only through the existing
lesson_store / lesson_quality path.

Examples:
    python scripts/create_lesson_candidate.py \\
        --proposal-dir .agent/proposals/20260601_120000/01-python-discount \\
        --repo-path /path/to/repo

    python scripts/create_lesson_candidate.py \\
        --dream-item-dir .agent/<tag>/dreams/2026-06-01/120000-run/01-fix \\
        --repo-path /path/to/repo
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Create a lesson candidate from a proposal or Dream artifact.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--proposal-dir", help="Path to .agent/proposals/<run>/<item>/.")
    source.add_argument("--dream-item-dir", help="Path to a Dream ready_to_apply item dir.")
    parser.add_argument(
        "--repo-path",
        default=None,
        help="Analyzed repo path. When provided, the candidate is repo-scoped by default.",
    )
    parser.add_argument(
        "--global-candidate",
        action="store_true",
        help="SCARY: create a global candidate instead of a repo-scoped one. Still never promotes.",
    )
    parser.add_argument(
        "--include-failed",
        action="store_true",
        help="Include failed apply/validation evidence; lesson_quality must gate it.",
    )
    args = parser.parse_args(argv)

    from core.lesson_auto_candidates import (
        maybe_create_lesson_candidate_from_dream_item,
        maybe_create_lesson_candidate_from_proposal,
    )

    try:
        if args.proposal_dir:
            result = maybe_create_lesson_candidate_from_proposal(
                args.proposal_dir,
                repo_path=args.repo_path,
                enabled=True,
                global_candidate=args.global_candidate,
                include_failed=args.include_failed,
            )
        else:
            result = maybe_create_lesson_candidate_from_dream_item(
                args.dream_item_dir,
                repo_path=args.repo_path,
                enabled=True,
                global_candidate=args.global_candidate,
                include_failed=args.include_failed,
            )
    except Exception as e:  # defensive: surface as friendly JSON, never a traceback
        print(
            json.dumps(
                {"status": "error", "reason": f"{type(e).__name__}: {e}"},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    # created / blocked / duplicate / skipped / disabled are all "handled"
    # outcomes; only an unexpected error returns non-zero.
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
