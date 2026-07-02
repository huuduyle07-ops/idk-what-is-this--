#!/usr/bin/env python
"""Create MIRROR.CLOSE3 Mirror Tunnel Live UI Readiness Checkpoint.

Report-only wrapper around the core checkpoint builder. It reads local registry,
source, and optional MIRROR.12 readiness artifacts, writes JSON/Markdown
checkpoint files, and prints a summary or the report JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.mirror_tunnel_live_ui_readiness_checkpoint import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REGISTRY,
    DEFAULT_READINESS_ARTIFACT,
    STATUS_BLOCKED,
    STATUS_FROZEN_WITH_WARNINGS,
    STATUS_NEEDS_LIVE_DEMO_EVIDENCE,
    write_mirror_tunnel_live_ui_readiness_checkpoint,
)


DEFAULT_REPO_PATH = "."


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).replace(microsecond=0).isoformat()


def _default_report_id(created_iso: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:32]
    return f"{stamp or 'report'}_mirror-live-ui-readiness"


def run_create_mirror_tunnel_live_ui_readiness_checkpoint(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    registry: str = DEFAULT_REGISTRY,
    output_dir: str = str(DEFAULT_OUTPUT_DIR),
    readiness_artifact: str | None = str(DEFAULT_READINESS_ARTIFACT),
    report_id: str | None = None,
    created_at: str | float | None = None,
) -> dict[str, Any]:
    """Build and write the MIRROR.CLOSE3 checkpoint."""
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)
    result = write_mirror_tunnel_live_ui_readiness_checkpoint(
        repo_path=repo_path,
        registry_path=registry,
        output_dir=output_dir,
        readiness_artifact_path=readiness_artifact,
        report_id=final_report_id,
        created_at=created_iso,
    )
    result["checkpoint_status"] = result["report"].get("checkpoint_status")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "MIRROR.CLOSE3: freeze the MIRROR.7-MIRROR.12 live/UI chain via "
            "a report-only readiness checkpoint."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY, help="Path to phase registry JSON.")
    parser.add_argument(
        "--readiness-artifact",
        default=str(DEFAULT_READINESS_ARTIFACT),
        help="Optional MIRROR.12 readiness JSON artifact path.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output artifact directory.")
    parser.add_argument("--report-id", default=None, help="Deterministic report id.")
    parser.add_argument("--created-at", default=None, help="Created-at timestamp (ISO-8601 or epoch seconds).")
    parser.add_argument("--json", action="store_true", help="Print report JSON to stdout.")
    parser.add_argument("--allow-warnings", action="store_true", help="Exit 0 for frozen-with-warnings status.")
    parser.add_argument("--allow-needs-evidence", action="store_true", help="Exit 0 for needs-live-demo-evidence status.")
    parser.add_argument("--allow-blocked-report", action="store_true", help="Exit 0 even when blocked.")
    return parser


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    print("MIRROR.CLOSE3 - Mirror Tunnel Live UI Readiness Checkpoint")
    print("=" * 62)
    print(f"Report id         : {report.get('report_id')}")
    print(f"Checkpoint status : {report.get('checkpoint_status')}")
    print(f"Checkpoint reason : {report.get('checkpoint_reason')}")
    print(f"Next phase        : {report.get('recommended_next_phase')}")
    print(f"JSON              : {result.get('json_path')}")
    print(f"Markdown          : {result.get('md_path')}")
    for blocker in report.get("blockers") or []:
        print(f"  BLOCKER: {blocker}")
    for warning in report.get("warnings") or []:
        print(f"  WARNING: {warning}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_mirror_tunnel_live_ui_readiness_checkpoint(
        repo_path=args.repo_path,
        registry=args.registry,
        output_dir=args.output_dir,
        readiness_artifact=args.readiness_artifact,
        report_id=args.report_id,
        created_at=args.created_at,
    )

    report = result["report"]
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)

    status = report.get("checkpoint_status")
    if status == STATUS_BLOCKED and not args.allow_blocked_report:
        return 1
    if status == STATUS_FROZEN_WITH_WARNINGS and not args.allow_warnings:
        return 1
    if status == STATUS_NEEDS_LIVE_DEMO_EVIDENCE and not args.allow_needs_evidence:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
