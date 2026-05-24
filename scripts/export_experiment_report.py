#!/usr/bin/env python
"""Export an experiment registry record as a Markdown lab note."""
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
        description="Export a benchmark experiment record to Markdown.",
    )
    parser.add_argument(
        "experiment",
        help="Experiment id, filename, or JSON path under .agent/experiments/.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional Markdown output path under .agent/experiments/.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = experiments.export_experiment_markdown(
            args.experiment,
            output=args.output,
        )
    except experiments.ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: could not write experiment report: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4

    print(f"exported experiment report: {result['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
