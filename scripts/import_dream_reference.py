#!/usr/bin/env python
"""Create a local Dream research reference from pasted notes."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core import dream_references  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import pasted research notes as a Dream reference artifact.",
    )
    parser.add_argument("--repo-path", required=True, help="Path to the analyzed repo.")
    parser.add_argument("--topic", required=True, help="Reference topic.")
    parser.add_argument("--raw", default="", help="Raw pasted research notes.")
    parser.add_argument("--input-file", help="Read raw research notes from a text file.")
    parser.add_argument(
        "--source-type",
        default="manual_paste",
        help="manual_paste, zapier_discord, paper_notes, web_summary, or other.",
    )
    parser.add_argument("--key-idea", action="append", default=[], help="Structured key idea.")
    parser.add_argument("--risk", action="append", default=[], help="Risk or weakness.")
    parser.add_argument(
        "--do-not-assume",
        action="append",
        default=[],
        help="Assumption C.A.T.T.U.S should not make.",
    )
    parser.add_argument(
        "--suggested-dream-trial-input",
        default="",
        help="Optional text to paste into a Dream Trial.",
    )
    parser.add_argument(
        "--normalize-loose",
        action="store_true",
        help=(
            "Parse Zapier/Discord-style headings (Summary, Key Papers & Articles, "
            "Key Insights, Resources & Links, Risks, What … Should Not Assume, "
            "Suggested Dream Trial Input) and fill missing structured fields "
            "from the parsed result. Explicit --key-idea / --risk / "
            "--do-not-assume / --suggested-dream-trial-input still win."
        ),
    )
    return parser


def _read_raw_input(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.raw:
        parts.append(args.raw)
    if args.input_file:
        parts.append(Path(args.input_file).read_text(encoding="utf-8"))
    return "\n\n".join(part.strip() for part in parts if part.strip())


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = dream_references.create_dream_reference(
            repo_path=args.repo_path,
            topic=args.topic,
            raw_input=_read_raw_input(args),
            source_type=args.source_type,
            key_ideas=args.key_idea,
            risks_or_weaknesses=args.risk,
            do_not_assume=args.do_not_assume,
            suggested_dream_trial_input=args.suggested_dream_trial_input,
            normalize_loose=args.normalize_loose,
        )
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(f"reference_id: {result.reference_id}")
    print(f"reference.md: {result.markdown_path}")
    print(f"reference.json: {result.json_path}")
    print(f"summary: {result.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

