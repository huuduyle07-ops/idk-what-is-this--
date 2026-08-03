"""Safe, deterministic lexical search over one supplied repository inventory.

CTX.SEARCH.1 performs candidate discovery only.  It never walks repository
membership, builds an index, calls a model, touches a database, or writes a
file.  Content is read from validated descriptors in bounded byte chunks and
every emitted match explicitly denies direct-read and write authority.
"""

from __future__ import annotations

import codecs
import os
import re
import stat
from dataclasses import dataclass
from itertools import islice
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Mapping

from core.file_candidate_selector import (
    MAX_EXPANSION_ROUNDS,
    MAX_LEXICAL_EXCLUDE_PATHS,
    MAX_LEXICAL_FILES,
    MAX_LEXICAL_INCLUDE_PATHS,
    MAX_LEXICAL_MATCHES,
    MAX_LEXICAL_MATCH_LENGTH,
    MAX_LEXICAL_TERMS,
    LexicalSearchRequest,
)
from core.file_capabilities import (
    LIMITED_DOCUMENT_EXTENSIONS,
    FileCapability,
    classify_file_capability,
    classify_repository_path_read_policy,
)
from core.repository_inventory import (
    RepositoryEntry,
    RepositoryFileIdentity,
    RepositoryInventory,
    validate_repository_inventory,
)
from core.repository_path_policy import is_safe_repository_relative_path


EXECUTION_AUTHORITY = "candidate_discovery_only"
RESULT_SOURCE = "ctx_search_1"

SEARCH_OUTCOMES = (
    "search_complete",
    "search_complete_with_truncation",
    "no_matches",
    "invalid_request",
    "inventory_mismatch",
    "file_changed_or_replaced",
    "sensitive_file_excluded",
    "binary_file_excluded",
    "budget_exhausted",
    "search_failed",
)

MAX_MATCHES_PER_FILE = 20
DEFAULT_MAX_BYTES_SCANNED_PER_FILE = 1_048_576
MAX_BYTES_SCANNED_PER_FILE = 8_388_608
DEFAULT_MAX_TOTAL_BYTES_SCANNED = 8_388_608
MAX_TOTAL_BYTES_SCANNED = 67_108_864
DEFAULT_MAX_SINGLE_LINE_LENGTH = 16_384
MAX_SINGLE_LINE_LENGTH = 65_536
DEFAULT_MAX_FILES_CONSIDERED = 1_000
MAX_FILES_CONSIDERED = 4_096
MAX_FILE_OUTCOMES = 200
MAX_SEARCH_TERM_LENGTH = MAX_LEXICAL_MATCH_LENGTH
_READ_CHUNK_BYTES = 8_192


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
class SearchSafetyLimits(_RecordMapping):
    """Additional runtime-only caps, all constrained by hard maxima."""

    max_bytes_scanned_per_file: int = DEFAULT_MAX_BYTES_SCANNED_PER_FILE
    max_total_bytes_scanned: int = DEFAULT_MAX_TOTAL_BYTES_SCANNED
    max_matches_per_file: int = MAX_MATCHES_PER_FILE
    max_single_line_length: int = DEFAULT_MAX_SINGLE_LINE_LENGTH
    max_files_considered: int = DEFAULT_MAX_FILES_CONSIDERED

    def __post_init__(self) -> None:
        _bounded_positive_integer(
            self.max_bytes_scanned_per_file,
            MAX_BYTES_SCANNED_PER_FILE,
            "max_bytes_scanned_per_file",
        )
        _bounded_positive_integer(
            self.max_total_bytes_scanned,
            MAX_TOTAL_BYTES_SCANNED,
            "max_total_bytes_scanned",
        )
        _bounded_positive_integer(
            self.max_matches_per_file,
            MAX_MATCHES_PER_FILE,
            "max_matches_per_file",
        )
        _bounded_positive_integer(
            self.max_single_line_length,
            MAX_SINGLE_LINE_LENGTH,
            "max_single_line_length",
        )
        _bounded_positive_integer(
            self.max_files_considered,
            MAX_FILES_CONSIDERED,
            "max_files_considered",
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_bytes_scanned_per_file": self.max_bytes_scanned_per_file,
            "max_total_bytes_scanned": self.max_total_bytes_scanned,
            "max_matches_per_file": self.max_matches_per_file,
            "max_single_line_length": self.max_single_line_length,
            "max_files_considered": self.max_files_considered,
        }


@dataclass(frozen=True, slots=True)
class BoundedLexicalMatch(_RecordMapping):
    path: str
    line_number: int
    match_offset: int
    matched_term: str
    excerpt: str
    excerpt_truncated: bool
    whole_token: bool
    whole_token_boundary_complete: bool
    whole_token_preference: bool
    parser_support: str
    candidate_path_priority: int
    term_priority: int
    match_kind: str = "literal"
    file_understanding: str = "raw_text_only"

    def __post_init__(self) -> None:
        if self.match_kind != "literal":
            raise ValueError("CTX.SEARCH.1 only emits literal matches")
        if self.file_understanding != "raw_text_only":
            raise ValueError("lexical matches must remain raw-text evidence")
        if self.line_number <= 0 or self.match_offset < 0:
            raise ValueError("match locations must be non-negative and one-based by line")
        if len(self.excerpt) > MAX_LEXICAL_MATCH_LENGTH:
            raise ValueError("match excerpt exceeds the hard lexical bound")

    def ordering_key(self) -> tuple[Any, ...]:
        return (
            self.term_priority,
            self.candidate_path_priority,
            self.path,
            self.line_number,
            self.match_offset,
            self.matched_term,
        )

    def as_context_select_result(self) -> dict[str, Any]:
        """Return the existing CTX.SELECT.1 supplied-result shape."""

        return {
            "path": self.path,
            "line_number": self.line_number,
            "location": f"{self.line_number}:{self.match_offset + 1}",
            "match_offset": self.match_offset,
            "matched_term": self.matched_term,
            "match_kind": "literal",
            "whole_token": self.whole_token,
            "whole_token_boundary_complete": self.whole_token_boundary_complete,
            "whole_token_preference": self.whole_token_preference,
            "excerpt": self.excerpt,
            "excerpt_truncated": self.excerpt_truncated,
            "truncated": self.excerpt_truncated,
            "result_source": RESULT_SOURCE,
            "file_understanding": "raw_text_only",
            "execution_authority": EXECUTION_AUTHORITY,
            "read_authority": False,
            "write_authority": False,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.as_context_select_result(),
            "column_number": self.match_offset + 1,
            "parser_support": self.parser_support,
            "understanding": "raw_text_only",
            "term_priority": self.term_priority,
            "candidate_path_priority": self.candidate_path_priority,
        }


