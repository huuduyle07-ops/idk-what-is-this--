"""CMD.3 - Create a Budget Governor Preview (CLI).

Reads an optional CMD.1 Commander Run Contract and optional CMD.2 Task
Decomposition Preview, then writes deterministic JSON and Markdown budget
governor preview artifacts.

This tool is report-only. It does not enforce budgets, execute tasks, run
agents, call models, apply patches, run validation, run benchmarks, contact
network services, launch workers, write to a database, push, merge, or open PRs.
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

from core.commander_budget_governor import (  # noqa: E402
    BUDGET_GOVERNOR_GUARDRAIL_NOTE,
    read_source_contract,
    read_source_decomposition,
    write_budget_governor_preview,
)


DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "commander" / "budget_previews")


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _default_preview_id(created_iso: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'preview'}_budget-governor-preview"


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    preview = result["preview"]
    scope = preview.get("estimated_scope") or {}
    budget = preview.get("budget_summary") or {}
    limits = preview.get("budget_limits") or {}
    return {
        "ok": bool(result.get("ok")),
        "preview_id": preview.get("preview_id"),
        "created_at": preview.get("created_at"),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "source_contract_path": preview.get("source_contract_path"),
        "source_decomposition_path": preview.get("source_decomposition_path"),
        "task": preview.get("task"),
        "budget_status": preview.get("budget_status"),
        "budget_summary": {
            "estimated_files_touched": scope.get("estimated_files_touched"),
            "estimated_lines_changed": scope.get("estimated_lines_changed"),
            "estimated_minutes": scope.get("estimated_minutes"),
            "phase_count": scope.get("phase_count"),
            "limit_classification": budget.get("limit_classification"),
            "human_reapproval_required": bool(budget.get("human_reapproval_required")),
        },
        "budget_limits": {
            "max_files": limits.get("max_files"),
            "max_lines": limits.get("max_lines"),
            "max_minutes": limits.get("max_minutes"),
        },
        "escalation_rule_count": len(preview.get("escalation_rules") or []),
        "stop_conditions": preview.get("stop_conditions") or [],
        "human_checkpoints": [
            checkpoint.get("checkpoint_id")
            for checkpoint in preview.get("human_approval_checkpoints") or []
        ],
        "warnings": preview.get("warnings") or [],
        "blockers": preview.get("blockers") or [],
    }


def run_create_commander_budget_governor(
    *,
    repo_path: str = ".",
    contract: str | None = None,
    decomposition: str | None = None,
    task: str = "",
    max_files: int = 5,
    max_lines: int = 150,
    max_minutes: int = 60,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    preview_id: str | None = None,
    created_at: str | float | None = None,
) -> dict[str, Any]:
    """Create the CMD.3 preview and return artifact paths plus the preview."""
    created_iso = _resolve_created_at(created_at)
    final_preview_id = preview_id or _default_preview_id(created_iso)
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

    result = write_budget_governor_preview(
        output_root=output_root,
        task=task,
        repo_path=repo_path,
        source_contract=source_contract,
        source_contract_path=contract_path,
        source_contract_error=contract_error,
        source_decomposition=source_decomposition,
        source_decomposition_path=decomposition_path,
        source_decomposition_error=decomposition_error,
        max_files=max_files,
        max_lines=max_lines,
        max_minutes=max_minutes,
        preview_id=final_preview_id,
        created_at=created_iso,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    budget = summary["budget_summary"]
    limits = summary["budget_limits"]
    print("CMD.3 - Budget Governor Preview")
    print("=" * 35)
    print(f"Preview id      : {summary['preview_id']}")
    print(f"Source contract : {summary['source_contract_path'] or '(none)'}")
    print(f"Source decomp   : {summary['source_decomposition_path'] or '(none)'}")
    print(f"Budget status   : {summary['budget_status']}")
    print(
        "Estimate        : "
        f"{budget['estimated_files_touched']} files, "
        f"{budget['estimated_lines_changed']} lines, "
        f"{budget['estimated_minutes']} minutes"
    )
    print(
        "Limits          : "
        f"{limits['max_files']} files, {limits['max_lines']} lines, {limits['max_minutes']} minutes"
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
    print(f"\n> {BUDGET_GOVERNOR_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "CMD.3: write a report-only Budget Governor Preview from a CMD.1 "
            "contract, CMD.2 decomposition preview, or task text."
        )
    )
    parser.add_argument("--repo-path", default=".", help="Repository path for the task context.")
    parser.add_argument("--contract", default=None, help="Optional CMD.1 contract JSON path.")
    parser.add_argument("--decomposition", default=None, help="Optional CMD.2 decomposition preview JSON path.")
    parser.add_argument("--task", default="", help="Plain-text task description; fallback when no source supplies one.")
    parser.add_argument("--max-files", type=int, default=5, help="Maximum files allowed before human reapproval.")
    parser.add_argument("--max-lines", type=int, default=150, help="Maximum changed lines allowed before human reapproval.")
    parser.add_argument("--max-minutes", type=int, default=60, help="Maximum minutes allowed before human reapproval.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory to write preview artifacts into.")
    parser.add_argument("--preview-id", default=None, help="Deterministic preview id and artifact stem.")
    parser.add_argument("--created-at", default=None, help="Deterministic created-at string or epoch seconds.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_commander_budget_governor(
        repo_path=args.repo_path,
        contract=args.contract,
        decomposition=args.decomposition,
        task=args.task,
        max_files=args.max_files,
        max_lines=args.max_lines,
        max_minutes=args.max_minutes,
        output_root=args.output_root,
        preview_id=args.preview_id,
        created_at=args.created_at,
    )

    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
