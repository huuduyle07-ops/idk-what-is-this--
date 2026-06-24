"""UX.1 — Create Operator Cockpit & Idea Intake Plan (CLI).

Builds a deterministic UX planning report that defines the C.A.T.T.U.S operator
cockpit and idea intake system, and writes JSON + Markdown under the output root.

Report-only: plans the cockpit without implementing the UI, changing backend
behavior, executing tasks, running agents, calling models, applying patches, running
validation or benchmarks, contacting network services, launching workers, pushing,
merging, or opening PRs.

Exit codes: 0 when plan_status is ``ready_for_review``; nonzero when ``blocked``.

Usage:
    python scripts/create_operator_cockpit_plan.py \\
        --repo-path . \\
        --output-root .agent/ux/operator_cockpit_plan \\
        --include-default-problems \\
        --include-default-ideas \\
        --json
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

from core.operator_cockpit_plan import (  # noqa: E402
    GUARDRAIL_NOTE,
    PLAN_STATUS_READY,
    REPORT_KIND,
    write_operator_cockpit_plan,
)

DEFAULT_REPO_PATH = "."
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "ux" / "operator_cockpit_plan")


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _default_plan_id(created_iso: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'plan'}_operator-cockpit-plan"


def run_create_operator_cockpit_plan(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    plan_id: str | None = None,
    created_at: str | float | None = None,
    extra_problems: list[str] | None = None,
    extra_ideas: list[str] | None = None,
    include_default_problems: bool = True,
    include_default_ideas: bool = True,
) -> dict[str, Any]:
    """Build and write the UX.1 plan. Returns {ok, json_path, md_path, report, plan_status}."""
    created_iso = _resolve_created_at(created_at)
    final_plan_id = plan_id or _default_plan_id(created_iso)
    result = write_operator_cockpit_plan(
        repo_path,
        output_root,
        plan_id=final_plan_id,
        created_at=created_iso,
        extra_problems=extra_problems,
        extra_ideas=extra_ideas,
        include_default_problems=include_default_problems,
        include_default_ideas=include_default_ideas,
    )
    result["plan_status"] = result["report"].get("plan_status")
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    board = report.get("idea_intake_board", {})
    print("UX.1 — Operator Cockpit & Idea Intake Plan")
    print("=" * 42)
    print(f"Plan id            : {report.get('plan_id')}")
    print(f"Repo path          : {report.get('repo_path')}")
    print(f"Plan status        : {report.get('plan_status')}")
    probs = report.get("ux_problem_inventory", [])
    print(f"Problems           : {len(probs)}")
    roadmap = report.get("ux_roadmap", [])
    print(f"UX roadmap phases  : {len(roadmap)}")
    print(f"Idea board — use_now         : {len(board.get('use_now', []))}")
    print(f"Idea board — prototype_later : {len(board.get('prototype_later', []))}")
    print(f"Idea board — park            : {len(board.get('park', []))}")
    print(f"Idea board — block           : {len(board.get('block', []))}")
    warnings = report.get("warnings", [])
    blockers = report.get("blockers", [])
    print(f"Warnings           : {len(warnings)}")
    print(f"Blockers           : {len(blockers)}")
    print(f"JSON               : {result.get('json_path')}")
    print(f"Markdown           : {result.get('md_path')}")
    print()
    print("Boundaries (UX.1 does not):")
    for b in report.get("boundaries", []):
        print(f"  {b}")
    print()
    print(f"Guardrail note: {report.get('guardrail_note', GUARDRAIL_NOTE)[:120]}...")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="UX.1 — Create Operator Cockpit & Idea Intake Plan (report-only)"
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--plan-id", default=None)
    parser.add_argument("--created-at", default=None)
    parser.add_argument("--problem", dest="problems", action="append", default=[])
    parser.add_argument("--idea", dest="ideas", action="append", default=[])
    parser.add_argument("--include-default-problems", action="store_true", default=False)
    parser.add_argument("--include-default-ideas", action="store_true", default=False)
    parser.add_argument("--json", dest="json_out", action="store_true", default=False)

    args = parser.parse_args(argv)

    result = run_create_operator_cockpit_plan(
        repo_path=args.repo_path,
        output_root=args.output_root,
        plan_id=args.plan_id,
        created_at=args.created_at,
        extra_problems=args.problems or [],
        extra_ideas=args.ideas or [],
        include_default_problems=args.include_default_problems,
        include_default_ideas=args.include_default_ideas,
    )

    if args.json_out:
        report = result["report"]
        summary = {
            "report_kind": report.get("report_kind", REPORT_KIND),
            "plan_id": report.get("plan_id"),
            "plan_status": report.get("plan_status"),
            "problem_count": len(report.get("ux_problem_inventory", [])),
            "roadmap_phase_count": len(report.get("ux_roadmap", [])),
            "idea_board_summary": {
                bucket: len(report.get("idea_intake_board", {}).get(bucket, []))
                for bucket in ("use_now", "prototype_later", "park", "block")
            },
            "warning_count": len(report.get("warnings", [])),
            "blocker_count": len(report.get("blockers", [])),
            "json_path": result.get("json_path"),
            "md_path": result.get("md_path"),
        }
        print(json.dumps(summary, indent=2))
    else:
        _print_summary(result)

    plan_status = result.get("plan_status", "")
    return 0 if plan_status == PLAN_STATUS_READY else 1


if __name__ == "__main__":
    sys.exit(main())
