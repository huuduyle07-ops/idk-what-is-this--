"""HARDEN.2 - Create the Web Mutation Surface Audit (CLI).

Loads the Flask app route map, inventories route methods and risky route names,
checks HARDEN.1 gate detectability, and writes deterministic JSON + Markdown
artifacts.

Report-only: this script does not call route handlers, call models, apply
patches, run validation, run benchmarks, launch workers, contact network
services, write to a database, or change auth/UI behavior.

Usage:
    python scripts/create_web_mutation_surface_audit.py --repo-path . --json --allow-warnings
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

from core.web_mutation_surface_audit import (  # noqa: E402
    GUARDRAIL_NOTE,
    STATUS_FAIL,
    STATUS_WARN,
    write_web_mutation_surface_audit,
)


DEFAULT_REPO_PATH = "."
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "harden" / "web_mutation_surface_audit")


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
    return f"{stamp or 'report'}_web-mutation-surface-audit"


def _load_default_app() -> Any:
    from web.app import app

    return app


def run_create_web_mutation_surface_audit(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | float | None = None,
) -> dict[str, Any]:
    """Build and write the HARDEN.2 audit. Returns paths, report, and verdict."""
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)
    result = write_web_mutation_surface_audit(
        app=_load_default_app(),
        repo_path=repo_path,
        output_dir=output_root,
        report_id=final_report_id,
        created_at=created_iso,
    )
    result["verdict"] = result["report"].get("verdict")
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    counts = report.get("route_counts") or {}
    print("HARDEN.2 - Web Mutation Surface Audit")
    print("=" * 39)
    print(f"Report id        : {report.get('report_id')}")
    print(f"Repo path        : {report.get('repo_path')}")
    print(f"Verdict          : {report.get('verdict')}")
    print(f"Reason           : {report.get('verdict_reason')}")
    print(f"Routes           : {counts.get('total', 0)}")
    print(f"Mutating routes  : {counts.get('mutating', 0)}")
    print(f"Covered mutations: {counts.get('covered_mutating', 0)}")
    print(f"Warnings         : {len(report.get('warnings') or [])}")
    print(f"Blockers         : {len(report.get('blockers') or [])}")
    for warning in report.get("warnings") or []:
        print(f"  WARNING: {warning}")
    for blocker in report.get("blockers") or []:
        print(f"  BLOCKER: {blocker}")
    print(f"JSON             : {result['json_path']}")
    print(f"Markdown         : {result['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "HARDEN.2: inventory Flask routes and report the web mutation surface. "
            "Report-only; no handlers or validation commands are executed."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
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
        help="Exit 0 even when verdict is pass_with_warnings.",
    )
    args = parser.parse_args(argv)

    result = run_create_web_mutation_surface_audit(
        repo_path=args.repo_path,
        output_root=args.output_root,
        report_id=args.report_id,
        created_at=args.created_at,
    )

    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=True, sort_keys=True))
    else:
        _print_summary(result)

    verdict = result["verdict"]
    if verdict == STATUS_FAIL:
        return 1
    if verdict == STATUS_WARN and not args.allow_warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
