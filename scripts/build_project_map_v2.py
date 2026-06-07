from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[1])
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from core.project_map_v2 import write_project_map_v2_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build read-only Project Map v2 artifacts for Project Evolution Mode.",
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Repository root to scan. Defaults to the current directory.",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Optional repo-relative output directory. Defaults to .agent/project_evolution/.",
    )
    parser.add_argument(
        "--max-full-file-candidates",
        type=int,
        default=30,
        help="Cap for heuristic full-file-read candidates.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = write_project_map_v2_artifacts(
        repo_path=args.repo_path,
        output_root=args.output_root,
        max_full_file_candidates=args.max_full_file_candidates,
    )
    print(f"json_path: {result['json_path']}")
    print(f"md_path: {result['md_path']}")
    print(f"candidate_count: {len(result['record']['full_file_read_candidates'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
