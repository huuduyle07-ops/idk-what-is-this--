"""EXEC.PLAN.1: repository-read-only preparation and immediate local recovery.

The direct executor historically has no file/aggregate byte cap. Keep that
compatibility: snapshot memory is O(unique target bytes), not O(ops * file
bytes). Existing payloads, generated diffs and one current edit also use memory. Invalid schemas are rejected before snapshots read any file bytes.
Only named targets and their parent chains are inspected; no repository walk.
This is not the durable user Undo store and grants no execution authority.
"""
from __future__ import annotations

import hashlib
import ntpath
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Literal

from core.patch_safety import evaluate_patch_safety
from core.validation_side_effects import with_atomicity_metadata


# Serializes plan snapshot -> mutate -> validation -> recovery in this process.
# Other mutation paths and external processes do not participate in this lock.
plan_mutation_lock = RLock()


class PlanError(Exception):
    def __init__(self, code: str, message: str, ordinal: int | None = None,
                 patch_safety: dict | None = None):
        super().__init__(message)
        self.code, self.ordinal, self.patch_safety = code, ordinal, patch_safety
        self.failed_op = None


def plan_rejection(error: PlanError) -> dict:
    result = with_atomicity_metadata({
        "success": False, "code": error.code, "error": str(error),
        "message": ("Empty or invalid patch_plan." if str(error) ==
                    "patch_plan must be a non-empty list of ops" else str(error)),
        "failed_op_index": error.ordinal,
        "failed_op": error.failed_op, "applied_ops": [], "diffs": [],
        "rollback_performed": False, "mutation_attempted": False,
        "recovery_attempted": False, "recovery_complete": None,
        "remaining_changed_paths": [], "remaining_created_directories": [],
    })
    if error.patch_safety is not None:
        result["patch_safety"] = error.patch_safety
    return result


@dataclass(frozen=True)
class PreparedOperation:
    kind: Literal["create_file", "replace_snippet"]
    relative_path: str
    target: Path
    ordinal: int
    requested_path: str = ""  # validated spelling for existing diff/result labels
    content: str = ""
    target_snippet: str = ""
    patched_snippet: str = ""

    def as_dict(self) -> dict:
        result = {"op": self.kind, "relative_path": self.requested_path or self.relative_path}
        if self.kind == "create_file":
            result["content"] = self.content
        else:
            result.update(target_snippet=self.target_snippet,
                          patched_snippet=self.patched_snippet)
        return result


@dataclass(frozen=True)
class PreparedPatchPlan:
    root: Path
    operations: tuple[PreparedOperation, ...]


def resolve_safe_target(root: Path, relative: str) -> Path:
    # Reuse the authoritative safety policy and its contained-symlink behavior.
    # splitdrive also rejects Windows drive-relative spellings on POSIX hosts.
    verdict = evaluate_patch_safety([relative], project_root=root)
    if not verdict["ok"]:
        path_error = ("path is absolute, empty, or escapes repo; " if any(
            item["category"] == "traversal" for item in verdict["blocked_paths"]
        ) else "")
        raise PlanError("unsafe_target", "Patch plan blocked by safety gate: " +
                        path_error + "; ".join(verdict["reasons"]), patch_safety=verdict)
    if ntpath.splitdrive(relative)[0] or "\x00" in relative:
        raise PlanError("unsafe_target", "Target must be a repository-relative path.")
    try:
        target = (root / relative).resolve()
        canonical = target.relative_to(root).as_posix()
    except (OSError, ValueError, RuntimeError):
        raise PlanError("unsafe_target", "Target cannot be resolved inside the repository.") from None
    if target == root:
        raise PlanError("unsafe_target", "Target must name a file inside the repository.")
    physical = evaluate_patch_safety([canonical], project_root=root)
    if not physical["ok"]:
        raise PlanError("unsafe_target", "Patch plan blocked by safety gate: " +
                        "; ".join(physical["reasons"]), patch_safety=physical)
    return target


def prepare_patch_plan(project_root: str | Path, plan: object) -> PreparedPatchPlan:
    """Validate ALL JSON fields and paths; never read target bytes or mutate.

    The direct executor tolerates extra keys (the separate strict worker
    envelope remains stricter). Extras are discarded, never execution authority.
    Content defaults to empty only when absent. Both supplied path aliases must
    be strings; relative_path takes precedence, with the existing empty fallback.
    File existence and snippet matches remain ordered runtime preconditions.
    """
    if type(plan) is not list or not plan:
        raise PlanError("invalid_plan_schema", "patch_plan must be a non-empty list of ops")
    # Finish type/schema parsing before performing even path I/O.
    parsed = []
    for index, raw in enumerate(plan):
        def invalid(message: str):
            raise PlanError("invalid_plan_schema", message, index)
        if type(raw) is not dict:
            invalid("op is not a JSON object")
        kind = raw.get("op")
        if type(kind) is not str:
            invalid("op must be a string")
        kind = kind.strip()
        if kind not in ("create_file", "replace_snippet"):
            raise PlanError("unsupported_operation", "Allowed ops: create_file, replace_snippet", index)
        for field in ("relative_path", "file"):
            if field in raw and type(raw[field]) is not str:
                invalid(f"{field} must be a string")
        relative = raw.get("relative_path") or raw.get("file")
        if not relative:
            invalid("relative_path or file is required")
        try:
            relative.encode("utf-8")
        except UnicodeError:
            invalid("relative_path must be valid UTF-8 text")
        fields = ("content",) if kind == "create_file" else ("target_snippet", "patched_snippet")
        values = []
        for field in fields:
            value = raw.get(field, "") if field == "content" else raw.get(field)
            if type(value) is not str:
                invalid(f"{kind}: {field} must be a string")
            # UTF-8 is the existing payload encoding. Lone surrogates must fail
            # before a prior operation writes, rather than at encode time.
            try:
                value.encode("utf-8")
            except UnicodeError:
                invalid(f"{kind}: {field} must be valid UTF-8 text")
            values.append(value)
        parsed.append((index, kind, relative, values))
    if not isinstance(project_root, (str, Path)):
        raise PlanError("invalid_plan_schema", "project_root must be a path string")
    try:
        root = Path(project_root).resolve()
        if not root.is_dir():
            raise PlanError("precondition_failed", "project_root is not a directory")
    except (OSError, ValueError, RuntimeError):
        raise PlanError("precondition_failed", "project_root cannot be resolved") from None
    operations = []
    for index, kind, relative, values in parsed:
        try:
            target = resolve_safe_target(root, relative)
        except PlanError as error:
            error.ordinal = index
            error.failed_op = {"op": kind, "relative_path": relative}
            raise
        canonical = Path(os.path.normcase(str(target))).relative_to(root).as_posix()
        payload = dict(zip(("content",) if kind == "create_file" else
                           ("target_snippet", "patched_snippet"), values))
        operations.append(PreparedOperation(kind, canonical, target, index,
                                            requested_path=relative, **payload))
    return PreparedPatchPlan(root, tuple(operations))


