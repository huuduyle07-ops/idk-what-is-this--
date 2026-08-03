"""Bounded, vector-independent candidate discovery over supplied metadata.

This module plans filename and lexical discovery and consumes caller-supplied
search results.  It intentionally contains no repository walk, file-content
read, subprocess, parser, model, index, graph, or database operation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import islice
from pathlib import PurePosixPath
from typing import Any, Iterable, Iterator, Mapping, Sequence

from core.file_actionability import (
    ActionabilityEvidence,
    ActionabilityScore,
    CandidateActionDecision,
    RiskAdjustment,
    calculate_actionability_score,
    derive_candidate_action,
)
from core.file_capabilities import (
    FileCapability,
    classify_file_capability,
    classify_repository_path_read_policy,
    normalize_repository_relative_path,
)
from core.repo_ignore import ANY_DEPTH_HARD_EXCLUDES, ROOT_ONLY_HARD_EXCLUDES


SMALL_REPOSITORY_MAX_READABLE_FILES = 30
MEDIUM_REPOSITORY_MAX_READABLE_FILES = 300

MAX_LEXICAL_MATCHES = 200
MAX_LEXICAL_FILES = 40
MAX_LEXICAL_MATCH_LENGTH = 240
MAX_EXPANSION_ROUNDS = 2
MAX_LEXICAL_TERMS = 32
MAX_LEXICAL_INCLUDE_PATHS = 40
MAX_LEXICAL_EXCLUDE_PATHS = 64
MAX_TEST_PAIRS_PER_FILE = 8
MAX_REFERENCE_EVIDENCE_PER_FILE = 8
MAX_SUPPLIED_LEXICAL_RESULTS = 10_000
MAX_SUPPLIED_LEXICAL_TERMS = 1_024
MAX_SUPPLIED_SEARCH_PATHS = 2_048
MAX_SUPPLIED_DISCOVERY_VALUES = 4_096
MAX_SUPPLIED_REFERENCE_FILES = 1_000
MAX_SUPPLIED_REFERENCE_EVIDENCE_PER_FILE = 256

MAX_LIKELY_ENTRYPOINTS = 20
MAX_EXACT_NAME_MATCHES = 20
MAX_TOKEN_NAME_MATCHES = 40
MAX_DIRECTORY_SYNOPSIS = 24
MAX_FILE_TYPE_COUNTS = 24
MAX_ROOT_ENTRIES = 24
MAX_CANDIDATE_FILES = 80

DEFAULT_LEXICAL_EXCLUDE_PATHS = (
    ".agent/",
    ".git/",
    ".pytest_cache/",
    ".tmp/",
    ".venv/",
    "node_modules/",
    "tmp/",
)

LIKELY_ENTRYPOINT_NAMES = frozenset(
    {
        "app.py",
        "cli.py",
        "index.js",
        "index.ts",
        "main.go",
        "main.py",
        "main.rs",
        "manage.py",
        "server.js",
        "server.py",
        "server.ts",
    }
)

CONFIGURATION_NAMES = frozenset(
    {
        ".env.example",
        ".env.sample",
        ".env.template",
        "cargo.toml",
        "docker-compose.yaml",
        "docker-compose.yml",
        "dockerfile",
        "go.mod",
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "setup.cfg",
        "tox.ini",
    }
)

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
_NOISY_PATH_TOKENS = frozenset(
    {
        "app",
        "core",
        "js",
        "lib",
        "py",
        "src",
        "test",
        "tests",
        "ts",
    }
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
class ListTruncation(_RecordMapping):
    total: int
    returned: int
    limit: int
    truncated: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "returned": self.returned,
            "limit": self.limit,
            "truncated": self.truncated,
        }


@dataclass(frozen=True, slots=True)
class CandidateFilenameReport(_RecordMapping):
    repository_tier: str
    repository_file_count: int
    readable_file_count: int
    complete_relative_paths: tuple[str, ...]
    capability_metadata: tuple[FileCapability, ...]
    root_entries: tuple[str, ...]
    directory_synopsis: tuple[str, ...]
    directory_file_counts: tuple[tuple[str, int], ...]
    file_type_counts: tuple[tuple[str, int], ...]
    likely_entrypoints: tuple[str, ...]
    exact_name_matches: tuple[str, ...]
    token_name_matches: tuple[str, ...]
    candidate_files: tuple[str, ...]
    associated_tests: tuple[tuple[str, tuple[str, ...]], ...]
    evidence_by_path: tuple[tuple[str, tuple[ActionabilityEvidence, ...]], ...]
    truncation: tuple[tuple[str, ListTruncation], ...]

    def evidence_for(self, path: str) -> tuple[ActionabilityEvidence, ...]:
        return dict(self.evidence_by_path).get(path, ())

    def tests_for(self, path: str) -> tuple[str, ...]:
        return dict(self.associated_tests).get(path, ())

    def as_dict(self) -> dict[str, Any]:
        return {
            "repository_tier": self.repository_tier,
            "repository_file_count": self.repository_file_count,
            "readable_file_count": self.readable_file_count,
            "complete_relative_paths": list(self.complete_relative_paths),
            "capability_metadata": [
                item.as_dict() for item in self.capability_metadata
            ],
            "root_entries": list(self.root_entries),
            "directory_synopsis": list(self.directory_synopsis),
            "directory_file_counts": dict(self.directory_file_counts),
            "file_type_counts": dict(self.file_type_counts),
            "likely_entrypoints": list(self.likely_entrypoints),
            "exact_name_matches": list(self.exact_name_matches),
            "token_name_matches": list(self.token_name_matches),
            "candidate_files": list(self.candidate_files),
            "associated_tests": {
                path: list(tests) for path, tests in self.associated_tests
            },
            "truncation": {
                name: metadata.as_dict() for name, metadata in self.truncation
            },
        }


@dataclass(frozen=True, slots=True)
class LexicalSearchRequest(_RecordMapping):
    terms: tuple[str, ...]
    include_paths: tuple[str, ...]
    exclude_paths: tuple[str, ...]
    max_matches: int
    max_files: int
    max_match_length: int
    max_expansion_rounds: int
    terms_truncation: ListTruncation
    include_paths_truncation: ListTruncation
    exclude_paths_truncation: ListTruncation
    scope_mode: str
    safe_inventory_filter_required: bool = True
    production_execution_authorized: bool = False
    case_sensitive: bool = False
    whole_token_preference: bool = True

    def __post_init__(self) -> None:
        if len(self.terms) > MAX_LEXICAL_TERMS:
            raise ValueError("lexical term output exceeds its contract limit")
        if len(self.include_paths) > MAX_LEXICAL_INCLUDE_PATHS:
            raise ValueError("lexical include-path output exceeds its contract limit")
        if len(self.exclude_paths) > MAX_LEXICAL_EXCLUDE_PATHS:
            raise ValueError("lexical exclude-path output exceeds its contract limit")
        if self.safe_inventory_filter_required is not True:
            raise ValueError("lexical requests must require a safe inventory filter")
        if self.production_execution_authorized is not False:
            raise ValueError("CTX.SELECT.1 cannot authorize lexical-search execution")
        if type(self.case_sensitive) is not bool:
            raise TypeError("case_sensitive must be a boolean")
        if type(self.whole_token_preference) is not bool:
            raise TypeError("whole_token_preference must be a boolean")
        if self.scope_mode not in {"safe_inventory", "explicit_paths", "match_none"}:
            raise ValueError("unknown lexical-search scope mode")
        if self.scope_mode == "explicit_paths" and not self.include_paths:
            raise ValueError("explicit lexical scope requires at least one include path")

    def as_dict(self) -> dict[str, Any]:
        return {
            "terms": list(self.terms),
            "include_paths": list(self.include_paths),
            "exclude_paths": list(self.exclude_paths),
            "max_matches": self.max_matches,
            "max_files": self.max_files,
            "max_match_length": self.max_match_length,
            "max_expansion_rounds": self.max_expansion_rounds,
            "terms_truncation": self.terms_truncation.as_dict(),
            "include_paths_truncation": self.include_paths_truncation.as_dict(),
            "exclude_paths_truncation": self.exclude_paths_truncation.as_dict(),
            "scope_mode": self.scope_mode,
            "safe_inventory_filter_required": self.safe_inventory_filter_required,
            "production_execution_authorized": False,
            "case_sensitive": self.case_sensitive,
            "whole_token_preference": self.whole_token_preference,
        }


@dataclass(frozen=True, slots=True)
class LexicalMatch(_RecordMapping):
    path: str
    line_number: int | None
    location: str | None
    matched_term: str
    excerpt: str | None
    result_source: str
    truncated: bool
    match_offset: int | None = None
    match_kind: str = "literal"
    whole_token: bool | None = None
    whole_token_boundary_complete: bool | None = None
    whole_token_preference: bool | None = None
    parser_support: str = "unsupported"
    file_understanding: str = "raw_text_only"

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "line_number": self.line_number,
            "location": self.location,
            "matched_term": self.matched_term,
            "excerpt": self.excerpt,
            "result_source": self.result_source,
            "truncated": self.truncated,
            "match_offset": self.match_offset,
            "match_kind": self.match_kind,
            "whole_token": self.whole_token,
            "whole_token_boundary_complete": self.whole_token_boundary_complete,
            "whole_token_preference": self.whole_token_preference,
            "parser_support": self.parser_support,
            "file_understanding": self.file_understanding,
            "execution_authority": "candidate_discovery_only",
            "read_authority": False,
            "write_authority": False,
        }


@dataclass(frozen=True, slots=True)
class ExcludedLexicalResult(_RecordMapping):
    path: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        # Never retain or render a caller-supplied excerpt for excluded paths.
        return {
            "path": self.path,
            "reason": self.reason,
            "excerpt": None,
            "execution_authority": "candidate_discovery_only",
            "read_authority": False,
            "write_authority": False,
        }


@dataclass(frozen=True, slots=True)
class LexicalSearchResultSet(_RecordMapping):
    matches: tuple[LexicalMatch, ...]
    excluded: tuple[ExcludedLexicalResult, ...]
    total_supplied: int
    matched_file_count: int
    truncated: bool
    truncation: tuple[tuple[str, ListTruncation], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "matches": [item.as_dict() for item in self.matches],
            "excluded": [item.as_dict() for item in self.excluded],
            "total_supplied": self.total_supplied,
            "matched_file_count": self.matched_file_count,
            "truncated": self.truncated,
            "truncation": {
                name: metadata.as_dict() for name, metadata in self.truncation
            },
            "execution_authority": "candidate_discovery_only",
            "read_authority": False,
            "write_authority": False,
        }


@dataclass(frozen=True, slots=True)
class RankedCandidate(_RecordMapping):
    path: str
    capability: FileCapability
    actionability: ActionabilityScore
    decision: CandidateActionDecision
    validation_candidates: tuple[str, ...]
    role: str

    def __post_init__(self) -> None:
        if not (
            self.path == self.capability.path == self.actionability.path
        ):
            raise ValueError("ranked candidate paths must be coherent")
        if self.decision.write_authority is not False:
            raise ValueError("ranked candidates can never carry write authority")
        if self.validation_candidates != tuple(
            sorted(set(self.validation_candidates))
        ):
            raise ValueError(
                "validation candidates must be unique and deterministic"
            )

    @property
    def actionability_score(self) -> int:
        return self.actionability.actionability_score

    @property
    def positive_evidence(self) -> tuple[ActionabilityEvidence, ...]:
        return self.actionability.positive_evidence

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "capability": self.capability.as_dict(),
            **self.actionability.as_dict(),
            "decision": self.decision.as_dict(),
            "validation_candidates": list(self.validation_candidates),
            "role": self.role,
            "write_authority": False,
        }


def _coerce_capability(value: FileCapability | Mapping[str, Any]) -> FileCapability:
    if isinstance(value, FileCapability):
        raw: Mapping[str, Any] = value.as_dict()
        return classify_file_capability(
            {**raw, "sensitive_policy": raw["read_policy"]}
        )
    if not isinstance(value, Mapping):
        raise TypeError("capabilities must be FileCapability values or mappings")
    required = {
        "path",
        "readability",
        "parser_support",
        "indexability",
        "direct_read_allowed",
        "read_policy",
        "editability",
        "understanding_confidence",
    }
    if required <= set(value):
        return classify_file_capability(
            {
                **value,
                "sensitive_policy": value.get(
                    "sensitive_policy", value.get("read_policy")
                ),
            }
        )
    return classify_file_capability(value)


def _validated_capabilities(
    values: Iterable[FileCapability | Mapping[str, Any]],
) -> tuple[FileCapability, ...]:
    materialized = tuple(_coerce_capability(value) for value in values)
    paths = [item.path.casefold() for item in materialized]
    if len(paths) != len(set(paths)):
        raise ValueError("candidate inventory contains duplicate canonical paths")
    return tuple(sorted(materialized, key=lambda item: item.path))


def classify_repository_tier(
    readable_file_count: int,
    *,
    small_max: int = SMALL_REPOSITORY_MAX_READABLE_FILES,
    medium_max: int = MEDIUM_REPOSITORY_MAX_READABLE_FILES,
) -> str:
    if isinstance(readable_file_count, bool) or readable_file_count < 0:
        raise ValueError("readable_file_count must be a non-negative integer")
    if small_max < 0 or medium_max <= small_max:
        raise ValueError("repository tier thresholds must satisfy 0 <= small < medium")
    if readable_file_count <= small_max:
        return "small"
    if readable_file_count <= medium_max:
        return "medium"
    return "large"


def _tokens(values: Iterable[str]) -> tuple[str, ...]:
    result = {
        token.casefold()
        for value in values
        for token in _TOKEN_PATTERN.findall(str(value))
        if len(token) >= 2 and token.casefold() not in _NOISY_PATH_TOKENS
    }
    return tuple(sorted(result))


def _path_tokens(path: str) -> tuple[str, ...]:
    return _tokens((path,))


def _bounded(values: Iterable[str], limit: int) -> tuple[tuple[str, ...], ListTruncation]:
    ordered = tuple(sorted(set(values)))
    selected = ordered[:limit]
    return selected, ListTruncation(
        total=len(ordered),
        returned=len(selected),
        limit=limit,
        truncated=len(ordered) > len(selected),
    )


def _is_test_path(path: str) -> bool:
    pure = PurePosixPath(path)
    name = pure.name.casefold()
    return (
        any(part.casefold() in {"test", "tests", "spec", "specs", "__tests__"} for part in pure.parts[:-1])
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
        or name.endswith("_test.py")
    )


def _pair_stem(path: str) -> str:
    name = PurePosixPath(path).name.casefold()
    for marker in (".test.", ".spec."):
        if marker in name:
            return name.split(marker, 1)[0]
    stem = PurePosixPath(name).stem
    if stem.startswith("test_"):
        stem = stem[5:]
    if stem.endswith("_test"):
        stem = stem[:-5]
    return stem


def _pair_parent(path: str) -> tuple[str, ...]:
    parts = [part.casefold() for part in PurePosixPath(path).parts[:-1]]
    ignored = {"src", "source", "lib", "test", "tests", "spec", "specs", "__tests__"}
    while parts and parts[0] in ignored:
        parts.pop(0)
    return tuple(part for part in parts if part not in {"test", "tests", "spec", "specs", "__tests__"})


def _parents_match(source: str, test: str) -> bool:
    source_parent = _pair_parent(source)
    test_parent = _pair_parent(test)
    if not source_parent or not test_parent:
        return False
    shorter = min(len(source_parent), len(test_parent))
    return source_parent[-shorter:] == test_parent[-shorter:]


def _test_associations(paths: Iterable[str]) -> dict[str, tuple[str, ...]]:
    ordered = tuple(sorted(set(paths)))
    tests_by_stem: dict[str, list[str]] = {}
    sources_by_stem: dict[str, list[str]] = {}
    for path in ordered:
        target = tests_by_stem if _is_test_path(path) else sources_by_stem
        target.setdefault(_pair_stem(path), []).append(path)
    result: dict[str, tuple[str, ...]] = {}
    for stem in sorted(set(tests_by_stem) & set(sources_by_stem)):
        tests = tuple(sorted(tests_by_stem[stem]))[:MAX_TEST_PAIRS_PER_FILE]
        sources = tuple(sorted(sources_by_stem[stem]))[:MAX_TEST_PAIRS_PER_FILE]
        pairs: set[tuple[str, str]] = set()
        if len(sources) == 1:
            pairs.update((sources[0], test) for test in tests)
        else:
            for test in tests:
                local_sources = tuple(
                    source for source in sources if _parents_match(source, test)
                )
                if len(local_sources) == 1:
                    pairs.add((local_sources[0], test))
        for source, test in sorted(pairs):
            result.setdefault(source, ())
            result[source] = tuple(sorted({*result[source], test}))
            result.setdefault(test, ())
            result[test] = tuple(sorted({*result[test], source}))
    return result


def _bounded_input_values(
    values: Iterable[Any],
    *,
    limit: int,
    label: str,
) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{label} must be an iterable of values, not a string")
    materialized = tuple(islice(iter(values), limit + 1))
    if len(materialized) > limit:
        raise ValueError(f"{label} exceeds the defensive input limit of {limit}")
    return materialized


def _add_evidence(
    target: dict[str, list[ActionabilityEvidence]],
    path: str,
    kind: str,
    detail: str,
    *,
    related_path: str | None = None,
    evidence_id: str | None = None,
) -> None:
    from core.file_actionability import EVIDENCE_STAGE, EVIDENCE_WEIGHTS

    target.setdefault(path, []).append(
        ActionabilityEvidence(
            kind=kind,
            detail=detail,
            stage=EVIDENCE_STAGE[kind],
            weight=EVIDENCE_WEIGHTS[kind],
            related_path=related_path,
            evidence_id=evidence_id,
        )
    )


def build_candidate_filename_report(
    capabilities: Iterable[FileCapability | Mapping[str, Any]],
    *,
    task_terms: Iterable[str] = (),
    user_named_files: Iterable[str] = (),
    user_named_symbols: Iterable[str] = (),
    recent_change_hints: Iterable[str] = (),
) -> CandidateFilenameReport:
    """Build the deterministic candidate-name report before lexical search."""

    records = _validated_capabilities(capabilities)
    visible = tuple(item for item in records if not item.hard_excluded)
    readable = tuple(item for item in visible if item.direct_read_allowed)
    tier = classify_repository_tier(len(readable))
    safe_paths = tuple(item.path for item in visible)
    readable_paths = tuple(item.path for item in readable)

    evidence: dict[str, list[ActionabilityEvidence]] = {}
    likely: list[str] = []
    config: set[str] = set()
    for item in visible:
        name = PurePosixPath(item.path).name.casefold()
        if name in LIKELY_ENTRYPOINT_NAMES:
            likely.append(item.path)
            _add_evidence(evidence, item.path, "likely_entrypoint", name)
        if name in CONFIGURATION_NAMES:
            config.add(item.path)
            _add_evidence(evidence, item.path, "configuration_file", name)
        if item.indexability == "direct_context_only" and item.direct_read_allowed:
            _add_evidence(
                evidence,
                item.path,
                "unsupported_but_readable_text",
                item.parser_support,
            )

    if len(readable) == 1:
        _add_evidence(
            evidence,
            readable[0].path,
            "single_readable_file",
            "only safe readable repository file",
        )

    exact: set[str] = set()
    token_matches: set[str] = set()
    named_input = _bounded_input_values(
        user_named_files,
        limit=MAX_SUPPLIED_DISCOVERY_VALUES,
        label="user_named_files",
    )
    task_input = _bounded_input_values(
        task_terms,
        limit=MAX_SUPPLIED_DISCOVERY_VALUES,
        label="task_terms",
    )
    symbol_input = _bounded_input_values(
        user_named_symbols,
        limit=MAX_SUPPLIED_DISCOVERY_VALUES,
        label="user_named_symbols",
    )
    recent_input = _bounded_input_values(
        recent_change_hints,
        limit=MAX_SUPPLIED_DISCOVERY_VALUES,
        label="recent_change_hints",
    )
    named_values = tuple(sorted(set(str(value) for value in named_input)))
    task_values = tuple(str(value) for value in task_input)
    symbol_values = tuple(str(value) for value in symbol_input)
    task_tokens = set(_tokens((*task_values, *symbol_values)))
    named_tokens = set(_tokens(named_values))

    normalized_named: set[str] = set()
    named_basenames: set[str] = set()
    for value in named_values:
        rendered_name = value.replace("\\", "/")
        normalized = normalize_repository_relative_path(rendered_name)
        if normalized:
            normalized_named.add(normalized.casefold())
        if "/" not in rendered_name:
            named_basenames.add(PurePosixPath(rendered_name).name.casefold())

    for item in visible:
        path_low = item.path.casefold()
        name_low = PurePosixPath(item.path).name.casefold()
        stem_low = PurePosixPath(item.path).stem.casefold()
        path_token_set = set(_path_tokens(item.path))
        name_token_set = set(_tokens((PurePosixPath(item.path).name,)))

        if path_low in normalized_named or name_low in named_basenames:
            exact.add(item.path)
            _add_evidence(
                evidence,
                item.path,
                "user_named_file",
                item.path,
                evidence_id=f"user-file:{item.path.casefold()}",
            )
        if any(
            value.casefold() in {path_low, name_low, stem_low}
            for value in task_values
        ):
            exact.add(item.path)
            _add_evidence(
                evidence,
                item.path,
                "exact_filename_match",
                item.path,
            )

        filename_hits = sorted((task_tokens | named_tokens) & name_token_set)
        path_hits = sorted(((task_tokens | named_tokens) & path_token_set) - set(filename_hits))
        for token in filename_hits:
            token_matches.add(item.path)
            _add_evidence(
                evidence,
                item.path,
                "filename_token_match",
                token,
            )
        for token in path_hits:
            token_matches.add(item.path)
            _add_evidence(evidence, item.path, "path_token_match", token)

    associations = _test_associations(safe_paths)
    relevant_seeds = set(evidence)
    for path in sorted(associations):
        if path not in relevant_seeds and not any(
            related in relevant_seeds for related in associations[path]
        ):
            continue
        for related in associations[path]:
            _add_evidence(
                evidence,
                path,
                "test_pair",
                related,
                related_path=related,
                evidence_id=f"test-pair:{min(path, related)}:{max(path, related)}:{path}",
            )

    valid_path_map = {item.path.casefold(): item.path for item in visible}
    for raw in sorted(set(str(value) for value in recent_input)):
        normalized = normalize_repository_relative_path(raw.replace("\\", "/"))
        canonical = valid_path_map.get((normalized or "").casefold())
        if canonical:
            _add_evidence(evidence, canonical, "recent_change_hint", canonical)

    for path in sorted(evidence):
        for symbol in sorted(set(symbol_values)):
            if symbol and symbol.casefold() in set(_path_tokens(path)):
                _add_evidence(evidence, path, "user_named_symbol", symbol)

    root_values = {
        (
            PurePosixPath(path).parts[0] + "/"
            if len(PurePosixPath(path).parts) > 1
            else path
        )
        for path in safe_paths
    }
    directory_values = {
        PurePosixPath(*PurePosixPath(path).parts[:depth]).as_posix() + "/"
        for path in safe_paths
        for depth in (1, 2)
        if len(PurePosixPath(path).parts) > depth
    }
    directory_count_map: dict[str, int] = {}
    file_type_count_map: dict[str, int] = {}
    for safe_path in safe_paths:
        pure = PurePosixPath(safe_path)
        file_type = pure.suffix.casefold() or "<no_extension>"
        file_type_count_map[file_type] = file_type_count_map.get(file_type, 0) + 1
        for depth in (1, 2):
            if len(pure.parts) <= depth:
                continue
            directory = PurePosixPath(*pure.parts[:depth]).as_posix() + "/"
            directory_count_map[directory] = directory_count_map.get(directory, 0) + 1

    if tier == "small":
        complete, complete_meta = _bounded(
            readable_paths,
            SMALL_REPOSITORY_MAX_READABLE_FILES,
        )
        capability_metadata = readable
        capability_metadata_meta = ListTruncation(
            total=len(readable),
            returned=len(capability_metadata),
            limit=SMALL_REPOSITORY_MAX_READABLE_FILES,
            truncated=False,
        )
    else:
        complete = ()
        capability_metadata = ()
        complete_meta = ListTruncation(
            total=len(readable_paths),
            returned=0,
            limit=0,
            truncated=bool(readable_paths),
        )
        capability_metadata_meta = ListTruncation(
            total=len(readable),
            returned=0,
            limit=0,
            truncated=bool(readable),
        )
    roots, roots_meta = _bounded(root_values, MAX_ROOT_ENTRIES)
    directories, directories_meta = _bounded(
        directory_values, MAX_DIRECTORY_SYNOPSIS
    )
    all_directory_counts = tuple(
        sorted(
            directory_count_map.items(),
            key=lambda item: (-item[1], item[0]),
        )
    )
    directory_counts = all_directory_counts[:MAX_DIRECTORY_SYNOPSIS]
    directory_counts_meta = ListTruncation(
        total=len(all_directory_counts),
        returned=len(directory_counts),
        limit=MAX_DIRECTORY_SYNOPSIS,
        truncated=len(all_directory_counts) > len(directory_counts),
    )
    all_file_type_counts = tuple(
        sorted(file_type_count_map.items(), key=lambda item: (-item[1], item[0]))
    )
    file_type_counts = all_file_type_counts[:MAX_FILE_TYPE_COUNTS]
    file_type_counts_meta = ListTruncation(
        total=len(all_file_type_counts),
        returned=len(file_type_counts),
        limit=MAX_FILE_TYPE_COUNTS,
        truncated=len(all_file_type_counts) > len(file_type_counts),
    )
    likely_values, likely_meta = _bounded(likely, MAX_LIKELY_ENTRYPOINTS)
    exact_values, exact_meta = _bounded(exact, MAX_EXACT_NAME_MATCHES)
    token_values, token_meta = _bounded(token_matches, MAX_TOKEN_NAME_MATCHES)
    def candidate_priority(path_value: str) -> tuple[Any, ...]:
        kinds = {item.kind for item in evidence[path_value]}
        total_weight = sum(item.weight for item in evidence[path_value])
        return (
            0 if "user_named_file" in kinds else 1,
            0 if "exact_filename_match" in kinds else 1,
            -total_weight,
            path_value,
        )

    all_candidate_values = tuple(sorted(evidence, key=candidate_priority))
    candidate_values = all_candidate_values[:MAX_CANDIDATE_FILES]
    candidate_meta = ListTruncation(
        total=len(all_candidate_values),
        returned=len(candidate_values),
        limit=MAX_CANDIDATE_FILES,
        truncated=len(all_candidate_values) > len(candidate_values),
    )

    evidence_records = tuple(
        (
            path,
            tuple(
                sorted(
                    evidence[path],
                    key=lambda item: (
                        {"inventory": 0, "filename_match": 1, "lexical_search": 2}[
                            item.stage
                        ],
                        item.kind,
                        item.detail,
                        item.related_path or "",
                    ),
                )
            ),
        )
        for path in candidate_values
    )
    association_records = tuple(
        (path, associations[path])
        for path in sorted(associations)
        if path in set(candidate_values) or any(
            related in set(candidate_values) for related in associations[path]
        )
    )
    truncation = tuple(
        sorted(
            {
                "candidate_files": candidate_meta,
                "capability_metadata": capability_metadata_meta,
                "complete_relative_paths": complete_meta,
                "directory_synopsis": directories_meta,
                "directory_file_counts": directory_counts_meta,
                "exact_name_matches": exact_meta,
                "file_type_counts": file_type_counts_meta,
                "likely_entrypoints": likely_meta,
                "root_entries": roots_meta,
                "token_name_matches": token_meta,
            }.items()
        )
    )
    return CandidateFilenameReport(
        repository_tier=tier,
        repository_file_count=len(records),
        readable_file_count=len(readable),
        complete_relative_paths=complete,
        capability_metadata=capability_metadata,
        root_entries=roots,
        directory_synopsis=directories,
        directory_file_counts=directory_counts,
        file_type_counts=file_type_counts,
        likely_entrypoints=likely_values,
        exact_name_matches=exact_values,
        token_name_matches=token_values,
        candidate_files=candidate_values,
        associated_tests=association_records,
        evidence_by_path=evidence_records,
        truncation=truncation,
    )


def _normalize_prefix(value: str) -> str | None:
    rendered = str(value).replace("\\", "/")
    wants_directory = rendered.endswith("/")
    core = rendered.rstrip("/")
    normalized = normalize_repository_relative_path(core)
    if normalized is None:
        return None
    return normalized + ("/" if wants_directory else "")


def _under_prefix(path: str, prefix: str) -> bool:
    core = prefix.rstrip("/")
    return path == core or path.startswith(core + "/")


def _hard_excluded_prefix(prefix: str) -> bool:
    parts = tuple(part.casefold() for part in PurePosixPath(prefix.rstrip("/")).parts)
    any_depth = {item.casefold() for item in ANY_DEPTH_HARD_EXCLUDES}
    root_only = {item.casefold() for item in ROOT_ONLY_HARD_EXCLUDES}
    ignored = any(part in any_depth for part in parts) or (
        bool(parts) and parts[0] in root_only
    )
    read_policy, _ = classify_repository_path_read_policy(prefix.rstrip("/"))
    return ignored or read_policy != "auto_read_allowed"


def build_lexical_search_request(
    terms: Iterable[str],
    *,
    include_paths: Iterable[str] = (),
    exclude_paths: Iterable[str] = DEFAULT_LEXICAL_EXCLUDE_PATHS,
    max_matches: int = MAX_LEXICAL_MATCHES,
    max_files: int = MAX_LEXICAL_FILES,
    max_match_length: int = MAX_LEXICAL_MATCH_LENGTH,
    max_expansion_rounds: int = MAX_EXPANSION_ROUNDS,
    match_none: bool = False,
    case_sensitive: bool = False,
    whole_token_preference: bool = True,
) -> LexicalSearchRequest:
    """Build a bounded request description; no search is executed."""

    supplied_terms = _bounded_input_values(
        terms,
        limit=MAX_SUPPLIED_LEXICAL_TERMS,
        label="lexical terms",
    )
    all_terms = tuple(
        sorted(
            {
                str(term).strip()
                for term in supplied_terms
                if str(term).strip()
            },
            key=lambda value: (value.casefold(), value),
        )
    )
    selected_terms = all_terms[:MAX_LEXICAL_TERMS]
    terms_meta = ListTruncation(
        len(all_terms),
        len(selected_terms),
        MAX_LEXICAL_TERMS,
        len(all_terms) > len(selected_terms),
    )

    supplied_includes = _bounded_input_values(
        include_paths,
        limit=MAX_SUPPLIED_SEARCH_PATHS,
        label="lexical include paths",
    )
    supplied_excludes = _bounded_input_values(
        exclude_paths,
        limit=MAX_SUPPLIED_SEARCH_PATHS,
        label="lexical exclude paths",
    )
    all_includes = tuple(
        sorted(
            {
                normalized
                for raw in supplied_includes
                if (normalized := _normalize_prefix(raw)) is not None
                and not _hard_excluded_prefix(normalized)
            }
        )
    )
    mandatory_excludes = tuple(
        sorted(
            {
                normalized
                for raw in DEFAULT_LEXICAL_EXCLUDE_PATHS
                if (normalized := _normalize_prefix(raw)) is not None
            }
        )
    )
    optional_excludes = tuple(
        sorted(
            {
                normalized
                for raw in supplied_excludes
                if (normalized := _normalize_prefix(raw)) is not None
                and normalized not in set(mandatory_excludes)
            }
        )
    )
    all_excludes = mandatory_excludes + optional_excludes
    all_includes = tuple(
        value
        for value in all_includes
        if not any(
            _under_prefix(value.rstrip("/"), excluded)
            for excluded in all_excludes
        )
    )
    includes = all_includes[:MAX_LEXICAL_INCLUDE_PATHS]
    excludes = all_excludes[:MAX_LEXICAL_EXCLUDE_PATHS]
    includes_meta = ListTruncation(
        total=len(all_includes),
        returned=len(includes),
        limit=MAX_LEXICAL_INCLUDE_PATHS,
        truncated=len(all_includes) > len(includes),
    )
    excludes_meta = ListTruncation(
        total=len(all_excludes),
        returned=len(excludes),
        limit=MAX_LEXICAL_EXCLUDE_PATHS,
        truncated=len(all_excludes) > len(excludes),
    )
    scope_mode = (
        "match_none"
        if match_none or (bool(supplied_includes) and not includes)
        else "explicit_paths"
        if includes
        else "safe_inventory"
    )

    return LexicalSearchRequest(
        terms=selected_terms,
        include_paths=includes,
        exclude_paths=excludes,
        max_matches=max(1, min(int(max_matches), MAX_LEXICAL_MATCHES)),
        max_files=max(1, min(int(max_files), MAX_LEXICAL_FILES)),
        max_match_length=max(
            1, min(int(max_match_length), MAX_LEXICAL_MATCH_LENGTH)
        ),
        max_expansion_rounds=max(
            0, min(int(max_expansion_rounds), MAX_EXPANSION_ROUNDS)
        ),
        terms_truncation=terms_meta,
        include_paths_truncation=includes_meta,
        exclude_paths_truncation=excludes_meta,
        scope_mode=scope_mode,
        case_sensitive=case_sensitive,
        whole_token_preference=whole_token_preference,
    )


def _coerce_request(value: LexicalSearchRequest | Mapping[str, Any]) -> LexicalSearchRequest:
    if isinstance(value, LexicalSearchRequest):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("request must be LexicalSearchRequest or a mapping")
    return build_lexical_search_request(
        value.get("terms", ()),
        include_paths=value.get("include_paths", ()),
        exclude_paths=value.get("exclude_paths", DEFAULT_LEXICAL_EXCLUDE_PATHS),
        max_matches=int(value.get("max_matches", MAX_LEXICAL_MATCHES)),
        max_files=int(value.get("max_files", MAX_LEXICAL_FILES)),
        max_match_length=int(
            value.get("max_match_length", MAX_LEXICAL_MATCH_LENGTH)
        ),
        max_expansion_rounds=int(
            value.get("max_expansion_rounds", MAX_EXPANSION_ROUNDS)
        ),
        match_none=value.get("scope_mode") == "match_none",
        case_sensitive=value.get("case_sensitive", False),
        whole_token_preference=value.get("whole_token_preference", True),
    )


def consume_lexical_search_results(
    results: Iterable[Mapping[str, Any]],
    *,
    request: LexicalSearchRequest | Mapping[str, Any],
    capabilities: Iterable[FileCapability | Mapping[str, Any]],
) -> LexicalSearchResultSet:
    """Validate, sanitize, deterministically order, and cap supplied matches."""

    bounded_request = _coerce_request(request)
    records = _validated_capabilities(capabilities)
    by_path = {item.path.casefold(): item for item in records}
    term_keys = {term.casefold() for term in bounded_request.terms}
    accepted: dict[tuple[Any, ...], LexicalMatch] = {}
    excluded: dict[tuple[str, str], ExcludedLexicalResult] = {}
    supplied = tuple(islice(iter(results), MAX_SUPPLIED_LEXICAL_RESULTS + 1))
    supplied_overflow = len(supplied) > MAX_SUPPLIED_LEXICAL_RESULTS
    if supplied_overflow:
        supplied_meta = ListTruncation(
            MAX_SUPPLIED_LEXICAL_RESULTS + 1,
            0,
            MAX_SUPPLIED_LEXICAL_RESULTS,
            True,
        )
        empty_matches = ListTruncation(
            MAX_SUPPLIED_LEXICAL_RESULTS + 1,
            0,
            bounded_request.max_matches,
            True,
        )
        empty_files = ListTruncation(0, 0, bounded_request.max_files, False)
        empty_excluded = ListTruncation(1, 1, MAX_LEXICAL_MATCHES, False)
        return LexicalSearchResultSet(
            matches=(),
            excluded=(
                ExcludedLexicalResult(
                    "<result-set>", "supplied_result_safety_limit_exceeded"
                ),
            ),
            total_supplied=MAX_SUPPLIED_LEXICAL_RESULTS + 1,
            matched_file_count=0,
            truncated=True,
            truncation=(
                ("excluded", empty_excluded),
                ("files", empty_files),
                ("matches", empty_matches),
                ("supplied", supplied_meta),
            ),
        )
    supplied_count = len(supplied) + (1 if supplied_overflow else 0)
    accepted_total = 0
    excluded_total = 0
    all_matched_files: set[str] = set()

    def record_exclusion(path: str, reason: str) -> None:
        nonlocal excluded_total
        excluded_total += 1
        key = (path, reason)
        excluded[key] = ExcludedLexicalResult(path, reason)
        if len(excluded) > MAX_LEXICAL_MATCHES:
            del excluded[max(excluded)]

    for raw in supplied:
        if not isinstance(raw, Mapping):
            record_exclusion("", "invalid_result_shape")
            continue
        raw_path = str(raw.get("path", raw.get("relative_path", "")))
        path = normalize_repository_relative_path(raw_path)
        safe_report_path = path or "<invalid-relative-path>"
        if path is None:
            record_exclusion(safe_report_path, "unsafe_path")
            continue
        if any(_under_prefix(path, prefix) for prefix in bounded_request.exclude_paths):
            record_exclusion(path, "excluded_path")
            continue
        if bounded_request.scope_mode == "match_none":
            record_exclusion(path, "empty_safe_search_scope")
            continue
        if bounded_request.include_paths and not any(
            _under_prefix(path, prefix) for prefix in bounded_request.include_paths
        ):
            record_exclusion(path, "outside_include_paths")
            continue
        capability = by_path.get(path.casefold())
        if capability is None:
            record_exclusion(path, "not_in_repository_inventory")
            continue
        if (
            capability.read_policy != "auto_read_allowed"
            or not capability.direct_read_allowed
            or capability.editability
            in {
                "sensitive_requires_approval",
                "outside_scope",
                "opaque",
                "forbidden",
            }
        ):
            record_exclusion(path, "security_policy_exclusion")
            continue
        if capability.readability not in {"readable_text", "readable_limited"}:
            record_exclusion(path, "non_text_result")
            continue

        term = str(raw.get("matched_term", raw.get("term", ""))).strip()
        if not term or term.casefold() not in term_keys:
            record_exclusion(path, "unrequested_term")
            continue
        line_raw = raw.get("line_number", raw.get("line"))
        line_number: int | None = None
        if line_raw is not None:
            if isinstance(line_raw, bool):
                record_exclusion(path, "invalid_location")
                continue
            try:
                line_number = int(line_raw)
            except (TypeError, ValueError):
                record_exclusion(path, "invalid_location")
                continue
            if line_number <= 0:
                record_exclusion(path, "invalid_location")
                continue
        location_raw = raw.get("location")
        location = str(location_raw)[:120] if location_raw else None
        if line_number is None and location is None:
            record_exclusion(path, "missing_location")
            continue

        excerpt_raw = raw.get("excerpt")
        excerpt = str(excerpt_raw) if excerpt_raw is not None else None
        clipped = False
        if excerpt is not None and len(excerpt) > bounded_request.max_match_length:
            excerpt = excerpt[: bounded_request.max_match_length]
            clipped = True
        source = str(raw.get("result_source", raw.get("source", "supplied")))[:80]
        offset_raw = raw.get("match_offset", raw.get("offset"))
        match_offset: int | None = None
        if offset_raw is not None:
            if isinstance(offset_raw, bool):
                record_exclusion(path, "invalid_location")
                continue
            try:
                match_offset = int(offset_raw)
            except (TypeError, ValueError):
                record_exclusion(path, "invalid_location")
                continue
            if match_offset < 0:
                record_exclusion(path, "invalid_location")
                continue
        whole_token_raw = raw.get("whole_token")
        if whole_token_raw is not None and type(whole_token_raw) is not bool:
            record_exclusion(path, "invalid_result_shape")
            continue
        whole_token_boundary_raw = raw.get("whole_token_boundary_complete")
        if (
            whole_token_boundary_raw is not None
            and type(whole_token_boundary_raw) is not bool
        ):
            record_exclusion(path, "invalid_result_shape")
            continue
        whole_token_preference_raw = raw.get("whole_token_preference")
        if (
            whole_token_preference_raw is not None
            and type(whole_token_preference_raw) is not bool
        ):
            record_exclusion(path, "invalid_result_shape")
            continue
        match_kind = str(raw.get("match_kind", "literal"))
        if match_kind != "literal":
            record_exclusion(path, "unsupported_match_kind")
            continue
        item = LexicalMatch(
            path=path,
            line_number=line_number,
            location=location,
            matched_term=term,
            excerpt=excerpt,
            result_source=source,
            truncated=bool(raw.get("truncated", False)) or clipped,
            match_offset=match_offset,
            match_kind="literal",
            whole_token=whole_token_raw,
            whole_token_boundary_complete=whole_token_boundary_raw,
            whole_token_preference=whole_token_preference_raw,
            parser_support=capability.parser_support,
            file_understanding="raw_text_only",
        )
        key = (
            item.path,
            item.line_number if item.line_number is not None else 2**63 - 1,
            item.match_offset if item.match_offset is not None else 2**63 - 1,
            item.location or "",
            item.matched_term.casefold(),
            item.result_source,
        )
        current = accepted.get(key)
        item_rank = (
            item.excerpt or "",
            item.truncated,
            item.location or "",
        )
        current_rank = (
            current.excerpt or "",
            current.truncated,
            current.location or "",
        ) if current is not None else None
        if current is None or item_rank < current_rank:
            accepted[key] = item
        if current is None:
            accepted_total += 1
        all_matched_files.add(path)
        if len(accepted) > bounded_request.max_matches:
            del accepted[max(accepted)]

    ordered = tuple(item for _, item in sorted(accepted.items(), key=lambda pair: pair[0]))
    all_files = tuple(sorted(all_matched_files))
    selected_files = set(all_files[: bounded_request.max_files])
    file_capped = tuple(item for item in ordered if item.path in selected_files)
    selected = file_capped[: bounded_request.max_matches]
    match_meta = ListTruncation(
        accepted_total,
        len(selected),
        bounded_request.max_matches,
        accepted_total > len(selected),
    )
    returned_file_count = len({item.path for item in selected})
    file_meta = ListTruncation(
        len(all_files),
        len(selected_files),
        bounded_request.max_files,
        len(all_files) > len(selected_files),
    )
    excluded_meta = ListTruncation(
        excluded_total,
        len(excluded),
        MAX_LEXICAL_MATCHES,
        excluded_total > len(excluded),
    )
    supplied_meta = ListTruncation(
        supplied_count,
        len(supplied),
        MAX_SUPPLIED_LEXICAL_RESULTS,
        supplied_overflow,
    )
    return LexicalSearchResultSet(
        matches=selected,
        excluded=tuple(
            item for _, item in sorted(excluded.items(), key=lambda pair: pair[0])
        ),
        total_supplied=supplied_count,
        matched_file_count=returned_file_count,
        truncated=(
            match_meta.truncated
            or file_meta.truncated
            or excluded_meta.truncated
            or supplied_meta.truncated
        ),
        truncation=(
            ("excluded", excluded_meta),
            ("files", file_meta),
            ("matches", match_meta),
            ("supplied", supplied_meta),
        ),
    )


normalize_lexical_search_results = consume_lexical_search_results


def _role_for(path: str, evidence: Sequence[ActionabilityEvidence]) -> str:
    kinds = {item.kind for item in evidence}
    if _is_test_path(path) or "test_pair" in kinds and PurePosixPath(path).name.casefold().startswith("test_"):
        return "validation"
    if "configuration_file" in kinds:
        return "configuration"
    if kinds & {"direct_import_reference", "direct_symbol_reference"}:
        return "dependency_or_caller"
    return "primary_or_supporting_target"


def rank_candidates(
    capabilities: Iterable[FileCapability | Mapping[str, Any]],
    *,
    filename_report: CandidateFilenameReport,
    lexical_results: LexicalSearchResultSet | None = None,
    reference_evidence: Mapping[str, Iterable[Mapping[str, Any] | str]] | None = None,
    risk_hints: Mapping[str, Iterable[RiskAdjustment | Mapping[str, Any] | str]] | None = None,
) -> tuple[RankedCandidate, ...]:
    """Merge supplied evidence and return deterministic relevance ranking."""

    records = _validated_capabilities(capabilities)
    by_path = {item.path: item for item in records}
    by_path_casefold = {item.path.casefold(): item.path for item in records}
    evidence: dict[str, list[ActionabilityEvidence]] = {
        path: list(items) for path, items in filename_report.evidence_by_path
    }

    if lexical_results is not None:
        for match in lexical_results.matches:
            _add_evidence(
                evidence,
                match.path,
                "lexical_match",
                match.matched_term,
                evidence_id=(
                    f"lexical:{match.path}:{match.line_number or match.location}:"
                    f"{match.matched_term.casefold()}"
                ),
            )

    if reference_evidence:
        if len(reference_evidence) > MAX_SUPPLIED_REFERENCE_FILES:
            raise ValueError(
                "reference_evidence exceeds the defensive file limit of "
                f"{MAX_SUPPLIED_REFERENCE_FILES}"
            )
        for raw_path in sorted(reference_evidence):
            normalized = normalize_repository_relative_path(raw_path)
            canonical = by_path_casefold.get((normalized or "").casefold())
            if canonical is None:
                continue
            normalized_references: list[
                tuple[str, str, str | None]
            ] = []
            supplied_references = _bounded_input_values(
                reference_evidence[raw_path],
                limit=MAX_SUPPLIED_REFERENCE_EVIDENCE_PER_FILE,
                label=f"reference evidence for {raw_path}",
            )
            for raw in supplied_references:
                if isinstance(raw, str):
                    kind = raw
                    detail = raw_path
                    related = None
                else:
                    kind = str(raw.get("kind", "direct_import_reference"))
                    detail = str(raw.get("detail", ""))
                    related = (
                        str(raw["related_path"])
                        if raw.get("related_path")
                        else None
                    )
                if kind not in {"direct_import_reference", "direct_symbol_reference"}:
                    raise ValueError("reference evidence kind must be direct import or symbol")
                related_normalized = (
                    normalize_repository_relative_path(related)
                    if related is not None
                    else None
                )
                if related_normalized is not None:
                    related_normalized = by_path_casefold.get(
                        related_normalized.casefold()
                    )
                normalized_references.append(
                    (kind, detail[:MAX_LEXICAL_MATCH_LENGTH], related_normalized)
                )
            for kind, detail, related in sorted(
                set(normalized_references),
                key=lambda item: (item[0], item[1], item[2] or ""),
            )[:MAX_REFERENCE_EVIDENCE_PER_FILE]:
                _add_evidence(
                    evidence,
                    canonical,
                    kind,
                    detail,
                    related_path=related,
                )

    validations = dict(filename_report.associated_tests)
    candidates: list[RankedCandidate] = []
    for path in sorted(evidence):
        capability = by_path.get(path)
        if capability is None:
            continue
        items = tuple(evidence[path])
        risks = tuple((risk_hints or {}).get(path, ()))
        score = calculate_actionability_score(
            path,
            items,
            risks=risks,
            capability=capability,
        )
        decision = derive_candidate_action(
            actionability_score=score.actionability_score,
            editability=capability.editability,
            readability=capability.readability,
            evidence=score.positive_evidence,
            read_policy=capability.read_policy,
            parser_support=capability.parser_support,
            authoritative_source=capability.authoritative_source,
        )
        if decision.action == "exclude":
            continue
        candidates.append(
            RankedCandidate(
                path=path,
                capability=capability,
                actionability=score,
                decision=decision,
                validation_candidates=tuple(validations.get(path, ())),
                role=_role_for(path, items),
            )
        )

    def sort_key(item: RankedCandidate) -> tuple[Any, ...]:
        kinds = {entry.kind for entry in item.positive_evidence}
        return (
            0 if "user_named_file" in kinds else 1,
            0 if "exact_filename_match" in kinds else 1,
            -item.actionability_score,
            item.path,
        )

    return tuple(sorted(candidates, key=sort_key)[:MAX_CANDIDATE_FILES])


rank_file_candidates = rank_candidates
