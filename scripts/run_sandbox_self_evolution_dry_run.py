"""AUTO.1b — Run a Sandbox Self-Evolution Dry Run (CLI).

Copies the repo into a disposable managed sandbox, runs only declared safe
validation commands there (A.18 safe validation path), records A.19 side
effects, and writes a dry-run artifact under
``.agent/self_evolution_trials/<trial_id>/``.

It refuses to run when the AUTO.1a trial contract is blocked, allows
self-approval, is eligible for an automatic merge, targets the
``AUTO_4_AUTO_MERGE`` or ``REMOTE_3_DRAFT_PR`` level, or does not require a
sandbox / human approval.

It never calls a model, generates a patch, applies a patch to the real repo,
pushes, merges, opens a PR, contacts a remote git host / chat service / external
automation, runs Dream or Project Evolution, promotes a lesson, imports a
proposal, or launches a worker.

Usage:
    python scripts/run_sandbox_self_evolution_dry_run.py \\
        --repo-path . --automation-level LOCAL_0_OBSERVE \\
        --validation-json '["python","-m","compileall","-q","core"]'
    python scripts/run_sandbox_self_evolution_dry_run.py \\
        --trial-contract .agent/self_evolution_trials/<id>/self_evolution_trial.json \\
        --validation "python -m pytest -q tests/test_x.py" --cleanup
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

from core.sandbox_self_evolution_runner import (  # noqa: E402
    DEFAULT_VALIDATION_TIMEOUT_SEC,
    SANDBOX_DRY_RUN_GUARDRAIL_NOTE,
    render_sandbox_dry_run_markdown,
    run_dry_run,
)
from core.sandbox_self_evolution_trial import (  # noqa: E402
    build_sandbox_self_evolution_trial,
)
from core.validation_execution import parse_safe_validation_command  # noqa: E402

DEFAULT_OUTPUT_SUBPATH = Path(".agent") / "self_evolution_trials"
DEFAULT_SANDBOX_SUBPATH = Path(".agent") / "self_evolution_sandboxes"
JSON_NAME = "sandbox_dry_run.json"
MD_NAME = "sandbox_dry_run.md"


def _resolve_created_at(raw: str | float | None) -> tuple[str, datetime | None]:
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
    return f"{stamp}_sandbox-dry-run"


def _flatten_csv(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for value in values or []:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                out.append(part)
    return out


def _load_contract(path: str) -> tuple[dict[str, Any] | None, str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not read trial contract: {exc}"
    if not isinstance(data, dict):
        return None, "trial contract JSON must be an object"
    return data, ""


def _collect_validation_commands(
    validation_json: list[str] | None,
    validation_texts: list[str] | None,
    repo_path: str,
    timeout_sec: int,
    allowed_tools: tuple[str, ...],
) -> tuple[list[list[str]], list[str]]:
    """Build argv lists from --validation-json arrays and --validation text."""
    commands: list[list[str]] = []
    errors: list[str] = []
    for raw in validation_json or []:
        try:
            argv = json.loads(raw)
        except ValueError as exc:
            errors.append(f"invalid --validation-json {raw!r}: {exc}")
            continue
        if isinstance(argv, list) and argv and all(isinstance(p, str) for p in argv):
            commands.append([str(p) for p in argv])
        else:
            errors.append(
                f"--validation-json must be a non-empty array of strings: {raw!r}"
            )
    for text in validation_texts or []:
        command, reason = parse_safe_validation_command(
            text, cwd=repo_path, timeout_sec=timeout_sec, allowed_tools=allowed_tools
        )
        if command is None:
            errors.append(f"--validation {text!r} rejected: {reason}")
        else:
            commands.append(list(command.command))
    return commands, errors


def run_sandbox_self_evolution_dry_run(
    *,
    repo_path: str = ".",
    contract: dict[str, Any] | None = None,
    trial_contract: str | None = None,
    validation_commands: list[list[str]] | None = None,
    automation_level: str = "LOCAL_0_OBSERVE",
    phase_id: str = "",
    phase_title: str = "",
    phase_summary: str = "",
    allowed_files: list[str] | None = None,
    budget_tier: str = "local_only",
    timeout_sec: int = DEFAULT_VALIDATION_TIMEOUT_SEC,
    trial_id: str | None = None,
    created_at: str | float | None = None,
    cleanup: bool = False,
    sandbox_root: str | None = None,
    output_root: str | None = None,
    allowed_tools: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Resolve the contract, run the dry run, and write JSON + Markdown."""
    created_iso, moment = _resolve_created_at(created_at)
    final_trial_id = trial_id or _default_trial_id(created_iso, moment)

    # Resolve the contract: explicit dict > loaded path > built from CLI args.
    contract_source = "args"
    if contract is None and trial_contract:
        contract, err = _load_contract(trial_contract)
        if contract is None:
            return {"ok": False, "error": err, "json_path": None, "md_path": None}
        contract_source = "trial_contract_file"
    if contract is None:
        contract = build_sandbox_self_evolution_trial(
            phase_id=phase_id or final_trial_id,
            phase_title=phase_title,
            phase_summary=phase_summary,
            automation_level=automation_level,
            allowed_files=allowed_files,
            validation_commands=[" ".join(c) for c in (validation_commands or [])],
            budget_tier=budget_tier,
            repo_path=str(Path(repo_path).resolve()),
            trial_id=final_trial_id,
            created_at=created_iso,
        )
        contract_source = "args"

    sandbox_root_path = sandbox_root or str(Path(repo_path) / DEFAULT_SANDBOX_SUBPATH)

    record = run_dry_run(
        repo_path=repo_path,
        contract=contract,
        validation_commands=validation_commands or [],
        timeout_sec=timeout_sec,
        trial_id=final_trial_id,
        created_at=created_iso,
        sandbox_root=sandbox_root_path,
        cleanup=cleanup,
        allowed_tools=allowed_tools,
    )
    record["contract_source"] = contract_source

    if output_root:
        base_dir = Path(output_root)
    else:
        base_dir = Path(repo_path) / DEFAULT_OUTPUT_SUBPATH
    out_dir = base_dir / final_trial_id
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path.write_text(render_sandbox_dry_run_markdown(record), encoding="utf-8")

    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "record": record,
    }


