"""Immutable CTX.READ.1 receipts and pure freshness decisions.

The records in this module describe an exact descriptor-validated read.  They
are deliberately independent from patching, indexing, databases, graphs, and
model clients.  A receipt is evidence that bytes were read for one task; it is
never reusable write authority.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from typing import Any, Iterator, Mapping

from core.repository_inventory import RepositoryFileIdentity


RECEIPT_FRESHNESS_STATES = (
    "fresh",
    "changed",
    "deleted",
    "replaced",
    "unverifiable",
)


class _RecordMapping(Mapping[str, Any]):
    def as_dict(self) -> dict[str, Any]:  # pragma: no cover - abstract helper
        raise NotImplementedError

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())


@dataclass(frozen=True, slots=True)
class DirectReadFileIdentity(_RecordMapping):
    """Stable stat identity plus bounded-read content digest evidence."""

    device: int
    inode: int
    mode: int
    size_bytes: int
    modified_ns: int
    changed_ns: int
    created_ns: int = 0
    content_sha256: str | None = None
    scanned_content_sha256: str | None = None
    content_digest_scope: str = "full_file"

    def __post_init__(self) -> None:
        for name in (
            "device",
            "inode",
            "mode",
            "size_bytes",
            "modified_ns",
            "changed_ns",
            "created_ns",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.content_digest_scope not in {"full_file", "scanned_prefix"}:
            raise ValueError("unknown content digest scope")
        for digest_name in ("content_sha256", "scanned_content_sha256"):
            digest = getattr(self, digest_name)
            if digest is not None and (
                len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                raise ValueError(f"{digest_name} must be a lowercase SHA-256 digest")
        if self.content_digest_scope == "full_file" and self.content_sha256 is None:
            raise ValueError("a full-file identity requires content_sha256")

    @classmethod
    def from_stat_result(
        cls,
        value: os.stat_result,
        *,
        content_sha256: str | None,
        scanned_content_sha256: str | None = None,
        content_digest_scope: str = "full_file",
    ) -> "DirectReadFileIdentity":
        return cls(
            device=int(value.st_dev),
            inode=int(value.st_ino),
            mode=int(value.st_mode),
            size_bytes=int(value.st_size),
            modified_ns=int(value.st_mtime_ns),
            changed_ns=int(value.st_ctime_ns),
            created_ns=int(getattr(value, "st_birthtime_ns", 0)),
            content_sha256=content_sha256,
            scanned_content_sha256=scanned_content_sha256,
            content_digest_scope=content_digest_scope,
        )

    @property
    def size(self) -> int:
        """Compatibility spelling used by serialized receipt examples."""

        return self.size_bytes

    @property
    def mtime_ns(self) -> int:
        return self.modified_ns

    def as_dict(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "inode": self.inode,
            "mode": self.mode,
            "size": self.size_bytes,
            "size_bytes": self.size_bytes,
            "mtime_ns": self.modified_ns,
            "modified_ns": self.modified_ns,
            "changed_ns": self.changed_ns,
            "created_ns": self.created_ns,
            "content_sha256": self.content_sha256,
            "scanned_content_sha256": self.scanned_content_sha256,
            "content_digest_scope": self.content_digest_scope,
        }


@dataclass(frozen=True, slots=True)
class DirectReadRangeReceipt(_RecordMapping):
    start_line: int
    end_line: int
    bytes_returned: int
    lines_returned: int

    def __post_init__(self) -> None:
        if self.start_line <= 0 or self.end_line < self.start_line:
            raise ValueError("receipt ranges must be positive and ordered")
        if self.bytes_returned < 0 or self.lines_returned <= 0:
            raise ValueError("receipt range counters are invalid")
        if self.lines_returned != self.end_line - self.start_line + 1:
            raise ValueError("receipt range line count does not match its bounds")

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_line": self.start_line,
            "end_line": self.end_line,
            "bytes_returned": self.bytes_returned,
            "lines_returned": self.lines_returned,
        }


@dataclass(frozen=True, slots=True)
class DirectReadReceipt(_RecordMapping):
    """Task- and operation-scoped proof of one successful direct read."""

    task_id: str
    operation_id: str
    inventory_identity: str
    path: str
    read_status: str
    read_mode: str
    file_identity: DirectReadFileIdentity
    ranges: tuple[DirectReadRangeReceipt, ...]
    bytes_scanned: int
    bytes_returned: int
    lines_scanned: int
    lines_returned: int
    truncated: bool
    truncation_reasons: tuple[str, ...]
    decoding: str
    replacement_count: int
    parser_support: str
    understanding_confidence: str
    read_authority_granted: bool = True
    write_authority: bool = False
    patch_authority: bool = False

    def __post_init__(self) -> None:
        if self.read_status not in {
            "read_complete",
            "read_complete_with_truncation",
        }:
            raise ValueError("receipts may only represent successful reads")
        if self.read_mode not in {
            "full_file",
            "match_windows",
            "explicit_ranges",
            "header_and_matches",
        }:
            raise ValueError("unknown direct-read mode")
        if not self.task_id or not self.operation_id or not self.inventory_identity:
            raise ValueError("receipt scope identifiers must be nonblank")
        if self.read_authority_granted is not True:
            raise ValueError("a successful receipt must grant temporary read authority")
        if self.write_authority is not False or self.patch_authority is not False:
            raise ValueError("a direct-read receipt can never grant write or patch authority")
        if min(
            self.bytes_scanned,
            self.bytes_returned,
            self.lines_scanned,
            self.lines_returned,
            self.replacement_count,
        ) < 0:
            raise ValueError("receipt counters must be non-negative")
        if self.bytes_returned > self.bytes_scanned:
            raise ValueError("returned bytes cannot exceed scanned bytes")
        if self.lines_returned > self.lines_scanned:
            raise ValueError("returned lines cannot exceed scanned lines")
        if sum(item.bytes_returned for item in self.ranges) != self.bytes_returned:
            raise ValueError("range bytes must equal receipt bytes_returned")
        if sum(item.lines_returned for item in self.ranges) != self.lines_returned:
            raise ValueError("range lines must equal receipt lines_returned")
        if tuple(sorted(set(self.truncation_reasons))) != self.truncation_reasons:
            raise ValueError("truncation reasons must be unique and deterministic")
        if self.truncated != bool(self.truncation_reasons):
            raise ValueError("receipt truncation flag and reasons disagree")
        if self.read_status == "read_complete" and self.truncated:
            raise ValueError("a complete receipt cannot be truncated")
        if self.read_status == "read_complete_with_truncation" and not self.truncated:
            raise ValueError("a truncated receipt must expose truncation metadata")
        if self.decoding not in {"utf8", "utf8_bom", "utf8_with_replacement"}:
            raise ValueError("unknown direct-read decoding")
        if self.decoding != "utf8_with_replacement" and self.replacement_count:
            raise ValueError("replacement_count requires explicit lossy decoding")
        if self.decoding == "utf8_with_replacement" and (
            self.replacement_count <= 0
            or self.understanding_confidence != "limited"
        ):
            raise ValueError("lossy decoding must report limited understanding")

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "operation_id": self.operation_id,
            "inventory_identity": self.inventory_identity,
            "path": self.path,
            "read_status": self.read_status,
            "read_mode": self.read_mode,
            "file_identity": self.file_identity.as_dict(),
            "ranges": [item.as_dict() for item in self.ranges],
            "bytes_scanned": self.bytes_scanned,
            "bytes_returned": self.bytes_returned,
            "lines_scanned": self.lines_scanned,
            "lines_returned": self.lines_returned,
            "truncated": self.truncated,
            "truncation_reasons": list(self.truncation_reasons),
            "decoding": self.decoding,
            "replacement_count": self.replacement_count,
            "parser_support": self.parser_support,
            "understanding_confidence": self.understanding_confidence,
            "read_authority_granted": True,
            "read_authority": True,
            "write_authority": False,
            "patch_authority": False,
            "authority_scope": {
                "task_scoped": True,
                "operation_scoped": True,
                "persistent": False,
                "repository_contained": True,
                "revocable_by_policy": True,
                "invalid_when_file_identity_changes": True,
            },
        }


@dataclass(frozen=True, slots=True)
class ReceiptFreshnessDecision(_RecordMapping):
    status: str
    reason: str
    receipt_usable_for_future_patch_proposal: bool
    write_authority: bool = False
    patch_authority: bool = False

    def __post_init__(self) -> None:
        if self.status not in RECEIPT_FRESHNESS_STATES:
            raise ValueError(f"unknown receipt freshness state: {self.status}")
        if self.receipt_usable_for_future_patch_proposal != (
            self.status == "fresh"
        ):
            raise ValueError("only a fresh receipt may support a later proposal")
        if self.write_authority is not False or self.patch_authority is not False:
            raise ValueError("freshness never grants write or patch authority")

    @property
    def fresh(self) -> bool:
        return self.status == "fresh"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "receipt_usable_for_future_patch_proposal": self.fresh,
            "write_authority": False,
            "patch_authority": False,
        }


def _mapping_identity(value: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = value.get("file_identity")
    return nested if isinstance(nested, Mapping) else value


def _identity_values(value: Any) -> dict[str, Any] | None:
    if isinstance(value, DirectReadFileIdentity):
        return value.as_dict()
    if isinstance(value, RepositoryFileIdentity):
        return {
            "device": value.device,
            "inode": value.inode,
            "mode": value.mode,
            "size_bytes": value.size_bytes,
            "modified_ns": value.modified_ns,
            "changed_ns": value.changed_ns,
            "created_ns": value.created_ns,
        }
    if isinstance(value, os.stat_result):
        return {
            "device": int(value.st_dev),
            "inode": int(value.st_ino),
            "mode": int(value.st_mode),
            "size_bytes": int(value.st_size),
            "modified_ns": int(value.st_mtime_ns),
            "changed_ns": int(value.st_ctime_ns),
            "created_ns": int(getattr(value, "st_birthtime_ns", 0)),
        }
    if isinstance(value, Mapping):
        mapped = _mapping_identity(value)
        if mapped.get("exists") is False or mapped.get("status") == "deleted":
            return {"deleted": True}
        aliases = {
            "device": ("device", "st_dev"),
            "inode": ("inode", "st_ino"),
            "mode": ("mode", "st_mode"),
            "size_bytes": ("size_bytes", "size", "st_size"),
            "modified_ns": ("modified_ns", "mtime_ns", "st_mtime_ns"),
            "changed_ns": ("changed_ns", "ctime_ns", "st_ctime_ns"),
            "created_ns": ("created_ns", "birthtime_ns", "st_birthtime_ns"),
            "content_sha256": ("content_sha256",),
        }
        result: dict[str, Any] = {}
        for canonical, names in aliases.items():
            for name in names:
                if name in mapped:
                    result[canonical] = mapped[name]
                    break
        return result
    return None


def _receipt_identity(value: DirectReadReceipt | Mapping[str, Any]) -> dict[str, Any] | None:
    if isinstance(value, DirectReadReceipt):
        return value.file_identity.as_dict()
    if isinstance(value, Mapping):
        nested_receipt = value.get("receipt")
        if isinstance(nested_receipt, Mapping):
            return _identity_values(nested_receipt)
        return _identity_values(value)
    return None


def verify_direct_read_receipt(
    receipt: DirectReadReceipt | Mapping[str, Any],
    current_file_identity: DirectReadFileIdentity
    | RepositoryFileIdentity
    | os.stat_result
    | Mapping[str, Any]
    | None,
) -> ReceiptFreshnessDecision:
    """Compare supplied identities without touching the filesystem.

    Callers own acquisition of ``current_file_identity``.  This helper never
    opens a path, and even a ``fresh`` result remains evidence only.
    """

    expected = _receipt_identity(receipt)
    if expected is None:
        return ReceiptFreshnessDecision(
            "unverifiable", "receipt does not contain a usable file identity", False
        )
    if current_file_identity is None:
        return ReceiptFreshnessDecision(
            "deleted", "the previously read inventory member no longer exists", False
        )
    current = _identity_values(current_file_identity)
    if current is None:
        return ReceiptFreshnessDecision(
            "unverifiable", "current identity has an unsupported shape", False
        )
    if current.get("deleted"):
        return ReceiptFreshnessDecision(
            "deleted", "the previously read inventory member no longer exists", False
        )

    required = {"device", "inode", "mode", "size_bytes", "modified_ns"}
    if not required <= expected.keys() or not required <= current.keys():
        return ReceiptFreshnessDecision(
            "unverifiable",
            "descriptor-comparable identity fields are incomplete",
            False,
        )
    if any(
        isinstance(values[name], bool) or not isinstance(values[name], int)
        for values in (expected, current)
        for name in required
    ):
        return ReceiptFreshnessDecision(
            "unverifiable", "current identity fields are invalid", False
        )

    replacement_fields = ("device", "inode", "mode")
    if any(current[name] != expected[name] for name in replacement_fields):
        return ReceiptFreshnessDecision(
            "replaced", "descriptor identity or file type changed", False
        )
    if not stat.S_ISREG(int(current["mode"])):
        return ReceiptFreshnessDecision(
            "replaced", "the path no longer identifies a regular file", False
        )
    expected_created = int(expected.get("created_ns") or 0)
    current_created = int(current.get("created_ns") or 0)
    if expected_created and current_created and expected_created != current_created:
        return ReceiptFreshnessDecision(
            "replaced", "file creation identity changed", False
        )

    changed_fields = ("size_bytes", "modified_ns")
    if any(current[name] != expected[name] for name in changed_fields):
        return ReceiptFreshnessDecision(
            "changed", "file size or modification time changed", False
        )
    if os.name != "nt" and (
        "changed_ns" in expected
        and "changed_ns" in current
        and current["changed_ns"] != expected["changed_ns"]
    ):
        return ReceiptFreshnessDecision(
            "changed", "file change time changed", False
        )
    expected_digest = expected.get("content_sha256")
    current_digest = current.get("content_sha256")
    if expected_digest and current_digest and current_digest != expected_digest:
        return ReceiptFreshnessDecision(
            "changed", "full-file content digest changed", False
        )
    return ReceiptFreshnessDecision(
        "fresh", "descriptor-comparable file identity is unchanged", True
    )


# Stable short alias for patch-gate callers.
verify_receipt_freshness = verify_direct_read_receipt
