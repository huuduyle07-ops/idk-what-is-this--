#!/usr/bin/env python
"""Phase A.11 — Proposal/Lesson Entry Consolidation Plan CLI.

Produces a static consolidation plan for the Proposal → Lesson candidate
creation pathways. Plan-only: no lesson writes, no source mutations,
no model calls, no subprocess calls, no web behavior changes.

Artifacts are written to:
    .agent/audits/<timestamp>_proposal-lesson-consolidation-plan.json
    .agent/audits/<timestamp>_proposal-lesson-consolidation-plan.md

Example:
    python scripts/create_proposal_lesson_consolidation_plan.py --repo-path .
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
            "Build a static consolidation plan for Proposal → Lesson candidate creation paths. "
            "Plan-only: no lesson writes, no source mutations, no runtime behavior changes."
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
        help="Directory where plan artifacts are written. Default: .agent/audits/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the plan but do not write artifact files.",
    )
    args = parser.parse_args(argv)

    from core.proposal_lesson_consolidation_plan import build_plan, write_artifacts

    try:
        plan = build_plan(repo_path=args.repo_path)
    except Exception as e:
        print(
            f"[consolidation_plan] error building plan: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    header = plan["header"]
    ct = plan["canonical_target"]
    phases = plan["future_phases"]
    print("[consolidation_plan] Plan built:")
    print(f"  Plan: {header['plan_name']}")
    print(f"  Status: {header['status']}")
    print(f"  Proposal entries: {len(plan['proposal_entry_map'])}")
    print(f"  Canonical target: {ct['function']} in {ct['file']}")
    print(f"  Delegate paths: {ct['delegate_ids']}")
    print(f"  Future phases: {[p['phase'] for p in phases]}")
    print(f"  Safety invariants: {len(plan['safety_invariants'])}")
    print(f"  Acceptance criteria (A.12): {len(plan['acceptance_criteria_a12'])}")

    if args.dry_run:
        print("[consolidation_plan] --dry-run: skipping artifact write.")
        return 0

    try:
        paths = write_artifacts(plan, audits_root=args.audits_root)
    except Exception as e:
        print(
            f"[consolidation_plan] error writing artifacts: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    print(f"[consolidation_plan] JSON:     {paths['json']}")
    print(f"[consolidation_plan] Markdown: {paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
