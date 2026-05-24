#!/usr/bin/env python
"""Phase 12.5b — read-only CLI that explains weighted graph node rankings."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph.builder import build_graph_from_repo
from graph.weights import explain_node_weights


TABLE_COLUMNS = [
    ("rank", "Rank"),
    ("node_id", "Node"),
    ("node_kind", "Kind"),
    ("total_weight", "Weight"),
    ("topology_contribution", "Topology"),
    ("complexity_contribution", "Complexity"),
    ("failure_penalty", "Penalty"),
    ("reasons_display", "Reasons"),
]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Explain weighted graph node rankings for a repository. "
            "Read-only debugging / presentation tool."
        ),
    )
    parser.add_argument(
        "--repo-path",
        required=True,
        help="Path to the repository whose graph should be analyzed.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of top-ranked nodes to display (default: 20).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print rows as JSON instead of a text table.",
    )
    parser.add_argument(
        "--include-zero-penalty",
        action="store_true",
        help="Include nodes whose failure penalty is 0 (default: hide them).",
    )
    parser.add_argument(
        "--filter",
        default=None,
        help=(
            "Only show nodes with this kind "
            "(e.g. file, function, class, symbol)."
        ),
    )
    return parser


def _format_number(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.2f}"
    return str(value)


def _sanitize_cell(value: Any) -> str:
    return " ".join(str(value).split())


def _format_reasons(reasons: list[str]) -> str:
    if not reasons:
        return ""
    return " + ".join(reasons)


def _format_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No nodes to display."
    display_rows = []
    for row in rows:
        display_rows.append(
            {
                "rank": str(row["rank"]),
                "node_id": _sanitize_cell(row["node_id"]),
                "node_kind": _sanitize_cell(row.get("node_kind") or ""),
                "total_weight": _format_number(row["total_weight"]),
                "topology_contribution": _format_number(row["topology_contribution"]),
                "complexity_contribution": _format_number(row["complexity_contribution"]),
                "failure_penalty": _format_number(row["failure_penalty"]),
                "reasons_display": _sanitize_cell(
                    _format_reasons(row.get("reasons") or [])
                ),
            }
        )
    widths = {
        key: max(len(label), *(len(display[key]) for display in display_rows))
        for key, label in TABLE_COLUMNS
    }
    header = "  ".join(label.ljust(widths[key]) for key, label in TABLE_COLUMNS)
    divider = "  ".join("-" * widths[key] for key, _label in TABLE_COLUMNS)
    lines = [header, divider]
    for display in display_rows:
        lines.append(
            "  ".join(display[key].ljust(widths[key]) for key, _label in TABLE_COLUMNS)
        )
    return "\n".join(lines)


def _rank_and_filter(
    rows: list[dict[str, Any]],
    *,
    top: int,
    kind_filter: str | None,
    include_zero_penalty: bool,
) -> list[dict[str, Any]]:
    if kind_filter:
        rows = [r for r in rows if r.get("node_kind") == kind_filter]
    if not include_zero_penalty:
        rows = [r for r in rows if float(r.get("failure_penalty") or 0.0) > 0.0]
    rows = sorted(
        rows,
        key=lambda r: (-float(r["total_weight"]), str(r["node_id"])),
    )
    rows = rows[:top]
    ranked: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        ranked.append({"rank": index, **row})
    return ranked


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.top <= 0:
        print("error: --top must be a positive integer", file=sys.stderr)
        return 2

    repo_path = Path(args.repo_path)
    if not repo_path.exists():
        print(
            f"error: --repo-path does not exist: {args.repo_path}",
            file=sys.stderr,
        )
        return 2
    if not repo_path.is_dir():
        print(
            f"error: --repo-path is not a directory: {args.repo_path}",
            file=sys.stderr,
        )
        return 2

    try:
        graph = build_graph_from_repo(str(repo_path))
    except Exception as exc:
        print(
            f"error: failed to build graph: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 4

    try:
        rows = explain_node_weights(graph, repo_path=str(repo_path))
    except Exception as exc:
        print(
            f"error: failed to compute weights: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 4

    ranked = _rank_and_filter(
        rows,
        top=args.top,
        kind_filter=args.filter,
        include_zero_penalty=args.include_zero_penalty,
    )

    if args.json:
        print(json.dumps(ranked, indent=2, ensure_ascii=False))
    else:
        print(_format_table(ranked))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
