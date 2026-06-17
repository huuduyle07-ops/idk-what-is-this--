"""AUTO.1a — Create a Sandbox Self-Evolution Trial Contract (report-only).

Defines and scores a single sandbox self-evolution attempt, then writes a
deterministic, report-only artifact describing whether the attempt would be safe
to try in a disposable sandbox and reviewable by a human afterwards.

This script never runs self-evolution. It never launches a model or an external
coding agent, edits the real repository, pushes, merges, opens a PR, runs
validation or the benchmark runner, runs Dream or Project Evolution, makes a
network call, promotes a lesson, imports a proposal, or launches a worker. It
only assembles the contract from the given values and writes the artifact under
``.agent/self_evolution_trials/``.

Usage:
    python scripts/create_sandbox_self_evolution_trial.py \\
        --phase-id AUTO.1a --phase-title "Tidy a helper" \\
        --automation-level SANDBOX_2_DRAFT_PATCH \\
        --allowed-files core/foo.py --validation "python -m pytest -q"
    python scripts/create_sandbox_self_evolution_trial.py \\
        --phase-id AUTO.1a --automation-level LOCAL_0_OBSERVE --json
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

from core.sandbox_self_evolution_trial import (  # noqa: E402
    AUTOMATION_LEVELS,
    BUDGET_TIERS,
    SCORE_DIMENSIONS,
    SELF_EVOLUTION_GUARDRAIL_NOTE,
    build_sandbox_self_evolution_trial,
    render_sandbox_self_evolution_trial_markdown,
)

#: Default location for trial artifacts, under the repo's ``.agent`` tree.
DEFAULT_OUTPUT_SUBPATH = Path(".agent") / "self_evolution_trials"
JSON_NAME = "self_evolution_trial.json"
MD_NAME = "self_evolution_trial.md"
PHASE_NAME = "selected_phase.md"
CONTRACT_NAME = "trial_contract.md"


def _resolve_created_at(raw: str | float | None) -> tuple[str, datetime | None]:
    """Return (iso_string, datetime_or_None) for the created-at hook.

    Accepts an ISO-8601 string (used verbatim), an epoch number, or None
    (uses the current UTC time). The datetime is None when ``raw`` is a literal
    ISO string we did not parse, which is fine — it is only used to derive a
    default trial id.
    """
    if raw is None:
        now = datetime.now(tz=timezone.utc)
        return now.isoformat(), now
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw), None
    moment = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return moment.isoformat(), moment


def _default_trial_id(iso: str, moment: datetime | None) -> str:
    if moment is not None:
        stamp = moment.strftime("%Y%m%d_%H%M%S")
    else:
        stamp = "".join(ch if ch.isalnum() else "-" for ch in iso).strip("-")[:24]
        stamp = stamp or "trial"
    return f"{stamp}_sandbox-self-evolution-trial"


def _flatten_csv(values: list[str] | None) -> list[str]:
    """Flatten repeated and/or comma-separated CLI values into a clean list."""
    out: list[str] = []
    for value in values or []:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                out.append(part)
    return out


def _selected_phase_md(record: dict[str, Any]) -> str:
    phase = record.get("phase") or {}
    lines = [
        "# Selected Phase",
        "",
        f"- Phase id: `{phase.get('id') or '(none)'}`",
        f"- Title: {phase.get('title') or '(untitled)'}",
    ]
    if phase.get("summary"):
        lines.append(f"- Summary: {phase['summary']}")
    lines += [
        f"- Automation level: `{record.get('automation_level', '')}`",
        f"  - {record.get('automation_level_summary', '')}",
        f"- Verdict: `{record.get('verdict', '')}`",
        f"- Next safe step: `{record.get('next_safe_step', '')}`",
        "",
    ]
    return "\n".join(lines) + "\n"


def _trial_contract_md(record: dict[str, Any]) -> str:
    lines = [
        "# Sandbox Self-Evolution Trial — Contract",
        "",
        f"> {record.get('guardrail_note', '')}",
        "",
        "## Boundaries",
        "",
        "- This trial does not run self-evolution.",
        "- This trial does not launch models or external agents.",
        "- This trial does not edit the real repo.",
        "- This trial does not push, merge, or open PRs.",
        "- This trial does not run validation or benchmarks.",
        "- Self-approval is forbidden.",
        "",
    ]
    return "\n".join(lines) + "\n"


def run_sandbox_self_evolution_trial(
    *,
    repo_path: str = ".",
    phase_id: str = "",
    phase_title: str = "",
    phase_summary: str = "",
    automation_level: str = "LOCAL_0_OBSERVE",
    allowed_files: list[str] | None = None,
    validation_commands: list[str] | None = None,
    budget_tier: str = "local_only",
    self_approval_allowed: bool = False,
    trial_id: str | None = None,
    created_at: str | float | None = None,
    output_root: str | None = None,
) -> dict[str, Any]:
    """Build the trial contract and write JSON + Markdown (+ companion files).

    Returns a result dict with ``ok``, ``json_path``, ``md_path``,
    ``phase_path``, ``contract_path``, and ``record``.
    """
    created_iso, moment = _resolve_created_at(created_at)
    final_trial_id = trial_id or _default_trial_id(created_iso, moment)

    record = build_sandbox_self_evolution_trial(
        phase_id=phase_id,
        phase_title=phase_title,
        phase_summary=phase_summary,
        automation_level=automation_level,
        allowed_files=allowed_files,
        validation_commands=validation_commands,
        budget_tier=budget_tier,
        self_approval_allowed=self_approval_allowed,
        repo_path=str(Path(repo_path).resolve()),
        trial_id=final_trial_id,
        created_at=created_iso,
    )

    # Resolve the output directory: <output_root>/<trial_id>/.
    if output_root:
        base_dir = Path(output_root)
    else:
        base_dir = Path(repo_path) / DEFAULT_OUTPUT_SUBPATH
    out_dir = base_dir / final_trial_id
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    phase_path = out_dir / PHASE_NAME
    contract_path = out_dir / CONTRACT_NAME

    json_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path.write_text(
        render_sandbox_self_evolution_trial_markdown(record), encoding="utf-8"
    )
    phase_path.write_text(_selected_phase_md(record), encoding="utf-8")
    contract_path.write_text(_trial_contract_md(record), encoding="utf-8")

    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "phase_path": str(phase_path),
        "contract_path": str(contract_path),
        "record": record,
    }


def _print_summary(result: dict[str, Any]) -> None:
    record = result["record"]
    phase = record.get("phase") or {}
    budget = record.get("budget") or {}
    print("AUTO.1a — Sandbox Self-Evolution Trial")
    print("=" * 40)
    print(
        f"Phase            : {phase.get('id') or '(none)'} "
        f"— {phase.get('title') or '(untitled)'}"
    )
    print(f"Automation level : {record.get('automation_level', '')}")
    print(f"Verdict          : {record.get('verdict', '')}")
    print(
        f"Human approval   : {str(record.get('human_approval_required', True)).lower()}"
    )
    print(
        f"External model   : {str(budget.get('external_model_allowed', False)).lower()}"
    )
    print(f"Sandbox required : {str(record.get('sandbox_required', True)).lower()}")
    print("Scorecard:")
    for dimension in SCORE_DIMENSIONS:
        print(f"  {dimension:<16}: {record['score'].get(dimension, '')}")
    print(f"Next safe step   : {record.get('next_safe_step', '')}")
    print(f"\nTrial id : {record.get('trial_id')}")
    print(f"JSON     : {result['json_path']}")
    print(f"Markdown : {result['md_path']}")
    print(f"\n> {SELF_EVOLUTION_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "AUTO.1a: define and score a sandbox self-evolution attempt and write "
            "a deterministic, report-only trial contract artifact. Does not run "
            "self-evolution, launch models or external agents, edit the real "
            "repo, push, merge, run validation, or run benchmarks."
        )
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Repo root (used to write artifacts; default: .).",
    )
    parser.add_argument("--phase-id", default="", help="Phase identifier.")
    parser.add_argument("--phase-title", default="", help="Phase title.")
    parser.add_argument(
        "--phase-summary", default="", help="One-line phase summary."
    )
    parser.add_argument(
        "--automation-level",
        default="LOCAL_0_OBSERVE",
        choices=list(AUTOMATION_LEVELS),
        help="Automation level to define and score (never executed).",
    )
    parser.add_argument(
        "--allowed-files",
        action="append",
        default=None,
        help="Allowed file paths (comma-separated and/or repeatable).",
    )
    parser.add_argument(
        "--validation",
        action="append",
        default=None,
        help="Validation command(s) to declare (comma-separated and/or repeatable).",
    )
    parser.add_argument(
        "--budget-tier",
        default="local_only",
        choices=list(BUDGET_TIERS),
        help="Budget tier for the attempt.",
    )
    parser.add_argument(
        "--trial-id",
        default=None,
        help="Deterministic trial id (also the artifact folder name).",
    )
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help=(
            "Override the artifact root "
            "(default: <repo-path>/.agent/self_evolution_trials)."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the trial JSON to stdout.",
    )
    args = parser.parse_args(argv)

    result = run_sandbox_self_evolution_trial(
        repo_path=args.repo_path,
        phase_id=args.phase_id,
        phase_title=args.phase_title,
        phase_summary=args.phase_summary,
        automation_level=args.automation_level,
        allowed_files=_flatten_csv(args.allowed_files),
        validation_commands=_flatten_csv(args.validation),
        budget_tier=args.budget_tier,
        trial_id=args.trial_id,
        created_at=args.created_at,
        output_root=args.output_root,
    )

    if args.json:
        print(json.dumps(result["record"], indent=2, ensure_ascii=False))
    else:
        _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
