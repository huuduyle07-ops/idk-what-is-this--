from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from config import AGENT_DIR
from core.repo_librarian import iter_repo_files
from core.repo_ignore import compute_policy_fingerprint
from core.repository_inventory import (
    MAX_CANONICAL_RELATIVE_PATH_LENGTH,
    is_canonical_index_relative_path,
    is_safe_repository_relative_path,
    validate_repository_inventory,
)
from core.security import is_safe_path
from core.repository_identity import (
    build_code_index_scope,
    build_repository_storage_key,
    canonicalize_repository_root,
    derive_repository_id,
    is_code_index_scope,
    is_repository_id,
)

if TYPE_CHECKING:
    from core.repository_inventory import RepositoryInventory

MANIFEST_VERSION = "repository_manifest_v1"
MANIFEST_FILENAME = "repository_manifest_v1.json"
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_MANIFEST_FILES = 100_000
MAX_MANIFEST_PATH_LENGTH = MAX_CANONICAL_RELATIVE_PATH_LENGTH
PRODUCTION_INDEX_EMBEDDING_DIMENSION = 384
DEFAULT_INDEX_EMBEDDING_MODEL = (
    "sentence-transformers/all-MiniLM-L6-v2"
)
INDEX_EMBEDDING_PROVIDER_ID = "sentence_transformers"

MANIFEST_LOAD_LOADED = "loaded"
MANIFEST_LOAD_MISSING = "missing"
MANIFEST_LOAD_INVALID = "invalid"
MANIFEST_LOAD_ROOT_MISMATCH = "root_mismatch"
MANIFEST_LOAD_REPOSITORY_MISMATCH = "repository_mismatch"
MANIFEST_LOAD_EPOCH_MISMATCH = "epoch_mismatch"
MANIFEST_LOAD_SCOPE_MISMATCH = "scope_mismatch"
MANIFEST_LOAD_UNSUPPORTED_SCHEMA = "unsupported_schema"


@dataclass(frozen=True)
class FileFingerprint:
    size: int
    mtime_ns: int
    sha256: str


@dataclass(frozen=True)
class EmbeddingSignature:
    provider_id: str
    model: str
    dimension: int


@dataclass(frozen=True)
class RepositoryManifest:
    version: str
    repo_root: str
    policy_fingerprint: str
    files: dict[str, FileFingerprint]
    repository_id: str | None = None
    architecture_epoch: int | None = None
    index_scope: str | None = None
    embedding_signature: EmbeddingSignature | None = None


@dataclass(frozen=True)
class RepositoryManifestLoadResult:
    status: str
    manifest: RepositoryManifest | None
    present: bool
    reason: str
    bytes_read: int = 0
    legacy_binding: bool = False

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
    previous_records_excluded: int = 0

def get_repository_manifest_path(repo_path: str) -> Path:
    root = Path(repo_path).expanduser().resolve()
    storage_key = build_repository_storage_key(root)

    return (
        AGENT_DIR
        / "repository_manifests"
        / storage_key
        / MANIFEST_FILENAME
    )

def _stable_repository_storage_key(
    repo_root: Path,
) -> str:
    return build_repository_storage_key(repo_root)

def load_repository_manifest(
    repo_path: str,
) -> RepositoryManifest | None:
    """Compatibility loader returning only a valid root-bound manifest."""
    root = Path(repo_path).expanduser().resolve()
    path = get_repository_manifest_path(str(root))

    read_status, payload, _bytes_read, _reason = (
        _read_manifest_payload(path)
    )
    if read_status != MANIFEST_LOAD_LOADED:
        return None

    manifest = _manifest_from_payload(payload)
    if manifest is None:
        return None

    if not _paths_match(manifest.repo_root, str(root)):
        return None
    if (
        not _manifest_paths_are_contained(root, manifest)
        or not _is_sha256(manifest.policy_fingerprint)
    ):
        return None
    if manifest.repository_id is not None and (
        manifest.repository_id != derive_repository_id(str(root))
        or manifest.index_scope
        != build_code_index_scope(
            str(root),
            architecture_epoch=manifest.architecture_epoch,
        )
    ):
        return None

    return manifest


