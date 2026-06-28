"""Create the UX.11 unified Workbench behavior preservation report."""
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

from core.unified_workbench_behavior_preservation import (  # noqa: E402
    NEXT_PHASE,
    REPORT_KIND,
    build_unified_workbench_behavior_preservation_report,
    write_unified_workbench_behavior_preservation_artifacts,
)


DEFAULT_REPO_PATH = "."
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "ux" / "unified_workbench_behavior_preservation")


def _created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    return str(raw)


def run_create_unified_workbench_behavior_preservation_report(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build and write the UX.11 preservation report."""
    return write_unified_workbench_behavior_preservation_artifacts(
        repo_path=repo_path,
        output_root=output_root,
        report_id=report_id,
        created_at=_created_at(created_at),
    )


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    return {
        "report_kind": report.get("report_kind", REPORT_KIND),
        "report_id": report.get("report_id"),
        "created_at": report.get("created_at"),
        "status": report.get("status"),
        "recommended_next_phase": report.get("recommended_next_phase", NEXT_PHASE),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
    }


def _print_text_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    print("UX.11 - Unified Workbench Behavior Preservation Check")
    print("=" * 57)
    print(f"Report id  : {report.get('report_id')}")
    print(f"Repo path  : {report.get('repo_path')}")
    print(f"Status     : {report.get('status')}")
    print(f"Next phase : {report.get('recommended_next_phase')}")
    print(f"JSON       : {result.get('json_path')}")
    print(f"Markdown   : {result.get('md_path')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="UX.11 unified Workbench behavior preservation report generator"
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-id", default=None)
    parser.add_argument("--created-at", default=None)
    parser.add_argument("--json", dest="json_out", action="store_true", default=False)
    args = parser.parse_args(argv)

    result = run_create_unified_workbench_behavior_preservation_report(
        repo_path=args.repo_path,
        output_root=args.output_root,
        report_id=args.report_id,
        created_at=args.created_at,
    )
    if args.json_out:
        print(json.dumps(_summary(result), indent=2))
    else:
        _print_text_summary(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
