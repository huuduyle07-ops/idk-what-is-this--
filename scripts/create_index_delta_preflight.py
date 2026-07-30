"""Create deterministic INDEX.1E.0 preflight audit artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.index_delta_preflight import (  # noqa: E402
    DEFAULT_BASELINE_JSON,
    PHASE_STATUS_BLOCKED,
    write_index_delta_preflight,
)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"unable to read known-failure baseline {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ValueError("known-failure baseline must contain a JSON object")
    return value


def run_create_index_delta_preflight(
    *,
    repo_root: str | Path = PROJECT_ROOT,
    baseline_path: str | Path = DEFAULT_BASELINE_JSON,
) -> dict[str, Any]:
    root = Path(repo_root).expanduser().resolve()
    source = Path(baseline_path)
    if not source.is_absolute():
        source = root / source
    baseline = _load_json_object(source)
    return write_index_delta_preflight(
        repo_root=root,
        baseline=baseline,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a captured repository-wide failure baseline and "
            "write INDEX.1E.0 JSON/Markdown audit artifacts."
        )
    )
    parser.add_argument(
        "--repo-root",
        default=str(PROJECT_ROOT),
        help="Repository root containing .agent and docs.",
    )
    parser.add_argument(
        "--baseline",
        default=str(DEFAULT_BASELINE_JSON),
        help=(
            "Captured, classified known-failure baseline JSON, relative "
            "to --repo-root unless absolute."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_create_index_delta_preflight(
            repo_root=args.repo_root,
            baseline_path=args.baseline,
        )
    except ValueError as exc:
        print(f"INDEX.1E.0 preflight failed: {exc}")
        return 2

    report = result["report"]
    status = report["readiness"]["phase_status"]
    print(f"Status: {status}")
    print(f"Known failures: {report['known_failure_baseline']['summary']['failed']}")
    print(
        "INDEX-intersecting failures: "
        f"{report['readiness']['index_runtime_failures'] + report['readiness']['index_adjacent_failures']}"
    )
    print(f"Baseline JSON: {result['baseline_json_path']}")
    print(f"Preflight JSON: {result['preflight_json_path']}")
    print(f"Baseline Markdown: {result['baseline_markdown_path']}")
    print(f"Preflight Markdown: {result['preflight_markdown_path']}")
    return 1 if status == PHASE_STATUS_BLOCKED else 0


if __name__ == "__main__":
    raise SystemExit(main())