def load_repository_manifest_result(
    repo_path: str,
    *,
    repository_id: str,
    architecture_epoch: int | None,
    index_scope: str,
) -> RepositoryManifestLoadResult:
    """Load and validate one applied manifest for shadow observation.

    Missing state is distinct from malformed or incompatible state. The
    artifact read is bounded and this function never writes, repairs, deletes,
    or advances the manifest.
    """
    try:
        root = Path(repo_path).expanduser().resolve()
        expected_repository_id = str(repository_id)
        expected_scope = str(index_scope)
    except (OSError, RuntimeError, TypeError, ValueError):
        return RepositoryManifestLoadResult(
            status=MANIFEST_LOAD_INVALID,
            manifest=None,
            present=False,
            reason="manifest_request_invalid",
        )

    if (
        not root.exists()
        or not root.is_dir()
        or not is_repository_id(expected_repository_id)
        or (
            architecture_epoch is not None
            and (
                type(architecture_epoch) is not int
                or architecture_epoch <= 0
            )
        )
        or not is_code_index_scope(expected_scope)
    ):
        return RepositoryManifestLoadResult(
            status=MANIFEST_LOAD_INVALID,
            manifest=None,
            present=False,
            reason="manifest_request_invalid",
        )

    path = get_repository_manifest_path(str(root))
    read_status, payload, bytes_read, reason = _read_manifest_payload(
        path
    )
    if read_status != MANIFEST_LOAD_LOADED:
        return RepositoryManifestLoadResult(
            status=read_status,
            manifest=None,
            present=(read_status != MANIFEST_LOAD_MISSING),
            reason=reason,
            bytes_read=bytes_read,
        )

    if not isinstance(payload, dict):
        return RepositoryManifestLoadResult(
            status=MANIFEST_LOAD_INVALID,
            manifest=None,
            present=True,
            reason="manifest_payload_invalid",
            bytes_read=bytes_read,
        )
    if payload.get("version") != MANIFEST_VERSION:
        return RepositoryManifestLoadResult(
            status=MANIFEST_LOAD_UNSUPPORTED_SCHEMA,
            manifest=None,
            present=True,
            reason="manifest_schema_unsupported",
            bytes_read=bytes_read,
        )

    manifest = _manifest_from_payload(payload)
    if manifest is None:
        return RepositoryManifestLoadResult(
            status=MANIFEST_LOAD_INVALID,
            manifest=None,
            present=True,
            reason="manifest_payload_invalid",
            bytes_read=bytes_read,
        )
    if not _paths_match(manifest.repo_root, str(root)):
        return RepositoryManifestLoadResult(
            status=MANIFEST_LOAD_ROOT_MISMATCH,
            manifest=None,
            present=True,
            reason="manifest_root_mismatch",
            bytes_read=bytes_read,
        )
    if not _manifest_paths_are_contained(root, manifest):
        return RepositoryManifestLoadResult(
            status=MANIFEST_LOAD_INVALID,
            manifest=None,
            present=True,
            reason="manifest_path_invalid",
            bytes_read=bytes_read,
        )
    if not _is_sha256(manifest.policy_fingerprint):
        return RepositoryManifestLoadResult(
            status=MANIFEST_LOAD_INVALID,
            manifest=None,
            present=True,
            reason="manifest_policy_fingerprint_invalid",
            bytes_read=bytes_read,
        )

    legacy_binding = (
        "repository_id" not in payload
        and "architecture_epoch" not in payload
        and "index_scope" not in payload
    )
    actual_repository_id = (
        manifest.repository_id
        if manifest.repository_id is not None
        else derive_repository_id(manifest.repo_root)
    )
    if actual_repository_id != expected_repository_id:
        return RepositoryManifestLoadResult(
            status=MANIFEST_LOAD_REPOSITORY_MISMATCH,
            manifest=None,
            present=True,
            reason="manifest_repository_mismatch",
            bytes_read=bytes_read,
            legacy_binding=legacy_binding,
        )

    actual_epoch = manifest.architecture_epoch
    if actual_epoch != architecture_epoch:
        return RepositoryManifestLoadResult(
            status=MANIFEST_LOAD_EPOCH_MISMATCH,
            manifest=None,
            present=True,
            reason="manifest_epoch_mismatch",
            bytes_read=bytes_read,
            legacy_binding=legacy_binding,
        )

    actual_scope = (
        manifest.index_scope
        if manifest.index_scope is not None
        else build_code_index_scope(
            str(root),
            architecture_epoch=actual_epoch,
        )
    )
    if actual_scope != expected_scope:
        return RepositoryManifestLoadResult(
            status=MANIFEST_LOAD_SCOPE_MISMATCH,
            manifest=None,
            present=True,
            reason="manifest_scope_mismatch",
            bytes_read=bytes_read,
            legacy_binding=legacy_binding,
        )

    normalized = RepositoryManifest(
        version=manifest.version,
        repo_root=manifest.repo_root,
        policy_fingerprint=manifest.policy_fingerprint,
        files=manifest.files,
        repository_id=actual_repository_id,
        architecture_epoch=actual_epoch,
        index_scope=actual_scope,
        embedding_signature=manifest.embedding_signature,
    )
    return RepositoryManifestLoadResult(
        status=MANIFEST_LOAD_LOADED,
        manifest=normalized,
        present=True,
        reason="manifest_loaded",
        bytes_read=bytes_read,
        legacy_binding=legacy_binding,
    )


