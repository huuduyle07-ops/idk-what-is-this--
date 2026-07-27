from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path


_CODE_INDEX_SCOPE_RE = re.compile(
    r"^code-index-[a-z0-9-]+-[0-9a-f]{32}$"
)


def _resolve_repository_root(
    repo_path: str | Path,
) -> Path:
    root = Path(repo_path).expanduser().resolve()

    if not root.is_dir():
        raise NotADirectoryError(
            f"repo_path is not a directory: {root}"
        )

    return root


def _repository_slug(root: Path) -> str:
    slug = root.name.casefold().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")

    return slug or "repository"


def _repository_path_digest(root: Path) -> str:
    normalized_path = os.path.normcase(
        os.path.normpath(str(root))
    )

    return hashlib.sha256(
        normalized_path.encode(
            "utf-8",
            errors="replace",
        )
    ).hexdigest()


def build_repository_storage_key(
    repo_path: str | Path,
) -> str:
    """Stable filesystem key used by repository-local artifacts."""
    root = _resolve_repository_root(repo_path)
    slug = _repository_slug(root)
    digest = _repository_path_digest(root)

    # Preserve INDEX.1B's existing path format exactly.
    return f"{slug}-{digest[:16]}"


def build_code_index_scope(
    repo_path: str | Path,
) -> str:
    """Stable DB scope for code units and dependencies."""
    root = _resolve_repository_root(repo_path)
    slug = _repository_slug(root)
    digest = _repository_path_digest(root)

    return f"code-index-{slug}-{digest[:32]}"


def is_code_index_scope(value: object) -> bool:
    return (
        isinstance(value, str)
        and _CODE_INDEX_SCOPE_RE.fullmatch(value) is not None
    )