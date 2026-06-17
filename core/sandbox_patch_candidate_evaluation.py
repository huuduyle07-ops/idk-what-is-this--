"""AUTO.1c — Sandbox Patch Candidate Evaluation.

Evaluates a *provided* patch candidate inside a disposable managed sandbox. The
evaluator may write the candidate into the sandbox copy only; it must never
write to the real repo, and it never generates a patch itself.

Flow: gate on the AUTO.1a trial contract, reject unsafe / empty / oversized
patches by path and size, copy the repo into a managed sandbox (AUTO.1b rules),
write the candidate into the sandbox, run only declared A.18-safe validation
there, and report A.19 side effects around both the candidate write and the
validation. Patch candidates may be tested in a sandbox; they may not graduate
without human review.

It never calls a model, generates a patch, writes to the real repo, pushes,
merges, opens a PR, contacts a remote git host / chat service / external
automation, runs Dream or Project Evolution, promotes a lesson, imports a
proposal, or launches a worker.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.patch_safety import evaluate_patch_safety
from core.sandbox_self_evolution_runner import (
    DEFAULT_VALIDATION_TIMEOUT_SEC,
    cleanup_managed_sandbox,
    contract_block_reason,
    create_managed_sandbox,
)
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

REPORT_KIND = "sandbox_patch_candidate_evaluation"

#: Deterministic verdicts.
PATCH_EVAL_VERDICTS: tuple[str, ...] = (
    "patch_candidate_passed",
    "patch_candidate_failed_validation",
    "patch_candidate_failed_apply",
    "patch_candidate_rejected_by_safety",
    "blocked_by_contract",
    "validation_skipped",
    "sandbox_setup_failed",
)

#: Conservative size ceilings; an oversized candidate is rejected unless it is
#: explicitly marked for manual review (``allow_large``).
MAX_PATCH_LINES = 800
MAX_PATCH_FILES = 25

#: Automation-level ranks (mirrors the AUTO.1a ladder). A patch candidate needs
#: at least the sandbox patch level.
_LEVEL_RANK: dict[str, int] = {
    "LOCAL_0_OBSERVE": 0,
    "LOCAL_1_PREPARE": 1,
    "SANDBOX_2_DRAFT_PATCH": 2,
    "REMOTE_3_DRAFT_PR": 3,
    "AUTO_4_AUTO_MERGE": 4,
}
SANDBOX_PATCH_LEVEL_RANK = 2

#: Secret-like path/name fragments rejected on top of the shared path gate.
_SECRET_SEGMENTS: tuple[str, ...] = ("secrets", "secret")
_SECRET_NAME_FRAGMENTS: tuple[str, ...] = (
    "secret",
    "credential",
    "password",
    "token",
    "auth_key",
)

PATCH_EVAL_GUARDRAIL_NOTE = (
    "Sandbox Patch Candidate Evaluation writes a provided patch candidate into a "
    "disposable managed sandbox only and runs declared safe validation there. "
    "Patch candidates may be tested in a sandbox; they may not graduate without "
    "human review. It does not generate a patch, call a model, write to the real "
    "repo, push, merge, open a PR, contact a remote git host / chat service / "
    "external automation, run Dream or Project Evolution, promote a lesson, "
    "import a proposal, or launch a worker. Self-approval is forbidden."
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
    out: list[list[str]] = []
    for item in validation_commands or []:
        if isinstance(item, (list, tuple)) and item:
            argv = [str(part) for part in item]
            if all(part.strip() for part in argv):
                out.append(argv)
        elif isinstance(item, str) and item.strip():
            out.append([item.strip()])
    return out


def _looks_like_benchmark(argv: list[str]) -> bool:
    return "benchmark" in " ".join(argv).lower()


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


# ── Unified-diff parsing ──────────────────────────────────────────────────────

def _strip_ab_prefix(path: str) -> str:
    text = path.strip()
    if text.startswith("a/") or text.startswith("b/"):
        return text[2:]
    return text


def _parse_hunk_header(header: str) -> tuple[int, int]:
    """Parse ``@@ -old_start,old_count +new_start,new_count @@`` line numbers."""
    try:
        middle = header.split("@@")[1].strip()
        old_part, new_part = middle.split(" ")[:2]
        old_start = int(old_part.lstrip("-").split(",")[0] or "0")
        new_start = int(new_part.lstrip("+").split(",")[0] or "0")
        return old_start, new_start
    except (IndexError, ValueError):
        return 1, 1


def _new_file_section() -> dict[str, Any]:
    return {
        "old_path": "",
        "new_path": "",
        "path": "",
        "is_new": False,
        "is_delete": False,
        "hunks": [],
        "added": 0,
        "removed": 0,
    }


def parse_unified_diff(patch_text: str) -> dict[str, Any]:
    """Parse a unified diff into a structured, deterministic description.

    Returns ``{files, file_count, touched_paths, added_total, removed_total}``.
    Each file carries its hunks (body of ``(marker, content)`` tuples), and the
    new-file / deleted-file flags. No file is read or written here.
    """
    files: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    lines = (patch_text or "").split("\n")
    i = 0
    total = len(lines)

    while i < total:
        line = lines[i]
        if line.startswith("diff --git "):
            if current is not None:
                files.append(current)
            current = _new_file_section()
            i += 1
            continue
        if line.startswith("--- "):
            if current is None:
                current = _new_file_section()
            current["old_path"] = line[4:].strip()
            if current["old_path"] == "/dev/null":
                current["is_new"] = True
            i += 1
            continue
        if line.startswith("+++ "):
            if current is None:
                current = _new_file_section()
            current["new_path"] = line[4:].strip()
            if current["new_path"] == "/dev/null":
                current["is_delete"] = True
            i += 1
            continue
        if line.startswith("@@"):
            if current is None:
                current = _new_file_section()
            old_start, new_start = _parse_hunk_header(line)
            body: list[tuple[str, str]] = []
            i += 1
            while i < total:
                body_line = lines[i]
                if (
                    body_line.startswith("@@")
                    or body_line.startswith("diff --git ")
                    or body_line.startswith("--- ")
                    or body_line == ""
                ):
                    break
                if body_line.startswith("+"):
                    body.append(("+", body_line[1:]))
                    current["added"] += 1
                elif body_line.startswith("-"):
                    body.append(("-", body_line[1:]))
                    current["removed"] += 1
                elif body_line.startswith(" "):
                    body.append((" ", body_line[1:]))
                elif body_line.startswith("\\"):
                    pass  # "\ No newline at end of file" — ignore
                else:
                    break
                i += 1
            current["hunks"].append(
                {"old_start": old_start, "new_start": new_start, "body": body}
            )
            continue
        i += 1

    if current is not None:
        files.append(current)

    for entry in files:
        if entry["is_new"]:
            entry["path"] = _strip_ab_prefix(entry["new_path"])
        elif entry["is_delete"]:
            entry["path"] = _strip_ab_prefix(entry["old_path"])
        else:
            entry["path"] = _strip_ab_prefix(entry["new_path"] or entry["old_path"])

    return {
        "files": files,
        "file_count": len(files),
        "touched_paths": [entry["path"] for entry in files if entry["path"]],
        "added_total": sum(entry["added"] for entry in files),
        "removed_total": sum(entry["removed"] for entry in files),
    }


# ── Sandbox-only candidate application ────────────────────────────────────────

def _find_sublist(lines: list[str], block: list[str]) -> int | None:
    if not block:
        return None
    first = block[0]
    length = len(block)
    for index in range(0, len(lines) - length + 1):
        if lines[index] == first and lines[index : index + length] == block:
            return index
    return None


def _apply_hunks(file_lines: list[str], hunks: list[dict[str, Any]]) -> tuple[bool, list[str], str]:
    lines = list(file_lines)
    for hunk in hunks:
        old_block = [text for marker, text in hunk["body"] if marker in (" ", "-")]
        new_block = [text for marker, text in hunk["body"] if marker in (" ", "+")]
        if not old_block:
            position = max(0, min(len(lines), int(hunk.get("new_start", 1)) - 1))
            lines[position:position] = new_block
            continue
        index = _find_sublist(lines, old_block)
        if index is None:
            return False, [], "hunk context did not match the sandbox file"
        lines[index : index + len(old_block)] = new_block
    return True, lines, ""


def apply_candidate_in_sandbox(
    sandbox_path: str | Path, parsed: dict[str, Any]
) -> dict[str, Any]:
    """Write the parsed candidate into the sandbox. All-or-nothing, no retry.

    Computes every file's new content in memory first; only if every hunk
    applies cleanly does it write. A failure writes nothing (no partial state)
    and is reported — it is never retried or auto-fixed.
    """
    sandbox = Path(sandbox_path)
    planned: dict[str, str | None] = {}

    for entry in parsed.get("files", []):
        rel = entry.get("path") or ""
        if not rel:
            return {"ok": False, "error": "patch section has no target path", "changed_files": []}
        target = sandbox / rel
        if entry["is_delete"]:
            if not target.exists():
                return {"ok": False, "error": f"cannot delete missing file: {rel}", "changed_files": []}
            planned[rel] = None
            continue
        if entry["is_new"]:
            content_lines = [
                text for hunk in entry["hunks"] for marker, text in hunk["body"] if marker in (" ", "+")
            ]
            planned[rel] = "\n".join(content_lines) + ("\n" if content_lines else "")
            continue
        if not target.exists():
            return {"ok": False, "error": f"target file not found in sandbox: {rel}", "changed_files": []}
        ok, new_lines, err = _apply_hunks(
            target.read_text(encoding="utf-8").split("\n"), entry["hunks"]
        )
        if not ok:
            return {"ok": False, "error": f"{rel}: {err}", "changed_files": []}
        planned[rel] = "\n".join(new_lines)

    changed: list[str] = []
    for rel, content in planned.items():
        target = sandbox / rel
        if content is None:
            target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        changed.append(rel)
    return {"ok": True, "error": "", "changed_files": sorted(changed)}


# ── Patch safety (path + size) ────────────────────────────────────────────────

def _secret_path_reason(path: str) -> str:
    normalized = str(path).replace("\\", "/").lower()
    parts = [part for part in normalized.split("/") if part]
    if any(segment in parts for segment in _SECRET_SEGMENTS):
        return f"patch touches a secrets path: {path}"
    name = parts[-1] if parts else ""
    if any(fragment in name for fragment in _SECRET_NAME_FRAGMENTS):
        return f"patch touches a secret-like file: {path}"
    return ""


def classify_patch_safety(
    parsed: dict[str, Any], repo_path: str | Path, *, allow_large: bool
) -> dict[str, Any]:
    """Reject empty, forbidden-path, traversal, or oversized candidates.

    Reuses the shared ``evaluate_patch_safety`` path gate (traversal / absolute /
    protected dirs / env files) and adds an explicit secrets check and a size
    ceiling. Returns ``{ok, empty, too_large, rejected_paths, reasons}``.
    """
    touched = parsed.get("touched_paths") or []
    added = int(parsed.get("added_total", 0))
    removed = int(parsed.get("removed_total", 0))
    file_count = int(parsed.get("file_count", 0))

    empty = file_count == 0 or (added == 0 and removed == 0 and not _has_structural_change(parsed))
    too_large = (added + removed) > MAX_PATCH_LINES or file_count > MAX_PATCH_FILES

    rejected: list[dict[str, str]] = []
    gate = evaluate_patch_safety(touched, repo_path)
    for blocked in gate.get("blocked_paths", []):
        rejected.append({"path": blocked.get("path", ""), "reason": blocked.get("reason", "")})
    for path in touched:
        reason = _secret_path_reason(path)
        if reason:
            rejected.append({"path": path, "reason": reason})

    reasons = [entry["reason"] for entry in rejected]
    if empty:
        reasons.append("empty patch (no file changes)")
    if too_large and not allow_large:
        reasons.append(
            f"patch is too large ({added + removed} changed lines across "
            f"{file_count} files); mark it for manual review to proceed"
        )

    ok = (not rejected) and (not empty) and (not (too_large and not allow_large))
    return {
        "ok": ok,
        "empty": empty,
        "too_large": too_large,
        "rejected_paths": rejected,
        "reasons": reasons,
        "changed_lines": added + removed,
        "file_count": file_count,
    }


def _has_structural_change(parsed: dict[str, Any]) -> bool:
    return any(entry["is_new"] or entry["is_delete"] for entry in parsed.get("files", []))


# ── Contract gate ─────────────────────────────────────────────────────────────

def patch_contract_block_reason(
    contract: Any, *, allow_below_sandbox_level: bool = False
) -> str:
    """Return why the contract forbids patch evaluation, or ``""`` if allowed.

    Layers the AUTO.1b contract gate (blocked verdict, self-approval, auto-merge,
    forbidden levels, sandbox / human-approval requirements) and additionally
    requires at least the sandbox patch level unless an explicit evaluation-only
    test mode is set.
    """
    base = contract_block_reason(contract)
    if base:
        return base
    level = str(contract.get("automation_level", "")) if isinstance(contract, dict) else ""
    rank = _LEVEL_RANK.get(level, -1)
    if rank < SANDBOX_PATCH_LEVEL_RANK and not allow_below_sandbox_level:
        return (
            f"automation level {level or '(unknown)'} is below the sandbox patch "
            "level (SANDBOX_2_DRAFT_PATCH); patch evaluation needs at least that level"
        )
    return ""


# ── Record assembly ───────────────────────────────────────────────────────────

def _boundaries() -> dict[str, bool]:
    return {
        "generates_patches": False,
        "calls_models": False,
        "modifies_real_repo": False,
        "pushes_merges_or_opens_pr": False,
        "contacts_remote_or_chat_or_automation": False,
        "allows_self_approval": False,
    }


def _base_record(
    *,
    trial_id: str,
    created_at: str,
    repo: Path,
    sandbox_root: Path,
    contract: Any,
    patch_source: str,
    parsed: dict[str, Any],
) -> dict[str, Any]:
    contract_dict = contract if isinstance(contract, dict) else {}
    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": PATCH_EVAL_GUARDRAIL_NOTE,
        "trial_id": str(trial_id or ""),
        "created_at": str(created_at or ""),
        "source_repo": str(repo),
        "sandbox_root": str(sandbox_root),
        "sandbox_path": "",
        "patch_source": str(patch_source or ""),
        "patch_touched_paths": list(parsed.get("touched_paths") or []),
        "patch_changed_lines": int(parsed.get("added_total", 0)) + int(parsed.get("removed_total", 0)),
        "patch_file_count": int(parsed.get("file_count", 0)),
        "patch_changed_files": [],
        "contract_verdict": str(contract_dict.get("verdict", "")),
        "automation_level": str(contract_dict.get("automation_level", "")),
        "contract_block_reason": "",
        "verdict": "",
        "validation_status": "not_run",
        "validation_commands": [],
        "patch_safety": {"ok": True, "empty": False, "too_large": False, "rejected_paths": [], "reasons": []},
        "apply_error": "",
        "setup_error": "",
        "patch_side_effects": empty_validation_side_effect_report("patch not applied"),
        "validation_side_effects": empty_validation_side_effect_report("validation not run"),
        "side_effects_sandbox_only": True,
        # ── guardrail booleans ──
        "sandbox_created": False,
        "sandbox_only": True,
        "patch_candidate_supplied": True,
        "patch_generated": False,
        "patch_applied_to_sandbox": False,
        "patch_applied_to_real_repo": False,
        "real_repo_modified": False,
        "validation_run_by_tool": False,
        "benchmark_run_by_tool": False,
        "model_call_performed": False,
        "worker_launch_performed": False,
        "push_performed": False,
        "merge_performed": False,
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
        "human_approval_required": True,
        "cleanup_performed": False,
        "cleanup_reason": "",
        "boundaries": _boundaries(),
    }


def evaluate_patch_candidate(
    *,
    repo_path: str | Path,
    contract: Any,
    patch_text: str,
    patch_source: str = "",
    validation_commands: Any = None,
    timeout_sec: int = DEFAULT_VALIDATION_TIMEOUT_SEC,
    trial_id: str = "",
    created_at: str = "",
    sandbox_root: str | Path | None = None,
    cleanup: bool = False,
    allowed_tools: Any = (),
    allow_large: bool = False,
    allow_below_sandbox_level: bool = False,
) -> dict[str, Any]:
    """Evaluate a provided patch candidate inside a disposable sandbox."""
    repo = Path(repo_path).resolve()
    root = Path(sandbox_root) if sandbox_root else repo / ".agent" / "self_evolution_sandboxes"
    commands = _normalize_commands(validation_commands)
    parsed = parse_unified_diff(patch_text or "")

    record = _base_record(
        trial_id=trial_id,
        created_at=created_at,
        repo=repo,
        sandbox_root=root,
        contract=contract,
        patch_source=patch_source,
        parsed=parsed,
    )

    # 1. Contract gate.
    block = patch_contract_block_reason(contract, allow_below_sandbox_level=allow_below_sandbox_level)
    if block:
        record["verdict"] = "blocked_by_contract"
        record["contract_block_reason"] = block
        return record

    # 2. Patch safety — empty / forbidden path / traversal / oversized.
    safety = classify_patch_safety(parsed, repo, allow_large=allow_large)
    record["patch_safety"] = safety
    if not safety["ok"]:
        record["verdict"] = "patch_candidate_rejected_by_safety"
        return record

    # 3. Create the managed sandbox (AUTO.1b copy rules).
    sandbox_dir = root / (str(trial_id) or "sandbox")
    setup = create_managed_sandbox(repo, sandbox_dir)
    if not setup["ok"]:
        record["verdict"] = "sandbox_setup_failed"
        record["setup_error"] = setup["error"]
        return record
    record["sandbox_created"] = True
    record["sandbox_path"] = setup["sandbox_path"]
    sandbox = Path(setup["sandbox_path"])

    # 4. Write the candidate into the sandbox (sandbox path only).
    snap_pre = snapshot_repo_files(sandbox)
    applied = apply_candidate_in_sandbox(sandbox, parsed)
    if not applied["ok"]:
        record["verdict"] = "patch_candidate_failed_apply"
        record["apply_error"] = applied["error"]
        record["patch_applied_to_sandbox"] = False
        snap_post = snapshot_repo_files(sandbox)
        record["patch_side_effects"] = diff_validation_side_effects(
            sandbox, snap_pre, snap_post, parsed["touched_paths"]
        )
        if cleanup:
            ok, reason = cleanup_managed_sandbox(sandbox)
            record["cleanup_performed"] = ok
            record["cleanup_reason"] = reason
        return record
    record["patch_applied_to_sandbox"] = True
    record["patch_changed_files"] = applied["changed_files"]
    snap_patched = snapshot_repo_files(sandbox)
    record["patch_side_effects"] = diff_validation_side_effects(
        sandbox, snap_pre, snap_patched, parsed["touched_paths"]
    )

    # 5. Run only declared A.18-safe validation inside the sandbox.
    if not commands:
        record["validation_status"] = "skipped"
        record["validation_run_by_tool"] = False
        record["verdict"] = "validation_skipped"
        snap_validated = snap_patched
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
        record["verdict"] = "patch_candidate_passed" if all_ok else "patch_candidate_failed_validation"
        snap_validated = snapshot_repo_files(sandbox)

    record["validation_side_effects"] = diff_validation_side_effects(
        sandbox, snap_patched, snap_validated, parsed["touched_paths"]
    )
    record["side_effects_sandbox_only"] = True

    # 6. Optional cleanup — managed sandbox only.
    if cleanup:
        ok, reason = cleanup_managed_sandbox(sandbox)
        record["cleanup_performed"] = ok
        record["cleanup_reason"] = reason

    return record


# ── Markdown rendering ────────────────────────────────────────────────────────

def _render_validation(lines: list[str], record: dict[str, Any]) -> None:
    lines += ["## Validation", ""]
    commands = record.get("validation_commands") or []
    if not commands:
        lines.append("_No validation command was declared; validation was skipped._")
        lines.append("")
        return
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


def _render_side_effects(lines: list[str], record: dict[str, Any]) -> None:
    lines += ["## Side Effects", ""]
    for label, key in (("Patch", "patch_side_effects"), ("Validation", "validation_side_effects")):
        effects = record.get(key) or {}
        summary = effects.get("summary") or {}
        lines.append(
            f"- {label}: created {summary.get('created', 0)}, "
            f"modified {summary.get('modified', 0)}, deleted {summary.get('deleted', 0)}"
        )
        for change in ("created", "modified", "deleted"):
            entries = effects.get(change) or []
            if entries:
                shown = ", ".join(f"`{_md(entry.get('path', ''))}`" for entry in entries[:20])
                lines.append(f"  - {change}: {shown}")
    lines.append(
        "- All effects were sandbox-only: "
        f"{str(record.get('side_effects_sandbox_only', True)).lower()}"
    )
    lines.append(f"- Real repo modified: {str(record.get('real_repo_modified', False)).lower()}")
    lines.append("")


def render_patch_candidate_evaluation_markdown(record: dict[str, Any]) -> str:
    """Render the evaluation record as operator-readable Markdown."""
    safety = record.get("patch_safety") or {}

    lines: list[str] = [
        "# Sandbox Patch Candidate Evaluation",
        "",
        f"> {record.get('guardrail_note', PATCH_EVAL_GUARDRAIL_NOTE)}",
        "",
        "_Sandbox only: a provided patch candidate is written into a disposable "
        "managed sandbox; the real repo is never modified, and no patch is "
        "generated. Human review is required before any graduation._",
        "",
        "---",
        "",
        "## Summary",
        "",
    ]
    lines.append(f"- **Trial id:** `{_md(record.get('trial_id') or '(none)')}`")
    lines.append(f"- **Patch file:** `{_md(record.get('patch_source') or '(inline)')}`")
    lines.append(
        f"- **Sandbox path:** `{_md(record.get('sandbox_path') or '(not created)')}`"
    )
    lines.append(f"- **Verdict:** `{_md(record.get('verdict') or '')}`")
    lines.append(f"- **Validation status:** {_md(record.get('validation_status') or '')}")
    cleanup_txt = "performed" if record.get("cleanup_performed") else "kept (no --cleanup)"
    lines.append(f"- **Cleanup status:** {cleanup_txt}")
    if record.get("contract_block_reason"):
        lines.append(f"- **Blocked because:** {_md(record['contract_block_reason'])}")
    if record.get("apply_error"):
        lines.append(f"- **Apply error:** {_md(record['apply_error'])}")
    if record.get("setup_error"):
        lines.append(f"- **Sandbox setup error:** {_md(record['setup_error'])}")
    lines.append("")

    # Patch Safety
    lines += ["## Patch Safety", ""]
    lines.append(f"- Touched files: {', '.join(f'`{_md(p)}`' for p in record.get('patch_touched_paths') or []) or 'none'}")
    lines.append(f"- Patch size: {record.get('patch_changed_lines', 0)} changed lines across {record.get('patch_file_count', 0)} files")
    lines.append(f"- Empty: {str(safety.get('empty', False)).lower()} | Too large: {str(safety.get('too_large', False)).lower()}")
    rejected = safety.get("rejected_paths") or []
    if rejected:
        lines.append("- Rejected paths:")
        for entry in rejected:
            lines.append(f"  - `{_md(entry.get('path', ''))}`: {_md(entry.get('reason', ''))}")
    else:
        lines.append("- Rejected paths: none")
    lines.append(
        "- Patch stayed sandbox-only: "
        f"{str(record.get('side_effects_sandbox_only', True)).lower()}"
    )
    lines.append("")

    _render_validation(lines, record)
    _render_side_effects(lines, record)

    # Boundaries
    lines += ["## Boundaries", ""]
    lines += [
        "- This evaluator does not generate patches.",
        "- This evaluator does not call models.",
        "- This evaluator does not modify the real repo.",
        "- This evaluator does not push, merge, open PRs, or contact a remote git "
        "host, chat app, or external automation.",
        "- Human approval is required before any real repo change.",
        "",
    ]
    return "\n".join(lines) + "\n"
