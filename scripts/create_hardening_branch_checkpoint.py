"""Create HARDEN.CLOSE - Hardening Branch Checkpoint.

Reads the phase registry, HARDEN.1 source markers, and existing HARDEN.2/HARDEN.3
audit artifacts, then writes a report-only JSON + Markdown checkpoint.

This script does not call models, apply patches, run validation, run benchmarks,
invoke MCP tools, launch workers, execute Dream or Replay janitor actions, use
Docker or subprocess, contact network services, write to a database, change
route/auth/UI behavior, push, merge, open PRs, or add automation power.

Usage:
    python scripts/create_hardening_branch_checkpoint.py --repo-path . --json --allow-warnings
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

from core.hardening_branch_checkpoint import (  # noqa: E402
    DEFAULT_HARDEN2_ARTIFACT,
    DEFAULT_HARDEN3_ARTIFACT,
    DEFAULT_REGISTRY,
    GUARDRAIL_NOTE,
    STATUS_BLOCKED,
    STATUS_FROZEN_WARNINGS,
    STATUS_NEEDS_HARDEN4,
    write_hardening_branch_checkpoint,
)


DEFAULT_REPO_PATH = "."
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "harden" / "hardening_branch_checkpoint")


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _default_report_id(created_iso: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'report'}_hardening-branch-checkpoint"


def run_create_hardening_branch_checkpoint(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    registry: str = DEFAULT_REGISTRY,
    harden2_artifact: str = DEFAULT_HARDEN2_ARTIFACT,
    harden3_artifact: str = DEFAULT_HARDEN3_ARTIFACT,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | float | None = None,
) -> dict[str, Any]:
    """Build and write the HARDEN.CLOSE checkpoint."""
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)
    result = write_hardening_branch_checkpoint(
        repo_path=repo_path,
        registry_path=registry,
        harden2_artifact_path=harden2_artifact,
        harden3_artifact_path=harden3_artifact,
        output_dir=output_root,
        report_id=final_report_id,
        created_at=created_iso,
    )
    result["checkpoint_status"] = result["report"].get("checkpoint_status")
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    h2 = report.get("harden2_route_surface_evidence") or {}
    h3 = report.get("harden3_validation_mcp_approval_evidence") or {}
    print("HARDEN.CLOSE - Hardening Branch Checkpoint")
    print("=" * 47)
    print(f"Report id          : {report.get('report_id')}")
    print(f"Repo path          : {report.get('repo_path')}")
    print(f"Registry           : {report.get('registry_path')}")
    print(f"Checkpoint status  : {report.get('checkpoint_status')}")
    print(f"Checkpoint reason  : {report.get('checkpoint_reason')}")
    print(f"Recommended next   : {report.get('recommended_next_phase')}")
    print(f"HARDEN.2 uncovered : {h2.get('uncovered_mutating_routes', 0)}")
    print(f"HARDEN.2 blockers  : {h2.get('blocker_count', 0)}")
    print(f"HARDEN.3 blockers  : {h3.get('blocker_count', 0)}")
    print(f"Warnings           : {len(report.get('warnings') or [])}")
    print(f"Blockers           : {len(report.get('blockers') or [])}")
    for blocker in report.get("blockers") or []:
        print(f"  BLOCKER: {blocker}")
    for warning in report.get("warnings") or []:
        print(f"  WARNING: {warning}")
    print(f"JSON               : {result['json_path']}")
    print(f"Markdown           : {result['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "HARDEN.CLOSE: consolidate HARDEN.1, HARDEN.2, and HARDEN.3 evidence "
            "into a report-only branch checkpoint."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY, help="Phase registry JSON path.")
    parser.add_argument(
        "--harden2-artifact",
        default=DEFAULT_HARDEN2_ARTIFACT,
        help="HARDEN.2 web mutation surface audit JSON path.",
    )
    parser.add_argument(
        "--harden3-artifact",
        default=DEFAULT_HARDEN3_ARTIFACT,
        help="HARDEN.3 safe validation / MCP approval audit JSON path.",
    )
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Output directory.")
    parser.add_argument("--report-id", default=None, help="Deterministic report id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Created-at timestamp (ISO-8601 or epoch seconds).",
    )
    parser.add_argument("--json", action="store_true", help="Print report JSON to stdout.")
    parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Exit 0 when checkpoint_status is frozen_with_manual_review_warnings.",
    )
    args = parser.parse_args(argv)

    result = run_create_hardening_branch_checkpoint(
        repo_path=args.repo_path,
        registry=args.registry,
        harden2_artifact=args.harden2_artifact,
        harden3_artifact=args.harden3_artifact,
        output_root=args.output_root,
        report_id=args.report_id,
        created_at=args.created_at,
    )

    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=True, sort_keys=True))
    else:
        _print_summary(result)

    status = result["checkpoint_status"]
    if status in {STATUS_BLOCKED, STATUS_NEEDS_HARDEN4}:
        return 1
    if status == STATUS_FROZEN_WARNINGS and not args.allow_warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
