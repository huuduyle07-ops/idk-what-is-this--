from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[1])
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from core.project_evolution_patch_draft import write_project_evolution_patch_draft_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a read-only Project Evolution patch draft package from an approved plan.",
    )
    parser.add_argument(
        "--repo-path",
        required=True,
        help="Repository root containing .agent/project_evolution artifacts.",
    )
    parser.add_argument(
        "--approval-path",
        required=True,
        help="Path to an approval JSON record under .agent/project_evolution/approvals/.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=12,
        help="Cap for the likely file and file-read selections.",
    )
    parser.add_argument(
        "--draft-title",
        default=None,
        help="Optional human-facing title for the draft package.",
    )
    parser.add_argument(
        "--notes",
        default=None,
        help="Optional notes for the draft package.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = write_project_evolution_patch_draft_artifacts(
        repo_path=args.repo_path,
        approval_path=args.approval_path,
        max_files=args.max_files,
        draft_title=args.draft_title,
        notes=args.notes,
    )
    record = result["record"]
    if record.get("status") != "ok":
        print(f"error: {record['error']['message']}", file=sys.stderr)
        return 1

    print(f"json_path: {result['json_path']}")
    print(f"md_path: {result['md_path']}")
    print(f"approval_hash_or_id: {record['approval_hash_or_id']}")
    print(f"likely_files_to_change: {len(record['likely_files_to_change'])}")
    print(f"patch_generation_allowed: {record['patch_generation_allowed']}")
    print(f"patch_apply_allowed: {record['patch_apply_allowed']}")
    print(f"validation_execution_allowed: {record['validation_execution_allowed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
