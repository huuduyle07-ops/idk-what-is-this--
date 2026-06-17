"""AUTO.1c — Evaluate a Sandbox Patch Candidate (CLI).

Writes a *provided* patch candidate into a disposable managed sandbox, runs only
declared A.18-safe validation there, reports A.19 side effects, and writes an
evaluation artifact under ``.agent/self_evolution_trials/<trial_id>/``.

The patch is applied to the sandbox copy only — never to the real repo — and the
evaluator never generates a patch. It refuses to run when the AUTO.1a contract is
blocked, allows self-approval, is eligible for an automatic merge, targets the
``AUTO_4_AUTO_MERGE`` / ``REMOTE_3_DRAFT_PR`` level, or is below the sandbox patch
level. Patch candidates may be tested in a sandbox; they may not graduate without
human review.

Usage:
    python scripts/evaluate_sandbox_patch_candidate.py --repo-path . \\
        --patch-file candidate.patch \\
        --validation-json '["python","-m","compileall","-q","core"]'
    python scripts/evaluate_sandbox_patch_candidate.py --repo-path . \\
        --trial-contract .agent/self_evolution_trials/<id>/self_evolution_trial.json \\
        --patch-file candidate.patch --cleanup
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

from core.sandbox_patch_candidate_evaluation import (  # noqa: E402
    PATCH_EVAL_GUARDRAIL_NOTE,
    evaluate_patch_candidate,
    parse_unified_diff,
    render_patch_candidate_evaluation_markdown,
)
from core.sandbox_self_evolution_runner import (  # noqa: E402
    DEFAULT_VALIDATION_TIMEOUT_SEC,
)
from core.sandbox_self_evolution_trial import (  # noqa: E402
    build_sandbox_self_evolution_trial,
)

DEFAULT_OUTPUT_SUBPATH = Path(".agent") / "self_evolution_trials"
DEFAULT_SANDBOX_SUBPATH = Path(".agent") / "self_evolution_sandboxes"
JSON_NAME = "patch_candidate_evaluation.json"
MD_NAME = "patch_candidate_evaluation.md"


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
    return f"{stamp}_patch-candidate-eval"


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
) -> tuple[list[list[str]], list[str]]:
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
            errors.append(f"--validation-json must be a non-empty array of strings: {raw!r}")
    return commands, errors


def run_evaluate_sandbox_patch_candidate(
    *,
    repo_path: str = ".",
    patch_file: str | None = None,
    patch_text: str | None = None,
    contract: dict[str, Any] | None = None,
    trial_contract: str | None = None,
    validation_commands: list[list[str]] | None = None,
    automation_level: str = "SANDBOX_2_DRAFT_PATCH",
    budget_tier: str = "local_only",
    timeout_sec: int = DEFAULT_VALIDATION_TIMEOUT_SEC,
    trial_id: str | None = None,
    created_at: str | float | None = None,
    cleanup: bool = False,
    sandbox_root: str | None = None,
    output_root: str | None = None,
    allow_large: bool = False,
    allow_below_sandbox_level: bool = False,
    allowed_tools: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Read the patch, resolve the contract, evaluate, and write JSON + Markdown."""
    # Resolve the patch text — an explicit file is required.
    if patch_text is None:
        if not patch_file:
            return {"ok": False, "error": "a patch file is required (--patch-file)", "json_path": None, "md_path": None}
        try:
            patch_text = Path(patch_file).read_text(encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "error": f"could not read patch file: {exc}", "json_path": None, "md_path": None}
        patch_source = str(patch_file)
    else:
        patch_source = patch_file or "(inline)"

    created_iso, moment = _resolve_created_at(created_at)
    final_trial_id = trial_id or _default_trial_id(created_iso, moment)
    parsed = parse_unified_diff(patch_text)

    # Resolve the contract: explicit dict > loaded path > built from args.
    if contract is None and trial_contract:
        contract, err = _load_contract(trial_contract)
        if contract is None:
            return {"ok": False, "error": err, "json_path": None, "md_path": None}
    if contract is None:
        contract = build_sandbox_self_evolution_trial(
            phase_id=final_trial_id,
            automation_level=automation_level,
            allowed_files=parsed["touched_paths"],
            validation_commands=[" ".join(c) for c in (validation_commands or [])],
            budget_tier=budget_tier,
            repo_path=str(Path(repo_path).resolve()),
            trial_id=final_trial_id,
            created_at=created_iso,
        )

    sandbox_root_path = sandbox_root or str(Path(repo_path) / DEFAULT_SANDBOX_SUBPATH)

    record = evaluate_patch_candidate(
        repo_path=repo_path,
        contract=contract,
        patch_text=patch_text,
        patch_source=patch_source,
        validation_commands=validation_commands or [],
        timeout_sec=timeout_sec,
        trial_id=final_trial_id,
        created_at=created_iso,
        sandbox_root=sandbox_root_path,
        cleanup=cleanup,
        allowed_tools=allowed_tools,
        allow_large=allow_large,
        allow_below_sandbox_level=allow_below_sandbox_level,
    )

    if output_root:
        base_dir = Path(output_root)
    else:
        base_dir = Path(repo_path) / DEFAULT_OUTPUT_SUBPATH
    out_dir = base_dir / final_trial_id
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_patch_candidate_evaluation_markdown(record), encoding="utf-8")

    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "record": record}


