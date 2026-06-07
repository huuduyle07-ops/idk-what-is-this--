from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[1])
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from core.project_node_summaries import write_project_node_summaries_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build heuristic Project Evolution node summaries.",
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Repository root to scan. Defaults to the current directory.",
    )
    parser.add_argument(
        "--source-map-path",
        default=None,
        help="Optional path to project_map_v2.json. Defaults to .agent/project_evolution/project_map_v2.json under the repo.",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Optional repo-relative output directory. Defaults to .agent/project_evolution/.",
    )
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=40,
        help="Cap for heuristic node summaries.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = write_project_node_summaries_artifacts(
        repo_path=args.repo_path,
        source_map_path=args.source_map_path,
        output_root=args.output_root,
        max_nodes=args.max_nodes,
    )
    print(f"json_path: {result['json_path']}")
    print(f"md_path: {result['md_path']}")
    print(f"summary_count: {result['record']['summary_count']}")
    if result["record"]["status"] != "ok":
        print(f"error: {result['record']['error']['message']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
