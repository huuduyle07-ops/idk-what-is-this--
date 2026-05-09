"""Atomic executor for multi-op patch plans.

Used when the AI returns `patch_plan` instead of `patch_candidate` — usually
for feature work that touches multiple files or creates new ones (only
permitted under balanced/vibe vibecoding styles).

Design rules:
- Atomicity: if ANY op fails, ALL prior ops are rolled back. The repo is left
  exactly as it was found.
- Security: every relative_path must resolve INSIDE project_root. Absolute
  paths and `..` traversal are rejected up front.
- Order matters: ops apply top-to-bottom. AI is responsible for ordering
  (e.g. create the file before replacing a snippet that imports it).

Supported ops:
  create_file       — write a new file with `content`. Fails if file exists.
  replace_snippet   — same as patch_candidate's target/patched snippet, but
                      for one of many files.
"""
from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any


# Each rollback entry is (path, original_text_or_None).
# original_text=None means the op was a CREATE → rollback = delete the file.
# original_text=str  means the op was a REPLACE → rollback = restore the bytes.
RollbackEntry = tuple[Path, str | None]


def _rollback_and_fail(
    rollbacks: list[RollbackEntry],
    op: dict,
    idx: int,
    error: str,
    diffs: list[str],
    applied_ops: list[dict],
) -> dict:
    """Reverse every applied op in LIFO order and return a failure result."""
    for path, original in reversed(rollbacks):
        try:
            if original is None:
                # The op was create_file — delete the file we created.
                if path.exists():
                    path.unlink()
            else:
                # The op was replace_snippet — restore the original bytes.
                path.write_text(original, encoding="utf-8")
        except Exception as e:
            print(f"⚠️ Rollback warning on {path}: {e}")

    return {
        "success": False,
        "failed_op_index": idx,
        "failed_op": op,
        "error": error,
        "rollback_performed": True,
        "applied_ops": applied_ops,
        "diffs": diffs,
    }


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_safe_target(root: Path, rel_path: str) -> Path | None:
    """Return absolute path inside root, or None if rel_path escapes/absolute."""
    if not rel_path:
        return None
    raw = Path(rel_path)
    if raw.is_absolute():
        return None
    try:
        target = (root / rel_path).resolve()
    except Exception:
        return None
    if not _is_inside(target, root):
        return None
    return target


def _make_diff(original: str, modified: str, label: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            original.splitlines(),
            modified.splitlines(),
            fromfile=f"a/{label}",
            tofile=f"b/{label}",
            lineterm="",
        )
    )


