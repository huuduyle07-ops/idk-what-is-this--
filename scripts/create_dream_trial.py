#!/usr/bin/env python
"""Phase 4.7b — CLI for creating a structured dream-trial report.

Writes the seven structured markdown files + trial.json into
.agent/dream_trials/<trial_id>/. Report-only: no patches, no commits, no
model calls.

Examples
--------
  python scripts/create_dream_trial.py \\
      --repo /path/to/repo \\
      --dream-type idea_trial \\
      --action-level report_only \\
      --title "Try X as a tiny experiment" \\
      --hint "see notes" \\
      --notes "..."
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from anywhere by stitching the project root onto sys.path.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core import dream_trials  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Create a structured dream-trial report (Phase 4.7b, report-only).",
    )
    p.add_argument("--repo", required=True, help="Path to the analyzed repo.")
    p.add_argument(
        "--dream-type",
        required=True,
        help=(
            "Work type. Must be one of: "
            "idea_trial, research_study, reference_study, case_idea_research."
        ),
    )
    p.add_argument(
        "--action-level",
        default="report_only",
        help="Action level. Phase 4.7b is report-only.",
    )
    p.add_argument("--title", required=True, help="Idea / trial title.")
    p.add_argument("--hint", default="", help="Optional hint.")
    p.add_argument("--notes", default="", help="Optional reference notes (pasted text).")
    p.add_argument(
        "--markdown-file",
        action="append",
        dest="markdown_files",
        default=[],
        help="Reference markdown file path (may be repeated).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = dream_trials.create_structured_dream_trial(
            repo_path=args.repo,
            dream_type=args.dream_type,
            action_level=args.action_level,
            title=args.title,
            hint=args.hint,
            reference_notes=args.notes,
            markdown_files=args.markdown_files,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(f"Trial written: {result.trial_dir}")
    print(f"Decision: {result.decision}")
    print(f"Allowed actions: {', '.join(result.allowed_actions)}")
    print(f"Blocked actions: {', '.join(result.blocked_actions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
