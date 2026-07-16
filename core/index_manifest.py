from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import AGENT_DIR
from core.repo_librarian import iter_repo_files
from core.repo_ignore import compute_policy_fingerprint

MANIFEST_VERSION = "repository_manifest_v1"
MANIFEST_FILENAME = "repository_manifest_v1.json"


@dataclass(frozen=True)
class FileFingerprint:
    size: int
    mtime_ns: int
    sha256: str


@dataclass(frozen=True)
class RepositoryManifest:
    version: str
    repo_root: str
    policy_fingerprint: str
    files: dict[str, FileFingerprint]

@dataclass(frozen=True)
class FingerprintResult:
    fingerprint: FileFingerprint
    hash_reused: bool

@dataclass(frozen=True)
class RepositoryDelta:
    added: tuple[str, ...]
    modified: tuple[str, ...]
    deleted: tuple[str, ...]
    unchanged: tuple[str, ...]
    hashes_computed: int
    hashes_reused: int
    policy_changed: bool

def get_repository_manifest_path(repo_path: str) -> Path:
    root = Path(repo_path).expanduser().resolve()
    storage_key = _stable_repository_storage_key(root)

    return (
        AGENT_DIR
        / "repository_manifests"
        / storage_key
        / MANIFEST_FILENAME
    )

def _stable_repository_storage_key(repo_root: Path) -> str:
    normalized_path = os.path.normcase(
        str(repo_root.expanduser().resolve())
    )

    path_hash = hashlib.sha256(
        normalized_path.encode(
            "utf-8",
            errors="replace",
        )
    ).hexdigest()[:16]

    readable_name = repo_root.name.casefold().replace(" ", "-")
    readable_name = re.sub(
        r"[^a-z0-9-]+",
        "-",
        readable_name,
    )
    readable_name = re.sub(
        r"-+",
        "-",
        readable_name,
    ).strip("-")

    if not readable_name:
        readable_name = "repository"

    return f"{readable_name}-{path_hash}"

def load_repository_manifest(
    repo_path: str,
) -> RepositoryManifest | None:
    root = Path(repo_path).expanduser().resolve()
    path = get_repository_manifest_path(str(root))

    if not path.is_file():
        return None

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8",
                errors="strict",
            )
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None

    manifest = _manifest_from_payload(payload)
    if manifest is None:
        return None

    if not _paths_match(manifest.repo_root, str(root)):
        return None

    return manifest


def save_repository_manifest(
    repo_path: str,
    manifest: RepositoryManifest,
) -> Path:
    root = Path(repo_path).expanduser().resolve()

    if manifest.version != MANIFEST_VERSION:
        raise ValueError(
            f"unsupported manifest version: {manifest.version!r}"
        )

    if not _paths_match(manifest.repo_root, str(root)):
        raise ValueError(
            "manifest repo_root does not match the requested repository"
        )

    path = get_repository_manifest_path(str(root))
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = _manifest_to_payload(manifest)
    serialized = json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    )
    serialized += "\n"

    temporary_path = path.with_suffix(path.suffix + ".tmp")

    try:
        temporary_path.write_text(
            serialized,
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary_path, path)
    except Exception:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return path


def _manifest_to_payload(
    manifest: RepositoryManifest,
) -> dict[str, Any]:
    return {
        "version": manifest.version,
        "repo_root": manifest.repo_root,
        "policy_fingerprint": manifest.policy_fingerprint,
        "files": {
            rel_path: {
                "size": fingerprint.size,
                "mtime_ns": fingerprint.mtime_ns,
                "sha256": fingerprint.sha256,
            }
            for rel_path, fingerprint in sorted(
                manifest.files.items()
            )
        },
    }


def _manifest_from_payload(
    payload: Any,
) -> RepositoryManifest | None:
    if not isinstance(payload, dict):
        return None

    if payload.get("version") != MANIFEST_VERSION:
        return None

    repo_root = payload.get("repo_root")
    policy_fingerprint = payload.get("policy_fingerprint")
    raw_files = payload.get("files")

    if not isinstance(repo_root, str):
        return None

    if not isinstance(policy_fingerprint, str):
        return None

    if not isinstance(raw_files, dict):
        return None

    files: dict[str, FileFingerprint] = {}

    for rel_path, raw_fingerprint in raw_files.items():
        if not isinstance(rel_path, str):
            return None

        if not _is_safe_relative_path(rel_path):
            return None

        if not isinstance(raw_fingerprint, dict):
            return None

        size = raw_fingerprint.get("size")
        mtime_ns = raw_fingerprint.get("mtime_ns")
        sha256 = raw_fingerprint.get("sha256")

        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
        ):
            return None

        if (
            not isinstance(mtime_ns, int)
            or isinstance(mtime_ns, bool)
            or mtime_ns < 0
        ):
            return None

        if not _is_sha256(sha256):
            return None

        files[rel_path] = FileFingerprint(
            size=size,
            mtime_ns=mtime_ns,
            sha256=sha256,
        )

    return RepositoryManifest(
        version=MANIFEST_VERSION,
        repo_root=repo_root,
        policy_fingerprint=policy_fingerprint,
        files=files,
    )