def apply_patch_plan(
    project_root: str,
    plan: list[dict],
    validation_command: str | None = None,
) -> dict[str, Any]:
    """Apply a list of ops atomically. Returns a result dict; never raises.

    Result shape:
        success            : bool
        applied_ops        : list of ops that were applied (or rolled back)
        diffs              : list of unified-diff strings (one per replace_snippet)
        rollback_performed : bool
        failed_op_index    : int | None  (only on failure)
        failed_op          : dict | None
        error              : str | None
        message            : human-readable summary
    """
    if not isinstance(plan, list) or not plan:
        return {
            "success": False,
            "error": "patch_plan must be a non-empty list of ops",
            "applied_ops": [],
            "diffs": [],
            "rollback_performed": False,
            "message": "Empty or invalid patch_plan.",
        }

    root = Path(project_root).resolve()
    if not root.is_dir():
        return {
            "success": False,
            "error": f"project_root is not a directory: {project_root}",
            "applied_ops": [],
            "diffs": [],
            "rollback_performed": False,
            "message": "Bad project_root.",
        }

    rollbacks: list[RollbackEntry] = []
    diffs: list[str] = []
    applied_ops: list[dict] = []

    for idx, op in enumerate(plan):
        if not isinstance(op, dict):
            return _rollback_and_fail(
                rollbacks, op, idx,
                "op is not a JSON object", diffs, applied_ops,
            )

        op_type = (op.get("op") or "").strip()
        rel_path = op.get("relative_path") or op.get("file") or ""
        target = _resolve_safe_target(root, rel_path)

        if target is None:
            return _rollback_and_fail(
                rollbacks, op, idx,
                f"path is absolute, empty, or escapes repo: {rel_path!r}",
                diffs, applied_ops,
            )

        # ---- create_file ----
        if op_type == "create_file":
            content = op.get("content", "")
            if not isinstance(content, str):
                return _rollback_and_fail(
                    rollbacks, op, idx,
                    "create_file: 'content' must be a string", diffs, applied_ops,
                )
            if target.exists():
                return _rollback_and_fail(
                    rollbacks, op, idx,
                    f"create_file: target already exists: {rel_path}", diffs, applied_ops,
                )
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            except Exception as e:
                return _rollback_and_fail(
                    rollbacks, op, idx,
                    f"create_file: write failed: {e}", diffs, applied_ops,
                )
            rollbacks.append((target, None))
            diffs.append(_make_diff("", content, rel_path))
            applied_ops.append(op)

        # ---- replace_snippet ----
        elif op_type == "replace_snippet":
            target_snippet = op.get("target_snippet")
            patched_snippet = op.get("patched_snippet")
            if not isinstance(target_snippet, str) or not isinstance(patched_snippet, str):
                return _rollback_and_fail(
                    rollbacks, op, idx,
                    "replace_snippet: target_snippet and patched_snippet must be strings",
                    diffs, applied_ops,
                )
            if not target.is_file():
                return _rollback_and_fail(
                    rollbacks, op, idx,
                    f"replace_snippet: target file does not exist: {rel_path}",
                    diffs, applied_ops,
                )
            try:
                original = target.read_text(encoding="utf-8")
            except Exception as e:
                return _rollback_and_fail(
                    rollbacks, op, idx,
                    f"replace_snippet: read failed: {e}", diffs, applied_ops,
                )
            if target_snippet not in original:
                return _rollback_and_fail(
                    rollbacks, op, idx,
                    f"replace_snippet: target_snippet not found verbatim in {rel_path}",
                    diffs, applied_ops,
                )
            # Replace first occurrence only (safer than replace_all).
            new_text = original.replace(target_snippet, patched_snippet, 1)
            try:
                target.write_text(new_text, encoding="utf-8")
            except Exception as e:
                return _rollback_and_fail(
                    rollbacks, op, idx,
                    f"replace_snippet: write failed: {e}", diffs, applied_ops,
                )
            rollbacks.append((target, original))
            diffs.append(_make_diff(original, new_text, rel_path))
            applied_ops.append(op)

        else:
            return _rollback_and_fail(
                rollbacks, op, idx,
                f"unknown op type: {op_type!r} (allowed: create_file, replace_snippet)",
                diffs, applied_ops,
            )
    # ---- validation after all ops ----
    validation_output = ""
    validation_ok = None

    if validation_command:
        try:
            from core.validator import run_validation_command, classify_validation_output

            validation_ok, validation_output = run_validation_command(
                validation_command,
                cwd=str(root),
            )

            if not validation_ok:
                info = classify_validation_output(validation_output)

                return _rollback_and_fail(
                    rollbacks=rollbacks,
                    op={
                        "op": "validation",
                        "command": validation_command,
                        "category": info.get("category", "unknown"),
                    },
                    idx=len(plan),
                    error=(
                        f"validation failed ({info.get('category', 'unknown')}): "
                        f"{info.get('reason', '')}"
                    ),
                    diffs=diffs,
                    applied_ops=applied_ops,
                ) | {
                    "validation_ok": False,
                    "validation_command": validation_command,
                    "validation_output": validation_output,
                    "validation_info": info,
                    "message": "Patch plan applied, validation failed, rollback performed.",
                }

        except Exception as e:
            return _rollback_and_fail(
                rollbacks=rollbacks,
                op={"op": "validation", "command": validation_command},
                idx=len(plan),
                error=f"validation runner crashed: {e}",
                diffs=diffs,
                applied_ops=applied_ops,
            ) | {
                "validation_ok": False,
                "validation_command": validation_command,
                "validation_output": validation_output,
                "message": "Patch plan validation crashed, rollback performed.",
            }
    return {
        "success": True,
        "applied_ops": applied_ops,
        "diffs": diffs,
        "rollback_performed": False,
        "failed_op_index": None,
        "failed_op": None,
        "error": None,
        "validation_ok": validation_ok,
        "validation_command": validation_command or "",
        "validation_output": validation_output,
        "message": (
            "Patch plan applied and validation passed."
            if validation_command
            else "Patch plan applied."
        ),
    }