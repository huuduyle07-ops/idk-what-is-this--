"""Create the UX.9 unified Workbench input plan artifacts."""
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

from core.unified_workbench_input_plan import (  # noqa: E402
    REPORT_KIND,
    build_unified_workbench_input_plan,
    demo_notes,
    write_unified_workbench_input_artifacts,
)

DEFAULT_REPO_PATH = "."
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "ux" / "unified_workbench_input_plan")


def _created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    return str(raw)


def run_create_unified_workbench_input_plan(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    plan_id: str | None = None,
    created_at: str | None = None,
    demo: bool = False,
) -> dict[str, Any]:
    """Build and write the UX.9 plan report."""
    report = build_unified_workbench_input_plan(
        repo_path=repo_path,
        created_at=_created_at(created_at),
        plan_id=plan_id,
    )
    if demo:
        report["demo_notes"] = demo_notes()
    return write_unified_workbench_input_artifacts(report, output_root)


def _button_reduction_summary(report: dict[str, Any]) -> list[str]:
    return [item["summary"] for item in report.get("button_reduction_plan", [])]


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    return {
        "report_kind": report.get("report_kind", REPORT_KIND),
        "plan_id": report.get("plan_id"),
        "plan_status": report.get("plan_status"),
        "recommended_next_phase": report.get("recommended_next_phase"),
        "button_reduction_summary": _button_reduction_summary(report),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
    }


def _print_text_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    print("UX.9 - Unified Workbench Input Plan")
    print("=" * 39)
    print(f"Plan id    : {report.get('plan_id')}")
    print(f"Repo path  : {report.get('repo_path')}")
    print(f"Status     : {report.get('plan_status')}")
    print(f"Next phase : {report.get('recommended_next_phase')}")
    print(f"JSON       : {result.get('json_path')}")
    print(f"Markdown   : {result.get('md_path')}")
    print()
    print("Button reduction:")
    for item in _button_reduction_summary(report):
        print(f"  - {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="UX.9 unified Workbench input plan generator"
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--plan-id", default=None)
    parser.add_argument("--created-at", default=None)
    parser.add_argument("--demo", action="store_true", default=False)
    parser.add_argument("--json", dest="json_out", action="store_true", default=False)
    args = parser.parse_args(argv)

    result = run_create_unified_workbench_input_plan(
        repo_path=args.repo_path,
        output_root=args.output_root,
        plan_id=args.plan_id,
        created_at=args.created_at,
        demo=args.demo,
    )
    if args.json_out:
        print(json.dumps(_summary(result), indent=2))
    else:
        _print_text_summary(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
