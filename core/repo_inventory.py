from __future__ import annotations

from pathlib import Path
from config import SUPPORTED_EXTENSIONS, FOLDER_BLACKLIST


def inspect_repo_inventory(repo_path: str) -> dict:
    root = Path(repo_path).resolve()

    if not root.exists() or not root.is_dir():
        return {
            "ok": False,
            "reason": "repo_path is not a directory",
            "repo_path": str(root),
            "saved_count": 0,
            "indexable_count": 0,
            "sample_files": [],
        }

    all_files: list[str] = []
    indexable_files: list[str] = []

    for p in root.rglob("*"):
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue

        if any(part in FOLDER_BLACKLIST for part in rel.parts):
            continue

        if not p.is_file():
            continue

        rel_str = str(rel).replace("\\", "/")
        all_files.append(rel_str)

        if p.suffix.lower() in SUPPORTED_EXTENSIONS:
            indexable_files.append(rel_str)

    return {
        "ok": len(indexable_files) > 0,
        "reason": "" if indexable_files else "0 indexable files found",
        "repo_path": str(root),
        "saved_count": len(all_files),
        "indexable_count": len(indexable_files),
        "sample_files": all_files[:20],
        "sample_indexable_files": indexable_files[:20],
    }