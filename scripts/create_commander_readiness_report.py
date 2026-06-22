"""CMD.4 - Create a Commander Readiness Report (CLI).

Reads optional CMD.1, CMD.2, and CMD.3 artifacts, then writes deterministic JSON
and Markdown readiness report artifacts.

This tool is report-only. It does not execute the commander plan, run agents,
call models, apply patches, run validation, run benchmarks, contact network
services, launch workers, write to a database, push, merge, or open PRs.
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

from core.commander_readiness_report import (  # noqa: E402
    READINESS_GUARDRAIL_NOTE,
    read_source_budget,
    read_source_contract,
    read_source_decomposition,
    write_commander_readiness_report,
)


DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "commander" / "readiness_reports")


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
    return f"{stamp or 'report'}_commander-readiness-report"


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    gates = report.get("gate_summary") or {}
    budget = report.get("budget_summary") or {}
    stops = report.get("stop_condition_summary") or {}
    human = report.get("human_approval_summary") or {}
    return {
        "ok": bool(result.get("ok")),
        "report_id": report.get("report_id"),
        "created_at": report.get("created_at"),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "source_contract_path": report.get("source_contract_path"),
        "source_decomposition_path": report.get("source_decomposition_path"),
        "source_budget_path": report.get("source_budget_path"),
        "readiness_status": report.get("readiness_status"),
        "readiness_reason": report.get("readiness_reason"),
        "gate_summary": {
            "missing_gates": gates.get("missing_gates") or [],
            "human_approval_gate_present": bool(gates.get("human_approval_gate_present")),
            "all_required_gates_present": bool(gates.get("all_required_gates_present")),
        },
        "budget_summary": {
            "budget_status": budget.get("budget_status"),
            "limit_classification": budget.get("limit_classification"),
            "human_reapproval_required": bool(budget.get("human_reapproval_required")),
            "estimated_files_touched": budget.get("estimated_files_touched"),
            "estimated_lines_changed": budget.get("estimated_lines_changed"),
            "estimated_minutes": budget.get("estimated_minutes"),
        },
        "stop_condition_count": stops.get("stop_condition_count"),
        "human_approval_summary": {
            "budget_reapproval_required": bool(human.get("budget_reapproval_required")),
            "approval_status": human.get("approval_status"),
        },
        "required_before_implementation": report.get("required_before_implementation") or [],
        "warnings": report.get("warnings") or [],
        "blockers": report.get("blockers") or [],
    }


def run_create_commander_readiness_report(
    *,
    repo_path: str = ".",
    contract: str | None = None,
    decomposition: str | None = None,
    budget: str | None = None,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | float | None = None,
) -> dict[str, Any]:
    """Create the CMD.4 readiness report and return artifact paths plus report."""
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)

    source_contract = None
    contract_error = ""
    contract_path = str(contract or "")
    if contract:
        source_contract, contract_error = read_source_contract(contract)

    source_decomposition = None
    decomposition_error = ""
    decomposition_path = str(decomposition or "")
    if decomposition:
        source_decomposition, decomposition_error = read_source_decomposition(decomposition)

    source_budget = None
    budget_error = ""
    budget_path = str(budget or "")
    if budget:
        source_budget, budget_error = read_source_budget(budget)

    result = write_commander_readiness_report(
        output_root=output_root,
        repo_path=repo_path,
        source_contract=source_contract,
        source_contract_path=contract_path,
        source_contract_error=contract_error,
        source_decomposition=source_decomposition,
        source_decomposition_path=decomposition_path,
        source_decomposition_error=decomposition_error,
        source_budget=source_budget,
        source_budget_path=budget_path,
        source_budget_error=budget_error,
        report_id=final_report_id,
        created_at=created_iso,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    budget = summary["budget_summary"]
    print("CMD.4 - Commander Readiness Report")
    print("=" * 38)
    print(f"Report id       : {summary['report_id']}")
    print(f"Source contract : {summary['source_contract_path'] or '(none)'}")
    print(f"Source decomp   : {summary['source_decomposition_path'] or '(none)'}")
    print(f"Source budget   : {summary['source_budget_path'] or '(none)'}")
    print(f"Readiness       : {summary['readiness_status']}")
    print(f"Reason          : {summary['readiness_reason']}")
    print(
        "Budget          : "
        f"{budget['budget_status']} / {budget['limit_classification']} "
        f"({budget['estimated_files_touched']} files, "
        f"{budget['estimated_lines_changed']} lines, "
        f"{budget['estimated_minutes']} minutes)"
    )
    print(f"JSON            : {summary['json_path']}")
    print(f"Markdown        : {summary['md_path']}")
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
    print(f"\n> {READINESS_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "CMD.4: write a report-only Commander Readiness Report from optional "
            "CMD.1, CMD.2, and CMD.3 artifacts."
        )
    )
    parser.add_argument("--repo-path", default=".", help="Repository path for the task context.")
    parser.add_argument("--contract", default=None, help="Optional CMD.1 contract JSON path.")
    parser.add_argument("--decomposition", default=None, help="Optional CMD.2 decomposition preview JSON path.")
    parser.add_argument("--budget", default=None, help="Optional CMD.3 budget preview JSON path.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory to write readiness artifacts into.")
    parser.add_argument("--report-id", default=None, help="Deterministic report id and artifact stem.")
    parser.add_argument("--created-at", default=None, help="Deterministic created-at string or epoch seconds.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_commander_readiness_report(
        repo_path=args.repo_path,
        contract=args.contract,
        decomposition=args.decomposition,
        budget=args.budget,
        output_root=args.output_root,
        report_id=args.report_id,
        created_at=args.created_at,
    )

    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
