from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[1])
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from core.external_queue_index import (
    load_external_queue_item_detail,
    render_external_queue_detail_json,
    render_external_queue_detail_text,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Show one external queue item under .agent/external_queue/. "
            "Read-only: no review write, conversion, Dream trigger, model call, "
            "webhook, promotion, or patch apply."
        ),
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Repository root containing .agent/external_queue/ (default: current directory).",
    )
    parser.add_argument(
        "--queue-id",
        required=True,
        help="Queue id or artifact directory id to inspect.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print deterministic JSON instead of the readable detail view.",
    )
    raw_group = parser.add_mutually_exclusive_group()
    raw_group.add_argument(
        "--include-raw",
        action="store_true",
        help="Include parsed raw item/review JSON in the output.",
    )
    raw_group.add_argument(
        "--no-raw",
        action="store_true",
        help="Do not include parsed raw item/review JSON (default).",
    )
    parser.add_argument(
        "--show-review",
        action="store_true",
        help="Expand review evidence, missing evidence, and suggested prompt details.",
    )
    parser.add_argument(
        "--show-linked",
        action="store_true",
        help="Show linked artifact paths explicitly.",
    )
    parser.add_argument(
        "--show-redaction-warnings",
        action="store_true",
        help="Show redaction, secret, and sensitive-field warnings explicitly.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    detail = load_external_queue_item_detail(
        args.repo_path,
        args.queue_id,
        include_raw=args.include_raw,
    )

    if args.json:
        print(render_external_queue_detail_json(detail), end="")
    elif detail.get("found"):
        print(
            render_external_queue_detail_text(
                detail,
                show_review=args.show_review,
                show_linked=args.show_linked,
                show_redaction_warnings=args.show_redaction_warnings,
            ),
            end="",
        )
    else:
        print(
            render_external_queue_detail_text(
                detail,
                show_review=args.show_review,
                show_linked=args.show_linked,
                show_redaction_warnings=args.show_redaction_warnings,
            ),
            end="",
            file=sys.stderr,
        )
    return 0 if detail.get("found") else 1


if __name__ == "__main__":
    raise SystemExit(main())
