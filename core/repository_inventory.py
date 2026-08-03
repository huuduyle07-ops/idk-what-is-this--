from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from config import LANGUAGE_MAP, SUPPORTED_EXTENSIONS
from core.repo_ignore import RepoIgnorePolicy, compute_policy_fingerprint
from core.repository_path_policy import (
    MAX_CANONICAL_RELATIVE_PATH_LENGTH,
    is_safe_repository_relative_path,
)
from core.security import has_safe_path_components, is_safe_path


CANONICAL_WALK_SITE = "core.repo_librarian._walk_policy_files"
_CANONICAL_INDEX_SKIP_NAMES = frozenset(
    {
        "session_log.txt",
        "memory_file_for_agent.txt",
        "postgres_auth.txt",
    }
)


@dataclass(frozen=True, slots=True)
class RepositoryFileIdentity:
    """Descriptor-comparable identity captured with repository membership."""

    device: int
    inode: int
    mode: int
    size_bytes: int
    modified_ns: int
    changed_ns: int
    created_ns: int = 0

    @classmethod
    def from_stat_result(cls, value: os.stat_result) -> "RepositoryFileIdentity":
        return cls(
            device=int(value.st_dev),
            inode=int(value.st_ino),
            mode=int(value.st_mode),
            size_bytes=int(value.st_size),
            modified_ns=int(value.st_mtime_ns),
            changed_ns=int(value.st_ctime_ns),
            created_ns=int(getattr(value, "st_birthtime_ns", 0)),
        )


@dataclass(frozen=True, slots=True)
class RepositoryEntry:
    """One immutable repository-membership entry."""

    absolute_path: Path
    relative_path: Path
    file_identity: RepositoryFileIdentity | None = field(
        default=None,
        compare=False,
        repr=False,
    )

    def as_pair(self) -> tuple[Path, Path]:
        return self.absolute_path, self.relative_path


