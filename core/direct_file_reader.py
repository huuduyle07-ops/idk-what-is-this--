"""Descriptor-bound, bounded direct reads for CTX.READ.1.

This module reads only an already-selected ``RepositoryEntry``.  Repository
membership and proposed-read validation belong to ``direct_context_runtime``;
the reader owns mode selection, range normalization, incremental byte limits,
UTF-8 validation, descriptor identity checks, and immutable receipts.

No helper in this module grants write or patch authority.
"""

from __future__ import annotations

import codecs
import hashlib
import os
import stat
from dataclasses import dataclass
from itertools import islice
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Mapping, Sequence

from core.bounded_lexical_search import (
    DescriptorFileChangedOrReplaced,
    DescriptorFileOpenFailed,
    current_path_matches_inventory,
    safe_open_inventory_entry,
    same_inventory_file_identity,
)
from core.direct_read_receipt import (
    DirectReadFileIdentity,
    DirectReadRangeReceipt,
    DirectReadReceipt,
)
from core.file_capabilities import FileCapability
from core.repository_inventory import RepositoryEntry
from core.repository_path_policy import is_safe_repository_relative_path


READ_MODES = (
    "full_file",
    "match_windows",
    "explicit_ranges",
    "header_and_matches",
)

DIRECT_READ_OUTCOMES = (
    "read_complete",
    "read_complete_with_truncation",
    "file_changed_or_replaced",
    "path_not_in_inventory",
    "path_outside_repository",
    "symlink_rejected",
    "sensitive_file_blocked",
    "binary_or_opaque",
    "encoding_unsupported",
    "budget_exhausted",
    "read_failed",
)

DEFAULT_MAX_FILES = 8
DEFAULT_MAX_TOTAL_BYTES = 1_048_576
DEFAULT_MAX_BYTES_PER_FILE = 262_144
DEFAULT_MAX_LINES_PER_FILE = 4_000
DEFAULT_MAX_MATCH_WINDOWS_PER_FILE = 8
DEFAULT_MAX_MERGED_RANGES_PER_FILE = 8
DEFAULT_MAX_EXCERPT_LINE_LENGTH = 16_384
DEFAULT_MATCH_LINES_BEFORE = 40
DEFAULT_MATCH_LINES_AFTER = 80
DEFAULT_HEADER_LINES = 80

# Public hard ceilings.  Request-scoped budgets may only reduce these values.
MAX_FILES = DEFAULT_MAX_FILES
MAX_TOTAL_BYTES = DEFAULT_MAX_TOTAL_BYTES
MAX_BYTES_PER_FILE = DEFAULT_MAX_BYTES_PER_FILE
MAX_LINES_PER_FILE = DEFAULT_MAX_LINES_PER_FILE
MAX_MATCH_WINDOWS_PER_FILE = DEFAULT_MAX_MATCH_WINDOWS_PER_FILE
MAX_MERGED_RANGES_PER_FILE = DEFAULT_MAX_MERGED_RANGES_PER_FILE
MAX_EXCERPT_LINE_LENGTH = 65_536
MAX_MATCH_CONTEXT_LINES = 1_000
MAX_HEADER_LINES = 1_000
MAX_LINE_NUMBER = 10_000_000
MAX_SUPPLIED_MATCH_LOCATIONS = 64
MAX_SUPPLIED_RANGES = 64


class _RecordMapping(Mapping[str, Any]):
    def as_dict(self) -> dict[str, Any]:  # pragma: no cover - abstract helper
        raise NotImplementedError

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())


