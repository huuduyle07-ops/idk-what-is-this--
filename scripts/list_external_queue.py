from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[1])
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from core.external_queue_index import (
    build_external_queue_index,
    render_external_queue_index_json,
    render_external_queue_index_table,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "List external queue artifacts under .agent/external_queue/. "
            "Read-only: no review, conversion, Dream trigger, model call, webhook, or patch apply."
        ),
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Repository root containing .agent/external_queue/ (default: current directory).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print deterministic JSON instead of the compact table.",
    )
    parser.add_argument(
        "--status",
        default="",
        help="Filter by status: queued, reviewed, rejected, promoted, invalid, or unknown.",
    )
    parser.add_argument(
        "--source",
        default="",
        help="Filter by source kind: discord, n8n, manual, or unknown.",
    )
    parser.add_argument(
        "--kind",
        default="",
        help="Filter by artifact kind, such as research_wishlist or bug_seed.",
    )
    parser.add_argument(
        "--risk",
        default="",
        help="Filter by risk level: low, medium, high, or unknown.",
    )
    parser.add_argument(
        "--recommendation",
        default="",
        help="Filter by review recommendation.",
    )
    parser.add_argument(
        "--reviewed",
        action="store_true",
        help="Shortcut for --status reviewed.",
    )
    parser.add_argument(
        "--unreviewed",
        action="store_true",
        help="Shortcut for --status queued.",
    )
    parser.add_argument(
        "--limit",
        type=_non_negative_int,
        default=None,
        help="Maximum number of rows to print.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    status = args.status
    if args.reviewed and args.unreviewed:
        parser.error("--reviewed and --unreviewed cannot be combined")
    if args.reviewed:
        status = "reviewed"
    if args.unreviewed:
        status = "queued"

    items = build_external_queue_index(
        args.repo_path,
        status=status,
        source=args.source,
        kind=args.kind,
        risk=args.risk,
        recommendation=args.recommendation,
        limit=args.limit,
    )
    if args.json:
        print(render_external_queue_index_json(items), end="")
    else:
        print(render_external_queue_index_table(items), end="")
    return 0


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
