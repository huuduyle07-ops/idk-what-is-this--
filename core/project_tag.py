"""Single source of truth for project tags.

A project tag is a short, stable, filesystem-safe identifier used to bucket
sessions, memories, tooling profiles, and the .agent/<tag>/ directory in the
database. It must be:

- DETERMINISTIC: same repo path always yields the same tag, so a project
  is never "forgotten" between runs.
- DISTINGUISHING: two repos that happen to share a folder name still get
  different tags (the fingerprint catches this).
- USER-OVERRIDABLE: if the user supplies an explicit tag, we honor it
  (after sanitizing).

Centralized here to prevent the previous bug where main.py and web/app.py
each invented their own tag scheme — and where create_agent_state silently
fell back to a hardcoded "game-web-mentor" string, causing every project's
memory to land in the same DB bucket.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Optional


_FINGERPRINT_FILE_LIMIT = 5000
IGNORE_DIRS = {".git", "node_modules", "__pycache__", "build", "dist", ".env", "storage","test",".vscode",".claude"}

def fingerprint_repo(path: str, max_files: int = _FINGERPRINT_FILE_LIMIT) -> str:
    """Short stable hash of a repo's file inventory.

    Uses sorted relative paths (not contents) so the hash is fast and stable
    against whitespace/edits while still changing when files are added,
    removed, or renamed. Returns 'nopath' for missing/invalid input.
    """
    if not path or not os.path.isdir(path):
        return "nopath"

    h = hashlib.sha1()
    count = 0
    root_abs = os.path.abspath(path)

    for root, _, files in os.walk(root_abs):
        for f in sorted(files):
            full = os.path.join(root, f)
            # Use relative path so two clones of the same repo produce the same hash.
            rel = os.path.relpath(full, root_abs)
            h.update(rel.encode("utf-8", errors="replace"))
            count += 1
            if count >= max_files:
                return h.hexdigest()[:10]

    return h.hexdigest()[:10]


def _sanitize(name: Optional[str]) -> str:
    """Lowercase, replace spaces with dashes, strip non-[a-z0-9-]."""
    if not name:
        return ""
    s = name.strip().lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def build_project_tag(
    repo_path: Optional[str],
    user_tag: Optional[str] = None,
) -> str:
    """Return the canonical project tag for a repo path.

    Priority:
        1. user_tag, if non-empty after sanitization.
        2. "<sanitized_repo_name>-<fingerprint>".
        3. "project-<short_hash>" if the repo name sanitizes to empty.
        4. "unknown-project" if no repo_path is given.

    Examples:
        build_project_tag("/home/me/MyGame")        -> "mygame-a1b2c3d4e5"
        build_project_tag("/x/MyGame", "tetris")    -> "tetris"
        build_project_tag(None)                     -> "unknown-project"
        build_project_tag("/x/!!!")                 -> "project-7421"
    """
    # 1. Explicit user tag wins.
    if user_tag:
        cleaned = _sanitize(user_tag)
        if cleaned:
            return cleaned

    # 4. No path at all.
    if not repo_path:
        return "unknown-project"

    name = _sanitize(Path(repo_path).name)
    fp = fingerprint_repo(repo_path)

    # 3. Name sanitizes to empty (path was just symbols/whitespace).
    if not name:
        stable = hashlib.sha1(str(repo_path).encode()).hexdigest()[:8]
        return f"project-{stable}"

    # 2. Standard case.
    return f"{name}-{fp}"
