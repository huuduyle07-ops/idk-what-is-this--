"""UX.5 — Create Goal Brief 4W1H Preview (CLI).

Builds a report-only preview that scores a Goal Brief across five 4W1H
dimensions (What / Why / Where / When-stop / How-validate) and suggests
a mode hint (instant_run_preview, commander_contract_preview, clarify, chat).

UX.5 simplifies task intake only.  It does not execute the task, start a run,
call models, apply patches, run validation or benchmarks, contact network
services, launch workers, mutate the repo, push, merge, or open PRs.

Usage:
    python scripts/create_goal_brief_4w1h_preview.py \\
        --repo-path . \\
        --what "Add completeness scoring" \\
        --why "Operators need clearer intake" \\
        --where "core/goal_brief_4w1h.py" \\
        --when-stop "When all tests pass" \\
        --how-validate "python -m pytest tests/ -q" \\
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

from core.goal_brief_4w1h import (  # noqa: E402
    GUARDRAIL_NOTE,
    PREVIEW_STATUS_READY,
    REPORT_KIND,
    build_goal_brief_4w1h_preview,
    write_goal_brief_4w1h_artifacts,
)

DEFAULT_REPO_PATH   = "."
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "ux" / "goal_brief_4w1h")


def _resolve_created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    return str(raw)


def run_create_goal_brief_4w1h_preview(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    preview_id: str | None = None,
    created_at: str | None = None,
    briefs: list[dict] | None = None,
    brief_json: str | None = None,
    what: str | None = None,
    why: str | None = None,
    where: str | None = None,
    when_stop: str | None = None,
    how_validate: str | None = None,
    constraints: list[str] | None = None,
    risk_notes: list[str] | None = None,
    examples: list[str] | None = None,
    non_goals: list[str] | None = None,
    operator_notes: list[str] | None = None,
    demo: bool = False,
) -> dict[str, Any]:
    """Build and write the UX.5 4W1H Goal Brief preview.  Returns {ok, json_path, md_path, report}."""
    created_iso = _resolve_created_at(created_at)

    resolved_briefs: list[dict] | None = briefs

    # Build a brief from individual field kwargs if provided
    if resolved_briefs is None and not demo:
        field_kwargs = {k: v for k, v in {
            "what": what,
            "why": why,
            "where": where,
            "when_stop": when_stop,
            "how_validate": how_validate,
        }.items() if v is not None}

        if brief_json:
            try:
                raw = json.loads(brief_json)
                resolved_briefs = raw if isinstance(raw, list) else [raw]
            except json.JSONDecodeError:
                resolved_briefs = []
        elif field_kwargs:
            resolved_briefs = [{
                "brief_id":    "inline-brief",
                "created_at":  created_iso,
                "repo_path":   repo_path,
                "fields":      field_kwargs,
                "constraints": list(constraints or []),
                "risk_notes":  list(risk_notes or []),
                "examples":    list(examples or []),
                "non_goals":   list(non_goals or []),
                "operator_notes": list(operator_notes or []),
            }]

    report = build_goal_brief_4w1h_preview(
        repo_path=repo_path,
        briefs=resolved_briefs,
        created_at=created_iso,
        preview_id=preview_id,
        demo=demo,
        ui_placeholder_added=True,
    )

    artifacts = write_goal_brief_4w1h_artifacts(report, output_root)
    return {**artifacts, "report": report}


def _print_summary(result: dict) -> None:
    report = result["report"]
    mfc = report.get("missing_field_counts", {})
    rmc = report.get("recommended_mode_counts", {})
    print("UX.5 — Goal Brief 4W1H Preview")
    print("=" * 40)
    print(f"Preview id          : {report.get('preview_id')}")
    print(f"Repo path           : {report.get('repo_path')}")
    print(f"Preview status      : {report.get('preview_status')}")
    print(f"Brief count         : {report.get('brief_count', 0)}")
    print(f"Avg completeness    : {report.get('average_completion_score', 0)}/100")
    print(f"Clarifying questions: {report.get('clarifying_question_count', 0)}")
    print(f"Missing fields      : {mfc}")
    print(f"Recommended modes   : {rmc}")
    print(f"JSON                : {result.get('json_path')}")
    print(f"Markdown            : {result.get('md_path')}")
    print()
    print("Brief previews:")
    for bp in report.get("brief_previews", []):
        bid  = bp.get("brief_id", "?")
        sc   = bp.get("completion_score", 0)
        hint = bp.get("recommended_mode_hint", "?")
        print(f"  [{bid}] score={sc}/100  hint={hint}")
    print()
    print("Boundaries (UX.5 does not):")
    for b in report.get("boundaries", []):
        print(f"  {b}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="UX.5 — Create Goal Brief 4W1H Preview (report-only)"
    )
    parser.add_argument("--repo-path",   default=DEFAULT_REPO_PATH)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--preview-id",  default=None)
    parser.add_argument("--created-at",  default=None)
    parser.add_argument("--what",        default=None, help="What should change?")
    parser.add_argument("--why",         default=None, help="Why is this change needed?")
    parser.add_argument("--where",       default=None, help="Where should C.A.T.T.U.S focus?")
    parser.add_argument("--when-stop",   default=None, dest="when_stop",
                        help="When should C.A.T.T.U.S stop?")
    parser.add_argument("--how-validate", default=None, dest="how_validate",
                        help="How should the result be validated?")
    parser.add_argument("--constraint",  dest="constraints", action="append",
                        default=None, metavar="TEXT", help="Add a constraint (repeatable)")
    parser.add_argument("--risk-note",   dest="risk_notes", action="append",
                        default=None, metavar="TEXT", help="Add a risk note (repeatable)")
    parser.add_argument("--example",     dest="examples", action="append",
                        default=None, metavar="TEXT", help="Add an example (repeatable)")
    parser.add_argument("--non-goal",    dest="non_goals", action="append",
                        default=None, metavar="TEXT", help="Add a non-goal (repeatable)")
    parser.add_argument("--operator-note", dest="operator_notes", action="append",
                        default=None, metavar="TEXT", help="Add an operator note (repeatable)")
    parser.add_argument("--brief-json",  default=None,
                        help="JSON array of brief dicts")
    parser.add_argument("--demo",   action="store_true", default=False)
    parser.add_argument("--json",   dest="json_out", action="store_true", default=False)

    args = parser.parse_args(argv)

    result = run_create_goal_brief_4w1h_preview(
        repo_path=args.repo_path,
        output_root=args.output_root,
        preview_id=args.preview_id,
        created_at=args.created_at,
        what=args.what,
        why=args.why,
        where=args.where,
        when_stop=args.when_stop,
        how_validate=args.how_validate,
        constraints=args.constraints,
        risk_notes=args.risk_notes,
        examples=args.examples,
        non_goals=args.non_goals,
        operator_notes=args.operator_notes,
        brief_json=args.brief_json,
        demo=args.demo,
    )

    if args.json_out:
        report = result["report"]
        summary = {
            "report_kind":    report.get("report_kind", REPORT_KIND),
            "preview_id":     report.get("preview_id"),
            "preview_status": report.get("preview_status"),
            "brief_count":    report.get("brief_count", 0),
            "average_completion_score": report.get("average_completion_score", 0),
            "missing_field_counts":     report.get("missing_field_counts", {}),
            "recommended_mode_counts":  report.get("recommended_mode_counts", {}),
            "clarifying_question_count": report.get("clarifying_question_count", 0),
            "json_path": result.get("json_path"),
            "md_path":   result.get("md_path"),
        }
        print(json.dumps(summary, indent=2))
    else:
        _print_summary(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
