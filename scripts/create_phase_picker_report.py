"""ROAD.2 — Create the Phase Picker / Night Candidate Report (CLI).

Reads the ROAD.1 roadmap phase registry, validates it (via the ROAD.1 validator),
classifies every phase into a safe-candidate bucket, and writes a deterministic
JSON + Markdown report under the output root.

This tool is report-only. It recommends candidate phases; it does not execute
phases, modify code, run the stored validation commands or a benchmark check, call
models, apply patches, write to the real repo, push, merge, open PRs, or contact a
remote git host / chat service / external automation. The validation commands inside
the registry are treated as opaque text and are never run by this tool.

Usage:
    python scripts/create_phase_picker_report.py
    python scripts/create_phase_picker_report.py \\
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

from core.phase_picker import (  # noqa: E402
    PHASE_PICKER_GUARDRAIL_NOTE,
    render_phase_picker_markdown,
    write_phase_picker_report,
)
from core.phase_registry import load_phase_registry  # noqa: E402

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
    return f"{stamp or 'report'}_phase-picker"


def run_create_phase_picker_report(
    *,
    registry: str = DEFAULT_REGISTRY,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | float | None = None,
    json_out: bool = False,
) -> dict[str, Any]:
    """Load the registry, classify phases, and write JSON + Markdown.

    Returns ``{ok, json_path, md_path, report, registry_valid}``. A registry that
    cannot be read or parsed is reported as invalid inside the report (not a crash).
    """
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)

    load_error = ""
    try:
        data: Any = load_phase_registry(registry)
    except (OSError, ValueError) as exc:
        data = None
        load_error = f"could not read registry at {registry}: {exc}"

    result = write_phase_picker_report(
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
        report["registry_valid"] = False
        Path(result["json_path"]).write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        Path(result["md_path"]).write_text(render_phase_picker_markdown(report), encoding="utf-8")

    result["registry_valid"] = bool(report.get("registry_valid"))
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    print("ROAD.2 — Phase Picker / Night Candidate Report")
    print("=" * 46)
    print(f"Report id        : {report.get('report_id')}")
    print(f"Registry         : {report.get('registry_path')}")
    print(f"Registry valid   : {'VALID' if report.get('registry_valid') else 'INVALID'}")
    print(f"Phase count      : {report.get('phase_count')}")
    print(f"Bucket counts    : {report.get('bucket_counts')}")
    top = report.get("top_recommendation")
    if top:
        print(f"Top candidate    : {top.get('phase_id')} -> {top.get('recommended_next_step')}")
    else:
        print("Top candidate    : (none)")
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
    print(f"\n> {PHASE_PICKER_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ROAD.2: read the machine-readable roadmap phase registry and classify "
            "phases into safe-candidate buckets. Report-only — it recommends "
            "candidates; it does not execute phases, run the stored validation "
            "commands or a benchmark check, or call models."
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
        "--allow-invalid-registry-report",
        action="store_true",
        help="Write the report and exit 0 even when the registry is invalid.",
    )
    args = parser.parse_args(argv)

    result = run_create_phase_picker_report(
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

    if not result["registry_valid"] and not args.allow_invalid_registry_report:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
