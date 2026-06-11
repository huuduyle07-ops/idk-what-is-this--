#!/usr/bin/env python
"""Phase A.14 - Deprecated Proposal Route Verification CLI.

Builds a report-only verification for:
    /lessons/create-candidate-from-proposal

Artifacts are written to:
    .agent/audits/<timestamp>_deprecated-proposal-route-verification.json
    .agent/audits/<timestamp>_deprecated-proposal-route-verification.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_AUDITS_ROOT = PROJECT_ROOT / ".agent" / "audits"


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify callers and safety for the deprecated/manual proposal lesson route. "
            "Report-only: no lesson writes, no source mutations, no runtime behavior changes."
        ),
    )
    parser.add_argument(
        "--repo-path",
        default=str(PROJECT_ROOT),
        help="Repository root to scan. Defaults to this project root.",
    )
    parser.add_argument(
        "--audits-root",
        default=str(DEFAULT_AUDITS_ROOT),
        help="Directory where verification artifacts are written. Default: .agent/audits/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the report but do not write artifact files.",
    )
    args = parser.parse_args(argv)

    from core.deprecated_proposal_route_verification import build_report, write_artifacts

    try:
        report = build_report(repo_path=args.repo_path)
    except Exception as e:
        print(
            f"[deprecated_proposal_route] error building report: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    route = report["route"]
    counts = report["caller_counts"]
    print("[deprecated_proposal_route] Report built:")
    print(f"  Route: {route['path']}")
    print(f"  Defined: {route['defined']} ({route.get('file')}::{route.get('function_name')})")
    print(f"  Methods: {route.get('http_methods')}")
    print(f"  UI callers: {counts['ui']}")
    print(f"  Test callers: {counts['tests']}")
    print(f"  Scripts/core callers: {counts['scripts_core']}")
    print(f"  Docs mentions: {counts['docs']}")
    print(f"  Safety: {report['safety']['safe']}")
    print(f"  Classification: {report['classification']}")
    print(f"  Recommendation: {report['recommendation']}")

    if args.dry_run:
        print("[deprecated_proposal_route] --dry-run: skipping artifact write.")
        return 0

    try:
        paths = write_artifacts(report, audits_root=args.audits_root)
    except Exception as e:
        print(
            f"[deprecated_proposal_route] error writing artifacts: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    print(f"[deprecated_proposal_route] JSON:     {paths['json']}")
    print(f"[deprecated_proposal_route] Markdown: {paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
