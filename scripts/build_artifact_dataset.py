"""MODEL.1 — Build the C.A.T.T.U.S Artifact Dataset (CLI).

Scans existing C.A.T.T.U.S artifacts under a repo's ``.agent`` directory and writes
a normalized JSONL dataset plus a JSON and Markdown report for future model and
classifier experiments.

This tool is report-only. It does not train or call models, does not call
embeddings, does not write to a database, does not apply patches, does not run
validation or a benchmark check, does not launch workers, and does not contact
Telegram, GitHub, n8n, or any network service. It reads source artifacts only and
never mutates them.

Usage:
    python scripts/build_artifact_dataset.py --repo-path . --json
    python scripts/build_artifact_dataset.py \\
        --repo-path . --output-root .agent/model_lab/artifact_dataset \\
        --include-kind goal_brief --include-kind driver_decision --limit 100
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

from core.artifact_dataset_builder import (  # noqa: E402
    ARTIFACT_DATASET_GUARDRAIL_NOTE,
    ARTIFACT_KINDS,
    write_artifact_dataset,
)

DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "model_lab" / "artifact_dataset")


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
    return f"{stamp or 'dataset'}_artifact-dataset"


def run_build_artifact_dataset(
    *,
    repo_path: str = ".",
    output_root: str = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | float | None = None,
    include_kinds: list[str] | None = None,
    limit: int | None = None,
    json_out: bool = False,
) -> dict[str, Any]:
    """Scan the repo, build the dataset, and write JSONL + JSON + Markdown.

    Returns ``{ok, jsonl_path, json_path, md_path, report, rows, row_count}``.
    """
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)

    result = write_artifact_dataset(
        repo_path,
        output_root,
        report_id=final_report_id,
        created_at=created_iso,
        include_kinds=include_kinds or None,
        limit=limit,
    )
    result["row_count"] = result["report"].get("row_count", 0)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    print("MODEL.1 — C.A.T.T.U.S Artifact Dataset")
    print("=" * 38)
    print(f"Report id                : {report.get('report_id')}")
    print(f"Repo path                : {report.get('repo_path')}")
    print(f"Row count                : {report.get('row_count')}")
    kinds = report.get("counts_by_artifact_kind") or {}
    if kinds:
        print("Counts by artifact kind  :")
        for key in sorted(kinds):
            print(f"  - {key}: {kinds[key]}")
    tasks = report.get("counts_by_dataset_task") or {}
    if tasks:
        print("Counts by dataset task   :")
        for key in sorted(tasks):
            print(f"  - {key}: {tasks[key]}")
    skipped = report.get("skipped_files") or []
    if skipped:
        print(f"Skipped files            : {len(skipped)}")
    warnings = report.get("warnings") or []
    if warnings:
        print("Warnings                 :")
        for warning in warnings[:10]:
            print(f"  - {warning}")
        if len(warnings) > 10:
            print(f"  - ... and {len(warnings) - 10} more")
    print(f"JSONL                    : {result['jsonl_path']}")
    print(f"JSON                     : {result['json_path']}")
    print(f"Markdown                 : {result['md_path']}")
    print(f"\n> {ARTIFACT_DATASET_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "MODEL.1: scan existing C.A.T.T.U.S artifacts and write a normalized JSONL "
            "dataset plus a report. Report-only — it does not train or call models, call "
            "embeddings, write to a database, apply patches, run validation or a benchmark "
            "check, launch workers, or contact Telegram, GitHub, n8n, or any network service."
        )
    )
    parser.add_argument("--repo-path", default=".", help="Repository root to scan for artifacts.")
    parser.add_argument(
        "--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory to write the dataset and report into."
    )
    parser.add_argument("--report-id", default=None, help="Deterministic report id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument("--json", action="store_true", help="Print the dataset report JSON.")
    parser.add_argument(
        "--include-kind",
        action="append",
        default=None,
        metavar="KIND",
        help=f"Limit the scan to one artifact kind (repeatable). Known kinds: {', '.join(ARTIFACT_KINDS)}.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Keep at most N rows (deterministic order).")
    args = parser.parse_args(argv)

    result = run_build_artifact_dataset(
        repo_path=args.repo_path,
        output_root=args.output_root,
        report_id=args.report_id,
        created_at=args.created_at,
        include_kinds=args.include_kind,
        limit=args.limit,
        json_out=args.json,
    )

    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
