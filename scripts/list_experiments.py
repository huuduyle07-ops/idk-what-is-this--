#!/usr/bin/env python
"""List file-based experiment registry records."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import experiments


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List benchmark experiment registry records.",
    )
    parser.add_argument("--status", default=None, help="Only show records with this status.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of records.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the list as JSON instead of a text table.",
    )
    return parser


def _cell(value: Any) -> str:
    return str(value if value is not None and value != "" else "")


def _try_format_with_pandas(rows: list[dict[str, Any]]) -> str | None:
    try:
        import pandas as pd  # type: ignore
    except ImportError:
        return None
    frame = pd.DataFrame(rows, columns=experiments.EXPERIMENT_LIST_COLUMNS)
    return frame.to_string(index=False)


def _format_stdlib_table(rows: list[dict[str, Any]]) -> str:
    columns = list(experiments.EXPERIMENT_LIST_COLUMNS)
    widths = {
        column: max(
            len(column),
            *(len(_cell(row.get(column))) for row in rows),
        )
        for column in columns
    }
    header = " | ".join(column.ljust(widths[column]) for column in columns)
    divider = "-+-".join("-" * widths[column] for column in columns)
    lines = [header, divider]
    for row in rows:
        lines.append(
            " | ".join(_cell(row.get(column)).ljust(widths[column]) for column in columns)
        )
    return "\n".join(lines)


def _format_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No experiments found."
    pandas_table = _try_format_with_pandas(rows)
    if pandas_table is not None:
        return pandas_table
    return _format_stdlib_table(rows)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        rows = experiments.list_experiments(
            status=args.status,
            limit=args.limit,
        )
    except experiments.ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4

    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        print(_format_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