def _print_summary(result: dict[str, Any]) -> None:
    record = result["record"]
    print("AUTO.1c — Sandbox Patch Candidate Evaluation")
    print("=" * 46)
    print(f"Trial id         : {record.get('trial_id')}")
    print(f"Patch file       : {record.get('patch_source') or '(inline)'}")
    print(f"Sandbox path     : {record.get('sandbox_path') or '(not created)'}")
    print(f"Verdict          : {record.get('verdict')}")
    print(f"Validation       : {record.get('validation_status')}")
    print(f"Applied to sandbox: {record.get('patch_applied_to_sandbox')}")
    if record.get("contract_block_reason"):
        print(f"Blocked because  : {record['contract_block_reason']}")
    if record.get("apply_error"):
        print(f"Apply error      : {record['apply_error']}")
    rejected = (record.get("patch_safety") or {}).get("rejected_paths") or []
    if rejected:
        print("Rejected paths   :")
        for entry in rejected:
            print(f"  {entry.get('path')}: {entry.get('reason')}")
    print(f"Cleanup          : {'performed' if record.get('cleanup_performed') else 'kept'}")
    print(f"JSON             : {result['json_path']}")
    print(f"Markdown         : {result['md_path']}")
    print(f"\n> {PATCH_EVAL_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "AUTO.1c: write a provided patch candidate into a disposable managed "
            "sandbox and run only declared safe validation there. Never writes to "
            "the real repo and never generates a patch."
        )
    )
    parser.add_argument("--repo-path", default=".", help="Repo root to copy (default: .).")
    parser.add_argument(
        "--trial-contract",
        default=None,
        help="Path to an AUTO.1a trial contract JSON (gates the evaluation).",
    )
    parser.add_argument("--patch-file", default=None, help="Path to the patch candidate file (required).")
    parser.add_argument(
        "--automation-level",
        default="SANDBOX_2_DRAFT_PATCH",
        help="Automation level when building a contract from args (no --trial-contract).",
    )
    parser.add_argument("--budget-tier", default="local_only")
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
        "--allow-large",
        action="store_true",
        help="Mark an oversized patch for manual review instead of rejecting it.",
    )
    parser.add_argument("--cleanup", action="store_true", help="Delete the managed sandbox afterwards.")
    parser.add_argument("--sandbox-root", default=None, help="Override the managed sandbox root.")
    parser.add_argument("--output-root", default=None, help="Override the artifact root.")
    parser.add_argument("--trial-id", default=None, help="Deterministic trial id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument("--json", action="store_true", help="Print the record JSON.")
    args = parser.parse_args(argv)

    commands, errors = _collect_validation_commands(args.validation_json)
    for err in errors:
        print(f"Warning: {err}")

    result = run_evaluate_sandbox_patch_candidate(
        repo_path=args.repo_path,
        patch_file=args.patch_file,
        trial_contract=args.trial_contract,
        validation_commands=commands,
        automation_level=args.automation_level,
        budget_tier=args.budget_tier,
        timeout_sec=args.timeout,
        trial_id=args.trial_id,
        created_at=args.created_at,
        cleanup=args.cleanup,
        sandbox_root=args.sandbox_root,
        output_root=args.output_root,
        allow_large=args.allow_large,
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
