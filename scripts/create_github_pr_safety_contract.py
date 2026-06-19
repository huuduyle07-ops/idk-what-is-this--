"""AUTO.2b — Create a GitHub Remote PR Safety Contract (CLI).

Reads one upstream evidence artifact (an AUTO.1e sandbox self-evolution evidence
pack or an AUTO.2a evidence summary contract) and writes a deterministic JSON +
Markdown contract describing what must be true before a *future* system may draft
a remote pull request.

This tool is report-only. It does not contact a remote git host, create branches,
push commits, open PRs, merge anything, call Webhooks, make any network request,
call models, apply patches, run validation or a benchmark check, write to the real
repo, or contact Telegram / N8N. A future PR is not merge authority.

Usage:
    python scripts/create_github_pr_safety_contract.py \\
        --source-artifact .agent/self_evolution_trials/<id>/self_evolution_evidence_pack.json
    python scripts/create_github_pr_safety_contract.py \\
        --source-artifact contract.json --output-root .agent/automation_contracts --json
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

from core.github_pr_safety_contract import (  # noqa: E402
    GITHUB_PR_SAFETY_GUARDRAIL_NOTE,
    render_github_pr_safety_contract_markdown,
    write_github_pr_safety_contract,
)

DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "automation_contracts")

#: Source verdicts that make a contract "not ready" and so refuse exit 0.
_REFUSED_VERDICTS = ("blocked", "incomplete_pack")


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _default_contract_id(created_iso: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'contract'}_pr-safety"


def _load_source_artifact(path: str) -> tuple[dict[str, Any] | None, str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not read source artifact at {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"source artifact at {path} is not a JSON object"
    return data, ""


def run_create_github_pr_safety_contract(
    *,
    source_artifact: str,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    contract_id: str | None = None,
    created_at: str | float | None = None,
    json_out: bool = False,
) -> dict[str, Any]:
    """Load the source artifact, build the contract, and write JSON + Markdown.

    Returns ``{ok, json_path, md_path, contract, is_pr_draft_allowed_in_future,
    refused}``. A source that cannot be read is recorded inside the contract (not a
    crash); ``refused`` is true when the source verdict is blocked/incomplete or the
    artifact was unreadable.
    """
    created_iso = _resolve_created_at(created_at)
    final_contract_id = contract_id or _default_contract_id(created_iso)

    data, load_error = _load_source_artifact(source_artifact)

    result = write_github_pr_safety_contract(
        data if data is not None else {},
        output_root,
        contract_id=final_contract_id,
        created_at=created_iso,
        source_artifact=str(source_artifact),
    )
    contract = result["contract"]

    if load_error:
        # Surface the read failure inside the written artifacts, deterministically.
        contract["warnings"] = sorted(set(list(contract.get("warnings") or []) + [load_error]))
        contract["blockers"] = sorted(set(list(contract.get("blockers") or []) + [load_error]))
        Path(result["json_path"]).write_text(
            json.dumps(contract, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        Path(result["md_path"]).write_text(
            render_github_pr_safety_contract_markdown(contract), encoding="utf-8"
        )

    result["is_pr_draft_allowed_in_future"] = bool(contract.get("is_pr_draft_allowed_in_future"))
    result["refused"] = bool(load_error) or contract.get("final_verdict") in _REFUSED_VERDICTS
    return result


def _print_summary(result: dict[str, Any]) -> None:
    contract = result["contract"]
    print("AUTO.2b — GitHub Remote PR Safety Contract")
    print("=" * 42)
    print(f"Contract id              : {contract.get('contract_id')}")
    print(f"Source artifact          : {contract.get('source_artifact')}")
    print(f"Source kind              : {contract.get('source_kind')}")
    print(f"Trial id                 : {contract.get('trial_id')}")
    print(f"Final verdict            : {contract.get('final_verdict')}")
    print(f"PR readiness             : {(contract.get('pr_readiness') or {}).get('status')}")
    print(f"Draft PR allowed (future): {contract.get('is_pr_draft_allowed_in_future')}")
    print(f"Merge allowed            : {contract.get('is_merge_allowed')}")
    print(f"Auto-merge allowed       : {contract.get('is_auto_merge_allowed')}")
    blockers = contract.get("blockers") or []
    if blockers:
        print("Blockers                 :")
        for blocker in blockers:
            print(f"  - {blocker}")
    warnings = contract.get("warnings") or []
    if warnings:
        print("Warnings                 :")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"JSON                     : {result['json_path']}")
    print(f"Markdown                 : {result['md_path']}")
    print(f"\n> {GITHUB_PR_SAFETY_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "AUTO.2b: read an AUTO.1e evidence pack or AUTO.2a evidence summary and write a "
            "remote-PR safety contract. Report-only — it does not contact GitHub, create "
            "branches, push commits, open or merge PRs, apply patches, run validation or a "
            "benchmark check, call a model, or run git."
        )
    )
    parser.add_argument("--source-artifact", required=True, help="Path to the AUTO.1e pack or AUTO.2a contract JSON.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory to write the contract into.")
    parser.add_argument("--contract-id", default=None, help="Deterministic contract id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument("--json", action="store_true", help="Print the contract JSON.")
    parser.add_argument(
        "--allow-blocked-contract",
        action="store_true",
        help="Write the contract and exit 0 even when the source is blocked or incomplete.",
    )
    args = parser.parse_args(argv)

    result = run_create_github_pr_safety_contract(
        source_artifact=args.source_artifact,
        output_root=args.output_root,
        contract_id=args.contract_id,
        created_at=args.created_at,
        json_out=args.json,
    )

    if args.json:
        print(json.dumps(result["contract"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)

    if result["refused"] and not args.allow_blocked_contract:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
