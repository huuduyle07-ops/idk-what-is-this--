#!/usr/bin/env python
"""Phase 12.14c - Create a memory-temperature dogfood experiment record.

Read-only. Compares the latest two meaningful benchmark reports (if available),
references the Phase 12.14a-12.14b memory-temperature artifacts, and writes a
behavior-focused JSON + Markdown record under ``.agent/experiments/``.

No model calls, no benchmark execution, no ranking/retrieval/patching/validation/
scoring or UI changes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import experiments
from core import memory_temperature_dogfood as dogfood


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a read-only memory-temperature dogfood experiment record "
            "(Phase 12.14c)."
        ),
    )
    parser.add_argument(
        "--repo-path",
        default=None,
        help="Repository whose memory-temperature artifacts are referenced "
        "(defaults to this project).",
    )
    parser.add_argument(
        "--min-total",
        type=int,
        default=5,
        help="Minimum benchmark report total to treat as meaningful (default: 5).",
    )
    parser.add_argument(
        "--benchmark-check",
        default=dogfood.DEFAULT_BENCHMARK_CHECK,
        help=f"Benchmark --check result to record (default: {dogfood.DEFAULT_BENCHMARK_CHECK}).",
    )
    parser.add_argument(
        "--pytest-passed",
        type=int,
        default=dogfood.DEFAULT_PYTEST_PASSED,
        help=f"Full pytest passed count to record (default: {dogfood.DEFAULT_PYTEST_PASSED}).",
    )
    parser.add_argument(
        "--correctness-changed",
        action="store_true",
        help="Assert correctness changed (overridden by observed report deltas).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        out = dogfood.create_memory_temperature_dogfood(
            repo_path=args.repo_path,
            min_total=args.min_total,
            correctness_unchanged=not args.correctness_changed,
            benchmark_check=args.benchmark_check,
            pytest_passed=args.pytest_passed,
        )
    except experiments.ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: could not write dogfood record: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - friendly CLI boundary
        print(f"error: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4

    record = out["record"]
    decision = record["behavior_decision"]
    comparison = record["benchmark_comparison"]
    print(f"experiment_id: {out['experiment_id']}")
    print(f"json: {out['json_path']}")
    print(f"markdown: {out['md_path']}")
    print(f"decision: {decision['status']}")
    print(f"behavior_unchanged: {decision['behavior_unchanged']}")
    print(f"human_review_required: {decision['human_review_required']}")
    if comparison.get("available"):
        print(
            "benchmark before/after: "
            f"{comparison.get('baseline_report')} -> {comparison.get('variant_report')}"
        )
    else:
        print(f"benchmark before/after: unavailable ({comparison.get('report_count', 0)} reports)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
