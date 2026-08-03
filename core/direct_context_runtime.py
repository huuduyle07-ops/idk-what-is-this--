"""Task-local orchestration for the CTX.READ.1 direct-file context runtime.

The runtime accepts a supplied immutable inventory and separate CTX.SELECT
proposed-read evidence.  It never discovers repository members, expands the
read set, invokes search, indexing, graphs, databases, parsers, models, APIs,
or patch machinery.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from core.context_selection import ProposedReadSet
from core.direct_file_reader import (
    MAX_FILES,
    MAX_LINE_NUMBER,
    MAX_SUPPLIED_MATCH_LOCATIONS,
    MAX_SUPPLIED_RANGES,
    READ_MODES,
    DirectReadRange,
    DirectFileReadResult,
    DirectReadBudgets,
    coerce_direct_read_budgets,
    execute_direct_file_read,
    failed_direct_file_read,
)
from core.direct_read_receipt import DirectReadReceipt
from core.file_capabilities import FileCapability, classify_file_capability
from core.repository_inventory import (
    RepositoryEntry,
    RepositoryInventory,
    validate_repository_inventory,
)
from core.repository_path_policy import is_safe_repository_relative_path


PHASE_ID = "CTX.READ.1"
DIRECT_READ_SCHEMA_VERSION = 1
OPERATION_OUTCOMES = (
    "operation_complete",
    "operation_complete_with_partial_reads",
    "operation_blocked",
)
MAX_WARNINGS = 64
MAX_ERRORS = 32
MAX_SEARCH_EVIDENCE = 200
MAX_TASK_ID_LENGTH = 200
MAX_OPERATION_ID_LENGTH = 240


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
class OmittedDirectRead(_RecordMapping):
    path: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "reason": self.reason,
            "content": None,
            "read_authority_granted": False,
            "write_authority": False,
            "patch_authority": False,
        }


@dataclass(frozen=True, slots=True)
class DirectFileContext(_RecordMapping):
    """Ephemeral task context containing bounded content and read receipts."""

    operation_status: str
    task_id: str
    operation_id: str
    repository_root: str
    inventory_identity: str
    files_requested: int
    file_results: tuple[DirectFileReadResult, ...]
    read_receipts: tuple[DirectReadReceipt, ...]
    omitted_files: tuple[OmittedDirectRead, ...]
    total_bytes_scanned: int
    total_bytes_returned: int
    total_lines_scanned: int
    total_lines_returned: int
    budget_remaining: int
    budgets: DirectReadBudgets
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()
    evidence_records: tuple[Mapping[str, Any], ...] = ()
    canonical_identity_state: str = "unconfirmed"

    def __post_init__(self) -> None:
        if self.operation_status not in OPERATION_OUTCOMES:
            raise ValueError("unknown direct-context operation status")
        if not self.task_id or not self.operation_id:
            raise ValueError("direct context must remain task and operation scoped")
        if not 0 <= self.files_requested <= MAX_FILES:
            raise ValueError("files_requested exceeds the hard context bound")
        if len(self.file_results) != self.files_requested:
            raise ValueError("every requested file requires one bounded outcome")
        expected_receipts = tuple(
            result.receipt for result in self.file_results if result.receipt is not None
        )
        if self.read_receipts != expected_receipts:
            raise ValueError("context receipts must exactly match successful reads")
        if self.total_bytes_scanned != sum(
            result.bytes_scanned for result in self.file_results
        ):
            raise ValueError("context scanned-byte counter is inaccurate")
        if self.total_bytes_returned != sum(
            result.bytes_returned for result in self.file_results
        ):
            raise ValueError("context returned-byte counter is inaccurate")
        if self.total_lines_scanned != sum(
            result.lines_scanned for result in self.file_results
        ):
            raise ValueError("context scanned-line counter is inaccurate")
        if self.total_lines_returned != sum(
            result.lines_returned for result in self.file_results
        ):
            raise ValueError("context returned-line counter is inaccurate")
        if self.total_bytes_returned > self.budgets.max_total_bytes:
            raise ValueError("context exceeds its returned-content byte budget")
        if self.budget_remaining != (
            self.budgets.max_total_bytes - self.total_bytes_returned
        ):
            raise ValueError("context budget_remaining is inaccurate")
        if tuple(sorted(set(self.warnings))) != self.warnings:
            raise ValueError("context warnings must be unique and deterministic")
        if tuple(sorted(set(self.errors))) != self.errors:
            raise ValueError("context errors must be unique and deterministic")
        if tuple(sorted(set(self.recommendations))) != self.recommendations:
            raise ValueError("context recommendations must be deterministic")

    @property
    def status(self) -> str:
        return self.operation_status

    @property
    def files_read(self) -> int:
        return len(self.read_receipts)

    @property
    def files_blocked(self) -> int:
        return self.files_requested - self.files_read

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase_id": PHASE_ID,
            "operation_status": self.operation_status,
            "status": self.operation_status,
            "context_kind": "direct_file_context",
            "task_id": self.task_id,
            "operation_id": self.operation_id,
            "repository_root": self.repository_root,
            "inventory_identity": self.inventory_identity,
            "repository_completeness_claimed": False,
            "canonical_index_used": False,
            "canonical_manifest_used": False,
            "vector_database_used": False,
            "embeddings_used": False,
            "activation_graph_used": False,
            "parser_used": False,
            "model_used": False,
            "api_calls_made": False,
            "database_operations": 0,
            "repository_membership_traversals": 0,
            "additional_searches_performed": 0,
            "writes_performed": 0,
            "patches_applied": 0,
            "files_requested": self.files_requested,
            "files_read": self.files_read,
            "files_blocked": self.files_blocked,
            "total_bytes_scanned": self.total_bytes_scanned,
            "total_bytes_returned": self.total_bytes_returned,
            "total_lines_scanned": self.total_lines_scanned,
            "total_lines_returned": self.total_lines_returned,
            "budget_remaining": self.budget_remaining,
            "budgets": self.budgets.as_dict(),
            "file_results": [item.as_dict() for item in self.file_results],
            "read_receipts": [item.as_dict() for item in self.read_receipts],
            "omitted_files": [item.as_dict() for item in self.omitted_files],
            "evidence_records": [dict(item) for item in self.evidence_records],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "recommendations": list(self.recommendations),
            "canonical_identity_state": self.canonical_identity_state,
            "canonical_identity_required": False,
            "ephemeral": True,
            "persisted": False,
            "read_authority_scope": "task_operation_only",
            "read_authority_granted": bool(self.read_receipts),
            "read_authority": bool(self.read_receipts),
            "write_authority": False,
            "patch_authority": False,
        }


@dataclass(frozen=True, slots=True)
class _SelectedFile:
    path: str
    requested_mode: str | None
    selection_reason: str
    match_locations: tuple[Any, ...]
    explicit_ranges: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class _ProposedFile:
    path: str
    selection_reason: str
    role: str
    actionability_score: int
    estimated_bytes: int
    priority: int


class _InvalidOperation(ValueError):
    pass


def compute_repository_inventory_identity(
    inventory: RepositoryInventory,
) -> str:
    """Hash immutable inventory metadata without reading files or traversing."""

    if not isinstance(inventory, RepositoryInventory):
        raise TypeError("inventory must be a RepositoryInventory")
    digest = hashlib.sha256()
    digest.update(b"ctx-read-inventory-v1\0")
    digest.update(inventory.canonical_root.encode("utf-8"))
    digest.update(b"\0")
    digest.update(inventory.ignore_policy_fingerprint.encode("utf-8"))
    for entry in inventory.entries:
        digest.update(b"\0path\0")
        digest.update(entry.relative_path.as_posix().encode("utf-8"))
        identity = entry.file_identity
        if identity is None:
            digest.update(b"\0missing-identity")
            continue
        for value in (
            identity.device,
            identity.inode,
            identity.mode,
            identity.size_bytes,
            identity.modified_ns,
            identity.changed_ns,
            identity.created_ns,
        ):
            digest.update(b"\0")
            digest.update(str(value).encode("ascii"))
    return "sha256:" + digest.hexdigest()


def _request_value(request: Mapping[str, Any], name: str, default: Any = None) -> Any:
    return request[name] if name in request else default


def _bounded_text(value: Any, *, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _InvalidOperation(f"{label} must be a nonblank string")
    if len(value) > maximum or any(ord(char) < 32 for char in value):
        raise _InvalidOperation(f"{label} exceeds its safe text bound")
    return value


def _selected_files(request: Mapping[str, Any]) -> tuple[_SelectedFile, ...]:
    raw = _request_value(request, "selected_files")
    if isinstance(raw, (str, bytes, Mapping)) or raw is None:
        raise _InvalidOperation("selected_files must be an iterable of records")
    captured = tuple(islice(iter(raw), MAX_FILES + 1))
    if len(captured) > MAX_FILES:
        raise _InvalidOperation(
            f"selected_files exceeds the hard maximum of {MAX_FILES}"
        )
    selected: list[_SelectedFile] = []
    seen: set[str] = set()
    for item in captured:
        if not isinstance(item, Mapping):
            raise _InvalidOperation("selected_files must contain mappings")
        path = item.get("path")
        if not isinstance(path, str) or not path:
            raise _InvalidOperation("selected file paths must be nonblank strings")
        key = path.casefold()
        if key in seen:
            raise _InvalidOperation("selected_files contains duplicate paths")
        seen.add(key)
        mode = item.get("requested_mode")
        if mode is not None and not isinstance(mode, str):
            raise _InvalidOperation("requested_mode must be a string or null")
        if mode not in {None, "auto", *READ_MODES}:
            raise _InvalidOperation("requested_mode is not a stable direct-read mode")
        reason = item.get("selection_reason", "")
        if not isinstance(reason, str):
            raise _InvalidOperation("selection_reason must be a string")
        matches = item.get("match_locations", ())
        ranges = item.get("ranges", item.get("explicit_ranges", ()))
        if isinstance(matches, (str, bytes, Mapping)):
            raise _InvalidOperation("match_locations must be an iterable")
        if isinstance(ranges, (str, bytes, Mapping)):
            raise _InvalidOperation("explicit ranges must be an iterable")
        captured_matches = tuple(
            islice(iter(matches), MAX_SUPPLIED_MATCH_LOCATIONS + 1)
        )
        captured_ranges = tuple(islice(iter(ranges), MAX_SUPPLIED_RANGES + 1))
        normalized_matches: list[dict[str, Any]] = []
        for match in captured_matches:
            if not isinstance(match, Mapping):
                raise _InvalidOperation("match locations must contain mappings")
            line = match.get("line", match.get("line_number"))
            term = match.get("term", match.get("matched_term"))
            if (
                isinstance(line, bool)
                or not isinstance(line, int)
                or not 1 <= line <= MAX_LINE_NUMBER
            ):
                raise _InvalidOperation(
                    "match locations require a bounded positive line"
                )
            if term is not None and (
                not isinstance(term, str) or len(term) > 240
            ):
                raise _InvalidOperation("match-location terms must be bounded strings")
            normalized_matches.append({"line": line, "term": term})
        normalized_ranges: list[dict[str, int]] = []
        for line_range in captured_ranges:
            try:
                if isinstance(line_range, Mapping):
                    normalized = DirectReadRange(
                        line_range.get("start_line", line_range.get("start")),
                        line_range.get("end_line", line_range.get("end")),
                    )
                elif (
                    isinstance(line_range, (tuple, list))
                    and len(line_range) == 2
                ):
                    normalized = DirectReadRange(line_range[0], line_range[1])
                else:
                    raise ValueError("unsupported range record")
            except (TypeError, ValueError) as exc:
                raise _InvalidOperation("explicit line range is malformed") from exc
            normalized_ranges.append(normalized.as_dict())
        selected.append(
            _SelectedFile(
                path=path,
                requested_mode=mode,
                selection_reason=reason[:400],
                match_locations=tuple(normalized_matches),
                explicit_ranges=tuple(normalized_ranges),
            )
        )
    return tuple(selected)


def _proposed_source(value: Any) -> Any:
    if hasattr(value, "proposed_read_files"):
        return value.proposed_read_files
    if isinstance(value, Mapping) and "proposed_read_files" in value:
        return value["proposed_read_files"]
    return value


def _proposed_files(
    proposed_read_set: ProposedReadSet | Mapping[str, Any],
) -> tuple[tuple[_ProposedFile, ...], int, int]:
    source = _proposed_source(proposed_read_set)
    if isinstance(source, ProposedReadSet):
        raw_selected = source.selected
        max_files = source.max_files
        max_total = source.max_total_bytes
        claimed_total = source.total_estimated_bytes
    elif isinstance(source, Mapping):
        if source.get("read_authority") is True or source.get("write_authority") is True:
            raise _InvalidOperation("proposed-read evidence cannot carry authority")
        raw_selected = source.get("selected")
        max_files = source.get("max_files", MAX_FILES)
        max_total = source.get("max_total_bytes", DirectReadBudgets().max_total_bytes)
        claimed_total = source.get("total_estimated_bytes")
    else:
        raise _InvalidOperation("proposed_read_set has an unsupported shape")
    if isinstance(raw_selected, (str, bytes, Mapping)) or raw_selected is None:
        raise _InvalidOperation("proposed_read_set.selected must be an iterable")
    if (
        isinstance(max_files, bool)
        or not isinstance(max_files, int)
        or not 0 <= max_files <= MAX_FILES
    ):
        raise _InvalidOperation("proposed read file budget is contradictory")
    hard_total = DirectReadBudgets().max_total_bytes
    if (
        isinstance(max_total, bool)
        or not isinstance(max_total, int)
        or not 0 <= max_total <= hard_total
    ):
        raise _InvalidOperation("proposed read byte budget is contradictory")
    captured = tuple(islice(iter(raw_selected), MAX_FILES + 1))
    if len(captured) > MAX_FILES or len(captured) > max_files:
        raise _InvalidOperation("proposed read set exceeds its file budget")
    result: list[_ProposedFile] = []
    seen: set[str] = set()
    estimated_total = 0
    for priority, item in enumerate(captured):
        if isinstance(item, Mapping):
            path = item.get("path")
            reason = item.get("selection_reason", "selected by CTX.SELECT.1")
            role = item.get("role", "primary_or_supporting_target")
            score = item.get("actionability_score", 0)
            estimated = item.get("estimated_bytes", item.get("size_bytes"))
            if item.get("read_authority") is True or item.get("write_authority") is True:
                raise _InvalidOperation("proposed file evidence cannot carry authority")
        else:
            path = getattr(item, "path", None)
            reason = getattr(item, "selection_reason", "selected by CTX.SELECT.1")
            role = getattr(item, "role", "primary_or_supporting_target")
            score = getattr(item, "actionability_score", 0)
            estimated = getattr(item, "estimated_bytes", None)
        if not isinstance(path, str) or not is_safe_repository_relative_path(path):
            raise _InvalidOperation("proposed read set contains an unsafe path")
        if not isinstance(reason, str) or not isinstance(role, str):
            raise _InvalidOperation("proposed read role and reason must be strings")
        key = path.casefold()
        if key in seen:
            raise _InvalidOperation("proposed read set contains duplicate paths")
        seen.add(key)
        if (
            isinstance(score, bool)
            or not isinstance(score, int)
            or not 0 <= score <= 100
        ):
            raise _InvalidOperation("proposed actionability score is invalid")
        if (
            isinstance(estimated, bool)
            or not isinstance(estimated, int)
            or estimated < 0
        ):
            raise _InvalidOperation("proposed estimated byte evidence is invalid")
        estimated_total += estimated
        result.append(
            _ProposedFile(
                path,
                reason[:400],
                role[:100],
                score,
                estimated,
                priority,
            )
        )
    if estimated_total > max_total:
        raise _InvalidOperation("proposed read set exceeds its byte budget")
    if claimed_total is not None:
        if (
            isinstance(claimed_total, bool)
            or not isinstance(claimed_total, int)
            or claimed_total < 0
            or claimed_total != estimated_total
        ):
            raise _InvalidOperation("proposed read byte evidence is contradictory")
    return tuple(result), max_files, max_total


def _evidence_candidates(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if hasattr(value, "search") and hasattr(value.search, "matches"):
        value = value.search.matches
    elif hasattr(value, "matches"):
        value = value.matches
    elif hasattr(value, "accepted"):
        value = value.accepted
    elif isinstance(value, Mapping):
        if isinstance(value.get("search"), Mapping):
            value = value["search"].get("matches", ())
        elif isinstance(value.get("ctx_select_lexical_results"), Mapping):
            value = value["ctx_select_lexical_results"].get("accepted", ())
        else:
            value = value.get("matches", value.get("accepted", ()))
    if isinstance(value, (str, bytes, Mapping)):
        return ()
    try:
        return tuple(islice(iter(value), MAX_SEARCH_EVIDENCE + 1))
    except TypeError:
        return ()


def _match_values(value: Any) -> tuple[str | None, int | None, str | None]:
    if isinstance(value, Mapping):
        path = value.get("path")
        line = value.get("line", value.get("line_number"))
        term = value.get("term", value.get("matched_term"))
    else:
        path = getattr(value, "path", None)
        line = getattr(value, "line", getattr(value, "line_number", None))
        term = getattr(value, "term", getattr(value, "matched_term", None))
    return (
        str(path) if isinstance(path, str) else None,
        line if isinstance(line, int) and not isinstance(line, bool) else None,
        str(term) if isinstance(term, str) else None,
    )


def _trusted_matches_by_path(value: Any) -> dict[str, tuple[dict[str, Any], ...]]:
    captured = _evidence_candidates(value)
    if len(captured) > MAX_SEARCH_EVIDENCE:
        captured = captured[:MAX_SEARCH_EVIDENCE]
    grouped: dict[str, dict[tuple[int, str], dict[str, Any]]] = {}
    for item in captured:
        path, line, term = _match_values(item)
        if (
            path is None
            or line is None
            or line <= 0
            or not is_safe_repository_relative_path(path)
        ):
            continue
        term_text = term or ""
        grouped.setdefault(path, {}).setdefault(
            (line, term_text), {"line": line, "term": term_text}
        )
    return {
        path: tuple(
            records[key]
            for key in sorted(records, key=lambda key: (key[0], key[1]))
        )
        for path, records in sorted(grouped.items())
    }


def _requested_match_values(value: Any) -> tuple[int | None, str | None]:
    if isinstance(value, Mapping):
        line = value.get("line", value.get("line_number"))
        term = value.get("term", value.get("matched_term"))
    else:
        line = getattr(value, "line", getattr(value, "line_number", None))
        term = getattr(value, "term", getattr(value, "matched_term", None))
    return (
        line if isinstance(line, int) and not isinstance(line, bool) else None,
        str(term) if isinstance(term, str) else None,
    )


def _validated_requested_matches(
    requested: tuple[Any, ...],
    trusted: tuple[dict[str, Any], ...],
) -> tuple[tuple[dict[str, Any], ...], bool]:
    if not requested:
        return trusted, False
    trusted_keys = {(item["line"], item["term"]) for item in trusted}
    trusted_lines = {item["line"] for item in trusted}
    accepted: dict[tuple[int, str], dict[str, Any]] = {}
    rejected = False
    for item in requested[:MAX_SUPPLIED_MATCH_LOCATIONS]:
        line, term = _requested_match_values(item)
        key = (line, term or "") if line is not None else None
        if line is None or (
            key not in trusted_keys and not (term is None and line in trusted_lines)
        ):
            rejected = True
            continue
        actual = next(
            candidate
            for candidate in trusted
            if candidate["line"] == line
            and (term is None or candidate["term"] == term)
        )
        accepted[(actual["line"], actual["term"])] = actual
    if len(requested) > MAX_SUPPLIED_MATCH_LOCATIONS:
        rejected = True
    return tuple(accepted[key] for key in sorted(accepted)), rejected


def _capabilities_by_path(
    inventory: RepositoryInventory,
    supplied: Iterable[FileCapability | Mapping[str, Any]] | None,
    *,
    selected_paths: Iterable[str],
) -> dict[str, FileCapability]:
    wanted = frozenset(selected_paths)
    entries = {
        entry.relative_path.as_posix(): entry
        for entry in inventory.entries
        if entry.relative_path.as_posix() in wanted
    }
    supplied_by_path: dict[str, FileCapability | Mapping[str, Any]] = {}
    if supplied is not None:
        if isinstance(supplied, (str, bytes, Mapping)):
            raise _InvalidOperation("capabilities must be an iterable of records")
        captured = tuple(islice(iter(supplied), MAX_FILES + 1))
        if len(captured) > MAX_FILES:
            raise _InvalidOperation("capabilities exceed the bounded selected read set")
        for item in captured:
            if not isinstance(item, (FileCapability, Mapping)):
                raise _InvalidOperation("capabilities must contain capability records")
            path = item.path if isinstance(item, FileCapability) else item.get("path")
            if not isinstance(path, str) or path not in entries:
                raise _InvalidOperation(
                    "capability path is not in the selected supplied inventory set"
                )
            if path.casefold() in {key.casefold() for key in supplied_by_path}:
                raise _InvalidOperation("capabilities contain duplicate paths")
            supplied_by_path[path] = item

    result: dict[str, FileCapability] = {}
    for path, entry in entries.items():
        identity = entry.file_identity
        metadata = supplied_by_path.get(path)
        base: Mapping[str, Any] | str
        if isinstance(metadata, FileCapability):
            base = metadata.as_dict()
        elif isinstance(metadata, Mapping):
            base = metadata
        else:
            base = path
        mapped_base = base if isinstance(base, Mapping) else {}
        result[path] = classify_file_capability(
            base,
            size_bytes=identity.size_bytes if identity else None,
            text_hint=bool(mapped_base.get("text_hint", True)),
            is_binary=bool(mapped_base.get("is_binary", False)),
            repository_contained=bool(
                mapped_base.get("repository_contained", True)
            ),
            symlink_escape=bool(mapped_base.get("symlink_escape", False)),
        )
    return result


def _repository_tier(
    inventory: RepositoryInventory,
    capabilities: Mapping[str, FileCapability],
) -> str:
    if (
        len(inventory.entries) == 1
        and len(capabilities) == 1
        and next(iter(capabilities.values())).direct_read_allowed
    ):
        return "single_file"
    if len(inventory.entries) <= 30:
        return "small"
    if len(inventory.entries) <= 300:
        return "medium"
    return "large"


def _proposed_priority(item: _ProposedFile) -> tuple[int, int, int, str]:
    role = item.role.casefold()
    reason = item.selection_reason.casefold()
    if "contrasting" in reason or "ambiguity" in reason:
        group = 4
    elif role in {"primary", "primary_target", "primary_or_supporting_target"}:
        group = 0
    elif role in {"dependency", "caller", "dependency_or_caller"}:
        group = 1
    elif role in {"test", "tests", "validation"}:
        group = 2
    elif role in {"config", "configuration"}:
        group = 3
    else:
        group = 5
    return group, -item.actionability_score, item.priority, item.path


def _operation_id(
    task_id: str,
    inventory_identity: str,
    selected: tuple[_SelectedFile, ...],
) -> str:
    payload = {
        "task_id": task_id,
        "inventory_identity": inventory_identity,
        "selected": [
            {
                "path": item.path,
                "requested_mode": item.requested_mode,
                "match_locations": list(item.match_locations),
                "explicit_ranges": list(item.explicit_ranges),
            }
            for item in selected
        ],
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]
    return f"ctx-read-{digest}"


def _blocked_context(
    *,
    task_id: str,
    repository_root: str,
    inventory_identity: str,
    budgets: DirectReadBudgets,
    error: str,
    canonical_identity_state: str,
) -> DirectFileContext:
    return DirectFileContext(
        operation_status="operation_blocked",
        task_id=task_id or "<invalid-task>",
        operation_id="ctx-read-blocked",
        repository_root=repository_root,
        inventory_identity=inventory_identity or "<invalid-inventory>",
        files_requested=0,
        file_results=(),
        read_receipts=(),
        omitted_files=(),
        total_bytes_scanned=0,
        total_bytes_returned=0,
        total_lines_scanned=0,
        total_lines_returned=0,
        budget_remaining=budgets.max_total_bytes,
        budgets=budgets,
        errors=(error,),
        recommendations=("request_more_candidates",),
        canonical_identity_state=canonical_identity_state,
    )


def execute_direct_context(
    repo_root: str | os.PathLike[str],
    inventory: RepositoryInventory,
    request: Mapping[str, Any],
    *,
    proposed_read_set: ProposedReadSet | Mapping[str, Any],
    search_evidence: Any = None,
    capabilities: Iterable[FileCapability | Mapping[str, Any]] | None = None,
    canonical_identity_state: str = "unconfirmed",
    vector_database_available: bool | None = None,
    embedding_provider_enabled: bool | None = None,
    canonical_manifest_available: bool | None = None,
    parser_available: bool | None = None,
) -> DirectFileContext:
    """Create one ephemeral bounded Direct File Context.

    Availability parameters are accepted solely to make independence explicit;
    they never activate those systems.
    """

    del vector_database_available
    del embedding_provider_enabled
    del canonical_manifest_available
    del parser_available

    fallback_budgets = DirectReadBudgets()
    task_hint = "<invalid-task>"
    root_hint = str(repo_root)
    identity_hint = "<invalid-inventory>"
    if not isinstance(request, Mapping):
        return _blocked_context(
            task_id=task_hint,
            repository_root=root_hint,
            inventory_identity=identity_hint,
            budgets=fallback_budgets,
            error="direct-read request must be a mapping",
            canonical_identity_state=str(canonical_identity_state)[:80],
        )
    try:
        schema = _request_value(request, "schema_version")
        if schema != DIRECT_READ_SCHEMA_VERSION or isinstance(schema, bool):
            raise _InvalidOperation("schema_version must equal integer 1")
        task_id = _bounded_text(
            _request_value(request, "task_id"),
            label="task_id",
            maximum=MAX_TASK_ID_LENGTH,
        )
        task_hint = task_id
        limits = coerce_direct_read_budgets(_request_value(request, "budgets"))
        selected = _selected_files(request)
        proposed, proposed_file_limit, proposed_byte_limit = _proposed_files(
            proposed_read_set
        )
        limits = DirectReadBudgets(
            **{
                **limits.as_dict(),
                "max_files": min(limits.max_files, proposed_file_limit or limits.max_files),
                "max_total_bytes": min(
                    limits.max_total_bytes,
                    proposed_byte_limit or limits.max_total_bytes,
                ),
            }
        )
        root = Path(repo_root).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise _InvalidOperation("repository root is not a directory")
        validated_inventory = validate_repository_inventory(root, inventory)
        requested_root = _request_value(request, "repository_root")
        if not isinstance(requested_root, str):
            raise _InvalidOperation("repository_root must be supplied as a string")
        try:
            request_root_path = Path(requested_root).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise _InvalidOperation("request repository_root is invalid") from exc
        if os.path.normcase(str(request_root_path)) != os.path.normcase(str(root)):
            raise _InvalidOperation("request repository_root does not match inventory root")
        root_hint = str(root)
        expected_identity = compute_repository_inventory_identity(validated_inventory)
        supplied_identity = _request_value(request, "inventory_identity")
        if not isinstance(supplied_identity, str) or supplied_identity != expected_identity:
            raise _InvalidOperation("inventory_identity does not match supplied inventory")
        identity_hint = expected_identity
        capability_map = _capabilities_by_path(
            validated_inventory,
            capabilities,
            selected_paths=(item.path for item in selected),
        )
    except (OSError, TypeError, ValueError, _InvalidOperation) as exc:
        return _blocked_context(
            task_id=task_hint,
            repository_root=root_hint,
            inventory_identity=identity_hint,
            budgets=locals().get("limits", fallback_budgets),
            error=str(exc),
            canonical_identity_state=str(canonical_identity_state)[:80],
        )

    operation_id_value = request.get("operation_id")
    if operation_id_value is None:
        operation_id = _operation_id(task_id, expected_identity, selected)
    else:
        try:
            operation_id = _bounded_text(
                operation_id_value,
                label="operation_id",
                maximum=MAX_OPERATION_ID_LENGTH,
            )
        except _InvalidOperation as exc:
            return _blocked_context(
                task_id=task_id,
                repository_root=str(root),
                inventory_identity=expected_identity,
                budgets=limits,
                error=str(exc),
                canonical_identity_state=str(canonical_identity_state)[:80],
            )

    inventory_by_path: dict[str, RepositoryEntry] = {
        entry.relative_path.as_posix(): entry for entry in validated_inventory.entries
    }
    proposed_by_path = {item.path: item for item in proposed}
    proposal_order = {
        item.path: index
        for index, item in enumerate(sorted(proposed, key=_proposed_priority))
    }
    requested_order = tuple(
        sorted(
            selected,
            key=lambda item: (
                0 if item.path in proposed_by_path else 1,
                proposal_order[item.path]
                if item.path in proposed_by_path
                else MAX_FILES,
                item.path,
            ),
        )
    )
    trusted_by_path = _trusted_matches_by_path(search_evidence)
    tier = _repository_tier(validated_inventory, capability_map)
    results: list[DirectFileReadResult] = []
    omitted: list[OmittedDirectRead] = []
    warnings: set[str] = set()
    recommendations: set[str] = set()
    total_returned = 0

    for position, selected_file in enumerate(requested_order):
        path = selected_file.path
        if position >= limits.max_files:
            results.append(
                failed_direct_file_read(
                    path,
                    "budget_exhausted",
                    "lower-priority file omitted by the operation file budget",
                    read_mode=selected_file.requested_mode,
                )
            )
            omitted.append(OmittedDirectRead(path, "file_limit"))
            continue
        if not is_safe_repository_relative_path(path):
            results.append(
                failed_direct_file_read(
                    path,
                    "path_outside_repository",
                    "requested path is not a safe repository-relative path",
                )
            )
            continue
        entry = inventory_by_path.get(path)
        if entry is None:
            results.append(
                failed_direct_file_read(
                    path,
                    "path_not_in_inventory",
                    "requested path is absent from the supplied immutable inventory",
                )
            )
            continue
        proposal = proposed_by_path.get(path)
        if proposal is None:
            results.append(
                failed_direct_file_read(
                    path,
                    "read_failed",
                    "path_not_in_proposed_read_set",
                    recommendation="request_more_candidates",
                )
            )
            recommendations.add("request_more_candidates")
            continue
        if proposal.estimated_bytes != (
            entry.file_identity.size_bytes if entry.file_identity else proposal.estimated_bytes
        ):
            results.append(
                failed_direct_file_read(
                    path,
                    "file_changed_or_replaced",
                    "proposed-read size evidence differs from inventory identity",
                )
            )
            continue

        trusted_matches, rejected_matches = _validated_requested_matches(
            selected_file.match_locations,
            trusted_by_path.get(path, ()),
        )
        if rejected_matches:
            warnings.add(f"{path}: untrusted match locations were ignored")
        remaining = limits.max_total_bytes - total_returned
        result = execute_direct_file_read(
            root,
            entry,
            capability=capability_map[path],
            task_id=task_id,
            operation_id=operation_id,
            inventory_identity=expected_identity,
            repository_tier=tier,
            requested_mode=selected_file.requested_mode,
            match_locations=trusted_matches,
            explicit_ranges=selected_file.explicit_ranges,
            budgets=limits,
            max_returned_bytes=remaining,
        )
        results.append(result)
        total_returned += result.bytes_returned
        if result.recommendation:
            recommendations.add(result.recommendation)
        if result.read_status == "budget_exhausted":
            omitted.append(OmittedDirectRead(path, "content_budget"))

    receipts = tuple(result.receipt for result in results if result.receipt is not None)
    successful = len(receipts)
    status = (
        "operation_complete"
        if successful == len(results)
        else "operation_complete_with_partial_reads"
    )
    result_tuple = tuple(results)
    return DirectFileContext(
        operation_status=status,
        task_id=task_id,
        operation_id=operation_id,
        repository_root=str(root),
        inventory_identity=expected_identity,
        files_requested=len(result_tuple),
        file_results=result_tuple,
        read_receipts=receipts,
        omitted_files=tuple(omitted),
        total_bytes_scanned=sum(item.bytes_scanned for item in result_tuple),
        total_bytes_returned=sum(item.bytes_returned for item in result_tuple),
        total_lines_scanned=sum(item.lines_scanned for item in result_tuple),
        total_lines_returned=sum(item.lines_returned for item in result_tuple),
        budget_remaining=limits.max_total_bytes - total_returned,
        budgets=limits,
        warnings=tuple(sorted(warnings))[:MAX_WARNINGS],
        recommendations=tuple(sorted(recommendations)),
        canonical_identity_state=str(canonical_identity_state)[:80],
    )


def build_direct_read_request(
    *,
    task_id: str,
    repository_root: str | os.PathLike[str],
    inventory: RepositoryInventory,
    proposed_read_set: ProposedReadSet,
    selected_files: Iterable[Mapping[str, Any]] | None = None,
    budgets: DirectReadBudgets | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the request envelope without granting read authority."""

    limits = coerce_direct_read_budgets(budgets)
    if selected_files is None:
        selected = tuple(
            {
                "path": item.path,
                "selection_reason": item.selection_reason,
                "requested_mode": "auto",
                "match_locations": [],
            }
            for item in proposed_read_set.selected
        )
    else:
        selected = tuple(dict(item) for item in islice(selected_files, MAX_FILES + 1))
        if len(selected) > MAX_FILES:
            raise ValueError(f"selected_files exceeds the hard maximum of {MAX_FILES}")
    return {
        "schema_version": DIRECT_READ_SCHEMA_VERSION,
        "task_id": task_id,
        "repository_root": str(Path(repository_root).expanduser().resolve()),
        "inventory_identity": compute_repository_inventory_identity(inventory),
        "selected_files": [dict(item) for item in selected],
        "budgets": limits.as_dict(),
        "read_authority": False,
        "write_authority": False,
        "patch_authority": False,
    }


# Stable public aliases.
execute_direct_context_runtime = execute_direct_context
run_direct_context_runtime = execute_direct_context
bounded_direct_read = execute_direct_context