class _DuplicateManifestKey(ValueError):
    pass


def _reject_duplicate_manifest_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateManifestKey("duplicate manifest key")
        result[key] = value
    return result


def _read_manifest_payload(
    path: Path,
) -> tuple[str, Any | None, int, str]:
    """Read at most ``MAX_MANIFEST_BYTES`` and parse duplicate-strict JSON."""
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return (
            MANIFEST_LOAD_MISSING,
            None,
            0,
            "manifest_missing",
        )
    except OSError:
        return (
            MANIFEST_LOAD_INVALID,
            None,
            0,
            "manifest_read_failed",
        )

    try:
        with os.fdopen(descriptor, "rb", buffering=0) as handle:
            metadata = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_size > MAX_MANIFEST_BYTES
            ):
                return (
                    MANIFEST_LOAD_INVALID,
                    None,
                    0,
                    "manifest_read_bound_exceeded",
                )
            raw = handle.read(MAX_MANIFEST_BYTES + 1)
    except OSError:
        return (
            MANIFEST_LOAD_INVALID,
            None,
            0,
            "manifest_read_failed",
        )

    if len(raw) > MAX_MANIFEST_BYTES:
        return (
            MANIFEST_LOAD_INVALID,
            None,
            MAX_MANIFEST_BYTES,
            "manifest_read_bound_exceeded",
        )
    try:
        decoded = raw.decode("utf-8", errors="strict")
        payload = json.loads(
            decoded,
            object_pairs_hook=_reject_duplicate_manifest_keys,
        )
    except (UnicodeError, ValueError, RecursionError):
        return (
            MANIFEST_LOAD_INVALID,
            None,
            len(raw),
            "manifest_json_invalid",
        )
    return (
        MANIFEST_LOAD_LOADED,
        payload,
        len(raw),
        "manifest_payload_read",
    )


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
    _validate_manifest_for_save(root, manifest)

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
    payload: dict[str, Any] = {
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
    if (
        manifest.repository_id is not None
        or manifest.index_scope is not None
        or manifest.architecture_epoch is not None
    ):
        payload.update(
            {
                "repository_id": manifest.repository_id,
                "architecture_epoch": manifest.architecture_epoch,
                "index_scope": manifest.index_scope,
            }
        )
    if manifest.embedding_signature is not None:
        payload["embedding_signature"] = {
            "provider_id": manifest.embedding_signature.provider_id,
            "model": manifest.embedding_signature.model,
            "dimension": manifest.embedding_signature.dimension,
        }
    return payload


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
    repository_id = payload.get("repository_id")
    architecture_epoch = payload.get("architecture_epoch")
    index_scope = payload.get("index_scope")
    raw_embedding_signature = payload.get("embedding_signature")

    if not isinstance(repo_root, str):
        return None

    if not isinstance(policy_fingerprint, str):
        return None

    if not isinstance(raw_files, dict):
        return None
    if len(raw_files) > MAX_MANIFEST_FILES:
        return None

    binding_fields_present = any(
        key in payload
        for key in (
            "repository_id",
            "architecture_epoch",
            "index_scope",
        )
    )
    if binding_fields_present:
        if not is_repository_id(repository_id):
            return None
        if (
            architecture_epoch is not None
            and (
                type(architecture_epoch) is not int
                or architecture_epoch <= 0
            )
        ):
            return None
        if not is_code_index_scope(index_scope):
            return None
    else:
        repository_id = None
        architecture_epoch = None
        index_scope = None

    embedding_signature = _embedding_signature_from_payload(
        raw_embedding_signature
    )
    if (
        raw_embedding_signature is not None
        and embedding_signature is None
    ):
        return None

    files: dict[str, FileFingerprint] = {}

    for rel_path, raw_fingerprint in raw_files.items():
        if not isinstance(rel_path, str):
            return None

        if (
            len(rel_path) > MAX_MANIFEST_PATH_LENGTH
            or not _is_safe_relative_path(rel_path)
        ):
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
        files={
            relative: files[relative]
            for relative in sorted(files)
        },
        repository_id=repository_id,
        architecture_epoch=architecture_epoch,
        index_scope=index_scope,
        embedding_signature=embedding_signature,
    )


