"""ROAD.1 — Validate the Machine-Readable Phase Registry (CLI).

Reads a roadmap phase registry JSON file, validates its schema and per-phase
metadata, and writes a deterministic JSON + Markdown report under the output root.

This tool is report-only. It validates and summarizes roadmap phase metadata; it
does not choose work, execute phases, run the stored validation commands or a
benchmark check, call models, apply patches, write to the real repo, push, merge,
open PRs, or contact a remote git host / chat service / external automation. The
validation commands inside the registry are treated as opaque text and are never
run by this tool.

Usage:
    python scripts/validate_phase_registry.py
    python scripts/validate_phase_registry.py \\
        --registry docs/roadmap/phase_registry.json --output-root .agent/roadmap --json
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

from core.phase_registry import (  # noqa: E402
    PHASE_REGISTRY_GUARDRAIL_NOTE,
    load_phase_registry,
    write_phase_registry_report,
)

DEFAULT_REGISTRY = "docs/roadmap/phase_registry.json"
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "roadmap")


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
    return f"{stamp or 'report'}_phase-registry"


def run_validate_phase_registry(
    *,
    registry: str = DEFAULT_REGISTRY,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | float | None = None,
    json_out: bool = False,
) -> dict[str, Any]:
    """Load the registry, build the report, and write JSON + Markdown.

    Returns ``{ok, json_path, md_path, report, is_valid}``. A registry that cannot
    be read or parsed is reported as invalid inside the report (not a crash).
    """
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)

    load_error = ""
    try:
        data: Any = load_phase_registry(registry)
    except (OSError, ValueError) as exc:
        data = None
        load_error = f"could not read registry at {registry}: {exc}"

    result = write_phase_registry_report(
        data,
        output_root,
        report_id=final_report_id,
        created_at=created_iso,
        registry_path=str(registry),
    )
    report = result["report"]

    if load_error:
        # Surface the load failure in the written artifacts deterministically.
        report["errors"] = sorted(set(list(report.get("errors") or []) + [load_error]))
        report["is_valid"] = False
        Path(result["json_path"]).write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        from core.phase_registry import render_phase_registry_markdown  # noqa: E402

        Path(result["md_path"]).write_text(render_phase_registry_markdown(report), encoding="utf-8")

    result["is_valid"] = bool(report.get("is_valid"))
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    print("ROAD.1 — Machine-Readable Phase Registry Report")
    print("=" * 47)
    print(f"Report id        : {report.get('report_id')}")
    print(f"Registry         : {report.get('registry_path')}")
    print(f"Schema version   : {report.get('schema_version')}")
    print(f"Phase count      : {report.get('phase_count')}")
    print(f"Valid            : {'VALID' if report.get('is_valid') else 'INVALID'}")
    print(f"Counts by track  : {report.get('counts_by_track')}")
    print(f"Counts by status : {report.get('counts_by_status')}")
    errors = report.get("errors") or []
    if errors:
        print("Errors           :")
        for error in errors:
            print(f"  - {error}")
    warnings = report.get("warnings") or []
    if warnings:
        print("Warnings         :")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"JSON             : {result['json_path']}")
    print(f"Markdown         : {result['md_path']}")
    print(f"\n> {PHASE_REGISTRY_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ROAD.1: validate and summarize the machine-readable roadmap phase "
            "registry. Report-only — it does not choose work, execute phases, run "
            "the stored validation commands or a benchmark check, or call models."
        )
    )
    parser.add_argument("--registry", default=DEFAULT_REGISTRY, help="Path to the registry JSON file.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory to write the report into.")
    parser.add_argument("--report-id", default=None, help="Deterministic report id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument("--json", action="store_true", help="Print the report JSON.")
    parser.add_argument(
        "--allow-invalid-report",
        action="store_true",
        help="Write the report and exit 0 even when the registry is invalid.",
    )
    args = parser.parse_args(argv)

    result = run_validate_phase_registry(
        registry=args.registry,
        output_root=args.output_root,
        report_id=args.report_id,
        created_at=args.created_at,
        json_out=args.json,
    )

    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)

    if not result["is_valid"] and not args.allow_invalid_report:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
