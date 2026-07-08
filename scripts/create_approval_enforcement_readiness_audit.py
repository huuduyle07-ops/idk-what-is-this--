#!/usr/bin/env python
"""Create HARDEN.N1 - Approval Enforcement Readiness Audit.

Writes a report-only audit that maps dangerous action categories to future
HUMAN.N2 approval-token requirements. It does not add approval enforcement,
validate tokens, block routes, change auth policy, call models, launch workers,
invoke tools, run validation or benchmarks, apply patches, or approve/reject
work.
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

from core.approval_enforcement_readiness_audit import (  # noqa: E402
    DEFAULT_APPROVAL_CONTRACT_PATH,
    DEFAULT_DRY_RUN_VALIDATOR_PATH,
    DEFAULT_HUMAN_BOUNDARY_PATH,
    DEFAULT_HUMAN_CHECKPOINT_PATH,
    DEFAULT_MODEL_ADOPTION_CHECKPOINT_PATH,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_REGISTRY_PATH,
    DEFAULT_SAMPLE_CATALOG_PATH,
    GUARDRAIL_NOTE,
    STATUS_READY,
    STATUS_READY_WITH_WARNINGS,
    write_approval_enforcement_readiness_audit,
)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "audit_status": report.get("audit_status"),
        "action_surface_count": int(report.get("action_surface_count") or 0),
        "mapped_action_count": int(report.get("mapped_action_count") or 0),
        "unmapped_action_count": int(report.get("unmapped_action_count") or 0),
        "enforcement_not_implemented_confirmed": bool(report.get("enforcement_not_implemented_confirmed")),
        "missing_approval_mappings": list(report.get("missing_approval_mappings") or []),
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "incomplete_reason_count": len(report.get("incomplete_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_approval_enforcement_readiness_audit(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    source_human_boundary_path: str | Path = DEFAULT_HUMAN_BOUNDARY_PATH,
    source_approval_contract_path: str | Path = DEFAULT_APPROVAL_CONTRACT_PATH,
    source_human_checkpoint_path: str | Path = DEFAULT_HUMAN_CHECKPOINT_PATH,
    source_dry_run_validator_path: str | Path = DEFAULT_DRY_RUN_VALIDATOR_PATH,
    source_sample_catalog_path: str | Path = DEFAULT_SAMPLE_CATALOG_PATH,
    source_model_adoption_checkpoint_path: str | Path = DEFAULT_MODEL_ADOPTION_CHECKPOINT_PATH,
    audit_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Create HARDEN.N1 audit artifacts and return paths plus summary."""
    result = write_approval_enforcement_readiness_audit(
        repo_root=repo_root,
        output_dir=output_dir,
        registry_path=registry_path,
        source_human_boundary_path=source_human_boundary_path,
        source_approval_contract_path=source_approval_contract_path,
        source_human_checkpoint_path=source_human_checkpoint_path,
        source_dry_run_validator_path=source_dry_run_validator_path,
        source_sample_catalog_path=source_sample_catalog_path,
        source_model_adoption_checkpoint_path=source_model_adoption_checkpoint_path,
        audit_id=audit_id,
        created_at=created_at,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("HARDEN.N1 - Approval Enforcement Readiness Audit")
    print("=" * 55)
    print(f"Audit status      : {summary['audit_status']}")
    print(f"Action surfaces   : {summary['action_surface_count']}")
    print(f"Mapped actions    : {summary['mapped_action_count']}")
    print(f"Unmapped actions  : {summary['unmapped_action_count']}")
    print(f"No enforcement    : {summary['enforcement_not_implemented_confirmed']}")
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
            "HARDEN.N1: write a report-only audit mapping dangerous action "
            "surfaces to future HUMAN.N2 approval-token requirements."
        )
    )
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH), help="Phase registry path.")
    parser.add_argument("--human-boundary-path", default=str(DEFAULT_HUMAN_BOUNDARY_PATH), help="HUMAN.N1 artifact.")
    parser.add_argument(
        "--approval-contract-path",
        default=str(DEFAULT_APPROVAL_CONTRACT_PATH),
        help="HUMAN.N2 artifact.",
    )
    parser.add_argument("--human-checkpoint-path", default=str(DEFAULT_HUMAN_CHECKPOINT_PATH), help="HUMAN.CLOSE artifact.")
    parser.add_argument(
        "--dry-run-validator-path",
        default=str(DEFAULT_DRY_RUN_VALIDATOR_PATH),
        help="HUMAN.N3 validator source marker.",
    )
    parser.add_argument("--sample-catalog-path", default=str(DEFAULT_SAMPLE_CATALOG_PATH), help="HUMAN.N4 artifact.")
    parser.add_argument(
        "--model-adoption-checkpoint-path",
        default=str(DEFAULT_MODEL_ADOPTION_CHECKPOINT_PATH),
        help="ADOPT.MODEL.CLOSE artifact.",
    )
    parser.add_argument("--audit-id", default="", help="Optional deterministic audit id.")
    parser.add_argument("--created-at", default="", help="Optional created-at timestamp.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_approval_enforcement_readiness_audit(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        registry_path=args.registry_path,
        source_human_boundary_path=args.human_boundary_path,
        source_approval_contract_path=args.approval_contract_path,
        source_human_checkpoint_path=args.human_checkpoint_path,
        source_dry_run_validator_path=args.dry_run_validator_path,
        source_sample_catalog_path=args.sample_catalog_path,
        source_model_adoption_checkpoint_path=args.model_adoption_checkpoint_path,
        audit_id=args.audit_id,
        created_at=args.created_at,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    status = result["summary"]["audit_status"]
    return 0 if status in {STATUS_READY, STATUS_READY_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
