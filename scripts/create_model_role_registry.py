"""MODEL.N1 - Create a Model Role Registry / Tower Card Contract (CLI).

Writes deterministic JSON and Markdown artifacts for advisory model/role tower
cards. Inputs are a manual role catalog JSON file or the built-in default
catalog. The script does not route tasks, call models, launch workers, bind
executable model IDs, change model selection, apply patches, run validation, run
benchmarks, contact networks, or write databases.
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

from core.model_role_registry import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    MODEL_ROLE_REGISTRY_GUARDRAIL_NOTE,
    read_json_input,
    write_model_role_registry,
)


DEFAULT_OUTPUT_DIR = str(DEFAULT_OUTPUT_ROOT)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    registry = result["registry"]
    source = registry.get("source_inputs") or {}
    next_phase = registry.get("recommended_next_phase") or {}
    findings = registry.get("validation_findings") or {}
    coverage = registry.get("coverage_matrix") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": registry.get("report_kind"),
        "input_source": source.get("input_source"),
        "role_catalog_path": source.get("role_catalog_path"),
        "validation_status": registry.get("validation_status"),
        "role_count": registry.get("role_count"),
        "weak_role_count": findings.get("weak_role_count"),
        "coverage_status": coverage.get("coverage_status"),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": registry.get("warnings") or [],
        "blocked_reasons": registry.get("blocked_reasons") or [],
    }


def run_create_model_role_registry(
    *,
    role_catalog: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create MODEL.N1 registry artifacts and return paths plus summary data."""
    catalog_data, catalog_blockers = read_json_input(role_catalog, "role_catalog")
    selected_catalog = catalog_data
    if role_catalog and catalog_data is None:
        selected_catalog = {"roles": []}
    result = write_model_role_registry(
        output_dir=output_dir,
        role_catalog_path=str(role_catalog or ""),
        role_catalog=selected_catalog,
        input_blockers=catalog_blockers,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("MODEL.N1 - Model Role Registry / Tower Card Contract")
    print("=" * 54)
    print(f"Input source      : {summary['input_source']}")
    print(f"Catalog path      : {summary['role_catalog_path']}")
    print(f"Validation status : {summary['validation_status']}")
    print(f"Role count        : {summary['role_count']}")
    print(f"Weak role count   : {summary['weak_role_count']}")
    print(f"Coverage status   : {summary['coverage_status']}")
    print(f"Recommended next  : {summary['recommended_next_phase']}")
    print(f"JSON              : {summary['json_path']}")
    print(f"Markdown          : {summary['md_path']}")
    blocked = summary["blocked_reasons"]
    if blocked:
        print("Blocked reasons   :")
        for reason in blocked:
            print(f"  - {reason}")
    warnings = summary["warnings"]
    if warnings:
        print("Warnings          :")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"\n> {MODEL_ROLE_REGISTRY_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "MODEL.N1: write a report-only advisory model role registry. "
            "The registry validates tower-card metadata only; it does not route "
            "tasks, call models, launch workers, or bind executable model IDs."
        )
    )
    parser.add_argument("--role-catalog", help="Path to a manual model role catalog JSON file.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_model_role_registry(
        role_catalog=args.role_catalog,
        output_dir=args.output_dir,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