@dataclass(frozen=True, slots=True)
class RepositoryInventory:
    """Operation-scoped snapshot of repository membership.

    The snapshot describes membership at enumeration time. It is not a
    guarantee that file contents, metadata, or even file existence remain
    unchanged while downstream processing runs.
    """

    canonical_root: str
    entries: tuple[RepositoryEntry, ...]
    indexable_entries: tuple[RepositoryEntry, ...]
    ignore_policy_fingerprint: str
    created_at: str | None = None
    traversal_count: int = 1
    walk_sites: tuple[str, ...] = (CANONICAL_WALK_SITE,)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.canonical_root, str)
            or not self.canonical_root.strip()
        ):
            raise ValueError(
                "inventory canonical_root must be a nonblank string"
            )
        if not isinstance(self.entries, tuple):
            raise TypeError("inventory entries must be an immutable tuple")
        if not isinstance(self.indexable_entries, tuple):
            raise TypeError(
                "inventory indexable_entries must be an immutable tuple"
            )
        if not isinstance(self.walk_sites, tuple):
            raise TypeError("inventory walk_sites must be an immutable tuple")
        if not isinstance(self.traversal_count, int):
            raise TypeError("inventory traversal_count must be an integer")
        if self.traversal_count < 0:
            raise ValueError("inventory traversal_count must be non-negative")
        if self.created_at is not None and not isinstance(
            self.created_at,
            str,
        ):
            raise TypeError(
                "inventory created_at must be a string or None"
            )
        if any(
            not isinstance(site, str) or not site.strip()
            for site in self.walk_sites
        ):
            raise ValueError(
                "inventory walk_sites must contain nonblank strings"
            )

        raw_root = Path(self.canonical_root).expanduser()
        if not raw_root.is_absolute():
            raise ValueError("inventory canonical_root must be absolute")
        root = raw_root.resolve()
        object.__setattr__(self, "canonical_root", str(root))

        normalized_entries = _validate_entries(
            root,
            self.entries,
            label="entries",
        )
        normalized_indexable = _validate_entries(
            root,
            self.indexable_entries,
            label="indexable_entries",
        )
        object.__setattr__(self, "entries", normalized_entries)
        object.__setattr__(
            self,
            "indexable_entries",
            normalized_indexable,
        )

        entry_keys = {
            (
                _canonical_path_key(entry.absolute_path),
                os.path.normcase(entry.relative_path.as_posix()),
            )
            for entry in normalized_entries
        }
        for entry in normalized_indexable:
            if (
                _canonical_path_key(entry.absolute_path),
                os.path.normcase(entry.relative_path.as_posix()),
            ) not in entry_keys:
                raise ValueError(
                    "inventory indexable_entries must be a subset of entries"
                )

        expected_indexable = tuple(
            entry
            for entry in normalized_entries
            if _is_default_indexable(entry)
        )
        if normalized_indexable != expected_indexable:
            raise ValueError(
                "inventory indexable_entries do not match the canonical "
                "deterministic filter"
            )

        if not isinstance(self.ignore_policy_fingerprint, str):
            raise TypeError(
                "inventory ignore_policy_fingerprint must be a string"
            )
        current_policy_fingerprint = compute_policy_fingerprint(
            str(root)
        )
        if (
            self.ignore_policy_fingerprint
            != current_policy_fingerprint
        ):
            raise ValueError(
                "inventory ignore-policy fingerprint does not match "
                "the repository"
            )
        policy = RepoIgnorePolicy.load(root)
        for entry in normalized_entries:
            target_relative = entry.absolute_path.relative_to(root)
            if (
                policy.classify(
                    entry.relative_path,
                    is_dir=False,
                ).ignored
                or policy.classify(
                    target_relative,
                    is_dir=False,
                ).ignored
            ):
                raise ValueError(
                    "inventory contains an entry excluded by "
                    "RepoIgnorePolicy"
                )
        if self.walk_sites != tuple(sorted(set(self.walk_sites))):
            raise ValueError(
                "inventory walk_sites must be unique and deterministic"
            )
        if self.traversal_count == 0 and self.walk_sites:
            raise ValueError(
                "inventory with zero traversals cannot report walk sites"
            )
        if self.traversal_count > 0 and not self.walk_sites:
            raise ValueError(
                "inventory with traversals must report at least one walk site"
            )

    @property
    def root_path(self) -> Path:
        return Path(self.canonical_root)

    @property
    def entry_pairs(self) -> tuple[tuple[Path, Path], ...]:
        return tuple(entry.as_pair() for entry in self.entries)

    @property
    def indexable_entry_pairs(
        self,
    ) -> tuple[tuple[Path, Path], ...]:
        return tuple(
            entry.as_pair()
            for entry in self.indexable_entries
        )

    @property
    def canonical_index_entries(
        self,
    ) -> tuple[RepositoryEntry, ...]:
        """Return the exact deterministic membership used by indexing.

        ``indexable_entries`` owns extension and infrastructure policy.
        This final translation removes the small credential/control-file
        denylist that the production indexer has historically enforced.
        It never enumerates the repository and never mutates the inventory.
        """
        return tuple(
            entry
            for entry in self.indexable_entries
            if (
                is_canonical_index_relative_path(entry.relative_path)
                and is_canonical_index_relative_path(
                    entry.absolute_path.relative_to(self.root_path)
                )
            )
        )

    @property
    def canonical_index_entry_pairs(
        self,
    ) -> tuple[tuple[Path, Path], ...]:
        return tuple(
            entry.as_pair()
            for entry in self.canonical_index_entries
        )

    def entries_for_query(
        self,
        query: str | None = None,
    ) -> tuple[RepositoryEntry, ...]:
        from core.repo_librarian import should_include_infra_file

        return tuple(
            entry
            for entry in self.entries
            if should_include_infra_file(
                query,
                entry.relative_path.as_posix(),
            )
        )

    def relative_paths(
        self,
        query: str | None = None,
    ) -> frozenset[str]:
        return frozenset(
            entry.relative_path.as_posix()
            for entry in self.entries_for_query(query)
        )

    def summary(self) -> dict:
        """Return the legacy repository-inventory summary without walking."""
        default_entries = self.entries_for_query(None)
        default_paths = [
            entry.relative_path.as_posix()
            for entry in default_entries
        ]
        indexable_paths = [
            entry.relative_path.as_posix()
            for entry in self.canonical_index_entries
        ]
        default_keys = {
            _canonical_path_key(entry.absolute_path)
            for entry in default_entries
        }
        skipped_paths = [
            entry.relative_path.as_posix()
            for entry in self.entries
            if _canonical_path_key(entry.absolute_path) not in default_keys
        ]

        language_counts: Counter[str] = Counter()
        extension_counts: Counter[str] = Counter()
        for entry in default_entries:
            extension = entry.absolute_path.suffix.lower()
            extension_counts[extension] += 1
            if extension not in SUPPORTED_EXTENSIONS:
                continue
            language = LANGUAGE_MAP.get(extension, "unknown")
            if language not in {
                "text",
                "document",
                "json",
                "unknown",
            }:
                language_counts[language] += 1

        primary_language = (
            language_counts.most_common(1)[0][0]
            if language_counts
            else "unknown"
        )
        warnings: list[str] = []
        if " " in self.canonical_root:
            warnings.append("repo_path contains spaces")
        if not indexable_paths:
            warnings.append("repo has 0 indexable files")
        if primary_language == "unknown":
            warnings.append(
                "could not infer primary language from file extensions"
            )

        return {
            "ok": bool(indexable_paths),
            "reason": (
                ""
                if indexable_paths
                else "0 indexable files found"
            ),
            "repo_root": self.canonical_root,
            "files_total": len(default_paths),
            "indexable_count": len(indexable_paths),
            "primary_language": primary_language,
            "languages": dict(language_counts),
            "extensions": dict(extension_counts),
            "files": default_paths,
            "indexable_files": indexable_paths,
            "skipped_files": skipped_paths[:50],
            "sample_files": default_paths[:20],
            "sample_indexable_files": indexable_paths[:20],
            "warnings": warnings,
        }

    def diagnostics(
        self,
        *,
        inventory_reuse: Mapping[str, bool] | None = None,
    ) -> dict:
        reuse = inventory_reuse or {}
        return {
            "repository_walks": self.traversal_count,
            "walk_sites": list(self.walk_sites),
            "inventory_reuse": {
                key: bool(reuse[key])
                for key in sorted(reuse)
            },
        }


