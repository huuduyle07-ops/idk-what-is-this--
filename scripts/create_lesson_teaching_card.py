#!/usr/bin/env python
"""Create an inert Lesson Teaching Card / Teacher Mode artifact (F.6).

Reads one existing lesson-like JSON artifact and writes local teaching-card
JSON/Markdown. It never calls models, promotes lessons, creates anti-lessons,
applies patches, runs validation, launches workers, triggers Dream, runs
Project Evolution, or calls webhooks/network.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.lesson_teaching_card import (  # noqa: E402
    create_lesson_teaching_card,
    render_lesson_teaching_card_json,
    render_lesson_teaching_card_text,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create an inert Lesson Teaching Card from an existing artifact.",
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Repository root for the teaching card artifact.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--lesson", default="", help="Path to a lesson JSON artifact.")
    source.add_argument("--anti-lesson", default="", help="Path to an anti-lesson JSON artifact.")
    source.add_argument("--benchmark-case", default="", help="Path to a benchmark case JSON artifact.")
    source.add_argument("--failure-report", default="", help="Path to a failure report JSON artifact.")
    parser.add_argument(
        "--output-root",
        default="",
        help="Optional teaching-card root. Defaults to .agent/teaching_cards/.",
    )
    parser.add_argument(
        "--teaching-card-id",
        default="",
        help="Optional stable teaching card id for smoke tests or reruns.",
    )
    parser.add_argument(
        "--created-at",
        default="",
        help="Optional ISO timestamp for deterministic JSON output.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show the card without writing files.")
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = create_lesson_teaching_card(
        repo_path=args.repo_path,
        lesson_path=args.lesson or None,
        anti_lesson_path=args.anti_lesson or None,
        benchmark_case_path=args.benchmark_case or None,
        failure_report_path=args.failure_report or None,
        dry_run=args.dry_run,
        output_root=args.output_root or None,
        teaching_card_id=args.teaching_card_id or None,
        created_at=args.created_at or None,
    )

    if args.json:
        print(render_lesson_teaching_card_json(result), end="")
    elif result.get("ok"):
        print(render_lesson_teaching_card_text(result), end="")
    else:
        print(render_lesson_teaching_card_text(result), end="", file=sys.stderr)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
