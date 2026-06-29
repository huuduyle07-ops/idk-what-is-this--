#!/usr/bin/env python
"""Create a MIRROR.1 Mirror Tunnel Trace Contract.

This CLI reads explicit existing artifact paths and writes report-only
``mirror_tunnel_trace_contract.json`` / ``mirror_tunnel_trace_contract.md``
artifacts. It never executes validation, benchmarks, workers, MCP tools,
Docker/subprocess commands, Dream actions, Replay janitor actions, network
calls, database writes, route changes, auth changes, model calls, patch
generation, or patch application.
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

from core.mirror_tunnel_trace_contract import (  # noqa: E402
    DEFAULT_EXCERPT_LIMIT,
    build_mirror_tunnel_trace_contract,
    render_mirror_tunnel_trace_json,
    render_mirror_tunnel_trace_markdown,
    write_mirror_tunnel_trace_contract,
)


DEFAULT_REPO_PATH = "."
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "mirror_tunnel" / "trace_contract")


def _resolve_created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
    return str(raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "MIRROR.1: reconstruct a report-only trace contract from explicit "
            "existing artifacts. No validation, benchmark, worker, model, MCP, "
            "Docker/subprocess, network, database, route, auth, or patch action "
            "is performed."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        metavar="PATH",
        help="Existing source artifact path to read after safety checks. Repeatable.",
    )
    parser.add_argument("--source-run-id", default="", help="Optional source run id to preserve.")
    parser.add_argument("--trace-id", default=None, help="Optional deterministic trace id.")
    parser.add_argument("--created-at", default=None, help="Optional deterministic created-at timestamp.")
    parser.add_argument(
        "--excerpt-limit",
        type=int,
        default=DEFAULT_EXCERPT_LIMIT,
        help="Maximum characters to store per frame excerpt.",
    )
    parser.add_argument(
        "--output-root",
        default=DEFAULT_OUTPUT_ROOT,
        help="Output directory for the JSON and Markdown artifacts.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Build the report without writing artifacts.")
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON.")
    parser.add_argument(
        "--allow-blocked-report",
        action="store_true",
        help="Exit 0 even when the trace status is blocked.",
    )
    return parser


def create_contract_result(args: argparse.Namespace) -> dict:
    created_at = _resolve_created_at(args.created_at)
    if args.dry_run:
        report = build_mirror_tunnel_trace_contract(
            repo_path=args.repo_path,
            source_artifact_paths=list(args.artifact),
            source_run_id=args.source_run_id,
            trace_id=args.trace_id,
            created_at=created_at,
            excerpt_limit=args.excerpt_limit,
        )
        return {
            "ok": report["status"] != "blocked",
            "dry_run": True,
            "status": report["status"],
            "report": report,
            "markdown": render_mirror_tunnel_trace_markdown(report),
        }

    result = write_mirror_tunnel_trace_contract(
        repo_path=args.repo_path,
        source_artifact_paths=list(args.artifact),
        source_run_id=args.source_run_id,
        trace_id=args.trace_id,
        created_at=created_at,
        excerpt_limit=args.excerpt_limit,
        output_root=args.output_root,
    )
    result["dry_run"] = False
    return result


def _print_text(result: dict) -> None:
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    print("MIRROR.1 - Mirror Tunnel Trace Contract")
    print("=" * 42)
    print(f"Trace id     : {report.get('trace_id', '')}")
    print(f"Status       : {report.get('status', '')}")
    print(f"Trust level  : {report.get('trust_level', '')}")
    print(f"Frames       : {len(report.get('frames', []) if isinstance(report.get('frames'), list) else [])}")
    print(f"Missing      : {len(report.get('missing_frames', []) if isinstance(report.get('missing_frames'), list) else [])}")
    if result.get("json_path"):
        print(f"JSON         : {result.get('json_path')}")
    if result.get("md_path"):
        print(f"Markdown     : {result.get('md_path')}")
    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    if blockers:
        print("Blockers     :")
        for blocker in blockers:
            print(f"  - {blocker.get('artifact_path', '')}: {blocker.get('reason', '')}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = create_contract_result(args)
    report = result.get("report") if isinstance(result.get("report"), dict) else {}

    if args.json:
        if args.dry_run:
            print(render_mirror_tunnel_trace_json(report), end="")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_text(result)

    if report.get("status") == "blocked" and not args.allow_blocked_report:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
