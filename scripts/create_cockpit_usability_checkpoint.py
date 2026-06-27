"""Create the UX.8 cockpit usability checkpoint artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.cockpit_usability_checkpoint import (  # noqa: E402
    REPORT_KIND,
    build_cockpit_usability_checkpoint,
    demo_observations,
    write_cockpit_usability_checkpoint_artifacts,
)

DEFAULT_REPO_PATH = "."
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "ux" / "cockpit_usability_checkpoint")


def _created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    return str(raw)


def run_create_cockpit_usability_checkpoint(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    checkpoint_id: str | None = None,
    created_at: str | None = None,
    observations: list[str] | None = None,
    demo: bool = False,
) -> dict[str, Any]:
    """Build and write the UX.8 checkpoint report."""
    resolved_observations = list(observations or [])
    if demo:
        resolved_observations.extend(demo_observations())
    report = build_cockpit_usability_checkpoint(
        repo_path=repo_path,
        observations=resolved_observations,
        created_at=_created_at(created_at),
        checkpoint_id=checkpoint_id,
    )
    return write_cockpit_usability_checkpoint_artifacts(report, output_root)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    high_risks = [
        risk["risk_id"]
        for risk in report.get("ux_risks", [])
        if risk.get("risk_level") == "high"
    ]
    return {
        "report_kind": report.get("report_kind", REPORT_KIND),
        "checkpoint_id": report.get("checkpoint_id"),
        "checkpoint_status": report.get("checkpoint_status"),
        "overall_usability_score": report.get("overall_usability_score"),
        "recommended_next_step": report.get("recommended_next_step"),
        "recommended_next_phase": report.get("recommended_next_phase"),
        "highest_ux_risks": high_risks,
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
    }


def _print_text_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    print("UX.8 - Cockpit Usability Checkpoint")
    print("=" * 39)
    print(f"Checkpoint id : {report.get('checkpoint_id')}")
    print(f"Repo path     : {report.get('repo_path')}")
    print(f"Status        : {report.get('checkpoint_status')}")
    print(f"Score         : {report.get('overall_usability_score')}")
    print(f"Next phase    : {report.get('recommended_next_phase')}")
    print(f"JSON          : {result.get('json_path')}")
    print(f"Markdown      : {result.get('md_path')}")
    print()
    print("Highest UX risks:")
    high = [risk for risk in report.get("ux_risks", []) if risk.get("risk_level") == "high"]
    if high:
        for risk in high:
            print(f"  - {risk.get('risk_id')}: {risk.get('finding')}")
    else:
        print("  - None")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="UX.8 cockpit usability checkpoint report generator"
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--checkpoint-id", default=None)
    parser.add_argument("--created-at", default=None)
    parser.add_argument("--observation", action="append", default=[])
    parser.add_argument("--demo", action="store_true", default=False)
    parser.add_argument("--json", dest="json_out", action="store_true", default=False)
    args = parser.parse_args(argv)

    result = run_create_cockpit_usability_checkpoint(
        repo_path=args.repo_path,
        output_root=args.output_root,
        checkpoint_id=args.checkpoint_id,
        created_at=args.created_at,
        observations=list(args.observation or []),
        demo=args.demo,
    )
    if args.json_out:
        print(json.dumps(_summary(result), indent=2))
    else:
        _print_text_summary(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
