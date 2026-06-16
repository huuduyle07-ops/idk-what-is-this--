#!/usr/bin/env python
"""Create a Visual Evidence Intake Contract for a source artifact (A.16).

Contract/report-only. This CLI reads a Worker Assignment (F.5) or a Driver
Decision (H.1) and writes inert ``visual_evidence_contract.json`` /
``visual_evidence_contract.md`` artifacts that record whether a visual/UI/design
issue is referenced and whether a resolution claim is allowed.

It never performs OCR, calls a vision model, calls any model, switches
providers, launches a worker, applies a patch, runs validation, starts Dream,
runs Project Evolution execution, calls webhooks, or promotes lessons.

Core rule: do not claim a visual/UI/design issue is resolved just because text
tests passed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.visual_evidence_contract import (  # noqa: E402
    create_visual_evidence_contract,
    render_visual_evidence_json,
    render_visual_evidence_text,
)


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create an inert Visual Evidence Intake Contract for a source artifact.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Path to a worker_assignment.json (F.5) or driver_decision.json (H.1).",
    )
    parser.add_argument(
        "--repo-path",
        default="",
        help="Repository root for the contract artifact. Defaults to the source's repo_path.",
    )
    parser.add_argument(
        "--visual-path",
        action="append",
        default=[],
        metavar="PATH",
        help="Optional visual evidence path (repeatable). Recorded, never read.",
    )
    parser.add_argument(
        "--human-summary",
        default="",
        help="Optional human caption summary of the visual evidence.",
    )
    parser.add_argument(
        "--visual-readable-by-model",
        default="",
        metavar="BOOL",
        help="Pass 'true' to assert a vision-capable model can read the evidence. "
        "Never inferred from file presence.",
    )
    parser.add_argument(
        "--validation-covers-visual",
        default="",
        metavar="BOOL",
        help="Pass 'true' to assert validation explicitly covers the visual issue.",
    )
    parser.add_argument(
        "--output-root",
        default="",
        help="Optional contract root. Defaults to .agent/visual_evidence/.",
    )
    parser.add_argument(
        "--visual-evidence-id",
        default="",
        help="Optional stable contract id for smoke tests or reruns.",
    )
    parser.add_argument(
        "--created-at",
        default="",
        help="Optional ISO timestamp for deterministic JSON output.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show the contract without writing files.")
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = create_visual_evidence_contract(
        source_path=args.source or None,
        repo_path=args.repo_path or None,
        visual_paths=list(args.visual_path),
        human_summary=args.human_summary or None,
        visual_readable_by_model=_truthy(args.visual_readable_by_model),
        validation_covers_visual=_truthy(args.validation_covers_visual),
        dry_run=args.dry_run,
        output_root=args.output_root or None,
        created_at=args.created_at or None,
        visual_evidence_id=args.visual_evidence_id or None,
    )

    if args.json:
        print(render_visual_evidence_json(result), end="")
    elif result.get("ok"):
        print(render_visual_evidence_text(result), end="")
    else:
        print(render_visual_evidence_text(result), end="", file=sys.stderr)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
