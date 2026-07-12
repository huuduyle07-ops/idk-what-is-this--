"""Create UX.LIVE.9's report-only bounded polling plan artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.run_progress_polling_plan import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    build_run_progress_polling_plan,
    write_run_progress_polling_plan,
)


def run_create_run_progress_polling_plan(
    *, output_root: str | Path = DEFAULT_OUTPUT_ROOT, created_at: str = ""
) -> dict[str, Any]:
    """Build and write static artifacts; it does not start or configure polling."""
    plan = build_run_progress_polling_plan(created_at=created_at)
    return write_run_progress_polling_plan(plan, output_root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create the UX.LIVE.9 report-only bounded polling experiment plan.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Directory for JSON and Markdown plan artifacts.")
    parser.add_argument("--created-at", default="", help="Optional deterministic report timestamp.")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_create_run_progress_polling_plan(output_root=args.output_root, created_at=args.created_at)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result["json_path"])
        print(result["markdown_path"])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
