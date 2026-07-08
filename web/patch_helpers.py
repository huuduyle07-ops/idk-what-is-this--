from __future__ import annotations

from pathlib import Path
from typing import Iterable

from config import LANGUAGE_MAP


def detect_patch_language(patch: dict) -> str:
    """Best-effort language inference from the target file extension."""
    target = patch.get("relative_path") or patch.get("file") or ""
    ext = Path(target).suffix.lower()
    return LANGUAGE_MAP.get(ext, "unknown")


def backup_key_for_path(target_file: str) -> str:
    """Return the legacy backup filename prefix for a repo-relative path."""
    return target_file.replace("/", "_").replace("\\", "_")


def detect_repo_language(repo_root: str | Path) -> str:
    """Infer the primary validation language from common repo markers."""
    root = Path(repo_root)

    if (root / "Cargo.toml").exists():
        return "rust"
    if (root / "go.mod").exists():
        return "go"
    if (root / "package.json").exists():
        return "javascript"
    if any(root.rglob("*.mojo")):
        return "mojo"
    if any(root.rglob("*.lua")):
        return "lua"
    if any(root.glob("*.py")) or any(root.rglob("*.py")):
        return "python"
    if (
        any(root.rglob("*.cs"))
        or any(root.rglob("*.sln"))
        or any(root.rglob("*.csproj"))
    ):
        return "csharp"
    if (
        any(root.rglob("*.cpp"))
        or any(root.rglob("*.cc"))
        or any(root.rglob("*.cxx"))
        or any(root.rglob("*.hpp"))
        or any(root.rglob("*.hxx"))
    ):
        return "cpp"
    return "unknown"


def patch_plan_files(plan: Iterable[object]) -> list[str]:
    """Return target paths from patch-plan ops for the safety gate."""
    return [
        (op.get("relative_path") or op.get("file") or "")
        for op in plan
        if isinstance(op, dict)
    ]
