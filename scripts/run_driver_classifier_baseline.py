"""MODEL.2 — Run the Driver Classifier Baseline (CLI).

Reads the MODEL.1 JSONL artifact dataset, learns a small offline pure-stdlib baseline
(a single-rule classifier with a majority-class fallback), and writes an advisory
evaluation report (JSON + Markdown) plus a predictions JSONL.

This tool is report-only. It does not route live tasks, override the deterministic
Driver, call model APIs, call LLMs, call embeddings, write to a database, apply
patches, run validation or a benchmark check, or launch workers. It reads the dataset
only and never mutates it. Predictions are advisory only.

Usage:
    python scripts/run_driver_classifier_baseline.py \\
        --dataset-path .agent/model_lab/artifact_dataset/artifact_dataset.jsonl --json
    python scripts/run_driver_classifier_baseline.py \\
        --dataset-path ds.jsonl --target-field labels.recommended_next_step --test-ratio 0.3
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

from core.driver_classifier_baseline import (  # noqa: E402
    DEFAULT_TARGET_FIELD,
    DRIVER_CLASSIFIER_GUARDRAIL_NOTE,
    write_driver_classifier_baseline,
)

DEFAULT_DATASET_PATH = str(Path(".agent") / "model_lab" / "artifact_dataset" / "artifact_dataset.jsonl")
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "model_lab" / "driver_classifier_baseline")


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
    return f"{stamp or 'baseline'}_driver-classifier"


def run_driver_classifier_baseline(
    *,
    dataset_path: str = DEFAULT_DATASET_PATH,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | float | None = None,
    target_field: str = DEFAULT_TARGET_FIELD,
    test_ratio: float = 0.3,
    limit: int | None = None,
    json_out: bool = False,
) -> dict[str, Any]:
    """Read the dataset, learn the baseline, and write JSON + Markdown + predictions.

    Returns ``{ok, json_path, md_path, predictions_path, report, result, report_id}``.
    """
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)

    result = write_driver_classifier_baseline(
        dataset_path,
        output_root,
        target_field=target_field,
        test_ratio=test_ratio,
        report_id=final_report_id,
        created_at=created_iso,
        limit=limit,
    )
    result["report_id"] = final_report_id
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    metrics = report.get("metrics") or {}
    print("MODEL.2 — Driver Classifier Baseline")
    print("=" * 36)
    print(f"Report id                : {report.get('report_id')}")
    print(f"Dataset path             : {report.get('dataset_path')}")
    print(f"Row count                : {report.get('row_count')}")
    print(f"Train / test             : {report.get('train_count')} / {report.get('test_count')}")
    print(f"Target field             : {report.get('target_field')}")
    print(f"Baseline                 : {report.get('baseline_kind')} (majority: {report.get('majority_label') or '(none)'})")
    if metrics:
        print(
            "Metrics                  : "
            f"accuracy={metrics.get('accuracy')} "
            f"macro_f1={metrics.get('macro_f1')} "
            f"({metrics.get('correct')}/{metrics.get('total')})"
        )
    else:
        print("Metrics                  : unavailable")
    distribution = report.get("target_distribution") or {}
    if distribution:
        print("Target distribution      :")
        for label in sorted(distribution):
            print(f"  - {label}: {distribution[label]}")
    blockers = report.get("blockers") or []
    if blockers:
        print("Blockers                 :")
        for blocker in blockers:
            print(f"  - {blocker}")
    warnings = report.get("warnings") or []
    if warnings:
        print("Warnings                 :")
        for warning in warnings[:10]:
            print(f"  - {warning}")
    print(f"JSON                     : {result['json_path']}")
    print(f"Markdown                 : {result['md_path']}")
    print(f"Predictions              : {result['predictions_path']}")
    print(f"\n> {DRIVER_CLASSIFIER_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "MODEL.2: read the MODEL.1 artifact dataset and write a pure-stdlib baseline "
            "evaluation report. Report-only — it does not route live tasks, override the "
            "deterministic Driver, call model APIs, call LLMs, call embeddings, write to a "
            "database, apply patches, run validation or a benchmark check, or launch workers."
        )
    )
    parser.add_argument("--dataset-path", default=DEFAULT_DATASET_PATH, help="Path to the MODEL.1 JSONL dataset.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory to write the report into.")
    parser.add_argument("--report-id", default=None, help="Deterministic report id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument("--target-field", default=DEFAULT_TARGET_FIELD, help="Dotted target field (default target.target_label).")
    parser.add_argument("--test-ratio", type=float, default=0.3, help="Fraction of rows held out for evaluation.")
    parser.add_argument("--json", action="store_true", help="Print the baseline report JSON.")
    parser.add_argument("--limit", type=int, default=None, help="Use at most N rows (deterministic order).")
    args = parser.parse_args(argv)

    result = run_driver_classifier_baseline(
        dataset_path=args.dataset_path,
        output_root=args.output_root,
        report_id=args.report_id,
        created_at=args.created_at,
        target_field=args.target_field,
        test_ratio=args.test_ratio,
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
