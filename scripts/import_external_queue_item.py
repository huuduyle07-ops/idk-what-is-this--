from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[1])
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from core.external_queue_import import (
    load_external_queue_item_from_json,
    write_external_queue_item_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Import an external queue item (from Discord, n8n, Zalo, webhook, or manual) "
            "as a review-only artifact under .agent/external_queue/."
        ),
    )
    parser.add_argument(
        "--repo-path",
        required=True,
        help="Repository root where .agent/external_queue/ artifacts will be written.",
    )
    parser.add_argument(
        "--input-json",
        default="",
        help="Path to a JSON file containing the queue item fields. Overrides individual flags.",
    )
    parser.add_argument(
        "--source",
        default="manual",
        help="Item source: discord, n8n, zalo, webhook, or manual (default: manual).",
    )
    parser.add_argument(
        "--kind",
        default="research_wishlist",
        help=(
            "Item kind: research_wishlist, bug_seed, project_evolution_seed, "
            "lesson_candidate_seed (default: research_wishlist)."
        ),
    )
    parser.add_argument(
        "--query",
        default="",
        help="The research question or item text (required unless --input-json is used).",
    )
    parser.add_argument(
        "--result",
        default="",
        help="Optional result or context for the query.",
    )
    parser.add_argument(
        "--source-url",
        default="",
        help="Optional URL to the original source message or thread.",
    )
    parser.add_argument(
        "--submitted-by",
        default="",
        help="Optional name or handle of the person who submitted the item.",
    )
    parser.add_argument(
        "--received-at",
        default="",
        help="Optional ISO timestamp of when the item was received.",
    )
    parser.add_argument(
        "--metadata-json",
        default="",
        help="Optional JSON object string for additional metadata.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.input_json:
        load_result = load_external_queue_item_from_json(args.input_json)
        if load_result.get("status") != "ok":
            print(
                f"error: {load_result.get('message', 'could not load input JSON')}",
                file=sys.stderr,
            )
            return 1
        data = load_result["data"]
        source = data.get("source", "manual")
        kind = data.get("kind", "research_wishlist")
        query = data.get("query", "")
        result = data.get("result", "")
        source_url = data.get("source_url", "")
        submitted_by = data.get("submitted_by", "")
        received_at = data.get("received_at", "")
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
    else:
        source = args.source
        kind = args.kind
        query = args.query
        result = args.result
        source_url = args.source_url
        submitted_by = args.submitted_by
        received_at = args.received_at
        metadata: dict = {}
        if args.metadata_json:
            try:
                metadata = json.loads(args.metadata_json)
                if not isinstance(metadata, dict):
                    metadata = {}
            except json.JSONDecodeError as exc:
                print(f"error: --metadata-json is not valid JSON: {exc}", file=sys.stderr)
                return 1

    out = write_external_queue_item_artifacts(
        repo_path=args.repo_path,
        source=source,
        kind=kind,
        query=query,
        result=result,
        source_url=source_url,
        submitted_by=submitted_by,
        received_at=received_at,
        metadata=metadata,
    )
    record = out["record"]
    if record.get("status") == "error":
        print(f"error: {record['error']['message']}", file=sys.stderr)
        return 1

    print(f"json_path: {out['json_path']}")
    print(f"md_path: {out['md_path']}")
    print(f"queue_id: {record['queue_id']}")
    print(f"risk_level: {record['risk_level']}")
    print(f"import_status: {record['import_status']}")
    print(f"auto_dream_allowed: {record['auto_dream_allowed']}")
    print(f"human_review_required: {record['human_review_required']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
