#!/usr/bin/env python
"""Create a MIRROR.12 Mirror Tunnel Live Demo Readiness report.

This CLI inspects existing MIRROR.7 and MIRROR.8 artifacts from a manually run
demo. It does not start the demo, enable tracing, generate previews, score
anything, mutate artifacts, or change runtime/UI behavior.
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

from core.mirror_tunnel_live_demo_readiness import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    STATUS_BLOCKED,
    write_mirror_tunnel_live_demo_readiness,
)


DEFAULT_REPO_PATH = "."


def _resolve_created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
    return str(raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "MIRROR.12: inspect an existing MIRROR.7 live trace and MIRROR.8 "
            "preview to report whether one manual Mirror Tunnel demo is ready."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
    parser.add_argument("--live-trace", required=True, help="Path to MIRROR.7 live trace JSON.")
    parser.add_argument("--preview", required=True, help="Path to MIRROR.8 live trace scoring preview JSON.")
    parser.add_argument("--preview-id", default=None, help="Optional MIRROR.11 preview id to verify.")
    parser.add_argument("--created-at", default=None, help="Optional deterministic created-at timestamp.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output artifact directory.")
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON result.")
    parser.add_argument("--allow-blocked-report", action="store_true", help="Exit 0 even when blocked.")
    return parser


def create_live_demo_readiness_result(args: argparse.Namespace) -> dict:
    return write_mirror_tunnel_live_demo_readiness(
        repo_path=args.repo_path,
        live_trace_path=args.live_trace,
        preview_path=args.preview,
        preview_id=args.preview_id,
        created_at=_resolve_created_at(args.created_at),
        output_dir=args.output_dir,
    )


def _print_text(result: dict) -> None:
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    print("MIRROR.12 - Mirror Tunnel Live Demo Readiness")
    print("=" * 49)
    print(f"Status      : {report.get('status', '')}")
    print(f"Trace id    : {report.get('trace_id', '')}")
    print(f"Preview id  : {report.get('preview_id', '')}")
    print(f"Next phase  : {report.get('recommended_next_phase', '')}")
    if result.get("json_path"):
        print(f"JSON        : {result.get('json_path')}")
    if result.get("md_path"):
        print(f"Markdown    : {result.get('md_path')}")
    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    if blockers:
        print("Blockers    :")
        for blocker in blockers:
            print(f"  - {blocker.get('reason', '')}: {blocker.get('message', '')}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = create_live_demo_readiness_result(args)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_text(result)
    if result.get("status") == STATUS_BLOCKED and not args.allow_blocked_report:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
