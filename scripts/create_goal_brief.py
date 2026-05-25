#!/usr/bin/env python
"""Create or update a GoalBrief artifact.

This CLI only writes GoalBrief JSON/Markdown artifacts. It never runs terminal
commands, applies patches, or mutates proposal artifacts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import goal_brief


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a structured GoalBrief.")
    parser.add_argument("--goal", default="", help="Vague goal to turn into a task brief.")
    parser.add_argument("--repo-path", default=None, help="Optional target repository path.")
    parser.add_argument("--answer", default="", help="Manual answer or pasted terminal result.")
    parser.add_argument("--brief-ref", default="", help="Existing goal_brief.json or brief directory.")
    parser.add_argument("--export-md", action="store_true", help="Also write goal_brief.md.")
    parser.add_argument("--dry-run", action="store_true", help="Print the result without writing files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.brief_ref:
            result = goal_brief.update_goal_brief(
                args.brief_ref,
                answer=args.answer,
                repo_path=args.repo_path,
                export_md=args.export_md,
                dry_run=args.dry_run,
            )
        else:
            result = goal_brief.create_goal_brief(
                goal=args.goal,
                repo_path=args.repo_path,
                export_md=args.export_md,
                dry_run=args.dry_run,
            )
            if args.answer:
                if args.dry_run:
                    brief = goal_brief.apply_answer_to_goal_brief(result["brief"], args.answer)
                    brief["updated_at"] = brief["created_at"]
                    result["brief"] = brief
                else:
                    result = goal_brief.update_goal_brief(
                        result["brief_path"],
                        answer=args.answer,
                        repo_path=args.repo_path,
                        export_md=args.export_md,
                    )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
