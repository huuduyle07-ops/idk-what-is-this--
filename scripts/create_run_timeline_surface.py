"""UX.2 — Create Run Timeline / Progress Surface (CLI).

Builds a deterministic timeline report from supplied events or a static demo
and writes JSON + Markdown under the output root.

Passive visibility layer: surfaces run progress without executing tasks, running
agents, calling models, applying patches, running validation or benchmarks,
contacting network services, launching workers, pushing, merging, or opening PRs.

Usage:
    python scripts/create_run_timeline_surface.py \\
        --repo-path . \\
        --output-root .agent/ux/run_timeline_surface \\
        --demo --json
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

from core.run_timeline_surface import (  # noqa: E402
    GUARDRAIL_NOTE,
    REPORT_KIND,
    TIMELINE_STATUS_READY,
    build_default_timeline,
    build_demo_timeline,
    build_timeline_from_events,
    write_timeline_artifacts,
)

DEFAULT_REPO_PATH   = "."
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "ux" / "run_timeline_surface")


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _default_timeline_id(created_iso: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'tl'}_run-timeline"


def run_create_run_timeline_surface(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    timeline_id: str | None = None,
    created_at: str | float | None = None,
    event_json: str | None = None,
    demo: bool = False,
) -> dict[str, Any]:
    """Build and write the UX.2 timeline. Returns {ok, json_path, md_path, report}."""
    created_iso  = _resolve_created_at(created_at)
    final_tid    = timeline_id or _default_timeline_id(created_iso)

    if demo:
        report = build_demo_timeline(
            repo_path=repo_path, timeline_id=final_tid, created_at=created_iso
        )
    elif event_json:
        try:
            raw_events: list[dict] = json.loads(event_json)
            if not isinstance(raw_events, list):
                raw_events = [raw_events]
        except json.JSONDecodeError:
            raw_events = []
        report = build_timeline_from_events(
            raw_events, repo_path=repo_path, timeline_id=final_tid, created_at=created_iso
        )
    else:
        report = build_default_timeline(
            repo_path=repo_path, timeline_id=final_tid, created_at=created_iso
        )

    artifacts = write_timeline_artifacts(report, output_root)
    return {**artifacts, "report": report}


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    print("UX.2 — Run Timeline / Progress Surface")
    print("=" * 40)
    print(f"Timeline id     : {report.get('timeline_id')}")
    print(f"Repo path       : {report.get('repo_path')}")
    print(f"Timeline status : {report.get('timeline_status')}")
    print(f"Current stage   : {report.get('current_stage')}")
    print(f"Progress        : {report.get('progress_percent')}%")
    print(f"Events          : {len(report.get('events', []))}")
    print(f"Blocking        : {len(report.get('blocking_events', []))}")
    print(f"Completed       : {len(report.get('completed_events', []))}")
    print(f"Next action     : {report.get('next_operator_action')}")
    print(f"JSON            : {result.get('json_path')}")
    print(f"Markdown        : {result.get('md_path')}")
    print()
    print("Boundaries (UX.2 does not):")
    for b in report.get("boundaries", []):
        print(f"  {b}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="UX.2 — Create Run Timeline / Progress Surface (passive visibility)"
    )
    parser.add_argument("--repo-path",    default=DEFAULT_REPO_PATH)
    parser.add_argument("--output-root",  default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--timeline-id",  default=None)
    parser.add_argument("--created-at",   default=None)
    parser.add_argument("--event-json",   default=None, help="JSON array of timeline events")
    parser.add_argument("--demo",         action="store_true", default=False)
    parser.add_argument("--json",         dest="json_out", action="store_true", default=False)

    args = parser.parse_args(argv)

    result = run_create_run_timeline_surface(
        repo_path=args.repo_path,
        output_root=args.output_root,
        timeline_id=args.timeline_id,
        created_at=args.created_at,
        event_json=args.event_json,
        demo=args.demo,
    )

    if args.json_out:
        report = result["report"]
        summary = {
            "report_kind":      report.get("report_kind", REPORT_KIND),
            "timeline_id":      report.get("timeline_id"),
            "timeline_status":  report.get("timeline_status"),
            "current_stage":    report.get("current_stage"),
            "progress_percent": report.get("progress_percent"),
            "event_count":      len(report.get("events", [])),
            "blocking_count":   len(report.get("blocking_events", [])),
            "json_path":        result.get("json_path"),
            "md_path":          result.get("md_path"),
        }
        print(json.dumps(summary, indent=2))
    else:
        _print_summary(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