def _embedding_signature_from_payload(
    value: Any,
) -> EmbeddingSignature | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {
        "provider_id",
        "model",
        "dimension",
    }:
        return None
    provider_id = value.get("provider_id")
    model = value.get("model")
    dimension = value.get("dimension")
    if (
        not isinstance(provider_id, str)
        or not provider_id.strip()
        or len(provider_id) > 128
        or not isinstance(model, str)
        or not model.strip()
        or len(model) > 512
        or type(dimension) is not int
        or dimension <= 0
        or dimension > 65_536
        or any(
            ord(char) < 32 or ord(char) == 127
            for char in provider_id + model
        )
    ):
        return None
    return EmbeddingSignature(
        provider_id=provider_id,
        model=model,
        dimension=dimension,
    )


def build_current_index_embedding_signature() -> EmbeddingSignature | None:
    """Return the configured signature expected by the production DB schema.

    This is configuration-only: it never loads a model or makes a network
    call. Runtime dimension drift still fails production persistence and is
    reported by shadow parity as an operational divergence.
    """
    retriever_enabled = (
        os.getenv("RETRIEVER_USE_EMBEDDINGS", "true").lower()
        not in {"0", "false", "no"}
    )
    configured_model = os.getenv(
        "EMBEDDING_MODEL",
        DEFAULT_INDEX_EMBEDDING_MODEL,
    )
    if not retriever_enabled:
        candidate = EmbeddingSignature(
            provider_id="zero_vector_fallback",
            model="numpy.zeros",
            dimension=PRODUCTION_INDEX_EMBEDDING_DIMENSION,
        )
    elif (
        configured_model == DEFAULT_INDEX_EMBEDDING_MODEL
    ):
        candidate = EmbeddingSignature(
            provider_id=INDEX_EMBEDDING_PROVIDER_ID,
            model=DEFAULT_INDEX_EMBEDDING_MODEL,
            dimension=PRODUCTION_INDEX_EMBEDDING_DIMENSION,
        )
    else:
        # Production does not expose a configured output dimension without
        # loading/calling the model. Shadow mode must not make that call or
        # guess a custom model's dimension.
        return None
    payload = {
        "provider_id": candidate.provider_id,
        "model": candidate.model,
        "dimension": candidate.dimension,
    }
    return (
        candidate
        if _embedding_signature_from_payload(payload) == candidate
        else None
    )


