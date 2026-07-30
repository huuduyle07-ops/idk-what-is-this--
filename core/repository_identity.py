"""Canonical, path-derived identity for persistent repository state.

INDEX.1D.2A separates physical repository identity from an optional,
human-confirmed semantic label. Identity derivation resolves one repository
root and hashes only its normalized path. It never walks the repository, reads
source files, inspects Git metadata, or derives authority from ``project_tag``.

Symlink policy
--------------
Persistent identity follows symlinks: ``Path.resolve(strict=True)`` binds both a
real path and a symlink to the same physical canonical root.

Case policy
-----------
The resolved display path is preserved in ``canonical_root``. The hash input is
``normpath``-normalized and passed through Windows ``normcase``, preserving the
existing lowercase/separator policy. It is not case-normalized on other
platforms; filesystem sensitivity is never discovered by scanning contents.

Compatibility
-------------
``build_repository_storage_key`` and ``build_code_index_scope`` retain their
pre-INDEX.1D.2A default formats. They delegate to the canonical primitive.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
from typing import Any


_REPOSITORY_ID_RE = re.compile(
    r"^[a-z0-9][a-z0-9-]*-[0-9a-f]{32}$"
)
_CODE_INDEX_SCOPE_RE = re.compile(
    r"^code-index-[a-z0-9][a-z0-9-]*-[0-9a-f]{32}"
    r"(?:-epoch-[0-9a-f]{16})?$"
)
_MAX_STORAGE_SLUG_LENGTH = 111


@dataclass(frozen=True)
class RepositoryIdentity:
    """One immutable identity/authority record for a physical repository."""

    canonical_root: str
    repository_id: str
    storage_key: str
    index_scope: str
    project_tag: str | None
    architecture_epoch: int | str | None = None


def canonicalize_repository_root(
    repo_path: str | os.PathLike[str],
) -> str:
    """Return an absolute, symlink-resolved repository directory.

    Missing paths, files, broken symlinks, and invalid inputs fail with the
    project's established ``NotADirectoryError`` convention. No repository
    inventory or file content is inspected.
    """
    if repo_path is None or not str(repo_path).strip():
        raise NotADirectoryError(
            "repo_path is not a directory: empty repository path"
        )

    candidate = Path(repo_path).expanduser()
    try:
        root = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise NotADirectoryError(
            f"repo_path is not a directory: {candidate}"
        ) from exc

    if not root.is_dir():
        raise NotADirectoryError(
            f"repo_path is not a directory: {root}"
        )

    return str(root)


def _canonical_identity_key(canonical_root: str) -> str:
    normalized = os.path.normpath(canonical_root)
    if os.name == "nt":
        # Preserve the pre-INDEX.1D.2A digest policy exactly.
        normalized = os.path.normcase(normalized)
    return normalized


def _repository_slug(canonical_root: str) -> str:
    slug = Path(canonical_root).name.casefold().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "repository"


def _repository_path_digest(canonical_root: str) -> str:
    identity_key = _canonical_identity_key(canonical_root)
    return hashlib.sha256(
        identity_key.encode("utf-8", errors="replace")
    ).hexdigest()


def _repository_id_from_canonical_root(
    canonical_root: str,
) -> str:
    slug = _repository_slug(canonical_root)
    digest = _repository_path_digest(canonical_root)
    return f"{slug}-{digest[:32]}"


def derive_repository_id(
    repo_path: str | os.PathLike[str],
) -> str:
    """Derive stable physical identity only from the canonical root."""
    canonical_root = canonicalize_repository_root(repo_path)
    return _repository_id_from_canonical_root(canonical_root)


def derive_repository_id_from_canonical_root(
    canonical_root: str,
) -> str:
    """Derive physical identity from an already-canonical absolute root.

    This pure validator counterpart performs no filesystem access. Callers
    that have not already established a canonical root must use
    :func:`derive_repository_id` instead.
    """
    if (
        not isinstance(canonical_root, str)
        or not canonical_root.strip()
        or not Path(canonical_root).is_absolute()
    ):
        raise ValueError(
            "canonical_root must be a nonblank absolute path"
        )
    return _repository_id_from_canonical_root(canonical_root)


def is_repository_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and _REPOSITORY_ID_RE.fullmatch(value) is not None
    )


def _repository_id_parts(repository_id: str) -> tuple[str, str]:
    if not is_repository_id(repository_id):
        raise ValueError(
            f"invalid repository_id: {repository_id!r}"
        )
    slug, digest = repository_id.rsplit("-", 1)
    return slug, digest


def _storage_key_from_repository_id(
    repository_id: str,
) -> str:
    slug, digest = _repository_id_parts(repository_id)
    # Preserve ordinary INDEX.1B keys exactly while ensuring the result remains
    # valid under lesson-store's 128-character repository-scope boundary.
    storage_slug = (
        slug[:_MAX_STORAGE_SLUG_LENGTH].rstrip("-")
        or "repository"
    )
    return f"{storage_slug}-{digest[:16]}"


def derive_repository_storage_key(
    repo_path: str | os.PathLike[str],
) -> str:
    """Derive the compatible filesystem namespace from ``repository_id``."""
    repository_id = derive_repository_id(repo_path)
    return _storage_key_from_repository_id(repository_id)


def derive_repository_storage_key_from_id(
    repository_id: str,
) -> str:
    """Derive the bounded artifact namespace from a physical repository ID."""
    return _storage_key_from_repository_id(repository_id)


def _architecture_epoch_suffix(
    architecture_epoch: int | str | None,
) -> str:
    if architecture_epoch is None:
        return ""
    if isinstance(architecture_epoch, bool):
        raise ValueError(
            "architecture_epoch must be an integer, string, or None"
        )
    if isinstance(architecture_epoch, int):
        if architecture_epoch < 0:
            raise ValueError(
                "architecture_epoch integer must be non-negative"
            )
        normalized = str(architecture_epoch)
    elif isinstance(architecture_epoch, str):
        normalized = architecture_epoch.strip()
        if not normalized:
            raise ValueError(
                "architecture_epoch string must not be empty"
            )
    else:
        raise ValueError(
            "architecture_epoch must be an integer, string, or None"
        )

    digest = hashlib.sha256(
        f"architecture-epoch:{normalized}".encode("utf-8")
    ).hexdigest()[:16]
    return f"-epoch-{digest}"


def derive_repository_index_scope(
    repo_path: str | os.PathLike[str],
    *,
    architecture_epoch: int | str | None = None,
) -> str:
    """Derive strict DB authority from physical identity and optional epoch."""
    repository_id = derive_repository_id(repo_path)
    return _index_scope_from_repository_id(
        repository_id,
        architecture_epoch=architecture_epoch,
    )


def derive_repository_index_scope_from_id(
    repository_id: str,
    *,
    architecture_epoch: int | str | None = None,
) -> str:
    """Derive strict DB authority from an already-validated physical ID.

    This is the pure, zero-filesystem counterpart to
    :func:`derive_repository_index_scope`. Identity-state validation uses it
    to verify persisted epoch scopes without resolving or scanning a
    repository again.
    """
    return _index_scope_from_repository_id(
        repository_id,
        architecture_epoch=architecture_epoch,
    )


def _index_scope_from_repository_id(
    repository_id: str,
    *,
    architecture_epoch: int | str | None,
) -> str:
    scope = (
        f"code-index-{repository_id}"
        f"{_architecture_epoch_suffix(architecture_epoch)}"
    )
    if not is_code_index_scope(scope):
        raise ValueError("derived an invalid code-index scope")
    return scope


def _semantic_project_tag(project_tag: Any) -> str | None:
    if project_tag is None:
        return None
    normalized = str(project_tag).strip()
    return normalized or None


def build_repository_identity(
    repo_path: str | os.PathLike[str],
    *,
    project_tag: str | None = None,
    architecture_epoch: int | str | None = None,
) -> RepositoryIdentity:
    """Build the complete physical identity and strict authority record."""
    canonical_root = canonicalize_repository_root(repo_path)
    repository_id = _repository_id_from_canonical_root(
        canonical_root
    )
    storage_key = _storage_key_from_repository_id(repository_id)
    index_scope = _index_scope_from_repository_id(
        repository_id,
        architecture_epoch=architecture_epoch,
    )
    return RepositoryIdentity(
        canonical_root=canonical_root,
        repository_id=repository_id,
        storage_key=storage_key,
        index_scope=index_scope,
        project_tag=_semantic_project_tag(project_tag),
        architecture_epoch=architecture_epoch,
    )


def build_repository_storage_key(
    repo_path: str | os.PathLike[str],
) -> str:
    """Compatibility wrapper for the canonical filesystem namespace."""
    return derive_repository_storage_key(repo_path)


def build_code_index_scope(
    repo_path: str | os.PathLike[str],
    *,
    architecture_epoch: int | str | None = None,
) -> str:
    """Compatibility wrapper for strict canonical DB scope."""
    return derive_repository_index_scope(
        repo_path,
        architecture_epoch=architecture_epoch,
    )


def is_code_index_scope(value: object) -> bool:
    return (
        isinstance(value, str)
        and _CODE_INDEX_SCOPE_RE.fullmatch(value) is not None
    )


def repository_identity_authority_matrix() -> tuple[dict[str, Any], ...]:
    """Return canonical code-index authority roles for identity fields.

    Legacy session/memory tables may still use ``project_tag`` as a semantic
    partition. They are not Canonical Incremental Graph authority and remain a
    separately documented compatibility boundary.
    """
    return (
        {
            "field": "canonical_root",
            "purpose": "physical_location",
            "may_be_none": False,
            "may_depend_on_inventory": False,
            "may_scope_db_writes_or_deletes": "indirectly",
        },
        {
            "field": "repository_id",
            "purpose": "stable_physical_identity",
            "may_be_none": False,
            "may_depend_on_inventory": False,
            "may_scope_db_writes_or_deletes": True,
        },
        {
            "field": "storage_key",
            "purpose": "artifact_namespace",
            "may_be_none": False,
            "may_depend_on_inventory": False,
            "may_scope_db_writes_or_deletes": False,
        },
        {
            "field": "index_scope",
            "purpose": "strict_persistent_db_isolation",
            "may_be_none": False,
            "may_depend_on_inventory": False,
            "may_scope_db_writes_or_deletes": True,
        },
        {
            "field": "project_tag",
            "purpose": "human_semantic_label",
            "may_be_none": True,
            "may_depend_on_inventory": False,
            "may_scope_db_writes_or_deletes": False,
        },
    )
