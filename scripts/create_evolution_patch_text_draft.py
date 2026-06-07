from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[1])
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from core.project_evolution_patch_text_draft import write_project_evolution_patch_text_draft_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a read-only Project Evolution patch text draft from an approved candidate chain.",
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
        "--patch-draft-package-path",
        required=True,
        help="Path to a patch draft package JSON record under .agent/project_evolution/patch_drafts/.",
    )
    parser.add_argument(
        "--patch-candidates-path",
        required=True,
        help="Path to a patch candidates JSON record under .agent/project_evolution/patch_candidates/.",
    )
    parser.add_argument(
        "--selected-candidate-id",
        action="append",
        default=None,
        help="Optional candidate id to include in the patch text draft; repeat to select more than one.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=12,
        help="Cap for file lists used in the patch text draft.",
    )
    parser.add_argument(
        "--notes",
        default=None,
        help="Optional notes for the patch text draft.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = write_project_evolution_patch_text_draft_artifacts(
        repo_path=args.repo_path,
        approval_path=args.approval_path,
        patch_draft_package_path=args.patch_draft_package_path,
        patch_candidates_path=args.patch_candidates_path,
        selected_candidate_ids=args.selected_candidate_id,
        max_files=args.max_files,
        notes=args.notes,
    )
    record = result["record"]
    if record.get("status") != "ok":
        print(f"error: {record['error']['message']}", file=sys.stderr)
        return 1

    print(f"json_path: {result['json_path']}")
    print(f"md_path: {result['md_path']}")
    print(f"candidate_count: {len(record['patch_text_drafts'])}")
    print(f"approval_verified: {record['approval_verified']}")
    print(f"patch_apply_allowed: {record['patch_apply_allowed']}")
    print(f"validation_execution_allowed: {record['validation_execution_allowed']}")
    print(f"real_repo_apply_allowed: {record['real_repo_apply_allowed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

