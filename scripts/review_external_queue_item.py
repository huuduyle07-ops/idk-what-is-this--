from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[1])
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from core.external_queue_review import write_external_queue_review_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read an imported external queue item and write a recommendation-only "
            "review artifact under the same queue directory. "
            "No conversion, no Dream creation, no patch apply."
        ),
    )
    parser.add_argument(
        "--repo-path",
        required=True,
        help="Repository root where .agent/external_queue/ artifacts live.",
    )
    parser.add_argument(
        "--item-path",
        required=True,
        help=(
            "Path to external_queue_item.json. "
            "Must be inside <repo>/.agent/external_queue/."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    out = write_external_queue_review_artifacts(
        repo_path=args.repo_path,
        item_path=args.item_path,
    )
    record = out["record"]
    if record.get("status") == "error":
        print(f"error: {record['error']['message']}", file=sys.stderr)
        return 1

    print(f"review_json_path: {out['json_path']}")
    print(f"review_md_path: {out['md_path']}")
    print(f"queue_id: {record['queue_id']}")
    print(f"recommendation: {record['recommendation']}")
    print(f"recommendation_confidence: {record['recommendation_confidence']}")
    print(f"human_approval_required: {record['human_approval_required']}")
    print(f"action_performed: {record['action_performed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