_HASH_CHUNK_SIZE = 1024 * 1024


def _sha256_file(
    path: Path,
    *,
    allowed_root: Path | None = None,
    return_metadata: bool = False,
) -> str | tuple[str, os.stat_result]:
    if allowed_root is None:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            while chunk := file.read(_HASH_CHUNK_SIZE):
                digest.update(chunk)
        result = digest.hexdigest()
        return (result, path.stat()) if return_metadata else result

    root = Path(allowed_root).resolve()
    for attempt in range(2):
        if not is_safe_path(
            str(path),
            allowed_roots=[str(root)],
        ):
            raise PermissionError(
                "manifest fingerprint path failed safety validation"
            )
        before_path = os.lstat(path)
        if (
            stat.S_ISLNK(before_path.st_mode)
            or not stat.S_ISREG(before_path.st_mode)
        ):
            raise PermissionError(
                "manifest fingerprint requires a regular non-symlink file"
            )

        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb", buffering=0) as handle:
            opened_before = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(opened_before.st_mode)
                or not _same_file_identity(
                    before_path,
                    opened_before,
                )
            ):
                raise PermissionError(
                    "manifest fingerprint path changed before open"
                )
            digest = hashlib.sha256()
            while chunk := handle.read(_HASH_CHUNK_SIZE):
                digest.update(chunk)
            opened_after = os.fstat(handle.fileno())

        try:
            current_path = os.lstat(path)
        except OSError as exc:
            raise OSError(
                "manifest fingerprint path changed during read"
            ) from exc
        if (
            _same_file_identity(opened_before, opened_after)
            and opened_before.st_size == opened_after.st_size
            and opened_before.st_mtime_ns == opened_after.st_mtime_ns
            and _same_file_identity(opened_after, current_path)
            and is_safe_path(
                str(path),
                allowed_roots=[str(root)],
            )
        ):
            result = digest.hexdigest()
            return (
                (result, opened_after)
                if return_metadata
                else result
            )
        if attempt:
            raise OSError(
                "file changed repeatedly while hashing"
            )
    raise OSError("manifest fingerprint failed")


def _same_file_identity(
    left: os.stat_result,
    right: os.stat_result,
) -> bool:
    identity = (left.st_dev, left.st_ino)
    other = (right.st_dev, right.st_ino)
    if identity != (0, 0) and other != (0, 0):
        return identity == other
    return (
        left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )

def _is_safe_relative_path(value: str) -> bool:
    return is_safe_repository_relative_path(value)


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False

    return all(char in "0123456789abcdef" for char in value)


def _paths_match(left: str, right: str) -> bool:
    try:
        left_root = canonicalize_repository_root(left)
        right_root = canonicalize_repository_root(right)
    except (OSError, ValueError):
        return False

    return os.path.normcase(left_root) == os.path.normcase(
        right_root
    )


def _manifest_paths_are_contained(
    root: Path,
    manifest: RepositoryManifest,
) -> bool:
    root_key = os.path.normcase(str(root.resolve()))
    seen: set[str] = set()
    for relative in manifest.files:
        if not _is_safe_relative_path(relative):
            return False
        try:
            candidate = (root / relative).resolve()
            candidate.relative_to(root)
        except (OSError, RuntimeError, ValueError):
            return False
        if os.path.commonpath(
            (root_key, os.path.normcase(str(candidate)))
        ) != root_key:
            return False
        candidate_key = os.path.normcase(str(candidate))
        if candidate_key in seen:
            return False
        seen.add(candidate_key)
    return True