@dataclass(frozen=True)
class TargetBaseline:
    paths: tuple[Path, ...]
    before_exists: bool
    before_bytes: bytes | None
    before_sha256: str | None
    before_mode: int | None


def recheck_target(root: Path, target: Path) -> None:
    if resolve_safe_target(root, target.relative_to(root).as_posix()) != target:
        raise PlanError("unsafe_target", "Prepared physical target changed before access.")


def snapshot_targets(plan: PreparedPatchPlan) -> tuple[TargetBaseline, ...]:
    """Read the complete baseline before first mutation, once per physical file."""
    groups = {}
    for operation in plan.operations:
        path = operation.target
        recheck_target(plan.root, path)
        exists = path.exists()
        info = path.stat() if exists else None
        if info is not None and not stat.S_ISREG(info.st_mode):
            raise PlanError("precondition_failed", "A plan target is not a regular file", operation.ordinal)
        # Resolve/case aliases and hard links share one captured byte baseline.
        key = (info.st_dev, info.st_ino) if info and info.st_ino else os.path.normcase(str(path))
        if key not in groups:
            raw = path.read_bytes() if exists else None
            groups[key] = ([path], raw, stat.S_IMODE(info.st_mode) if info else None)
        elif path not in groups[key][0]:
            groups[key][0].append(path)
    return tuple(TargetBaseline(tuple(paths), raw is not None, raw,
                                hashlib.sha256(raw).hexdigest() if raw is not None else None, mode)
                 for paths, raw, mode in groups.values())


@dataclass(frozen=True)
class CreatedDirectory:
    path: Path
    device: int | None
    inode: int | None


def create_parents(root: Path, target: Path, created: list[CreatedDirectory]) -> None:
    missing = []
    parent = target.parent
    while parent != root and not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        recheck_target(root, directory)
        # An I/O failure after mkdir must not hide the directory side effect.
        # Until stat establishes ownership it is reportable, never deletable.
        created.append(CreatedDirectory(directory, None, None))
        directory.mkdir()  # no recursive deletion or pre-existing ownership
        info = directory.stat()
        created[-1] = CreatedDirectory(directory, info.st_dev, info.st_ino)


def _matches(root: Path, path: Path, baseline: TargetBaseline) -> bool:
    try:
        recheck_target(root, path)
        if not baseline.before_exists:
            return not path.exists() and not path.is_symlink()
        if not path.is_file():
            return False
        return (hashlib.sha256(path.read_bytes()).hexdigest() == baseline.before_sha256
                and stat.S_IMODE(path.stat().st_mode) == baseline.before_mode)
    except Exception:
        return False


def restore_target(path: Path, baseline: TargetBaseline) -> None:
    if baseline.before_exists:
        path.write_bytes(baseline.before_bytes)
        path.chmod(baseline.before_mode)
    elif path.exists():
        path.unlink()


def recover_transaction(root: Path, baselines: tuple[TargetBaseline, ...],
                        created: list[CreatedDirectory]) -> dict:
    """Attempt all targets, then independently verify actual bytes/existence/mode."""
    for baseline in reversed(baselines):
        for path in reversed(baseline.paths):
            try:
                recheck_target(root, path)
                if not _matches(root, path, baseline):
                    restore_target(path, baseline)
            except Exception:
                pass  # Final inspection, not a caught exception, determines truth.
    for directory in reversed(created):
        try:
            recheck_target(root, directory.path)
            info = directory.path.stat()
            if directory.inode is not None and (info.st_dev, info.st_ino) == (directory.device, directory.inode):
                directory.path.rmdir()  # only empty, still-owned directories
        except Exception:
            pass
    remaining = sorted({path.relative_to(root).as_posix()
                        for baseline in baselines for path in baseline.paths
                        if not _matches(root, path, baseline)})
    remaining_dirs = []
    for directory in created:
        try:
            absent = not directory.path.exists() and not directory.path.is_symlink()
        except Exception:
            absent = False
        if not absent:
            remaining_dirs.append(directory.path.relative_to(root).as_posix())
    return {"recovery_attempted": True, "recovery_complete": not remaining and not remaining_dirs,
            "remaining_changed_paths": remaining,
            "remaining_created_directories": sorted(remaining_dirs)}
