"""Create DOGFOOD.1A's safe, report-only live-progress evaluation artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.live_progress_operator_dogfood import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    build_live_progress_dogfood_report,
    load_safe_operator_observations,
    write_live_progress_dogfood_report,
)


def run_create_live_progress_operator_dogfood_report(*, output_root: str | Path = DEFAULT_OUTPUT_ROOT, input_root: str | Path | None = None, created_at: str = "") -> dict[str, Any]:
    """Use supplied records only; never start C.A.T.T.U.S or alter its settings."""
    root = Path(output_root)
    observations = load_safe_operator_observations(input_root if input_root is not None else root / "runs")
    return write_live_progress_dogfood_report(build_live_progress_dogfood_report(observations, created_at=created_at), root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create the report-only DOGFOOD.1A live-progress evaluation framework artifact.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--input-root", default=None)
    parser.add_argument("--created-at", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = run_create_live_progress_operator_dogfood_report(output_root=args.output_root, input_root=args.input_root, created_at=args.created_at)
    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(result["json_path"])
        print(result["markdown_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