def _validate_manifest_for_save(
    root: Path,
    manifest: RepositoryManifest,
) -> None:
    if len(manifest.files) > MAX_MANIFEST_FILES:
        raise ValueError("manifest contains too many file records")
    if not _manifest_paths_are_contained(root, manifest):
        raise ValueError("manifest contains an unsafe file path")
    if (
        manifest.embedding_signature is not None
        and _embedding_signature_from_payload(
            {
                "provider_id": (
                    manifest.embedding_signature.provider_id
                ),
                "model": manifest.embedding_signature.model,
                "dimension": manifest.embedding_signature.dimension,
            }
        )
        != manifest.embedding_signature
    ):
        raise ValueError("manifest embedding signature is invalid")

    bound = (
        manifest.repository_id is not None
        or manifest.architecture_epoch is not None
        or manifest.index_scope is not None
    )
    if not bound:
        return
    if (
        not is_repository_id(manifest.repository_id)
        or not is_code_index_scope(manifest.index_scope)
        or not _is_sha256(manifest.policy_fingerprint)
        or (
            manifest.architecture_epoch is not None
            and (
                type(manifest.architecture_epoch) is not int
                or manifest.architecture_epoch <= 0
            )
        )
    ):
        raise ValueError("manifest identity binding is invalid")
    expected_repository_id = derive_repository_id(str(root))
    expected_scope = build_code_index_scope(
        str(root),
        architecture_epoch=manifest.architecture_epoch,
    )
    if manifest.repository_id != expected_repository_id:
        raise ValueError("manifest repository_id does not match repository")
    if manifest.index_scope != expected_scope:
        raise ValueError(
            "manifest index_scope does not match repository epoch"
        )

