#!/usr/bin/env python
"""Phase 12.5j — CLI to import external linter findings.

Reads ESLint and/or Pylint JSON reports and writes a normalized
.agent/linter/findings.json under the given repo. The output is later
consumed by Phantom Limb, CONTROL, and graph ranking.

This script never executes a linter and never installs anything. Provide a
pre-rendered JSON report (e.g. `eslint --format json ...` or
`pylint --output-format=json ...`) and point the CLI at it.

Examples:
    python scripts/import_linter_findings.py --repo-path . \\
        --eslint-json eslint-report.json
    python scripts/import_linter_findings.py --repo-path . \\
        --pylint-json pylint-report.json
    python scripts/import_linter_findings.py --repo-path . \\
        --eslint-json eslint-report.json --pylint-json pylint-report.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import linter_adapter


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Normalize ESLint/Pylint JSON into .agent/linter/findings.json. "
            "Provide at least one of --eslint-json or --pylint-json."
        ),
    )
    p.add_argument(
        "--repo-path",
        default=".",
        help="Path to the repo root that the findings are about (default: '.').",
    )
    p.add_argument(
        "--eslint-json",
        default=None,
        help="Path to an ESLint JSON report (eslint --format json).",
    )
    p.add_argument(
        "--pylint-json",
        default=None,
        help="Path to a Pylint JSON report (pylint --output-format=json).",
    )
    return p


def _display_output_path(out: str, repo_path: str) -> str:
    """Show the output path relative to the repo when possible."""
    try:
        out_p = Path(out).resolve()
        repo_p = Path(repo_path).resolve()
        return out_p.relative_to(repo_p).as_posix()
    except (ValueError, OSError):
        return out


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not args.eslint_json and not args.pylint_json:
        print(
            "error: provide at least one of --eslint-json or --pylint-json",
            file=sys.stderr,
        )
        return 2

    try:
        summary = linter_adapter.import_linter_findings(
            repo_path=args.repo_path,
            eslint_json=args.eslint_json,
            pylint_json=args.pylint_json,
        )
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    output_display = _display_output_path(summary["output"], args.repo_path)
    print(f"imported: {summary['imported']}")
    print(f"skipped: {summary['skipped']}")
    print(f"output: {output_display}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
