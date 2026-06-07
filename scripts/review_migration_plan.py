from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[1])
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from core.project_evolution_approval import write_project_evolution_approval_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record a manual approval decision for a Project Evolution migration plan.",
    )
    parser.add_argument(
        "--source-plan-path",
        required=True,
        help="Path to .agent/project_evolution/migration_plan_dry_run.json.",
    )
    parser.add_argument(
        "--decision",
        required=True,
        help="Operator decision: approve, reject, or needs_revision.",
    )
    parser.add_argument(
        "--reviewer",
        default=None,
        help="Optional reviewer name or label.",
    )
    parser.add_argument(
        "--notes",
        default=None,
        help="Optional reviewer notes.",
    )
    parser.add_argument(
        "--approved-scope",
        action="append",
        default=None,
        help="Optional approved scope entry. Repeat the flag to add more items.",
    )
    parser.add_argument(
        "--blocked-scope",
        action="append",
        default=None,
        help="Optional blocked scope entry. Repeat the flag to add more items.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = write_project_evolution_approval_artifacts(
            source_plan_path=args.source_plan_path,
            decision=args.decision,
            reviewer=args.reviewer,
            notes=args.notes,
            approved_scope=args.approved_scope,
            blocked_scope=args.blocked_scope,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"json_path: {result['json_path']}")
    print(f"md_path: {result['md_path']}")
    print(f"source_plan_hash: {result['record'].get('source_plan_hash', '')}")
    print(f"patch_generation_allowed: {result['record'].get('patch_generation_allowed', False)}")
    if result["record"].get("status") != "ok":
        print(f"error: {result['record']['error']['message']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
