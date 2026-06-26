"""UX.6 — Create Evidence Card Layout Preview (CLI).

Builds a report-only preview that formats operator-facing evidence cards
summarising what changed, what evidence exists, what checks say, what risks
remain, and what the human should do next.

UX.6 is a preview-only evidence layout phase.  It does not create new evidence,
dispatch execution, start runs, call AI services, apply patches, run validation
or benchmarks, contact network services, launch workers, mutate the repo,
push, merge, or open PRs.

Usage:
    python scripts/create_evidence_card_layout_preview.py \\
        --repo-path . \\
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

from core.evidence_card_layout import (  # noqa: E402
    GUARDRAIL_NOTE,
    PREVIEW_STATUS_READY,
    REPORT_KIND,
    build_evidence_card_layout_preview,
    write_evidence_card_layout_artifacts,
)

DEFAULT_REPO_PATH   = "."
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "ux" / "evidence_card_layout")


def _resolve_created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    return str(raw)


def run_create_evidence_card_layout_preview(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    preview_id: str | None = None,
    created_at: str | None = None,
    cards: list[dict] | None = None,
    card_json: str | None = None,
    demo: bool = False,
) -> dict[str, Any]:
    """Build and write the UX.6 Evidence Card Layout preview.  Returns {ok, json_path, md_path, report}."""
    created_iso = _resolve_created_at(created_at)

    resolved_cards: list[dict] | None = cards

    if resolved_cards is None and not demo and card_json:
        try:
            raw = json.loads(card_json)
            resolved_cards = raw if isinstance(raw, list) else [raw]
        except json.JSONDecodeError:
            resolved_cards = []

    report   = build_evidence_card_layout_preview(
        repo_path=repo_path,
        cards=resolved_cards,
        created_at=created_iso,
        preview_id=preview_id,
        demo=demo,
        ui_placeholder_added=True,
    )
    artifacts = write_evidence_card_layout_artifacts(report, output_root)
    return {**artifacts, "report": report}


def _print_summary(result: dict) -> None:
    report   = result["report"]
    cc       = report.get("card_counts", {})
    sc       = report.get("status_counts", {})
    miss     = report.get("missing_evidence_cards", [])
    decision = report.get("operator_decision_summary", "?")
    print("UX.6 — Evidence Card Layout Preview")
    print("=" * 42)
    print(f"Preview id       : {report.get('preview_id')}")
    print(f"Repo path        : {report.get('repo_path')}")
    print(f"Preview status   : {report.get('preview_status')}")
    print(f"Card count       : {len(report.get('cards', []))}")
    print(f"Card counts      : {cc}")
    print(f"Status counts    : {sc}")
    print(f"Missing evidence : {miss}")
    print(f"Decision         : {decision}")
    print(f"JSON             : {result.get('json_path')}")
    print(f"Markdown         : {result.get('md_path')}")
    print()
    print("Evidence cards:")
    for card in report.get("cards", []):
        cid  = card.get("card_id", "?")
        cst  = card.get("status", "?")
        cpri = card.get("priority", "?")
        ctitle = card.get("title", "?")
        print(f"  [{cid}] {ctitle}  status={cst}  priority={cpri}")
    print()
    print("Boundaries (UX.6 does not):")
    for b in report.get("boundaries", []):
        print(f"  {b}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="UX.6 — Create Evidence Card Layout Preview (report-only)"
    )
    parser.add_argument("--repo-path",    default=DEFAULT_REPO_PATH)
    parser.add_argument("--output-root",  default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--preview-id",   default=None)
    parser.add_argument("--created-at",   default=None)
    parser.add_argument("--card-json",    default=None,
                        help="JSON array of raw card dicts")
    parser.add_argument("--demo",   action="store_true", default=False)
    parser.add_argument("--json",   dest="json_out", action="store_true", default=False)

    args   = parser.parse_args(argv)
    result = run_create_evidence_card_layout_preview(
        repo_path=args.repo_path,
        output_root=args.output_root,
        preview_id=args.preview_id,
        created_at=args.created_at,
        card_json=args.card_json,
        demo=args.demo,
    )

    if args.json_out:
        report  = result["report"]
        summary = {
            "report_kind":              report.get("report_kind", REPORT_KIND),
            "preview_id":               report.get("preview_id"),
            "preview_status":           report.get("preview_status"),
            "card_counts":              report.get("card_counts", {}),
            "status_counts":            report.get("status_counts", {}),
            "missing_evidence_cards":   report.get("missing_evidence_cards", []),
            "operator_decision_summary": report.get("operator_decision_summary"),
            "json_path":                result.get("json_path"),
            "md_path":                  result.get("md_path"),
        }
        print(json.dumps(summary, indent=2))
    else:
        _print_summary(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
