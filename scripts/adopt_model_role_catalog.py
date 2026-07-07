"""ADOPT.MODEL.1 - Adopt the human-approved model role catalog artifact.

Writes backups, replaces the active advisory catalog artifact, and emits JSON
plus Markdown adoption receipts. This script grants no model routing, model
calls, worker launch, executable model binding, validation, benchmark, patch,
network, database, route/auth, approval-token, or automatic authority.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.model_role_catalog_adoption import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    MODEL_ROLE_CATALOG_ADOPTION_GUARDRAIL_NOTE,
    read_json_input,
    write_model_role_catalog_adoption,
)


DEFAULT_ACTIVE_CATALOG = ".agent/model_role_registry/model_role_registry.json"
DEFAULT_ACTIVE_CATALOG_MD = ".agent/model_role_registry/model_role_registry.md"
DEFAULT_PROPOSED_CATALOG = (
    ".agent/model_role_registry/model_role_catalog_update_proposal/proposed_model_role_registry.json"
)
DEFAULT_OUTPUT_DIR = str(DEFAULT_OUTPUT_ROOT)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    receipt = result["receipt"]
    next_phase = receipt.get("recommended_next_phase") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": receipt.get("report_kind"),
        "adoption_status": receipt.get("adoption_status"),
        "adopted_phase_id": receipt.get("adopted_phase_id"),
        "source_proposal_phase_id": receipt.get("source_proposal_phase_id"),
        "source_proposed_catalog_path": receipt.get("source_proposed_catalog_path"),
        "active_catalog_path": receipt.get("active_catalog_path"),
        "previous_role_count": receipt.get("previous_role_count"),
        "adopted_role_count": receipt.get("adopted_role_count"),
        "added_roles": receipt.get("added_roles") or [],
        "warning_count": len(receipt.get("warnings") or []),
        "blocked_reason_count": len(receipt.get("blocked_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": receipt.get("warnings") or [],
        "blocked_reasons": receipt.get("blocked_reasons") or [],
    }


def run_adopt_model_role_catalog(
    *,
    active_catalog: str = DEFAULT_ACTIVE_CATALOG,
    active_catalog_md: str = DEFAULT_ACTIVE_CATALOG_MD,
    proposed_catalog: str = DEFAULT_PROPOSED_CATALOG,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Adopt the proposed catalog artifact and return paths plus summary data."""
    active_data, active_blockers = read_json_input(active_catalog, "active catalog", required=True)
    proposed_data, proposed_blockers = read_json_input(proposed_catalog, "proposed catalog", required=True)
    result = write_model_role_catalog_adoption(
        active_catalog_path=active_catalog,
        active_catalog_md_path=active_catalog_md,
        active_catalog_data=active_data,
        proposed_catalog_path=proposed_catalog,
        proposed_catalog_data=proposed_data,
        output_dir=output_dir,
        input_blockers=active_blockers + proposed_blockers,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("ADOPT.MODEL.1 - Human-Approved Model Role Catalog Adoption")
    print("=" * 64)
    print(f"Adoption status : {summary['adoption_status']}")
    print(f"Active catalog  : {summary['active_catalog_path']}")
    print(f"Proposed catalog: {summary['source_proposed_catalog_path']}")
    print(f"Previous roles  : {summary['previous_role_count']}")
    print(f"Adopted roles   : {summary['adopted_role_count']}")
    print(f"Added roles     : {', '.join(summary['added_roles'])}")
    print(f"Recommended next: {summary['recommended_next_phase']}")
    print(f"JSON receipt    : {summary['json_path']}")
    print(f"Markdown receipt: {summary['md_path']}")
    if summary["blocked_reasons"]:
        print("Blocked reasons :")
        for reason in summary["blocked_reasons"]:
            print(f"  - {reason}")
    if summary["warnings"]:
        print("Warnings        :")
        for warning in summary["warnings"]:
            print(f"  - {warning}")
    print(f"\n> {MODEL_ROLE_CATALOG_ADOPTION_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ADOPT.MODEL.1: adopt the reviewed MODEL.N4 advisory model-role "
            "catalog as the active artifact only. This grants no routing, "
            "worker launch, model-call, patch, executable model-binding, "
            "validation, benchmark, or automatic authority."
        )
    )
    parser.add_argument("--active-catalog", default=DEFAULT_ACTIVE_CATALOG)
    parser.add_argument("--active-catalog-md", default=DEFAULT_ACTIVE_CATALOG_MD)
    parser.add_argument("--proposed-catalog", default=DEFAULT_PROPOSED_CATALOG)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_adopt_model_role_catalog(
        active_catalog=args.active_catalog,
        active_catalog_md=args.active_catalog_md,
        proposed_catalog=args.proposed_catalog,
        output_dir=args.output_dir,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