def _positive_bounded(value: Any, maximum: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    if not 1 <= value <= maximum:
        raise ValueError(f"{label} must be between 1 and {maximum}")
    return value


def _nonnegative_bounded(value: Any, maximum: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    if not 0 <= value <= maximum:
        raise ValueError(f"{label} must be between 0 and {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class DirectReadBudgets(_RecordMapping):
    max_files: int = DEFAULT_MAX_FILES
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES
    max_bytes_per_file: int = DEFAULT_MAX_BYTES_PER_FILE
    max_lines_per_file: int = DEFAULT_MAX_LINES_PER_FILE
    max_match_windows_per_file: int = DEFAULT_MAX_MATCH_WINDOWS_PER_FILE
    max_merged_ranges_per_file: int = DEFAULT_MAX_MERGED_RANGES_PER_FILE
    max_excerpt_line_length: int = DEFAULT_MAX_EXCERPT_LINE_LENGTH
    match_lines_before: int = DEFAULT_MATCH_LINES_BEFORE
    match_lines_after: int = DEFAULT_MATCH_LINES_AFTER
    header_lines: int = DEFAULT_HEADER_LINES

    def __post_init__(self) -> None:
        _positive_bounded(self.max_files, MAX_FILES, "max_files")
        _positive_bounded(
            self.max_total_bytes, MAX_TOTAL_BYTES, "max_total_bytes"
        )
        _positive_bounded(
            self.max_bytes_per_file,
            MAX_BYTES_PER_FILE,
            "max_bytes_per_file",
        )
        _positive_bounded(
            self.max_lines_per_file, MAX_LINES_PER_FILE, "max_lines_per_file"
        )
        _positive_bounded(
            self.max_match_windows_per_file,
            MAX_MATCH_WINDOWS_PER_FILE,
            "max_match_windows_per_file",
        )
        _positive_bounded(
            self.max_merged_ranges_per_file,
            MAX_MERGED_RANGES_PER_FILE,
            "max_merged_ranges_per_file",
        )
        _positive_bounded(
            self.max_excerpt_line_length,
            MAX_EXCERPT_LINE_LENGTH,
            "max_excerpt_line_length",
        )
        _nonnegative_bounded(
            self.match_lines_before,
            MAX_MATCH_CONTEXT_LINES,
            "match_lines_before",
        )
        _nonnegative_bounded(
            self.match_lines_after,
            MAX_MATCH_CONTEXT_LINES,
            "match_lines_after",
        )
        _positive_bounded(self.header_lines, MAX_HEADER_LINES, "header_lines")

    def as_dict(self) -> dict[str, int]:
        return {
            "max_files": self.max_files,
            "max_total_bytes": self.max_total_bytes,
            "max_bytes_per_file": self.max_bytes_per_file,
            "max_lines_per_file": self.max_lines_per_file,
            "max_match_windows_per_file": self.max_match_windows_per_file,
            "max_merged_ranges_per_file": self.max_merged_ranges_per_file,
            "max_excerpt_line_length": self.max_excerpt_line_length,
            "match_lines_before": self.match_lines_before,
            "match_lines_after": self.match_lines_after,
            "header_lines": self.header_lines,
        }


def coerce_direct_read_budgets(
    value: DirectReadBudgets | Mapping[str, Any] | None,
) -> DirectReadBudgets:
    if value is None:
        return DirectReadBudgets()
    if isinstance(value, DirectReadBudgets):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("budgets must be a mapping or DirectReadBudgets")
    allowed = set(DirectReadBudgets().as_dict())
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(
            "unknown direct-read budget fields: " + ", ".join(sorted(unknown))
        )
    return DirectReadBudgets(**{name: value[name] for name in value})


@dataclass(frozen=True, slots=True, order=True)
class DirectReadRange(_RecordMapping):
    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.start_line, bool)
            or isinstance(self.end_line, bool)
            or not isinstance(self.start_line, int)
            or not isinstance(self.end_line, int)
            or not 1 <= self.start_line <= MAX_LINE_NUMBER
            or not self.start_line <= self.end_line <= MAX_LINE_NUMBER
        ):
            raise ValueError("line ranges must be positive, bounded, and ordered")

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1

    def as_dict(self) -> dict[str, int]:
        return {"start_line": self.start_line, "end_line": self.end_line}


@dataclass(frozen=True, slots=True)
class ReadModeDecision(_RecordMapping):
    mode: str | None
    reason: str
    default_ranges: tuple[DirectReadRange, ...] = ()
    bounded: bool = True

    def __post_init__(self) -> None:
        if self.mode is not None and self.mode not in READ_MODES:
            raise ValueError("unknown direct-read mode decision")
        if not self.reason:
            raise ValueError("mode decisions require an explanation")
        if self.bounded is not True:
            raise ValueError("direct-read mode decisions must remain bounded")

    @property
    def accepted(self) -> bool:
        return self.mode is not None

    @property
    def read_mode(self) -> str | None:
        return self.mode

    def as_dict(self) -> dict[str, Any]:
        return {
            "read_mode": self.mode,
            "accepted": self.accepted,
            "reason": self.reason,
            "default_ranges": [item.as_dict() for item in self.default_ranges],
            "bounded": True,
            "read_authority_granted": False,
            "write_authority": False,
            "patch_authority": False,
        }


def _capability_value(capability: Any, name: str, default: Any = None) -> Any:
    if isinstance(capability, Mapping):
        return capability.get(name, default)
    return getattr(capability, name, default)


def choose_direct_read_mode(
    *,
    file_size: int | None,
    repository_tier: str,
    lexical_matches: Iterable[Any],
    capability: FileCapability | Mapping[str, Any],
    budgets: DirectReadBudgets | Mapping[str, Any] | None = None,
) -> ReadModeDecision:
    """Pure, deterministic, explainable default-mode selection."""

    limits = coerce_direct_read_budgets(budgets)
    captured_matches = tuple(
        islice(iter(lexical_matches), limits.max_match_windows_per_file + 1)
    )
    if not bool(_capability_value(capability, "direct_read_allowed", False)):
        return ReadModeDecision(
            None, "file capability does not permit automatic direct reading"
        )
    if _capability_value(capability, "read_policy") != "auto_read_allowed":
        return ReadModeDecision(None, "file read policy requires a stronger gate")
    if _capability_value(capability, "readability") != "readable_text":
        return ReadModeDecision(None, "file is not classified as readable text")
    if file_size is None:
        return ReadModeDecision(
            None,
            "unknown file size cannot receive an automatic unbounded read",
        )
    if isinstance(file_size, bool) or not isinstance(file_size, int) or file_size < 0:
        return ReadModeDecision(None, "file size evidence is invalid")
    available = min(limits.max_bytes_per_file, limits.max_total_bytes)
    tier = str(repository_tier).casefold()
    if file_size <= available:
        qualifier = (
            "single readable inventory member fits the operation budget"
            if tier in {"single", "single_file", "one_file"}
            else "safe readable file fits the complete-read budget"
        )
        return ReadModeDecision("full_file", qualifier)
    if captured_matches:
        return ReadModeDecision(
            "match_windows",
            "file exceeds the complete-read budget and has bounded lexical matches",
        )
    return ReadModeDecision(
        "explicit_ranges",
        "large unmatched file is limited to a small header pending stronger evidence",
        (DirectReadRange(1, min(limits.header_lines, limits.max_lines_per_file)),),
    )


def _coerce_range(value: Any) -> DirectReadRange:
    if isinstance(value, DirectReadRange):
        return value
    if isinstance(value, Mapping):
        start = value.get("start_line", value.get("start"))
        end = value.get("end_line", value.get("end"))
        return DirectReadRange(start, end)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if len(value) != 2:
            raise ValueError("line range pairs must contain exactly two values")
        return DirectReadRange(value[0], value[1])
    raise TypeError("line ranges must be mappings, pairs, or DirectReadRange values")


def _normalize_ranges_with_metadata(
    ranges: Iterable[Any],
    *,
    max_ranges: int,
    max_total_lines: int,
) -> tuple[tuple[DirectReadRange, ...], tuple[str, ...]]:
    if isinstance(ranges, (str, bytes, Mapping)):
        raise TypeError("ranges must be an iterable of range records")
    captured = tuple(islice(iter(ranges), MAX_SUPPLIED_RANGES + 1))
    reasons: set[str] = set()
    if len(captured) > MAX_SUPPLIED_RANGES:
        captured = captured[:MAX_SUPPLIED_RANGES]
        reasons.add("supplied_range_input_limit")
    materialized = sorted((_coerce_range(value) for value in captured))
    merged: list[DirectReadRange] = []
    for item in materialized:
        if merged and item.start_line <= merged[-1].end_line + 1:
            merged[-1] = DirectReadRange(
                merged[-1].start_line,
                max(merged[-1].end_line, item.end_line),
            )
        else:
            merged.append(item)
    if len(merged) > max_ranges:
        merged = merged[:max_ranges]
        reasons.add("merged_range_limit")

    bounded: list[DirectReadRange] = []
    remaining_lines = max_total_lines
    for item in merged:
        if remaining_lines <= 0:
            reasons.add("line_return_limit")
            break
        keep = min(item.line_count, remaining_lines)
        bounded.append(
            DirectReadRange(item.start_line, item.start_line + keep - 1)
        )
        remaining_lines -= keep
        if keep < item.line_count:
            reasons.add("line_return_limit")
            break
    return tuple(bounded), tuple(sorted(reasons))


def normalize_direct_read_ranges(
    ranges: Iterable[Any],
    *,
    max_ranges: int = DEFAULT_MAX_MERGED_RANGES_PER_FILE,
    max_total_lines: int = DEFAULT_MAX_LINES_PER_FILE,
) -> tuple[DirectReadRange, ...]:
    """Normalize trusted explicit ranges into sorted, merged bounded ranges."""

    range_limit = _positive_bounded(
        max_ranges, MAX_MERGED_RANGES_PER_FILE, "max_ranges"
    )
    line_limit = _positive_bounded(
        max_total_lines, MAX_LINES_PER_FILE, "max_total_lines"
    )
    normalized, _ = _normalize_ranges_with_metadata(
        ranges, max_ranges=range_limit, max_total_lines=line_limit
    )
    return normalized


def _match_line(value: Any) -> int:
    if isinstance(value, Mapping):
        line = value.get("line", value.get("line_number"))
    else:
        line = getattr(value, "line", getattr(value, "line_number", None))
    if (
        isinstance(line, bool)
        or not isinstance(line, int)
        or not 1 <= line <= MAX_LINE_NUMBER
    ):
        raise ValueError("match locations require a bounded positive line")
    return line


def _build_match_windows_with_metadata(
    match_locations: Iterable[Any],
    *,
    lines_before: int,
    lines_after: int,
    max_windows: int,
    max_ranges: int,
    max_total_lines: int,
) -> tuple[tuple[DirectReadRange, ...], tuple[str, ...]]:
    if isinstance(match_locations, (str, bytes, Mapping)):
        raise TypeError("match_locations must be an iterable of match records")
    captured = tuple(
        islice(iter(match_locations), MAX_SUPPLIED_MATCH_LOCATIONS + 1)
    )
    reasons: set[str] = set()
    if len(captured) > MAX_SUPPLIED_MATCH_LOCATIONS:
        captured = captured[:MAX_SUPPLIED_MATCH_LOCATIONS]
        reasons.add("supplied_match_input_limit")
    lines = sorted(set(_match_line(item) for item in captured))
    if len(lines) > max_windows:
        lines = lines[:max_windows]
        reasons.add("match_window_limit")
    raw_ranges = (
        DirectReadRange(max(1, line - lines_before), min(MAX_LINE_NUMBER, line + lines_after))
        for line in lines
    )
    normalized, range_reasons = _normalize_ranges_with_metadata(
        raw_ranges,
        max_ranges=max_ranges,
        max_total_lines=max_total_lines,
    )
    reasons.update(range_reasons)
    return normalized, tuple(sorted(reasons))


def build_match_windows(
    match_locations: Iterable[Any],
    *,
    lines_before: int = DEFAULT_MATCH_LINES_BEFORE,
    lines_after: int = DEFAULT_MATCH_LINES_AFTER,
    max_windows: int = DEFAULT_MAX_MATCH_WINDOWS_PER_FILE,
    max_ranges: int = DEFAULT_MAX_MERGED_RANGES_PER_FILE,
    max_total_lines: int = DEFAULT_MAX_LINES_PER_FILE,
) -> tuple[DirectReadRange, ...]:
    before = _nonnegative_bounded(
        lines_before, MAX_MATCH_CONTEXT_LINES, "lines_before"
    )
    after = _nonnegative_bounded(
        lines_after, MAX_MATCH_CONTEXT_LINES, "lines_after"
    )
    window_limit = _positive_bounded(
        max_windows, MAX_MATCH_WINDOWS_PER_FILE, "max_windows"
    )
    range_limit = _positive_bounded(
        max_ranges, MAX_MERGED_RANGES_PER_FILE, "max_ranges"
    )
    line_limit = _positive_bounded(
        max_total_lines, MAX_LINES_PER_FILE, "max_total_lines"
    )
    windows, _ = _build_match_windows_with_metadata(
        match_locations,
        lines_before=before,
        lines_after=after,
        max_windows=window_limit,
        max_ranges=range_limit,
        max_total_lines=line_limit,
    )
    return windows


@dataclass(frozen=True, slots=True)
class DirectFileReadResult(_RecordMapping):
    path: str
    read_status: str
    read_mode: str | None
    reason: str
    content: str | None
    receipt: DirectReadReceipt | None
    bytes_scanned: int = 0
    lines_scanned: int = 0
    truncated: bool = False
    truncation_reasons: tuple[str, ...] = ()
    approval_required: bool = False
    forbidden: bool = False
    recommendation: str | None = None

    def __post_init__(self) -> None:
        if self.read_status not in DIRECT_READ_OUTCOMES:
            raise ValueError(f"unknown direct-file read outcome: {self.read_status}")
        if self.read_mode is not None and self.read_mode not in READ_MODES:
            raise ValueError("unknown direct-file read mode")
        successful = self.receipt is not None
        if successful != (self.read_status in {"read_complete", "read_complete_with_truncation"}):
            raise ValueError("successful read status and receipt must agree")
        if successful and self.content is None:
            raise ValueError("successful reads must expose bounded content")
        if not successful and self.content is not None:
            raise ValueError("failed reads must not expose file content")
        if successful and (
            self.bytes_scanned != self.receipt.bytes_scanned
            or self.lines_scanned != self.receipt.lines_scanned
            or self.truncated != self.receipt.truncated
        ):
            raise ValueError("result and receipt counters must agree")
        if tuple(sorted(set(self.truncation_reasons))) != self.truncation_reasons:
            raise ValueError("truncation reasons must be deterministic")

    @property
    def read_authority_granted(self) -> bool:
        return self.receipt is not None

    @property
    def bytes_returned(self) -> int:
        return self.receipt.bytes_returned if self.receipt else 0

    @property
    def lines_returned(self) -> int:
        return self.receipt.lines_returned if self.receipt else 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "read_status": self.read_status,
            "read_mode": self.read_mode,
            "reason": self.reason,
            "content": self.content,
            "receipt": self.receipt.as_dict() if self.receipt else None,
            "bytes_scanned": self.bytes_scanned,
            "bytes_returned": self.bytes_returned,
            "lines_scanned": self.lines_scanned,
            "lines_returned": self.lines_returned,
            "truncated": self.truncated,
            "truncation_reasons": list(self.truncation_reasons),
            "approval_required": self.approval_required,
            "forbidden": self.forbidden,
            "recommendation": self.recommendation,
            "read_authority_granted": self.read_authority_granted,
            "read_authority": self.read_authority_granted,
            "write_authority": False,
            "patch_authority": False,
        }


