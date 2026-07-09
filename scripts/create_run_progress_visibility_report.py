"""Create UX.RUN.1 Run Progress / Operator Visibility report artifacts.

Writes a read-only progress visibility JSON/Markdown report. It does not change
execution behavior, launch workers, route models, enforce approval, apply
patches, run validation, run benchmarks, or add live polling.
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

from core.run_progress_visibility import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    GUARDRAIL_NOTE,
    READY,
    READY_WITH_WARNINGS,
    write_run_progress_visibility_report,
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
    return f"{stamp or 'report'}_run-progress-visibility"


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    next_phase = report.get("recommended_next_phase") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "report_id": report.get("report_id"),
        "status": report.get("status"),
        "stage_count": len(report.get("stage_contract") or []),
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
    }


def run_create_run_progress_visibility_report(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | float | None = None,
    live_stream_implemented: bool = False,
) -> dict[str, Any]:
    """Write UX.RUN.1 report artifacts and return paths plus a summary."""
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)
    result = write_run_progress_visibility_report(
        output_dir=output_dir,
        report_id=final_report_id,
        created_at=created_iso,
        live_stream_implemented=live_stream_implemented,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("UX.RUN.1 - Run Progress / Operator Visibility")
    print("=" * 48)
    print(f"Report id       : {summary['report_id']}")
    print(f"Status          : {summary['status']}")
    print(f"Stages          : {summary['stage_count']}")
    print(f"Warnings        : {summary['warning_count']}")
    print(f"Blocked reasons : {summary['blocked_reason_count']}")
    print(f"Recommended next: {summary['recommended_next_phase']}")
    print(f"JSON            : {summary['json_path']}")
    print(f"Markdown        : {summary['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "UX.RUN.1: write a read-only run progress visibility contract/report. "
            "This defines operator-visible progress stages and safe display "
            "boundaries; it does not add live progress or execution power."
        )
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--report-id", default=None)
    parser.add_argument("--created-at", default=None)
    parser.add_argument(
        "--live-stream-implemented",
        action="store_true",
        default=False,
        help="Mark a live stream as already implemented; normally false for UX.RUN.1.",
    )
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_run_progress_visibility_report(
        output_dir=args.output_dir,
        report_id=args.report_id,
        created_at=args.created_at,
        live_stream_implemented=args.live_stream_implemented,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["report"]["status"] in {READY, READY_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
