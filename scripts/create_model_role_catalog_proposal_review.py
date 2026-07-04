"""MODEL.N5 - Create a Model Role Catalog Proposal Review (CLI).

Writes deterministic JSON and Markdown review artifacts for the MODEL.N4
proposal before any human-approved adoption phase. The script does not replace
MODEL.N1, mutate proposed registries, route tasks, call models, launch workers,
bind executable model IDs, run validation or benchmarks, apply patches, contact
networks, write databases, or change runtime behavior.
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

from core.model_role_catalog_proposal_review import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    MODEL_ROLE_CATALOG_PROPOSAL_REVIEW_GUARDRAIL_NOTE,
    read_json_input,
    write_model_role_catalog_proposal_review,
)


DEFAULT_OUTPUT_DIR = str(DEFAULT_OUTPUT_ROOT)
PROPOSED_REGISTRY_NAME = "proposed_model_role_registry.json"


def _path_is_safe(path: str | None) -> bool:
    if path is None or str(path).strip() == "":
        return True
    segments = [segment for segment in str(path).replace("\\", "/").split("/") if segment]
    return ".." not in segments


def _existing_path(path: str | None) -> str | None:
    if path is None or str(path).strip() == "":
        return None
    if not _path_is_safe(path):
        return path
    return path if Path(path).is_file() else None


def _default_proposed_registry_path(proposal: str) -> str | None:
    if not _path_is_safe(proposal):
        return None
    candidate = Path(proposal).parent / PROPOSED_REGISTRY_NAME
    return str(candidate) if candidate.is_file() else None


def _default_source_registry_path(proposal_data: dict[str, Any] | None) -> str | None:
    if not isinstance(proposal_data, dict):
        return None
    value = str(proposal_data.get("source_model_registry_path") or "").strip()
    if not value or not _path_is_safe(value):
        return None
    return value if Path(value).is_file() else None


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    proposal = report.get("proposal_summary") or {}
    next_phase = report.get("recommended_next_phase") or {}
    return {
        "ok": bool(result.get("ok")),
        "json_path": result.get("json_path"),
        "md_path": result.get("md_path"),
        "report_kind": report.get("report_kind"),
        "review_status": report.get("review_status"),
        "adoption_readiness": report.get("adoption_readiness"),
        "source_proposal_path": report.get("source_proposal_path"),
        "source_registry_path": report.get("source_registry_path"),
        "proposed_registry_path": report.get("proposed_registry_path"),
        "source_role_count": proposal.get("source_role_count"),
        "proposed_role_count": proposal.get("proposed_role_count"),
        "proposed_new_role_count": proposal.get("proposed_new_role_count"),
        "warning_count": len(report.get("warnings") or []),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "recommended_next_phase": next_phase.get("phase_id"),
        "warnings": report.get("warnings") or [],
        "blocked_reasons": report.get("blocked_reasons") or [],
    }


def run_create_model_role_catalog_proposal_review(
    *,
    proposal: str,
    proposed_registry: str | None = None,
    source_registry: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Create MODEL.N5 review artifacts and return paths plus summary data."""
    proposal_data, proposal_blockers = read_json_input(proposal, "proposal", required=True)

    proposed_registry_path = proposed_registry
    if proposed_registry_path is None and proposal_data is not None:
        proposed_registry_path = _default_proposed_registry_path(proposal)
    proposed_data: dict[str, Any] | None = None
    proposed_blockers: list[str] = []
    if proposed_registry_path is not None:
        if not _path_is_safe(proposed_registry_path):
            proposed_data, proposed_blockers = read_json_input(proposed_registry_path, "proposed registry")
        elif _existing_path(proposed_registry_path) is not None:
            proposed_data, proposed_blockers = read_json_input(proposed_registry_path, "proposed registry")

    source_registry_path = source_registry
    if source_registry_path is None:
        source_registry_path = _default_source_registry_path(proposal_data)
    source_data: dict[str, Any] | None = None
    source_blockers: list[str] = []
    if source_registry_path is not None:
        if not _path_is_safe(source_registry_path):
            source_data, source_blockers = read_json_input(source_registry_path, "source registry")
        elif _existing_path(source_registry_path) is not None:
            source_data, source_blockers = read_json_input(source_registry_path, "source registry")

    result = write_model_role_catalog_proposal_review(
        proposal_path=proposal,
        proposed_registry_path=proposed_registry_path,
        source_registry_path=source_registry_path,
        output_dir=output_dir,
        proposal_data=proposal_data,
        proposed_registry_data=proposed_data,
        source_registry_data=source_data,
        input_blockers=proposal_blockers + proposed_blockers + source_blockers,
    )
    result["summary"] = _summary(result)
    return result


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("MODEL.N5 - Model Role Catalog Proposal Review")
    print("=" * 49)
    print(f"Review status   : {summary['review_status']}")
    print(f"Adoption        : {summary['adoption_readiness']}")
    print(f"Proposal        : {summary['source_proposal_path']}")
    print(f"Proposed catalog: {summary['proposed_registry_path']}")
    print(f"Source registry : {summary['source_registry_path']}")
    print(f"Source roles    : {summary['source_role_count']}")
    print(f"Proposed roles  : {summary['proposed_role_count']}")
    print(f"New roles       : {summary['proposed_new_role_count']}")
    print(f"Recommended next: {summary['recommended_next_phase']}")
    print(f"JSON            : {summary['json_path']}")
    print(f"Markdown        : {summary['md_path']}")
    if summary["blocked_reasons"]:
        print("Blocked reasons :")
        for reason in summary["blocked_reasons"]:
            print(f"  - {reason}")
    if summary["warnings"]:
        print("Warnings        :")
        for warning in summary["warnings"]:
            print(f"  - {warning}")
    print(f"\n> {MODEL_ROLE_CATALOG_PROPOSAL_REVIEW_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "MODEL.N5: write a report-only review of a MODEL.N4 proposed "
            "model-role catalog update. The review grants no routing, worker "
            "launch, model-call, patch, or executable model-binding authority."
        )
    )
    parser.add_argument("--proposal", required=True, help="Path to MODEL.N4 model_role_catalog_update_proposal.json.")
    parser.add_argument("--proposed-registry", help="Optional MODEL.N4 proposed_model_role_registry.json.")
    parser.add_argument("--source-registry", help="Optional MODEL.N1 model_role_registry.json.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    args = parser.parse_args(argv)

    result = run_create_model_role_catalog_proposal_review(
        proposal=args.proposal,
        proposed_registry=args.proposed_registry,
        source_registry=args.source_registry,
        output_dir=args.output_dir,
    )
    if args.json:
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
