#!/usr/bin/env python
"""Create MIRROR.CLOSE - Mirror Tunnel Branch Checkpoint.

Reads the phase registry, existing MIRROR.1-MIRROR.6 artifacts, and local Mirror
Tunnel source text, then writes a report-only JSON + Markdown branch checkpoint.

No model call, patch apply, validation run, benchmark run, MCP invocation,
worker launch, Dream execution, Replay janitor apply, Docker/subprocess use,
network call, database write, route behavior change, auth policy change, live
runtime tracing, or execution blocking is performed.
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

from core.mirror_tunnel_branch_checkpoint import (  # noqa: E402
    DEFAULT_ARTIFACT_PATHS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REGISTRY,
    GUARDRAIL_NOTE,
    STATUS_BLOCKED,
    STATUS_FROZEN_WARNINGS,
    STATUS_NEEDS_MANUAL_EVIDENCE,
    gather_mirror_tunnel_branch_checkpoint_inputs,
    write_mirror_tunnel_branch_checkpoint,
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
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'report'}_mirror-tunnel-branch-checkpoint"


def run_create_mirror_tunnel_branch_checkpoint(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    registry: str = DEFAULT_REGISTRY,
    output_root: str = str(DEFAULT_OUTPUT_DIR),
    report_id: str | None = None,
    created_at: str | float | None = None,
    trace_contract: str | None = None,
    derailment_score: str | None = None,
    claim_diff_check: str | None = None,
    ingestion_plan: str | None = None,
    manual_trace: str | None = None,
    manual_review: str | None = None,
) -> dict[str, Any]:
    """Build and write the MIRROR.CLOSE checkpoint."""
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)
    inputs = gather_mirror_tunnel_branch_checkpoint_inputs(
        repo_path=repo_path,
        registry_path=registry,
        trace_contract_path=trace_contract,
        derailment_score_path=derailment_score,
        claim_diff_check_path=claim_diff_check,
        ingestion_plan_path=ingestion_plan,
        manual_trace_path=manual_trace,
        manual_review_path=manual_review,
    )
    result = write_mirror_tunnel_branch_checkpoint(
        repo_path=repo_path,
        registry_path=registry,
        output_dir=output_root,
        report_id=final_report_id,
        created_at=created_iso,
        inputs=inputs,
    )
    result["checkpoint_status"] = result["report"].get("checkpoint_status")
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    manual = report.get("manual_pipeline_summary") or {}
    guardrails = report.get("guardrail_summary") or {}
    print("MIRROR.CLOSE - Mirror Tunnel Branch Checkpoint")
    print("=" * 48)
    print(f"Report id          : {report.get('report_id')}")
    print(f"Repo path          : {report.get('repo_path')}")
    print(f"Registry           : {report.get('registry_path')}")
    print(f"Checkpoint status  : {report.get('checkpoint_status')}")
    print(f"Checkpoint reason  : {report.get('checkpoint_reason')}")
    print(f"Recommended next   : {report.get('recommended_next_phase')}")
    print(f"Manual frames      : {manual.get('meaningful_manual_frame_count', 0)}")
    print(f"Manual usable      : {manual.get('usable_even_if_real_trace_quality_is_weak')}")
    print(f"Guardrails clear   : {guardrails.get('all_clear')}")
    print(f"Warnings           : {len(report.get('warnings') or [])}")
    print(f"Blockers           : {len(report.get('blockers') or [])}")
    for warning in report.get("warnings") or []:
        print(f"  WARNING: {warning}")
    for blocker in report.get("blockers") or []:
        print(f"  BLOCKER: {blocker}")
    for gap in report.get("manual_evidence_gaps") or []:
        print(f"  MANUAL EVIDENCE GAP: {gap}")
    print(f"JSON               : {result['json_path']}")
    print(f"Markdown           : {result['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "MIRROR.CLOSE: freeze the manual Mirror Tunnel branch before any "
            "shadow live trace writer work. Report-only."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY, help="Phase registry JSON path.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    parser.add_argument("--report-id", default=None, help="Deterministic report id.")
    parser.add_argument("--created-at", default=None, help="Created-at timestamp, ISO-8601 or epoch seconds.")
    parser.add_argument("--trace-contract", default=None, help=f"MIRROR.1 artifact path. Default: {DEFAULT_ARTIFACT_PATHS['trace_contract']}")
    parser.add_argument("--derailment-score", default=None, help=f"MIRROR.2 artifact path. Default: {DEFAULT_ARTIFACT_PATHS['derailment_score']}")
    parser.add_argument("--claim-diff-check", default=None, help=f"MIRROR.3 artifact path. Default: {DEFAULT_ARTIFACT_PATHS['claim_diff_check']}")
    parser.add_argument("--ingestion-plan", default=None, help=f"MIRROR.4 artifact path. Default: {DEFAULT_ARTIFACT_PATHS['ingestion_plan']}")
    parser.add_argument("--manual-trace", default=None, help="MIRROR.5 manual trace artifact path. Default: discover latest manual trace.")
    parser.add_argument("--manual-review", default=None, help="MIRROR.6 manual review artifact path. Default: discover latest manual review.")
    parser.add_argument("--json", action="store_true", help="Print report JSON.")
    parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Exit 0 when checkpoint_status is frozen_with_manual_review_warnings.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_mirror_tunnel_branch_checkpoint(
        repo_path=args.repo_path,
        registry=args.registry,
        output_root=args.output_root,
        report_id=args.report_id,
        created_at=args.created_at,
        trace_contract=args.trace_contract,
        derailment_score=args.derailment_score,
        claim_diff_check=args.claim_diff_check,
        ingestion_plan=args.ingestion_plan,
        manual_trace=args.manual_trace,
        manual_review=args.manual_review,
    )

    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=True, sort_keys=True))
    else:
        _print_summary(result)

    status = result["checkpoint_status"]
    if status in {STATUS_BLOCKED, STATUS_NEEDS_MANUAL_EVIDENCE}:
        return 1
    if status == STATUS_FROZEN_WARNINGS and not args.allow_warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
