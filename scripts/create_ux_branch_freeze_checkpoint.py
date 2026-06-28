"""UX.CLOSE — Create UX Branch Freeze Checkpoint (CLI).

Reads the phase registry, the UX.11 behavior preservation report (built from
local source text), integration evidence, and documentation, then writes a
deterministic JSON + Markdown checkpoint under the output root.

Report-only: it audits the completed UX branch without choosing work, executing
phases, calling models, applying patches, running a validation command, running a
benchmark check, contacting network services, launching workers, writing to a
database, adding a backend or mutation route, changing UI behavior, blocking
execution, pushing, merging, or opening PRs.

Exit codes: 0 when checkpoint_status is ``pass`` (or ``pass_with_warnings`` with
``--allow-warnings``); nonzero when ``blocked`` (or ``pass_with_warnings``
without ``--allow-warnings``).

Usage:
    python scripts/create_ux_branch_freeze_checkpoint.py \\
        --repo-path . \\
        --registry docs/roadmap/phase_registry.json \\
        --json --allow-warnings
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

from core.ux_branch_freeze_checkpoint import (  # noqa: E402
    GUARDRAIL_NOTE,
    STATUS_BLOCKED,
    STATUS_WARN,
    write_ux_branch_freeze_checkpoint,
)

DEFAULT_REPO_PATH = "."
DEFAULT_REGISTRY = "docs/roadmap/phase_registry.json"
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "ux" / "ux_branch_freeze_checkpoint")


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
    return f"{stamp or 'report'}_ux-branch-freeze-checkpoint"


def run_create_ux_branch_freeze_checkpoint(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    registry: str = DEFAULT_REGISTRY,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | float | None = None,
) -> dict[str, Any]:
    """Build and write the UX.CLOSE checkpoint. Returns {ok, json_path, md_path, report, checkpoint_status}."""
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)
    result = write_ux_branch_freeze_checkpoint(
        repo_path,
        registry,
        output_root,
        report_id=final_report_id,
        created_at=created_iso,
    )
    result["checkpoint_status"] = result["report"].get("checkpoint_status")
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    print("UX.CLOSE — UX Branch Freeze Checkpoint")
    print("=" * 40)
    print(f"Report id          : {report.get('report_id')}")
    print(f"Repo path          : {report.get('repo_path')}")
    print(f"Registry           : {report.get('registry_path')}")
    print(f"Checkpoint status  : {report.get('checkpoint_status')}")
    print(f"Checkpoint reason  : {report.get('checkpoint_reason')}")
    print(f"Recommended next   : {report.get('recommended_next_step')}")
    print(f"Next branch        : {report.get('recommended_next_branch')}")
    arc = report.get("ux_arc_summary") or {}
    print(f"UX arc complete    : {arc.get('all_complete')}")
    bp = report.get("behavior_preservation_summary") or {}
    print(f"Preservation status: {bp.get('status')}")
    print(f"Freeze criteria ok : {report.get('all_freeze_criteria_satisfied')}")
    for b in report.get("blockers") or []:
        print(f"  BLOCKER: {b}")
    for w in report.get("warnings") or []:
        print(f"  WARNING: {w}")
    print(f"JSON               : {result['json_path']}")
    print(f"Markdown           : {result['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "UX.CLOSE: read the phase registry, the UX.11 behavior preservation report, "
            "integration evidence, and docs and write a freeze checkpoint for the UX "
            "branch. Report-only."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY, help="Path to registry JSON.")
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
        help="Exit 0 even when checkpoint_status is 'pass_with_warnings'.",
    )
    args = parser.parse_args(argv)

    result = run_create_ux_branch_freeze_checkpoint(
        repo_path=args.repo_path,
        registry=args.registry,
        output_root=args.output_root,
        report_id=args.report_id,
        created_at=args.created_at,
    )

    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=True, sort_keys=True))
    else:
        _print_summary(result)

    status = result["checkpoint_status"]
    if status == STATUS_BLOCKED:
        return 1
    if status == STATUS_WARN and not args.allow_warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
