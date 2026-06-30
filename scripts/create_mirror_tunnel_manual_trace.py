#!/usr/bin/env python
"""Create a MIRROR.5 manually assembled Mirror Tunnel trace.

This CLI reads explicit artifact paths and writes a MIRROR.1-compatible
``mirror_tunnel_trace_contract.json`` / ``mirror_tunnel_trace_contract.md``
under ``.agent/mirror_tunnel/manual_trace/<trace_id>/``. It does not call
models, apply patches, run validation/benchmarks, invoke MCP tools, launch
workers, execute Dream or Replay janitor actions, use Docker/subprocess,
contact the network, write to a database, change route/auth behavior, or enable
automatic live tracing.
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

from core.mirror_tunnel_manual_trace_assembler import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    FRAME_INPUTS,
    build_manual_mirror_tunnel_trace,
    render_manual_mirror_tunnel_trace_json,
    render_manual_mirror_tunnel_trace_markdown,
    write_manual_mirror_tunnel_trace,
)
from core.mirror_tunnel_trace_contract import DEFAULT_EXCERPT_LIMIT  # noqa: E402


DEFAULT_REPO_PATH = "."


def _resolve_created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
    return str(raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "MIRROR.5: manually assemble a MIRROR.1-compatible trace from "
            "explicit artifact paths. No automatic live tracing, model call, "
            "patch apply, validation, benchmark, MCP, worker, Docker/subprocess, "
            "network, database, route, auth, or blocking action is performed."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
    parser.add_argument("--trace-id", default=None, help="Optional trace id.")
    parser.add_argument("--created-at", default=None, help="Optional deterministic created-at timestamp.")
    parser.add_argument(
        "--excerpt-limit",
        type=int,
        default=DEFAULT_EXCERPT_LIMIT,
        help="Maximum characters to store per frame excerpt.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Base output directory; the trace id directory is created beneath it.",
    )
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the trace report without writing artifacts.",
    )
    parser.add_argument(
        "--allow-blocked-report",
        action="store_true",
        help="Exit 0 even when the assembled trace status is blocked.",
    )
    for item in FRAME_INPUTS:
        parser.add_argument(
            "--" + item["source_key"].replace("_", "-"),
            default=None,
            metavar="PATH",
            help=f"Explicit artifact path for {item['frame_type']}.",
        )
    return parser


def create_manual_trace_result(args: argparse.Namespace) -> dict:
    created_at = _resolve_created_at(args.created_at)
    artifact_paths = _artifact_paths_from_args(args)
    if args.dry_run:
        report = build_manual_mirror_tunnel_trace(
            repo_path=args.repo_path,
            artifact_paths=artifact_paths,
            trace_id=args.trace_id,
            created_at=created_at,
            excerpt_limit=args.excerpt_limit,
        )
        return {
            "ok": report["status"] != "blocked",
            "dry_run": True,
            "status": report["status"],
            "report": report,
            "markdown": render_manual_mirror_tunnel_trace_markdown(report),
        }
    result = write_manual_mirror_tunnel_trace(
        repo_path=args.repo_path,
        artifact_paths=artifact_paths,
        trace_id=args.trace_id,
        created_at=created_at,
        excerpt_limit=args.excerpt_limit,
        output_dir=args.output_dir,
    )
    result["dry_run"] = False
    return result


def _artifact_paths_from_args(args: argparse.Namespace) -> dict[str, str | None]:
    return {item["source_key"]: getattr(args, item["source_key"]) for item in FRAME_INPUTS}


def _print_text(result: dict) -> None:
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    print("MIRROR.5 - Manual Trace Assembler")
    print("=" * 38)
    print(f"Trace id     : {report.get('trace_id', '')}")
    print(f"Status       : {report.get('status', '')}")
    print(f"Trust level  : {report.get('trust_level', '')}")
    print(f"Frames       : {len(report.get('frames', []) if isinstance(report.get('frames'), list) else [])}")
    print(f"Missing      : {len(report.get('missing_evidence', []) if isinstance(report.get('missing_evidence'), list) else [])}")
    if result.get("json_path"):
        print(f"JSON         : {result.get('json_path')}")
    if result.get("md_path"):
        print(f"Markdown     : {result.get('md_path')}")
    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    if blockers:
        print("Blockers     :")
        for blocker in blockers:
            print(f"  - {blocker.get('source_key', '')}: {blocker.get('reason', '')}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = create_manual_trace_result(args)
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    if args.json:
        if args.dry_run:
            print(render_manual_mirror_tunnel_trace_json(report), end="")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_text(result)
    if report.get("status") == "blocked" and not args.allow_blocked_report:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
