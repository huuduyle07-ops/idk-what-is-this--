"""DATA.UNDO.1: durable, exact web Undo artifacts (not executor rollback).

The opaque ID commits to immutable metadata, including a random transaction.
Storage location conveys no repository authority. No inventory or latest-file
lookup is used. The local lock serializes this web producer and its consumer;
external editors and independent processes do not participate in that lock.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import ntpath
import os
from pathlib import Path
import re
import stat
import tempfile
from threading import RLock
from uuid import uuid4

from core.patch_safety import evaluate_patch_safety
from core.repository_identity import build_repository_identity, is_repository_id


mutation_lock = RLock()
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_TRANSACTION = re.compile(r"[0-9a-f]{32}\Z")


class BackupError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

    def response(self) -> dict:
        return {"success": False, "code": self.code, "message": str(self)}


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


@dataclass(frozen=True)
class BackupArtifact:
    backup_id: str
    schema_version: int
    canonical_repository_identity: str
    repository_relative_path: str
    transaction_id: str
    before_exists: bool
    before_sha256: str
    backup_bytes_sha256: str
    expected_post_exists: bool
    expected_post_sha256: str

    def identity_id(self) -> str:
        fields = asdict(self)
        del fields["backup_id"]
        return _sha256(_json_bytes(fields))

    def validate(self) -> None:
        if (
            type(self.schema_version) is not int or self.schema_version != 1
            or not is_repository_id(self.canonical_repository_identity)
            or not isinstance(self.repository_relative_path, str)
            or not self.repository_relative_path
            or not isinstance(self.transaction_id, str)
            or not _TRANSACTION.fullmatch(self.transaction_id)
            # Created-file Undo was never supported by the durable web flow.
            or self.before_exists is not True
            or self.expected_post_exists is not True
            or any(not isinstance(v, str) or not _HASH.fullmatch(v) for v in (
                self.backup_id, self.before_sha256, self.backup_bytes_sha256,
                self.expected_post_sha256,
            ))
            or self.before_sha256 != self.backup_bytes_sha256
            or self.identity_id() != self.backup_id
        ):
            raise BackupError("backup_metadata_invalid", "Backup metadata integrity failed.")


def _target(root: Path, relative: str) -> tuple[Path, str]:
    # Use the existing gate and physical containment/case policy. A drive is
    # never a repository-relative target (also reject Windows forms on POSIX).
    if not isinstance(relative, str) or ntpath.splitdrive(relative)[0]:
        raise BackupError("backup_target_invalid", "Undo requires a repository-relative target.")
    safety = evaluate_patch_safety([relative], project_root=root)
    if not safety["ok"]:
        raise BackupError("backup_target_invalid", "; ".join(safety["reasons"]))
    try:
        target = (root / relative).resolve()
        normalized = target.relative_to(root)
    except (ValueError, OSError, RuntimeError) as exc:
        raise BackupError("backup_target_invalid", "Undo target escapes the repository.") from exc
    # Path.resolve follows in-repository links, just as the existing patch gate
    # does; outside links fail containment. Windows normcase matches repo policy.
    return target, Path(os.path.normcase(str(normalized))).as_posix()


def _atomic_replace_bytes(path: Path, raw: bytes) -> None:
    """Same-directory binary replacement; existing atomic helpers are text/JSON-only."""
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    fd, temporary = tempfile.mkstemp(prefix=".undo-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@dataclass(frozen=True)
class PendingBackup:
    canonical_repository_identity: str
    repository_relative_path: str
    transaction_id: str
    before_sha256: str
    path: Path


class UndoBackupStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory) / "v1"

    def prepare(self, repo_path: str | Path, relative: str) -> PendingBackup | None:
        """Under mutation_lock, durably preserve bytes before invoking mutation."""
        identity = build_repository_identity(repo_path)
        target, normalized = _target(Path(identity.canonical_root), relative)
        if not target.exists():
            return None
        before = target.read_bytes()
        transaction = uuid4().hex
        self.directory.mkdir(parents=True, exist_ok=True)
        pending = self.directory / f"pending-{transaction}.bak"
        # Pending bytes survive an executor error/crash for manual recovery;
        # they are never a valid ID or an automated restore source.
        _atomic_replace_bytes(pending, before)
        return PendingBackup(identity.repository_id, normalized, transaction, _sha256(before), pending)

    def complete(self, pending: PendingBackup | None, repo_path: str | Path, relative: str) -> BackupArtifact | None:
        """Publish authority only for a completed successful existing-file mutation."""
        if pending is None:
            return None
        identity = build_repository_identity(repo_path)
        target, normalized = _target(Path(identity.canonical_root), relative)
        if identity.repository_id != pending.canonical_repository_identity:
            raise BackupError("backup_repo_mismatch", "Repository changed during Apply.")
        if normalized != pending.repository_relative_path:
            raise BackupError("backup_target_mismatch", "Target changed during Apply.")
        before_hash = _sha256(pending.path.read_bytes())
        if before_hash != pending.before_sha256:
            raise BackupError("backup_integrity_failed", "Stored backup bytes changed during Apply.")
        record = BackupArtifact("", 1, identity.repository_id, normalized, pending.transaction_id,
                                True, before_hash, before_hash, True, _sha256(target.read_bytes()))
        record = replace(record, backup_id=record.identity_id())
        record.validate()
        # The metadata is the commit marker. Until it exists, bytes are unbound.
        os.replace(pending.path, self.directory / f"{record.backup_id}.bak")
        _atomic_replace_bytes(self.directory / f"{record.backup_id}.json", _json_bytes(asdict(record)))
        return record

    def lookup(self, backup_id: str) -> BackupArtifact:
        if not isinstance(backup_id, str) or not _HASH.fullmatch(backup_id):
            raise BackupError("backup_id_required", "An exact opaque backup_id is required; legacy unbound backups cannot be used.")
        if (self.directory / f"{backup_id}.consumed.json").exists():
            raise BackupError("backup_already_consumed", "This backup was already consumed.")
        path = self.directory / f"{backup_id}.json"
        try:
            record = BackupArtifact(**json.loads(path.read_bytes()))
            record.validate()
            if record.backup_id != backup_id:
                raise BackupError("backup_metadata_invalid", "Backup ID does not match its metadata.")
            return record
        except FileNotFoundError as exc:
            raise BackupError("backup_not_found", "Exact backup artifact not found; legacy backups are not trusted.") from exc
        except (TypeError, ValueError, UnicodeError) as exc:
            raise BackupError("backup_metadata_invalid", "Backup metadata is invalid.") from exc

    def undo(self, repo_path: str | Path, backup_id: str, *, relative: str | None = None,
             transaction_id: str | None = None) -> dict:
        try:
            with mutation_lock:
                identity = build_repository_identity(repo_path)
                root = Path(identity.canonical_root)
                record = self.lookup(backup_id)
                if record.canonical_repository_identity != identity.repository_id:
                    raise BackupError("backup_repo_mismatch", "Backup belongs to another repository.")
                target, normalized = _target(root, record.repository_relative_path)
                if normalized != record.repository_relative_path:
                    raise BackupError("backup_target_mismatch", "Backup physical target has changed.")
                if relative is not None and _target(root, relative)[1] != normalized:
                    raise BackupError("backup_target_mismatch", "Backup belongs to another target.")
                if transaction_id is not None and transaction_id != record.transaction_id:
                    raise BackupError("backup_transaction_mismatch", "Backup belongs to another mutation.")
                stored = self.directory / f"{backup_id}.bak"
                try:
                    before = stored.read_bytes()
                except FileNotFoundError as exc:
                    raise BackupError("backup_integrity_failed", "Backup bytes are missing.") from exc
                if _sha256(before) != record.backup_bytes_sha256:
                    raise BackupError("backup_integrity_failed", "Stored backup bytes failed integrity verification.")
                if not target.is_file() or _sha256(target.read_bytes()) != record.expected_post_sha256:
                    raise BackupError("stale_target", "Target changed since this mutation; Undo refused.")
                _atomic_replace_bytes(target, before)
                if not target.is_file() or _sha256(target.read_bytes()) != record.before_sha256:
                    raise BackupError("backup_restore_verification_failed", "Final restored bytes failed verification; backup retained.")
                # A durable tombstone makes reuse deterministic even if later
                # byte cleanup fails. Neither step occurs before verification.
                os.replace(self.directory / f"{backup_id}.json",
                           self.directory / f"{backup_id}.consumed.json")
                try:
                    stored.unlink()
                except OSError:
                    pass  # Consumed authority remains durable; no janitor here.
                return {"success": True, "message": "Undo successful", "backup_id": backup_id,
                        "transaction_id": record.transaction_id, "restored_sha256": record.before_sha256}
        except BackupError as exc:
            return exc.response()
        except (OSError, ValueError, RuntimeError) as exc:
            return {"success": False, "code": "backup_io_failed", "message": f"Undo failed; backup retained: {exc}"}