@dataclass(frozen=True, slots=True)
class FileSearchOutcome(_RecordMapping):
    path: str
    status: str
    reason: str
    bytes_scanned: int
    matches_returned: int
    truncated: bool
    truncation_reasons: tuple[str, ...]
    parser_support: str
    understanding: str = "unknown"

    def __post_init__(self) -> None:
        if self.status not in SEARCH_OUTCOMES:
            raise ValueError(f"unknown lexical file outcome: {self.status}")
        if self.bytes_scanned < 0 or self.matches_returned < 0:
            raise ValueError("file outcome counts must be non-negative")

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "status": self.status,
            "reason": self.reason,
            "bytes_scanned": self.bytes_scanned,
            "matches_returned": self.matches_returned,
            "truncated": self.truncated,
            "truncation_reasons": list(self.truncation_reasons),
            "parser_support": self.parser_support,
            "understanding": self.understanding,
            # File-level exclusions never echo file content.
            "excerpt": None,
            "execution_authority": EXECUTION_AUTHORITY,
            "read_authority": False,
            "write_authority": False,
        }


@dataclass(frozen=True, slots=True)
class LexicalSearchDiagnostics(_RecordMapping):
    status: str
    terms_requested: int
    files_considered: int
    files_scanned: int
    files_excluded: int
    bytes_scanned: int
    matches_returned: int
    matched_files: int
    truncated: bool
    truncation_reasons: tuple[str, ...]
    file_outcomes_total: int
    file_outcomes_returned: int
    inventory_entries_supplied: int
    inventory_membership_traversals: int = 0
    expansion_rounds_used: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "terms_requested": self.terms_requested,
            "files_considered": self.files_considered,
            "files_scanned": self.files_scanned,
            "files_excluded": self.files_excluded,
            "bytes_scanned": self.bytes_scanned,
            "matches_returned": self.matches_returned,
            "matched_files": self.matched_files,
            "truncated": self.truncated,
            "truncation_reasons": list(self.truncation_reasons),
            "file_outcomes_total": self.file_outcomes_total,
            "file_outcomes_returned": self.file_outcomes_returned,
            "inventory_entries_supplied": self.inventory_entries_supplied,
            "inventory_membership_traversals": 0,
            "inventory_reused": True,
            "expansion_rounds_used": self.expansion_rounds_used,
            "vector_database_used": False,
            "embeddings_used": False,
            "canonical_manifest_used": False,
            "canonical_index_used": False,
            "model_used": False,
            "api_calls_made": False,
            "database_operations": 0,
            "writes_performed": 0,
            "patch_authority_granted": False,
            "execution_authority": EXECUTION_AUTHORITY,
            "read_authority": False,
            "write_authority": False,
        }


@dataclass(frozen=True, slots=True)
class BoundedLexicalSearchResult(_RecordMapping):
    status: str
    matches: tuple[BoundedLexicalMatch, ...]
    file_outcomes: tuple[FileSearchOutcome, ...]
    diagnostics: LexicalSearchDiagnostics
    limits: SearchSafetyLimits
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in SEARCH_OUTCOMES:
            raise ValueError(f"unknown lexical search outcome: {self.status}")
        if self.status != self.diagnostics.status:
            raise ValueError("result and diagnostics status must agree")
        if self.matches != tuple(sorted(self.matches, key=lambda item: item.ordering_key())):
            raise ValueError("lexical matches must use deterministic priority ordering")

    @property
    def lexical_search(self) -> LexicalSearchDiagnostics:
        return self.diagnostics

    def context_select_results(self) -> tuple[dict[str, Any], ...]:
        return tuple(item.as_context_select_result() for item in self.matches)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "matches": [item.as_dict() for item in self.matches],
            "file_outcomes": [item.as_dict() for item in self.file_outcomes],
            "lexical_search": self.diagnostics.as_dict(),
            "limits": self.limits.as_dict(),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "execution_authority": EXECUTION_AUTHORITY,
            "read_authority": False,
            "write_authority": False,
        }


@dataclass(frozen=True, slots=True)
class _ValidatedRequest:
    terms: tuple[str, ...]
    include_paths: tuple[str, ...]
    exclude_paths: tuple[str, ...]
    max_matches: int
    max_files: int
    max_match_length: int
    max_expansion_rounds: int
    scope_mode: str
    case_sensitive: bool
    whole_token_preference: bool
    upstream_truncation_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ScannedFile:
    matches: tuple[BoundedLexicalMatch, ...]
    bytes_scanned: int
    binary: bool
    truncated: bool
    truncation_reasons: tuple[str, ...]
    error: str | None = None


