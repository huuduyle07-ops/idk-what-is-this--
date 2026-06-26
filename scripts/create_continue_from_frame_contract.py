"""UX.3 — Create Continue-from-Frame Contract (CLI).

Builds a report-only contract defining what a reusable frame is, what context
can be carried forward, what context must be excluded, what human confirmation
is required, and what continuation modes are allowed.

UX.3 defines the contract only. It does not implement actual continuation
execution, start a run from history, call models, apply patches, run
validation, run benchmarks, contact network services, launch workers,
mutate the repo, push, merge, or open PRs.

Usage:
    python scripts/create_continue_from_frame_contract.py \\
        --repo-path . \\
        --output-root .agent/ux/continue_from_frame_contract \\
        --demo --json
"""
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

from core.continue_from_frame_contract import (  # noqa: E402
    CONTRACT_STATUS_READY,
    GUARDRAIL_NOTE,
    REPORT_KIND,
    build_continue_from_frame_contract,
    write_continue_from_frame_artifacts,
)

DEFAULT_REPO_PATH   = "."
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "ux" / "continue_from_frame_contract")


def _resolve_created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    return str(raw)


def run_create_continue_from_frame_contract(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    contract_id: str | None = None,
    created_at: str | None = None,
    frame_json: str | None = None,
    demo: bool = False,
) -> dict[str, Any]:
    """Build and write the UX.3 contract. Returns {ok, json_path, md_path, contract}."""
    created_iso = _resolve_created_at(created_at)

    frames: list[dict[str, Any]] | None = None
    if frame_json:
        try:
            raw = json.loads(frame_json)
            frames = raw if isinstance(raw, list) else [raw]
        except json.JSONDecodeError:
            frames = None

    contract = build_continue_from_frame_contract(
        repo_path=repo_path,
        frames=frames,
        created_at=created_iso,
        contract_id=contract_id,
        demo=demo,
        ui_placeholder_added=True,
    )

    artifacts = write_continue_from_frame_artifacts(contract, output_root)
    return {**artifacts, "contract": contract}


def _print_summary(result: dict[str, Any]) -> None:
    contract = result["contract"]
    print("UX.3 — Continue-from-Frame Contract")
    print("=" * 40)
    print(f"Contract id      : {contract.get('contract_id')}")
    print(f"Repo path        : {contract.get('repo_path')}")
    print(f"Contract status  : {contract.get('contract_status')}")
    print(f"Example frames   : {len(contract.get('example_frames', []))}")
    print(f"Allowed modes    : {len(contract.get('allowed_continuation_modes', []))}")
    print(f"Forbidden modes  : {len(contract.get('forbidden_continuation_modes', []))}")
    print(f"Warnings         : {len(contract.get('warnings', []))}")
    print(f"JSON             : {result.get('json_path')}")
    print(f"Markdown         : {result.get('md_path')}")
    print()
    print("Boundaries (UX.3 does not):")
    for b in contract.get("boundaries", []):
        print(f"  {b}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="UX.3 — Create Continue-from-Frame Contract (report-only)"
    )
    parser.add_argument("--repo-path",    default=DEFAULT_REPO_PATH)
    parser.add_argument("--output-root",  default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--contract-id",  default=None)
    parser.add_argument("--created-at",   default=None)
    parser.add_argument("--frame-json",   default=None, help="JSON array of frame dicts")
    parser.add_argument("--demo",         action="store_true", default=False)
    parser.add_argument("--json",         dest="json_out", action="store_true", default=False)

    args = parser.parse_args(argv)

    result = run_create_continue_from_frame_contract(
        repo_path=args.repo_path,
        output_root=args.output_root,
        contract_id=args.contract_id,
        created_at=args.created_at,
        frame_json=args.frame_json,
        demo=args.demo,
    )

    if args.json_out:
        contract = result["contract"]
        summary = {
            "report_kind":              contract.get("report_kind", REPORT_KIND),
            "contract_id":              contract.get("contract_id"),
            "contract_status":          contract.get("contract_status"),
            "allowed_continuation_modes": contract.get("allowed_continuation_modes"),
            "forbidden_continuation_modes": contract.get("forbidden_continuation_modes"),
            "example_frame_count":      len(contract.get("example_frames", [])),
            "warning_count":            len(contract.get("warnings", [])),
            "json_path":                result.get("json_path"),
            "md_path":                  result.get("md_path"),
        }
        print(json.dumps(summary, indent=2))
    else:
        _print_summary(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
