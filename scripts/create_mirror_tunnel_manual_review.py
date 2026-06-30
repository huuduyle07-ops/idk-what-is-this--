#!/usr/bin/env python
"""Create a MIRROR.6 Manual Trace Score Pipeline review pack.

This CLI reads a MIRROR.5/MIRROR.1 trace JSON, optionally reads existing
MIRROR.2 and MIRROR.3 JSON reports, and writes one combined manual review pack.
It does not shell out to MIRROR.2/MIRROR.3 CLI scripts and does not call models,
apply patches, run validation/benchmarks, invoke MCP tools, launch workers, use
Docker/subprocess, contact the network, write to a database, change routes/auth,
or enable live runtime tracing.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.mirror_tunnel_manual_review_pipeline import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    render_mirror_tunnel_manual_review_json,
    write_mirror_tunnel_manual_review,
)


DEFAULT_REPO_PATH = "."


def _resolve_created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
    return str(raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "MIRROR.6: create a report-only manual review pack from a MIRROR.5 "
            "trace, deriving MIRROR.2/MIRROR.3 reports via pure Python builders "
            "when they are not supplied. No CLI shell-out, model call, patch "
            "apply, validation, benchmark, MCP, worker, Docker/subprocess, "
            "network, database, route, auth, or live tracing action is performed."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
    parser.add_argument("--trace", required=True, help="MIRROR.5/MIRROR.1-compatible trace JSON path.")
    parser.add_argument("--score", default=None, help="Optional existing MIRROR.2 score JSON path.")
    parser.add_argument("--claim-diff", default=None, help="Optional existing MIRROR.3 claim-diff JSON path.")
    parser.add_argument("--review-id", default=None, help="Optional review id.")
    parser.add_argument("--created-at", default=None, help="Optional deterministic created-at timestamp.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Base output directory; the review id directory is created beneath it.",
    )
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON.")
    parser.add_argument(
        "--allow-blocked-report",
        action="store_true",
        help="Exit 0 even when the manual review status is blocked.",
    )
    return parser


def create_manual_review_result(args: argparse.Namespace) -> dict:
    return write_mirror_tunnel_manual_review(
        repo_path=args.repo_path,
        trace_path=args.trace,
        score_path=args.score,
        claim_diff_path=args.claim_diff,
        review_id=args.review_id,
        created_at=_resolve_created_at(args.created_at),
        output_dir=args.output_dir,
    )


def _print_text(result: dict) -> None:
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    print("MIRROR.6 - Manual Trace Score Pipeline")
    print("=" * 42)
    print(f"Review id    : {report.get('review_id', '')}")
    print(f"Trace id     : {report.get('trace_id', '')}")
    print(f"Verdict      : {report.get('combined_verdict', '')}")
    print(f"Next action  : {report.get('recommended_next_action', '')}")
    if result.get("json_path"):
        print(f"JSON         : {result.get('json_path')}")
    if result.get("md_path"):
        print(f"Markdown     : {result.get('md_path')}")
    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    if blockers:
        print("Blockers     :")
        for blocker in blockers:
            print(f"  - {blocker.get('reason', '')}: {blocker.get('message', '')}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = create_manual_review_result(args)
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_text(result)
    if report.get("combined_verdict") == "blocked" and not args.allow_blocked_report:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
