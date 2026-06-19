"""AUTO.2c — Create an n8n Orchestration Dry Run (CLI).

Reads one or more upstream artifacts (an AUTO.1e self-evolution evidence pack, an
AUTO.2a evidence summary contract, and/or an AUTO.2b PR safety contract) and writes
a deterministic JSON + Markdown report that *simulates* how a future n8n workflow
would orchestrate the review chain.

This tool is report-only. It does not contact n8n, call Webhooks, make any network
request, send Telegram messages, contact GitHub, run Git commands, create branches,
open or merge PRs, push commits, call models, launch workers, apply patches, or run
validation or a benchmark check. Live execution is never performed.

Usage:
    python scripts/create_n8n_orchestration_dry_run.py \\
        --evidence-pack pack.json --telegram-contract tg.json --github-pr-contract gh.json
    python scripts/create_n8n_orchestration_dry_run.py \\
        --evidence-pack pack.json --output-root .agent/automation_contracts --json
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

from core.n8n_orchestration_dry_run import (  # noqa: E402
    N8N_ORCHESTRATION_GUARDRAIL_NOTE,
    write_n8n_orchestration_dry_run,
)

DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "automation_contracts")

#: Overall verdict that makes a dry run "not ready" and so refuses exit 0.
_REFUSED_VERDICTS = ("blocked",)


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _default_dry_run_id(created_iso: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'dry-run'}_n8n-orchestration"


def _load_artifact(path: str) -> dict[str, Any]:
    """Return a source record ``{path, artifact, load_error}`` (never raises)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"path": path, "artifact": None, "load_error": f"could not read artifact at {path}: {exc}"}
    if not isinstance(data, dict):
        return {"path": path, "artifact": None, "load_error": f"artifact at {path} is not a JSON object"}
    return {"path": path, "artifact": data, "load_error": ""}


def run_create_n8n_orchestration_dry_run(
    *,
    evidence_pack: str | None = None,
    telegram_contract: str | None = None,
    github_pr_contract: str | None = None,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    dry_run_id: str | None = None,
    created_at: str | float | None = None,
    json_out: bool = False,
) -> dict[str, Any]:
    """Load any provided artifacts, build the dry run, and write JSON + Markdown.

    Returns ``{ok, json_path, md_path, report, overall_verdict, refused}``. Unreadable
    artifacts are recorded inside the report (not a crash); ``refused`` is true when the
    overall verdict is blocked (which covers missing/incomplete/breach sources).
    """
    created_iso = _resolve_created_at(created_at)
    final_dry_run_id = dry_run_id or _default_dry_run_id(created_iso)

    sources: list[dict[str, Any]] = []
    for path in (evidence_pack, telegram_contract, github_pr_contract):
        if path:
            sources.append(_load_artifact(path))

    result = write_n8n_orchestration_dry_run(
        sources, output_root, dry_run_id=final_dry_run_id, created_at=created_iso
    )
    report = result["report"]
    result["overall_verdict"] = report.get("overall_verdict")
    result["refused"] = report.get("overall_verdict") in _REFUSED_VERDICTS
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    print("AUTO.2c — n8n Orchestration Dry Run")
    print("=" * 34)
    print(f"Dry-run id               : {report.get('dry_run_id')}")
    print(f"Detected sources         : {', '.join(report.get('detected_sources') or []) or '(none)'}")
    print(f"Trial id                 : {report.get('trial_id')}")
    print(f"Overall verdict          : {report.get('overall_verdict')}")
    print(f"Orchestration (future)   : {report.get('is_orchestration_allowed_in_future')}")
    print(f"Live execution allowed   : {report.get('is_live_execution_allowed')}")
    print(f"Merge allowed            : {report.get('is_merge_allowed')}")
    print(f"Auto-merge allowed       : {report.get('is_auto_merge_allowed')}")
    blockers = report.get("blockers") or []
    if blockers:
        print("Blockers                 :")
        for blocker in blockers:
            print(f"  - {blocker}")
    warnings = report.get("warnings") or []
    if warnings:
        print("Warnings                 :")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"JSON                     : {result['json_path']}")
    print(f"Markdown                 : {result['md_path']}")
    print(f"\n> {N8N_ORCHESTRATION_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "AUTO.2c: read AUTO.1e / AUTO.2a / AUTO.2b artifacts and write a simulated "
            "orchestration dry run. Report-only — it does not contact n8n, call Webhooks, "
            "send Telegram messages, contact GitHub, run Git, launch workers, or call a model."
        )
    )
    parser.add_argument("--evidence-pack", default=None, help="Path to the AUTO.1e evidence pack JSON.")
    parser.add_argument("--telegram-contract", default=None, help="Path to the AUTO.2a evidence summary contract JSON.")
    parser.add_argument("--github-pr-contract", default=None, help="Path to the AUTO.2b PR safety contract JSON.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory to write the report into.")
    parser.add_argument("--dry-run-id", default=None, help="Deterministic dry-run id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument("--json", action="store_true", help="Print the dry-run report JSON.")
    parser.add_argument(
        "--allow-blocked-dry-run",
        action="store_true",
        help="Write the report and exit 0 even when the dry run is blocked or incomplete.",
    )
    args = parser.parse_args(argv)

    result = run_create_n8n_orchestration_dry_run(
        evidence_pack=args.evidence_pack,
        telegram_contract=args.telegram_contract,
        github_pr_contract=args.github_pr_contract,
        output_root=args.output_root,
        dry_run_id=args.dry_run_id,
        created_at=args.created_at,
        json_out=args.json,
    )

    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)

    if result["refused"] and not args.allow_blocked_dry_run:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
