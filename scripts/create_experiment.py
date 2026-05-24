#!/usr/bin/env python
"""Create a file-based benchmark experiment record."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import experiments


def _split_metrics(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    out: list[str] = []
    for raw in values:
        for part in str(raw or "").split(","):
            name = part.strip()
            if name and name not in out:
                out.append(name)
    return out or None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a benchmark experiment registry record.",
    )
    parser.add_argument("--experiment-id", default=None)
    parser.add_argument("--title", required=True)
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--baseline-report", required=True)
    parser.add_argument("--variant-report", required=True)
    parser.add_argument("--subset", default=None)
    parser.add_argument(
        "--metric-name",
        "--metric",
        "--metric-names",
        action="append",
        dest="metric_names",
        help="Metric to compare. May be repeated or comma-separated.",
    )
    parser.add_argument("--greenlight-rule", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        record = experiments.create_experiment(
            title=args.title,
            hypothesis=args.hypothesis,
            baseline_report=args.baseline_report,
            variant_report=args.variant_report,
            subset=args.subset,
            metric_names=_split_metrics(args.metric_names),
            greenlight_rule=args.greenlight_rule,
            experiment_id=args.experiment_id,
        )
    except experiments.ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: could not write experiment record: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4

    path = experiments.resolve_experiment_path(record["experiment_id"])
    print(f"created experiment: {path}")
    print(f"experiment_id: {record['experiment_id']}")
    print(f"status: {record['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
