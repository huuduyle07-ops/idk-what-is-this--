"""MODEL.3 - Build the Lesson Graph Activation Dataset (CLI).

Reads the MODEL.1 artifact dataset plus lesson / anti-lesson candidates and
writes deterministic advisory activation rows for future scoring.

This tool is report-only. It changes no lesson retrieval or prompt behavior,
calls no models or embeddings, writes no database, does not apply patches, does
not run validation or benchmarks, does not launch workers, and does not promote,
merge, or block lessons.
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

from core.lesson_activation_dataset import (  # noqa: E402
    LESSON_ACTIVATION_GUARDRAIL_NOTE,
    write_lesson_activation_dataset,
)

DEFAULT_ARTIFACT_DATASET = str(Path(".agent") / "model_lab" / "artifact_dataset" / "artifact_dataset.jsonl")
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "model_lab" / "lesson_activation_dataset")


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
    return f"{stamp or 'dataset'}_lesson-activation"


def run_build_lesson_activation_dataset(
    *,
    repo_path: str = ".",
    output_root: str = DEFAULT_OUTPUT_ROOT,
    artifact_dataset: str = DEFAULT_ARTIFACT_DATASET,
    report_id: str | None = None,
    created_at: str | float | None = None,
    json_out: bool = False,
    limit: int | None = None,
    min_overlap: int = 1,
) -> dict[str, Any]:
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)
    result = write_lesson_activation_dataset(
        repo_path,
        output_root,
        artifact_dataset_path=artifact_dataset,
        report_id=final_report_id,
        created_at=created_iso,
        limit=limit,
        min_overlap=min_overlap,
    )
    result["report_id"] = final_report_id
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    print("MODEL.3 - Lesson Graph Activation Dataset")
    print("=" * 43)
    print(f"Report id                : {report.get('report_id')}")
    print(f"Repo path                : {report.get('repo_path')}")
    print(f"Query artifacts          : {report.get('query_artifact_count')}")
    print(f"Lesson candidates        : {report.get('lesson_candidate_count')}")
    print(f"Rows                     : {report.get('row_count')}")
    print("Lesson kinds             :")
    for key, value in (report.get("counts_by_lesson_kind") or {}).items():
        print(f"  - {key}: {value}")
    print("Activation labels        :")
    for key, value in (report.get("counts_by_activation_label") or {}).items():
        print(f"  - {key}: {value}")
    warnings = report.get("warnings") or []
    if warnings:
        print("Warnings                 :")
        for warning in warnings[:10]:
            print(f"  - {warning}")
    print(f"JSONL                    : {result['jsonl_path']}")
    print(f"JSON                     : {result['json_path']}")
    print(f"Markdown                 : {result['md_path']}")
    print(f"\n> {LESSON_ACTIVATION_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "MODEL.3: build a deterministic advisory lesson activation dataset from "
            "MODEL.1 rows and lesson candidates. Report-only; no retrieval or prompt "
            "behavior is changed."
        )
    )
    parser.add_argument("--repo-path", default=".", help="Repository path to scan.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory for output artifacts.")
    parser.add_argument("--artifact-dataset", default=DEFAULT_ARTIFACT_DATASET, help="Path to the MODEL.1 JSONL dataset.")
    parser.add_argument("--report-id", default=None, help="Deterministic report id.")
    parser.add_argument("--created-at", default=None, help="Deterministic created-at value.")
    parser.add_argument("--json", action="store_true", help="Print the report JSON.")
    parser.add_argument("--limit", type=int, default=None, help="Use at most N activation rows.")
    parser.add_argument("--min-overlap", type=int, default=1, help="Minimum overlap for heuristic activation.")
    args = parser.parse_args(argv)

    result = run_build_lesson_activation_dataset(
        repo_path=args.repo_path,
        output_root=args.output_root,
        artifact_dataset=args.artifact_dataset,
        report_id=args.report_id,
        created_at=args.created_at,
        json_out=args.json,
        limit=args.limit,
        min_overlap=args.min_overlap,
    )

    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
