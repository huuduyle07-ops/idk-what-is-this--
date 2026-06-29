#!/usr/bin/env python
"""Create a MIRROR.4 Real Run Trace Ingestion Plan.

This CLI writes report-only ``mirror_tunnel_ingestion_plan.json`` /
``mirror_tunnel_ingestion_plan.md`` artifacts. It defines how future real runs
should emit Mirror Tunnel frames, but it does not enable automatic tracing,
change routes/auth, call models, run validation/benchmarks, launch workers, use
Docker/subprocess, contact the network, or write anything except plan artifacts.
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

from core.mirror_tunnel_ingestion_plan import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    build_mirror_tunnel_ingestion_plan,
    render_mirror_tunnel_ingestion_json,
    write_mirror_tunnel_ingestion_plan,
)


DEFAULT_REPO_PATH = "."


def _resolve_created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
    return str(raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "MIRROR.4: create a report-only plan for future real-run Mirror "
            "Tunnel frame emission. No automatic tracing, model call, patch "
            "apply, validation, benchmark, MCP, worker, Docker/subprocess, "
            "network, database, route, auth, or blocking action is performed."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
    parser.add_argument("--plan-id", default=None, help="Optional deterministic plan id.")
    parser.add_argument("--created-at", default=None, help="Optional deterministic created-at timestamp.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory for artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Build the report without writing artifacts.")
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON.")
    parser.add_argument(
        "--allow-blocked-report",
        action="store_true",
        help="Exit 0 even when the output path is blocked.",
    )
    return parser


def create_ingestion_result(args: argparse.Namespace) -> dict:
    created_at = _resolve_created_at(args.created_at)
    if args.dry_run:
        report = build_mirror_tunnel_ingestion_plan(
            repo_path=args.repo_path,
            plan_id=args.plan_id,
            created_at=created_at,
        )
        return {"ok": True, "dry_run": True, "status": report["status"], "report": report, "markdown": ""}

    result = write_mirror_tunnel_ingestion_plan(
        repo_path=args.repo_path,
        output_root=args.output_root,
        plan_id=args.plan_id,
        created_at=created_at,
    )
    result["dry_run"] = False
    return result


def _print_text(result: dict) -> None:
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    print("MIRROR.4 - Real Run Trace Ingestion Plan")
    print("=" * 43)
    print(f"Plan id      : {report.get('plan_id', '')}")
    print(f"Status       : {report.get('status', '')}")
    print(f"Next phase   : {report.get('recommended_next_phase', '')}")
    print(f"Next action  : {report.get('recommended_next_action', '')}")
    if result.get("json_path"):
        print(f"JSON         : {result.get('json_path')}")
    if result.get("md_path"):
        print(f"Markdown     : {result.get('md_path')}")
    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    if blockers:
        print("Blockers     :")
        for blocker in blockers:
            print(f"  - {blocker.get('reason', '')}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = create_ingestion_result(args)
    report = result.get("report") if isinstance(result.get("report"), dict) else {}

    if args.json:
        if args.dry_run:
            print(render_mirror_tunnel_ingestion_json(report), end="")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_text(result)

    if result.get("status") == "blocked" and not args.allow_blocked_report:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
