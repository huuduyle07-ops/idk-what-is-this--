#!/usr/bin/env python
"""Compare benchmark reports referenced by an experiment record."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import experiments


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare the benchmark reports for one experiment record.",
    )
    parser.add_argument(
        "experiment",
        help="Experiment id, filename, or JSON path under .agent/experiments/.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        record = experiments.compare_experiment(args.experiment)
    except experiments.ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4

    print(experiments.format_comparison_summary(record))
    path = experiments.resolve_experiment_path(record["experiment_id"])
    print(f"saved: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