def _print_summary(result: dict[str, Any]) -> None:
    record = result["record"]
    side_effects = record.get("side_effects") or {}
    summary = side_effects.get("summary") or {}
    print("AUTO.1b — Sandbox Self-Evolution Dry Run")
    print("=" * 42)
    print(f"Trial id         : {record.get('trial_id')}")
    print(f"Source repo      : {record.get('source_repo')}")
    print(f"Sandbox path     : {record.get('sandbox_path') or '(not created)'}")
    print(f"Contract verdict : {record.get('contract_verdict') or '(none)'}")
    print(f"Dry-run verdict  : {record.get('dry_run_verdict')}")
    print(f"Validation       : {record.get('validation_status')}")
    if record.get("contract_block_reason"):
        print(f"Blocked because  : {record['contract_block_reason']}")
    print(
        "Side effects     : "
        f"+{summary.get('created', 0)} ~{summary.get('modified', 0)} "
        f"-{summary.get('deleted', 0)} "
        f"(sandbox-only={record.get('side_effects_sandbox_only')})"
    )
    print(f"Cleanup          : {'performed' if record.get('cleanup_performed') else 'kept'}")
    print(f"JSON             : {result['json_path']}")
    print(f"Markdown         : {result['md_path']}")
    print(f"\n> {SANDBOX_DRY_RUN_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "AUTO.1b: copy the repo into a disposable managed sandbox and run "
            "only declared safe validation commands there. Never modifies the "
            "real repo, generates patches, or calls models."
        )
    )
    parser.add_argument("--repo-path", default=".", help="Repo root to copy (default: .).")
    parser.add_argument(
        "--trial-contract",
        default=None,
        help="Path to an AUTO.1a trial contract JSON (gates the dry run).",
    )
    parser.add_argument(
        "--automation-level",
        default="LOCAL_0_OBSERVE",
        help="Automation level when building a contract from args (no --trial-contract).",
    )
    parser.add_argument("--phase-id", default="")
    parser.add_argument("--phase-title", default="")
    parser.add_argument("--phase-summary", default="")
    parser.add_argument("--allowed-files", action="append", default=None)
    parser.add_argument("--budget-tier", default="local_only")
    parser.add_argument(
        "--validation",
        action="append",
        default=None,
        help="Safe validation command text (repeatable); shell metacharacters are rejected.",
    )
    parser.add_argument(
        "--validation-json",
        action="append",
        default=None,
        help=(
            "Safe validation argv as a JSON array, e.g. "
            "'[\"python\",\"-m\",\"compileall\",\"-q\",\"core\"]' (repeatable)."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_VALIDATION_TIMEOUT_SEC,
        help=f"Per-command timeout in seconds (default: {DEFAULT_VALIDATION_TIMEOUT_SEC}).",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete the managed sandbox after the dry run.",
    )
    parser.add_argument(
        "--sandbox-root",
        default=None,
        help="Override the managed sandbox root (default: <repo>/.agent/self_evolution_sandboxes).",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Override the artifact root (default: <repo>/.agent/self_evolution_trials).",
    )
    parser.add_argument("--trial-id", default=None, help="Deterministic trial id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument("--json", action="store_true", help="Print the record JSON.")
    args = parser.parse_args(argv)

    commands, errors = _collect_validation_commands(
        args.validation_json, args.validation, args.repo_path, args.timeout, ()
    )
    for err in errors:
        print(f"Warning: {err}")

    result = run_sandbox_self_evolution_dry_run(
        repo_path=args.repo_path,
        trial_contract=args.trial_contract,
        validation_commands=commands,
        automation_level=args.automation_level,
        phase_id=args.phase_id,
        phase_title=args.phase_title,
        phase_summary=args.phase_summary,
        allowed_files=_flatten_csv(args.allowed_files),
        budget_tier=args.budget_tier,
        timeout_sec=args.timeout,
        trial_id=args.trial_id,
        created_at=args.created_at,
        cleanup=args.cleanup,
        sandbox_root=args.sandbox_root,
        output_root=args.output_root,
    )

    if not result["ok"]:
        print(f"Error: {result.get('error', 'unknown error')}")
        return 1

    if args.json:
        print(json.dumps(result["record"], indent=2, ensure_ascii=False))
    else:
        _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