@dataclass(frozen=True, slots=True)
class _DescriptorSnapshot:
    raw: bytes
    text: str | None
    lines: tuple[str, ...]
    bytes_scanned: int
    lines_scanned: int
    reached_eof: bool
    reached_requested_line: bool
    decoding: str
    binary: bool
    encoding_error: bool
    partial_utf8_sequence: bool
    scanned_sha256: str


def _scan_descriptor(
    stream: Any,
    *,
    expected_size: int,
    byte_limit: int,
    stop_after_line: int | None,
) -> _DescriptorSnapshot:
    """Read incrementally without issuing a read larger than remaining bytes."""

    raw_chunks: list[bytes] = []
    bytes_scanned = 0
    newline_chunks = 0
    while bytes_scanned < byte_limit:
        remaining = min(expected_size - bytes_scanned, byte_limit - bytes_scanned)
        if remaining <= 0:
            break
        raw = stream.readline(remaining)
        if not raw:
            break
        raw_chunks.append(raw)
        bytes_scanned += len(raw)
        newline_chunks += raw.count(b"\n")
        if stop_after_line is not None and newline_chunks >= stop_after_line:
            break

    raw_value = b"".join(raw_chunks)
    reached_eof = bytes_scanned == expected_size
    nul_binary = b"\x00" in raw_value
    sampled = len(raw_value)
    controls = sum(byte < 9 or 13 < byte < 32 for byte in raw_value)
    control_binary = sampled >= 32 and controls / sampled > 0.02
    digest = hashlib.sha256(raw_value).hexdigest()
    if nul_binary or control_binary:
        return _DescriptorSnapshot(
            raw_value,
            None,
            (),
            bytes_scanned,
            0,
            reached_eof,
            False,
            "utf8",
            True,
            False,
            False,
            digest,
        )

    has_bom = raw_value.startswith(codecs.BOM_UTF8)
    decoder = codecs.getincrementaldecoder("utf-8-sig" if has_bom else "utf-8")(
        errors="strict"
    )
    try:
        text = decoder.decode(raw_value, final=reached_eof)
    except UnicodeDecodeError:
        return _DescriptorSnapshot(
            raw_value,
            None,
            (),
            bytes_scanned,
            0,
            reached_eof,
            False,
            "utf8_bom" if has_bom else "utf8",
            False,
            True,
            False,
            digest,
        )
    buffered, _ = decoder.getstate()
    partial_utf8 = bool(buffered)
    lines = tuple(text.splitlines(keepends=True))
    if text and not lines:
        lines = (text,)
    reached_requested_line = (
        stop_after_line is None or len(lines) >= stop_after_line or reached_eof
    )
    return _DescriptorSnapshot(
        raw_value,
        text,
        lines,
        bytes_scanned,
        len(lines),
        reached_eof,
        reached_requested_line,
        "utf8_bom" if has_bom else "utf8",
        False,
        False,
        partial_utf8,
        digest,
    )


