#!/usr/bin/env python
"""Evaluate a Driver Model Routing decision for a Worker Assignment (H.1).

Contract/report-only. This CLI reads a Worker Assignment (F.5) and writes inert
``driver_decision.json`` / ``driver_decision.md`` artifacts recommending the
safest allowed vehicle (model level). It never calls a model, switches
providers, launches a worker, applies a patch, runs validation, starts Dream,
runs Project Evolution execution, calls webhooks, or promotes lessons.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.driver_model_routing import (  # noqa: E402
    evaluate_driver_route,
    render_driver_decision_json,
    render_driver_decision_text,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate an inert Driver Model Routing decision for a Worker Assignment.",
    )
    parser.add_argument(
        "--worker-assignment",
        required=True,
        help="Path to a worker_assignment.json produced by F.5.",
    )
    parser.add_argument(
        "--repo-path",
        default="",
        help="Repository root for the decision artifact. Defaults to the assignment's repo_path.",
    )
    parser.add_argument(
        "--output-root",
        default="",
        help="Optional driver decision root. Defaults to .agent/driver_decisions/.",
    )
    parser.add_argument("--driver-decision-id", default="", help="Optional stable decision id for smoke tests or reruns.")
    parser.add_argument("--created-at", default="", help="Optional ISO timestamp for deterministic JSON output.")
    parser.add_argument("--dry-run", action="store_true", help="Show the decision without writing files.")
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = evaluate_driver_route(
        worker_assignment_path=args.worker_assignment or None,
        repo_path=args.repo_path or None,
        dry_run=args.dry_run,
        output_root=args.output_root or None,
        driver_decision_id=args.driver_decision_id or None,
        created_at=args.created_at or None,
    )

    if args.json:
        print(render_driver_decision_json(result), end="")
    elif result.get("ok"):
        print(render_driver_decision_text(result), end="")
    else:
        print(render_driver_decision_text(result), end="", file=sys.stderr)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
