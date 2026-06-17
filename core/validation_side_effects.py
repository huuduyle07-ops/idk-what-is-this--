from __future__ import annotations

import os
from pathlib import Path
from typing import Any


ATOMICITY_SCOPE = "patch_ops_only"
VALIDATION_SIDE_EFFECT_POLICY = "reported_not_rolled_back"

_SNAPSHOT_EXCLUDED_DIRS = {
    ".git",
    ".agent",
    ".tmp",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "node_modules",
    "target",
}

_KNOWN_GENERATED_PARTS = {
    ".cache",
    ".pytest_cache",
    "__pycache__",
    "build",
    "dist",
    "target",
    "coverage",
}

_KNOWN_GENERATED_SUFFIXES = {
    ".log",
    ".pyc",
    ".pyo",
    ".tmp",
    ".temp",
}

FileStamp = tuple[int, int]


def empty_validation_side_effect_report(reason: str = "validation not run") -> dict[str, Any]:
    return {
        "supported": False,
        "reason": reason,
        "created": [],
        "modified": [],
        "deleted": [],
        "summary": {"created": 0, "modified": 0, "deleted": 0},
    }


def atomicity_metadata(
    validation_side_effects: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "atomicity_scope": ATOMICITY_SCOPE,
        "patch_ops_rollback_protected": True,
        "validation_side_effects_in_rollback_scope": False,
        "validation_side_effect_policy": VALIDATION_SIDE_EFFECT_POLICY,
        "sandbox_validation_recommended": True,
        "validation_side_effects": (
            validation_side_effects
            if validation_side_effects is not None
            else empty_validation_side_effect_report()
        ),
    }


def with_atomicity_metadata(
    result: dict[str, Any],
    validation_side_effects: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if validation_side_effects is None:
        validation_side_effects = result.get("validation_side_effects")
    return {
        **atomicity_metadata(validation_side_effects),
        **result,
    }


def snapshot_repo_files(project_root: str | Path) -> dict[str, FileStamp]:
    root = Path(project_root).resolve()
    snapshot: dict[str, FileStamp] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in _SNAPSHOT_EXCLUDED_DIRS
        ]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.is_symlink():
                continue
            try:
                stat = path.stat()
                rel = _relative_posix(path, root)
            except OSError:
                continue
            if rel:
                snapshot[rel] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def diff_validation_side_effects(
    project_root: str | Path,
    before: dict[str, FileStamp],
    after: dict[str, FileStamp],
    patch_touched_paths: list[str | Path],
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    touched = {
        _normalize_relative_path(path, root)
        for path in patch_touched_paths
    }
    touched.discard("")

    created = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    modified = sorted(
        rel
        for rel in set(before) & set(after)
        if before[rel] != after[rel]
    )

    report = {
        "supported": True,
        "reason": "",
        "created": [_side_effect_entry(rel, touched) for rel in created],
        "modified": [_side_effect_entry(rel, touched) for rel in modified],
        "deleted": [_side_effect_entry(rel, touched) for rel in deleted],
    }
    report["summary"] = {
        "created": len(report["created"]),
        "modified": len(report["modified"]),
        "deleted": len(report["deleted"]),
    }
    return report


def _side_effect_entry(rel: str, touched: set[str]) -> dict[str, Any]:
    return {
        "path": rel,
        "inside_patch_touched_scope": rel in touched,
        "known_generated_or_noisy": _is_known_generated_or_noisy(rel),
    }


def _is_known_generated_or_noisy(rel: str) -> bool:
    path = Path(rel)
    lowered_parts = {part.lower() for part in path.parts}
    suffix = path.suffix.lower()
    return bool(lowered_parts & _KNOWN_GENERATED_PARTS) or suffix in _KNOWN_GENERATED_SUFFIXES


def _relative_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except (ValueError, OSError):
        return ""


def _normalize_relative_path(path: str | Path, root: Path) -> str:
    candidate = Path(path)
    try:
        if candidate.is_absolute():
            return candidate.resolve().relative_to(root).as_posix()
    except (ValueError, OSError):
        return ""
    text = str(path).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text