def _truncate_utf8(value: str, maximum: int) -> tuple[str, bool]:
    raw = value.encode("utf-8")
    if len(raw) <= maximum:
        return value, False
    return raw[:maximum].decode("utf-8", errors="ignore"), True


def _returned_range_receipts(
    returned_lines: Sequence[tuple[int, int]],
) -> tuple[DirectReadRangeReceipt, ...]:
    if not returned_lines:
        return ()
    receipts: list[DirectReadRangeReceipt] = []
    start = previous = returned_lines[0][0]
    bytes_in_range = returned_lines[0][1]
    for line, byte_count in returned_lines[1:]:
        if line == previous + 1:
            previous = line
            bytes_in_range += byte_count
            continue
        receipts.append(
            DirectReadRangeReceipt(
                start,
                previous,
                bytes_in_range,
                previous - start + 1,
            )
        )
        start = previous = line
        bytes_in_range = byte_count
    receipts.append(
        DirectReadRangeReceipt(
            start,
            previous,
            bytes_in_range,
            previous - start + 1,
        )
    )
    return tuple(receipts)


def failed_direct_file_read(
    path: str,
    status: str,
    reason: str,
    *,
    read_mode: str | None = None,
    bytes_scanned: int = 0,
    lines_scanned: int = 0,
    approval_required: bool = False,
    forbidden: bool = False,
    recommendation: str | None = None,
) -> DirectFileReadResult:
    """Build a no-content, no-authority stable file outcome."""

    return DirectFileReadResult(
        path=path,
        read_status=status,
        read_mode=read_mode,
        reason=reason,
        content=None,
        receipt=None,
        bytes_scanned=bytes_scanned,
        lines_scanned=lines_scanned,
        approval_required=approval_required,
        forbidden=forbidden,
        recommendation=recommendation,
    )