def create_repository_inventory(
    repo_path: str | os.PathLike[str],
    *,
    created_at: str | None = None,
) -> RepositoryInventory:
    """Walk one repository once and materialize its canonical inventory."""
    root = Path(repo_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise NotADirectoryError(
            f"repo_path is not a directory: {root}"
        )

    # Local import avoids a module cycle: repo_librarian exposes compatibility
    # APIs that themselves accept RepositoryInventory.
    from core.repo_librarian import _walk_policy_files

    policy_before = compute_policy_fingerprint(str(root))
    pairs = tuple(_walk_policy_files(root))
    policy_after = compute_policy_fingerprint(str(root))
    if policy_before != policy_after:
        raise RuntimeError(
            "repository ignore policy changed during inventory creation"
        )
    return repository_inventory_from_entries(
        root,
        pairs,
        created_at=created_at,
        traversal_count=1,
        walk_sites=(CANONICAL_WALK_SITE,),
        sort_entries=True,
        ignore_policy_fingerprint=policy_before,
    )


def repository_inventory_from_entries(
    repo_path: str | os.PathLike[str],
    entries: Iterable[
        RepositoryEntry | tuple[Path, Path]
    ],
    *,
    created_at: str | None = None,
    traversal_count: int = 0,
    walk_sites: tuple[str, ...] = (),
    sort_entries: bool = False,
    ignore_policy_fingerprint: str | None = None,
) -> RepositoryInventory:
    """Build a validated inventory from an already materialized enumeration.

    ``sort_entries`` is reserved for the canonical scanner. External supplied
    inventories default to strict ordering validation instead of being silently
    repaired.
    """
    root = Path(repo_path).expanduser().resolve()
    materialized = tuple(
        _coerce_entry(root, entry)
        for entry in entries
    )
    if sort_entries:
        materialized = tuple(
            sorted(
                materialized,
                key=lambda item: item.relative_path.as_posix(),
            )
        )

    indexable = tuple(
        entry
        for entry in materialized
        if _is_default_indexable(entry)
    )
    return RepositoryInventory(
        canonical_root=str(root),
        entries=materialized,
        indexable_entries=indexable,
        ignore_policy_fingerprint=(
            compute_policy_fingerprint(str(root))
            if ignore_policy_fingerprint is None
            else ignore_policy_fingerprint
        ),
        created_at=created_at,
        traversal_count=traversal_count,
        walk_sites=walk_sites,
    )


def validate_repository_inventory(
    repo_path: str | os.PathLike[str],
    inventory: RepositoryInventory,
) -> RepositoryInventory:
    if not isinstance(inventory, RepositoryInventory):
        raise TypeError(
            "inventory must be a RepositoryInventory instance"
        )

    expected_root = Path(repo_path).expanduser().resolve()
    inventory_root = Path(inventory.canonical_root)
    if _canonical_path_key(expected_root) != _canonical_path_key(
        inventory_root
    ):
        raise ValueError(
            "supplied inventory belongs to another repository"
        )
    return inventory


def _coerce_entry(
    root: Path,
    entry: RepositoryEntry | tuple[Path, Path],
) -> RepositoryEntry:
    if isinstance(entry, RepositoryEntry):
        return entry
    if not isinstance(entry, tuple) or len(entry) != 2:
        raise TypeError(
            "repository entries must be RepositoryEntry values or "
            "(absolute_path, relative_path) tuples"
        )
    absolute_path, relative_path = entry
    return RepositoryEntry(
        absolute_path=Path(absolute_path),
        relative_path=Path(relative_path),
    )


def _validate_entries(
    root: Path,
    entries: tuple[RepositoryEntry, ...],
    *,
    label: str,
) -> tuple[RepositoryEntry, ...]:
    normalized: list[RepositoryEntry] = []
    seen: set[str] = set()

    for raw_entry in entries:
        if not isinstance(raw_entry, RepositoryEntry):
            raise TypeError(
                f"inventory {label} must contain RepositoryEntry values"
            )

        relative = Path(raw_entry.relative_path)
        if (
            relative.is_absolute()
            or not relative.parts
            or any(
                part in {"", ".", ".."}
                for part in relative.parts
            )
        ):
            raise ValueError(
                f"inventory {label} contains an unsafe relative path"
            )

        absolute = Path(raw_entry.absolute_path).expanduser().resolve()
        expected = (root / relative).resolve()
        try:
            absolute.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"inventory {label} contains a path outside the repository"
            ) from exc
        if _canonical_path_key(absolute) != _canonical_path_key(
            expected
        ):
            raise ValueError(
                f"inventory {label} absolute and relative paths disagree"
            )

        key = os.path.normcase(relative.as_posix())
        if key in seen:
            raise ValueError(
                f"inventory {label} contains duplicate canonical paths "
                "or relative paths"
            )
        seen.add(key)
        normalized.append(
            RepositoryEntry(
                absolute_path=absolute,
                relative_path=Path(relative.as_posix()),
                file_identity=_capture_file_identity(absolute),
            )
        )

    ordered = tuple(normalized)
    expected_order = tuple(
        sorted(
            ordered,
            key=lambda item: item.relative_path.as_posix(),
        )
    )
    if ordered != expected_order:
        raise ValueError(
            f"inventory {label} must use deterministic path ordering"
        )
    return ordered


