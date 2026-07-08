#!/usr/bin/env python
"""Create HARDEN.N3 - Approval Enforcement Dry-Run Gate Simulator.

Writes a report-only simulator for sample approval-gate decisions. It does not
enforce gates, validate live tokens, issue or consume tokens, change auth or
routes, call models, launch workers, invoke tools, apply patches, or run
validation or benchmarks as part of report generation.
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

from core.approval_enforcement_dry_run_gate_simulator import (  # noqa: E402
    DEFAULT_ATTACHMENT_PLAN_PATH,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_SAMPLE_CATALOG_PATH,
    DEFAULT_TOKEN_CONTRACT_PATH,
    DEFAULT_TOKEN_DRY_RUN_VALIDATOR_PATH,
    GUARDRAIL_NOTE,
    STATUS_READY,
    STATUS_READY_WITH_WARNINGS,
    write_approval_enforcement_dry_run_gate_simulator,
)


def _load_optional_json(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return data


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "simulator_status": report.get("simulator_status"),
        "sample_scenario_count": int(report.get("sample_scenario_count") or 0),
        "simulation_result_count": len(report.get("simulation_results") or []),
        "enforcement_was_applied": bool(report.get("enforcement_was_applied")),
        "sample_tokens_treated_as_real_authority": bool(report.get("sample_tokens_treated_as_real_authority")),
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "incomplete_reason_count": len(report.get("incomplete_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_approval_enforcement_dry_run_gate_simulator(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    source_attachment_plan_path: str | Path = DEFAULT_ATTACHMENT_PLAN_PATH,
    source_token_contract_path: str | Path = DEFAULT_TOKEN_CONTRACT_PATH,
    source_token_dry_run_validator_path: str | Path = DEFAULT_TOKEN_DRY_RUN_VALIDATOR_PATH,
    source_sample_catalog_path: str | Path = DEFAULT_SAMPLE_CATALOG_PATH,
    sample_action_request_path: str | Path | None = None,
    sample_approval_token_path: str | Path | None = None,
    sample_action_request: dict[str, Any] | None = None,
    sample_approval_token: dict[str, Any] | None = None,
    simulation_id: str = "",
    created_at: str = "",
    now: str = "",
) -> dict[str, Any]:
    """Create HARDEN.N3 simulator artifacts and return paths plus summary."""
    request = sample_action_request if sample_action_request is not None else _load_optional_json(sample_action_request_path)
    token = sample_approval_token if sample_approval_token is not None else _load_optional_json(sample_approval_token_path)
    result = write_approval_enforcement_dry_run_gate_simulator(
        repo_root=repo_root,
        output_dir=output_dir,
        source_attachment_plan_path=source_attachment_plan_path,
        source_token_contract_path=source_token_contract_path,
        source_token_dry_run_validator_path=source_token_dry_run_validator_path,
        source_sample_catalog_path=source_sample_catalog_path,
        sample_action_request=request,
        sample_approval_token=token,
        simulation_id=simulation_id,
        created_at=created_at,
        now=now,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("HARDEN.N3 - Approval Enforcement Dry-Run Gate Simulator")
    print("=" * 63)
    print(f"Simulator status  : {summary['simulator_status']}")
    print(f"Sample scenarios  : {summary['sample_scenario_count']}")
    print(f"Simulation results: {summary['simulation_result_count']}")
    print(f"Enforcement       : {summary['enforcement_was_applied']}")
    print(f"Tokens authority  : {summary['sample_tokens_treated_as_real_authority']}")
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
            "HARDEN.N3: write a report-only simulator for sample approval-gate "
            "decisions without adding runtime enforcement."
        )
    )
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory.")
    parser.add_argument("--attachment-plan-path", default=str(DEFAULT_ATTACHMENT_PLAN_PATH), help="HARDEN.N2 artifact.")
    parser.add_argument("--token-contract-path", default=str(DEFAULT_TOKEN_CONTRACT_PATH), help="HUMAN.N2 artifact.")
    parser.add_argument(
        "--token-dry-run-validator-path",
        default=str(DEFAULT_TOKEN_DRY_RUN_VALIDATOR_PATH),
        help="Optional HUMAN.N3 validator source marker.",
    )
    parser.add_argument("--sample-catalog-path", default=str(DEFAULT_SAMPLE_CATALOG_PATH), help="Optional HUMAN.N4 catalog.")
    parser.add_argument("--sample-action-request-path", default=None, help="Optional sample action request JSON.")
    parser.add_argument("--sample-approval-token-path", default=None, help="Optional sample approval token JSON.")
    parser.add_argument("--simulation-id", default="", help="Optional deterministic simulation id.")
    parser.add_argument("--created-at", default="", help="Optional created-at timestamp.")
    parser.add_argument("--now", default="", help="Optional deterministic simulation clock.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_approval_enforcement_dry_run_gate_simulator(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        source_attachment_plan_path=args.attachment_plan_path,
        source_token_contract_path=args.token_contract_path,
        source_token_dry_run_validator_path=args.token_dry_run_validator_path,
        source_sample_catalog_path=args.sample_catalog_path,
        sample_action_request_path=args.sample_action_request_path,
        sample_approval_token_path=args.sample_approval_token_path,
        simulation_id=args.simulation_id,
        created_at=args.created_at,
        now=args.now,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    status = result["summary"]["simulator_status"]
    return 0 if status in {STATUS_READY, STATUS_READY_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
