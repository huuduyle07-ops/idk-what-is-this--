"""CMD.2 - Create a Task Decomposition Preview (CLI).

Reads an optional CMD.1 Commander Run Contract or accepts direct task text, then
writes deterministic JSON and Markdown decomposition preview artifacts.

This tool is report-only. It does not execute the decomposition, run agents, call
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

from core.commander_task_decomposition import (  # noqa: E402
    TASK_DECOMPOSITION_GUARDRAIL_NOTE,
    read_source_contract,
    write_task_decomposition_preview,
)


DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "commander" / "decomposition_previews")


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
    return f"{stamp or 'preview'}_task-decomposition-preview"


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    preview = result["preview"]
    evidence = preview.get("evidence_plan_preview") or {}
    validation = preview.get("validation_plan_preview") or {}
    benchmark = preview.get("benchmark_plan_preview") or {}
    budget = preview.get("budget_plan_preview") or {}
    rollback = preview.get("rollback_plan_preview") or {}
    checkpoint = preview.get("human_checkpoint_preview") or {}
    return {
        "ok": bool(result.get("ok")),
        "preview_id": preview.get("preview_id"),
        "created_at": preview.get("created_at"),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "source_contract_path": preview.get("source_contract_path"),
        "task": preview.get("task"),
        "source_mode": preview.get("source_mode"),
        "phase_count": len(preview.get("phase_plan_preview") or []),
        "evidence_plan_summary": {
            "changed_file_count": len(evidence.get("changed_files") or []),
            "artifact_count": len(evidence.get("generated_artifacts") or []),
        },
        "validation_plan_summary": {
            "text_only": bool(validation.get("text_only")),
            "command_count": len(validation.get("commands") or []),
        },
        "benchmark_plan_summary": {
            "text_only": bool(benchmark.get("text_only")),
            "command_count": len(benchmark.get("commands") or []),
        },
        "budget_plan_summary": {
            "estimated_files_touched": budget.get("estimated_files_touched"),
            "estimated_lines_changed": budget.get("estimated_lines_changed"),
            "estimated_human_review_cost": budget.get("estimated_human_review_cost"),
            "estimated_validation_cost": budget.get("estimated_validation_cost"),
        },
        "rollback_plan_summary": {
            "step_count": len(rollback.get("steps") or []),
            "auto_rollback_allowed": bool(rollback.get("auto_rollback_allowed")),
        },
        "human_checkpoints": checkpoint.get("checkpoints") or [],
        "warnings": preview.get("warnings") or [],
        "blockers": preview.get("blockers") or [],
    }


def run_create_commander_task_decomposition(
    *,
    repo_path: str = ".",
    contract: str | None = None,
    task: str = "",
    max_phases: int = 5,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    preview_id: str | None = None,
    created_at: str | float | None = None,
) -> dict[str, Any]:
    """Create the CMD.2 preview and return artifact paths plus the preview."""
    created_iso = _resolve_created_at(created_at)
    final_preview_id = preview_id or _default_preview_id(created_iso)
    source_contract = None
    contract_error = ""
    contract_path = str(contract or "")
    if contract:
        source_contract, contract_error = read_source_contract(contract)

    result = write_task_decomposition_preview(
        output_root=output_root,
        task=task,
        repo_path=repo_path,
        source_contract=source_contract,
        source_contract_path=contract_path,
        source_contract_error=contract_error,
        max_phases=max_phases,
        preview_id=final_preview_id,
        created_at=created_iso,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("CMD.2 - Task Decomposition Preview")
    print("=" * 36)
    print(f"Preview id      : {summary['preview_id']}")
    print(f"Source contract : {summary['source_contract_path'] or '(none)'}")
    print(f"Source mode     : {summary['source_mode']}")
    print(f"Phase count     : {summary['phase_count']}")
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
    print(f"\n> {TASK_DECOMPOSITION_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "CMD.2: write a report-only Task Decomposition Preview from a CMD.1 "
            "contract or task text. It only writes JSON/Markdown preview artifacts."
        )
    )
    parser.add_argument("--repo-path", default=".", help="Repository path for the task context.")
    parser.add_argument("--contract", default=None, help="Optional CMD.1 contract JSON path.")
    parser.add_argument("--task", default="", help="Plain-text task description; optional when --contract is provided.")
    parser.add_argument("--max-phases", type=int, default=5, help="Maximum number of preview phases to emit.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory to write preview artifacts into.")
    parser.add_argument("--preview-id", default=None, help="Deterministic preview id and artifact stem.")
    parser.add_argument("--created-at", default=None, help="Deterministic created-at string or epoch seconds.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_commander_task_decomposition(
        repo_path=args.repo_path,
        contract=args.contract,
        task=args.task,
        max_phases=args.max_phases,
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