def _ranges_for_mode(
    mode: str,
    *,
    match_locations: Iterable[Any],
    explicit_ranges: Iterable[Any],
    budgets: DirectReadBudgets,
    default_ranges: tuple[DirectReadRange, ...],
) -> tuple[tuple[DirectReadRange, ...], tuple[str, ...]]:
    if mode == "full_file":
        return (), ()
    if mode in {"match_windows", "header_and_matches"}:
        match_ranges, reasons = _build_match_windows_with_metadata(
            match_locations,
            lines_before=budgets.match_lines_before,
            lines_after=budgets.match_lines_after,
            max_windows=budgets.max_match_windows_per_file,
            max_ranges=budgets.max_merged_ranges_per_file,
            max_total_lines=budgets.max_lines_per_file,
        )
        if mode == "header_and_matches":
            combined, combined_reasons = _normalize_ranges_with_metadata(
                (
                    DirectReadRange(1, budgets.header_lines),
                    *match_ranges,
                ),
                max_ranges=budgets.max_merged_ranges_per_file,
                max_total_lines=budgets.max_lines_per_file,
            )
            return combined, tuple(sorted(set(reasons) | set(combined_reasons)))
        return match_ranges, reasons
    supplied = tuple(explicit_ranges) or default_ranges
    return _normalize_ranges_with_metadata(
        supplied,
        max_ranges=budgets.max_merged_ranges_per_file,
        max_total_lines=budgets.max_lines_per_file,
    )


