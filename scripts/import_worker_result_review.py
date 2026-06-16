#!/usr/bin/env python
"""Import an external worker result into an inert F.7 review stub.

This script writes local review artifacts only. It never calls models, launches
workers, applies patches, runs validation, imports proposals, promotes lessons,
creates teaching cards, triggers Dream, runs Project Evolution, or calls
webhooks/network.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.worker_result_review import (  # noqa: E402
    create_worker_result_review,
    render_worker_result_review_json,
    render_worker_result_review_text,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import an external worker result into an inert review stub.",
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Repository root for the worker result review artifact.",
    )
    parser.add_argument(
        "--worker-assignment",
        required=True,
        help="Path to the worker_assignment.json artifact.",
    )
    parser.add_argument(
        "--result-text",
        default="",
        help="Worker result text pasted directly on the command line.",
    )
    parser.add_argument(
        "--result-file",
        default="",
        help="Path to a text/Markdown file containing the worker result.",
    )
    parser.add_argument(
        "--driver-decision",
        default="",
        help="Optional linked driver decision artifact.",
    )
    parser.add_argument(
        "--visual-evidence-contract",
        default="",
        help="Optional linked visual evidence contract artifact.",
    )
    parser.add_argument(
        "--output-root",
        default="",
        help="Optional review root. Defaults to .agent/worker_result_reviews/.",
    )
    parser.add_argument(
        "--review-id",
        default="",
        help="Optional stable review id for smoke tests or reruns.",
    )
    parser.add_argument(
        "--created-at",
        default="",
        help="Optional ISO timestamp for deterministic JSON output.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show the review without writing files.")
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = create_worker_result_review(
        repo_path=args.repo_path,
        worker_assignment_path=args.worker_assignment,
        result_text=args.result_text or None,
        result_file_path=args.result_file or None,
        driver_decision_path=args.driver_decision or None,
        visual_evidence_contract_path=args.visual_evidence_contract or None,
        dry_run=args.dry_run,
        output_root=args.output_root or None,
        review_id=args.review_id or None,
        created_at=args.created_at or None,
    )

    if args.json:
        print(render_worker_result_review_json(result), end="")
    elif result.get("ok"):
        print(render_worker_result_review_text(result), end="")
    else:
        print(render_worker_result_review_text(result), end="", file=sys.stderr)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
