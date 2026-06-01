#!/usr/bin/env python
"""Phase 13.10 - Create a Memory Temperature tie-breaker dogfood report.

Evidence-only. Takes a caller-supplied candidate list (from a local JSON file,
or a small built-in representative sample) and writes a Markdown (+ optional
JSON) report showing what the default-off Memory Temperature tie-breaker *would*
do to their ordering.

It does not query lesson_store or the DB, does not run models or benchmarks,
does not touch live retrieval / the CONTROL prompt, and does not enable
MEMORY_TEMPERATURE_RETRIEVAL_ENABLED. The only side effect is writing the
requested local report file(s).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.memory_temperature_retrieval_dogfood import (
    build_memory_temperature_tiebreaker_dogfood,
    format_memory_temperature_tiebreaker_dogfood_markdown,
)


def _sample_candidates() -> list[dict]:
    """A small representative, near-equal-relevance lesson candidate set."""
    return [
        {
            "id": "cold-manual",
            "title": "old manual note about retries",
            "score": 0.50,
            "status": "active",
            "source_type": "manual",
            "updated_at": "2026-03-01T12:00:00+00:00",
        },
        {
            "id": "hot-lesson",
            "title": "trusted retry lesson",
            "score": 0.50,
            "status": "active",
            "source_type": "lesson",
            "trusted": True,
            "updated_at": "2026-05-30T12:00:00+00:00",
        },
        {
            "id": "warm-manual",
            "title": "recent manual retry note",
            "score": 0.49,
            "status": "active",
            "source_type": "manual",
            "updated_at": "2026-05-25T12:00:00+00:00",
        },
        {
            "id": "blocked-lesson",
            "title": "blocked lesson",
            "score": 0.50,
            "status": "blocked",
            "source_type": "lesson",
            "updated_at": "2026-05-30T12:00:00+00:00",
        },
        {
            "id": "high-relevance-cold",
            "title": "clearly more relevant but cold",
            "score": 0.92,
            "status": "active",
            "source_type": "manual",
            "updated_at": "2026-02-01T12:00:00+00:00",
        },
    ]


def _load_candidates(path: str | None) -> list[dict]:
    if not path:
        return _sample_candidates()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("candidates"), list):
        data = data["candidates"]
    if not isinstance(data, list):
        raise ValueError("candidates JSON must be a list (or {\"candidates\": [...]})")
    return data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a read-only Memory Temperature tie-breaker dogfood report "
            "(Phase 13.10)."
        ),
    )
    parser.add_argument(
        "--candidates-json",
        default=None,
        help="Path to a JSON file with the candidate list (defaults to a "
        "built-in representative sample).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Path to write the Markdown report (defaults to stdout).",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional path to write the raw JSON report.",
    )
    parser.add_argument(
        "--disabled",
        action="store_true",
        help="Simulate the tie-breaker disabled (pass-through) instead of enabled.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        candidates = _load_candidates(args.candidates_json)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: could not load candidates: {exc}", file=sys.stderr)
        return 1

    report = build_memory_temperature_tiebreaker_dogfood(
        candidates, enabled=not args.disabled
    )
    markdown = format_memory_temperature_tiebreaker_dogfood_markdown(report)

    if args.out:
        try:
            Path(args.out).write_text(markdown, encoding="utf-8")
        except OSError as exc:
            print(f"error: could not write report: {exc}", file=sys.stderr)
            return 1
        print(f"markdown: {args.out}")
    else:
        print(markdown)

    if args.json_out:
        try:
            Path(args.json_out).write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as exc:
            print(f"error: could not write JSON report: {exc}", file=sys.stderr)
            return 1
        print(f"json: {args.json_out}")

    print(f"candidate_count: {report['candidate_count']}")
    print(f"default_off_passthrough_unchanged: {report['default_off_passthrough_unchanged']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