def execute_direct_file_read(
    repo_root: str | os.PathLike[str],
    entry: RepositoryEntry,
    *,
    capability: FileCapability | Mapping[str, Any],
    task_id: str,
    operation_id: str,
    inventory_identity: str,
    repository_tier: str,
    requested_mode: str | None = None,
    match_locations: Iterable[Any] = (),
    explicit_ranges: Iterable[Any] = (),
    budgets: DirectReadBudgets | Mapping[str, Any] | None = None,
    max_returned_bytes: int | None = None,
) -> DirectFileReadResult:
    """Read one trusted inventory entry through the descriptor-safe boundary."""

    limits = coerce_direct_read_budgets(budgets)
    path = entry.relative_path.as_posix()
    if not is_safe_repository_relative_path(path):
        return failed_direct_file_read(
            path, "path_outside_repository", "inventory path shape is unsafe"
        )
    try:
        root = Path(repo_root).expanduser().resolve(strict=True)
        candidate = root.joinpath(*PurePosixPath(path).parts)
        candidate.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return failed_direct_file_read(
            path,
            "path_outside_repository",
            "repository containment could not be established",
        )

    read_policy = _capability_value(capability, "read_policy")
    readability = _capability_value(capability, "readability")
    editability = _capability_value(capability, "editability")
    direct_allowed = bool(_capability_value(capability, "direct_read_allowed", False))
    if read_policy == "explicit_human_approval_required":
        return failed_direct_file_read(
            path,
            "sensitive_file_blocked",
            "file requires explicit human approval and was not opened",
            approval_required=True,
            recommendation="human_approval_required",
        )
    if read_policy == "hard_no_auto_read" or not direct_allowed:
        status = (
            "sensitive_file_blocked"
            if editability == "forbidden"
            else "binary_or_opaque"
            if readability in {"opaque_binary", "readable_limited", "unreadable"}
            else "sensitive_file_blocked"
        )
        return failed_direct_file_read(
            path,
            status,
            "file capability forbids automatic direct reading",
            forbidden=True,
        )
    if readability == "readable_limited":
        return failed_direct_file_read(
            path,
            "binary_or_opaque",
            "adapter-required document types are opaque to CTX.READ.1",
            forbidden=True,
        )
    if entry.file_identity is None:
        return failed_direct_file_read(
            path,
            "file_changed_or_replaced",
            "inventory entry has no descriptor-comparable identity",
        )

    captured_matches = tuple(
        islice(iter(match_locations), MAX_SUPPLIED_MATCH_LOCATIONS + 1)
    )
    captured_ranges = tuple(islice(iter(explicit_ranges), MAX_SUPPLIED_RANGES + 1))
    mode_decision = choose_direct_read_mode(
        file_size=entry.file_identity.size_bytes,
        repository_tier=repository_tier,
        lexical_matches=captured_matches,
        capability=capability,
        budgets=limits,
    )
    mode = requested_mode or mode_decision.mode
    if mode == "auto":
        mode = mode_decision.mode
    if mode not in READ_MODES:
        return failed_direct_file_read(
            path,
            "read_failed",
            "no valid bounded read mode was authorized",
            recommendation="request_additional_search",
        )
    try:
        ranges, range_reasons = _ranges_for_mode(
            mode,
            match_locations=captured_matches,
            explicit_ranges=captured_ranges,
            budgets=limits,
            default_ranges=mode_decision.default_ranges,
        )
    except (TypeError, ValueError) as exc:
        return failed_direct_file_read(
            path, "read_failed", f"invalid bounded ranges: {exc}", read_mode=mode
        )
    if mode in {"match_windows", "header_and_matches"} and not captured_matches:
        return failed_direct_file_read(
            path,
            "read_failed",
            "match-based mode requires trusted lexical match evidence",
            read_mode=mode,
            recommendation="request_additional_search",
        )
    if mode == "explicit_ranges" and not ranges:
        return failed_direct_file_read(
            path,
            "read_failed",
            "explicit-range mode requires at least one trusted bounded range",
            read_mode=mode,
            recommendation="request_more_candidates",
        )

    available_return = (
        limits.max_total_bytes
        if max_returned_bytes is None
        else max_returned_bytes
    )
    if (
        isinstance(available_return, bool)
        or not isinstance(available_return, int)
        or available_return <= 0
    ):
        return failed_direct_file_read(
            path,
            "budget_exhausted",
            "no total returned-content budget remains",
            read_mode=mode,
        )
    return_limit = min(limits.max_bytes_per_file, available_return)
    if mode == "full_file" and entry.file_identity.size_bytes > return_limit:
        return failed_direct_file_read(
            path,
            "budget_exhausted",
            "complete file does not fit the remaining returned-content budget",
            read_mode=mode,
        )

    try:
        current_path = os.lstat(candidate)
    except OSError:
        return failed_direct_file_read(
            path,
            "file_changed_or_replaced",
            "inventory path is no longer available",
            read_mode=mode,
        )
    if stat.S_ISLNK(current_path.st_mode):
        return failed_direct_file_read(
            path,
            "symlink_rejected",
            "direct reads reject symlink files even when the target is contained",
            read_mode=mode,
        )
    if not stat.S_ISREG(current_path.st_mode):
        return failed_direct_file_read(
            path,
            "read_failed",
            "direct reads require an unchanged regular file",
            read_mode=mode,
            forbidden=True,
        )

    try:
        stream = safe_open_inventory_entry(root, entry)
    except DescriptorFileChangedOrReplaced as exc:
        return failed_direct_file_read(
            path, "file_changed_or_replaced", str(exc), read_mode=mode
        )
    except (OSError, DescriptorFileOpenFailed):
        return failed_direct_file_read(
            path,
            "read_failed",
            "candidate descriptor could not be opened",
            read_mode=mode,
        )

    stop_after_line = None
    if mode == "full_file":
        stop_after_line = limits.max_lines_per_file
    elif ranges:
        stop_after_line = max(item.end_line for item in ranges)
    with stream:
        snapshot = _scan_descriptor(
            stream,
            expected_size=entry.file_identity.size_bytes,
            byte_limit=min(
                limits.max_bytes_per_file,
                entry.file_identity.size_bytes,
            ),
            stop_after_line=stop_after_line,
        )
        try:
            final_stat = os.fstat(stream.fileno())
            final_descriptor_matches = same_inventory_file_identity(
                entry.file_identity, final_stat
            )
        except OSError:
            final_descriptor_matches = False
            final_stat = None
    final_identity_matches = (
        final_descriptor_matches
        and current_path_matches_inventory(root, entry)
    )
    if not final_identity_matches or final_stat is None:
        return failed_direct_file_read(
            path,
            "file_changed_or_replaced",
            "descriptor or path identity changed during bounded read",
            read_mode=mode,
            bytes_scanned=snapshot.bytes_scanned,
            lines_scanned=snapshot.lines_scanned,
        )
    if snapshot.binary:
        return failed_direct_file_read(
            path,
            "binary_or_opaque",
            "descriptor content failed the bounded text safety check",
            read_mode=mode,
            bytes_scanned=snapshot.bytes_scanned,
        )
    if snapshot.encoding_error:
        return failed_direct_file_read(
            path,
            "encoding_unsupported",
            "descriptor content is not valid UTF-8",
            read_mode=mode,
            bytes_scanned=snapshot.bytes_scanned,
        )

    lines = snapshot.lines
    truncation_reasons = set(range_reasons)
    if snapshot.partial_utf8_sequence:
        truncation_reasons.add("partial_utf8_sequence_at_scan_limit")
    if mode == "full_file":
        effective_ranges = (
            (DirectReadRange(1, min(len(lines), limits.max_lines_per_file)),)
            if lines
            else ()
        )
        if not snapshot.reached_eof:
            if snapshot.lines_scanned >= limits.max_lines_per_file:
                truncation_reasons.add("line_return_limit")
            else:
                truncation_reasons.add("file_byte_limit")
    else:
        if not lines:
            if snapshot.reached_eof:
                return failed_direct_file_read(
                    path,
                    "read_failed",
                    "requested ranges are outside an empty file",
                    read_mode=mode,
                    bytes_scanned=snapshot.bytes_scanned,
                )
            return failed_direct_file_read(
                path,
                "budget_exhausted",
                "byte budget ended before the requested ranges were reached",
                read_mode=mode,
                bytes_scanned=snapshot.bytes_scanned,
            )
        effective: list[DirectReadRange] = []
        for item in ranges:
            if item.start_line > len(lines):
                if snapshot.reached_eof:
                    truncation_reasons.add("range_outside_file")
                else:
                    truncation_reasons.add("requested_range_unavailable")
                continue
            end = min(item.end_line, len(lines))
            effective.append(DirectReadRange(item.start_line, end))
            if end < item.end_line:
                truncation_reasons.add(
                    "range_end_clamped"
                    if snapshot.reached_eof
                    else "requested_range_unavailable"
                )
        effective_ranges = tuple(effective)
        if not effective_ranges:
            status = (
                "read_failed" if snapshot.reached_eof else "budget_exhausted"
            )
            return failed_direct_file_read(
                path,
                status,
                "no requested range was reachable within the bounded scan",
                read_mode=mode,
                bytes_scanned=snapshot.bytes_scanned,
                lines_scanned=snapshot.lines_scanned,
            )

    pieces: list[str] = []
    returned_lines: list[tuple[int, int]] = []
    remaining_return = return_limit
    for line_range in effective_ranges:
        for line_number in range(line_range.start_line, line_range.end_line + 1):
            if remaining_return <= 0:
                truncation_reasons.add("returned_byte_limit")
                break
            value = lines[line_number - 1]
            value, line_truncated = _truncate_utf8(
                value, limits.max_excerpt_line_length
            )
            if line_truncated:
                truncation_reasons.add("excerpt_line_length")
            value, budget_truncated = _truncate_utf8(value, remaining_return)
            if budget_truncated:
                truncation_reasons.add("returned_byte_limit")
            byte_count = len(value.encode("utf-8"))
            if byte_count == 0 and lines[line_number - 1]:
                truncation_reasons.add("returned_byte_limit")
                break
            pieces.append(value)
            returned_lines.append((line_number, byte_count))
            remaining_return -= byte_count
            if budget_truncated:
                break
        if remaining_return <= 0:
            break

    content = "".join(pieces)
    bytes_returned = len(content.encode("utf-8"))
    receipt_ranges = _returned_range_receipts(returned_lines)
    if effective_ranges and not receipt_ranges:
        return failed_direct_file_read(
            path,
            "budget_exhausted",
            "returned-content budget could not preserve a requested line",
            read_mode=mode,
            bytes_scanned=snapshot.bytes_scanned,
            lines_scanned=snapshot.lines_scanned,
        )

    full_digest = snapshot.scanned_sha256 if snapshot.reached_eof else None
    file_identity = DirectReadFileIdentity.from_stat_result(
        final_stat,
        content_sha256=full_digest,
        scanned_content_sha256=snapshot.scanned_sha256,
        content_digest_scope="full_file" if full_digest else "scanned_prefix",
    )
    ordered_reasons = tuple(sorted(truncation_reasons))
    truncated = bool(ordered_reasons)
    status = "read_complete_with_truncation" if truncated else "read_complete"
    receipt = DirectReadReceipt(
        task_id=task_id,
        operation_id=operation_id,
        inventory_identity=inventory_identity,
        path=path,
        read_status=status,
        read_mode=mode,
        file_identity=file_identity,
        ranges=receipt_ranges,
        bytes_scanned=snapshot.bytes_scanned,
        bytes_returned=bytes_returned,
        lines_scanned=snapshot.lines_scanned,
        lines_returned=len(returned_lines),
        truncated=truncated,
        truncation_reasons=ordered_reasons,
        decoding=snapshot.decoding,
        replacement_count=0,
        parser_support=str(_capability_value(capability, "parser_support", "unsupported")),
        # CTX.READ.1 never invokes a parser, even when parser support exists.
        understanding_confidence="raw_text_only",
    )
    return DirectFileReadResult(
        path=path,
        read_status=status,
        read_mode=mode,
        reason="bounded descriptor read completed",
        content=content,
        receipt=receipt,
        bytes_scanned=snapshot.bytes_scanned,
        lines_scanned=snapshot.lines_scanned,
        truncated=truncated,
        truncation_reasons=ordered_reasons,
    )


# Stable public aliases.
read_inventory_file = execute_direct_file_read
direct_file_read = execute_direct_file_read
