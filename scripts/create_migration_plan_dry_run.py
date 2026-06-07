from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[1])
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from core.project_migration_planner import write_migration_plan_dry_run_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a read-only Project Evolution migration plan dry run.",
    )
    parser.add_argument(
        "--repo-path",
        required=True,
        help="Repository root to scan.",
    )
    parser.add_argument(
        "--goal",
        required=True,
        help="Migration goal string used to steer the dry run.",
    )
    parser.add_argument(
        "--constraints",
        action="append",
        default=None,
        help="Optional constraint. Repeat the flag to add more constraints.",
    )
    parser.add_argument(
        "--risk-tolerance",
        default=None,
        help="Optional risk tolerance note.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=12,
        help="Cap for likely affected and full-file-read selections.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = write_migration_plan_dry_run_artifacts(
        repo_path=args.repo_path,
        goal=args.goal,
        constraints=args.constraints,
        risk_tolerance=args.risk_tolerance,
        max_files=args.max_files,
    )
    print(f"json_path: {result['json_path']}")
    print(f"md_path: {result['md_path']}")
    print(f"likely_affected_files: {len(result['record']['likely_affected_files'])}")
    if result["record"]["status"] != "ok":
        print(f"error: {result['record']['error']['message']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
