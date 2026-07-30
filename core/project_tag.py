"""Legacy/display project-tag compatibility.

INDEX.1D.2A makes ``core.repository_identity`` the authority for persistent
repository identity. A project tag is now only a human-facing semantic label
or a compatibility namespace. It must never scope canonical code-index access.

The default compatibility value delegates to the path-derived storage key and
therefore performs zero repository walks. ``fingerprint_repo`` remains only as
a legacy inventory diagnostic for callers that explicitly request it.
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import Optional

from core.repository_identity import build_repository_storage_key


_FINGERPRINT_FILE_LIMIT = 5000
IGNORE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    "build",
    "dist",
    ".env",
    "storage",
    "test",
    ".vscode",
    ".claude",
}


def fingerprint_repo(
    path: str,
    max_files: int = _FINGERPRINT_FILE_LIMIT,
) -> str:
    """Return the legacy display-only hash of a repository inventory.

    This helper is retained for explicit compatibility/diagnostic callers. Its
    result is forbidden as a persistent repository identity, artifact storage
    key, or code-index scope.
    """
    if not path or not os.path.isdir(path):
        return "nopath"

    digest = hashlib.sha1()
    count = 0
    root_abs = os.path.abspath(path)

    for root, _, files in os.walk(root_abs):
        for filename in sorted(files):
            full = os.path.join(root, filename)
            relative = os.path.relpath(full, root_abs)
            digest.update(
                relative.encode("utf-8", errors="replace")
            )
            count += 1
            if count >= max_files:
                return digest.hexdigest()[:10]

    return digest.hexdigest()[:10]


def _sanitize(name: Optional[str]) -> str:
    """Lowercase and retain only filesystem-safe label characters."""
    if not name:
        return ""
    sanitized = name.strip().lower().replace(" ", "-")
    sanitized = re.sub(r"[^a-z0-9\-]", "", sanitized)
    return re.sub(r"-+", "-", sanitized).strip("-")


def build_project_tag(
    repo_path: Optional[str],
    user_tag: Optional[str] = None,
) -> str:
    """Return a display/compatibility label, never DB authority.

    Explicit user labels retain legacy sanitization. Without one, a valid
    repository delegates to the canonical path-derived storage key and performs
    no inventory scan. Invalid paths fail through the identity primitive.
    """
    if user_tag:
        cleaned = _sanitize(user_tag)
        if cleaned:
            return cleaned

    if not repo_path:
        return "unknown-project"

    return build_repository_storage_key(repo_path)