def fingerprint_file(
    path: Path,
    *,
    previous: FileFingerprint | None = None,
    allowed_root: Path | None = None,
) -> FingerprintResult:
    candidate = Path(path)
    root = (
        Path(allowed_root).expanduser().resolve()
        if allowed_root is not None
        else None
    )
    if root is not None and not is_safe_path(
        str(candidate),
        allowed_roots=[str(root)],
    ):
        raise PermissionError(
            "manifest fingerprint path failed safety validation"
        )

    before = (
        os.lstat(candidate)
        if root is not None
        else candidate.stat()
    )
    if root is not None and (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(before.st_mode)
    ):
        raise PermissionError(
            "manifest fingerprint requires a regular non-symlink file"
        )

    if (
        previous is not None
        and previous.size == before.st_size
        and previous.mtime_ns == before.st_mtime_ns
    ):
        if root is not None and not is_safe_path(
            str(candidate),
            allowed_roots=[str(root)],
        ):
            raise PermissionError(
                "manifest fingerprint path failed safety validation"
            )
        return FingerprintResult(
            fingerprint=previous,
            hash_reused=True,
        )

    if root is not None:
        sha256, after = _sha256_file(
            candidate,
            allowed_root=root,
            return_metadata=True,
        )
        return FingerprintResult(
            fingerprint=FileFingerprint(
                size=after.st_size,
                mtime_ns=after.st_mtime_ns,
                sha256=sha256,
            ),
            hash_reused=False,
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
    inventory: "RepositoryInventory | None" = None,
    indexable_only: bool = False,
    repository_id: str | None = None,
    architecture_epoch: int | None = None,
    index_scope: str | None = None,
    index_entries: tuple[tuple[Path, Path], ...] | None = None,
    embedding_signature: EmbeddingSignature | None = None,
) -> tuple[RepositoryManifest, RepositoryDelta]:
    """Inspect the current repository and classify file-state changes.

    This function is read-only with respect to manifest persistence:
    it builds and returns the next manifest but does not save it.
    """
    root = Path(repo_path).expanduser().resolve()
    operation_inventory = (
        validate_repository_inventory(root, inventory)
        if inventory is not None
        else None
    )
    if indexable_only and operation_inventory is None:
        raise ValueError(
            "indexable_only inspection requires a supplied inventory"
        )
    if index_entries is not None:
        if not indexable_only or operation_inventory is None:
            raise ValueError(
                "index_entries require indexable_only supplied inventory"
            )
        materialized_index_entries = tuple(index_entries)
        if (
            materialized_index_entries
            != operation_inventory.canonical_index_entry_pairs
        ):
            raise ValueError(
                "index_entries do not match canonical inventory membership"
            )
    else:
        materialized_index_entries = None

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
    bound_observation = any(
        value is not None
        for value in (
            repository_id,
            architecture_epoch,
            index_scope,
        )
    )
    if bound_observation:
        if (
            not is_repository_id(repository_id)
            or not is_code_index_scope(index_scope)
            or (
                architecture_epoch is not None
                and (
                    type(architecture_epoch) is not int
                    or architecture_epoch <= 0
                )
            )
        ):
            raise ValueError("observed manifest identity binding is invalid")
        if repository_id != derive_repository_id(str(root)):
            raise ValueError(
                "observed manifest repository_id does not match repository"
            )
        if index_scope != build_code_index_scope(
            str(root),
            architecture_epoch=architecture_epoch,
        ):
            raise ValueError(
                "observed manifest index_scope does not match epoch"
            )
        if previous is not None and (
            previous.repository_id != repository_id
            or previous.architecture_epoch != architecture_epoch
            or previous.index_scope != index_scope
        ):
            raise ValueError(
                "previous manifest identity binding does not match observation"
            )
    if (
        operation_inventory is not None
        and policy_fingerprint
        and policy_fingerprint
        != operation_inventory.ignore_policy_fingerprint
    ):
        raise ValueError(
            "policy_fingerprint conflicts with supplied inventory"
        )
    current_policy_fingerprint = (
        (
            operation_inventory.ignore_policy_fingerprint
            if operation_inventory is not None
            else policy_fingerprint
        )
        or compute_policy_fingerprint(str(root))
    )

    policy_changed = (
        previous is not None
        and previous.policy_fingerprint
        != current_policy_fingerprint
    )

    previous_files = previous.files if previous is not None else {}
    previous_record_count = len(previous_files)
    if indexable_only:
        # Applied v1 manifests may predate the canonical index-membership
        # translation and contain repository metadata or secret-like names.
        # Such records are observation-incompatible, not deletion authority.
        # Supported files that are newly ignored remain in this static domain
        # and therefore still classify as deleted as intended.
        previous_files = {
            relative: fingerprint
            for relative, fingerprint in previous_files.items()
            if is_canonical_index_relative_path(relative)
        }
    previous_records_excluded = (
        previous_record_count - len(previous_files)
    )

    current_files: dict[str, FileFingerprint] = {}
    added: list[str] = []
    modified: list[str] = []
    unchanged: list[str] = []

    hashes_computed = 0
    hashes_reused = 0

    entry_pairs = (
        materialized_index_entries
        if materialized_index_entries is not None
        else operation_inventory.canonical_index_entry_pairs
        if indexable_only and operation_inventory is not None
        else iter_repo_files(
            str(root),
            inventory=operation_inventory,
        )
    )
    for absolute_path, relative_path in entry_pairs:
        relative = relative_path.as_posix()
        old_fingerprint = previous_files.get(relative)

        result = fingerprint_file(
            absolute_path,
            previous=old_fingerprint,
            allowed_root=(root if indexable_only else None),
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
        repository_id=repository_id if bound_observation else None,
        architecture_epoch=(
            architecture_epoch if bound_observation else None
        ),
        index_scope=index_scope if bound_observation else None,
        embedding_signature=embedding_signature,
    )

    delta = RepositoryDelta(
        added=tuple(sorted(added)),
        modified=tuple(sorted(modified)),
        deleted=tuple(sorted(deleted)),
        unchanged=tuple(sorted(unchanged)),
        hashes_computed=hashes_computed,
        hashes_reused=hashes_reused,
        policy_changed=policy_changed,
        previous_records_excluded=previous_records_excluded,
    )

    return manifest, delta
