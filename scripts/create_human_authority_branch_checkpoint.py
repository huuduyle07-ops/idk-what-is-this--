#!/usr/bin/env python
"""Create HUMAN.CLOSE - Human Authority Branch Checkpoint.

Writes checkpoint JSON/Markdown artifacts only. It does not enforce approvals,
approve/reject work, issue or consume tokens, run validation or benchmarks,
apply patches, launch workers, route models, invoke MCP tools, contact networks,
write databases, or change route/auth behavior.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.human_authority_branch_checkpoint import (  # noqa: E402
    DEFAULT_BOUNDARY_MAP_PATH,
    DEFAULT_DRY_RUN_VALIDATOR_PATH,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_REGISTRY_PATH,
    DEFAULT_SAMPLE_CATALOG_PATH,
    DEFAULT_TOKEN_CONTRACT_PATH,
    GUARDRAIL_NOTE,
    STATUS_FROZEN,
    STATUS_FROZEN_WITH_WARNINGS,
    write_human_authority_branch_checkpoint,
)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "checkpoint_status": report.get("checkpoint_status"),
        "all_required_human_phases_complete": bool(summary.get("all_required_human_phases_complete")),
        "required_artifacts_present": bool(summary.get("required_artifacts_present")),
        "sample_token_files_present": bool(summary.get("sample_token_files_present")),
        "warning_count": int(summary.get("warning_count") or 0),
        "blocked_reason_count": int(summary.get("blocked_reason_count") or 0),
        "incomplete_reason_count": int(summary.get("incomplete_reason_count") or 0),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_human_authority_branch_checkpoint(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    boundary_map_path: str | Path = DEFAULT_BOUNDARY_MAP_PATH,
    token_contract_path: str | Path = DEFAULT_TOKEN_CONTRACT_PATH,
    dry_run_validator_path: str | Path = DEFAULT_DRY_RUN_VALIDATOR_PATH,
    sample_catalog_path: str | Path = DEFAULT_SAMPLE_CATALOG_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create HUMAN.CLOSE checkpoint artifacts and return paths plus summary."""
    result = write_human_authority_branch_checkpoint(
        repo_root=repo_root,
        registry_path=registry_path,
        boundary_map_path=boundary_map_path,
        token_contract_path=token_contract_path,
        dry_run_validator_path=dry_run_validator_path,
        sample_catalog_path=sample_catalog_path,
        output_dir=output_dir,
        report_id=report_id,
        created_at=created_at,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("HUMAN.CLOSE - Human Authority Branch Checkpoint")
    print("=" * 52)
    print(f"Checkpoint status : {summary['checkpoint_status']}")
    print(f"Phases complete   : {summary['all_required_human_phases_complete']}")
    print(f"Artifacts present : {summary['required_artifacts_present']}")
    print(f"Sample files      : {summary['sample_token_files_present']}")
    print(f"Warnings          : {summary['warning_count']}")
    print(f"Blocked reasons   : {summary['blocked_reason_count']}")
    print(f"Incomplete items  : {summary['incomplete_reason_count']}")
    print(f"Recommended next  : {summary['recommended_next_phase']}")
    print(f"JSON              : {summary['json_path']}")
    print(f"Markdown          : {summary['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "HUMAN.CLOSE: write a report-only checkpoint freezing HUMAN.N1-N4 "
            "before runtime enforcement or approval-gate work."
        )
    )
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root.")
    parser.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH), help="Phase registry path.")
    parser.add_argument("--boundary-map-path", default=str(DEFAULT_BOUNDARY_MAP_PATH), help="HUMAN.N1 artifact path.")
    parser.add_argument("--token-contract-path", default=str(DEFAULT_TOKEN_CONTRACT_PATH), help="HUMAN.N2 artifact path.")
    parser.add_argument(
        "--dry-run-validator-path",
        default=str(DEFAULT_DRY_RUN_VALIDATOR_PATH),
        help="HUMAN.N3 dry-run validator source path.",
    )
    parser.add_argument("--sample-catalog-path", default=str(DEFAULT_SAMPLE_CATALOG_PATH), help="HUMAN.N4 artifact path.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument("--report-id", default="", help="Optional deterministic report id.")
    parser.add_argument("--created-at", default="", help="Optional created-at timestamp.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_human_authority_branch_checkpoint(
        repo_root=args.repo_root,
        registry_path=args.registry_path,
        boundary_map_path=args.boundary_map_path,
        token_contract_path=args.token_contract_path,
        dry_run_validator_path=args.dry_run_validator_path,
        sample_catalog_path=args.sample_catalog_path,
        output_dir=args.output_dir,
        report_id=args.report_id,
        created_at=args.created_at,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    status = result["summary"]["checkpoint_status"]
    return 0 if status in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
