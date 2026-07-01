#!/usr/bin/env python
"""Create a MIRROR.9 Live Trace Operator Report Panel Plan.

This CLI writes a report-only operator panel contract for displaying MIRROR.7
live traces and MIRROR.8 scoring previews. It does not build UI, call models,
apply patches, run validation or benchmarks, contact network services, launch
workers, or change runtime behavior.
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

from core.mirror_tunnel_operator_panel_plan import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    STATUS_BLOCKED,
    write_mirror_tunnel_operator_panel_plan,
)


DEFAULT_REPO_PATH = "."


def _resolve_created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
    return str(raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "MIRROR.9: create a report-only operator panel plan for MIRROR.7 "
            "live traces and MIRROR.8 scoring previews."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
    parser.add_argument("--preview", default=None, help="Optional MIRROR.8 live trace scoring preview JSON.")
    parser.add_argument("--trace", default=None, help="Optional MIRROR.7 or MIRROR.1-compatible trace JSON.")
    parser.add_argument("--created-at", default=None, help="Optional deterministic created-at timestamp.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output artifact directory.")
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON result.")
    parser.add_argument("--allow-blocked-report", action="store_true", help="Exit 0 even when blocked.")
    return parser


def create_operator_panel_plan_result(args: argparse.Namespace) -> dict:
    return write_mirror_tunnel_operator_panel_plan(
        repo_path=args.repo_path,
        preview_path=args.preview,
        trace_path=args.trace,
        output_dir=args.output_dir,
        created_at=_resolve_created_at(args.created_at),
    )


def _print_text(result: dict) -> None:
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    print("MIRROR.9 - Live Trace Operator Report Panel Plan")
    print("=" * 53)
    print(f"Status      : {report.get('status', '')}")
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
    result = create_operator_panel_plan_result(args)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_text(result)
    if result.get("status") == STATUS_BLOCKED and not args.allow_blocked_report:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
