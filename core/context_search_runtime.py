"""CTX.SEARCH.1 integration with the existing CTX.SELECT.1 result contract."""

from __future__ import annotations

import os
from dataclasses import dataclass
from itertools import islice
from typing import Any, Iterable, Iterator, Mapping

from core.bounded_lexical_search import (
    DEFAULT_MAX_BYTES_SCANNED_PER_FILE,
    DEFAULT_MAX_FILES_CONSIDERED,
    DEFAULT_MAX_SINGLE_LINE_LENGTH,
    DEFAULT_MAX_TOTAL_BYTES_SCANNED,
    EXECUTION_AUTHORITY,
    MAX_FILES_CONSIDERED,
    MAX_MATCHES_PER_FILE,
    BoundedLexicalSearchResult,
    capability_records_for_search,
    execute_bounded_lexical_search,
)
from core.file_candidate_selector import (
    LexicalSearchRequest,
    LexicalSearchResultSet,
    build_lexical_search_request,
    consume_lexical_search_results,
)
from core.file_capabilities import FileCapability
from core.repository_inventory import RepositoryInventory


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
class ContextSearchRuntimeResult(_RecordMapping):
    """Both the execution evidence and its deterministic selector projection."""

    search: BoundedLexicalSearchResult
    lexical_results: LexicalSearchResultSet
    canonical_identity_state: str

    @property
    def status(self) -> str:
        return self.search.status

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase_id": "CTX.SEARCH.1",
            "status": self.status,
            "search": self.search.as_dict(),
            "ctx_select_lexical_results": self.lexical_results.as_dict(),
            "canonical_identity_state": self.canonical_identity_state,
            "canonical_identity_required": False,
            "vector_database_used": False,
            "embeddings_used": False,
            "canonical_manifest_used": False,
            "canonical_index_used": False,
            "model_used": False,
            "api_calls_made": False,
            "database_operations": 0,
            "writes_performed": 0,
            "execution_authority": EXECUTION_AUTHORITY,
            "read_authority": False,
            "write_authority": False,
        }


def execute_context_search(
    repo_root: str | os.PathLike[str],
    inventory: RepositoryInventory,
    request: LexicalSearchRequest | Mapping[str, Any],
    *,
    capabilities: Iterable[FileCapability | Mapping[str, Any]] | None = None,
    canonical_identity_state: str = "unconfirmed",
    vector_database_available: bool | None = None,
    embedding_provider_enabled: bool | None = None,
    canonical_manifest_available: bool | None = None,
    case_sensitive: bool | None = None,
    whole_token_preference: bool | None = None,
    allow_generated: bool = False,
    max_bytes_scanned_per_file: int = DEFAULT_MAX_BYTES_SCANNED_PER_FILE,
    max_total_bytes_scanned: int = DEFAULT_MAX_TOTAL_BYTES_SCANNED,
    max_matches_per_file: int = MAX_MATCHES_PER_FILE,
    max_single_line_length: int = DEFAULT_MAX_SINGLE_LINE_LENGTH,
    max_files_considered: int = DEFAULT_MAX_FILES_CONSIDERED,
) -> ContextSearchRuntimeResult:
    """Run bounded search and pass only sanitized evidence to CTX.SELECT.1.

    Availability arguments intentionally do not activate vectors, embeddings,
    manifests, identity confirmation, or any other intelligence subsystem.
    They exist so callers can make that independence explicit at the seam.
    """

    del vector_database_available
    del embedding_provider_enabled
    del canonical_manifest_available
    execution = execute_bounded_lexical_search(
        repo_root,
        inventory,
        request,
        case_sensitive=case_sensitive,
        whole_token_preference=whole_token_preference,
        allow_generated=allow_generated,
        max_bytes_scanned_per_file=max_bytes_scanned_per_file,
        max_total_bytes_scanned=max_total_bytes_scanned,
        max_matches_per_file=max_matches_per_file,
        max_single_line_length=max_single_line_length,
        max_files_considered=max_files_considered,
    )
    if capabilities is None:
        selector_capabilities = (
            capability_records_for_search(
                inventory,
                paths=tuple(dict.fromkeys(item.path for item in execution.matches)),
            )
            if isinstance(inventory, RepositoryInventory)
            else ()
        )
    else:
        captured_capabilities = tuple(
            islice(iter(capabilities), MAX_FILES_CONSIDERED + 1)
        )
        selector_capabilities = (
            captured_capabilities
            if len(captured_capabilities) <= MAX_FILES_CONSIDERED
            else ()
        )
    try:
        lexical_results = consume_lexical_search_results(
            execution.context_select_results(),
            request=request,
            capabilities=selector_capabilities,
        )
    except (TypeError, ValueError):
        # Invalid selector-side inputs remain a closed, empty evidence set.  The
        # execution result retains the precise stable failure outcome.
        lexical_results = consume_lexical_search_results(
            (),
            request=build_lexical_search_request(
                ("<invalid-request>",),
                max_matches=1,
                max_files=1,
                max_match_length=1,
                max_expansion_rounds=0,
                match_none=True,
            ),
            capabilities=(),
        )
    return ContextSearchRuntimeResult(
        search=execution,
        lexical_results=lexical_results,
        canonical_identity_state=str(canonical_identity_state)[:80],
    )


run_context_search_runtime = execute_context_search
context_search = execute_context_search
