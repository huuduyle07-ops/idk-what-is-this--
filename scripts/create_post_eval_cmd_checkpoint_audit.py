"""ROAD.4 — Create Post-EVAL/CMD Checkpoint Audit (CLI).

Reads the phase registry, EVAL/CMD artifact root directories, and
documentation, then writes a deterministic JSON + Markdown checkpoint audit
under the output root.

Report-only: audits the completed EVAL and CMD arcs without choosing work,
executing phases, calling models, applying patches, running validation or
benchmarks, contacting network services, launching workers, pushing, merging,
or opening PRs.

Exit codes: 0 when audit_status is ``pass`` (or ``pass_with_warnings`` with
``--allow-warnings``); nonzero when ``blocked`` (or ``pass_with_warnings``
without ``--allow-warnings``).

Usage:
    python scripts/create_post_eval_cmd_checkpoint_audit.py \\
        --repo-path . \\
        --registry docs/roadmap/phase_registry.json \\
        --json --allow-warnings
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

from core.post_eval_cmd_checkpoint_audit import (  # noqa: E402
    GUARDRAIL_NOTE,
    STATUS_BLOCKED,
    STATUS_WARN,
    write_post_eval_cmd_checkpoint_audit,
)

DEFAULT_REPO_PATH = "."
DEFAULT_REGISTRY = "docs/roadmap/phase_registry.json"
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "roadmap" / "post_eval_cmd_checkpoint")


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
    return f"{stamp or 'report'}_post-eval-cmd-checkpoint"


def run_create_post_eval_cmd_checkpoint_audit(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    registry: str = DEFAULT_REGISTRY,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | float | None = None,
    external_audit: str | None = None,
) -> dict[str, Any]:
    """Build and write the ROAD.4 audit. Returns {ok, json_path, md_path, report, audit_status}."""
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)
    result = write_post_eval_cmd_checkpoint_audit(
        repo_path,
        registry,
        output_root,
        report_id=final_report_id,
        created_at=created_iso,
        external_audit_path=external_audit or None,
    )
    result["audit_status"] = result["report"].get("audit_status")
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    print("ROAD.4 — Post-EVAL/CMD Checkpoint Audit")
    print("=" * 40)
    print(f"Report id          : {report.get('report_id')}")
    print(f"Repo path          : {report.get('repo_path')}")
    print(f"Registry           : {report.get('registry_path')}")
    print(f"Audit status       : {report.get('audit_status')}")
    print(f"Audit reason       : {report.get('audit_reason')}")
    print(f"Recommended next   : {report.get('recommended_next_step')}")
    reg = report.get("registry_summary") or {}
    print(f"Registry valid     : {reg.get('registry_valid')}")
    print(f"Phase count        : {reg.get('phase_count')}")
    eval_arc = report.get("eval_arc_summary") or {}
    print(f"EVAL arc complete  : {eval_arc.get('all_complete')}")
    cmd_arc = report.get("cmd_arc_summary") or {}
    print(f"CMD arc complete   : {cmd_arc.get('all_complete')}")
    for b in report.get("blockers") or []:
        print(f"  BLOCKER: {b}")
    for w in report.get("warnings") or []:
        print(f"  WARNING: {w}")
    print(f"JSON               : {result['json_path']}")
    print(f"Markdown           : {result['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ROAD.4: read the phase registry, EVAL/CMD artifact roots, and docs and write a "
            "checkpoint audit of the completed EVAL and CMD arcs. Report-only."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY, help="Path to registry JSON.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Output directory.")
    parser.add_argument("--report-id", default=None, help="Deterministic report id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Created-at timestamp (ISO-8601 or epoch seconds).",
    )
    parser.add_argument(
        "--external-audit",
        default=None,
        metavar="PATH",
        help="Path to external codebase audit Markdown file (e.g. docs/audit-2026-06-22.md).",
    )
    parser.add_argument("--json", action="store_true", help="Print report JSON to stdout.")
    parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Exit 0 even when audit_status is 'pass_with_warnings'.",
    )
    args = parser.parse_args(argv)

    result = run_create_post_eval_cmd_checkpoint_audit(
        repo_path=args.repo_path,
        registry=args.registry,
        output_root=args.output_root,
        report_id=args.report_id,
        created_at=args.created_at,
        external_audit=args.external_audit,
    )

    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=True, sort_keys=True))
    else:
        _print_summary(result)

    status = result["audit_status"]
    if status == STATUS_BLOCKED:
        return 1
    if status == STATUS_WARN and not args.allow_warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
