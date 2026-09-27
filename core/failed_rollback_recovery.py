"""Durable emergency material for incomplete automatic rollback.

This store is intentionally separate from DATA.UNDO.1.  Its opaque IDs are
locators for manual repair only: this module exposes no restore operation and
grants no write authority.  Artifacts are created only after rollback was
measured as incomplete or unverifiable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from uuid import uuid4

from core.repository_identity import build_repository_identity
from core.repository_path_policy import is_safe_repository_relative_path
from core.rollback_outcome import ROLLBACK_INCOMPLETE, ROLLBACK_UNVERIFIABLE


RECOVERY_ARTIFACT_SCHEMA_VERSION = 1
RECOVERY_ARTIFACT_NAMESPACE = "failed_rollback_recovery"
_ALLOWED_ORIGINATING_STATUSES = frozenset(
    {ROLLBACK_INCOMPLETE, ROLLBACK_UNVERIFIABLE}
)
_MAX_SOURCE_EXECUTION_ID_CHARS = 256


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value: dict) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def _atomic_bytes(path: Path, raw: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=".recovery-", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _is_link_or_reparse(path: Path) -> bool:
    metadata = path.lstat()
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _real_directory_chain(
    root: Path, parts: tuple[str, ...], *, create: bool = False
) -> Path:
    """Check a store path without following pre-existing links/junctions."""

    current = root
    for part in parts:
        current = current / part
        if create:
            try:
                current.mkdir()
            except FileExistsError:
                pass
        if _is_link_or_reparse(current):
            raise ValueError("recovery store path cannot contain links or reparse points")
        if not current.is_dir():
            raise ValueError("recovery store path must contain only directories")
    try:
        current.resolve().relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError("recovery store escaped the repository") from exc
    return current


def _lexical_target(root: Path, relative_path: str) -> tuple[Path, str]:
    """Preserve the named relative path and reject link-based relabelling."""

    if type(relative_path) is not str or not relative_path:
        raise ValueError("recovery target must be a non-empty relative path")
    normalized_input = relative_path.replace("\\", "/")
    if (
        relative_path != relative_path.strip()
        or Path(relative_path).is_absolute()
        or not is_safe_repository_relative_path(normalized_input)
    ):
        raise ValueError("recovery target must be repository-relative")
    target = Path(os.path.abspath(root / Path(normalized_input)))
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise ValueError("recovery target escaped the repository") from exc
    normalized = relative.as_posix()
    normalized_key = normalized.casefold()
    if not normalized or normalized_key == ".agent" or normalized_key.startswith(".agent/"):
        raise ValueError("recovery target must be a repository source path")

    current = root
    for part in relative.parts:
        current = current / part
        try:
            if _is_link_or_reparse(current):
                raise ValueError(
                    "recovery target cannot traverse a link or reparse point"
                )
        except FileNotFoundError:
            break
    return target, normalized


def _validate_origin(source_execution_id: str, status: str) -> None:
    if (
        type(source_execution_id) is not str
        or not source_execution_id
        or source_execution_id != source_execution_id.strip()
        or len(source_execution_id) > _MAX_SOURCE_EXECUTION_ID_CHARS
        or any(ord(char) < 32 or ord(char) == 127 for char in source_execution_id)
    ):
        raise ValueError("source execution identity is invalid")
    if type(status) is not str or status not in _ALLOWED_ORIGINATING_STATUSES:
        raise ValueError("recovery material requires a failed rollback status")


def _validate_baseline(
    exists: bool, baseline_bytes: bytes | None, mode: int | None
) -> None:
    if type(exists) is not bool or exists != (baseline_bytes is not None):
        raise ValueError("baseline existence and bytes disagree")
    if baseline_bytes is not None and type(baseline_bytes) is not bytes:
        raise ValueError("baseline must contain exact bytes")
    if mode is not None and (
        type(mode) is not int or mode < 0 or mode > 0o7777
    ):
        raise ValueError("baseline mode must be a bounded integer or None")
    if not exists and mode is not None:
        raise ValueError("an absent baseline cannot carry a file mode")


@dataclass(frozen=True, slots=True)
class FailedRollbackRecoveryArtifact:
    artifact_id: str
    schema_version: int
    namespace: str
    canonical_repository_identity: str
    repository_relative_path: str
    source_execution_id: str
    baseline_exists: bool
    baseline_sha256: str
    baseline_bytes_sha256: str
    baseline_mode: int | None
    observed_post_exists: bool | None
    observed_post_sha256: str
    originating_rollback_status: str
    automated_restore_authority: bool = False

    def identity_id(self) -> str:
        fields = asdict(self)
        del fields["artifact_id"]
        return _sha256(_json_bytes(fields))


class FailedRollbackRecoveryStore:
    """Write and integrity-check bounded baseline artifacts inside a repo."""

    def __init__(self, repository_root: str | Path):
        identity = build_repository_identity(repository_root)
        self.root = Path(identity.canonical_root)
        self.repository_id = identity.repository_id
        self.directory = self.root / ".agent" / RECOVERY_ARTIFACT_NAMESPACE / "v1"

    def _check_directory(self, *, create: bool = False) -> None:
        _real_directory_chain(
            self.root, (".agent", RECOVERY_ARTIFACT_NAMESPACE, "v1"), create=create
        )

    def _read_artifact_bytes(self, suffix: str, artifact_id: str) -> bytes:
        self._check_directory()
        path = self.directory / f"{artifact_id}.{suffix}"
        if _is_link_or_reparse(path):
            raise ValueError("recovery artifact cannot be a link or reparse point")
        return path.read_bytes()

    def persist(
        self,
        *,
        relative_path: str,
        baseline_bytes: bytes | None,
        baseline_exists: bool,
        source_execution_id: str,
        originating_rollback_status: str,
        baseline_mode: int | None = None,
    ) -> FailedRollbackRecoveryArtifact:
        target, normalized = _lexical_target(self.root, relative_path)
        _validate_baseline(baseline_exists, baseline_bytes, baseline_mode)
        _validate_origin(source_execution_id, originating_rollback_status)

        try:
            if target.is_file():
                observed_exists: bool | None = True
                observed_hash = _sha256(target.read_bytes())
            elif target.exists() or target.is_symlink():
                observed_exists = True
                observed_hash = ""
            else:
                observed_exists = False
                observed_hash = ""
        except OSError:
            observed_exists = None
            observed_hash = ""

        baseline_hash = _sha256(baseline_bytes) if baseline_bytes is not None else ""
        artifact = FailedRollbackRecoveryArtifact(
            artifact_id="",
            schema_version=RECOVERY_ARTIFACT_SCHEMA_VERSION,
            namespace=RECOVERY_ARTIFACT_NAMESPACE,
            canonical_repository_identity=self.repository_id,
            repository_relative_path=normalized,
            source_execution_id=source_execution_id,
            baseline_exists=baseline_exists,
            baseline_sha256=baseline_hash,
            baseline_bytes_sha256=baseline_hash,
            baseline_mode=baseline_mode,
            observed_post_exists=observed_exists,
            observed_post_sha256=observed_hash,
            originating_rollback_status=originating_rollback_status,
        )
        artifact = replace(artifact, artifact_id=artifact.identity_id())

        # Recheck the destination immediately before each committed write. This
        # blocks pre-existing and normal-process replacement by a junction or
        # symlink; no cross-process CAS guarantee is claimed.
        self._check_directory(create=True)

        # Bytes precede the manifest commit marker.  A created-file baseline has
        # exact original absence, so the manifest itself is the recovery data.
        if baseline_bytes is not None:
            self._check_directory()
            _atomic_bytes(
                self.directory / f"{artifact.artifact_id}.baseline",
                baseline_bytes,
            )
        self._check_directory()
        _atomic_bytes(
            self.directory / f"{artifact.artifact_id}.json",
            _json_bytes(asdict(artifact)),
        )
        self.verify(artifact)
        return artifact

    def verify(self, artifact: FailedRollbackRecoveryArtifact) -> None:
        if artifact.identity_id() != artifact.artifact_id:
            raise ValueError("recovery artifact identity failed verification")
        if (
            type(artifact.schema_version) is not int
            or artifact.schema_version != RECOVERY_ARTIFACT_SCHEMA_VERSION
            or artifact.namespace != RECOVERY_ARTIFACT_NAMESPACE
            or artifact.canonical_repository_identity != self.repository_id
            or artifact.automated_restore_authority is not False
        ):
            raise ValueError("recovery artifact scope failed verification")
        _lexical_target(self.root, artifact.repository_relative_path)
        _validate_origin(
            artifact.source_execution_id, artifact.originating_rollback_status
        )
        raw = self._read_artifact_bytes("json", artifact.artifact_id)
        stored = FailedRollbackRecoveryArtifact(**json.loads(raw))
        if stored != artifact:
            raise ValueError("recovery artifact metadata failed verification")
        baseline_path = self.directory / f"{artifact.artifact_id}.baseline"
        if artifact.baseline_exists:
            baseline = self._read_artifact_bytes("baseline", artifact.artifact_id)
            _validate_baseline(artifact.baseline_exists, baseline, artifact.baseline_mode)
            if (
                _sha256(baseline) != artifact.baseline_bytes_sha256
                or artifact.baseline_sha256 != artifact.baseline_bytes_sha256
            ):
                raise ValueError("recovery baseline bytes failed verification")
        else:
            _validate_baseline(artifact.baseline_exists, None, artifact.baseline_mode)
            self._check_directory()
            if (
                artifact.baseline_sha256
                or artifact.baseline_bytes_sha256
                or baseline_path.exists()
                or baseline_path.is_symlink()
            ):
                raise ValueError("absence baseline unexpectedly has stored bytes")


def persist_failed_rollback_material(
    repository_root: str | Path,
    entries: list[tuple[str, bytes | None, bool, int | None]],
    *,
    originating_rollback_status: str,
    source_execution_id: str | None = None,
) -> tuple[tuple[str, ...], str, str]:
    """Persist every unresolved baseline and return IDs, error, execution ID.

    Partial persistence remains visible: successfully committed IDs are kept
    and the bounded error reports that the remaining material could not be
    proven durable.
    """

    execution_id = uuid4().hex if source_execution_id is None else source_execution_id
    ids: list[str] = []
    errors: list[str] = []
    try:
        store = FailedRollbackRecoveryStore(repository_root)
    except Exception as exc:  # noqa: BLE001 - reporting boundary
        return (), f"recovery_store_unavailable:{type(exc).__name__}", execution_id
    for relative, baseline, existed, baseline_mode in entries:
        try:
            artifact = store.persist(
                relative_path=relative,
                baseline_bytes=baseline,
                baseline_exists=existed,
                source_execution_id=execution_id,
                originating_rollback_status=originating_rollback_status,
                baseline_mode=baseline_mode,
            )
            ids.append(artifact.artifact_id)
        except Exception as exc:  # noqa: BLE001 - preserve other targets
            errors.append(f"{relative}:{type(exc).__name__}")
    return tuple(ids), ";".join(errors), execution_id


__all__ = [
    "RECOVERY_ARTIFACT_SCHEMA_VERSION",
    "RECOVERY_ARTIFACT_NAMESPACE",
    "FailedRollbackRecoveryArtifact",
    "FailedRollbackRecoveryStore",
    "persist_failed_rollback_material",
]