class _InvalidRequest(ValueError):
    pass


class _FileChangedOrReplaced(RuntimeError):
    pass


class _FileOpenFailed(RuntimeError):
    pass


def _bounded_positive_integer(value: Any, maximum: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    if not 1 <= value <= maximum:
        raise ValueError(f"{label} must be between 1 and {maximum}")
    return value


def _bounded_nonnegative_integer(value: Any, maximum: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _InvalidRequest(f"{label} must be an integer")
    if not 0 <= value <= maximum:
        raise _InvalidRequest(f"{label} must be between 0 and {maximum}")
    return value


def _capture_bounded_values(value: Any, maximum: int, label: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or value is None:
        raise _InvalidRequest(f"{label} must be an iterable of values")
    try:
        captured = tuple(islice(iter(value), maximum + 1))
    except TypeError as exc:
        raise _InvalidRequest(f"{label} must be an iterable of values") from exc
    if len(captured) > maximum:
        raise _InvalidRequest(f"{label} exceeds the limit of {maximum}")
    return captured


def _normalize_scope_path(value: Any, *, label: str) -> str:
    if not isinstance(value, str):
        raise _InvalidRequest(f"{label} entries must be strings")
    wants_directory = value.endswith("/")
    core = value[:-1] if wants_directory else value
    if not is_safe_repository_relative_path(core):
        raise _InvalidRequest(f"{label} contains an unsafe repository-relative path")
    return core + ("/" if wants_directory else "")


def _request_field(request: LexicalSearchRequest | Mapping[str, Any], name: str, default: Any) -> Any:
    if isinstance(request, LexicalSearchRequest):
        return getattr(request, name, default)
    return request.get(name, default)


def _truncation_flag(request: LexicalSearchRequest | Mapping[str, Any], name: str) -> bool:
    value = _request_field(request, name, None)
    if hasattr(value, "truncated"):
        return bool(value.truncated)
    if isinstance(value, Mapping):
        return value.get("truncated") is True
    return False


def _validate_request(
    request: LexicalSearchRequest | Mapping[str, Any],
    *,
    case_sensitive: bool | None,
    whole_token_preference: bool | None,
) -> _ValidatedRequest:
    if not isinstance(request, (LexicalSearchRequest, Mapping)):
        raise _InvalidRequest("request must be a LexicalSearchRequest or mapping")

    raw_case = (
        _request_field(request, "case_sensitive", False)
        if case_sensitive is None
        else case_sensitive
    )
    raw_whole = (
        _request_field(request, "whole_token_preference", True)
        if whole_token_preference is None
        else whole_token_preference
    )
    if type(raw_case) is not bool:
        raise _InvalidRequest("case_sensitive must be a boolean")
    if type(raw_whole) is not bool:
        raise _InvalidRequest("whole_token_preference must be a boolean")

    supplied_terms = _capture_bounded_values(
        _request_field(request, "terms", ()),
        MAX_LEXICAL_TERMS,
        "terms",
    )
    if not supplied_terms:
        raise _InvalidRequest("at least one non-empty literal term is required")
    normalized_terms: list[str] = []
    seen_terms: set[str] = set()
    for term in supplied_terms:
        if not isinstance(term, str) or not term.strip():
            raise _InvalidRequest("terms must contain non-empty strings")
        if (
            len(term) > MAX_SEARCH_TERM_LENGTH
            or "\x00" in term
            or "\r" in term
            or "\n" in term
            or any(ord(char) < 32 and char != "\t" for char in term)
        ):
            raise _InvalidRequest(
                f"terms must be bounded literals of at most {MAX_SEARCH_TERM_LENGTH} characters"
            )
        key = term if raw_case else term.casefold()
        if key not in seen_terms:
            seen_terms.add(key)
            normalized_terms.append(term)

    raw_includes = _capture_bounded_values(
        _request_field(request, "include_paths", ()),
        MAX_LEXICAL_INCLUDE_PATHS,
        "include_paths",
    )
    raw_excludes = _capture_bounded_values(
        _request_field(request, "exclude_paths", ()),
        MAX_LEXICAL_EXCLUDE_PATHS,
        "exclude_paths",
    )
    includes = tuple(
        dict.fromkeys(
            _normalize_scope_path(value, label="include_paths")
            for value in raw_includes
        )
    )
    excludes = tuple(
        dict.fromkeys(
            _normalize_scope_path(value, label="exclude_paths")
            for value in raw_excludes
        )
    )
    for prefix in includes:
        policy, _ = classify_repository_path_read_policy(prefix.rstrip("/"))
        if policy != "auto_read_allowed":
            raise _InvalidRequest("include_paths contains a non-auto-readable scope")

    max_matches = _bounded_nonnegative_integer(
        _request_field(request, "max_matches", MAX_LEXICAL_MATCHES),
        MAX_LEXICAL_MATCHES,
        "max_matches",
    )
    if max_matches == 0:
        raise _InvalidRequest("max_matches must be positive")
    max_files = _bounded_nonnegative_integer(
        _request_field(request, "max_files", MAX_LEXICAL_FILES),
        MAX_LEXICAL_FILES,
        "max_files",
    )
    if max_files == 0:
        raise _InvalidRequest("max_files must be positive")
    max_match_length = _bounded_nonnegative_integer(
        _request_field(request, "max_match_length", MAX_LEXICAL_MATCH_LENGTH),
        MAX_LEXICAL_MATCH_LENGTH,
        "max_match_length",
    )
    if max_match_length == 0:
        raise _InvalidRequest("max_match_length must be positive")
    max_rounds = _bounded_nonnegative_integer(
        _request_field(request, "max_expansion_rounds", MAX_EXPANSION_ROUNDS),
        MAX_EXPANSION_ROUNDS,
        "max_expansion_rounds",
    )
    scope_mode = str(
        _request_field(
            request,
            "scope_mode",
            "explicit_paths" if includes else "safe_inventory",
        )
    )
    if scope_mode not in {"safe_inventory", "explicit_paths", "match_none"}:
        raise _InvalidRequest("scope_mode is invalid")
    if scope_mode == "explicit_paths" and not includes:
        raise _InvalidRequest("explicit_paths scope requires include_paths")
    if scope_mode == "safe_inventory" and includes:
        raise _InvalidRequest("safe_inventory scope cannot carry include_paths")
    if _request_field(request, "safe_inventory_filter_required", True) is not True:
        raise _InvalidRequest("safe inventory filtering must remain required")
    if _request_field(request, "production_execution_authorized", False) is not False:
        raise _InvalidRequest("CTX.SELECT cannot grant production execution authority")

    upstream_reasons = tuple(
        name.removesuffix("_truncation") + "_truncated_upstream"
        for name in (
            "terms_truncation",
            "include_paths_truncation",
            "exclude_paths_truncation",
        )
        if _truncation_flag(request, name)
    )
    return _ValidatedRequest(
        terms=tuple(normalized_terms),
        include_paths=includes,
        exclude_paths=excludes,
        max_matches=max_matches,
        max_files=max_files,
        max_match_length=max_match_length,
        max_expansion_rounds=max_rounds,
        scope_mode=scope_mode,
        case_sensitive=raw_case,
        whole_token_preference=raw_whole,
        upstream_truncation_reasons=upstream_reasons,
    )


def _under_prefix(path: str, prefix: str) -> bool:
    core = prefix.rstrip("/")
    return path == core or path.startswith(core + "/")


def _in_scope(path: str, request: _ValidatedRequest) -> bool:
    if request.scope_mode == "match_none":
        return False
    if any(_under_prefix(path, prefix) for prefix in request.exclude_paths):
        return False
    return not request.include_paths or any(
        _under_prefix(path, prefix) for prefix in request.include_paths
    )


def _candidate_priority(path: str, request: _ValidatedRequest) -> int:
    for index, prefix in enumerate(request.include_paths):
        if _under_prefix(path, prefix):
            return index
    return len(request.include_paths)


def _iter_scoped_inventory_entries(
    inventory: RepositoryInventory,
    request: _ValidatedRequest,
) -> Iterator[RepositoryEntry]:
    """Yield request-priority entries without copying or re-sorting inventory."""

    if not request.include_paths:
        for entry in inventory.entries:
            if _in_scope(entry.relative_path.as_posix(), request):
                yield entry
        return

    seen: set[str] = set()
    for prefix in request.include_paths:
        for entry in inventory.entries:
            path = entry.relative_path.as_posix()
            if path in seen or not _in_scope(path, request):
                continue
            if _under_prefix(path, prefix):
                seen.add(path)
                yield entry


def _entry_capability(entry: RepositoryEntry) -> FileCapability:
    size = entry.file_identity.size_bytes if entry.file_identity is not None else None
    # Unknown extensions are provisionally treated as text and then checked from
    # the bounded descriptor.  Known binary/document extensions still override
    # this hint inside classify_file_capability.
    return classify_file_capability(
        entry.relative_path.as_posix(),
        size_bytes=size,
        text_hint=True,
        is_binary=False,
        repository_contained=True,
        symlink_escape=False,
    )


def capability_records_for_search(
    inventory: RepositoryInventory,
    *,
    paths: Iterable[str] | None = None,
) -> tuple[FileCapability, ...]:
    """Adapt supplied inventory entries for CTX.SELECT without filesystem I/O."""

    if not isinstance(inventory, RepositoryInventory):
        raise TypeError("inventory must be a RepositoryInventory")
    if paths is None:
        selected_paths = None
    else:
        if isinstance(paths, (str, bytes)):
            raise TypeError("capability paths must be an iterable of paths")
        captured_paths = tuple(islice(iter(paths), MAX_LEXICAL_FILES + 1))
        if len(captured_paths) > MAX_LEXICAL_FILES:
            raise ValueError(
                f"capability path projection exceeds {MAX_LEXICAL_FILES} files"
            )
        selected_paths = frozenset(str(path) for path in captured_paths)
    return tuple(
        _entry_capability(entry)
        for entry in inventory.entries
        if selected_paths is None
        or entry.relative_path.as_posix() in selected_paths
    )


def _same_identity(
    expected: RepositoryFileIdentity | None,
    observed: os.stat_result,
) -> bool:
    if expected is None:
        return False
    actual = RepositoryFileIdentity.from_stat_result(observed)
    # Windows may settle ``st_ctime_ns`` immediately after a newly-created file
    # is closed, so change-time is retained diagnostically but is not a stable
    # descriptor identity field there.  Device/inode catches replacement while
    # size and modification time catch ordinary in-place content changes.
    return (
        actual.device == expected.device
        and actual.inode == expected.inode
        and actual.mode == expected.mode
        and actual.size_bytes == expected.size_bytes
        and actual.modified_ns == expected.modified_ns
        and (os.name == "nt" or actual.changed_ns == expected.changed_ns)
        and (
            os.name != "nt"
            or not expected.created_ns
            or actual.created_ns == expected.created_ns
        )
        and stat.S_ISREG(actual.mode)
    )


def _safe_open_candidate(root: Path, entry: RepositoryEntry):
    relative = entry.relative_path.as_posix()
    if not is_safe_repository_relative_path(relative):
        raise _FileChangedOrReplaced("unsafe inventory relative path")
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise _FileChangedOrReplaced(
            "symlink escape, missing file, or outside-root path"
        ) from exc
    if os.path.normcase(str(resolved)) != os.path.normcase(str(entry.absolute_path)):
        raise _FileChangedOrReplaced(
            "inventory path now resolves to a different file"
        )
    try:
        before_path = os.lstat(candidate)
    except OSError as exc:
        raise _FileChangedOrReplaced("inventory path is no longer available") from exc
    if stat.S_ISLNK(before_path.st_mode) or not _same_identity(
        entry.file_identity,
        before_path,
    ):
        raise _FileChangedOrReplaced(
            "lexical search requires an unchanged regular non-symlink path"
        )

    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(candidate, flags)
    except OSError as exc:
        raise _FileOpenFailed("candidate descriptor could not be opened") from exc
    try:
        opened = os.fstat(descriptor)
        if not _same_identity(entry.file_identity, opened):
            raise _FileChangedOrReplaced(
                "opened descriptor identity differs from inventory"
            )
        return os.fdopen(descriptor, "rb", buffering=0)
    except BaseException:
        os.close(descriptor)
        raise


def _current_path_matches_inventory(root: Path, entry: RepositoryEntry) -> bool:
    candidate = root.joinpath(*PurePosixPath(entry.relative_path.as_posix()).parts)
    try:
        current = os.lstat(candidate)
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return False
    return (
        not stat.S_ISLNK(current.st_mode)
        and os.path.normcase(str(resolved))
        == os.path.normcase(str(entry.absolute_path))
        and _same_identity(entry.file_identity, current)
    )


def _is_token_character(value: str) -> bool:
    return value == "_" or value.isalnum()


def _excerpt(
    text: str,
    start: int,
    end: int,
    *,
    maximum: int,
    prefix_missing: bool,
    suffix_missing: bool,
) -> tuple[str, bool]:
    cleaned = "".join(
        char if char == "\t" or char.isprintable() else "\ufffd"
        for char in text.replace("\r", "")
    )
    removed_before = len(text[:start]) - len(text[:start].replace("\r", ""))
    clean_start = max(0, start - removed_before)
    clean_end = min(len(cleaned), clean_start + (end - start))
    if len(cleaned) <= maximum:
        return cleaned, prefix_missing or suffix_missing
    left_context = max(0, (maximum - (clean_end - clean_start)) // 2)
    window_start = max(0, clean_start - left_context)
    window_end = min(len(cleaned), window_start + maximum)
    if window_end - window_start < maximum:
        window_start = max(0, window_end - maximum)
    return (
        cleaned[window_start:window_end],
        prefix_missing
        or suffix_missing
        or window_start > 0
        or window_end < len(cleaned),
    )


def _scan_descriptor(
    stream: Any,
    *,
    path: str,
    parser_support: str,
    candidate_priority: int,
    request: _ValidatedRequest,
    byte_limit: int,
    match_limit: int,
    max_single_line_length: int,
) -> _ScannedFile:
    flags = 0 if request.case_sensitive else re.IGNORECASE
    patterns = tuple(
        (index, term, re.compile(re.escape(term), flags))
        for index, term in enumerate(request.terms)
    )
    max_term_length = max(len(term) for term in request.terms)
    overlap_limit = max(0, max_term_length - 1)
    decoder = codecs.getincrementaldecoder("utf-8-sig")("strict")
    matches: dict[tuple[int, int, int, str], BoundedLexicalMatch] = {}
    bytes_scanned = 0
    control_bytes = 0
    sampled_bytes = 0
    line_number = 1
    line_characters_seen = 0
    tail = ""
    line_streamed = False
    reached_eof = False
    match_limit_hit = False

    def process_piece(piece: str, *, line_ended: bool) -> bool:
        nonlocal line_number, line_characters_seen, tail, line_streamed
        combined = tail + piece
        combined_start = line_characters_seen - len(tail)
        previous_end = line_characters_seen
        prefix_missing = combined_start > 0
        suffix_missing = not line_ended
        for term_priority, term, pattern in patterns:
            for found in pattern.finditer(combined):
                absolute_offset = combined_start + found.start()
                absolute_end = combined_start + found.end()
                if absolute_end <= previous_end:
                    continue
                key = (line_number, absolute_offset, term_priority, term)
                if key in matches:
                    continue
                left_complete = found.start() > 0 or absolute_offset == 0
                right_complete = found.end() < len(combined) or line_ended
                left_ok = (
                    absolute_offset == 0
                    or (found.start() > 0 and not _is_token_character(combined[found.start() - 1]))
                )
                right_ok = (
                    line_ended and found.end() == len(combined)
                    or found.end() < len(combined)
                    and not _is_token_character(combined[found.end()])
                )
                excerpt, excerpt_truncated = _excerpt(
                    combined,
                    found.start(),
                    found.end(),
                    maximum=request.max_match_length,
                    prefix_missing=prefix_missing,
                    suffix_missing=suffix_missing,
                )
                matches[key] = BoundedLexicalMatch(
                    path=path,
                    line_number=line_number,
                    match_offset=absolute_offset,
                    matched_term=term,
                    excerpt=excerpt,
                    excerpt_truncated=excerpt_truncated,
                    whole_token=left_ok and right_ok and left_complete and right_complete,
                    whole_token_boundary_complete=left_complete and right_complete,
                    whole_token_preference=request.whole_token_preference,
                    parser_support=parser_support,
                    candidate_path_priority=candidate_priority,
                    term_priority=term_priority,
                )
                if len(matches) >= match_limit:
                    return True

        line_characters_seen += len(piece)
        if line_ended:
            line_number += 1
            line_characters_seen = 0
            tail = ""
            line_streamed = False
        else:
            tail = combined[-overlap_limit:] if overlap_limit else ""
            line_streamed = line_streamed or len(piece) >= max_single_line_length
        return False

    def process_text(text: str) -> bool:
        pieces = text.split("\n")
        for index, piece in enumerate(pieces):
            if process_piece(piece, line_ended=index < len(pieces) - 1):
                return True
        return False

    try:
        while bytes_scanned < byte_limit:
            chunk_size = min(
                _READ_CHUNK_BYTES,
                max_single_line_length,
                byte_limit - bytes_scanned,
            )
            raw = stream.read(chunk_size)
            if not raw:
                reached_eof = True
                break
            bytes_scanned += len(raw)
            sampled_bytes += len(raw)
            if b"\x00" in raw:
                return _ScannedFile((), bytes_scanned, True, False, ())
            control_bytes += sum(
                byte < 9 or 13 < byte < 32
                for byte in raw
            )
            try:
                decoded = decoder.decode(raw, final=False)
            except UnicodeDecodeError:
                return _ScannedFile((), bytes_scanned, True, False, ())
            if process_text(decoded):
                match_limit_hit = True
                break

        if reached_eof and not match_limit_hit:
            try:
                final_text = decoder.decode(b"", final=True)
            except UnicodeDecodeError:
                return _ScannedFile((), bytes_scanned, True, False, ())
            if final_text and process_text(final_text):
                match_limit_hit = True
    except OSError as exc:
        return _ScannedFile((), bytes_scanned, False, False, (), str(exc))

    if sampled_bytes >= 32 and control_bytes / sampled_bytes > 0.02:
        return _ScannedFile((), bytes_scanned, True, False, ())
    reasons: set[str] = set()
    if match_limit_hit:
        reasons.add("match_limit")
    if not reached_eof and not match_limit_hit:
        reasons.add("file_byte_limit")
    ordered = tuple(sorted(matches.values(), key=lambda item: item.ordering_key()))
    return _ScannedFile(
        ordered,
        bytes_scanned,
        False,
        bool(reasons),
        tuple(sorted(reasons)),
    )


def _failure_result(
    status: str,
    *,
    error: str,
    limits: SearchSafetyLimits,
    terms_requested: int = 0,
    inventory_entries: int = 0,
) -> BoundedLexicalSearchResult:
    diagnostics = LexicalSearchDiagnostics(
        status=status,
        terms_requested=terms_requested,
        files_considered=0,
        files_scanned=0,
        files_excluded=0,
        bytes_scanned=0,
        matches_returned=0,
        matched_files=0,
        truncated=False,
        truncation_reasons=(),
        file_outcomes_total=0,
        file_outcomes_returned=0,
        inventory_entries_supplied=inventory_entries,
    )
    return BoundedLexicalSearchResult(
        status=status,
        matches=(),
        file_outcomes=(),
        diagnostics=diagnostics,
        limits=limits,
        errors=(error,),
    )


def execute_bounded_lexical_search(
    repo_root: str | os.PathLike[str],
    inventory: RepositoryInventory,
    request: LexicalSearchRequest | Mapping[str, Any],
    *,
    case_sensitive: bool | None = None,
    whole_token_preference: bool | None = None,
    allow_generated: bool = False,
    max_bytes_scanned_per_file: int = DEFAULT_MAX_BYTES_SCANNED_PER_FILE,
    max_total_bytes_scanned: int = DEFAULT_MAX_TOTAL_BYTES_SCANNED,
    max_matches_per_file: int = MAX_MATCHES_PER_FILE,
    max_single_line_length: int = DEFAULT_MAX_SINGLE_LINE_LENGTH,
    max_files_considered: int = DEFAULT_MAX_FILES_CONSIDERED,
) -> BoundedLexicalSearchResult:
    """Execute one bounded literal search without rediscovering membership."""

    try:
        limits = SearchSafetyLimits(
            max_bytes_scanned_per_file=max_bytes_scanned_per_file,
            max_total_bytes_scanned=max_total_bytes_scanned,
            max_matches_per_file=max_matches_per_file,
            max_single_line_length=max_single_line_length,
            max_files_considered=max_files_considered,
        )
    except (TypeError, ValueError) as exc:
        fallback_limits = SearchSafetyLimits()
        return _failure_result("invalid_request", error=str(exc), limits=fallback_limits)
    if type(allow_generated) is not bool:
        return _failure_result(
            "invalid_request",
            error="allow_generated must be a boolean",
            limits=limits,
        )
    try:
        validated_request = _validate_request(
            request,
            case_sensitive=case_sensitive,
            whole_token_preference=whole_token_preference,
        )
    except (TypeError, ValueError) as exc:
        return _failure_result("invalid_request", error=str(exc), limits=limits)

    inventory_count = len(inventory.entries) if isinstance(inventory, RepositoryInventory) else 0
    try:
        root = Path(repo_root).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise NotADirectoryError("repository root is not a directory")
        validated_inventory = validate_repository_inventory(root, inventory)
    except (OSError, TypeError, ValueError):
        return _failure_result(
            "inventory_mismatch",
            error="repository root or supplied inventory failed validation",
            limits=limits,
            terms_requested=len(validated_request.terms),
            inventory_entries=inventory_count,
        )

    if validated_request.scope_mode == "match_none":
        diagnostics = LexicalSearchDiagnostics(
            status="no_matches",
            terms_requested=len(validated_request.terms),
            files_considered=0,
            files_scanned=0,
            files_excluded=0,
            bytes_scanned=0,
            matches_returned=0,
            matched_files=0,
            truncated=bool(validated_request.upstream_truncation_reasons),
            truncation_reasons=validated_request.upstream_truncation_reasons,
            file_outcomes_total=0,
            file_outcomes_returned=0,
            inventory_entries_supplied=len(validated_inventory.entries),
        )
        return BoundedLexicalSearchResult(
            status="no_matches",
            matches=(),
            file_outcomes=(),
            diagnostics=diagnostics,
            limits=limits,
        )

    scoped_entries = iter(
        _iter_scoped_inventory_entries(
            validated_inventory,
            validated_request,
        )
    )
    matches: dict[tuple[Any, ...], BoundedLexicalMatch] = {}
    outcomes: list[FileSearchOutcome] = []
    outcome_total = 0
    files_considered = 0
    files_scanned = 0
    files_excluded = 0
    bytes_scanned = 0
    matched_paths: set[str] = set()
    truncation_reasons: set[str] = set(validated_request.upstream_truncation_reasons)
    errors: set[str] = set()
    budget_exhausted = False

    def record_outcome(outcome: FileSearchOutcome) -> None:
        nonlocal outcome_total
        outcome_total += 1
        if len(outcomes) < MAX_FILE_OUTCOMES:
            outcomes.append(outcome)
        else:
            truncation_reasons.add("file_outcomes_limit")

    for entry in scoped_entries:
        if files_considered >= limits.max_files_considered:
            truncation_reasons.add("files_considered_limit")
            break
        if bytes_scanned >= limits.max_total_bytes_scanned:
            truncation_reasons.add("total_byte_limit")
            budget_exhausted = True
            break
        if len(matches) >= validated_request.max_matches:
            truncation_reasons.add("global_match_limit")
            break
        if len(matched_paths) >= validated_request.max_files:
            truncation_reasons.add("matched_file_limit")
            break

        path = entry.relative_path.as_posix()
        files_considered += 1
        capability = _entry_capability(entry)
        path_read_policy, _ = classify_repository_path_read_policy(path)
        sensitive = (
            path_read_policy != "auto_read_allowed"
            or capability.readability == "sensitive"
            or not capability.repository_contained
            or capability.symlink_escape
        )
        generated_excluded = (capability.generated and not allow_generated) or capability.vendor
        known_binary = (
            capability.readability in {"opaque_binary", "readable_limited"}
            or entry.relative_path.suffix.casefold() in LIMITED_DOCUMENT_EXTENSIONS
        )
        if sensitive or generated_excluded:
            files_excluded += 1
            reason = (
                "generated files require explicit search-only permission"
                if capability.generated and not allow_generated
                else "vendor files are excluded by lexical-search policy"
                if capability.vendor
                else "sensitive or non-auto-readable file policy"
            )
            record_outcome(
                FileSearchOutcome(
                    path,
                    "sensitive_file_excluded",
                    reason,
                    0,
                    0,
                    False,
                    (),
                    capability.parser_support,
                )
            )
            continue
        if known_binary:
            files_excluded += 1
            record_outcome(
                FileSearchOutcome(
                    path,
                    "binary_file_excluded",
                    "known opaque or adapter-required file type",
                    0,
                    0,
                    False,
                    (),
                    capability.parser_support,
                )
            )
            continue
        if entry.file_identity is None:
            files_excluded += 1
            record_outcome(
                FileSearchOutcome(
                    path,
                    "inventory_mismatch",
                    "inventory entry has no descriptor-comparable identity",
                    0,
                    0,
                    False,
                    (),
                    capability.parser_support,
                )
            )
            continue

        try:
            stream = _safe_open_candidate(root, entry)
        except _FileChangedOrReplaced as exc:
            files_excluded += 1
            record_outcome(
                FileSearchOutcome(
                    path,
                    "file_changed_or_replaced",
                    str(exc),
                    0,
                    0,
                    False,
                    (),
                    capability.parser_support,
                )
            )
            continue
        except (OSError, _FileOpenFailed):
            files_excluded += 1
            errors.add(f"{path}: candidate descriptor could not be opened")
            record_outcome(
                FileSearchOutcome(
                    path,
                    "search_failed",
                    "candidate descriptor could not be opened",
                    0,
                    0,
                    False,
                    (),
                    capability.parser_support,
                )
            )
            continue

        available_bytes = limits.max_total_bytes_scanned - bytes_scanned
        file_byte_limit = min(limits.max_bytes_scanned_per_file, available_bytes)
        global_remaining_matches = validated_request.max_matches - len(matches)
        file_match_limit = min(limits.max_matches_per_file, global_remaining_matches)
        with stream:
            scanned = _scan_descriptor(
                stream,
                path=path,
                parser_support=capability.parser_support,
                candidate_priority=_candidate_priority(path, validated_request),
                request=validated_request,
                byte_limit=file_byte_limit,
                match_limit=file_match_limit,
                max_single_line_length=limits.max_single_line_length,
            )
            try:
                final_identity_matches = _same_identity(
                    entry.file_identity,
                    os.fstat(stream.fileno()),
                )
            except OSError:
                final_identity_matches = False
        final_identity_matches = final_identity_matches and _current_path_matches_inventory(
            root,
            entry,
        )

        files_scanned += 1
        bytes_scanned += scanned.bytes_scanned
        if not final_identity_matches:
            files_excluded += 1
            record_outcome(
                FileSearchOutcome(
                    path,
                    "file_changed_or_replaced",
                    "descriptor identity changed during bounded scan",
                    scanned.bytes_scanned,
                    0,
                    False,
                    (),
                    capability.parser_support,
                )
            )
            continue
        if scanned.error is not None:
            files_excluded += 1
            errors.add(f"{path}: bounded descriptor read failed")
            record_outcome(
                FileSearchOutcome(
                    path,
                    "search_failed",
                    "bounded descriptor read failed",
                    scanned.bytes_scanned,
                    0,
                    False,
                    (),
                    capability.parser_support,
                )
            )
            continue
        if scanned.binary:
            files_excluded += 1
            record_outcome(
                FileSearchOutcome(
                    path,
                    "binary_file_excluded",
                    "descriptor content failed the bounded UTF-8 text check",
                    scanned.bytes_scanned,
                    0,
                    False,
                    (),
                    "not_applicable",
                )
            )
            continue

        before_count = len(matches)
        for match in scanned.matches:
            key = (
                match.path,
                match.line_number,
                match.match_offset,
                match.matched_term if validated_request.case_sensitive else match.matched_term.casefold(),
            )
            matches.setdefault(key, match)
        returned_here = len(matches) - before_count
        if returned_here:
            matched_paths.add(path)
        file_reasons = set(scanned.truncation_reasons)
        if (
            "file_byte_limit" in file_reasons
            and entry.file_identity.size_bytes <= scanned.bytes_scanned
        ):
            file_reasons.remove("file_byte_limit")
        if "match_limit" in file_reasons:
            if file_match_limit == global_remaining_matches:
                file_reasons.remove("match_limit")
                file_reasons.add("global_match_limit")
                truncation_reasons.add("global_match_limit")
            else:
                file_reasons.remove("match_limit")
                file_reasons.add("per_file_match_limit")
                truncation_reasons.add("per_file_match_limit")
        if "file_byte_limit" in file_reasons:
            if file_byte_limit == available_bytes < limits.max_bytes_scanned_per_file:
                file_reasons.remove("file_byte_limit")
                file_reasons.add("total_byte_limit")
                truncation_reasons.add("total_byte_limit")
                budget_exhausted = True
            else:
                truncation_reasons.add("file_byte_limit")
        file_truncated = bool(file_reasons)
        record_outcome(
            FileSearchOutcome(
                path,
                "search_complete_with_truncation"
                if file_truncated
                else "search_complete"
                if returned_here
                else "no_matches",
                "bounded literal scan completed",
                scanned.bytes_scanned,
                returned_here,
                file_truncated,
                tuple(sorted(file_reasons)),
                capability.parser_support,
                "raw_text_only",
            )
        )

        if len(matches) >= validated_request.max_matches:
            truncation_reasons.add("global_match_limit")
            break
        if len(matched_paths) >= validated_request.max_files:
            sentinel = object()
            if next(scoped_entries, sentinel) is not sentinel:
                truncation_reasons.add("matched_file_limit")
            break
        if budget_exhausted:
            break

    ordered_matches = tuple(sorted(matches.values(), key=lambda item: item.ordering_key()))
    truncated = bool(truncation_reasons)
    if budget_exhausted:
        status = "budget_exhausted"
    elif ordered_matches:
        status = "search_complete_with_truncation" if truncated else "search_complete"
    elif files_scanned and any(item.status == "no_matches" for item in outcomes):
        status = "no_matches"
    else:
        statuses = {item.status for item in outcomes}
        status = (
            next(
                candidate
                for candidate in (
                    "file_changed_or_replaced",
                    "inventory_mismatch",
                    "sensitive_file_excluded",
                    "binary_file_excluded",
                    "search_failed",
                )
                if candidate in statuses
            )
            if statuses
            else "no_matches"
        )
    diagnostics = LexicalSearchDiagnostics(
        status=status,
        terms_requested=len(validated_request.terms),
        files_considered=files_considered,
        files_scanned=files_scanned,
        files_excluded=files_excluded,
        bytes_scanned=bytes_scanned,
        matches_returned=len(ordered_matches),
        matched_files=len(matched_paths),
        truncated=truncated,
        truncation_reasons=tuple(sorted(truncation_reasons)),
        file_outcomes_total=outcome_total,
        file_outcomes_returned=len(outcomes),
        inventory_entries_supplied=len(validated_inventory.entries),
    )
    warnings = (
        ("generated files were permitted for search-only evidence",)
        if allow_generated
        else ()
    )
    return BoundedLexicalSearchResult(
        status=status,
        matches=ordered_matches,
        file_outcomes=tuple(outcomes),
        diagnostics=diagnostics,
        limits=limits,
        errors=tuple(sorted(errors)),
        warnings=warnings,
    )


# Stable public aliases for callers that prefer a shorter verb.
bounded_lexical_search = execute_bounded_lexical_search
search_inventory = execute_bounded_lexical_search

# CTX.READ.1 reuses this exact descriptor boundary instead of introducing a
# second path/identity policy.  The implementation names remain private so the
# search module can keep its internal call sites compact; these aliases are the
# supported cross-runtime seam.
DescriptorFileChangedOrReplaced = _FileChangedOrReplaced
DescriptorFileOpenFailed = _FileOpenFailed
same_inventory_file_identity = _same_identity
safe_open_inventory_entry = _safe_open_candidate
current_path_matches_inventory = _current_path_matches_inventory