_HASH_CHUNK_SIZE = 1024 * 1024


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)

    return digest.hexdigest()

def _is_safe_relative_path(value: str) -> bool:
    path = Path(value)

    if path.is_absolute():
        return False

    if not path.parts:
        return False

    return all(part not in {"", ".", ".."} for part in path.parts)


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False

    return all(char in "0123456789abcdef" for char in value)


def _paths_match(left: str, right: str) -> bool:
    try:
        left_path = Path(left).expanduser().resolve()
        right_path = Path(right).expanduser().resolve()
    except OSError:
        return False

    return os.path.normcase(str(left_path)) == os.path.normcase(
        str(right_path)
    )

def fingerprint_file(
    path: Path,
    *,
    previous: FileFingerprint | None = None,
) -> FingerprintResult:
    candidate = Path(path)

    before = candidate.stat()

    if (
        previous is not None
        and previous.size == before.st_size
        and previous.mtime_ns == before.st_mtime_ns
    ):
        return FingerprintResult(
            fingerprint=previous,
            hash_reused=True,
        )

    sha256 = _sha256_file(candidate)
    after = candidate.stat()

    # File changed while it was being read. Retry once using its newest state.
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        sha256 = _sha256_file(candidate)
        final = candidate.stat()

        if (
            after.st_size != final.st_size
            or after.st_mtime_ns != final.st_mtime_ns
        ):
            raise OSError(
                f"file changed repeatedly while hashing: {candidate}"
            )

        after = final

    return FingerprintResult(
        fingerprint=FileFingerprint(
            size=after.st_size,
            mtime_ns=after.st_mtime_ns,
            sha256=sha256,
        ),
        hash_reused=False,
    )

def inspect_repository_delta(
    repo_path: str,
    *,
    previous: RepositoryManifest | None = None,
    policy_fingerprint: str = "",
) -> tuple[RepositoryManifest, RepositoryDelta]:
    """Inspect the current repository and classify file-state changes.

    This function is read-only with respect to manifest persistence:
    it builds and returns the next manifest but does not save it.
    """
    root = Path(repo_path).expanduser().resolve()

    if not root.exists() or not root.is_dir():
        raise NotADirectoryError(
            f"repo_path is not a directory: {root}"
        )

    if previous is not None:
        if previous.version != MANIFEST_VERSION:
            raise ValueError(
                f"unsupported previous manifest version: "
                f"{previous.version!r}"
            )

        if not _paths_match(previous.repo_root, str(root)):
            raise ValueError(
                "previous manifest belongs to another repository"
            )
    current_policy_fingerprint = (
        policy_fingerprint
        or compute_policy_fingerprint(str(root))
    )

    policy_changed = (
        previous is not None
        and previous.policy_fingerprint
        != current_policy_fingerprint
    )

    previous_files = previous.files if previous is not None else {}

    current_files: dict[str, FileFingerprint] = {}
    added: list[str] = []
    modified: list[str] = []
    unchanged: list[str] = []

    hashes_computed = 0
    hashes_reused = 0

    for absolute_path, relative_path in iter_repo_files(str(root)):
        relative = relative_path.as_posix()
        old_fingerprint = previous_files.get(relative)

        result = fingerprint_file(
            absolute_path,
            previous=old_fingerprint,
        )
        current_fingerprint = result.fingerprint
        current_files[relative] = current_fingerprint

        if result.hash_reused:
            hashes_reused += 1
        else:
            hashes_computed += 1

        if old_fingerprint is None:
            added.append(relative)
            continue

        if current_fingerprint.sha256 != old_fingerprint.sha256:
            modified.append(relative)
        else:
            # Metadata may have changed, but equal content hashes mean
            # downstream parsing and embedding work can be reused.
            unchanged.append(relative)

    current_paths = set(current_files)
    previous_paths = set(previous_files)

    deleted = previous_paths - current_paths

    manifest = RepositoryManifest(
        version=MANIFEST_VERSION,
        repo_root=str(root),
        policy_fingerprint=current_policy_fingerprint,
        files={
            relative: current_files[relative]
            for relative in sorted(current_files)
        },
    )

    delta = RepositoryDelta(
        added=tuple(sorted(added)),
        modified=tuple(sorted(modified)),
        deleted=tuple(sorted(deleted)),
        unchanged=tuple(sorted(unchanged)),
        hashes_computed=hashes_computed,
        hashes_reused=hashes_reused,
        policy_changed=policy_changed,
    )

    return manifest, delta