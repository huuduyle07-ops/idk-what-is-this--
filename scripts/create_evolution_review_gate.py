from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[1])
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from core.project_evolution_review_gate import (
    write_project_evolution_review_gate_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only Project Evolution review gate artifact "
            "from an executable patch draft."
        ),
    )
    parser.add_argument(
        "--repo-path",
        required=True,
        help="Repository root containing .agent/project_evolution artifacts.",
    )
    parser.add_argument(
        "--executable-patch-draft-path",
        required=True,
        help=(
            "Path to an executable patch draft JSON record "
            "under .agent/project_evolution/executable_patch_drafts/."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = write_project_evolution_review_gate_artifacts(
        repo_path=args.repo_path,
        executable_patch_draft_path=args.executable_patch_draft_path,
    )
    record = result["record"]
    if record.get("status") == "error":
        print(f"error: {record['error']['message']}", file=sys.stderr)
        return 1

    print(f"json_path: {result['json_path']}")
    print(f"md_path: {result['md_path']}")
    print(f"affected_file_count: {len(record['affected_files'])}")
    print(f"planned_edit_count: {record['planned_edit_count']}")
    print(f"risk_level: {record['risk_level']}")
    print(f"apply_allowed: {record['apply_allowed']}")
    print(f"human_approval_required: {record['human_approval_required']}")
    print(f"approval_status: {record['approval_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
