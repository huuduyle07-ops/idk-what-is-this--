"""CMD.1 - Create a Commander Run Contract (CLI).

Accepts a task description and optional context fields, then writes deterministic
JSON and Markdown artifacts classifying the task as instant_run, commander_run,
needs_clarification, or reject_or_defer.

This tool is report-only. It does not execute Commander Mode, run agents, call
models, apply patches, run validation, run benchmarks, contact network services,
launch workers, write to a database, push, merge, or open PRs.
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

from core.commander_run_contract import (  # noqa: E402
    COMMANDER_RUN_CONTRACT_GUARDRAIL_NOTE,
    write_commander_run_contract,
)


DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "commander" / "contracts")


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _default_contract_id(created_iso: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'contract'}_commander-run-contract"


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    contract = result["contract"]
    return {
        "ok": bool(result.get("ok")),
        "contract_id": contract.get("contract_id"),
        "created_at": contract.get("created_at"),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "recommended_mode": contract.get("recommended_mode"),
        "risk_level": contract.get("risk_level"),
        "complexity_level": contract.get("complexity_level"),
        "complexity_score": contract.get("complexity_score"),
        "required_gates": contract.get("required_gates") or [],
        "stop_conditions": contract.get("stop_conditions") or [],
        "warnings": contract.get("warnings") or [],
        "blockers": contract.get("blockers") or [],
    }


def run_create_commander_run_contract(
    *,
    repo_path: str = ".",
    task: str,
    changed_files: list[str] | None = None,
    estimated_files_touched: int | None = None,
    estimated_lines_changed: int | None = None,
    requires_network: bool = False,
    requires_model_calls: bool = False,
    requires_validation: bool = False,
    requires_benchmark: bool = False,
    requires_patch: bool = False,
    requires_remote_action: bool = False,
    time_budget_minutes: int | None = None,
    risk_notes: list[str] | None = None,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    contract_id: str | None = None,
    created_at: str | float | None = None,
) -> dict[str, Any]:
    """Create the CMD.1 contract and return artifact paths plus the contract."""
    created_iso = _resolve_created_at(created_at)
    final_contract_id = contract_id or _default_contract_id(created_iso)
    result = write_commander_run_contract(
        output_root=output_root,
        task=task,
        repo_path=repo_path,
        changed_files=changed_files or [],
        estimated_files_touched=estimated_files_touched,
        estimated_lines_changed=estimated_lines_changed,
        requires_network=requires_network,
        requires_model_calls=requires_model_calls,
        requires_validation=requires_validation,
        requires_benchmark=requires_benchmark,
        requires_patch=requires_patch,
        requires_remote_action=requires_remote_action,
        time_budget_minutes=time_budget_minutes,
        risk_notes=risk_notes or [],
        contract_id=final_contract_id,
        created_at=created_iso,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("CMD.1 - Commander Run Contract")
    print("=" * 32)
    print(f"Contract id     : {summary['contract_id']}")
    print(f"Recommended mode: {summary['recommended_mode']}")
    print(f"Risk level      : {summary['risk_level']}")
    print(f"Complexity      : {summary['complexity_level']} ({summary['complexity_score']})")
    print(f"Required gates  : {', '.join(summary['required_gates']) or '(none)'}")
    blockers = summary["blockers"]
    if blockers:
        print("Blockers        :")
        for blocker in blockers:
            print(f"  - {blocker}")
    warnings = summary["warnings"]
    if warnings:
        print("Warnings        :")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"JSON            : {summary['json_path']}")
    print(f"Markdown        : {summary['md_path']}")
    print(f"\n> {COMMANDER_RUN_CONTRACT_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "CMD.1: write a report-only Commander Run Contract that classifies a task "
            "as instant_run, commander_run, needs_clarification, or reject_or_defer."
        )
    )
    parser.add_argument("--repo-path", default=".", help="Repository path for the task context.")
    parser.add_argument("--task", required=True, help="Plain-text task description to classify.")
    parser.add_argument("--changed-file", action="append", default=[], help="Changed file path; repeatable.")
    parser.add_argument("--estimated-files-touched", type=int, default=None, help="Estimated number of files touched.")
    parser.add_argument("--estimated-lines-changed", type=int, default=None, help="Estimated number of changed lines.")
    parser.add_argument("--requires-network", action="store_true", help="Future task would require network access.")
    parser.add_argument("--requires-model-calls", action="store_true", help="Future task would require model calls.")
    parser.add_argument("--requires-validation", action="store_true", help="Future task would require validation.")
    parser.add_argument("--requires-benchmark", action="store_true", help="Future task would require benchmark checks.")
    parser.add_argument("--requires-patch", action="store_true", help="Future task would require patch work.")
    parser.add_argument("--requires-remote-action", action="store_true", help="Future task would require remote action.")
    parser.add_argument("--time-budget-minutes", type=int, default=None, help="Future task time budget.")
    parser.add_argument("--risk-note", action="append", default=[], help="Risk note; repeatable.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory to write contract artifacts into.")
    parser.add_argument("--contract-id", default=None, help="Deterministic contract id and artifact stem.")
    parser.add_argument("--created-at", default=None, help="Deterministic created-at string or epoch seconds.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_commander_run_contract(
        repo_path=args.repo_path,
        task=args.task,
        changed_files=args.changed_file,
        estimated_files_touched=args.estimated_files_touched,
        estimated_lines_changed=args.estimated_lines_changed,
        requires_network=args.requires_network,
        requires_model_calls=args.requires_model_calls,
        requires_validation=args.requires_validation,
        requires_benchmark=args.requires_benchmark,
        requires_patch=args.requires_patch,
        requires_remote_action=args.requires_remote_action,
        time_budget_minutes=args.time_budget_minutes,
        risk_notes=args.risk_note,
        output_root=args.output_root,
        contract_id=args.contract_id,
        created_at=args.created_at,
    )

    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
