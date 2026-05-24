#!/usr/bin/env python
"""Create an experiment from the latest two meaningful benchmark reports."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import experiments


DEFAULT_SUBSET = "full-fast"
DEFAULT_GREENLIGHT_RULE = "No correctness regression; review cost or speed increases."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create an experiment from the latest two benchmark reports.",
    )
    parser.add_argument("--title", required=True)
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--subset", default=DEFAULT_SUBSET)
    parser.add_argument("--greenlight-rule", default=DEFAULT_GREENLIGHT_RULE)
    parser.add_argument(
        "--min-total",
        type=int,
        default=5,
        help="Minimum report total to treat as meaningful.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Immediately compare the created experiment.",
    )
    parser.add_argument(
        "--export-md",
        action="store_true",
        help="Export a Markdown lab note after creation or comparison.",
    )
    return parser


def _latest_pair(min_total: int) -> tuple[dict, dict]:
    reports = experiments.list_benchmark_reports(min_total=min_total)
    if len(reports) < 2:
        raise experiments.ExperimentError(
            f"need at least two benchmark reports with total >= {min_total}; found {len(reports)}"
        )
    return reports[0], reports[1]


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        variant, baseline = _latest_pair(args.min_total)
        record = experiments.create_experiment(
            title=args.title,
            hypothesis=args.hypothesis,
            baseline_report=baseline["path"],
            variant_report=variant["path"],
            subset=args.subset,
            greenlight_rule=args.greenlight_rule,
        )
        experiment_path = experiments.resolve_experiment_path(record["experiment_id"])
        print(f"created experiment: {experiment_path}")
        print(f"experiment_id: {record['experiment_id']}")
        print(f"baseline_report: {record['baseline_report']}")
        print(f"variant_report: {record['variant_report']}")

        if args.compare:
            record = experiments.compare_experiment(record["experiment_id"])
            print(f"compared experiment: {record['experiment_id']}")

        if args.export_md:
            md = experiments.export_experiment_markdown(record["experiment_id"])
            print(f"markdown report: {md['path']}")

    except experiments.ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: could not create experiment from latest reports: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
