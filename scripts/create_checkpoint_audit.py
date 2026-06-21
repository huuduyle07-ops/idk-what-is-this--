"""ROAD.3 — Create the Post-MODEL Checkpoint Audit (CLI).

Reads the roadmap registry, the registry and picker reports, the generated
model-lab and automation-contract artifacts, and the docs, then writes a
deterministic JSON + Markdown checkpoint audit report under the output root.

This tool is report-only. It audits the completed roadmap arc; it does not choose
new work, execute phases, run validation or a benchmark check, call models or
embeddings, contact a network service, run git, apply patches, launch workers,
write to a database, or promote, merge, block, or retrieve lessons. Missing input
artifacts are reported as warnings, not failures; malformed JSON is skipped with a
warning rather than crashing.

Exit codes: 0 when the verdict is ``pass`` (or ``warn`` with ``--allow-warnings``);
nonzero when the verdict is ``fail`` (or ``warn`` without ``--allow-warnings``).

Usage:
    python scripts/create_checkpoint_audit.py --repo-path . \\
        --registry docs/roadmap/phase_registry.json --json --allow-warnings
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

from core.checkpoint_audit import (  # noqa: E402
    CHECKPOINT_AUDIT_GUARDRAIL_NOTE,
    DEFAULT_EXPECTED_COMPLETE_PHASES,
    write_checkpoint_audit,
)

DEFAULT_REPO_PATH = "."
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
    return f"{stamp or 'report'}_checkpoint-audit"


def run_create_checkpoint_audit(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    registry: str = DEFAULT_REGISTRY,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | float | None = None,
    expected_phases: Any = None,
    json_out: bool = False,
) -> dict[str, Any]:
    """Gather inputs, build the checkpoint audit, and write JSON + Markdown.

    Returns ``{ok, json_path, md_path, report, checkpoint_verdict}``. A registry that
    cannot be read is reported as invalid inside the report (a ``fail`` verdict), not
    a crash.
    """
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)
    expected = tuple(expected_phases) if expected_phases else DEFAULT_EXPECTED_COMPLETE_PHASES

    result = write_checkpoint_audit(
        repo_path,
        registry,
        output_root,
        expected_complete_phases=expected,
        report_id=final_report_id,
        created_at=created_iso,
    )
    result["checkpoint_verdict"] = result["report"].get("checkpoint_verdict")
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    print("ROAD.3 — Post-MODEL Checkpoint Audit")
    print("=" * 36)
    print(f"Report id          : {report.get('report_id')}")
    print(f"Repo path          : {report.get('repo_path')}")
    print(f"Registry           : {report.get('registry_path')}")
    print(f"Checkpoint verdict : {report.get('checkpoint_verdict')}")
    print(f"Recommended next   : {report.get('recommended_next_step')}")
    print(f"Registry valid     : {report.get('registry_valid')}")
    print(f"Phase count        : {report.get('phase_count')}")
    print(f"Complete phases    : {report.get('complete_phase_count')}")
    print(f"Safe-to-prepare    : {report.get('safe_to_prepare_count')}")
    missing = report.get("missing_expected_phases") or []
    if missing:
        print(f"Missing expected   : {', '.join(missing)}")
    blockers = report.get("blockers") or []
    if blockers:
        print("Blockers           :")
        for blocker in blockers:
            print(f"  - {blocker}")
    warnings = report.get("warnings") or []
    if warnings:
        print("Warnings           :")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"JSON               : {result['json_path']}")
    print(f"Markdown           : {result['md_path']}")
    print(f"\n> {CHECKPOINT_AUDIT_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ROAD.3: read the roadmap registry, reports, artifacts, and docs and write a "
            "checkpoint audit of the completed roadmap arc. Report-only — it audits "
            "existing files; it does not choose work, execute phases, run validation or a "
            "benchmark check, call models, run git, apply patches, or launch workers."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root to audit.")
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
        "--expected-phase",
        action="append",
        default=None,
        dest="expected_phase",
        help="Override the expected-complete phase set (repeatable). Replaces the default arc.",
    )
    parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Exit 0 even when the checkpoint verdict is 'warn'.",
    )
    args = parser.parse_args(argv)

    result = run_create_checkpoint_audit(
        repo_path=args.repo_path,
        registry=args.registry,
        output_root=args.output_root,
        report_id=args.report_id,
        created_at=args.created_at,
        expected_phases=args.expected_phase,
        json_out=args.json,
    )

    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)

    verdict = result["checkpoint_verdict"]
    if verdict == "fail":
        return 1
    if verdict == "warn" and not args.allow_warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
