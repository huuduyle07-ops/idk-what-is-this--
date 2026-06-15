from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[1])
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from core.external_queue_export import (
    SUPPORTED_TARGETS,
    export_external_queue_item,
    render_external_queue_export_json,
    render_external_queue_export_text,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export one reviewed external queue item as an inert draft artifact. "
            "Draft-only: no Goal Brief creation, Dream run, Project Evolution plan, "
            "model call, webhook, promotion, validation command, or patch apply."
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
        help="Queue id or artifact directory id to export.",
    )
    parser.add_argument(
        "--target",
        required=True,
        choices=SUPPORTED_TARGETS,
        help="Draft target to create.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print deterministic JSON instead of the readable status view.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the draft that would be written without creating files.",
    )
    parser.add_argument(
        "--output-root",
        default="",
        help=(
            "Optional export root. Defaults to .agent/external_queue_exports/ "
            "inside the repository."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    result = export_external_queue_item(
        args.repo_path,
        args.queue_id,
        args.target,
        dry_run=args.dry_run,
        output_root=args.output_root,
    )

    if args.json:
        print(render_external_queue_export_json(result), end="")
    elif result.get("ok") or result.get("status") == "already_exists":
        print(render_external_queue_export_text(result), end="")
    else:
        print(render_external_queue_export_text(result), end="", file=sys.stderr)
    return 0 if result.get("ok") or result.get("status") == "already_exists" else 1


if __name__ == "__main__":
    raise SystemExit(main())
