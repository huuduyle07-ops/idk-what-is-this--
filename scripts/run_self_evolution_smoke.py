"""AUTO.1f — End-to-End Sandbox Self-Evolution Smoke Scenario (CLI).

Drives the AUTO.1a -> 1e chain over ONE harmless patch candidate inside ONE
trial directory, so every artifact shares the same ``trial_id`` and output
folder. This is the deterministic single-trial smoke scenario that exercises the
whole sandbox self-evolution pipeline before any future external review
automation is wired in.

What it does, in order, using one deterministic ``trial_id``:

  1a. Build a sandbox self-evolution *contract* for a harmless text patch.
  1b. Run a sandbox *dry run* (copy + declared safe validation, no patch).
  1c. Evaluate an explicit, harmless *patch candidate* in the sandbox copy.
  1d. Review whether the candidate is eligible for *human review*.
  1e. Package the four artifacts into one *evidence pack*.

Boundaries. The smoke runner orchestrates the existing AUTO.1a-1e tools
in-process. The only execution it triggers is declared safe validation inside a
disposable managed sandbox (the AUTO.1b/1c path). It never writes to the real
repo, never generates a patch (the candidate is a fixed literal it consumes),
never calls a model, and never pushes, merges, opens a PR, promotes a lesson,
imports a proposal, launches a worker, or contacts external automation. Human
approval is always required before any real repo change; self-approval is
forbidden. Managed sandboxes are removed when cleanup is requested (the default).

Usage:
    python scripts/run_self_evolution_smoke.py
    python scripts/run_self_evolution_smoke.py --trial-id auto1f_smoke --keep-sandbox
    python scripts/run_self_evolution_smoke.py --output-root .agent/self_evolution_trials --json
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

from scripts.create_sandbox_self_evolution_trial import (  # noqa: E402
    run_sandbox_self_evolution_trial,
)
from scripts.run_sandbox_self_evolution_dry_run import (  # noqa: E402
    run_sandbox_self_evolution_dry_run,
)
from scripts.evaluate_sandbox_patch_candidate import (  # noqa: E402
    run_evaluate_sandbox_patch_candidate,
)
from scripts.create_sandbox_patch_graduation_review import (  # noqa: E402
    run_create_sandbox_patch_graduation_review,
)
from scripts.create_self_evolution_evidence_pack import (  # noqa: E402
    run_create_self_evolution_evidence_pack,
)

# ── Smoke defaults ────────────────────────────────────────────────────────────

DEFAULT_TRIAL_ID = "auto1f_smoke"
DEFAULT_AUTOMATION_LEVEL = "SANDBOX_2_DRAFT_PATCH"
DEFAULT_SANDBOX_SUBPATH = Path(".agent") / "self_evolution_sandboxes"

#: The single declared safe validation command, run inside the sandbox copy.
DEFAULT_VALIDATION_ARGV: tuple[str, ...] = ("python", "-m", "compileall", "-q", "core")

#: The harmless file the smoke candidate creates — sandbox-only, never the repo.
SMOKE_PATCH_TARGET = "pkg/auto1f_smoke_demo.txt"

#: A fixed, explicit unified diff (consumed, never generated) that creates one
#: harmless text file inside the sandbox copy.
SMOKE_PATCH_TEXT = (
    f"diff --git a/{SMOKE_PATCH_TARGET} b/{SMOKE_PATCH_TARGET}\n"
    "--- /dev/null\n"
    f"+++ b/{SMOKE_PATCH_TARGET}\n"
    "@@ -0,0 +1,3 @@\n"
    "+AUTO.1f smoke demo file.\n"
    "+This file exists only inside a disposable sandbox copy.\n"
    "+It is never written to the real repository.\n"
)

STEP_NAMES = ("contract", "dry_run", "patch_evaluation", "graduation_review", "evidence_pack")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_created_at(raw: str | float | None) -> str:
    """Return an ISO-8601 created-at string from a string, epoch, or None."""
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _resolved_sandbox_path(repo_path: str, sandbox_root: str | None, trial_id: str) -> str:
    root = sandbox_root or str(Path(repo_path) / DEFAULT_SANDBOX_SUBPATH)
    return str(Path(root) / trial_id)


def _fail(step: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "failed_step": step,
        "error": str(result.get("error") or f"{step} did not complete"),
    }


# ── Orchestration ─────────────────────────────────────────────────────────────

def run_self_evolution_smoke(
    *,
    repo_path: str = ".",
    trial_id: str = DEFAULT_TRIAL_ID,
    created_at: str | float | None = None,
    output_root: str | None = None,
    sandbox_root: str | None = None,
    cleanup: bool = True,
    validation_commands: list[list[str]] | None = None,
    patch_text: str | None = None,
    patch_target: str | None = None,
    timeout_sec: int = 120,
) -> dict[str, Any]:
    """Run the AUTO.1a->1e chain over one harmless candidate in one trial dir.

    Every step uses the same ``trial_id``, ``created_at``, and output directory,
    so the resulting artifacts form one coherent single-trial bundle. Returns a
    structured result describing each step, the final evidence-pack verdict, and
    explicit cleanup accounting for the managed sandbox.
    """
    created_iso = _resolve_created_at(created_at)
    argv_commands = [list(cmd) for cmd in (validation_commands or [list(DEFAULT_VALIDATION_ARGV)])]
    text_commands = [" ".join(cmd) for cmd in argv_commands]
    final_patch_text = patch_text if patch_text is not None else SMOKE_PATCH_TEXT
    final_patch_target = patch_target or SMOKE_PATCH_TARGET

    # 1a — contract for a harmless docs/text patch.
    contract_res = run_sandbox_self_evolution_trial(
        repo_path=repo_path,
        phase_id="AUTO.1f",
        phase_title="End-to-end sandbox self-evolution smoke",
        phase_summary="Run the AUTO.1a->1e chain on one harmless sandbox patch.",
        automation_level=DEFAULT_AUTOMATION_LEVEL,
        allowed_files=[final_patch_target],
        validation_commands=text_commands,
        budget_tier="local_only",
        trial_id=trial_id,
        created_at=created_iso,
        output_root=output_root,
    )
    contract_json = contract_res["json_path"]
    trial_dir = str(Path(contract_json).parent)

    # 1b — sandbox dry run (no patch).
    dry_res = run_sandbox_self_evolution_dry_run(
        repo_path=repo_path,
        trial_contract=contract_json,
        validation_commands=argv_commands,
        trial_id=trial_id,
        created_at=created_iso,
        cleanup=cleanup,
        sandbox_root=sandbox_root,
        output_root=output_root,
        timeout_sec=timeout_sec,
    )
    if not dry_res.get("ok"):
        return _fail("dry_run", dry_res)

    # 1c — evaluate the explicit harmless candidate in the sandbox copy.
    patch_res = run_evaluate_sandbox_patch_candidate(
        repo_path=repo_path,
        patch_text=final_patch_text,
        trial_contract=contract_json,
        validation_commands=argv_commands,
        trial_id=trial_id,
        created_at=created_iso,
        cleanup=cleanup,
        sandbox_root=sandbox_root,
        output_root=output_root,
        timeout_sec=timeout_sec,
    )
    if not patch_res.get("ok"):
        return _fail("patch_evaluation", patch_res)
    patch_json = patch_res["json_path"]

    # 1d — graduation review (writes next to the 1c evaluation, same trial dir).
    grad_res = run_create_sandbox_patch_graduation_review(
        evaluation_path=patch_json,
        review_id=f"{trial_id}_graduation",
        created_at=created_iso,
    )

    # 1e — evidence pack (discovers the four artifacts in the trial dir).
    pack_res = run_create_self_evolution_evidence_pack(
        trial_dir=trial_dir,
        pack_id=f"{trial_id}_evidence",
        created_at=created_iso,
    )
    pack_record = pack_res["record"]

    # Explicit sandbox / cleanup accounting.
    sandbox_path = _resolved_sandbox_path(repo_path, sandbox_root, trial_id)

    steps = [
        {
            "step": "1a",
            "name": "contract",
            "json_path": contract_res["json_path"],
            "md_path": contract_res["md_path"],
            "verdict": contract_res["record"].get("verdict"),
        },
        {
            "step": "1b",
            "name": "dry_run",
            "json_path": dry_res["json_path"],
            "md_path": dry_res["md_path"],
            "verdict": dry_res["record"].get("dry_run_verdict"),
        },
        {
            "step": "1c",
            "name": "patch_evaluation",
            "json_path": patch_res["json_path"],
            "md_path": patch_res["md_path"],
            "verdict": patch_res["record"].get("verdict"),
        },
        {
            "step": "1d",
            "name": "graduation_review",
            "json_path": grad_res["json_path"],
            "md_path": grad_res["md_path"],
            "verdict": grad_res["record"].get("graduation_verdict"),
        },
        {
            "step": "1e",
            "name": "evidence_pack",
            "json_path": pack_res["json_path"],
            "md_path": pack_res["md_path"],
            "verdict": pack_record.get("final_verdict"),
        },
    ]

    return {
        "ok": True,
        "trial_id": trial_id,
        "trial_dir": trial_dir,
        "created_at": created_iso,
        "final_verdict": pack_record.get("final_verdict"),
        "recommended_next_step": pack_record.get("recommended_next_step"),
        "cleanup_requested": bool(cleanup),
        "sandbox_root": str(sandbox_root or (Path(repo_path) / DEFAULT_SANDBOX_SUBPATH)),
        "sandbox_path": sandbox_path,
        "sandbox_exists_after": Path(sandbox_path).exists(),
        "patch_target": final_patch_target,
        "steps": steps,
        "records": {
            "contract": contract_res["record"],
            "dry_run": dry_res["record"],
            "patch_evaluation": patch_res["record"],
            "graduation_review": grad_res["record"],
            "evidence_pack": pack_record,
        },
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_summary(result: dict[str, Any]) -> None:
    print("AUTO.1f — End-to-End Sandbox Self-Evolution Smoke")
    print("=" * 50)
    if not result.get("ok"):
        print(f"Failed at step   : {result.get('failed_step')}")
        print(f"Error            : {result.get('error')}")
        return
    print(f"Trial id         : {result.get('trial_id')}")
    print(f"Trial dir        : {result.get('trial_dir')}")
    print("Steps:")
    for step in result.get("steps") or []:
        print(f"  {step['step']} {step['name']:<18}: {step.get('verdict')}")
    print(f"Final verdict    : {result.get('final_verdict')}")
    print(f"Next step        : {result.get('recommended_next_step')}")
    print(f"Sandbox path     : {result.get('sandbox_path')}")
    cleanup_txt = "removed" if not result.get("sandbox_exists_after") else "kept"
    print(f"Sandbox          : {cleanup_txt} (cleanup requested: {result.get('cleanup_requested')})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "AUTO.1f: run the AUTO.1a->1e sandbox self-evolution chain over one "
            "harmless patch candidate inside one trial directory. The only "
            "execution is declared safe validation inside a disposable sandbox; "
            "the real repo is never modified and no patch is generated."
        )
    )
    parser.add_argument("--repo-path", default=".", help="Repo root to copy into the sandbox (default: .).")
    parser.add_argument("--trial-id", default=DEFAULT_TRIAL_ID, help="Deterministic trial id (folder name).")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Override the artifact root (default: <repo>/.agent/self_evolution_trials).",
    )
    parser.add_argument(
        "--sandbox-root",
        default=None,
        help="Override the managed sandbox root (default: <repo>/.agent/self_evolution_sandboxes).",
    )
    parser.add_argument(
        "--keep-sandbox",
        action="store_true",
        help="Keep the managed sandbox instead of removing it (cleanup is on by default).",
    )
    parser.add_argument("--json", action="store_true", help="Print the smoke result JSON.")
    args = parser.parse_args(argv)

    result = run_self_evolution_smoke(
        repo_path=args.repo_path,
        trial_id=args.trial_id,
        created_at=args.created_at,
        output_root=args.output_root,
        sandbox_root=args.sandbox_root,
        cleanup=not args.keep_sandbox,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_summary(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
