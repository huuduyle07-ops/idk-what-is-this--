#!/usr/bin/env python
"""Create a draft-only Worker Assignment / Route Card.

This CLI writes inert route-card artifacts only. It never launches a worker,
calls models, applies patches, runs validation, starts Dream, runs Project
Evolution execution, calls webhooks, or promotes lessons.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.worker_assignment import (  # noqa: E402
    create_worker_assignment,
    render_worker_assignment_json,
    render_worker_assignment_text,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create an inert Worker Assignment / Route Card draft.",
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Repository root for the worker route card.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--goal-brief", default="", help="Path to goal_brief.json or its directory.")
    source.add_argument("--handoff", default="", help="Path to a handoff note or handoff draft JSON.")
    source.add_argument("--seed-draft", default="", help="Path to an External Queue export seed draft JSON.")
    source.add_argument("--review-pack", default="", help="Path to a Review Pack draft JSON.")
    parser.add_argument(
        "--mode",
        default="debug",
        choices=["debug", "project-evolution", "project_evolution", "dream-trial", "dream_trial", "documentation", "review-only", "review_only"],
        help="Selected worker mode.",
    )
    parser.add_argument(
        "--role",
        default="implementer",
        choices=["implementer", "reviewer", "skeptic", "documenter", "researcher"],
        help="Worker role for the route card.",
    )
    parser.add_argument("--allowed-file", action="append", default=[], help="Extra allowed file.")
    parser.add_argument("--forbidden-file", action="append", default=[], help="Extra forbidden file.")
    parser.add_argument("--validation-command", action="append", default=[], help="Extra validation command to preserve.")
    parser.add_argument(
        "--output-root",
        default="",
        help="Optional worker assignment root. Defaults to .agent/worker_assignments/.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show the draft without writing files.")
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = create_worker_assignment(
        repo_path=args.repo_path,
        goal_brief_path=args.goal_brief or None,
        handoff_path=args.handoff or None,
        seed_draft_path=args.seed_draft or None,
        review_pack_path=args.review_pack or None,
        mode=args.mode,
        worker_role=args.role,
        allowed_files=args.allowed_file,
        forbidden_files=args.forbidden_file,
        validation_commands=args.validation_command,
        dry_run=args.dry_run,
        output_root=args.output_root,
    )

    if args.json:
        print(render_worker_assignment_json(result), end="")
    elif result.get("ok"):
        print(render_worker_assignment_text(result), end="")
    else:
        print(render_worker_assignment_text(result), end="", file=sys.stderr)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
