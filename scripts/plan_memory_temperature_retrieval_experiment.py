#!/usr/bin/env python
"""Phase 12.14d - Create the memory-temperature retrieval experiment plan.

Read-only. Writes a JSON + Markdown experiment plan under ``.agent/experiments/``
describing how memory temperature would be tested safely before any behavior
change. It does NOT enable memory temperature to affect retrieval or ranking.

No model calls, no benchmark execution, no ranking/retrieval/patching/validation/
scoring or DB changes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import experiments
from core import memory_temperature_experiment_plan as plan


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a read-only memory-temperature retrieval experiment plan "
            "(Phase 12.14d). Does not enable any behavior change."
        ),
    )
    parser.add_argument(
        "--experiments-root",
        default=None,
        help="Directory to write the plan into (defaults to the project "
        "experiments root, .agent/experiments).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        out = plan.create_memory_temperature_retrieval_plan(
            experiments_root=args.experiments_root,
        )
    except experiments.ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: could not write plan: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - friendly CLI boundary
        print(f"error: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4

    record = out["record"]
    print(f"experiment_id: {out['experiment_id']}")
    print(f"json: {out['json_path']}")
    print(f"markdown: {out['md_path']}")
    print(f"status: {record['status']}")
    print(f"behavior_change_enabled: {record['behavior_change_enabled']}")
    print(
        "feature flags: "
        + ", ".join(f"{f['name']}={f['default']}" for f in record["feature_flags"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