def _capture_file_identity(path: Path) -> RepositoryFileIdentity | None:
    """Capture identity without making unreadable/missing entries look valid."""

    try:
        return RepositoryFileIdentity.from_stat_result(path.stat())
    except OSError:
        return None


def _is_default_indexable(entry: RepositoryEntry) -> bool:
    from core.repo_librarian import should_include_infra_file

    return (
        entry.relative_path.suffix.lower() in SUPPORTED_EXTENSIONS
        and should_include_infra_file(
            None,
            entry.relative_path.as_posix(),
        )
    )


def should_skip_index_filename(file_name: str) -> bool:
    """Return the production filename deny decision without filesystem I/O."""
    name = str(file_name).casefold()
    return (
        name == ".env"
        or name.startswith(".env")
        or name in _CANONICAL_INDEX_SKIP_NAMES
    )


def is_canonical_index_path(
    path: str | os.PathLike[str],
    *,
    repo_root: str | os.PathLike[str],
    relative_path: str | os.PathLike[str] | None = None,
) -> bool:
    """Return the exact request-time path gate shared by shadow and runtime.

    Inventory membership owns extension and ignore policy. This final gate
    reuses the production security boundary so secret-like filenames and
    paths that resolve outside the repository never enter shadow hashing or
    planning. Production rechecks the same helper immediately before reading
    to protect against post-inventory path changes.
    """
    candidate = Path(path)
    root = Path(repo_root).resolve()
    if relative_path is None:
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            return False
    else:
        relative = Path(relative_path)
    return (
        is_canonical_index_relative_path(relative)
        and is_safe_path(
            str(candidate),
            allowed_roots=[str(root)],
        )
    )


def is_canonical_index_relative_path(
    relative_path: str | os.PathLike[str],
) -> bool:
    """Apply production index membership rules without filesystem access."""
    from core.repo_librarian import should_include_infra_file

    relative = Path(relative_path)
    rendered = relative.as_posix()
    return (
        is_safe_repository_relative_path(rendered)
        and not should_skip_index_filename(relative.name)
        and relative.suffix.lower() in SUPPORTED_EXTENSIONS
        and should_include_infra_file(None, rendered)
        and has_safe_path_components(relative)
    )


def _canonical_path_key(path: Path) -> str:
    return os.path.normcase(str(Path(path).resolve()))
