"""AUTO.1b — Sandbox Self-Evolution Dry-Run Runner.

The first *executable* self-evolution layer. It copies the current repo into a
disposable, managed sandbox, runs only explicitly declared safe validation
commands inside that sandbox (via the A.18 safe validation path), records the
A.19 before/after side effects, and returns a review record. It may test the
sandbox; it may not evolve the real repo.

It never calls a model, generates a patch, applies a patch to the real repo,
pushes, merges, opens a PR, contacts a remote git host / chat service / external
automation, runs Dream or Project Evolution, promotes a lesson, imports a
proposal, or launches a worker. The only writes it makes are inside the managed
sandbox (validation side effects) and, via the CLI wrapper, the dry-run artifact
under ``.agent/self_evolution_trials/``.

Validation execution is delegated entirely to the A.18 safe path
(``core.validation_execution``): argv command, shell disabled, a required
bounded timeout, and a scrubbed environment — there is no raw shell fallback and
no legacy shell validation here.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from core.validation_execution import (
    SafeValidationCommand,
    run_safe_validation_command,
)
from core.validation_side_effects import (
    diff_validation_side_effects,
    empty_validation_side_effect_report,
    snapshot_repo_files,
)


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "sandbox_self_evolution_dry_run"

#: Deterministic dry-run verdicts.
DRY_RUN_VERDICTS: tuple[str, ...] = (
    "dry_run_passed",
    "dry_run_failed",
    "blocked_by_contract",
    "validation_skipped",
    "sandbox_setup_failed",
)

#: Marker file written at the root of every managed sandbox. Cleanup refuses to
#: delete any directory that does not carry it.
SANDBOX_MARKER_NAME = ".sandbox_self_evolution_managed"

DEFAULT_VALIDATION_TIMEOUT_SEC = 120

#: Directory names never copied into a sandbox (VCS, our artifact tree, caches,
#: temp dirs, virtualenvs, dependency trees, build outputs).
_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".agent",
        ".tmp",
        "tmp_tests",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "build",
        "dist",
        "target",
        ".idea",
        ".vs",
        ".vscode",
        ".cache",
        "coverage",
        ".gradle",
        ".next",
    }
)

#: Exact file names never copied (local env / secrets / OS noise).
_EXCLUDED_NAMES: frozenset[str] = frozenset(
    {".env", ".env.local", ".env.production", "secrets", ".DS_Store"}
)

#: File suffixes never copied (compiled / noisy artifacts).
_EXCLUDED_SUFFIXES: tuple[str, ...] = (".pyc", ".pyo", ".log")

SANDBOX_DRY_RUN_GUARDRAIL_NOTE = (
    "Sandbox Self-Evolution Dry Run copies the repo into a disposable managed "
    "sandbox and runs only declared safe validation commands there. It may test "
    "the sandbox; it may not evolve the real repo. It does not call a model, "
    "generate a patch, apply a patch to the real repo, push, merge, open a PR, "
    "contact a remote git host / chat service / external automation, run Dream "
    "or Project Evolution, promote a lesson, import a proposal, or launch a "
    "worker. Self-evolution may be tested in a sandbox; self-approval is "
    "forbidden."
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _tail(text: str, limit: int = 1200) -> str:
    flat = (text or "").strip()
    if len(flat) > limit:
        return "…" + flat[-(limit - 1):]
    return flat


def _normalize_commands(validation_commands: Any) -> list[list[str]]:
    """Coerce the declared commands into a list of non-empty argv lists."""
    out: list[list[str]] = []
    for item in validation_commands or []:
        if isinstance(item, (list, tuple)) and item:
            argv = [str(part) for part in item]
            if all(part.strip() for part in argv):
                out.append(argv)
        elif isinstance(item, str) and item.strip():
            # A bare string is treated as a single token; the CLI splits text
            # commands safely before reaching here.
            out.append([item.strip()])
    return out


def _looks_like_benchmark(argv: list[str]) -> bool:
    return "benchmark" in " ".join(argv).lower()


# ── Managed sandbox creation / cleanup ────────────────────────────────────────

def _copy_ignore(_dirpath: Any, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in _EXCLUDED_DIRS or name in _EXCLUDED_NAMES:
            ignored.add(name)
        elif name.startswith(".env"):
            ignored.add(name)
        elif name.endswith(_EXCLUDED_SUFFIXES) or name.endswith(".egg-info"):
            ignored.add(name)
    return ignored


def create_managed_sandbox(
    repo_path: str | Path, sandbox_path: str | Path
) -> dict[str, Any]:
    """Copy ``repo_path`` into a fresh managed sandbox at ``sandbox_path``.

    Excludes VCS, our artifact tree, caches, temp dirs, virtualenvs, dependency
    trees, build outputs, and local env / secrets. Writes a marker file so the
    sandbox can be safely identified for cleanup. Returns an info dict with
    ``ok``, ``sandbox_path``, ``source_repo``, ``managed``, and ``error``.
    """
    repo = Path(repo_path).resolve()
    sandbox = Path(sandbox_path)
    info: dict[str, Any] = {
        "ok": False,
        "source_repo": str(repo),
        "sandbox_path": str(sandbox),
        "managed": False,
        "error": "",
    }
    if not repo.is_dir():
        info["error"] = f"source repo is not a directory: {repo}"
        return info
    try:
        sandbox.parent.mkdir(parents=True, exist_ok=True)
        if sandbox.exists():
            shutil.rmtree(sandbox)
        shutil.copytree(repo, sandbox, ignore=_copy_ignore)
    except OSError as exc:
        info["error"] = f"copy failed: {type(exc).__name__}: {exc}"
        try:
            if sandbox.exists():
                shutil.rmtree(sandbox)
        except OSError:
            pass
        return info
    try:
        (sandbox / SANDBOX_MARKER_NAME).write_text(
            f"source={repo}\nmanaged=true\n", encoding="utf-8"
        )
    except OSError as exc:
        info["error"] = f"marker write failed: {type(exc).__name__}: {exc}"
        return info
    info["ok"] = True
    info["managed"] = True
    info["sandbox_path"] = str(sandbox.resolve())
    return info


def is_managed_sandbox(path: str | Path) -> bool:
    """True only if ``path`` carries the managed-sandbox marker file."""
    return (Path(path) / SANDBOX_MARKER_NAME).is_file()


def cleanup_managed_sandbox(path: str | Path) -> tuple[bool, str]:
    """Delete a managed sandbox. Refuse any path without the marker file."""
    target = Path(path)
    if not target.exists():
        return False, "refused: sandbox path does not exist"
    if not is_managed_sandbox(target):
        return False, "refused: not a managed sandbox (marker file missing)"
    try:
        resolved = target.resolve()
    except OSError as exc:
        return False, f"refused: cannot resolve path: {exc}"
    if resolved.parent == resolved:
        return False, "refused: cannot delete a filesystem root"
    try:
        shutil.rmtree(resolved)
    except OSError as exc:
        return False, f"cleanup error: {type(exc).__name__}: {exc}"
    return True, ""


# ── Contract gate ─────────────────────────────────────────────────────────────

def contract_block_reason(contract: Any) -> str:
    """Return why the AUTO.1a contract forbids a dry run, or ``""`` if allowed."""
    if not isinstance(contract, dict):
        return "no trial contract provided"
    if contract.get("verdict") == "blocked":
        return "trial contract verdict is blocked"
    if contract.get("self_approval_allowed") is True:
        return "trial contract allows self-approval, which is forbidden"
    if contract.get("eligible_for_auto_merge") is True:
        return "trial contract is eligible for an automatic merge, which is forbidden"
    level = contract.get("automation_level")
    if level == "AUTO_4_AUTO_MERGE":
        return "automation level AUTO_4_AUTO_MERGE is forbidden"
    if level == "REMOTE_3_DRAFT_PR":
        return "automation level REMOTE_3_DRAFT_PR is not runnable in a local sandbox dry run"
    if contract.get("sandbox_required") is False:
        return "trial contract does not require a sandbox"
    if contract.get("human_approval_required") is False:
        return "trial contract does not require human approval"
    return ""


# ── Record assembly ───────────────────────────────────────────────────────────

def _boundaries() -> dict[str, bool]:
    return {
        "calls_models": False,
        "generates_patches": False,
        "modifies_real_repo": False,
        "pushes_merges_or_opens_pr": False,
        "contacts_remote_or_chat_or_automation": False,
        "allows_self_approval": False,
    }


def _summarize_validation_result(res: Any) -> dict[str, Any]:
    return {
        "command": list(res.command),
        "ok": bool(res.ok),
        "blocked": bool(res.blocked),
        "block_reason": res.block_reason or "",
        "exit_code": res.exit_code,
        "timed_out": bool(res.timed_out),
        "stdout_tail": _tail(res.stdout),
        "stderr_tail": _tail(res.stderr),
    }


def _base_record(
    *,
    trial_id: str,
    created_at: str,
    source_repo: Path,
    sandbox_root: Path,
    contract: Any,
) -> dict[str, Any]:
    contract_dict = contract if isinstance(contract, dict) else {}
    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": SANDBOX_DRY_RUN_GUARDRAIL_NOTE,
        "trial_id": str(trial_id or ""),
        "created_at": str(created_at or ""),
        "source_repo": str(source_repo),
        "sandbox_root": str(sandbox_root),
        "sandbox_path": "",
        "managed_sandbox": False,
        "cleanup_policy": "the managed sandbox is deleted only when --cleanup is set",
        "contract_verdict": str(contract_dict.get("verdict", "")),
        "automation_level": str(contract_dict.get("automation_level", "")),
        "contract_block_reason": "",
        "dry_run_verdict": "",
        "validation_status": "not_run",
        "validation_commands": [],
        "side_effects": empty_validation_side_effect_report("validation not run"),
        "side_effects_sandbox_only": True,
        "setup_error": "",
        # ── guardrail booleans ──
        "sandbox_created": False,
        "sandbox_only": True,
        "real_repo_modified": False,
        "push_performed": False,
        "merge_performed": False,
        "model_call_performed": False,
        "worker_launch_performed": False,
        "patch_generated": False,
        "patch_applied_to_real_repo": False,
        "validation_run_by_tool": False,
        "benchmark_run_by_tool": False,
        "human_approval_required": True,
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
        "cleanup_performed": False,
        "cleanup_reason": "",
        "boundaries": _boundaries(),
    }


def run_dry_run(
    *,
    repo_path: str | Path,
    contract: Any,
    validation_commands: Any = None,
    timeout_sec: int = DEFAULT_VALIDATION_TIMEOUT_SEC,
    trial_id: str = "",
    created_at: str = "",
    sandbox_root: str | Path | None = None,
    cleanup: bool = False,
    allowed_tools: Any = (),
) -> dict[str, Any]:
    """Run a sandbox self-evolution dry run and return the review record.

    Order: gate on the contract, create a managed sandbox copy, run only the
    declared safe validation commands inside it, diff side effects, optionally
    delete the managed sandbox. The real repo is never touched.
    """
    repo = Path(repo_path).resolve()
    root = Path(sandbox_root) if sandbox_root else repo / ".agent" / "self_evolution_sandboxes"
    commands = _normalize_commands(validation_commands)

    record = _base_record(
        trial_id=trial_id,
        created_at=created_at,
        source_repo=repo,
        sandbox_root=root,
        contract=contract,
    )

    # 1. Contract gate — refuse before creating anything.
    block = contract_block_reason(contract)
    if block:
        record["contract_block_reason"] = block
        record["dry_run_verdict"] = "blocked_by_contract"
        record["side_effects"] = empty_validation_side_effect_report("blocked by contract")
        return record

    # 2. Create the managed sandbox.
    sandbox_path = root / (str(trial_id) or "sandbox")
    setup = create_managed_sandbox(repo, sandbox_path)
    if not setup["ok"]:
        record["dry_run_verdict"] = "sandbox_setup_failed"
        record["setup_error"] = setup["error"]
        record["side_effects"] = empty_validation_side_effect_report("sandbox setup failed")
        return record
    record["sandbox_created"] = True
    record["managed_sandbox"] = True
    record["sandbox_path"] = setup["sandbox_path"]
    sandbox = Path(setup["sandbox_path"])

    # 3. Run only declared safe validation commands inside the sandbox.
    before = snapshot_repo_files(sandbox)
    if not commands:
        record["validation_status"] = "skipped"
        record["validation_run_by_tool"] = False
        record["dry_run_verdict"] = "validation_skipped"
    else:
        record["validation_status"] = "ran"
        record["validation_run_by_tool"] = True
        results: list[dict[str, Any]] = []
        all_ok = True
        for argv in commands:
            cmd = SafeValidationCommand(
                command=argv,
                cwd=str(sandbox),
                timeout_sec=int(timeout_sec),
                allowed_tools=tuple(allowed_tools),
            )
            res = run_safe_validation_command(cmd)
            results.append(_summarize_validation_result(res))
            if not res.ok:
                all_ok = False
        record["validation_commands"] = results
        record["benchmark_run_by_tool"] = any(_looks_like_benchmark(a) for a in commands)
        record["dry_run_verdict"] = "dry_run_passed" if all_ok else "dry_run_failed"

    # 4. A.19 before/after side-effect diff (no patch-touched paths here).
    after = snapshot_repo_files(sandbox)
    record["side_effects"] = diff_validation_side_effects(sandbox, before, after, [])
    record["side_effects_sandbox_only"] = True

    # 5. Optional cleanup — managed sandbox only.
    if cleanup:
        ok, reason = cleanup_managed_sandbox(sandbox)
        record["cleanup_performed"] = ok
        record["cleanup_reason"] = reason

    return record


# ── Markdown rendering ────────────────────────────────────────────────────────

def render_sandbox_dry_run_markdown(record: dict[str, Any]) -> str:
    """Render the dry-run record as operator-readable Markdown."""
    side_effects = record.get("side_effects") or {}
    summary = side_effects.get("summary") or {}

    lines: list[str] = [
        "# Sandbox Self-Evolution Dry Run",
        "",
        f"> {record.get('guardrail_note', SANDBOX_DRY_RUN_GUARDRAIL_NOTE)}",
        "",
        "_Sandbox dry run only: the repo is copied into a disposable managed "
        "sandbox; declared safe validation runs there; the real repo is never "
        "modified._",
        "",
        "---",
        "",
        "## Summary",
        "",
    ]
    lines.append(f"- **Trial id:** `{_md(record.get('trial_id') or '(none)')}`")
    lines.append(f"- **Source repo:** `{_md(record.get('source_repo') or '')}`")
    lines.append(
        f"- **Sandbox path:** `{_md(record.get('sandbox_path') or '(not created)')}`"
    )
    lines.append(
        f"- **Contract verdict:** `{_md(record.get('contract_verdict') or '(none)')}`"
    )
    lines.append(f"- **Dry-run verdict:** `{_md(record.get('dry_run_verdict') or '')}`")
    lines.append(f"- **Validation status:** {_md(record.get('validation_status') or '')}")
    cleanup_txt = "performed" if record.get("cleanup_performed") else "kept (no --cleanup)"
    lines.append(f"- **Cleanup status:** {cleanup_txt}")
    if record.get("contract_block_reason"):
        lines.append(f"- **Blocked because:** {_md(record['contract_block_reason'])}")
    if record.get("setup_error"):
        lines.append(f"- **Sandbox setup error:** {_md(record['setup_error'])}")
    lines.append("")

    # Validation
    lines += ["## Validation", ""]
    commands = record.get("validation_commands") or []
    if not commands:
        lines.append("_No validation command was declared; validation was skipped._")
        lines.append("")
    else:
        lines.append("| Command | Exit code | OK | Timed out | Blocked |")
        lines.append("|---|---|---|---|---|")
        for cmd in commands:
            argv = " ".join(cmd.get("command") or [])
            lines.append(
                f"| `{_md(argv)}` | {cmd.get('exit_code')} | {cmd.get('ok')} "
                f"| {cmd.get('timed_out')} | {cmd.get('blocked')} |"
            )
        lines.append("")
        for cmd in commands:
            argv = " ".join(cmd.get("command") or [])
            out = cmd.get("stdout_tail") or ""
            err = cmd.get("stderr_tail") or ""
            if out or err or cmd.get("block_reason"):
                lines.append(f"- `{_md(argv)}`")
                if cmd.get("block_reason"):
                    lines.append(f"  - blocked: {_md(cmd['block_reason'])}")
                if out:
                    lines.append(f"  - stdout: `{_md(out[-400:])}`")
                if err:
                    lines.append(f"  - stderr: `{_md(err[-400:])}`")
        lines.append("")

    # Side effects
    lines += ["## Side Effects", ""]
    lines.append(
        f"- Created: {summary.get('created', 0)} "
        f"| Modified: {summary.get('modified', 0)} "
        f"| Deleted: {summary.get('deleted', 0)}"
    )
    lines.append(
        "- Side effects were sandbox-only: "
        f"{str(record.get('side_effects_sandbox_only', True)).lower()}"
    )
    lines.append(
        f"- Real repo modified: {str(record.get('real_repo_modified', False)).lower()}"
    )
    for label in ("created", "modified", "deleted"):
        entries = side_effects.get(label) or []
        if entries:
            shown = ", ".join(f"`{_md(entry.get('path', ''))}`" for entry in entries[:20])
            lines.append(f"- {label.capitalize()} files: {shown}")
    lines.append("")

    # Boundaries
    lines += ["## Boundaries", ""]
    lines += [
        "- This dry run does not call models.",
        "- This dry run does not generate patches.",
        "- This dry run does not modify the real repo.",
        "- This dry run does not push, merge, open PRs, or contact a remote git "
        "host, chat app, or external automation.",
        "- Self-approval remains forbidden.",
        "",
    ]
    return "\n".join(lines) + "\n"
