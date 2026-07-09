"""Create UX.RUN.2 Run Progress Snapshot Loader report artifacts.

Writes a report about loading an existing progress snapshot/report artifact. It
does not create live progress, poll active runs, change execution behavior,
launch workers, call models, apply patches, run validation, run benchmarks, or
trigger actions.
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

from core.run_progress_snapshot_loader import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    GUARDRAIL_NOTE,
    LOADED,
    LOADED_WITH_WARNINGS,
    write_run_progress_snapshot_loader_report,
)


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
    return f"{stamp or 'report'}_run-progress-snapshot-loader"


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    loader_result = report.get("loader_result") or {}
    next_phase = report.get("recommended_next_phase") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "report_id": report.get("report_id"),
        "loader_status": loader_result.get("loader_status"),
        "snapshot_id": loader_result.get("snapshot_id"),
        "source_path": loader_result.get("source_path"),
        "warning_count": len(loader_result.get("warnings") or []),
        "blocked_reason_count": len(loader_result.get("blocked_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_run_progress_snapshot_loader_report(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    snapshot_id: str | None = "default",
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | float | None = None,
) -> dict[str, Any]:
    """Write UX.RUN.2 loader report artifacts and return paths plus a summary."""
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)
    result = write_run_progress_snapshot_loader_report(
        repo_root=repo_root,
        snapshot_id=snapshot_id,
        output_dir=output_dir,
        report_id=final_report_id,
        created_at=created_iso,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("UX.RUN.2 - Run Progress Snapshot Loader")
    print("=" * 44)
    print(f"Report id       : {summary['report_id']}")
    print(f"Loader status   : {summary['loader_status']}")
    print(f"Snapshot id     : {summary['snapshot_id']}")
    print(f"Source path     : {summary['source_path']}")
    print(f"Warnings        : {summary['warning_count']}")
    print(f"Blocked reasons : {summary['blocked_reason_count']}")
    print(f"Recommended next: {summary['recommended_next_phase']}")
    print(f"JSON            : {summary['json_path']}")
    print(f"Markdown        : {summary['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "UX.RUN.2: write a report for a read-only existing run progress "
            "snapshot load. This loads JSON artifacts only; it does not add "
            "live progress, polling, or action controls."
        )
    )
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT))
    parser.add_argument("--snapshot-id", default="default")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--report-id", default=None)
    parser.add_argument("--created-at", default=None)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_run_progress_snapshot_loader_report(
        repo_root=args.repo_root,
        snapshot_id=args.snapshot_id,
        output_dir=args.output_dir,
        report_id=args.report_id,
        created_at=args.created_at,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["report"]["status"] in {LOADED, LOADED_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
