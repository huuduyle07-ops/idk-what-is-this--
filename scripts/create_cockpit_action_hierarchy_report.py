"""UX.7 — Create Cockpit Action Hierarchy Report (CLI).

Analyses the operator cockpit HTML and CSS to produce a structured report
showing which surfaces belong to which navigation group, what was merged,
and what is collapsed behind the Advanced / Debug drawer.

UX.7 is a report-only layout-analysis phase.  It does not add new backend
routes, mutation routes, or execution powers.  It does not start runs, call
models, apply patches, run validation or benchmarks, contact network services,
launch workers, mutate the repo, push, merge, or open PRs.

Usage:
    python scripts/create_cockpit_action_hierarchy_report.py --json
    python scripts/create_cockpit_action_hierarchy_report.py --demo
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

from core.cockpit_action_hierarchy import (  # noqa: E402
    GUARDRAIL_NOTE,
    PREVIEW_STATUS_READY,
    REPORT_KIND,
    build_cockpit_action_hierarchy_report,
    write_cockpit_action_hierarchy_artifacts,
)

DEFAULT_HTML_PATH   = str(PROJECT_ROOT / "web" / "templates" / "index.html")
DEFAULT_CSS_PATH    = str(PROJECT_ROOT / "web" / "static" / "style.css")
DEFAULT_REPO_PATH   = "."
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "ux" / "cockpit_action_hierarchy")


def _resolve_created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    return str(raw)


def run_create_cockpit_action_hierarchy_report(
    *,
    html_path: str = DEFAULT_HTML_PATH,
    css_path: str = DEFAULT_CSS_PATH,
    repo_path: str = DEFAULT_REPO_PATH,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | None = None,
    demo: bool = False,
) -> dict[str, Any]:
    """Build and write UX.7 Cockpit Action Hierarchy report.

    Returns {ok, json_path, md_path, report}.
    """
    created_iso = _resolve_created_at(created_at)

    if demo:
        html_path = DEFAULT_HTML_PATH
        css_path  = DEFAULT_CSS_PATH

    report   = build_cockpit_action_hierarchy_report(
        html_path=html_path,
        css_path=css_path,
        repo_path=repo_path,
        report_id=report_id,
        created_at=created_iso,
    )
    artifacts = write_cockpit_action_hierarchy_artifacts(report, output_root)
    return {**artifacts, "report": report}


def _print_summary(result: dict) -> None:
    report = result["report"]
    print("UX.7 — Cockpit Action Hierarchy Report")
    print("=" * 42)
    print(f"Report id          : {report.get('report_id')}")
    print(f"Repo path          : {report.get('repo_path')}")
    print(f"Preview status     : {report.get('preview_status')}")
    print(f"Has advanced drawer: {report.get('has_advanced_drawer')}")
    print(f"Primary nav count  : {report.get('primary_nav_count')}")
    print(f"Cockpit CSS present: {report.get('cockpit_css_present')}")
    print(f"Primary workflow   : {report.get('primary_workflow')}")
    print(f"Workflow surfaces  : {report.get('workflow_surfaces')}")
    print(f"Advanced/debug     : {report.get('advanced_debug_surfaces')}")
    print(f"Merged surfaces    : {report.get('merged_surfaces')}")
    risks = report.get("remaining_navigation_risks", [])
    print(f"Navigation risks   : {len(risks)}")
    for r in risks:
        print(f"  - {r}")
    print(f"JSON               : {result.get('json_path')}")
    print(f"Markdown           : {result.get('md_path')}")
    print()
    print("Boundaries (UX.7 does not):")
    for b in report.get("boundaries", []):
        print(f"  {b}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="UX.7 — Cockpit Action Hierarchy Report (layout analysis only)"
    )
    parser.add_argument("--html-path",    default=DEFAULT_HTML_PATH)
    parser.add_argument("--css-path",     default=DEFAULT_CSS_PATH)
    parser.add_argument("--repo-path",    default=DEFAULT_REPO_PATH)
    parser.add_argument("--output-root",  default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-id",    default=None)
    parser.add_argument("--created-at",   default=None)
    parser.add_argument("--demo",   action="store_true", default=False)
    parser.add_argument("--json",   dest="json_out", action="store_true", default=False)

    args   = parser.parse_args(argv)
    result = run_create_cockpit_action_hierarchy_report(
        html_path=args.html_path,
        css_path=args.css_path,
        repo_path=args.repo_path,
        output_root=args.output_root,
        report_id=args.report_id,
        created_at=args.created_at,
        demo=args.demo,
    )

    if args.json_out:
        report  = result["report"]
        summary = {
            "report_kind":                 report.get("report_kind", REPORT_KIND),
            "report_id":                   report.get("report_id"),
            "preview_status":              report.get("preview_status"),
            "has_advanced_drawer":         report.get("has_advanced_drawer"),
            "primary_nav_count":           report.get("primary_nav_count"),
            "cockpit_css_present":         report.get("cockpit_css_present"),
            "primary_workflow":            report.get("primary_workflow"),
            "workflow_surfaces":           report.get("workflow_surfaces"),
            "advanced_debug_surfaces":     report.get("advanced_debug_surfaces"),
            "merged_surfaces":             report.get("merged_surfaces"),
            "remaining_navigation_risks":  report.get("remaining_navigation_risks"),
            "json_path":                   result.get("json_path"),
            "md_path":                     result.get("md_path"),
        }
        print(json.dumps(summary, indent=2))
    else:
        _print_summary(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
